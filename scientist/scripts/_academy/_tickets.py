"""Tickets (docs/protocol.md): vocabulary, transitions, routing edges, blocking,
validation, file names and the thread. Rules on ticket data only; the two rules that
read other tickets through a store (``relay_depth``, ``mirror_blocks``) are in ``_store``.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import os
import re

from ._base import (
    AcademyError, HUMAN, MODELS, RE_COWORK, RE_DATE, RE_INSTANCE, RE_PACKET_ID,
    RE_TICKET_ID, ROLES, today)
from ._files import IDS_DIR, write_frontmatter

# ----------------------------------------------------------------------------
# Tickets
# ----------------------------------------------------------------------------

TICKET_STATUSES = ("open", "accepted", "in-progress", "delivered", "closed",
                   "rejected", "cancelled", "blocked")
TERMINAL = ("closed", "rejected", "cancelled")
TICKET_KINDS = ("verify", "cite", "lookup", "prove", "review-experiment", "generalize",
                "experiment", "test", "code", "notation", "referee", "build", "figure",
                "decision", "question", "research", "note", "write", "apply", "copy",
                "sweep", "other")
PRIORITIES = ("high", "normal", "low")

#: (from, to) -> parties who may make the transition; 'human' may make any, always.
#: Mirrors permissions.json "tickets.transitions" (a test keeps them equal).
TRANSITIONS = {
    ("open", "accepted"): ("receiver",),
    ("open", "rejected"): ("receiver",),
    ("open", "blocked"): ("receiver",),
    ("open", "cancelled"): ("sender",),
    ("accepted", "in-progress"): ("receiver",),
    ("accepted", "blocked"): ("receiver",),
    ("accepted", "rejected"): ("receiver",),
    ("accepted", "cancelled"): ("sender",),
    ("in-progress", "delivered"): ("receiver",),
    ("in-progress", "blocked"): ("receiver",),
    # started, and it turns out it cannot be done as asked: rejected with a reason, as from
    # open or accepted (the human's decision, 2026-11-14; before, the route offered was
    # in-progress -> blocked -> accepted -> rejected)
    ("in-progress", "rejected"): ("receiver",),
    ("in-progress", "cancelled"): ("sender",),
    ("blocked", "accepted"): ("receiver",),
    ("blocked", "in-progress"): ("receiver",),
    ("blocked", "cancelled"): ("sender",),
    ("delivered", "closed"): ("sender",),
    ("delivered", "in-progress"): ("sender",),
}

#: ticket frontmatter fields by owner (mirrors permissions.json "tickets.fields")
TICKET_FIELDS = {
    "system": ("id", "from", "created", "updated"),
    "human_only": ("to",),
    "sender": ("title", "kind", "ask", "deliverable", "refs", "priority", "budget",
               "parent", "blocks", "agenda", "domain", "final_to", "campaign", "cowork"),
    "receiver": ("status", "result", "waiting_on", "blocked_by", "reopen_if", "packets"),
}
TICKET_KEY_ORDER = ("id", "title", "kind", "from", "to", "status", "priority", "ask",
                    "deliverable", "refs", "agenda", "domain", "parent", "final_to", "campaign",
                    "cowork", "blocks", "waiting_on", "blocked_by", "reopen_if", "budget", "result",
                    "packets", "created", "updated")
REQUIRED_TICKET_FIELDS = ("id", "title", "kind", "from", "to", "status", "ask",
                          "deliverable", "priority", "budget", "created", "updated")
THREAD_HEADING = "## Thread"
RE_THREAD_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) ([^\s:]+): (.*)$")
RE_WHO = re.compile(r"^(human|(author|researcher|expert|scientist)@[a-z0-9][a-z0-9-]*"
                    r"(/[a-z0-9][a-z0-9-]*)?)$")


def is_party(name):
    """True for a valid 'from'/'to' value: an instance name or 'human'."""
    return name == HUMAN or (isinstance(name, str) and RE_INSTANCE.match(name) is not None)


#: the ticket chain (docs/protocol.md section 5); permissions.json tickets.edges overrides
CHAIN_DEFAULT = ("author", "expert", "researcher", "scientist")
#: the directional relay of a crossing: (from role, middle role, "down" or "up") -> agent
RELAYS = {("author", "expert", "down"): "research-intake",
          ("researcher", "expert", "up"): "paper-liaison",
          ("expert", "researcher", "down"): "experiment-spec",
          ("scientist", "researcher", "up"): "lit-request"}
#: the agent name of a role skill running in the main session inside a home
MAIN_AGENT = "main"


def role_of(party, workspace=None):
    """The role of an instance name ('author@main' -> 'author'); None for 'human'."""
    if not party or party == HUMAN:
        return None
    inst = (workspace or {}).get("instances", {}).get(party)
    if inst and inst.get("role"):
        return inst["role"]
    m = RE_INSTANCE.match(str(party))
    return m.group(1) if m else None


def ticket_edges(perms):
    """permissions.json tickets.edges with defaults: chain, maxHops, liaisons, exempt."""
    e = ((perms or {}).get("tickets") or {}).get("edges") or {}
    return {"chain": list(e.get("chain") or CHAIN_DEFAULT),
            "maxHops": int(e.get("maxHops", 3)),
            "liaisons": dict(e.get("liaisons") or {}),
            "exempt": list(e.get("exempt") or [])}


def relay_return_ready(meta, status_of, workspace=None):
    """Whether a blocked relay parent is ready for its return leg (protocol section 5.2).

    True when ``meta`` is ``blocked``, carries a ``final_to`` beyond its receiver's own
    role, waits on ticket ids only (no ``human``), and every one of them is
    ``delivered`` or terminal. ``status_of`` maps a ticket id to its status (None when
    the ticket is not found). A ``research`` ticket to an Expert with no ``final_to``
    (or ``final_to`` the Expert) reads as ``final_to: researcher``, as research-intake
    reads it.
    """
    if meta.get("status") != "blocked":
        return False
    ft = meta.get("final_to")
    final = (ft if ft in ROLES else role_of(ft, workspace)) if ft else None
    receiver = role_of(meta.get("to"), workspace)
    if meta.get("kind") == "research" and receiver == "expert" and \
            final in (None, "expert"):
        final = "researcher"
    if final is None or final == receiver:
        return False
    return released_waits(meta, status_of)


def released_waits(meta, status_of):
    """Whether a pending-blocked ticket has nothing left to wait for: ``meta`` is ``blocked``
    (not a dead route), ``waiting_on`` holds ticket ids only (no ``human``, no instance),
    and every one of them is ``delivered`` or terminal. ``status_of`` maps a ticket id to
    its status (None when not found). The shared wait rule of the relay return leg and of
    a wrapper that releases its own blocked tickets (the Author's)."""
    if meta.get("status") != "blocked" or is_dead_route(meta):
        return False
    waits = [str(w) for w in (meta.get("waiting_on") or [])]
    if not waits or not all(RE_TICKET_ID.match(w) for w in waits):
        return False
    return all(status_of(w) in ("delivered",) + TERMINAL for w in waits)


def ticket_edge_allowed(frm, to, agent, perms, workspace=None, final_to=None, depth=0,
                        clerical=False):
    """Whether ``agent`` of instance ``frm`` may file a ticket to ``to``.

    Rules (docs/protocol.md section 5): 'human' at either end is allowed; a clerical
    ticket or an exempt agent is allowed; the same role is allowed; otherwise the roles
    must be adjacent in the chain and ``agent`` a liaison of that direction.
    ``final_to`` (a role or instance) must lie beyond ``to`` as seen from ``frm``, and
    ``depth`` (relay_depth of the parent) + 1 may not exceed maxHops.
    Returns ``(allowed, reason)``.
    """
    edges = ticket_edges(perms)
    chain = edges["chain"]
    rf, rt = role_of(frm, workspace), role_of(to, workspace)
    if final_to:
        rF = final_to if final_to in chain else role_of(final_to, workspace)
        if rF not in chain:
            return False, "final_to must be a chain role or an instance, not %r" % final_to
        if rt is None:
            return False, "final_to needs a receiver with a role, not 'human'"
        if rF != rt and rf in chain and rt in chain:
            i, j, k = chain.index(rf), chain.index(rt), chain.index(rF)
            if not (min(i, k) < j < max(i, k)):
                return False, ("final_to %s does not lie beyond %s as seen from %s"
                               % (rF, rt, rf))
        if depth + 1 > edges["maxHops"]:
            return False, "the relay chain would exceed %d hops" % edges["maxHops"]
    if frm == HUMAN or to == HUMAN:
        return True, "human"
    if clerical or agent in edges["exempt"]:
        return True, "clerical"
    if rf == rt:
        return True, "same role"
    if rf not in chain or rt not in chain:
        return False, "unknown role for %r or %r" % (frm, to)
    i, j = chain.index(rf), chain.index(rt)
    if abs(i - j) != 1:
        step = chain[i + (1 if j > i else -1)]
        relay = RELAYS.get((rf, step, "down" if j > i else "up"), "its relay")
        return False, ("%s may not file to %s: file to the %s with final_to %s; "
                       "%s relays it" % (rf, rt, step, rt, relay))
    names = edges["liaisons"].get("%s->%s" % (rf, rt), [])
    who = agent or MAIN_AGENT
    if who in names:
        return True, "liaison"
    return False, ("%s is not a liaison for %s->%s (liaisons: %s); file it to your own "
                   "%s instance instead, with the ask: its inbox routes it and a liaison "
                   "files it with the %s"
                   % (who, rf, rt, ", ".join(names) or "none", rf, rt))


def parties(meta, instance):
    """The parties ``instance`` plays on a ticket: a subset of {'sender','receiver'}.

    ``instance`` is the caller's instance name, or 'human' for the human (who is also
    allowed everything regardless).
    """
    out = set()
    if meta.get("from") == instance:
        out.add("sender")
    if meta.get("to") == instance:
        out.add("receiver")
    return out


def transition_route(old, new):
    """The shortest chain of statuses from ``old`` to ``new`` over TRANSITIONS, or None."""
    seen, queue = {old: [old]}, [old]
    for cur in queue:
        for (a, b) in TRANSITIONS:
            if a == cur and b not in seen:
                seen[b] = seen[cur] + [b]
                queue.append(b)
    return seen.get(new)


def can_transition(old, new, party_set, human=False):
    """Whether a caller playing ``party_set`` may move a ticket from ``old`` to ``new``.

    The human may make any change between two valid statuses, including
    re-opening a terminal ticket (-> 'open'). Returns (allowed, reason).
    """
    if old not in TICKET_STATUSES or new not in TICKET_STATUSES:
        return False, "unknown status %r -> %r" % (old, new)
    if old == new:
        return True, "no change"
    if human:
        return True, "human"
    who = TRANSITIONS.get((old, new))
    if who is None:
        route = transition_route(old, new)
        hint = "; go one step at a time: %s" % " -> ".join(route) if route else ""
        if route and new == "delivered" and old in ("open", "accepted"):
            hint += ("; or, as the receiver, in one call: tickets_update deliver: true "
                     "with fields.result")
        return False, "%s -> %s is not a transition%s" % (old, new, hint)
    if set(who) & set(party_set):
        return True, "allowed"
    return False, "%s -> %s is made by the %s" % (old, new, " or ".join(who))


def allowed_moves(old, party_set, human=False):
    """The statuses a caller playing ``party_set`` may move a ticket to from ``old``
    (sorted; every other valid status for the human)."""
    if human:
        return sorted(s for s in TICKET_STATUSES if s != old)
    return sorted(b for (a, b), who in TRANSITIONS.items()
                  if a == old and set(who) & set(party_set))


def editable_fields(party_set, human=False):
    """The frontmatter fields a caller may change directly (status goes via can_transition)."""
    if human:
        return set(TICKET_KEY_ORDER)
    out = set()
    for p in party_set:
        if p in ("sender", "receiver"):
            out.update(TICKET_FIELDS[p])
    return out


def is_dead_route(meta):
    """A ticket whose route was abandoned: both ``blocked_by`` and ``reopen_if`` (the one
    predicate of validate_ticket, apply_blocking, the inbox core and the board codec)."""
    return bool(meta.get("blocked_by") and meta.get("reopen_if"))


#: ``blocked_by`` names a ticket or a registry object: ``T-0007``, ``GEO-31``, ``Q1``,
#: ``EX-L3``, ``PA-5w``, or namespaced (``paper:lem:x``, ``lab:foo``, ``nb:GEO-31``)
RE_BLOCKED_BY = re.compile(r"^(?:[a-z][a-z0-9]*:[^\s:]+(?::[^\s:]+)*"
                           r"|[A-Z][A-Z0-9]*(?:-[A-Za-z0-9.]+)+|[A-Z]+\d+)$")

BLOCK_FIELDS = ("waiting_on", "blocked_by", "reopen_if")
REOPEN_ONLY = "reopen applies only to blocked -> accepted of a dead-route ticket"


def reason_needed(old, new):
    """Whether moving a ticket ``old -> new`` must carry a reason in the thread."""
    return new in ("rejected", "cancelled") or (old, new) == ("delivered", "in-progress")


def _has_tried_after_reopen(body):
    """True when the thread has a ``tried:`` entry after its last ``reopened:`` entry (a
    second dead-route block needs its own)."""
    tried = False
    for _date, _who, text in thread_lines(body):
        if text.startswith("reopened:"):
            tried = False
        elif text.startswith("tried:"):
            tried = True
    return tried


def apply_blocking(old_meta, meta, new, reason="", waiting_on=None, blocked_by=None,
                   reopen_if=None, reopen="", human=False):
    """The blocking rules of a status move ``old_meta['status'] -> new`` (docs/protocol.md
    section 4), once for board.py and the MCP ``tickets_update``.

    ``meta`` is the ticket being changed (mutated in place); ``old_meta`` its state before
    the move. Returns the thread entries to append, in the one order every transport
    writes them -- ``tried:`` and ``set blocked_by/reopen_if`` (a dead route) or ``set
    waiting_on`` (pending) on the way into ``blocked``, ``reopened:`` on the way out of a
    dead route; the caller appends them (after any ``set result:`` line, before its own
    ``status old -> new`` line). Raises AcademyError.

    A dead-route ticket leaves ``blocked`` only by ``accepted`` with ``reopen`` (the new
    mechanism) or by ``cancelled``; **the human** may leave it by any transition, giving
    ``reopen`` or ``reason`` as the record (written as ``reopened:`` when the ticket goes
    to ``accepted``). ``reopen`` applies only to a dead-route ticket moving to ``accepted``.
    """
    old = old_meta.get("status")
    was_dead = old == "blocked" and is_dead_route(old_meta)
    reason = " ".join(str(reason or "").split())
    reopen = " ".join(str(reopen or "").split())
    bb = " ".join(str(blocked_by or "").split()) or None
    ri = " ".join(str(reopen_if or "").split()) or None
    wo = [str(w) for w in (waiting_on or [])]
    lines = []
    add = lines.append

    if new != "blocked" and (bb or ri or wo):
        raise AcademyError("blocked_by, reopen_if and waiting_on belong to a move to blocked")
    if reopen and not (was_dead and new == "accepted"):
        raise AcademyError(REOPEN_ONLY)
    if reason_needed(old, new) and not reason:
        raise AcademyError("%s -> %s needs a reason" % (old, new))
    if new == "blocked":
        if wo and (bb or ri):
            raise AcademyError("blocked is pending (waiting_on) or a dead route "
                               "(blocked_by and reopen_if), not both")
        if bb or ri:
            if not (bb and ri):
                raise AcademyError("a dead-route block needs both blocked_by and reopen_if")
            if not RE_BLOCKED_BY.match(bb):
                raise AcademyError("blocked_by must be a ticket or registry id (T-0007, "
                                   "GEO-31, paper:lem:x), not %r" % bb)
            if not reason:
                raise AcademyError("a dead-route block needs a reason naming what was tried")
            meta["blocked_by"], meta["reopen_if"], meta["waiting_on"] = bb, ri, []
            add("tried: %s" % reason)
            add("set blocked_by: %s; reopen_if: %s" % (bb, ri))
        else:
            wo = wo or [str(w) for w in (meta.get("waiting_on") or [])]
            if not wo:
                raise AcademyError("a blocked ticket needs waiting_on, or both blocked_by "
                                   "and reopen_if")
            meta["waiting_on"] = wo
            meta.pop("blocked_by", None)
            meta.pop("reopen_if", None)
            add("set waiting_on: [%s]" % ", ".join(wo))
        return lines
    if was_dead and new != "cancelled":
        if new == "accepted":
            if not (reopen or (human and reason)):
                raise AcademyError("a dead-route ticket reopens by blocked -> accepted with "
                                   "reopen (the new mechanism)")
        elif not human:
            raise AcademyError("a dead-route ticket reopens only by blocked -> accepted "
                               "with reopen (the new mechanism); the sender may cancel, "
                               "with a reason")
        elif not reason:
            raise AcademyError("the human leaving a dead route gives a reason (the new "
                               "mechanism, or why the route is dropped)")
        if new == "accepted":
            add("reopened: %s" % (reopen or reason))
    if meta.get("waiting_on"):
        meta["waiting_on"] = []
    meta.pop("blocked_by", None)
    meta.pop("reopen_if", None)
    return lines


def validate_ticket(meta, body=None, workspace=None):
    """Return a list of problems with a ticket (empty when valid). See docs/protocol.md.

    With ``workspace`` (a loaded workspace.json), ``from``, ``to`` and an instance
    ``final_to`` must also name an instance of it (or ``human``): a ticket addressed to
    an instance that was renamed or removed is a problem, not a silent dead letter.
    """
    probs = []
    for f in REQUIRED_TICKET_FIELDS:
        if meta.get(f) in (None, ""):
            probs.append("missing %s" % f)
    known = set(TICKET_KEY_ORDER)
    for k in meta:
        if k not in known:
            probs.append("unknown field %s" % k)
    if meta.get("id") and not RE_TICKET_ID.match(str(meta["id"])):
        probs.append("id must look like T-0001")
    if meta.get("kind") and meta["kind"] not in TICKET_KINDS:
        probs.append("kind %r is not one of %s" % (meta["kind"], ", ".join(TICKET_KINDS)))
    for f in ("from", "to"):
        if meta.get(f) and not is_party(meta[f]):
            probs.append("%s must be an instance name or 'human'" % f)
    if workspace is not None:
        known_inst = (workspace.get("instances") or {})
        for f in ("from", "to"):
            v = meta.get(f)
            if v and is_party(v) and v != HUMAN and v not in known_inst:
                probs.append("%s %r is not an instance of workspace.json" % (f, v))
        ft = meta.get("final_to")
        if ft and ft not in ROLES and RE_INSTANCE.match(str(ft)) and ft not in known_inst:
            probs.append("final_to %r is not an instance of workspace.json" % ft)
    st = meta.get("status")
    if st and st not in TICKET_STATUSES:
        probs.append("status %r is not one of %s" % (st, ", ".join(TICKET_STATUSES)))
    if meta.get("priority") and meta["priority"] not in PRIORITIES:
        probs.append("priority must be one of %s" % ", ".join(PRIORITIES))
    for f in ("created", "updated"):
        if meta.get(f) and not RE_DATE.match(str(meta[f])):
            probs.append("%s must be YYYY-MM-DD" % f)
    for f in ("refs", "blocks", "waiting_on", "packets"):
        if meta.get(f) is not None and not isinstance(meta[f], list):
            probs.append("%s must be a list" % f)
    for f in ("blocks",):
        for t in meta.get(f) or []:
            if not RE_TICKET_ID.match(str(t)):
                probs.append("%s entry %r is not a ticket id" % (f, t))
    for p in meta.get("packets") or []:
        if not RE_PACKET_ID.match(str(p)):
            probs.append("packets entry %r is not a packet id" % p)
    if meta.get("parent") and not RE_TICKET_ID.match(str(meta["parent"])):
        probs.append("parent must be a ticket id")
    if meta.get("campaign") is not None and (not isinstance(meta["campaign"], str)
                                             or "\n" in meta["campaign"]):
        probs.append("campaign must be a registry id (the campaign's target)")
    if meta.get("cowork") is not None and not RE_COWORK.match(str(meta["cowork"])):
        probs.append("cowork must be a slug [a-z0-9-] (the plan file board/cowork/<slug>.md)")
    if meta.get("campaign") and meta.get("cowork"):
        probs.append("a ticket belongs to one workplan: campaign or cowork, not both")
    ft = meta.get("final_to")
    if ft and ft not in ROLES and not RE_INSTANCE.match(str(ft)):
        probs.append("final_to must be a role or an instance name, not %r" % ft)
    b = meta.get("budget")
    if b is not None:
        if not isinstance(b, dict):
            probs.append("budget must be a map {runs[, max_model]}")
        else:
            if not (isinstance(b.get("runs"), int) and b["runs"] >= 1):
                probs.append("budget.runs must be a positive integer")
            # optional advisory note, never a gate; checked only for typos
            if b.get("max_model") is not None and b["max_model"] not in MODELS:
                probs.append("budget.max_model, when given, must be one of %s"
                             % ", ".join(MODELS))
    for f in ("blocked_by", "reopen_if"):
        v = meta.get(f)
        if v is not None and (not isinstance(v, str) or "\n" in v):
            probs.append("%s must be a single line" % f)
    pending = bool(meta.get("waiting_on"))
    dead = is_dead_route(meta)
    if isinstance(meta.get("blocked_by"), str) and meta["blocked_by"].strip() \
            and "\n" not in meta["blocked_by"] and not RE_BLOCKED_BY.match(
                meta["blocked_by"].strip()):
        probs.append("blocked_by must be a ticket or registry id (T-0007, GEO-31, "
                     "paper:lem:x), not %r" % meta["blocked_by"])
    if st == "blocked":
        if pending and (meta.get("blocked_by") or meta.get("reopen_if")):
            probs.append("a blocked ticket is pending (waiting_on) or a dead route "
                         "(blocked_by and reopen_if), not both")
        elif not pending and not dead:
            probs.append("a blocked ticket needs waiting_on, or both blocked_by and reopen_if")
    else:
        if pending:
            probs.append("waiting_on must be empty unless status is blocked")
        if meta.get("blocked_by") or meta.get("reopen_if"):
            probs.append("blocked_by and reopen_if must be empty unless status is blocked")
    if st in ("delivered", "closed") and not meta.get("result"):
        probs.append("a %s ticket needs result" % st)
    if body is not None:
        if THREAD_HEADING not in body.split("\n"):
            probs.append("missing '## Thread' section")
        else:
            if st == "blocked" and dead and not pending and \
                    not _has_tried_after_reopen(body):
                probs.append("a dead-route block needs a thread line 'tried: <what was "
                             "tried>' (after the last 'reopened:' line, if any)")
            for ln in thread_lines(body, raw=True):
                if not RE_THREAD_LINE.match(ln) and not ln.startswith("  "):
                    probs.append("malformed thread line: %r" % ln)
                    continue
                m = RE_THREAD_LINE.match(ln)
                if m and not RE_WHO.match(m.group(2)):
                    probs.append("bad speaker %r in thread" % m.group(2))
    return probs


def slugify(title, maxlen=40, default="ticket"):
    """Lower-case ASCII slug of ``title``: [a-z0-9-], at most ``maxlen`` chars."""
    s = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rstrip("-")
    return s or default


def ticket_filename(tid, title):
    """'T-0007', 'Check Lemma 4.2' -> 'T-0007-check-lemma-4-2.md' (never renamed later)."""
    return "%s-%s.md" % (tid, slugify(title))


def packet_filename(pid, title):
    """'P-0003', 'Verify lem:x' -> 'P-0003-verify-lem-x.md'."""
    return "%s-%s.md" % (pid, slugify(title, default="packet"))


def find_ticket(board, tid):
    """Path of the ticket file with id ``tid`` anywhere on the board, or None."""
    return _find_by_id(board, tid)


def find_packet(board, pid):
    """Path of the packet file with id ``pid`` (under board/packets/), or None."""
    return _find_by_id(os.path.join(str(board), "packets"), pid)


def _find_by_id(root, xid):
    rx = re.compile(r"^%s(?:-.*)?\.md$" % re.escape(xid))
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in (".git", IDS_DIR)]
        for f in filenames:
            if rx.match(f):
                return os.path.join(dirpath, f)
    return None


def thread_lines(body, raw=False):
    """The entries of the body's '## Thread' section (the last section of a ticket).

    With ``raw`` the non-blank lines are returned as they are (continuation lines
    included); otherwise a list of ``(date, who, text)`` with continuation lines
    (indented two spaces) joined to their entry by a newline.
    """
    lines = body.replace("\r\n", "\n").split("\n")
    try:
        start = lines.index(THREAD_HEADING) + 1
    except ValueError:
        return []
    section = []
    for ln in lines[start:]:
        if ln.startswith("## "):
            break
        if ln.strip():
            section.append(ln.rstrip())
    if raw:
        return section
    out = []
    for ln in section:
        m = RE_THREAD_LINE.match(ln)
        if m:
            out.append([m.group(1), m.group(2), m.group(3)])
        elif ln.startswith("  ") and out:
            out[-1][2] += "\n" + ln[2:]
    return [tuple(x) for x in out]


def format_who(instance, agent=""):
    """Thread speaker: 'human', '<instance>' or '<instance>/<bare agent>'."""
    if not instance or instance == HUMAN:
        return HUMAN
    return "%s/%s" % (instance, agent) if agent else instance


def append_thread(body, who, text, date=None):
    """Return ``body`` with one entry appended to its '## Thread' section.

    Creates the section at the end if it is missing. Multi-line ``text`` is written
    as continuation lines indented by two spaces. Existing lines are never touched.
    """
    if not RE_WHO.match(who):
        raise AcademyError("bad thread speaker %r" % who)
    date = date or today()
    parts = str(text).strip().replace("\r\n", "\n").split("\n")
    entry = ["- %s %s: %s" % (date, who, parts[0])] + ["  " + p for p in parts[1:]]
    body = body.replace("\r\n", "\n")
    lines = body.split("\n")
    if THREAD_HEADING not in lines:
        base = body.rstrip("\n")
        return (base + "\n\n" if base else "") + THREAD_HEADING + "\n\n" + \
            "\n".join(entry) + "\n"
    start = lines.index(THREAD_HEADING) + 1
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    last = end
    while last > start and not lines[last - 1].strip():
        last -= 1
    if last == start:                      # empty section: keep one blank line
        new = lines[:start] + [""] + entry + lines[end:] if end < len(lines) else \
            lines[:start] + [""] + entry + [""]
    else:
        new = lines[:last] + entry + lines[last:]
    out = "\n".join(new)
    return out if out.endswith("\n") else out + "\n"


def thread_is_append_only(old_body, new_body):
    """True when ``new_body``'s thread starts with every line of ``old_body``'s thread."""
    old, new = thread_lines(old_body, raw=True), thread_lines(new_body, raw=True)
    return new[:len(old)] == old


def new_ticket(meta, ask_detail=""):
    """Render a new ticket file (frontmatter in canonical order + the standard body)."""
    ordered = {k: meta[k] for k in TICKET_KEY_ORDER if k in meta}
    for k in meta:
        if k not in ordered:
            ordered[k] = meta[k]
    body = "\n## Ask\n\n%s\n\n## Result\n\n\n%s\n\n" % (
        ask_detail.strip() or ordered.get("ask", ""), THREAD_HEADING)
    return write_frontmatter(ordered, body)
