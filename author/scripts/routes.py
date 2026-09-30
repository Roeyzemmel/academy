"""routes.py -- the Author's routing table: who handles a ticket or a landing, by kind.

The one part of the Author's inbox that is not shared (``inbox.py`` wraps the academy's
``inbox_core``). ``route(meta)`` gives ``{how, target, why}`` for a ticket addressed to
the Author, by its kind (the roadmap-item kinds ride on self-tickets):

| kind | route |
|---|---|
| write | agent ``math-writer`` |
| apply, copy | agent ``math-editor`` |
| figure | agent ``figure-maker`` |
| build | agent ``tex-engineer`` |
| notation | agent ``notation-auditor`` |
| sweep | agent ``note-sweeper`` |
| note | agent ``math-writer`` (a literature result from the Expert, folded into an item) |
| any other kind | ``human``: asked, never guessed |

``land_route(tag)`` is the agent that lands a returned ticket of a roadmap item: a
verdict or a citation with ``math-editor``, a proof or an experiment with ``math-writer``,
a referee packet with ``/author:notes``.
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
    "note": ("agent", "math-writer", "fold the literature note into a roadmap item"),
}
#: roadmap item tag -> the ticket kind of its self-ticket (items that stay in the Author)
ITEM_KINDS = {"write": "write", "apply": "apply", "figure": "figure", "build": "build",
              "notation": "notation", "sweep": "sweep"}
#: an item's ``route:`` agent -> the ticket kind that routes back to it
AGENT_KINDS = {"math-writer": "write", "math-editor": "apply", "figure-maker": "figure",
               "tex-engineer": "build", "notation-auditor": "notation",
               "note-sweeper": "sweep"}
#: ask items that leave the Author: tag -> the agent that lands the returned ticket
LAND_ROUTES = {"lead": "math-writer", "verify": "math-editor", "cite": "math-editor",
               "experiment": "math-writer"}


def route(meta):
    kind = meta.get("kind") or "other"
    if kind in KIND_ROUTES:
        how, target, why = KIND_ROUTES[kind]
        return {"how": how, "target": target, "why": why}
    return {"how": "human", "target": "human",
            "why": "no Author route for a %s ticket: ask Roey (accept and file an item, "
                   "reject with a reason, forward)" % kind}


def land_route(tag):
    if tag == "referee":
        return {"how": "skill", "target": "author:notes",
                "why": "land the returned referee packet as roadmap items"}
    return {"how": "agent", "target": LAND_ROUTES.get(tag, "math-editor"),
            "why": "land the returned %s ticket in the tex" % tag}
