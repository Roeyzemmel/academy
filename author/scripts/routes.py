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
writer files the argument as a ``research`` ticket and lands what returns. Not when the
argument exists: an ``apply`` ticket's edit is decided (math-editor), and a ticket whose
refs or waiting_on name a delivered ``research`` or ``prove`` ticket (``delivered_argument``) or whose
first ref is proved in another namespace's registry (``proved_source``) is landed by the agent of its kind
(#92: T-1441, T-1385).
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
    r"(?i)(?<!\bno )(?<!\bnot a )\b(missing|new|own|fresh)\s+(argument|proof|lemma|step)s?\b"
    r"|\bfill (in )?the gap\b|\brepair (the|its) (proof|argument)\b"
    r"|\bconstruct (a|the) proof\b|\b(find|give|write) a (new )?proof\b"
    r"|\bprove (that|it|the)\b|\bcleaner formulation\b|\bunifying lemma\b"
    r"|\b(add|drop|weaken|strengthen) (a |the )?hypothes")
#: the self kinds whose ask is checked for a missing argument (``check_filed``)
WRITER_KINDS = ("write", "apply", "copy", "note")
#: the self kinds ``route`` sends to research when the ask needs an argument: not
#: ``apply``, whose edit is already decided (KIND_ROUTES; #92, T-1441 went to research
#: four times on "add ... the hypothesis", the human's own decided edit)
ROUTED_WRITER_KINDS = tuple(k for k in WRITER_KINDS if k != "apply")
#: ticket kinds whose delivery is an argument, and the statuses that say it was delivered
ARGUMENT_TICKET_KINDS = ("research", "prove")
DELIVERED_STATUSES = ("delivered", "closed")
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


#: registry statuses that say the argument exists (a write ticket then only lands it)
LANDABLE_STATUSES = ("proved", "proved-modulo")


def proved_source(meta, status_of=None):
    """The ticket's subject, its first ref, when it names a claim of another namespace (a
    notebook, the lab) whose registry status is proved or proved-modulo: the argument
    exists, so the ticket lands it, whatever its wording (#92, T-0426 sent to research
    three times for flat:FND-14). Only the first ref: a later proved ref is often a lemma
    the asked argument would use (review of d4ffad3). The paper's own namespace is
    skipped: a repair asked of a paper claim proved on the human's word, or with a GAP
    review, needs a new argument although the registry says proved (T-1387, T-1626);
    a delivered repair is found by ``delivered_argument`` instead (T-1385).
    ``status_of`` (qid -> status or None) replaces the registry lookup; '' when it does
    not qualify or the registry cannot be read."""
    own = ""
    if status_of is None:
        status_of, own = _registry_status, _own_ns(meta.get("to"))
    for ref in list(meta.get("refs") or ())[:1]:
        ns, _, name = str(ref).partition(":")
        if not name or not re.match(r"^[a-z][a-z0-9]*$", ns) or ns in ("file", "bib", own):
            continue
        try:
            st = status_of(str(ref))
        except Exception:    # a routing table answers even when the registry cannot
            st = None
        if str(st or "").strip().lower() in LANDABLE_STATUSES:
            return str(ref)
    return ""


def delivered_argument(meta, ticket_of=None):
    """The first of the ticket's refs that names a ``research`` or ``prove`` ticket now
    delivered or closed: the argument was delivered, so the ticket lands it, whatever its
    wording (#92, T-1385 sent to research again after T-1618 delivered the repair). A
    ``research`` ticket relayed to the Scientist is an experiment, not an argument, and
    does not count (``check_filed``'s rule). ``ticket_of`` (ticket id -> meta or None,
    ``ticket_lookup``; the inbox passes its own board's) replaces the workspace board's;
    '' when none qualifies or the board cannot be read."""
    tids = []
    for r in _as_list(meta.get("refs")) + _as_list(meta.get("waiting_on")):
        r = str(r).strip()
        if re.match(r"^T-\d+$", r) and r not in tids:
            tids.append(r)
    if tids and ticket_of is None:
        ticket_of = _workspace_tickets()
    for tid in tids:
        try:
            t = ticket_of(tid) or {}
        except Exception:    # a routing table answers even when the board cannot
            continue
        if (t.get("kind") in ARGUMENT_TICKET_KINDS
                and t.get("status") in DELIVERED_STATUSES
                and str(t.get("final_to") or "").split("@")[0] != "scientist"):
            return tid
    return ""


def _as_list(v):
    """A field that should be a list, as one: a scalar is one item, None none."""
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def _ticket_num(tid):
    m = re.search(r"\d+", str(tid or ""))
    return int(m.group()) if m else None


def ticket_lookup(store):
    """``ticket_of`` for ``delivered_argument`` on a board store: ticket id -> meta (None
    when it is not on the board), by number as the store finds an issue, from one listing
    made on the first question (``status_lookup``'s reason: a request per ticket on a
    github board)."""
    held = {}

    def ticket_of(tid):
        if "by_num" not in held:
            held["by_num"] = {_ticket_num(m.get("id")): m
                              for _ref, m in store.iter_meta() if m}
        return held["by_num"].get(_ticket_num(tid))
    return ticket_of


def _own_ns(instance):
    try:
        import _academy as ac
        return str(((ac.load_workspace() or {}).get("instances") or {})
                   .get(str(instance or ""), {}).get("ns") or "")
    except Exception:
        return ""


def _workspace_tickets():
    """``ticket_lookup`` on the workspace's board; one that knows no ticket when the board
    cannot be opened (a routing table answers even then)."""
    try:
        import _academy as ac
        return ticket_lookup(ac.open_store(ac.load_workspace()))
    except Exception:
        return lambda _tid: None


def _registry_status(qid):
    import os
    import sys
    import _academy as ac
    plugin = os.path.join(ac.repo_root(), "academy")
    if plugin not in sys.path:
        sys.path.insert(0, plugin)
    from registry.core import federation, workspace as rws
    ns, _, name = qid.partition(":")
    info = rws.namespaces().get(ns)
    home = info and info.get("home")
    if not home or not os.path.isdir(str(home)):
        return None
    rec = federation.store(ns, home).get(name)
    return rec.status if rec is not None else None


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


def route(meta, ticket_of=None):
    """``{how, target, why}`` for a ticket to the Author. ``ticket_of`` (``ticket_lookup``)
    reads the tickets the refs name; default: the workspace's board."""
    meta = dict(meta, refs=[str(r) for r in _as_list(meta.get("refs"))
                            if isinstance(r, (str, int))])
    kind = meta.get("kind") or "other"
    if kind in BELONGS:
        role = BELONGS[kind]
        return {"how": "reject", "target": None,
                "why": "a %s ticket is %s work, not the Author's (the Author only lands); "
                       "reject it, and ask through a `research` ticket to the Expert with "
                       "final_to %s" % (kind, role, role)}
    if kind in ROUTED_WRITER_KINDS and needs_argument(meta):
        tid = delivered_argument(meta, ticket_of)
        src = "" if tid else proved_source(meta)
        if tid or src:
            how, target, _why = KIND_ROUTES[kind]
            said = ("%s delivered it" % tid if tid
                    else "%s is proved in the registry" % src)
            return {"how": how, "target": target,
                    "why": "land the argument: %s, so it exists (the ask's wording is "
                           "not a missing argument)" % said}
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
    if len(argv) == 2 and argv[0] == "--check-filed":
        # the notes workflow (2026-10-31): a JSON list of proposed ticket metas in, one list
        # of check_filed problems per ticket out, in order (empty: the ticket passes)
        import json
        with open(argv[1], encoding="utf-8") as fh:
            metas = json.load(fh)
        print(json.dumps([check_filed(m) for m in metas]))
        return 0
    sys.stderr.write("routes.py: --tables | --sync FILE | --check-filed FILE\n")
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(main())
