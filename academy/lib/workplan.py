"""workplan -- the shared mechanics of a campaign and a cowork: tags, state, caps.

Two kinds of workplan reach other roles only through tickets and then wait for the next
actor (academy/references/roster-rules.md, "Role cut", rule 5):

* a **campaign** (``/researcher:campaign``): autonomous, research-focused, led by the
  Researcher's ``lead-researcher``; its tickets carry ``campaign: <target id>``;
* a **cowork** (``/academy:cowork``): interactive, led by the human with the main session
  as orchestrator (academy/references/orchestrator.md); its tickets carry
  ``cowork: <slug>`` and its plan is ``<board>/cowork/<slug>.md``.

This module is stdlib only and knows nothing of a board's storage: it reads ticket
metadata dicts (as ``BoardStore.iter_meta`` yields them). ``academy_common`` (vendored as
every plugin's ``_academy.py``) knows the two tag fields; a script outside the academy
plugin imports this file by path (``import_workplan`` in researcher's notebook.py).

**State**, computed from the tagged tickets, never hand-kept. Each ticket is classed:

* ``done`` -- delivered, closed, rejected or cancelled;
* ``decision`` -- addressed to the human, or blocked with ``human`` in ``waiting_on``:
  only the human can move it (``/academy:decide``);
* ``dead`` -- blocked as a dead route (``blocked_by`` and ``reopen_if``): held;
* ``out`` -- open, accepted, in progress, or blocked on another ticket, addressed to an
  instance other than the lead: it waits for that role's next actor;
* ``own`` -- the same, addressed to the lead's own instance: work the lead can do.

A group of tickets (one approach of a campaign, one task of a cowork, or the whole
workplan) is then:

* ``PAUSE`` when a decision is pending and nothing else can move it (no ``own`` ticket
  and nothing ``out``), or always for a per-group decision (``pause_on_any``);
* ``WAITING`` when tickets are out with other actors and the lead has nothing of its own;
* ``ACTIVE`` when the lead has work (an ``own`` ticket, or no open ticket at all);
* ``DONE`` when every ticket is done (and there is at least one).

Across groups (``combine``): ``PAUSE`` when every active group is paused, ``WAITING`` when
every active group is waiting or paused and one waits, ``DONE`` when all are done, else
``ACTIVE``.
"""

import os
import re

KINDS = ("campaign", "cowork")
TERMINAL = ("delivered", "closed", "rejected", "cancelled")
OPEN = ("open", "accepted", "in-progress", "blocked")
STATES = ("ACTIVE", "WAITING", "PAUSE", "DONE")
HUMAN = "human"
RE_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
#: where a cowork's plan lives, under the board
COWORK_DIR = "cowork"


class WorkplanError(ValueError):
    pass


# ----------------------------------------------------------------------------
# Tags
# ----------------------------------------------------------------------------

def check_tag(kind, value):
    """The problem with tagging ``kind: value``, or ''. A campaign names its target
    (a registry id, one line); a cowork a slug (``[a-z0-9-]``, as its plan file)."""
    if kind not in KINDS:
        return "a workplan is a %s, not %r" % (" or a ".join(KINDS), kind)
    if not isinstance(value, str) or not value.strip() or "\n" in value:
        return "%s must be one line" % kind
    if kind == "cowork" and not RE_SLUG.match(value):
        return "cowork must be a slug ([a-z0-9-], the plan file's name), not %r" % value
    return ""


def tag_of(meta):
    """``(kind, value)`` of a ticket's workplan tag, or ``(None, None)``."""
    for k in KINDS:
        v = (meta or {}).get(k)
        if v:
            return k, str(v)
    return None, None


def tagged(metas, kind, value):
    """The tickets carrying ``kind: value``."""
    return [m for m in metas if (m or {}).get(kind) == value]


def active(metas, kind):
    """``{value: [ticket ids not done]}`` of every workplan of ``kind`` with an open
    ticket: the active campaigns or coworks."""
    out = {}
    for m in metas:
        v = (m or {}).get(kind)
        if v and m.get("status") not in TERMINAL:
            out.setdefault(str(v), []).append(m.get("id"))
    return {k: sorted(v) for k, v in sorted(out.items())}


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------

def _waits(meta):
    return [str(w) for w in (meta.get("waiting_on") or [])]


def ticket_class(meta, lead=None):
    """One of ``done``, ``decision``, ``dead``, ``out``, ``own`` (see the module doc).
    ``lead`` is the leading instance (a campaign's Researcher; a cowork has none, so
    every open ticket is ``out``)."""
    st = meta.get("status")
    if st in TERMINAL:
        return "done"
    if meta.get("to") == HUMAN or (st == "blocked" and HUMAN in _waits(meta)):
        return "decision"
    if st == "blocked" and meta.get("blocked_by") and meta.get("reopen_if"):
        return "dead"
    if lead and meta.get("to") == lead:
        return "own"
    return "out"


def group_state(metas, lead=None, pause_on_any=False):
    """``{state, counts, decision, out, own, dead, done}`` of one group of tickets.

    ``pause_on_any``: a pending decision pauses the group whatever else is open (an
    approach whose ticket needs the human: its route depends on the answer)."""
    by = {"done": [], "decision": [], "dead": [], "out": [], "own": []}
    for m in metas:
        by[ticket_class(m, lead)].append(m.get("id"))
    if by["decision"] and (pause_on_any or not (by["own"] or by["out"])):
        state = "PAUSE"
    elif by["out"] and not by["own"]:
        state = "WAITING"
    elif metas and not (by["own"] or by["out"] or by["decision"] or by["dead"]):
        state = "DONE"
    else:
        state = "ACTIVE"
    out = {k: sorted(v) for k, v in by.items()}
    out["state"] = state
    out["counts"] = {k: len(v) for k, v in by.items()}
    return out


def combine(states):
    """The state of a workplan from its active groups' states (see the module doc)."""
    states = [s for s in states if s]
    if not states:
        return "ACTIVE"
    if all(s == "DONE" for s in states):
        return "DONE"
    live = [s for s in states if s != "DONE"]
    if all(s == "PAUSE" for s in live):
        return "PAUSE"
    if all(s in ("PAUSE", "WAITING") for s in live):
        return "WAITING"
    return "ACTIVE"


def state(metas, kind, value, lead=None):
    """The state of one workplan from every ticket on the board: the group of its
    tagged tickets (``group_state``), plus ``kind`` and ``value``."""
    st = group_state(tagged(metas, kind, value), lead)
    st.update(kind=kind, value=value)
    return st


# ----------------------------------------------------------------------------
# Caps (academy/references/budget.md, "Campaigns" and "Cowork")
# ----------------------------------------------------------------------------

def caps(kind, rounds=None, agents=None, runs=None, profile="", cloud=False):
    """The normalized caps of a workplan, or ``WorkplanError`` naming the problem.

    A campaign requires ``rounds`` and ``agents`` (stop and ask: suggest 3 and 4);
    ``runs`` defaults to 0, is forced to 0 in a cloud session, and needs ``profile``
    when positive. A cowork is interactive: only ``agents`` binds (parallel tickets at
    once, default 1); ``rounds`` and ``runs`` are advisory and recorded as given.
    Only validation: the driver keeps count."""
    if kind not in KINDS:
        raise WorkplanError("unknown workplan kind %r" % kind)
    if kind == "campaign":
        for name, v in (("--rounds", rounds), ("--agents", agents)):
            if v is None:
                raise WorkplanError("%s is required: stop and ask (suggest 3 rounds, "
                                    "4 agents)" % name)
            if v < 1:
                raise WorkplanError("%s must be at least 1" % name)
    else:
        agents = 1 if agents is None else agents
        if agents < 1:
            raise WorkplanError("--agents must be at least 1")
    runs = 0 if runs is None else runs
    if runs < 0:
        raise WorkplanError("--runs must not be negative")
    forced = bool(cloud) and runs > 0
    if forced:
        runs = 0
    if runs > 0 and not profile:
        raise WorkplanError("--runs %d needs --profile (the one lab profile to queue on)"
                            % runs)
    return {"kind": kind, "rounds": rounds, "agents": agents, "runs": runs,
            "profile": profile or None, "cloud": bool(cloud),
            "runs_forced_to_zero": forced,
            "binding": ["rounds", "agents", "runs"] if kind == "campaign" else ["agents"]}


# ----------------------------------------------------------------------------
# The cowork plan file
# ----------------------------------------------------------------------------

def plan_path(board_dir, slug):
    return os.path.join(board_dir, COWORK_DIR, slug + ".md")


def plans(board_dir):
    """Slugs of the cowork plan files under ``<board>/cowork/``."""
    d = os.path.join(board_dir or "", COWORK_DIR)
    if not os.path.isdir(d):
        return []
    return sorted(f[:-3] for f in os.listdir(d)
                  if f.endswith(".md") and RE_SLUG.match(f[:-3]))


RE_PLAN_STATUS = re.compile(r"^status:\s*(\S+)\s*$", re.M)


def plan_status(text):
    """The ``status:`` line of a plan file's header (``active``, ``closed``), or ''."""
    m = RE_PLAN_STATUS.search(text or "")
    return m.group(1) if m else ""
