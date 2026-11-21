"""audit.py -- the consistency audit of the board and the registry (academy #111).

Read-only. It lists every state that contradicts its own evidence, by class, with the ids
and a suggested fix, so that nobody has to find them by hand:

* tickets (the board):
  - ``ticket-waiting-done``: blocked, and every ticket it waits on (not ``human``) has ended
    (delivered, closed, rejected, cancelled), so nothing will release it;
  - ``ticket-waiting-unknown``: blocked on a ticket id the board does not have;
  - ``ticket-in-progress-idle``: in progress and not updated for ``--idle-days`` days;
  - ``ticket-delivered-no-result``: delivered with an empty result line (#100);
* packets:
  - ``packet-duplicate-id``: one packet id in two files (#90);
  - ``packet-open-all-decided``: open although every decision has its line in
    ``## Decision`` (the template says it is then ``decided``);
  - ``packet-open-no-decisions``: open with ``## Decisions needed`` "None." (it asks only
    for an acknowledgement);
  - ``packet-malformed``: ``validate_packet`` problems;
* claims (``registry.py stale --json``, run from every home with a namespace):
  - ``claim-stale-hash``: proved or proved-modulo, the statement changed since its last
    positive review pass;
  - ``claim-no-positive-pass``: proved or proved-modulo, review passes on record and none
    positive (for example proved on the human's word with a GAP review, #85).

Not covered yet (#111): the draft colour against the registry status (``check_paper.py``
reports colour rules within the paper) and tickets cancelled although their work was
delivered (needs the thread, not the listing).

    py audit.py [--json] [--class C ...] [--idle-days N] [--limit N]
                [--no-tickets] [--no-packets] [--no-registry]

The exit status is 0 whatever is found (it reports; ``/academy:audit`` reads it). Each
finding is ``{"class", "id", "detail", "fix"}``.
"""

import argparse
import collections
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board as boardlib  # noqa: E402
import packets as packetlib  # noqa: E402

TICKET_ID = re.compile(r"^T-\d+$")

#: a ticket in one of these has ended: nothing more comes from it
ENDED = ("delivered", "closed", "rejected", "cancelled")

#: the classes, in report order, with a one-line description
CLASSES = collections.OrderedDict([
    ("ticket-waiting-done", "blocked, and every ticket it waits on has ended"),
    ("ticket-waiting-unknown", "blocked on a ticket the board does not have"),
    ("ticket-in-progress-idle", "in progress, not updated for days"),
    ("ticket-delivered-no-result", "delivered with no result"),
    ("packet-duplicate-id", "one packet id in two files"),
    ("packet-open-all-decided", "open although every decision is recorded"),
    ("packet-open-no-decisions", "open, asks for no decision (acknowledgement only)"),
    ("packet-malformed", "fails the packet template's checks"),
    ("claim-stale-hash", "proved, statement changed since its last positive pass"),
    ("claim-no-positive-pass", "proved, review passes on record and none positive"),
])


def finding(cls, fid, detail, fix):
    return {"class": cls, "id": fid, "detail": detail, "fix": fix}


def _date(s):
    try:
        return datetime.date.fromisoformat(str(s or "")[:10])
    except ValueError:
        return None


def audit_tickets(tickets, today, idle_days=3):
    """Findings over the board's ticket metas (every status, terminal ones included)."""
    by = {str(t.get("id")): t for t in tickets if t.get("id")}
    out = []
    for t in sorted(by.values(), key=lambda m: int(str(m.get("id", "T-0")).split("-")[1] or 0)):
        tid, st = str(t["id"]), t.get("status")
        if st == "blocked":
            waits = [str(w) for w in (t.get("waiting_on") or [])]
            ids = [w for w in waits if w != ac.HUMAN]
            unknown = [w for w in ids if w not in by]
            if unknown:
                named = ["%s (%s)" % (w, "not on the board" if TICKET_ID.match(w) else "no ticket id: an instance or role name")
                         for w in unknown]
                out.append(finding("ticket-waiting-unknown", tid, "waits on " + ", ".join(named),
                                   "correct waiting_on, or release %s (board transition %s open)" % (tid, tid)))
            elif ids and ac.HUMAN not in waits and all(by[w].get("status") in ENDED for w in ids):
                ended = ", ".join("%s %s" % (w, by[w].get("status")) for w in ids)
                out.append(finding("ticket-waiting-done", tid, "waits on %s" % ended,
                                   "release it: board transition %s open (its waits ended)" % tid))
        elif st == "in-progress":
            d = _date(t.get("updated"))
            if d is not None and (today - d).days >= idle_days:
                out.append(finding("ticket-in-progress-idle", tid,
                                   "in progress, last updated %s (%d days)" % (d.isoformat(), (today - d).days),
                                   "check for a live run; if none, put it back (board transition %s accepted)" % tid))
        elif st == "delivered" and not str(t.get("result") or "").strip():
            out.append(finding("ticket-delivered-no-result", tid, "delivered with no result line",
                               "name the artefact in its result, or reopen it if none exists (#100)"))
    return out


def audit_packets(rows):
    """Findings over packet rows: ``packets.list_packets`` metas, each with ``_asked`` (the
    decision numbers it asks), ``_pending`` and ``_problems``."""
    out = []
    files = collections.defaultdict(list)
    for m in rows:
        files[str(m.get("packet"))].append(m.get("_path") or "?")
    for pid, paths in sorted(files.items()):
        if len(paths) > 1:
            out.append(finding("packet-duplicate-id", pid, "%d files: %s" % (len(paths), "; ".join(
                os.path.basename(p) for p in paths)), "renumber all but the first (packets.py new numbers from the counter, #90)"))
    for m in rows:
        pid = str(m.get("packet"))
        if m.get("_problems"):
            out.append(finding("packet-malformed", pid, "; ".join(m["_problems"]),
                               "fix the packet to the template (docs/packet-template.md)"))
        if m.get("state") != "open":
            continue
        asked = m.get("_asked") or []
        if asked and not m.get("_pending"):
            out.append(finding("packet-open-all-decided", pid, "every decision (%s) has its line"
                               % ", ".join("D%d" % k for k in asked),
                               "set state: decided and decided: <date> (packets.py decide records it so)"))
        elif not asked:
            out.append(finding("packet-open-no-decisions", pid, "asks for no decision",
                               "acknowledge it in /academy:review, which closes it"))
    return out


def audit_claims(items):
    """Findings over ``registry.py stale --json`` items (each with ``kind``, ``qid``,
    ``status``, ``pass``, ``hold``), deduplicated by ``qid``."""
    out, seen = [], set()
    for it in sorted(items, key=lambda i: (i.get("qid") or "")):
        q = it.get("qid")
        if not q or q in seen:
            continue
        seen.add(q)
        if it.get("kind") == "stale":
            out.append(finding("claim-stale-hash", q, "%s; statement changed since pass %s%s" % (
                it.get("status"), it.get("pass") or "?", "; " + it["hold"] if it.get("hold") else ""),
                "registry.py stale --file-reword (a reword verify)" if not it.get("hold") else "a blind verify, or the human decides"))
        elif it.get("kind") == "unreviewed":
            out.append(finding("claim-no-positive-pass", q, it.get("hold") or it.get("status") or "",
                               "the human decides: a blind verify, or the status reverts to what the reviews support"))
    return out


# ---- gathering (the only part that reads the workspace) ---------------------------------

def gather_packets(board):
    rows = []
    for m in packetlib.list_packets(board):
        try:
            _meta, body = packetlib.read_packet(m["_path"])
            m["_asked"] = sorted(ac.packet_decisions(body))
        except Exception:                        # unreadable since the listing: say nothing new
            m["_asked"] = []
        rows.append(m)
    return rows


def gather_stale(workspace, problems):
    """``registry.py stale --json`` from every home with a namespace; a home that fails is
    named in ``problems``, never silently left out."""
    reg = os.path.join(HERE, "registry.py")
    items = []
    for name, inst in sorted((workspace.get("instances") or {}).items()):
        home = inst.get("home")
        if not inst.get("ns") and inst.get("role") != "author":
            continue
        if not home or not os.path.isdir(home):
            problems.append("%s: home %s missing, its claims not audited" % (name, home))
            continue
        try:
            p = subprocess.run([sys.executable, reg, "stale", "--json"], cwd=home, capture_output=True,
                               text=True, encoding="utf-8", timeout=300)
            items += json.loads(p.stdout or "{}").get("items") or []
        except (subprocess.SubprocessError, ValueError, OSError) as e:
            problems.append("%s: registry.py stale failed (%s)" % (name, e))
    return items


def render(findings, problems, limit=10):
    by = collections.defaultdict(list)
    for f in findings:
        by[f["class"]].append(f)
    lines = ["Academy audit: %d finding(s) in %d class(es)" % (len(findings), len(by))]
    for cls, desc in CLASSES.items():
        fs = by.get(cls)
        if not fs:
            continue
        lines.append("")
        lines.append("%s (%d): %s" % (cls, len(fs), desc))
        for f in fs[:limit] if limit else fs:
            lines.append("  %s  %s  -> %s" % (f["id"], f["detail"], f["fix"]))
        if limit and len(fs) > limit:
            lines.append("  ... and %d more (--limit 0 for all)" % (len(fs) - limit))
    if problems:
        lines.append("")
        lines.append("Not audited:")
        lines += ["  " + p for p in problems]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--board")
    ap.add_argument("--workspace")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--class", dest="classes", action="append", choices=list(CLASSES), help="only this class (repeatable)")
    ap.add_argument("--idle-days", type=int, default=3)
    ap.add_argument("--limit", type=int, default=10, help="rows per class in the text report (0 = all)")
    ap.add_argument("--today", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--no-tickets", action="store_true")
    ap.add_argument("--no-packets", action="store_true")
    ap.add_argument("--no-registry", action="store_true")
    a = ap.parse_args(argv)
    today = _date(a.today) or datetime.date.fromisoformat(ac.today())
    # tickets from the store board.backend names (GitHub issues, or the files); packets are
    # always files in the board directory
    board = boardlib.resolve_board(a.board, a.workspace)
    findings, problems = [], []
    if not a.no_tickets:
        store = boardlib.resolve_store(a.board, a.workspace)
        findings += audit_tickets(boardlib.list_tickets(store, include_terminal=True), today, a.idle_days)
    if not a.no_packets:
        findings += audit_packets(gather_packets(board))
    if not a.no_registry:
        ws = ac.load_workspace(a.workspace)
        findings += audit_claims(gather_stale(ws, problems))
    if a.classes:
        findings = [f for f in findings if f["class"] in a.classes]
    order = {c: i for i, c in enumerate(CLASSES)}
    findings.sort(key=lambda f: order[f["class"]])
    if a.json:
        print(json.dumps({"findings": findings, "counts": dict(collections.Counter(f["class"] for f in findings)),
                          "not_audited": problems}, indent=2, ensure_ascii=False))
    else:
        boardlib._utf8_stdout()
        print(render(findings, problems, a.limit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
