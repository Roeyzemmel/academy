"""routes.py -- the Expert's routing table: which skill or agent handles a ticket.

The one part of the Expert's inbox that is not shared (``inbox.py`` wraps the academy's
``inbox_core``). ``route(meta)`` gives ``{how, target, why}``:

| kind | route |
|---|---|
| verify | skill ``expert:verify`` (review-chair; two rigor-reviewer runs) |
| cite | skill ``expert:cite`` (librarian) |
| lookup, question | agent ``clerk``; a miss escalates to ``librarian`` |
| referee | skill ``expert:referee`` |
| notation | skill ``expert:domain`` (librarian) |
| any kind with ``final_to`` beyond the Expert | agent ``research-intake`` (toward the Researcher or Scientist) or ``paper-liaison`` (toward an Author): a relay |
| research without ``final_to``, or with ``final_to`` the Expert | agent ``research-intake``, read as ``final_to: researcher`` |
| note | ``human``: a note is for the Author; block with ``waiting_on [human]`` |
| decision, other | ``human``: block the ticket with ``waiting_on: [human]`` |
| any other kind | ``reject``: not Expert work; the reason names the role it belongs to and, for Researcher or Scientist work, says to ask through a ``research`` ticket to the Expert with ``final_to`` |
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402

ROUTES = {
    "verify": ("skill", "expert:verify", "review-chair runs the pair and applies the table"),
    "cite": ("skill", "expert:cite", "librarian: bib entry, card, index row"),
    "lookup": ("agent", "clerk", "quick answer from hot.md and the library; a miss escalates"),
    "question": ("agent", "clerk", "the clerk first; a miss escalates to the librarian"),
    "referee": ("skill", "expert:referee", "cold whole-paper read, landed as a packet"),
    "notation": ("skill", "expert:domain", "librarian edits the domain pack"),
    "research": ("agent", "research-intake",
                 "relay toward the Researcher: no final_to (or final_to the Expert) is "
                 "read as final_to researcher"),
    "note": ("human", "human", "a note is for the Author; block with waiting_on [human]"),
    "decision": ("human", "human", "only the human decides: block with waiting_on [human]"),
    "other": ("human", "human", "no Expert route: block with waiting_on [human]"),
}
BELONGS = {
    "prove": "researcher", "review-experiment": "researcher", "generalize": "researcher",
    "experiment": "scientist", "test": "scientist", "code": "scientist",
    "build": "author", "figure": "author",
}
#: relay tickets (final_to beyond the Expert) go to the relay of their crossing
RELAYS = {"researcher": "research-intake", "scientist": "research-intake",
          "author": "paper-liaison"}


def _final_role(meta):
    ft = meta.get("final_to")
    return ac.role_of(ft) if ft and ft not in ac.ROLES else ft


def route(meta):
    final = _final_role(meta)
    if final and final != "expert" and final in RELAYS:
        return {"how": "agent", "target": RELAYS[final],
                "why": "relay toward %s: check, sharpen, forward (final_to)" % final}
    kind = meta.get("kind") or "other"
    if kind in ROUTES:
        how, target, why = ROUTES[kind]
        return {"how": how, "target": target, "why": why}
    role = BELONGS.get(kind, "another role")
    why = "a %s ticket is %s work, not Expert work; reject it with that reason" % (kind, role)
    if role in ("researcher", "scientist"):
        why += ("; ask through a research ticket to the Expert with final_to %s" % role)
    return {"how": "reject", "target": None, "why": why}
