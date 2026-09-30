"""routes.py -- the Author's routing table: who handles a ticket or a landing, by kind.

The one part of the Author's inbox that is not shared (``inbox.py`` wraps the academy's
``inbox_core``). The board is the Author's only queue: every work item is a ticket.
``route(meta)`` gives ``{how, target, why}`` for a ticket addressed to the Author, by
its kind:

| kind | route |
|---|---|
| write | agent ``math-writer`` |
| apply, copy | agent ``math-editor`` |
| figure | agent ``figure-maker`` |
| build | agent ``tex-engineer`` |
| notation | agent ``notation-auditor`` |
| sweep | agent ``note-sweeper`` |
| note | agent ``math-writer`` (a literature result from the Expert, folded into the paper) |
| any other kind | ``human``: asked, never guessed |

``land_route(kind, final_to)`` is the agent that lands a returned ticket (one this
Author filed to another role that came back ``delivered``): a verdict or a citation
with ``math-editor``, a proof or an experiment (a ``research`` ticket relayed to the
Researcher or the Scientist) with ``math-writer``, a referee packet with
``/author:notes``.

``OUT_ROUTES`` is how the Author files an ask that leaves it (used by
``agenda.py gaps --file``; a hand-filed ticket uses ``board.py new`` /
``tickets_create`` with the same kind, ``final_to`` and ``agenda``).
"""

#: ticket kind -> (how, target, why)
KIND_ROUTES = {
    "write": ("agent", "math-writer", "prose, definitions, a write-up from a source"),
    "apply": ("agent", "math-editor", "the edit is already decided"),
    "copy": ("agent", "math-editor", "copy-edit a settled section; no mathematics"),
    "figure": ("agent", "figure-maker", "an illustration"),
    "build": ("agent", "tex-engineer", "toolchain or build repair"),
    "notation": ("agent", "notation-auditor", "a notation decision or clash"),
    "sweep": ("agent", "note-sweeper", "the machine-note sweep"),
    "note": ("agent", "math-writer", "fold the literature result into the paper"),
}
#: the ticket kinds an Author files to itself (the work items that stay in the Author)
SELF_KINDS = ("write", "apply", "copy", "figure", "build", "notation", "sweep")
#: ask -> (role of the receiver, ticket kind, final_to, deliverable key). An ask that
#: needs the Researcher or the Scientist goes to the Expert as ``research`` with
#: ``final_to`` (docs/protocol.md section 5).
OUT_ROUTES = {
    "lead": ("expert", "research", "researcher", "prove"),
    "verify": ("expert", "verify", None, "verify"),
    "cite": ("expert", "cite", None, "cite"),
    "experiment": ("expert", "research", "scientist", "experiment"),
    "referee": ("expert", "referee", None, "referee"),
}
DELIVERABLES = {
    "prove": "A proof (or a refutation) of the statement, as a proof object with its "
             "status proposed; the ticket result names it.",
    "verify": "A verification packet with two verdicts; the ticket result names the "
              "verdict and whether a recolour is proposed.",
    "cite": "A bibliography entry and a card with the verbatim quote and version; the "
            "ticket result gives the key and pinpoint.",
    "experiment": "An experiment report packet with its ## Conclusion; the ticket result "
                  "names the lab claim.",
    "referee": "A referee packet on the built PDF.",
}
#: the deliverable of a ticket the Author files to itself
SELF_DELIVERABLE = ("The work done in the paper and recorded; this ticket delivered with "
                    "a one-line result.")
#: returned-ticket kind -> the agent that lands it in the tex
LAND_ROUTES = {"verify": "math-editor", "cite": "math-editor", "research": "math-writer",
               "prove": "math-writer", "experiment": "math-writer"}


def route(meta):
    kind = meta.get("kind") or "other"
    if kind in KIND_ROUTES:
        how, target, why = KIND_ROUTES[kind]
        return {"how": how, "target": target, "why": why}
    return {"how": "human", "target": "human",
            "why": "no Author route for a %s ticket: ask Roey (accept and file a work "
                   "ticket, reject with a reason, forward)" % kind}


def land_route(kind, final_to=None):
    if kind == "referee":
        return {"how": "skill", "target": "author:notes",
                "why": "land the returned referee packet as tickets"}
    return {"how": "agent", "target": LAND_ROUTES.get(kind, "math-editor"),
            "why": "land the returned %s ticket in the tex" % kind}
