"""audit.py -- the consistency audit of the board and the registry (academy #111).

Read-only. It lists every state that contradicts its own evidence, by class, with the ids
and a suggested fix, so that nobody has to find them by hand:

* tickets (the board):
  - ``ticket-waiting-done``: blocked, and every ticket it waits on has ended. A wait on an
    instance or on ``human`` is a legal wait that never ends here (protocol.md: waiting_on
    holds ticket ids, instances or ``human``). A child that is ``delivered`` means the return
    leg is due (the inbox takes it); only children that are all closed, rejected or
    cancelled call for a release (``blocked -> accepted``, waiting_on cleared);
  - ``ticket-waiting-unknown``: blocked on a ticket id the board does not have;
  - ``ticket-waiting-malformed``: a waiting_on entry that is no ticket id, instance or
    ``human``;
  - ``ticket-in-progress-idle``: in progress and not updated for ``--idle-days`` days;
  - ``ticket-delivered-no-result``: delivered with an empty result line (#100);
* packets:
  - ``packet-unreadable``: a packet file whose frontmatter does not parse;
  - ``packet-duplicate-id``: one packet id in two files (#90);
  - ``packet-open-all-decided``: open although every decision has its line in
    ``## Decision`` (for an informational packet: its ``D0`` acknowledgement is there); the
    template says it is then ``decided``. An informational packet still waiting for its
    acknowledgement is a pending item, not a contradiction, and is not listed;
  - ``packet-malformed``: ``validate_packet`` problems;
* claims (``registry.py stale --json``, run from every home with a namespace):
  - ``claim-stale-hash``: proved or proved-modulo, the statement changed since its last
    positive review pass;
  - ``claim-no-positive-pass``: proved or proved-modulo, review passes on record and none
    positive (for example proved on the human's word with a GAP review, #85).
  A claim an open verify ticket already covers is counted in the report's "Covered" line,
  not listed (``--covered`` lists it).

Not covered yet (#111): the draft colour against the registry status (``check_paper.py``
reports colour rules within the paper) and tickets cancelled although their work was
delivered (needs the thread, not the listing).

    py audit.py [--json] [--class C ...] [--idle-days N] [--limit N] [--covered]
                [--no-tickets] [--no-packets] [--no-registry]

The exit status is 0 whatever is found (it reports; ``/academy:audit`` reads it). Each
finding is ``{"class", "id", "detail", "fix"}``; a source that could not be read is named
under "Not audited" (``not_audited`` in the JSON), never left out silently.
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
    ("ticket-waiting-malformed", "a waiting_on entry that is no ticket, instance or human"),
    ("ticket-in-progress-idle", "in progress, not updated for days"),
    ("ticket-delivered-no-result", "delivered with no result"),
    ("packet-unreadable", "a packet file that does not parse"),
    ("packet-duplicate-id", "one packet id in two files"),
    ("packet-open-all-decided", "open although every decision is recorded"),
    ("packet-malformed", "fails the packet template's checks"),
    ("claim-stale-hash", "proved, statement changed since its last positive pass"),
    ("claim-no-positive-pass", "proved, review passes on record and none positive"),
])

RELEASE = "release it: board transition %s accepted (waiting_on cleared)"


def finding(cls, fid, detail, fix):
    return {"class": cls, "id": fid, "detail": detail, "fix": fix}


def _date(s):
    try:
        return datetime.date.fromisoformat(str(s or "")[:10])
    except ValueError:
        return None


def _num(tid):
    try:
        return int(str(tid).split("-")[1])
    except (IndexError, ValueError):
        return 0


def audit_tickets(tickets, today, idle_days=3):
    """Findings over the board's ticket metas (every status, terminal ones included)."""
    by = {str(t.get("id")): t for t in tickets if t.get("id")}
    out = []
    for t in sorted(by.values(), key=lambda m: _num(m.get("id"))):
        tid, st = str(t["id"]), t.get("status")
        if st == "blocked":
            waits = [str(w).strip() for w in (t.get("waiting_on") or [])]
            ids = [w for w in waits if TICKET_ID.match(w)]
            legal = [w for w in waits if w == ac.HUMAN or ac.RE_INSTANCE.match(w)]
            bad = [w for w in waits if w not in ids and w not in legal]
            unknown = [w for w in ids if w not in by]
            if bad:
                out.append(finding("ticket-waiting-malformed", tid, "waiting_on %s: no ticket id, instance or human"
                                   % ", ".join(repr(w) for w in bad),
                                   "rewrite waiting_on as ticket ids, instances or human"))
            if unknown:
                out.append(finding("ticket-waiting-unknown", tid, "waits on %s, not on the board" % ", ".join(unknown),
                                   "correct waiting_on to the ticket meant"))
            elif ids and not legal and not bad and all(by[w].get("status") in ENDED for w in ids):
                ended = ", ".join("%s %s" % (w, by[w].get("status")) for w in ids)
                if any(by[w].get("status") == "delivered" for w in ids):
                    fix = ("the return leg is due: run the inbox for %s, which takes it; if the inbox does not, "
                           % (t.get("to") or "its instance")) + RELEASE % tid
                else:
                    fix = RELEASE % tid + " (every wait closed without a delivery)"
                out.append(finding("ticket-waiting-done", tid, "waits on %s" % ended, fix))
        elif st == "in-progress":
            d = _date(t.get("updated"))
            if d is not None and (today - d).days >= idle_days:
                out.append(finding("ticket-in-progress-idle", tid,
                                   "in progress, last updated %s (%d days)" % (d.isoformat(), (today - d).days),
                                   "check for a live run; if none, put it back (board transition %s accepted)" % tid))
        elif st == "delivered" and not str(t.get("result") or "").strip():
            out.append(finding("ticket-delivered-no-result", tid, "delivered with no result line",
                               "name the artefact in its result, or return it (delivered -> in-progress) if none exists (#100)"))
    return out


def audit_packets(rows):
    """Findings over packet rows: ``packets.list_packets`` metas, each with ``_asked`` (the
    decision numbers it asks), ``_answered`` (those with a line in ``## Decision``, 0 for an
    informational packet's acknowledgement), ``_pending`` and ``_problems``; a row with
    ``_unreadable`` set is a file that did not parse."""
    out = []
    files = collections.defaultdict(list)
    for m in rows:
        if m.get("_unreadable"):
            out.append(finding("packet-unreadable", os.path.basename(m.get("_path") or "?"), m["_unreadable"],
                               "repair its frontmatter to the template (docs/packet-template.md)"))
            continue
        files[str(m.get("packet"))].append(m.get("_path") or "?")
    for pid, paths in sorted(files.items()):
        if len(paths) > 1:
            out.append(finding("packet-duplicate-id", pid, "%d files: %s" % (len(paths), "; ".join(
                os.path.basename(p) for p in paths)), "renumber all but the first (packets.py new numbers from the counter, #90)"))
    for m in rows:
        if m.get("_unreadable"):
            continue
        pid = str(m.get("packet"))
        if m.get("_problems"):
            out.append(finding("packet-malformed", pid, "; ".join(m["_problems"]),
                               "fix the packet to the template (docs/packet-template.md)"))
        if m.get("state") != "open":
            continue
        asked, answered = m.get("_asked") or [], m.get("_answered") or []
        if asked and not m.get("_pending"):
            out.append(finding("packet-open-all-decided", pid, "every decision (%s) has its line"
                               % ", ".join("D%d" % k for k in asked),
                               "set state: decided and decided: <date> (packets.py decide records it so)"))
        elif not asked and 0 in answered:
            out.append(finding("packet-open-all-decided", pid, "its D0 acknowledgement is recorded",
                               "set state: decided and decided: <date>"))
    return out


def audit_claims(items, covered=False):
    """Findings over ``registry.py stale --json`` items (each with ``kind``, ``qid``,
    ``status``, ``pass``, ``hold``, ``open_ticket``), deduplicated by ``qid``. Returns
    ``(findings, covered_qids)``: a claim an open ticket covers is listed only with
    ``covered``."""
    out, seen, cov = [], set(), []
    for it in sorted(items, key=lambda i: (i.get("qid") or "")):
        q = it.get("qid")
        if not q or q in seen or it.get("kind") not in ("stale", "unreviewed"):
            continue
        seen.add(q)
        ot = it.get("open_ticket")
        if ot:
            cov.append(q)
            if not covered:
                continue
        if it.get("kind") == "stale":
            detail = "%s; statement changed since pass %s%s" % (it.get("status"), it.get("pass") or "?",
                                                                "; " + it["hold"] if it.get("hold") else "")
            fix = ("registry.py stale --file-reword (a reword verify)" if not it.get("hold")
                   else "a blind verify, or the human decides")
            cls = "claim-stale-hash"
        else:
            detail, cls = it.get("hold") or it.get("status") or "", "claim-no-positive-pass"
            fix = "the human decides: a blind verify, or the status reverts to what the reviews support"
        if ot:
            fix = "covered by the open ticket %s: wait for it" % ot
        out.append(finding(cls, q, detail, fix))
    return out, cov


# ---- gathering (the only part that reads the workspace) ---------------------------------

def gather_packets(board):
    """Every packet file, parsed or not: the parsed ones as ``list_packets`` gives them with
    ``_asked`` and ``_answered``; an unparseable one as ``{"_path", "_unreadable"}``."""
    rows = {m["_path"]: m for m in packetlib.list_packets(board)}
    out = []
    for path, meta, body in packetlib.iter_packets(board):
        if meta is None or path not in rows:
            out.append({"_path": path, "_unreadable": "the frontmatter does not parse"})
            continue
        m = rows[path]
        m["_asked"] = sorted(ac.packet_decisions(body))
        m["_answered"] = sorted(ac.packet_answers(body))
        out.append(m)
    return out


def _run_stale(home):
    reg = os.path.join(HERE, "registry.py")
    return subprocess.run([sys.executable, reg, "stale", "--json"], cwd=home, capture_output=True,
                          text=True, encoding="utf-8", timeout=300)


def gather_stale(workspace, problems, run=_run_stale):
    """``registry.py stale --json`` from every home with a namespace (and every Author home);
    a home that fails, warns or could not read the board is named in ``problems``."""
    items = []
    for name, inst in sorted((workspace.get("instances") or {}).items()):
        home = inst.get("home")
        if not inst.get("ns") and inst.get("role") != "author":
            continue
        if not home or not os.path.isdir(home):
            problems.append("%s: home %s missing, its claims not audited" % (name, home))
            continue
        try:
            p = run(home)
        except (subprocess.SubprocessError, OSError) as e:
            problems.append("%s: registry.py stale failed (%s)" % (name, e))
            continue
        err = (p.stderr or "").strip()
        if p.returncode != 0:
            problems.append("%s: registry.py stale exit %d: %s" % (name, p.returncode, err[:300] or "no message"))
            continue
        try:
            d = json.loads(p.stdout or "{}")
        except ValueError:
            problems.append("%s: registry.py stale printed no JSON" % name)
            continue
        if err:
            problems.append("%s: registry.py stale: %s" % (name, err[:300]))
        if d.get("board"):
            problems.append("%s: registry.py stale could not read the board (%s): open tickets not matched"
                            % (name, d["board"]))
        items += d.get("items") or []
    return items


def render(findings, problems, limit=10, covered=()):
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
    if covered:
        lines.append("")
        lines.append("Covered: %d stale or unreviewed claim(s) already have an open verify ticket (--covered lists them)"
                     % len(covered))
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
    ap.add_argument("--covered", action="store_true", help="also list claims an open verify ticket covers")
    ap.add_argument("--today", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--no-tickets", action="store_true")
    ap.add_argument("--no-packets", action="store_true")
    ap.add_argument("--no-registry", action="store_true")
    a = ap.parse_args(argv)
    today = _date(a.today) or datetime.date.fromisoformat(ac.today())
    # tickets from the store board.backend names (GitHub issues, or the files); packets are
    # always files in the board directory
    board = boardlib.resolve_board(a.board, a.workspace)
    findings, problems, cov = [], [], []
    if not a.no_tickets:
        store = boardlib.resolve_store(a.board, a.workspace)
        findings += audit_tickets(boardlib.list_tickets(store, include_terminal=True), today, a.idle_days)
    if not a.no_packets:
        findings += audit_packets(gather_packets(board))
    if not a.no_registry:
        fs, cov = audit_claims(gather_stale(ac.load_workspace(a.workspace), problems), covered=a.covered)
        findings += fs
    if a.classes:
        findings = [f for f in findings if f["class"] in a.classes]
    order = {c: i for i, c in enumerate(CLASSES)}
    findings.sort(key=lambda f: order[f["class"]])
    if a.json:
        print(json.dumps({"findings": findings, "counts": dict(collections.Counter(f["class"] for f in findings)),
                          "covered": cov, "not_audited": problems}, indent=2, ensure_ascii=False))
    else:
        boardlib._utf8_stdout()
        print(render(findings, problems, a.limit, cov))
    return 0


if __name__ == "__main__":
    sys.exit(main())
