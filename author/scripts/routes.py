"""routes.py -- the Author's routing table: who handles a ticket or a landing, by kind.

The one part of the Author's inbox that is not shared (``inbox.py`` wraps the academy's
``inbox_core``). The board is the Author's only queue: every work item is a ticket.
``route(meta)`` gives ``{how, target, why}`` for a ticket addressed to the Author, by
its kind (``KIND_ROUTES``).

The tables (kind -> agent, ask -> receiver, returned kind -> lander) are generated from
the data below: ``py routes.py --tables`` prints them, ``py routes.py --sync FILE`` rewrites
the marked blocks of a doc (``skills/inbox/references/routing.md`` holds them; a test
compares). Any other kind routes to ``human``: asked, never guessed.

``land_route(kind)`` is the agent that lands a returned ticket (one this Author filed to
another role that came back ``delivered``): see the landing table.

``OUT_ROUTES`` is how the Author files an ask that leaves it (used by
``agenda.py gaps --file``; a hand-filed ticket uses ``board.py new`` /
``tickets_create`` with the same kind, ``final_to`` and ``agenda``).

The role cut (academy/references/roster-rules.md): the Researcher proves, the Author only
lands. ``route`` rejects a ticket of another role's kind (``BELONGS``), and sends a
self-ticket whose ask needs a new argument (``needs_argument``) to ``research``: the
writer files the argument as a ``research`` ticket and lands what returns.
``check_filed(meta)`` is the check on what an Author writer files for a missing
argument: kind ``research``, to the Expert, ``final_to: researcher``; ``gaps.py`` runs it
before filing.
"""

import re

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
#: kinds that are another role's work: the Author asks for them, it never does them
BELONGS = {"prove": "researcher", "generalize": "researcher",
           "review-experiment": "researcher", "experiment": "scientist",
           "test": "scientist", "code": "scientist"}
#: an ask that needs an argument nobody has delivered yet (the Researcher's work)
RE_NEEDS_ARGUMENT = re.compile(
    r"(?i)\b(missing|new|own|fresh)\s+(argument|proof|lemma|step)s?\b"
    r"|\bfill (in )?the gap\b|\brepair (the|its) (proof|argument)\b"
    r"|\bconstruct (a|the) proof\b|\b(find|give|write) a (new )?proof\b"
    r"|\bprove (that|it|the)\b|\bcleaner formulation\b|\bunifying lemma\b"
    r"|\b(add|drop|weaken|strengthen) (a |the )?hypothes")
#: the self kinds whose ask is checked for a missing argument
WRITER_KINDS = ("write", "apply", "copy", "note")
#: the deliverable of a ticket the Author files to itself
SELF_DELIVERABLE = ("The work done in the paper and recorded; this ticket delivered with "
                    "a one-line result.")
#: returned-ticket kind -> the agent that lands it in the tex
LAND_ROUTES = {"verify": "math-editor", "cite": "math-editor", "research": "math-writer",
               "prove": "math-writer", "experiment": "math-writer"}


def needs_argument(meta):
    """True when a ticket's title or ask asks for an argument that does not exist yet
    (a missing step, a new proof or lemma, a hypothesis change): Researcher work."""
    text = " ".join(str(meta.get(k) or "") for k in ("title", "ask"))
    return bool(RE_NEEDS_ARGUMENT.search(text))


def research_route(why):
    return {"how": "research", "target": "expert",
            "why": "%s: the Researcher proves, the Author only lands. File a `research` "
                   "ticket to the Expert with final_to researcher (check_filed), block "
                   "this one waiting on it, and land what returns" % why}


def check_filed(meta):
    """Problems with a ticket an Author writer files for a missing argument (empty: it
    passes). The role cut: an argument is asked of the Researcher as ``kind: research``,
    ``to`` the Expert (the Author's only neighbour), ``final_to: researcher``; never a
    self ``write``/``apply`` ticket, never ``prove`` to the Expert."""
    probs = []
    kind = meta.get("kind")
    asks_argument = (kind == "prove" or (kind == "research" and str(
        meta.get("final_to") or "researcher").split("@")[0] != "scientist")
        or (kind in WRITER_KINDS + SELF_KINDS and needs_argument(meta)))
    if not asks_argument:
        return probs
    to = str(meta.get("to") or "")
    if kind in WRITER_KINDS or kind in SELF_KINDS:
        probs.append("a missing argument is not a `%s` ticket: file `research` to the "
                     "Expert with final_to researcher" % kind)
    elif kind != "research":
        probs.append("an argument is asked as kind `research`, not `%s`" % kind)
    if to and not to.startswith("expert@"):
        probs.append("an Author files to the Expert (its only neighbour), not %s" % to)
    if kind == "research" or kind not in WRITER_KINDS + SELF_KINDS:
        ft = str(meta.get("final_to") or "")
        if ft.split("@")[0] != "researcher":
            probs.append("final_to must be researcher (the Researcher proves), not %r"
                         % (ft or None))
    return probs


def _human():
    """The human's name from workspace.json (``human.name``), else 'the human'."""
    try:
        import _academy as ac
        return ac.human_name()
    except Exception:       # a routing table must answer even without a workspace
        return "the human"


def route(meta):
    kind = meta.get("kind") or "other"
    if kind in BELONGS:
        role = BELONGS[kind]
        return {"how": "reject", "target": None,
                "why": "a %s ticket is %s work, not the Author's (the Author only lands); "
                       "reject it, and ask through a `research` ticket to the Expert with "
                       "final_to %s" % (kind, role, role)}
    if kind in WRITER_KINDS and needs_argument(meta):
        return research_route("the ask needs an argument nobody has delivered")
    if kind in KIND_ROUTES:
        how, target, why = KIND_ROUTES[kind]
        return {"how": how, "target": target, "why": why}
    return {"how": "human", "target": "human",
            "why": "no Author route for a %s ticket: ask %s (accept and file a work "
                   "ticket, reject with a reason, forward)" % (kind, _human())}


def land_route(kind):
    if kind == "referee":
        return {"how": "skill", "target": "author:notes",
                "why": "land the returned referee packet as tickets"}
    return {"how": "agent", "target": LAND_ROUTES.get(kind, "math-editor"),
            "why": "land the returned %s ticket in the tex" % kind}


# ----------------------------------------------------------------------------
# The documentation tables, generated from the data above
# ----------------------------------------------------------------------------

BLOCKS = ("kinds", "out", "land")


def agents():
    """Every agent the Author's routes name (a ticket route or a landing)."""
    return sorted({t for _h, t, _w in KIND_ROUTES.values()}
                  | {t for t in LAND_ROUTES.values()} | {"math-editor"})


def render_table(name):
    """The markdown table of block ``name`` (``kinds``, ``out`` or ``land``)."""
    if name == "kinds":
        rows = ["| kind | how | target | why |", "|---|---|---|---|"]
        rows += ["| `%s` | %s | `%s` | %s |" % (k, h, t, w)
                 for k, (h, t, w) in KIND_ROUTES.items()]
        rows.append("| any other kind | human | `human` | asked, never guessed |")
    elif name == "out":
        rows = ["| ask | kind | to | final_to |", "|---|---|---|---|"]
        rows += ["| `%s` | `%s` | %s | %s |" % (a, kind, role, ("`%s`" % ft) if ft else "-")
                 for a, (role, kind, ft, _d) in OUT_ROUTES.items()]
    elif name == "land":
        rows = ["| returned kind | how | target |", "|---|---|---|"]
        for kind in sorted(LAND_ROUTES) + ["referee", "(any other)"]:
            r = land_route("other" if kind == "(any other)" else kind)
            rows.append("| `%s` | %s | `%s` |" % (kind, r["how"], r["target"]))
    else:
        raise KeyError(name)
    return "\n".join(rows)


def block_markers(name):
    return "<!-- routes:%s -->" % name, "<!-- /routes:%s -->" % name


def extract_block(text, name):
    """The text between a doc's markers for block ``name`` (stripped), or None."""
    a, b = block_markers(name)
    if a not in text or b not in text:
        return None
    return text.split(a, 1)[1].split(b, 1)[0].strip("\n")


def sync_text(text):
    """``text`` with every marked block regenerated."""
    for name in BLOCKS:
        a, b = block_markers(name)
        if a in text and b in text:
            head, rest = text.split(a, 1)
            tail = rest.split(b, 1)[1]
            text = head + a + "\n" + render_table(name) + "\n" + b + tail
    return text


def main(argv=None):
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--tables"]:
        for name in BLOCKS:
            print("%s\n" % render_table(name))
        return 0
    if len(argv) == 2 and argv[0] == "--sync":
        with open(argv[1], encoding="utf-8", newline="") as fh:
            text = fh.read()
        new = sync_text(text)
        if new != text:
            with open(argv[1], "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
        return 0
    sys.stderr.write("routes.py: --tables | --sync FILE\n")
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
