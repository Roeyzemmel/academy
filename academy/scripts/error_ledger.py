"""error_ledger.py -- errors accumulate during the week and are settled weekly.

Usage:

    py error_ledger.py [hook]                    # PostToolUseFailure hook, event on stdin
    py error_ledger.py report [--days 7 | --since YYYY-MM-DD] [--json] [--workspace PATH]
    py error_ledger.py settle --packet P-NNNN [--quiet-days 7] [--workspace PATH]
    py error_ledger.py resolve SIG [SIG ...] [--note TEXT] [--by WHO] [--workspace PATH]

The ledger is ``<board>/.errors/<instance>.jsonl`` (one file per instance, so two
machines never merge-conflict; the board's SessionStart commit carries it). It is
append-only; each line is one JSON record:

    {"t": "error",   "ts", "session", "instance", "tool", "sig", "msg"}
    {"t": "settle",  "ts", "packet", "upto"}      # a weekly review took the errors up to ``upto``
    {"t": "resolve", "ts", "sig", "note", "by"}   # the class is closed

An *error class* is a signature: the tool plus the first line of the message with
paths, ids, numbers and hex normalised away. A class is **open** from its first
error record after its last ``resolve`` record. The weekly cycle:

1. ``hook`` accumulates every failed tool call, all week, silently (it never fails a
   tool call, and never records a command line or tool input, only a redacted,
   truncated message);
2. ``report`` lists the classes seen in the window (new since the last settle) and
   the classes carried over from earlier weeks that are still open, with counts,
   sessions, first/last seen and how many weeks each has been open;
3. ``settle`` (run by the usage-analyst after it filed its packet) records that the
   week was reviewed, and closes every class that was reported before and has not
   recurred for ``--quiet-days`` days (solved by silence). A class that recurs
   carries over and its weeks-open count grows, which is what the analyst escalates.

``resolve`` closes classes by hand (the human's word: a fix landed, or accepted noise).
"""

import argparse
import collections
import datetime as _dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402

LEDGER_DIR = ".errors"
MSG_MAX = 240
#: an error that is the human declining or interrupting a call is not a fault
SKIP_PATTERNS = (r"user (doesn't|does not) want to proceed", r"permission (was )?denied by the user",
                 r"the user rejected", r"request interrupted")
SECRET_PATTERNS = (r"gh[pousr]_[A-Za-z0-9]{20,}", r"sk-[A-Za-z0-9_-]{16,}",
                   r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{12,}",
                   r"(?i)(token|secret|password|api[_-]?key)\s*[=:]\s*\S+")
RE_PATH = re.compile(r"(?:[A-Za-z]:)?[\\/](?:[\w.@ -]+[\\/])+[\w.@-]*|~[\\/][\w./\\-]*")
RE_ID = re.compile(r"\b(?:[TP]-\d{4,}|session_[A-Za-z0-9]+|[0-9a-f]{7,}|[0-9a-f-]{32,})\b")
RE_NUM = re.compile(r"\d+")
RE_WS = re.compile(r"\s+")


def _now():
    return _dt.datetime.now().replace(microsecond=0)


def _stamp(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S")


def _parse(ts):
    return _dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")


def redact(text):
    for pat in SECRET_PATTERNS:
        text = re.sub(pat, "<redacted>", text)
    return text


def first_line(text):
    for ln in (text or "").splitlines():
        if ln.strip():
            return ln.strip()
    return ""


def clean_message(text):
    return redact(RE_WS.sub(" ", first_line(text)))[:MSG_MAX]


def signature(tool, message):
    """Tool plus the message with paths, ids, numbers and quoted strings normalised."""
    s = first_line(message)
    s = RE_PATH.sub("<path>", s)
    s = re.sub(r"(['\"]).*?\1", "<q>", s)
    s = RE_ID.sub("<id>", s)
    s = RE_NUM.sub("<n>", s)
    return "%s: %s" % (tool or "?", RE_WS.sub(" ", s).lower()[:100])


def is_noise(message):
    return any(re.search(p, message or "", re.I) for p in SKIP_PATTERNS)


def board_path(workspace_path=None):
    return ac.load_workspace(workspace_path)["board"]


def ledger_file(board, instance):
    return os.path.join(board, LEDGER_DIR, re.sub(r"[^A-Za-z0-9@._-]", "_", instance) + ".jsonl")


def append(board, instance, record):
    """Append one record; a single write of one line, so concurrent sessions interleave
    whole lines."""
    path = ledger_file(board, instance)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)


def read_all(board):
    """Every record of every instance's ledger, oldest first; bad lines are skipped."""
    root = os.path.join(board, LEDGER_DIR)
    out = []
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return out
    for name in names:
        if not name.endswith(".jsonl"):
            continue
        with open(os.path.join(root, name), "r", encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    rec = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(rec, dict) and rec.get("ts") and rec.get("t"):
                    out.append(rec)
    out.sort(key=lambda r: r["ts"])
    return out


def classes(records):
    """Open error classes: sig -> {sig, tool, msg, count, sessions, instances, first,
    last, reported} over the errors after each class's last ``resolve``. ``reported``
    is true when a settle happened at or after the class's first error."""
    last_resolve = {}
    settles = []
    for r in records:
        if r["t"] == "resolve" and r.get("sig"):
            last_resolve[r["sig"]] = r["ts"]
        elif r["t"] == "settle":
            settles.append(r.get("upto") or r["ts"])
    out = {}
    for r in records:
        if r["t"] != "error" or not r.get("sig"):
            continue
        if r["ts"] <= last_resolve.get(r["sig"], ""):
            continue
        c = out.setdefault(r["sig"], {"sig": r["sig"], "tool": r.get("tool", "?"),
                                      "msg": r.get("msg", ""), "count": 0,
                                      "sessions": set(), "instances": set(),
                                      "first": r["ts"], "last": r["ts"],
                                      "weeks": set()})
        c["count"] += 1
        c["sessions"].add(r.get("session") or "?")
        c["instances"].add(r.get("instance") or "?")
        c["last"] = r["ts"]
        c["weeks"].add(_parse(r["ts"]).strftime("%G-W%V"))
    for c in out.values():
        c["reported"] = any(u >= c["first"] for u in settles)
    return out


def report(records, start, now=None):
    """The weekly picture: every open class, with its count inside the window
    (``in_window``; 0 for a class carried over from an earlier week) and its total."""
    now = now or _now()
    lo = _stamp(start)
    cls = classes(records)
    in_window = collections.Counter()
    for r in records:
        if r["t"] == "error" and r["ts"] >= lo and r.get("sig") in cls:
            in_window[r["sig"]] += 1
    rows = []
    for sig, c in cls.items():
        weeks_open = max(1, (now - _parse(c["first"])).days // 7 + 1)
        rows.append({"sig": sig, "tool": c["tool"], "msg": c["msg"], "count": c["count"],
                     "in_window": in_window.get(sig, 0), "sessions": len(c["sessions"]),
                     "instances": sorted(c["instances"]), "first": c["first"],
                     "last": c["last"], "weeks_open": weeks_open,
                     "distinct_weeks": len(c["weeks"]), "reported": c["reported"],
                     # recurring: seen on three or more sessions, or in two calendar weeks
                     "recurring": len(c["sessions"]) >= 3 or len(c["weeks"]) >= 2})
    rows.sort(key=lambda r: (-r["in_window"], -r["count"], r["sig"]))
    return {"window": {"start": start.strftime("%Y-%m-%d"), "end": now.strftime("%Y-%m-%d")},
            "errors_in_window": sum(in_window.values()),
            "open_classes": len(rows),
            "recurring": [r for r in rows if r["recurring"]],
            "classes": rows}


def render_markdown(rep):
    w = rep["window"]
    out = ["# Errors %s .. %s" % (w["start"], w["end"]), "",
           "%d error(s) in the window; %d open class(es), %d recurring."
           % (rep["errors_in_window"], rep["open_classes"], len(rep["recurring"])), "",
           "| class | in window | total | sessions | first | last | weeks open | state |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rep["classes"]:
        state = ("recurring" if r["recurring"] else "new" if not r["reported"] else "carried")
        out.append("| `%s` | %d | %d | %d | %s | %s | %d | %s |" % (
            r["sig"].replace("|", "\\|"), r["in_window"], r["count"], r["sessions"],
            r["first"][:10], r["last"][:10], r["weeks_open"], state))
    if not rep["classes"]:
        out.append("| none | | | | | | | |")
    out += ["", "Example messages:", ""]
    for r in rep["classes"][:10]:
        out.append("- `%s`: %s" % (r["sig"].replace("|", "\\|"), r["msg"] or "-"))
    return "\n".join(out) + "\n"


def settle(board, instance, packet, quiet_days=7, now=None):
    """Record the weekly review; close classes reported earlier and quiet since.

    Returns the list of signatures it closed."""
    now = now or _now()
    records = read_all(board)
    cutoff = _stamp(now - _dt.timedelta(days=quiet_days))
    closed = []
    for sig, c in sorted(classes(records).items()):
        if c["reported"] and c["last"] < cutoff:
            closed.append(sig)
    for sig in closed:
        append(board, instance, {"t": "resolve", "ts": _stamp(now), "sig": sig, "by": "settle",
                                 "note": "quiet for %d days after being reported" % quiet_days})
    append(board, instance, {"t": "settle", "ts": _stamp(now), "upto": _stamp(now),
                             "packet": packet, "closed": len(closed)})
    return closed


def hook_record(event, instance, now=None):
    """The ledger line for a PostToolUseFailure event, or None when it is not a fault."""
    if event.get("is_interrupt"):
        return None
    err = event.get("error")
    err = err if isinstance(err, str) else json.dumps(err) if err else ""
    if not err.strip() or is_noise(err):
        return None
    tool = ac.tool_name(event) or "?"
    return {"t": "error", "ts": _stamp(now or _now()), "session": event.get("session_id") or "",
            "instance": instance, "tool": tool, "sig": signature(tool, err),
            "msg": clean_message(err)}


def _instance_for(event):
    """The instance of the home the failing session runs in, or 'other'."""
    home = ac.find_home(ac.event_cwd(event))
    if not home:
        return "other"
    try:
        return ac.load_config(home).get("instance") or "other"
    except ac.AcademyError:
        return "other"


def run_hook(stream=None):
    """Never raises and never blocks: a ledger problem must not fail a tool call."""
    try:
        event = ac.read_event(stream)
        instance = _instance_for(event)
        rec = hook_record(event, instance)
        if rec is None:
            return 0
        append(board_path(), instance, rec)
    except Exception:
        pass
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")  # no subcommand: the hook, event on stdin
    sub.add_parser("hook")
    p = sub.add_parser("report")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--days", type=int, default=None)
    g.add_argument("--since")
    p.add_argument("--json", action="store_true")
    p.add_argument("--workspace")
    p = sub.add_parser("settle")
    p.add_argument("--packet", required=True)
    p.add_argument("--quiet-days", type=int, default=7)
    p.add_argument("--instance", help="ledger file to note the settle in (default: cwd's home)")
    p.add_argument("--workspace")
    p = sub.add_parser("resolve")
    p.add_argument("sig", nargs="+")
    p.add_argument("--note", default="")
    p.add_argument("--by", default="human")
    p.add_argument("--instance")
    p.add_argument("--workspace")
    a = ap.parse_args(argv)
    if a.cmd in (None, "hook"):
        return run_hook()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        board = board_path(a.workspace)
    except ac.AcademyError as e:
        print("error_ledger: %s" % e, file=sys.stderr)
        return 2
    instance = getattr(a, "instance", None) or _instance_for({})
    if a.cmd == "report":
        now = _now()
        if a.since:
            start = _dt.datetime.strptime(a.since, "%Y-%m-%d")
        else:
            start = now - _dt.timedelta(days=a.days if a.days is not None else 7)
        rep = report(read_all(board), start, now)
        if a.json:
            print(json.dumps(rep, indent=2))
        else:
            sys.stdout.write(render_markdown(rep))
    elif a.cmd == "settle":
        closed = settle(board, instance, a.packet, a.quiet_days)
        print("settled %s: %d class(es) closed" % (a.packet, len(closed)))
        for sig in closed:
            print("  closed: " + sig)
    elif a.cmd == "resolve":
        now = _stamp(_now())
        for sig in a.sig:
            append(board, instance, {"t": "resolve", "ts": now, "sig": sig, "by": a.by,
                                     "note": a.note})
        print("resolved %d class(es)" % len(a.sig))
    return 0


if __name__ == "__main__":
    sys.exit(main())
