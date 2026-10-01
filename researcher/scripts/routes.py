"""routes.py -- the Researcher's routing table: which skill or agent handles a ticket.

The one thing of the Researcher's inbox that is not shared: ``inbox.py`` wraps the
academy's ``inbox_core`` (selection, ordering, return legs, the blocked filter), and asks
``route(meta)`` for the ``{how, target, why}`` of each ticket.

    prove               skill researcher:prove
    review-experiment   skill researcher:review-experiment (or researcher:settle when the
                        report lists candidate counterexamples)
    generalize          skill researcher:generalize
    decision            agent claim-keeper (a status proposal from claims_propose_status)
    question            skill researcher:explore (as a question)
    research            agent lead-researcher
    final_to beyond the Researcher (whatever the kind): agent experiment-spec (toward the
                        Scientist) or lit-request (toward the Expert or the Author)
    everything else     agent lead-researcher, which may reject with a reason
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402

ROUTES = {
    "prove": ("skill", "researcher:prove", "a proof attempt, then a verify ticket"),
    "review-experiment": ("skill", "researcher:review-experiment",
                          "two reviewer runs; researcher:settle when the report lists "
                          "candidate counterexamples"),
    "generalize": ("skill", "researcher:generalize", "conjectures with falsifiers"),
    "decision": ("agent", "claim-keeper", "a status proposal"),
    "question": ("skill", "researcher:explore", "answered as a question"),
    "research": ("agent", "lead-researcher", "brought to the notebook"),
}
#: a ticket whose final_to lies beyond the Researcher goes to the relay of its direction
RELAYS = {"scientist": "experiment-spec", "expert": "lit-request", "author": "lit-request"}
DEFAULT = ("agent", "lead-researcher", "no route of its own; may reject with a reason")


def route(meta):
    ft = meta.get("final_to")
    final = ac.role_of(ft) if ft and ft not in ac.ROLES else ft
    if final and final != "researcher" and final in RELAYS:
        return {"how": "agent", "target": RELAYS[final],
                "why": "relay toward %s: check, sharpen, forward (final_to)" % final}
    how, target, why = ROUTES.get(meta.get("kind"), DEFAULT)
    return {"how": how, "target": target, "why": why}
