"""decisions.py -- pending decisions across the board, for /academy:decide.

Subagents cannot use ``AskUserQuestion`` (docs/protocol.md, budget.md rule 5), so
asking the human is split in two: this script collects and records; the ``secretary``
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
    py decisions.py record <id> (--choice <letter|label> | --action <what>) [--force]
                                [--comment TEXT]
    py decisions.py accept-recommended [--mechanical-only] [--dry-run] [--json]
    py decisions.py stalled-rulings [--json]

``record`` writes back via ``packets.decide_packet`` for a ``P-NNNN/Dk`` (or a bare
``P-NNNN`` with exactly one decision still pending), and via ``board.append_to_ticket``
+ ``board.transition_ticket`` (as human) for a ``T-NNNN``. Recording a decision never
starts work: the ticket's owner picks it up on its own next inbox run
(``references/budget.md`` rule 3).

A **ruling** (``rulings.py``: an Expert's decision ticket on the inputs of a pass with two
CONFIRMED runs) takes (a) union, (b) intersection, (c) re-run or (d) decline, not a bare
proceed; ``record`` files its follow-up in the same step (the keeper's ``decision``
ticket for (a)/(b), a ``verify`` ticket to the Expert for (c)), names it on the ruling and
delivers the ruling; a second ``record`` files nothing (#121 item 4).

A ticket whose ask carries its **own lettered options** ("(a) accept ...; (b) re-run ...;
(c) wait ...") is read by them (#125): ``--choice c`` is the ticket's (c), classified by
keyword (re-run / accept / wait / split / decline); ``--action`` names the answer by what
it does and is refused when it disagrees with the letter. A re-run ruling always files its
re-run, even over an earlier ruling the claim-keeper acted on; any other answer over such
an earlier, different one is refused unless ``--force``.

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
import rulings as rulinglib  # noqa: E402

# a packet id may carry '@<part of its path under packets/>' when two files share it (#90)
RE_PACKET_DECISION_ID = re.compile(r"^(P-\d{4,}(?:@[^\s]+?)?)/D(\d+)$")
RE_PACKET_ID = re.compile(r"^P-\d{4,}(?:@\S+)?$")

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


def _ticket_metas(board):
    """``{id: meta}`` of every ticket, from one listing (on the GitHub board a ticket read
    one at a time is two requests; 2026-11-13: the pending decisions of fourteen packets
    took 27 s, 32 single reads among them)."""
    return {str(m.get("id")): m for _ref, m in ac.as_store(board).iter_meta() if m}


def _packet_unblocks(board, tid, metas=None):
    if not tid:
        return []
    if metas is None:
        metas = _ticket_metas(board)
    meta = metas.get(str(tid))
    if meta is None:
        return [tid]
    out = [tid]
    out.extend(str(b) for b in (meta.get("blocks") or []) if str(b) not in out)
    return out


def _staleness(board, meta, created, packets=None):
    """A later, already-decided packet sharing a subject: worth a second look.
    ``packets`` is the board's packet listing when the caller already holds it."""
    subj = set(str(s) for s in (meta.get("subject") or []))
    if not subj:
        return None
    hints = []
    for other in (packetlib.list_packets(board) if packets is None else packets):
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
    every = packetlib.list_packets(board)                 # read once, for _staleness
    metas = None                                          # the tickets, listed on first need
    root = os.path.join(ac.board_dir(board), "packets")
    seen = {}
    for m in every:
        seen[m["packet"]] = seen.get(m["packet"], 0) + 1
    for m in every:
        if m.get("state") != "open" or (instance and m.get("instance") != instance):
            continue
        with open(m["_path"], "r", encoding="utf-8") as fh:
            _meta2, body = ac.read_frontmatter(fh.read())
        asked, answers = ac.packet_decisions(body), ac.packet_answers(body)
        # #90: an id two packet files share is qualified with this file's path, so every
        # write (record, proceed, accept-recommended) reaches this file and not its twin
        ref = m["packet"]
        if seen.get(ref, 0) > 1:
            rel = os.path.relpath(m["_path"], root).replace(os.sep, "/")
            ref = "%s@%s" % (ref, rel[:-3] if rel.endswith(".md") else rel)
        for k in sorted(asked):
            if k in answers:
                continue
            d = asked[k]
            rec = d.get("recommendation") or ""
            mrec = re.match(r"^\(([a-d])\)", rec)
            kept, note = select_options(d["options"], mrec.group(1) if mrec else None)
            if metas is None and m.get("ticket"):
                metas = _ticket_metas(board)
            items.append({
                "id": "%s/D%d" % (ref, k),
                "instance": m.get("instance"),
                "title": m.get("title"),
                "question": d["question"],
                "options": _opt_dicts(kept, note),
                "recommendation": rec or None,
                "kind": _classify_packet(m),
                # the packet proposes a status that publishes a result: never worked on
                # provisionally (proceed), the human decides first
                "publishing": (m.get("status_proposed") in PUBLISHING_STATUSES
                               and m.get("status_proposed") != m.get("status_before")),
                "provisional": packetlib.provisional_choices(body).get(k),
                "unblocks": _packet_unblocks(board, m.get("ticket"), metas),
                "stale": _staleness(board, m, m.get("created"), every),
                "source": "packet",
                "ref": ref,
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


def _ruling(board, t, workspace):
    """``(ruling, ticket)``: ``t``'s ruling (rulings.py) when it is a decision ticket from an
    Expert, with the ticket as read (``(path, meta, body)``), else ``(None, None)``."""
    if t.get("kind") != "decision" or t.get("to") != ac.HUMAN:
        return None, None
    # the listing reads metas only (2026-11-13: one read per ticket made it 27 s): a
    # ticket's body is read only when its title, ask or deliverable speak of inputs
    if not rulinglib.RE_ABOUT_INPUTS.search(" ".join(
            str(t.get(k) or "") for k in ("title", "ask", "deliverable"))):
        return None, None
    try:
        ticket = boardlib.get_ticket(board, t["id"])
        r = rulinglib.find_ruling(board, t["id"], workspace, ticket=ticket)
        return (r, ticket) if r else (None, None)
    except (ac.AcademyError, OSError):
        return None, None


def _ticket_items(board, instance=None, to_human=False, workspace=None):
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
        r, ticket = _ruling(board, t, workspace) if to_human else (None, None)
        # a ticket's own lettered options are what its letters mean (#125): a ruling's read
        # with its body, a plain ticket's from its ask line, as record reads them
        own = rulinglib.own_options(t, ticket[2] if r else None)
        items.append({
            "id": t["id"],
            "instance": inst,
            "title": t.get("title"),
            "question": _ticket_question(t),
            "options": (rulinglib.own_option_dicts(own) if own
                        else rulinglib.options(r) if r else _ticket_options(t)),
            "ruling": {k: r[k] for k in ("subject", "pass", "union", "intersection", "keeper")}
            if r else None,
            "recommendation": None,
            "kind": _classify_ticket(t),
            "unblocks": [str(b) for b in (t.get("blocks") or [])],
            "stale": None,
            "source": "ticket-human" if to_human else "ticket-blocked",
            "ref": t["id"],
        })
    return items


def pending_decisions(board, instance=None, workspace=None):
    """Every pending decision (a)+(b)+(c) above, as a list of item dicts.

    Ordered packets first (by id, then D-number), then tickets to human, then
    blocked-on-human tickets (each by id). ``batches`` imposes the working order.
    A ruling ticket (rulings.py) carries its four options and ``ruling``.
    """
    items = _packet_items(board, instance)
    items += _ticket_items(board, instance, to_human=True, workspace=workspace)
    items += _ticket_items(board, instance, to_human=False, workspace=workspace)
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

#: the generic answers a plain ticket always takes, own options or not
GENERIC_WORDS = ("proceed", "yes", "y", "decline", "no", "n")


def _is_proceed(choice):
    c = str(choice).strip().lower().strip("()")
    if c == "accept":
        return True
    if c in ("a", "proceed", "yes", "y"):
        return True
    if c in ("b", "decline", "no", "n"):
        return False
    raise ac.AcademyError(
        "a ticket decision takes proceed/a or decline/b, not %r" % choice)


def _record_ticket(board, tid, choice, comment, date, workspace=None, action=None,
                   force=False):
    ticket = boardlib.get_ticket(board, tid)
    path, meta, body = ticket
    r = None
    if meta.get("kind") == "decision" and meta.get("to") == ac.HUMAN:
        r = rulinglib.find_ruling(board, tid, workspace, ticket=ticket)
    if r:
        # a ruling on a pass's inputs: its follow-up is filed in this same step (#121)
        return rulinglib.record(board, r, choice, comment, workspace=workspace, date=date,
                                ticket=ticket, action=action, force=force)
    own = rulinglib.own_options(meta)            # the ask line, as the listing reads it
    word = str(choice or "").strip().lower() in GENERIC_WORDS and action in (None, "")
    if own and not word:
        # the ticket's own letters (#125): its (b) is its (b), not the generic decline
        letter, cls, option, _act = rulinglib.pick_own(own, choice, action, tid)
        proceed = cls != "decline"
        text = "human decision: (%s) %s [the ticket's own (%s): %s]" % (
            letter, cls, letter, " ".join(option.split())[:120])
    else:
        if choice in (None, "") and action in (None, ""):
            raise ac.AcademyError("%s: name the answer with --choice or --action" % tid)
        given = [x for x in (choice, action) if x not in (None, "")]
        answers = {_is_proceed(x) for x in given}
        if len(answers) > 1:
            raise ac.AcademyError("%s: --choice %s and --action %s disagree (a proceed and a "
                                  "decline)" % (tid, choice, action))
        proceed = answers.pop()
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


def record(board, item_id, choice, comment="", workspace=None, date=None, action=None,
           force=False):
    """Write back the human's answer to one pending decision. Returns a small dict.

    For a ticket, ``choice`` is a letter (its own when its ask carries lettered options,
    #125) and ``action`` the answer by what it does (rerun, accept, wait, split, decline);
    ``force`` records a ruling's answer over an earlier, different one that was acted on
    (rulings.record)."""
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
        return _record_ticket(board, item_id, choice, comment, date, workspace, action, force)
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


def proceed(board, instance=None, dry_run=False, date=None):
    """Let the work go on under each pending packet decision's own recommendation, without
    deciding it (the human's rule, 2026-11-14: a decision is collected when the human
    comes to it; it does not hold the work that depends on it).

    For every pending packet decision that has a recommended option and whose packet does
    not propose a publishing status: the packet gets a provisional note (it stays open, the
    decision stays pending and is still asked), and the tickets the decision unblocks get
    one thread line naming the option. What is done under it is provisional: it raises no
    status, and if the human then chooses another option the decision's echo says so and a
    delivered ticket is returned to its receiver. Returns ``[{"id", "choice", "tickets"}]``
    (with ``dry_run``, what would be done)."""
    date = date or ac.today()
    out = []
    for item in pending_decisions(board, instance):
        if item["source"] != "packet" or item.get("publishing") or item.get("provisional"):
            continue
        m = re.match(r"^\(([a-d])\)", item.get("recommendation") or "")
        if not m:
            continue
        letter, pid, k = m.group(1), item["ref"], int(item["id"].rsplit("/D", 1)[1])
        option = next((o["description"] for o in item["options"]
                       if o["label"].startswith("(%s)" % letter)), "")
        tickets = []
        if not dry_run:
            if not packetlib.note_provisional(board, pid, k, letter, date):
                continue
            store = ac.as_store(board)
            for tid in item.get("unblocks") or []:
                if not store.find(tid):
                    continue
                boardlib.append_to_ticket(
                    board, tid, "proceeding on %s D%d (%s) %s -- the recommendation, not yet "
                    "decided: what is done on it is provisional and raises no status"
                    % (pid, k, letter, " ".join(option.split())[:160]),
                    as_instance=item.get("instance") or ac.HUMAN, agent="decisions", date=date)
                tickets.append(tid)
        else:
            tickets = list(item.get("unblocks") or [])
        out.append({"id": item["id"], "choice": letter, "tickets": tickets})
    return out


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _fmt_item(i):
    return "%-14s %-20s [%-11s] %s" % (i["id"], i.get("instance") or "-", i["kind"], i["question"])


def _wire(obj):
    """``obj`` as the JSON a session reads: one line, and no key whose value is null or
    empty (a decision without a staleness hint or a recommendation simply has no such
    key). 21 pending decisions were 24 800 characters indented."""
    def lean(x):
        if isinstance(x, dict):
            return {k: lean(v) for k, v in x.items() if v not in (None, "", [], {})}
        if isinstance(x, list):
            return [lean(v) for v in x]
        return x
    return json.dumps(lean(obj), ensure_ascii=False, separators=(",", ":"))


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
    p.add_argument("id")
    p.add_argument("--choice", help="a letter: the ticket's own when its ask has lettered "
                                    "options, else the generic ones (or proceed/decline)")
    p.add_argument("--action", help="the answer by what it does: rerun, accept, wait, split, "
                                    "decline (a ruling: also union, intersection); must agree "
                                    "with --choice when both are given")
    p.add_argument("--force", action="store_true",
                   help="record a ruling's answer over an earlier, different one that was "
                        "acted on (a re-run needs no --force)")
    p.add_argument("--comment", default="")

    p = sub.add_parser("accept-recommended", help="accept every packet's own recommendation")
    p.add_argument("--mechanical-only", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("proceed", help="let the work go on under each pending decision's "
                                       "recommendation, provisionally; nothing is decided")
    p.add_argument("--instance")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("stalled-rulings", help="rulings the human answered that are not "
                                               "delivered (read-only)")
    p.add_argument("--json", action="store_true")

    a = ap.parse_args(argv)
    boardlib._utf8_stdout()
    try:
        ws = boardlib._workspace_or_none(a.workspace)
        board = boardlib.resolve_store(a.board, a.workspace)
        if a.cmd == "list":
            items = pending_decisions(board, a.instance, ws)
            if a.json:
                print(_wire(items))
            else:
                for i in items:
                    print(_fmt_item(i))
                print("%d pending decision(s)" % len(items))
        elif a.cmd == "batches":
            bs = batches(pending_decisions(board, a.instance, ws), a.size)
            if a.json:
                print(_wire(bs))
            else:
                for n, b in enumerate(bs, 1):
                    print("Batch %d (%d item(s))" % (n, len(b)))
                    for i in b:
                        print("  " + _fmt_item(i))
        elif a.cmd == "record":
            if a.choice is None and a.action is None:
                raise ac.AcademyError("record needs --choice or --action")
            if RE_PACKET_DECISION_ID.match(a.id) or RE_PACKET_ID.match(a.id):
                if a.choice is None or a.action is not None:
                    raise ac.AcademyError("a packet decision takes --choice <letter> only")
            print(json.dumps(record(board, a.id, a.choice, a.comment, ws, action=a.action,
                                    force=a.force), ensure_ascii=False))
        elif a.cmd == "stalled-rulings":
            rows = rulinglib.stalled(board, ws)
            if a.json:
                print(json.dumps(rows, ensure_ascii=False))
            else:
                for r in rows:
                    print("%s %s: %s (follow-up: %s)" % (r["id"], r["subject"], r["answer"],
                                                         r["follow_up"] or "none"))
                print("%d answered ruling(s) not delivered; `record <id> --choice <a-c>` "
                      "files or completes the follow-up" % len(rows))
        elif a.cmd == "proceed":
            done = proceed(board, a.instance, a.dry_run)
            if a.json:
                print(_wire(done))
            else:
                for d in done:
                    print("%s (%s) provisional%s" % (d["id"], d["choice"], (
                        ": " + ", ".join(d["tickets"])) if d["tickets"] else ""))
                print("%d decision(s) %s on their recommendation; none is decided" % (
                    len(done), "would proceed" if a.dry_run else "proceed"))
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
