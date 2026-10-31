"""error_ledger.py -- errors accumulate during the week and are settled weekly.

Usage:

    py error_ledger.py [hook]                    # PostToolUseFailure hook, event on stdin
    py error_ledger.py report [--days 7 | --since YYYY-MM-DD] [--json] [--workspace PATH]
    py error_ledger.py settle --packet P-NNNN [--quiet-days 7] [--workspace PATH]
    py error_ledger.py resolve SIG [SIG ...] [--note TEXT] [--by WHO] [--commit SHA] [--workspace PATH]

The ledger is ``<board>/.errors/<instance>.jsonl`` (one file per instance, so two
machines never merge-conflict; the board's SessionStart commit carries it). It is
append-only; each line is one JSON record:

    {"t": "error",   "ts", "session", "instance", "tool", "sig", "msg",
                     ["detail"], ["cmd"], ["cwd"], ["path"]}
    {"t": "settle",  "ts", "packet", "upto"}      # a weekly review took the errors up to ``upto``
    {"t": "resolve", "ts", "sig", "note", "by", ["commit"]}   # the class is closed

An *error class* is a signature: the tool plus the first line of the message with
paths, ids, numbers and hex normalised away. A class is **open** from its first
error record after its last ``resolve`` record. The weekly cycle:

1. ``hook`` accumulates every failed tool call, all week, silently (it never fails a
   tool call). It records a redacted, truncated message and, to make the error
   actionable: for Bash/PowerShell the head of the error output after the exit code
   (``detail``) and the head of the command (``cmd``, first line, redacted); for
   Read/Glob/Grep (and other file tools) the session's ``cwd`` and the ``path`` or
   pattern asked for. An identical record (the hook firing twice for one failure) is
   written once, and ``read_all`` drops identical lines already in a ledger;
2. ``report`` lists the classes seen in the window (new since the last settle) and
   the classes carried over from earlier weeks that are still open, with counts,
   sessions, first/last seen and how many weeks each has been open;
3. ``settle`` (run by the usage-analyst after it filed its packet) records that the
   week was reviewed, and closes every class that was reported before and has not
   recurred for ``--quiet-days`` days (solved by silence). A class that recurs
   carries over and its weeks-open count grows, which is what the analyst escalates.

``resolve`` closes classes by hand (the human's word: a fix landed, or accepted noise).
``--commit SHA`` records the fixing commit in the resolve record; a class whose last
resolve carries a commit and that then records a new error is a **regression** (state
``regression`` in the report, ahead of ``new`` and ``recurring``). A resolve without a
commit, and ``settle``'s resolve by silence, behave as before.
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
    """The first line; when it ends in ':' the reason is on the next line, keep that too."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    head = lines[0] if lines else ""
    if head.endswith(":") and len(lines) > 1:
        head += " " + lines[1].lstrip("- ")
    return redact(RE_WS.sub(" ", head))[:MSG_MAX]


def signature(tool, message):
    """Tool plus the message with paths, ids, numbers and quoted strings normalised."""
    s = first_line(message)
    s = RE_PATH.sub("<path>", s)
    s = re.sub(r"(['\"]).*?\1", "<q>", s)
    s = RE_ID.sub("<id>", s)
    s = RE_NUM.sub("<n>", s)
    return "%s: %s" % (tool or "?", RE_WS.sub(" ", s).lower()[:100])


#: a search or comparison whose last pipeline stage exits 1 with no output found nothing
NO_MATCH_CMD = re.compile(r"^\s*(?:grep|egrep|fgrep|rg|diff|cmp|test|\[)\b")


def is_no_match(tool, tool_input, err):
    """Bash ``... | grep x`` exiting 1 with nothing on stderr: an answer, not a fault."""
    if tool not in SHELL_TOOLS or not re.fullmatch(r"\s*exit code 1\s*", err or "", re.I):
        return False
    cmd = str((tool_input or {}).get("command") or "").strip().splitlines()[-1:] or [""]
    last = re.split(r"\|(?!\|)|&&|;", cmd[0])[-1]
    return bool(NO_MATCH_CMD.match(last))


def is_noise(message):
    return any(re.search(p, message or "", re.I) for p in SKIP_PATTERNS)


def board_path(workspace_path=None):
    return ac.load_workspace(workspace_path)["board"]


def ledger_file(board, instance):
    return os.path.join(board, LEDGER_DIR, re.sub(r"[^A-Za-z0-9@._-]", "_", instance) + ".jsonl")


TAIL_BYTES = 16384


def _tail_lines(path):
    """The last lines of ``path`` (about TAIL_BYTES), for the duplicate check."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            return fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []


def append(board, instance, record):
    """Append one record; a single write of one line, so concurrent sessions interleave
    whole lines. An error record identical to one near the end of the ledger (the same
    failure reported twice, e.g. by a hook registered twice) is not written again.
    Returns True when the line was written."""
    path = ledger_file(board, instance)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    if record.get("t") == "error" and line.rstrip("\n") in _tail_lines(path):
        return False
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
    return True


def read_all(board):
    """Every record of every instance's ledger, oldest first; bad lines are skipped."""
    root = os.path.join(board, LEDGER_DIR)
    out = []
    seen = set()
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
                if not (isinstance(rec, dict) and rec.get("ts") and rec.get("t")):
                    continue
                if rec["t"] == "error":     # identical duplicates count once
                    key = json.dumps(rec, sort_keys=True)
                    if key in seen:
                        continue
                    seen.add(key)
                out.append(rec)
    out.sort(key=lambda r: r["ts"])
    return out


def classes(records):
    """Open error classes: sig -> {sig, tool, msg, count, sessions, instances, first,
    last, reported} over the errors after each class's last ``resolve``. ``reported``
    is true when a settle happened at or after the class's first error."""
    last_resolve = {}
    last_commit = {}
    settles = []
    for r in records:
        if r["t"] == "resolve" and r.get("sig"):
            last_resolve[r["sig"]] = r["ts"]
            last_commit[r["sig"]] = r.get("commit") or ""
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
                                      "weeks": set(), "recs": []})
        c["recs"].append(r)
        c["count"] += 1
        c["sessions"].add(r.get("session") or "?")
        c["instances"].add(r.get("instance") or "?")
        c["last"] = r["ts"]
        c["weeks"].add(_parse(r["ts"]).strftime("%G-W%V"))
    for c in out.values():
        c["reported"] = any(u >= c["first"] for u in settles)
        # an error after a resolve that named its fixing commit: the fix did not hold
        c["regression_commit"] = last_commit.get(c["sig"], "")
    return out


#: (pattern on the message part of a signature, family reason); first match wins
FAMILY_RULES = [
    (re.compile(r"the grounds do not support"), "grounds do not support"),
    (re.compile(r"is not a transition"), "not a transition"),
    (re.compile(r"\bthe kb does not build"), "kb does not build"),
    (re.compile(r"\bdoes not exist\b"), "path does not exist"),
    # the egress error is a JSON object, which signature() reduces to its shape
    (re.compile(r"egress_blocked|enotfound|egress proxy|^\{<q>:<q>(,<q>:<q>)*\}$"),
     "host unreachable"),
    (re.compile(r"^agent .*(could act for|runs outside every academy home|belongs to the)"),
     "agent cannot act for the instance"),
    (re.compile(r"\bno domain pack\b"), "no domain pack"),
    (re.compile(r"\bdelivered needs result\b"), "delivered needs result"),
    (re.compile(r"\bdoes not contain the quote\b.*\bverbatim"), "quote not verbatim"),
    # the 2026-10-31 review: the remaining recurring reasons, one family each
    (re.compile(r"^deliver: true is for the receiver"), "deliver by a non-receiver"),
    (re.compile(r"\bis made by the (sender|receiver)"), "move made by the other party"),
    (re.compile(r"is not a liaison for|may not file to"), "ticket chain refusal"),
    (re.compile(r"exceeds maximum allowed (tokens|size)"), "file too large to read"),
    (re.compile(r"^eisdir\b"), "read a directory"),
    (re.compile(r"sent no response or progress"), "mcp timeout"),
]


def family(sig):
    """A coarser label for a class signature: the verb and the reason, without the
    normalised target (id, status, path, host). Falls back to the signature itself.
    The class keys (``signature``) are not touched; this only groups them for reading."""
    tool, sep, msg = sig.partition(": ")
    if not sep:
        return sig
    for pat, reason in FAMILY_RULES:
        if pat.search(msg):
            return "%s: %s" % (tool.rsplit("__", 1)[-1], reason)
    return sig


BASH_EXIT_SIG = "Bash: exit code <n>"


def cmd_word(cmd):
    """First word of a recorded command, folded to ``git``, ``py``, ``python3`` or
    ``other``; a record without a command is ``unknown cmd``."""
    words = (cmd or "").split()
    if not words:
        return "unknown cmd"
    w = words[0].rsplit("/", 1)[-1].lower()
    return w if w in ("git", "py", "python3") else "other"


def family_of(sig, rec=None):
    """``family(sig)``, except that the ``Bash: exit code`` class is split by the first
    word of the record's ``cmd`` (it needs the record, which the signature lacks)."""
    if sig == BASH_EXIT_SIG and rec is not None:
        return "Bash: exit code (%s)" % cmd_word(rec.get("cmd"))
    return family(sig)


#: records of one class in one session this close to the previous one are one occurrence
BURST_SECONDS = 60


def burst_starts(recs):
    """Ids of the records that open a burst: the first of a class in a session, or one
    more than ``BURST_SECONDS`` after the previous record of that class in that session.
    ``recs`` are the records of ONE class, oldest first."""
    last = {}
    starts = set()
    for rec in recs:
        key = rec.get("session") or "?"
        t = _parse(rec["ts"])
        prev = last.get(key)
        if prev is None or (t - prev).total_seconds() > BURST_SECONDS:
            starts.add(id(rec))
        last[key] = t
    return starts


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
    starts = {}
    for sig, c in cls.items():
        starts[sig] = burst_starts(c["recs"])
    for sig, c in cls.items():
        weeks_open = max(1, (now - _parse(c["first"])).days // 7 + 1)
        rows.append({"sig": sig, "tool": c["tool"], "msg": c["msg"], "count": c["count"],
                     "in_window": in_window.get(sig, 0),
                     "bursts": sum(1 for rec in c["recs"]
                                   if id(rec) in starts[sig] and rec["ts"] >= lo),
                     "sessions": len(c["sessions"]),
                     "instances": sorted(c["instances"]), "first": c["first"],
                     "last": c["last"], "weeks_open": weeks_open,
                     "distinct_weeks": len(c["weeks"]), "reported": c["reported"],
                     "regression": bool(c["regression_commit"]),
                     "regression_commit": c["regression_commit"],
                     # recurring: seen on three or more sessions, or in two calendar weeks
                     "recurring": len(c["sessions"]) >= 3 or len(c["weeks"]) >= 2})
    # class rows stay ordered by raw counts; only the families rank by bursts
    rows.sort(key=lambda r: (-r["in_window"], -r["count"], r["sig"]))
    fams = {}

    def fam_entry(name, r):
        return fams.setdefault(name, {"family": name, "in_window": 0, "bursts": 0, "count": 0,
                                      "classes": 0, "sessions": set(),
                                      "recurring": False, "regression": False,
                                      "example": r["msg"]})

    for r in rows:
        if r["sig"] == BASH_EXIT_SIG:  # split by command word, per record
            for rec in cls[r["sig"]]["recs"]:
                f = fam_entry(family_of(r["sig"], rec), r)
                f["count"] += 1
                f["in_window"] += 1 if rec["ts"] >= lo else 0
                f["bursts"] += 1 if id(rec) in starts[r["sig"]] and rec["ts"] >= lo else 0
                f["sessions"].add(rec.get("session") or "?")
                f["recurring"] = f["recurring"] or r["recurring"]
                f["regression"] = f["regression"] or r["regression"]
            for name in {family_of(r["sig"], rec) for rec in cls[r["sig"]]["recs"]}:
                fams[name]["classes"] += 1
            continue
        f = fam_entry(family(r["sig"]), r)
        f["in_window"] += r["in_window"]
        f["bursts"] += r["bursts"]
        f["count"] += r["count"]
        f["classes"] += 1
        f["recurring"] = f["recurring"] or r["recurring"]
        f["regression"] = f["regression"] or r["regression"]
        f["sessions"].update(cls[r["sig"]]["sessions"])
    families = sorted(({**f, "sessions": len(f["sessions"])} for f in fams.values()),
                      key=lambda f: (-f["bursts"], -f["count"], f["family"]))
    return {"window": {"start": start.strftime("%Y-%m-%d"), "end": now.strftime("%Y-%m-%d")},
            "errors_in_window": sum(in_window.values()),
            "families": families,
            "open_classes": len(rows),
            "recurring": [r for r in rows if r["recurring"]],
            "classes": rows}


def render_markdown(rep):
    w = rep["window"]
    out = ["# Errors %s .. %s" % (w["start"], w["end"]), "",
           "%d error(s) in the window; %d open class(es), %d recurring."
           % (rep["errors_in_window"], rep["open_classes"], len(rep["recurring"])), ""]
    fams = [f for f in rep.get("families", []) if f["in_window"]][:10]
    if fams:
        out += ["## Top families", "",
                "| family | in window | bursts | classes | sessions | state | example reason |",
                "|---|---|---|---|---|---|---|"]
        for f in fams:
            out.append("| `%s` | %d | %d | %d | %d | %s | %s |" % (
                f["family"].replace("|", "\\|"), f["in_window"], f["bursts"], f["classes"],
                f["sessions"],
                "regression" if f.get("regression") else "recurring" if f["recurring"] else "-",
                (f["example"] or "-").replace("|", "\\|")[:100]))
        out.append("")
    out += ["## Classes", "",
           "| class | in window | bursts | total | sessions | first | last | weeks open | state |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rep["classes"]:
        state = ("regression" if r.get("regression") else "recurring" if r["recurring"]
                 else "new" if not r["reported"] else "carried")
        out.append("| `%s` | %d | %d | %d | %d | %s | %s | %d | %s |" % (
            r["sig"].replace("|", "\\|"), r["in_window"], r["bursts"], r["count"], r["sessions"],
            r["first"][:10], r["last"][:10], r["weeks_open"], state))
    if not rep["classes"]:
        out.append("| none | | | | | | | | |")
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
    ti0 = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    if is_no_match(tool, ti0, err):
        return None
    rec = {"t": "error", "ts": _stamp(now or _now()), "session": event.get("session_id") or "",
           "instance": instance, "tool": tool, "sig": signature(tool, err),
           "msg": clean_message(err)}
    # the acting agent (additive, U2): "MAIN" for the main session, so a record without
    # the field is an old one; the namespace is kept ("author:math-writer")
    ns, bare = ac.agent_identity(event)
    rec["agent"] = redact(("%s:%s" % (ns, bare)) if ns else bare)[:80] if bare else "MAIN"
    rec.update(context(event, tool, err))
    return rec


SHELL_TOOLS = ("Bash", "PowerShell")
FILE_TOOLS = ("Read", "Glob", "Grep", "Edit", "Write", "MultiEdit", "NotebookEdit")
DETAIL_MAX = 400
CMD_MAX = 160


def _head(text, limit, lines=4):
    """The first ``lines`` non-empty lines of ``text``, whitespace-collapsed, redacted,
    at most ``limit`` characters."""
    got = [RE_WS.sub(" ", ln).strip() for ln in (text or "").splitlines() if ln.strip()]
    return redact(" | ".join(got[:lines]))[:limit]


def context(event, tool, err):
    """What makes a failure actionable: the shell's error output and command head, or a
    file tool's cwd and path. Redacted and truncated; {} for other tools."""
    ti = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    out = {}
    if tool in SHELL_TOOLS:
        lines = [ln for ln in (err or "").splitlines() if ln.strip()]
        rest = lines[1:] if lines and re.match(r"(?i)^\s*exit code", lines[0]) else lines
        detail = _head("\n".join(rest), DETAIL_MAX)
        if detail:
            out["detail"] = detail
        cmd = _head(str(ti.get("command") or ""), CMD_MAX, lines=1)
        if cmd:
            out["cmd"] = cmd
    elif tool in FILE_TOOLS:
        cwd = event.get("cwd") if isinstance(event.get("cwd"), str) else ""
        if cwd:
            out["cwd"] = str(cwd).replace("\\", "/")
        target = ti.get("file_path") or ti.get("path") or ti.get("notebook_path")
        if target:
            out["path"] = str(target).replace("\\", "/")[:CMD_MAX]
        if ti.get("pattern"):
            out["pattern"] = redact(str(ti["pattern"]))[:CMD_MAX]
    return out


def _in_workspace(cwd):
    try:
        root = os.path.dirname(ac.load_workspace()["_path"])
    except (ac.AcademyError, KeyError):
        return False
    a, r = (os.path.normcase(os.path.realpath(x)) for x in (cwd, root))
    return a == r or a.startswith(r.rstrip(os.sep) + os.sep)


def _instance_for(event):
    """The instance of the home the failing session runs in; 'workspace' for a cwd
    inside the workspace root that is no instance home; else 'other'."""
    cwd = ac.event_cwd(event)
    home = ac.find_home(cwd)
    if not home:
        return "workspace" if _in_workspace(cwd) else "other"
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
    p.add_argument("--commit", default="", help="the fixing commit; a later error is a regression")
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
            rec = {"t": "resolve", "ts": now, "sig": sig, "by": a.by, "note": a.note}
            if a.commit:
                rec["commit"] = a.commit
            append(board, instance, rec)
        print("resolved %d class(es)" % len(a.sig))
    return 0


if __name__ == "__main__":
    sys.exit(main())
