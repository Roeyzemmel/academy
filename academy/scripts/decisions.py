"""decisions.py -- pending decisions across the board, for /academy:decide.

Subagents cannot use ``AskUserQuestion`` (docs/protocol.md, budget.md rule 5), so
asking Roey is split in two: this script collects and records; the ``secretary``
agent (read-only) phrases the questions; the ``/academy:decide`` skill is the only
caller of ``AskUserQuestion``.

A "pending decision" is one of:

  (a) a decision in an **open packet**'s ``## Decisions needed`` (docs/packet-template.md)
      whose ``## Decision`` has no line yet -- id ``P-NNNN/Dk``;
  (b) a **ticket addressed to human** that is still ``open`` -- id ``T-NNNN``;
  (c) a ticket **in any folder** that is ``blocked`` with ``human`` in ``waiting_on``
      -- id ``T-NNNN``.

Usage::

    py decisions.py list [--json] [--instance X]
    py decisions.py batches [--size 4] [--json] [--instance X]
    py decisions.py record <id> --choice <letter|label> [--comment TEXT]
    py decisions.py accept-recommended [--mechanical-only] [--dry-run] [--json]

``record`` writes back via ``packets.decide_packet`` for a ``P-NNNN/Dk`` (or a bare
``P-NNNN`` with exactly one decision still pending), and via ``board.append_to_ticket``
+ ``board.transition_ticket`` (as human) for a ``T-NNNN``. Recording a decision never
starts work: the ticket's owner picks it up on its own next inbox run
(``references/budget.md`` rule 3).

``accept-recommended`` only ever applies a **packet's own recorded** ``Recommendation:``
line -- a raw ticket carries no such recommendation, so ticket-sourced items are never
auto-accepted; they always go through ``record`` with an explicit choice.

Classification (``mechanical`` vs ``substantive``) and the "most-unblocking first"
ordering of ``batches`` are heuristics over the kind of packet/ticket and the
registry status it proposes; they are documented, not authoritative, and a human note
should flag any borderline call (``academy:honest-reporting``).
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board as boardlib  # noqa: E402
import packets as packetlib  # noqa: E402

RE_PACKET_DECISION_ID = re.compile(r"^(P-\d{4,})/D(\d+)$")
RE_PACKET_ID = re.compile(r"^P-\d{4,}$")

#: docs/packet-template.md kinds that are about the mathematics, a research
#: direction or spending real agent budget -- never auto-accepted mechanically.
SUBSTANTIVE_PACKET_KINDS = {
    "verification", "citation", "referee", "experiment-report", "experiment-review",
    "generalization", "proof", "migration",
}
#: the rest: config, layout, bookkeeping.
MECHANICAL_PACKET_KINDS = set(ac.PACKET_KINDS) - SUBSTANTIVE_PACKET_KINDS

#: docs/protocol.md ticket kinds that carry mathematics or a spending choice.
SUBSTANTIVE_TICKET_KINDS = {
    "verify", "prove", "review-experiment", "generalize", "experiment", "test",
    "referee", "decision",
}
MECHANICAL_TICKET_KINDS = set(ac.TICKET_KINDS) - SUBSTANTIVE_TICKET_KINDS

#: registry statuses that make a packet substantive regardless of its kind
#: (docs/packet-template.md CLAIM_STATUSES): publishing a claim's status.
PUBLISHING_STATUSES = {"proved", "proved-modulo", "refuted", "refuted-as-stated"}


# ----------------------------------------------------------------------------
# Option selection (label + one-line description, max 4)
# ----------------------------------------------------------------------------

def _words(text):
    return set(re.findall(r"[a-z0-9]+", str(text).lower()))


def _jaccard(a, b):
    if not a and not b:
        return 0.0
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def select_options(options, recommended=None, max_options=4):
    """Cap a ``{key: text}`` map of options at ``max_options``.

    With few enough options, returns them all (recommended moved first). With more,
    keeps the recommended one plus the most mutually distinct of the rest (greedy,
    by word-set Jaccard distance) and returns a note naming what was left out.

    Returns ``(kept, note)``: ``kept`` a list of ``(key, text)`` pairs, recommended
    first when present; ``note`` a string, or None when nothing was omitted.
    """
    keys = list(options.keys())
    if len(keys) <= max_options:
        ordered = list(keys)
        if recommended in ordered:
            ordered.remove(recommended)
            ordered.insert(0, recommended)
        return [(k, options[k]) for k in ordered], None
    chosen = []
    if recommended in options:
        chosen.append(recommended)
    remaining = [k for k in keys if k not in chosen]
    while len(chosen) < max_options and remaining:
        best, best_score = None, -1.0
        for k in remaining:
            if not chosen:
                score = 0.0
            else:
                score = min(1.0 - _jaccard(_words(options[k]), _words(options[c]))
                           for c in chosen)
            if score > best_score:
                best, best_score = k, score
        chosen.append(best)
        remaining.remove(best)
    omitted = [k for k in keys if k not in chosen]
    note = "%d more option(s) not shown: %s" % (len(omitted), ", ".join(sorted(omitted)))
    return [(k, options[k]) for k in chosen], note


def _opt_dicts(kept, note):
    out = [{"label": "(%s) %s" % (k, txt.split(".")[0].split(",")[0][:48]),
            "description": txt} for k, txt in kept]
    if note:
        out.append({"label": "(more)", "description": note})
    return out


# ----------------------------------------------------------------------------
# Gathering
# ----------------------------------------------------------------------------

def _classify_packet(meta):
    if meta.get("status_proposed") in PUBLISHING_STATUSES:
        return "substantive"
    return "substantive" if meta.get("kind") in SUBSTANTIVE_PACKET_KINDS else "mechanical"


def _classify_ticket(t):
    return "substantive" if t.get("kind") in SUBSTANTIVE_TICKET_KINDS else "mechanical"


def _packet_unblocks(board, tid):
    if not tid:
        return []
    path = ac.find_ticket(board, tid)
    if not path:
        return [tid]
    meta, _body = boardlib.read_ticket(path)
    out = [tid]
    out.extend(str(b) for b in (meta.get("blocks") or []) if str(b) not in out)
    return out


def _staleness(board, meta, created):
    """A later, already-decided packet sharing a subject: worth a second look."""
    subj = set(str(s) for s in (meta.get("subject") or []))
    if not subj:
        return None
    hints = []
    for other in packetlib.list_packets(board):
        if other.get("packet") == meta.get("packet") or other.get("state") != "decided":
            continue
        oshare = subj & set(str(s) for s in (other.get("subject") or []))
        if oshare and str(other.get("decided") or "") > str(created or ""):
            hints.append("%s (decided %s) shares %s -- check it does not contradict "
                        "this recommendation" % (other["packet"], other.get("decided"),
                                                 ", ".join(sorted(oshare))))
    return "; ".join(hints) or None


def _packet_items(board, instance=None):
    items = []
    for m in packetlib.list_packets(board, only_open=True, instance=instance):
        with open(m["_path"], "r", encoding="utf-8") as fh:
            _meta2, body = ac.read_frontmatter(fh.read())
        asked, answers = ac.packet_decisions(body), ac.packet_answers(body)
        for k in sorted(asked):
            if k in answers:
                continue
            d = asked[k]
            rec = d.get("recommendation") or ""
            mrec = re.match(r"^\(([a-d])\)", rec)
            kept, note = select_options(d["options"], mrec.group(1) if mrec else None)
            items.append({
                "id": "%s/D%d" % (m["packet"], k),
                "instance": m.get("instance"),
                "title": m.get("title"),
                "question": d["question"],
                "options": _opt_dicts(kept, note),
                "recommendation": rec or None,
                "kind": _classify_packet(m),
                "unblocks": _packet_unblocks(board, m.get("ticket")),
                "stale": _staleness(board, m, m.get("created")),
                "source": "packet",
                "ref": m["packet"],
            })
    return items


def _ticket_question(t):
    ask = str(t.get("ask") or t.get("title") or "").strip()
    return ask if ask.endswith("?") else ask.rstrip(".") + "?"


def _ticket_options(t):
    return [
        {"label": "(a) Proceed", "description": "Accept as asked: %s"
         % (t.get("deliverable") or "let it move forward")},
        {"label": "(b) Decline", "description": "Reject or hold the ticket; nothing proceeds."},
    ]


def _ticket_items(board, instance=None, to_human=False):
    items = []
    if to_human:
        rows = boardlib.list_tickets(board, to=ac.HUMAN, status="open")
    else:
        rows = [t for t in boardlib.list_tickets(board, status="blocked")
                if ac.HUMAN in [str(w) for w in (t.get("waiting_on") or [])]]
    for t in rows:
        inst = t.get("from") if to_human else t.get("to")
        if instance and inst != instance:
            continue
        items.append({
            "id": t["id"],
            "instance": inst,
            "title": t.get("title"),
            "question": _ticket_question(t),
            "options": _ticket_options(t),
            "recommendation": None,
            "kind": _classify_ticket(t),
            "unblocks": [str(b) for b in (t.get("blocks") or [])],
            "stale": None,
            "source": "ticket-human" if to_human else "ticket-blocked",
            "ref": t["id"],
        })
    return items


def pending_decisions(board, instance=None):
    """Every pending decision (a)+(b)+(c) above, as a list of item dicts.

    Ordered packets first (by id, then D-number), then tickets to human, then
    blocked-on-human tickets (each by id). ``batches`` imposes the working order.
    """
    items = _packet_items(board, instance)
    items += _ticket_items(board, instance, to_human=True)
    items += _ticket_items(board, instance, to_human=False)
    return items


# ----------------------------------------------------------------------------
# Batching
# ----------------------------------------------------------------------------

def batches(items, size=4):
    """Group ``items`` into batches of at most ``size``.

    Ordered most-unblocking first, substantive before mechanical, and grouped by
    topic (instance) within ties -- a stable sort, then a plain chunking.
    """
    size = max(1, int(size))
    ordered = sorted(items, key=lambda i: (
        -len(i.get("unblocks") or []),
        0 if i.get("kind") == "substantive" else 1,
        str(i.get("instance") or ""),
        str(i.get("id"))))
    return [ordered[i:i + size] for i in range(0, len(ordered), size)]


# ----------------------------------------------------------------------------
# Recording
# ----------------------------------------------------------------------------

def _is_proceed(choice):
    c = str(choice).strip().lower().strip("()")
    if c in ("a", "proceed", "yes", "y"):
        return True
    if c in ("b", "decline", "no", "n"):
        return False
    raise ac.AcademyError(
        "a ticket decision takes proceed/a or decline/b, not %r" % choice)


def _record_ticket(board, tid, choice, comment, date):
    path, meta, _body = boardlib.get_ticket(board, tid)
    proceed = _is_proceed(choice)
    text = "human decision: %s" % ("proceed" if proceed else "decline")
    if comment.strip():
        text += " -- " + " ".join(comment.split())
    boardlib.append_to_ticket(board, tid, text, as_instance=ac.HUMAN, date=date)
    old = meta.get("status")
    if old == "blocked":
        new = "accepted" if proceed else "cancelled"
    elif old == "open" and meta.get("to") == ac.HUMAN:
        new = "accepted" if proceed else "rejected"
    else:
        raise ac.AcademyError("%s is not a pending human decision (status %s)" % (tid, old))
    reason = (comment.strip() or "declined via /academy:decide") if new in (
        "rejected", "cancelled") else ""
    boardlib.transition_ticket(board, tid, new, reason=reason, as_instance=ac.HUMAN, date=date)
    return {"ref": tid, "status": new}


def record(board, item_id, choice, comment="", workspace=None, date=None):
    """Write back the human's answer to one pending decision. Returns a small dict."""
    date = date or ac.today()
    m = RE_PACKET_DECISION_ID.match(str(item_id))
    if m:
        pid, k = m.group(1), int(m.group(2))
        path, kk, decided = packetlib.decide_packet(board, pid, choice, decision=k,
                                                     comment=comment, date=date)
        return {"ref": pid, "decision": kk, "decided": decided, "path": path}
    if RE_PACKET_ID.match(str(item_id)):
        _path, meta, body = packetlib.get_packet(board, item_id)
        asked, answers = ac.packet_decisions(body), ac.packet_answers(body)
        pending = sorted(k for k in asked if k not in answers) if asked else (
            [] if 0 in answers else [0])
        if len(pending) != 1:
            raise ac.AcademyError(
                "%s has %d pending decision(s); name one as %s/D<k>"
                % (item_id, len(pending), item_id))
        return record(board, "%s/D%d" % (item_id, pending[0]), choice, comment, workspace, date)
    if ac.RE_TICKET_ID.match(str(item_id)):
        return _record_ticket(board, item_id, choice, comment, date)
    raise ac.AcademyError(
        "id must look like P-0001/D1, P-0001 or T-0001, not %r" % item_id)


def accept_recommended(board, mechanical_only=False, dry_run=False, workspace=None, date=None):
    """Apply every packet's own recorded recommendation (never a ticket's, which has none).

    Returns the list of ``{"id":..., "choice": <letter>}`` applied (or, with
    ``dry_run``, that *would* be applied -- nothing is written).
    """
    date = date or ac.today()
    out = []
    for item in pending_decisions(board):
        if item["source"] != "packet" or not item.get("recommendation"):
            continue
        if mechanical_only and item["kind"] != "mechanical":
            continue
        m = re.match(r"^\(([a-d])\)", item["recommendation"])
        if not m:
            continue
        letter = m.group(1)
        if not dry_run:
            record(board, item["id"], letter,
                  comment="accepted recommendation (accept-recommended)",
                  workspace=workspace, date=date)
        out.append({"id": item["id"], "choice": letter})
    return out


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _fmt_item(i):
    return "%-14s %-20s [%-11s] %s" % (i["id"], i.get("instance") or "-", i["kind"], i["question"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="decisions.py", description=__doc__.split("\n")[0])
    ap.add_argument("--board"); ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="every pending decision")
    p.add_argument("--json", action="store_true"); p.add_argument("--instance")

    p = sub.add_parser("batches", help="pending decisions grouped into batches")
    p.add_argument("--size", type=int, default=4); p.add_argument("--json", action="store_true")
    p.add_argument("--instance")

    p = sub.add_parser("record", help="record the human's answer to one decision")
    p.add_argument("id"); p.add_argument("--choice", required=True)
    p.add_argument("--comment", default="")

    p = sub.add_parser("accept-recommended", help="accept every packet's own recommendation")
    p.add_argument("--mechanical-only", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")

    a = ap.parse_args(argv)
    boardlib._utf8_stdout()
    try:
        ws = boardlib._workspace_or_none(a.workspace)
        board = boardlib.resolve_board(a.board, a.workspace)
        if a.cmd == "list":
            items = pending_decisions(board, a.instance)
            if a.json:
                print(json.dumps(items, indent=2, ensure_ascii=False))
            else:
                for i in items:
                    print(_fmt_item(i))
                print("%d pending decision(s)" % len(items))
        elif a.cmd == "batches":
            bs = batches(pending_decisions(board, a.instance), a.size)
            if a.json:
                print(json.dumps(bs, indent=2, ensure_ascii=False))
            else:
                for n, b in enumerate(bs, 1):
                    print("Batch %d (%d item(s))" % (n, len(b)))
                    for i in b:
                        print("  " + _fmt_item(i))
        elif a.cmd == "record":
            print(json.dumps(record(board, a.id, a.choice, a.comment, ws),
                             ensure_ascii=False))
        elif a.cmd == "accept-recommended":
            out = accept_recommended(board, a.mechanical_only, a.dry_run, ws)
            if a.json:
                print(json.dumps(out, indent=2, ensure_ascii=False))
            else:
                verb = "would accept" if a.dry_run else "accepted"
                for r in out:
                    print("%s %s: (%s)" % (verb, r["id"], r["choice"]))
                print("%d %s" % (len(out), verb))
    except ac.AcademyError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
