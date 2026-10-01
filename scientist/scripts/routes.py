"""routes.py -- the lab's routing table: who takes a ticket, by kind.

The one part of the Scientist's inbox that is not shared (``inbox.py`` wraps the
academy's ``inbox_core``). ``route(meta)`` gives ``{how, target, why}``. The routed
agent runs on its agent file's model; a ticket's ``budget.max_model``, if present, is
an advisory note and never blocks a route, so no row is ``over_budget`` on the model
(T-0071; academy references/budget.md rules 6 and 7):

==================  ============================================================
kind                route
==================  ============================================================
experiment          agent experimenter (a new experiment and its report)
test                agent experimenter, falsifier first (a conjectured generalization)
code                agent developer, then test-engineer reviews the diff; a title
                    beginning "Upstream:" goes to upstream-contributor (drafts only)
question            agent experimenter (answers from the lab's records; no new compute)
other               human (Roey says what it is)
anything else       reject: not the lab's work (names the usual receiver)
==================  ============================================================
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

ROUTES = {
    "experiment": ("experimenter", "design, header approval, script, queue, report"),
    "test": ("experimenter", "test the falsifier first; the report goes back to the sender"),
    "code": ("developer", "test-first in a worktree; test-engineer reviews the diff"),
    "question": ("experimenter", "answer from the lab's records and results; no new compute"),
}
ELSEWHERE = {"verify": "expert", "cite": "expert", "lookup": "expert", "referee": "expert",
             "prove": "researcher", "review-experiment": "researcher",
             "generalize": "researcher", "notation": "expert or author",
             "build": "author", "figure": "author", "decision": "human or claim-keeper"}


def route(meta):
    kind = meta.get("kind") or "other"
    if kind == "code" and str(meta.get("title") or "").lower().startswith("upstream:"):
        row = {"how": "agent", "target": "upstream-contributor",
               "why": "draft the reproducer, issue text and patch branch; Roey files it"}
    elif kind in ROUTES:
        agent, why = ROUTES[kind]
        row = {"how": "agent", "target": agent, "why": why}
    elif kind == "other":
        row = {"how": "human", "target": "human", "why": "Roey says what it is"}
    else:
        row = {"how": "reject", "target": None,
               "why": "not the lab's work; usually for %s"
               % ELSEWHERE.get(kind, "another instance")}
    return row
