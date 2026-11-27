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
    py decisions.py policy [--dry-run] [--json] [--instance X]
    py decisions.py undo <T-id>
    py decisions.py select --ticked T-1,T-2 --unticked T-3 [--comment TEXT]

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

**The routine policy (#86).** workspace.json's ``decisions.routine`` lists the categories
the human accepts once, for good (ticket kinds, ``claim-status``, ``repair``;
``routine_policy``). ``policy`` accepts every pending ticket of one of them that has
nothing to choose (no ruling, no alternatives, no pinned statement), writes one thread
line naming the policy and prints one digest line per category; ``undo`` reverts one such
acceptance until an inbox run touches the ticket. ``review-experiment`` and a plain
``decision`` are never routine.

**Alternatives (#86).** A ticket whose ask names alternatives without letters ("Decide:
drop the note, or a literature lookup and a one-line remark"; ``rulings.alternatives``)
is listed with them and a decline; ``record`` takes one of their letters or a decline,
never a bare ``proceed`` (nor on a ticket with lettered options), and stores the choice on
the ticket as ``decision_choice`` (a human-only field the resuming agent reads; plain
``proceed`` for a ticket with nothing to choose).

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
import subprocess
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


# ----------------------------------------------------------------------------
# Pinned statements (#86 ruling 4): "accept and release <labels>"
# ----------------------------------------------------------------------------

#: the Author plugin's pin reader (a sibling plugin of this one); absent, nothing is pinned
AUTHOR_PINNED = os.path.join(os.path.dirname(PLUGIN), "author", "scripts", "pinned.py")
#: the Author home's release list (author/scripts/pinned.py RELEASE_REL)
RELEASE_REL = os.path.join(".claude", "pinned-release.txt")
RE_LABEL = re.compile(r"(?<![A-Za-z0-9])((?:%s):[A-Za-z0-9][\w.:-]*)" % "|".join(
    sorted(set(rulinglib.LABEL_PREFIXES) | {"quest", "problem", "exc", "exer"},
           key=len, reverse=True)))
_PINS = {}


def _pinned_labels(home):
    """The labels pinned (and not released) in an Author home: ``pinned.py --labels``, read
    once per home and run; an empty set when the Author plugin or the home is missing."""
    if home not in _PINS:
        out = set()
        if os.path.isfile(AUTHOR_PINNED) and os.path.isdir(home):
            try:
                p = subprocess.run([sys.executable, AUTHOR_PINNED, "--home", home, "--labels"],
                                   capture_output=True, text=True, timeout=120,
                                   encoding="utf-8")
                if p.returncode == 0:
                    out = {ln.strip() for ln in p.stdout.splitlines() if ln.strip()}
            except (OSError, subprocess.SubprocessError):
                pass
        _PINS[home] = out
    return _PINS[home]


def _author_home(t, workspace):
    """The home of the Author the ticket's edit is for: its receiver, or for a ticket to
    the human its sender, when that is an Author instance."""
    insts = (workspace or {}).get("instances") or {}
    for who in (t.get("to"), t.get("from") if t.get("to") == ac.HUMAN else None):
        inst = insts.get(str(who or ""))
        if inst and inst.get("role") == "author" and inst.get("home"):
            return inst["home"]
    return None


def pinned_of(t, workspace):
    """``(home, labels)``: the pinned statements a ticket's title, ask or refs name, in the
    Author home it edits; ``(home, [])`` when it names none."""
    home = _author_home(t, workspace)
    if not home:
        return None, []
    text = " ".join([str(t.get("title") or ""), str(t.get("ask") or "")]
                    + [str(r) for r in (t.get("refs") or [])])
    named = {m.group(1).rstrip(".:") for m in RE_LABEL.finditer(text)}
    if not named:
        return home, []
    return home, sorted(named & _pinned_labels(home))


def release_pins(home, labels, tid, comment, date):
    """Append the human's release of ``labels`` to ``<home>/.claude/pinned-release.txt``:
    one line per label not already listed, with the ticket and the human's word. The file
    stays the human's: this is their answer on /academy:decide (``decide_guard`` keeps an
    agent from running ``record``; ``pinned_guard`` still refuses a tool edit of it)."""
    path = os.path.join(home, RELEASE_REL)
    have = set()
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            have = {ln.split("#", 1)[0].strip() for ln in fh}
    word = " ".join(str(comment or "").split()) or "accepted the edit"
    new = [lab for lab in labels if lab not in have]
    if new:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as fh:
            for lab in new:
                fh.write("%s  # released by the human on /academy:decide (%s, %s): %s\n"
                         % (lab, tid, date, word))
    return new


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
        # alternatives named without letters ("drop the note, or a lookup and a remark",
        # #86): asked as such, never as a bare proceed; a ruling keeps its own four
        alts = {} if (own or r) else rulinglib.alternatives(t.get("ask"))
        _home, pins = pinned_of(t, workspace)
        options = (rulinglib.own_option_dicts(own) if own
                   else rulinglib.options(r) if r
                   else rulinglib.alternative_dicts(alts) if alts
                   else _ticket_options(t))
        if pins:
            options = options + [{
                "label": "(release) Accept and release %s" % ", ".join(pins),
                "description": "Accept the edit and release the pin of %s (pinned by a "
                               "CONFIRMED review): appended to the Author's %s with your "
                               "word" % (", ".join(pins), RELEASE_REL.replace(os.sep, "/"))}]
        items.append({
            "id": t["id"],
            "instance": inst,
            "title": t.get("title"),
            "question": _ticket_question(t),
            "options": options,
            "pinned": pins or None,
            "ruling": {k: r[k] for k in ("subject", "pass", "union", "intersection", "keeper")}
            if r else None,
            "recommendation": None,
            "kind": _classify_ticket(t),
            "ticket_kind": t.get("kind"),
            "claim": next((str(x) for x in (t.get("refs") or []) if x), None),
            "category": category(t),
            "not_now": _not_now_date(t),
            "own_options": bool(own or alts),
            "unblocks": [str(b) for b in (t.get("blocks") or [])],
            "stale": None,
            "source": "ticket-human" if to_human else "ticket-blocked",
            "ref": t["id"],
        })
    return items


#: the kinds asked as multi-select batches, "tick the ones to run" (#86): spending choices
SELECT_KINDS = ("prove", "experiment", "test")
#: the thread line of an unticked multi-select item; ``decision_choice`` keeps its date
NOT_NOW = "human decision: not now"
RE_NOT_NOW = re.compile(r"^not now \((\d{4}-\d{2}-\d{2})\)$")


def _not_now_date(t):
    m = RE_NOT_NOW.match(str(t.get("decision_choice") or ""))
    return m.group(1) if m else None


def _selectable(item):
    """True for a ticket item asked in a multi-select batch: a prove, experiment or test
    with nothing else to choose (no ruling, no alternatives)."""
    return (item.get("source") in ("ticket-human", "ticket-blocked")
            and item.get("ticket_kind") in SELECT_KINDS
            and not item.get("ruling") and not item.get("own_options"))


def pending_decisions(board, instance=None, workspace=None, date=None):
    """Every pending decision (a)+(b)+(c) above, as a list of item dicts.

    Ordered packets first (by id, then D-number), then tickets to human, then
    blocked-on-human tickets (each by id). ``batches`` imposes the working order.
    A ruling ticket (rulings.py) carries its four options and ``ruling``.
    """
    items = _packet_items(board, instance)
    items += _ticket_items(board, instance, to_human=True, workspace=workspace)
    items += _ticket_items(board, instance, to_human=False, workspace=workspace)
    if date:
        # "not now" on that day (an unticked multi-select item, #86): asked another day
        items = [i for i in items if i.get("not_now") != date]
    return items


# ----------------------------------------------------------------------------
# The routine policy (#86): kinds the human accepts once, in workspace.json
# ----------------------------------------------------------------------------

#: the categories ``decisions.routine`` may name besides a ticket kind: a claim-status
#: change (a ``decision`` ticket titled "Status of <id> -> <status>", claims_propose_status)
#: and a repair (a ``prove`` / ``research`` ticket whose title or ask asks for a repair)
EXTRA_CATEGORIES = ("claim-status", "repair")
#: never accepted under a policy, whatever it says: an experiment review is always asked
#: (the human's ruling, 2026-11-27), and a plain ``decision`` is the human's by definition
NEVER_ROUTINE = ("review-experiment", "decision")
RE_STATUS_TITLE = re.compile(r"^Status of \S+.*->\s*[a-z-]+")
RE_REPAIR = re.compile(r"(?i)\brepair(?:s|ed|ing)?\b")
#: the thread line a policy acceptance writes; ``undo`` looks for it
POLICY_MARK = "accepted under the routine policy"
RE_POLICY_WAS = re.compile(r"; was (open|blocked)\b")


def routine_policy(workspace):
    """The categories workspace.json's ``decisions.routine`` accepts without asking (a list:
    ticket kinds, ``claim-status``, ``repair``); ``[]`` when it names none. An entry that is
    no category, or one of ``NEVER_ROUTINE``, is refused: the policy is the human's, and a
    typo in it would silently ask what they meant to accept (or accept what they did not)."""
    raw = ((workspace or {}).get("decisions") or {}).get("routine") or []
    if not isinstance(raw, list):
        raise ac.AcademyError("workspace.json decisions.routine must be a list of kinds")
    out = []
    for c in raw:
        c = str(c).strip()
        if c in NEVER_ROUTINE:
            raise ac.AcademyError("workspace.json decisions.routine: %r is never routine (it is "
                                  "always asked)" % c)
        if c not in ac.TICKET_KINDS and c not in EXTRA_CATEGORIES:
            raise ac.AcademyError("workspace.json decisions.routine: %r is not a ticket kind "
                                  "or one of %s" % (c, ", ".join(EXTRA_CATEGORIES)))
        if c not in out:
            out.append(c)
    return out


def category(t):
    """The policy category of a ticket: ``claim-status``, ``repair`` or its kind."""
    kind = t.get("kind") or "other"
    title = str(t.get("title") or "")
    if kind == "decision" and RE_STATUS_TITLE.match(title):
        return "claim-status"
    if kind in ("prove", "research") and RE_REPAIR.search(
            title + " " + str(t.get("ask") or "")):
        return "repair"
    return kind


def _routine(item, policy):
    """True when the policy accepts ``item`` without asking: a ticket item of a policy
    category with nothing to choose (no ruling, no alternatives, no pinned statement)."""
    if item.get("source") not in ("ticket-human", "ticket-blocked"):
        return False
    if item.get("ruling") or item.get("own_options") or item.get("pinned"):
        return False
    return item.get("category") in policy


def apply_policy(board, workspace, date=None, dry_run=False, instance=None):
    """Accept every pending ticket the routine policy covers (``routine_policy``), as the
    human's standing answer: a thread line ``accepted under the routine policy (...)`` and
    the move to ``accepted``, written ``human (via main session)``. Returns
    ``[{"id", "category", "was", "instance"}]`` (with ``dry_run`` what would be accepted).
    Each acceptance can be undone (``undo``) until an inbox run touches the ticket."""
    policy = routine_policy(workspace)
    if not policy:
        return []
    date = date or ac.today()
    out = []
    for item in pending_decisions(board, instance, workspace):
        if not _routine(item, policy):
            continue
        tid = item["id"]
        was = "blocked" if item["source"] == "ticket-blocked" else "open"
        if not dry_run:
            boardlib.append_to_ticket(
                board, tid, "%s (decisions.routine: %s; was %s%s); undo: decisions.py undo %s, "
                "until an inbox run touches it" % (
                    POLICY_MARK, item["category"], was,
                    " waiting on human" if was == "blocked" else "", tid),
                as_instance=ac.HUMAN, date=date, via=ac.VIA_SESSION)
            boardlib.transition_ticket(board, tid, "accepted", as_instance=ac.HUMAN,
                                       date=date, via=ac.VIA_SESSION)
            _set_choice(board, tid, "proceed (routine policy)")
        out.append({"id": tid, "category": item["category"], "was": was,
                    "instance": item.get("instance")})
    return out


def digest(done):
    """One line for what the policy accepted, a group per category in first-seen order:
    ``accepted under the policy: 12 verify (T-1, ...), 3 cite (...)``; ``""`` for none."""
    groups = {}
    for d in done:
        groups.setdefault(d["category"], []).append(d["id"])
    if not groups:
        return ""
    return "accepted under the policy: " + ", ".join(
        "%d %s (%s)" % (len(ids), cat, ", ".join(ids)) for cat, ids in groups.items())


def undo(board, tid, date=None):
    """Revert a routine-policy acceptance of ``tid``: back to ``open`` (a ticket to the
    human) or ``blocked`` waiting on the human, so the next /academy:decide asks it.

    The undo window: the ticket is still ``accepted`` and nothing has been written on it
    since the policy's line but that acceptance itself (no line by an instance or an
    agent, no answer of the human's). Once an inbox run has touched it, the acceptance
    stands: decline the ticket instead."""
    date = date or ac.today()
    _path, meta, body = boardlib.get_ticket(board, tid)
    lines = ac.thread_lines(body)
    idx = max((i for i, (_d, _w, t) in enumerate(lines) if t.startswith(POLICY_MARK)),
              default=None)
    if idx is None:
        raise ac.AcademyError("%s was not accepted under the routine policy; nothing to undo"
                              % tid)
    if meta.get("status") != "accepted":
        raise ac.AcademyError("%s is %s, not accepted: the undo window is closed (decline it "
                              "instead)" % (tid, meta.get("status")))
    for _d, who, text in lines[idx + 1:]:
        if who not in (ac.HUMAN, ac.HUMAN_VIA_SESSION) or text.startswith(
                ("human decision", "undo:")):
            raise ac.AcademyError("%s: %s wrote on it after the policy accepted it (%r): the "
                                  "undo window is closed (decline it instead)"
                                  % (tid, who, text[:60]))
    m = RE_POLICY_WAS.search(lines[idx][2])
    was = m.group(1) if m else "blocked"
    note = "undo: the routine-policy acceptance is reverted; asked again at the next decide"
    boardlib.append_to_ticket(board, tid, note, as_instance=ac.HUMAN, date=date,
                              via=ac.VIA_SESSION)
    _set_choice(board, tid, None)
    if was == "open":
        boardlib.transition_ticket(board, tid, "open", reason="policy acceptance undone",
                                   as_instance=ac.HUMAN, date=date, via=ac.VIA_SESSION)
    else:
        boardlib.transition_ticket(board, tid, "blocked", waiting_on=[ac.HUMAN],
                                   reason="policy acceptance undone", as_instance=ac.HUMAN,
                                   date=date, via=ac.VIA_SESSION)
    return {"ref": tid, "status": was}


# ----------------------------------------------------------------------------
# Batching
# ----------------------------------------------------------------------------

def batches(items, size=4):
    """Group ``items`` into batches of at most ``size``.

    Ordered most-unblocking first, substantive before mechanical, and grouped by
    topic (instance) within ties -- a stable sort, then a plain chunking. Proofs,
    experiments and tests with nothing else to choose (``SELECT_KINDS``) come after, as
    multi-select batches grouped by claim: each of their items carries ``multiselect`` and
    ``select`` (the claim); the human ticks the ones to run (``select``).
    """
    size = max(1, int(size))
    ordered = sorted(items, key=lambda i: (
        -len(i.get("unblocks") or []),
        0 if i.get("kind") == "substantive" else 1,
        str(i.get("instance") or ""),
        str(i.get("id"))))
    single = [i for i in ordered if not _selectable(i)]
    out = [single[i:i + size] for i in range(0, len(single), size)]
    # #86: proofs, experiments and tests are asked as multi-select batches ("tick the ones
    # to run"), grouped by claim (the first ref): a claim's items stay in one batch when
    # they fit, and small groups share a batch up to ``size``
    groups = {}
    for i in ordered:
        if _selectable(i):
            groups.setdefault(i.get("claim") or "(no claim)", []).append(i)
    batch = []
    for claim, group in groups.items():
        group = sorted(group, key=lambda i: str(i.get("id")))
        rows = [dict(i, multiselect=True, select=claim) for i in group]
        if batch and len(batch) + len(rows) > size:
            out.append(batch)
            batch = []
        while len(rows) > size:
            out.append(rows[:size])
            rows = rows[size:]
        batch += rows
    if batch:
        out.append(batch)
    return out


# ----------------------------------------------------------------------------
# Recording
# ----------------------------------------------------------------------------

#: the generic answers a plain ticket always takes, own options or not
PROCEED_WORDS = ("proceed", "yes", "y")
DECLINE_WORDS = ("decline", "no", "n")
GENERIC_WORDS = PROCEED_WORDS + DECLINE_WORDS


def _set_choice(board, tid, value):
    """Write (or, with ``None``, clear) the ticket's ``decision_choice``: the alternative the
    human chose, which the agent resuming the ticket reads and does (#86). A human-only
    field (``ac.TICKET_FIELDS``), written here as the human's answer."""
    store = ac.as_store(board)
    path, meta, body = store.get(tid)
    if value is None:
        if "decision_choice" not in meta:
            return path
        meta.pop("decision_choice")
    else:
        meta["decision_choice"] = " ".join(str(value).split())[:300]
    return store.save(meta, body, path)


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
    alts = {} if own else rulinglib.alternatives(meta.get("ask"))
    c = str(choice or "").strip().lower().strip("()")
    no_action = action in (None, "")
    released = None
    if c in ("release", "accept and release"):
        # #86 ruling 4: accept the edit of a pinned statement and release its pin
        home, pins = pinned_of(meta, workspace)
        if not pins:
            raise ac.AcademyError("%s names no pinned statement of an Author home: nothing to "
                                  "release (record proceed or decline)" % tid)
        own, alts, c, choice = {}, {}, "proceed", "proceed"
        released = (home, pins)
    if (own or alts) and no_action and c in PROCEED_WORDS + ("accept",) and (
            alts or c != "accept"):
        # #86 comment 1: a ticket that names alternatives takes one of them, never a bare
        # proceed (T-0896: "proceed" recorded no option, and the agent blocked again)
        raise ac.AcademyError(
            "%s names alternatives: %s. Record one of their letters (or decline), not a "
            "bare %r" % (tid, "; ".join("(%s) %s" % kv for kv in (own or alts).items()),
                         choice))
    word = c in GENERIC_WORDS and no_action
    chosen = "proceed"
    if own and not word:
        # the ticket's own letters (#125): its (b) is its (b), not the generic decline
        letter, cls, option, _act = rulinglib.pick_own(own, choice, action, tid)
        proceed = cls != "decline"
        chosen = "(%s) %s" % (letter, " ".join(option.split()))
        text = "human decision: (%s) %s [the ticket's own (%s): %s]" % (
            letter, cls, letter, " ".join(option.split())[:120])
    elif alts and c in alts and no_action:
        # an alternative is what to do, never a decline of the ticket ("drop the note")
        proceed, chosen = True, "(%s) %s" % (c, alts[c])
        text = "human decision: %s [one of the ticket's alternatives]" % chosen
    elif alts and not (c in DECLINE_WORDS or str(action or "").lower() == "decline"):
        raise ac.AcademyError("%s names alternatives: %s. --choice takes one of their letters "
                              "or decline" % (tid, "; ".join("(%s) %s" % kv
                                                             for kv in alts.items())))
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
        if released:
            chosen = "accept and release %s" % ", ".join(released[1])
            text = "human decision: %s (the pinned statement's edit is accepted)" % chosen
    if comment.strip():
        text += " -- " + " ".join(comment.split())
    boardlib.append_to_ticket(board, tid, text, as_instance=ac.HUMAN, date=date)
    if proceed:
        _set_choice(board, tid, chosen)
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
    out = {"ref": tid, "status": new}
    if released:
        release_pins(released[0], released[1], tid, comment, date)
        out["released"] = released[1]
    return out


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


def select(board, ticked=(), unticked=(), comment="", date=None):
    """Record one multi-select batch (#86): every ``ticked`` ticket proceeds (``record``,
    ``decision_choice: proceed``); every ``unticked`` one stays on the board as it is (open
    to the human, or blocked on the human), with a ``human decision: not now`` thread line
    and ``decision_choice: not now (<date>)``, so it is not asked again that day and is
    asked again on a later one. Only proofs, experiments and tests pending on the human
    are selectable. Returns ``[{"ref", "status"}]`` in the order given."""
    date = date or ac.today()
    ids = list(ticked) + list(unticked)
    if len(set(ids)) != len(ids):
        raise ac.AcademyError("a ticket is both ticked and unticked, or named twice")
    for tid in ids:
        _p, meta, _b = boardlib.get_ticket(board, tid)
        pending = (meta.get("to") == ac.HUMAN and meta.get("status") == "open") or (
            meta.get("status") == "blocked"
            and ac.HUMAN in [str(w) for w in (meta.get("waiting_on") or [])])
        if meta.get("kind") not in SELECT_KINDS or not pending:
            raise ac.AcademyError("%s is not a multi-select item (a %s ticket, %s): record it "
                                  "on its own" % (tid, meta.get("kind"), meta.get("status")))
    out = []
    for tid in ticked:
        out.append(record(board, tid, "proceed", comment, date=date))
    for tid in unticked:
        text = NOT_NOW + " (unticked in a multi-select batch); it stays on the board and is " \
            "asked again on a later day"
        if comment.strip():
            text += " -- " + " ".join(comment.split())
        boardlib.append_to_ticket(board, tid, text, as_instance=ac.HUMAN, date=date)
        _set_choice(board, tid, "not now (%s)" % date)
        out.append({"ref": tid, "status": boardlib.get_ticket(board, tid)[1].get("status")})
    return out


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

    p = sub.add_parser("policy", help="accept the pending tickets the routine policy covers "
                                      "(workspace.json decisions.routine); prints the digest")
    p.add_argument("--instance"); p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("select", help="record one multi-select batch: ticked proceed, "
                                      "unticked stay on the board (not now)")
    p.add_argument("--ticked", default=""); p.add_argument("--unticked", default="")
    p.add_argument("--comment", default="")

    p = sub.add_parser("undo", help="revert a routine-policy acceptance, until an inbox run "
                                    "touches the ticket")
    p.add_argument("id")

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
            bs = batches(pending_decisions(board, a.instance, ws, date=ac.today()), a.size)
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
        elif a.cmd == "policy":
            done = apply_policy(board, ws, dry_run=a.dry_run, instance=a.instance)
            if a.json:
                print(_wire({"accepted": done, "digest": digest(done)}))
            else:
                line = digest(done)
                print(("(dry run) " if a.dry_run and line else "") + (
                    line or "nothing accepted under the policy"))
        elif a.cmd == "select":
            ids = lambda v: [x for x in re.split(r"[,\s]+", v or "") if x]  # noqa: E731
            print(json.dumps(select(board, ids(a.ticked), ids(a.unticked), a.comment),
                             ensure_ascii=False))
        elif a.cmd == "undo":
            if not ac.RE_TICKET_ID.match(a.id):
                raise ac.AcademyError("undo takes a ticket id, not %r" % a.id)
            print(json.dumps(undo(board, a.id), ensure_ascii=False))
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
