"""academy_status.py -- the one-screen view across all instances.

Behind ``/academy:desk`` (no argument) and ``/academy:status``.

Usage:

    py academy_status.py [--since YYYY-MM-DD | --since last] [--mark-visit]
                         [--usage] [--instances-only] [--json]
                         [--board DIR] [--workspace PATH]

Sections (plan section 7):

1. **Needs you**: tickets addressed to ``human`` that are not terminal; tickets
   blocked with ``human`` in ``waiting_on``; open packets with pending decisions.
2. **In flight**: non-terminal tickets between instances, counted by receiver and
   status.
3. **Came back** since the last visit: tickets delivered, and packets created, on or
   after the ``--since`` date. ``--since last`` reads the date of the last
   ``--mark-visit`` from ``~/.claude/academy/desk-last-visit`` (outside the board,
   so a visit makes no board commit); with no record it means the last 7 days.
4. **Instances**: for each workspace instance, whether its home exists and whether
   its academy.json is present, valid and in agreement with workspace.json.
5. **Usage** (``--usage``): the one-line week summary from usage_report.py.
6. **Overdue** (only when something is): the routine jobs that have gone quiet. The
   weekly usage review files a ``usage`` packet and settles the error ledger; when the
   newest ``usage`` packet is older than ``OVERDUE_DAYS`` (or there is none while the
   ledger has errors), the job is not doing its work, whatever its scheduler reports
   (2026-11-13: the weekly cloud task had "succeeded" every Sunday for five weeks
   while stopping at its first step, with no packet since 2026-09-28).

Read-only on the board and the homes; ``--mark-visit`` writes only the visit file.
"""

import argparse
import collections
import datetime as _dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

try:
    import academy_common as ac  # noqa: E402
except ImportError:  # vendored copy
    import _academy as ac  # noqa: E402
import board as boardlib  # noqa: E402
import packets as packetlib  # noqa: E402

VISIT_FILE = os.path.join("~", ".claude", "academy", "desk-last-visit")


def visit_path():
    return os.path.expanduser(VISIT_FILE)


def last_visit(default_days=7, today=None):
    try:
        with open(visit_path(), "r", encoding="utf-8") as fh:
            s = fh.read().strip()
        if ac.RE_DATE.match(s):
            return s
    except OSError:
        pass
    today = today or _dt.date.today()
    return (today - _dt.timedelta(days=default_days)).isoformat()


def mark_visit(date=None):
    ac.atomic_write(visit_path(), (date or ac.today()) + "\n")


def instance_health(name, row):
    """One instance's config state: (ok, message)."""
    home = row.get("home", "")
    if not os.path.isdir(home):
        return False, "home %s missing" % home
    cfg_path = os.path.join(home, ac.CONFIG_REL)
    if not os.path.isfile(cfg_path):
        return False, "no .claude/academy.json yet (not switched over)"
    try:
        cfg = ac.load_config(home)
    except ac.AcademyError as exc:
        return False, "config invalid: %s" % exc
    probs = []
    if cfg.get("instance") != name:
        probs.append("academy.json says %s" % cfg.get("instance"))
    for key in ("role", "domains", "ns"):
        if row.get(key) != cfg.get(key):
            probs.append("%s differs from workspace.json" % key)
    if probs:
        return False, "; ".join(probs)
    return True, "ok"


#: a weekly job is overdue after this many days without its packet
OVERDUE_DAYS = 10


def overdue(board, today=None):
    """Lines for the routine jobs that have gone quiet (empty when none has)."""
    today = today or _dt.date.today()
    out = []
    usage = sorted(str(p.get("created") or "") for p in packetlib.list_packets(board)
                   if p.get("kind") == "usage" and p.get("created"))
    errors, last_settle = 0, ""
    try:
        import error_ledger
        recs = error_ledger.read_all(board)
        week = (today - _dt.timedelta(days=7)).isoformat()
        errors = sum(1 for r in recs if r.get("t") == "error" and r.get("ts", "") >= week)
        settles = [r.get("ts", "")[:10] for r in recs if r.get("t") == "settle"]
        last_settle = max(settles) if settles else ""
    except Exception:           # the ledger is optional; its absence is not overdue
        recs = []
    if usage:
        try:
            age = (today - _dt.date.fromisoformat(usage[-1][:10])).days
        except ValueError:
            age = 0
        if age > OVERDUE_DAYS:
            out.append("weekly usage review: the last usage packet is of %s (%d days ago); the "
                       "weekly job is not filing one (check its last run, not its status)"
                       % (usage[-1][:10], age))
    elif recs:
        out.append("weekly usage review: no usage packet on the board, and the error ledger "
                   "has records; run /academy:usage --weekly or check the scheduled job")
    if recs and (out or not usage):
        out.append("error ledger: %s; %d error(s) in the last 7 days"
                   % ("last settled %s" % last_settle if last_settle else "never settled", errors))
    return out


def summary(board, workspace, since, include_instances=True):
    """The status dict (see the module docstring)."""
    tickets = boardlib.list_tickets(board, include_terminal=True)
    live = [t for t in tickets if t.get("status") not in ac.TERMINAL]
    needs = {
        "tickets_to_human": [t for t in live if t.get("to") == ac.HUMAN],
        "blocked_on_human": [t for t in live if t.get("status") == "blocked"
                             and ac.HUMAN in [str(w) for w in (t.get("waiting_on") or [])]],
        "packets": [p for p in packetlib.list_packets(board, only_open=True)],
    }
    flight = collections.defaultdict(collections.Counter)
    for t in live:
        if t.get("to") != ac.HUMAN:
            flight[t.get("to")][t.get("status")] += 1
    back_tickets = [t for t in tickets if t.get("status") == "delivered"
                    and str(t.get("updated") or "") >= since]
    back_packets = [p for p in packetlib.list_packets(board)
                    if str(p.get("created") or "") >= since]
    out = {
        "since": since,
        "needs_you": needs,
        "in_flight": {k: dict(v) for k, v in sorted(flight.items())},
        "came_back": {"tickets": back_tickets, "packets": back_packets},
        "overdue": overdue(board),
    }
    if include_instances:
        out["instances"] = {}
        for name, row in sorted(workspace.get("instances", {}).items()):
            ok, msg = instance_health(name, row)
            out["instances"][name] = {"ok": ok, "message": msg, "home": row.get("home")}
    return out


def _t(t):
    return "%s %s (%s -> %s, %s)" % (t.get("id"), t.get("title"), t.get("from"),
                                     t.get("to"), t.get("status"))


def _p(p):
    pend = p.get("_pending") or []
    tail = ("%d decision(s) pending" % len(pend)) if pend else "acknowledge"
    return "%s %s [%s, %s] %s" % (p.get("packet"), p.get("title"), p.get("instance"),
                                  p.get("kind"), tail)


#: rows of one kind the screen lists before it counts the rest (``--all`` lists every row)
SCREEN_ROWS = 12
RE_NUM = re.compile(r"\d+")
PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


def _short(text, width=160):
    """One line of at most ``width`` characters."""
    text = " ".join(str(text or "").split())
    return text if len(text) <= width else text[:width - 1].rstrip() + "…"


def _cut(rows, cap, what, key):
    """``(shown, line)``: the first ``cap`` rows, urgent first then newest, and a line that
    counts the rest by ``key`` (None when nothing was cut). Packets with a pending decision
    come before those to acknowledge. One screen is the point of the
    command: 286 waiting items printed in full were 48 000 characters."""
    def rank(r):
        m = RE_NUM.search(str(r.get("id") or r.get("packet") or ""))
        # a packet with a decision to make comes before one to acknowledge
        waits = 0 if r.get("_pending") or "packet" not in r else 1
        return (waits, PRIORITY_RANK.get(r.get("priority"), 1), -(int(m.group()) if m else 0))
    rows = sorted(rows, key=rank)
    if not cap or len(rows) <= cap:
        return rows, None
    counts = {}
    for r in rows[cap:]:
        counts[r.get(key) or "?"] = counts.get(r.get(key) or "?", 0) + 1
    by = ", ".join("%s %d" % kv for kv in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    return rows[:cap], "  ... and %d more %s (%s); --all lists them" % (len(rows) - cap, what, by)


def render(s, usage_line=None, cap=SCREEN_ROWS):
    out = []
    if s.get("overdue"):
        out.append("OVERDUE")
        out += ["  " + ln for ln in s["overdue"]]
    n = s["needs_you"]
    count = len(n["tickets_to_human"]) + len(n["blocked_on_human"]) + len(n["packets"])
    out.append("NEEDS YOU (%d)" % count)
    for rows, tag, what, key, fmt in (
            (n["tickets_to_human"], "ticket ", "tickets to you", "from", _t),
            (n["blocked_on_human"], "blocked", "tickets blocked on you", "to", _t),
            (n["packets"], "packet ", "packets", "instance", _p)):
        shown, more = _cut(rows, cap, what, key)
        out += ["  %s %s" % (tag, fmt(r)) for r in shown]
        if more:
            out.append(more)
    if not count:
        out.append("  nothing")
    out.append("IN FLIGHT")
    if not s["in_flight"]:
        out.append("  nothing")
    for inst, counts in s["in_flight"].items():
        out.append("  %-20s %s" % (inst, ", ".join("%s %d" % kv for kv in sorted(counts.items()))))
    cb = s["came_back"]
    out.append("CAME BACK since %s (%d)" % (s["since"], len(cb["tickets"]) + len(cb["packets"])))
    shown, more = _cut(cb["tickets"], cap, "delivered tickets", "to")
    for t in shown:
        out.append("  delivered " + _t(t) + (" -- %s" % _short(t.get("result"))
                                             if t.get("result") else ""))
    if more:
        out.append(more)
    shown, more = _cut(cb["packets"], cap, "packets", "instance")
    out += ["  packet    " + _p(p) for p in shown]
    if more:
        out.append(more)
    if "instances" in s:
        out.append("INSTANCES")
        for name, h in s["instances"].items():
            out.append("  %-20s %s" % (name, h["message"]))
    if usage_line:
        out.append("USAGE")
        out.append("  " + usage_line)
    return "\n".join(out) + "\n"


def _strip(obj):
    """Drop private '_' keys (paths, problems) for JSON output, keep _pending."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items()
                if not k.startswith("_") or k == "_pending"}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", default="last")
    ap.add_argument("--mark-visit", action="store_true")
    ap.add_argument("--usage", action="store_true")
    ap.add_argument("--instances-only", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="list every row (default: the first %d of each kind, urgent "
                         "first then newest, and a count of the rest)" % SCREEN_ROWS)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--board")
    ap.add_argument("--workspace")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        ws = ac.load_workspace(a.workspace)
        board = os.path.abspath(a.board or ws["board"])
        if a.instances_only:
            for name, row in sorted(ws.get("instances", {}).items()):
                ok, msg = instance_health(name, row)
                print("%-20s %-4s %s" % (name, "ok" if ok else "!!", msg))
            return 0
        since = last_visit() if a.since == "last" else a.since
        if not ac.RE_DATE.match(since):
            raise ac.AcademyError("--since wants YYYY-MM-DD or 'last'")
        s = summary(board, ws, since)
        usage_line = None
        if a.usage:
            import usage_report
            report, _start, _end = usage_report.build(days=7, workspace_path=a.workspace)
            usage_line = usage_report.render_brief(report, "7d")
            s["usage"] = usage_line
        if a.json:
            print(json.dumps(_strip(s), indent=2, ensure_ascii=False))
        else:
            sys.stdout.write(render(s, usage_line, cap=0 if a.all else SCREEN_ROWS))
        if a.mark_visit:
            mark_visit()
    except (ac.AcademyError, OSError, ValueError) as exc:
        print("academy_status: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
