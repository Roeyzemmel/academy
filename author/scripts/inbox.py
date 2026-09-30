"""inbox.py -- the Author's inbox: the board is the only queue; tickets are routed.

    py inbox.py [--n N] [--all] [--json] [--campaign TARGET]
    py inbox.py --check T-NNNN                the serial checkpoint of a ticket just handled

Common options: ``--home DIR`` (default: the Author home holding the cwd), and for
tests ``--agenda FILE --board DIR --workspace FILE --instance NAME --ns NS`` in place
of the home's config.

A thin wrapper over the academy's ``inbox_core`` (``_academy.py``). There is no
roadmap: a work item is a ticket (kind write / apply / copy / figure / build /
notation / sweep to this Author itself, or an ask to another role), filed with
``board.py new`` / ``tickets_create`` or, from an agenda gap, ``agenda.py gaps --file``.
The Author's routing table is ``routes.py``. What is Author-specific lives here:

1. **Sweep first.** Every run starts with the machine-note sweep (``note-sweeper``, as
   ``/author:sweep`` does); the output says so first and it counts against no item cap.
2. **Selection.** The core's, in the Author's precedence: in-progress tickets first,
   then returned tickets to land (a ticket this Author filed to another role that came
   back ``delivered``; ``"return": true``), then ``open``/``accepted`` tickets ordered by
   the earliest agenda position they unblock (the ``agenda`` field: their own entry, or
   any entry resting on it, transitively), then priority, then id. At most
   ``budget.itemsPerRun`` (never more than 3). ``--all`` lists everything open, accepted,
   in progress or blocked, without the cut.
3. **Gaps.** The header says how many agenda entries below their required status have no
   ticket working on them (``agenda.py gaps``; ``agenda.py gaps --file`` files them).

Exit codes: 0 ok; 1 nothing to take; 2 error (one line on stderr); 3 for ``--check`` on
an unfinished ticket.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import agenda_lib as al  # noqa: E402
from routes import land_route, route  # noqa: E402

core = ac.inbox_core

TICKET_DEAD = ("rejected", "cancelled")
MAX_ITEMS = 3
INF = 10 ** 9


class InboxError(Exception):
    pass


# ----------------------------------------------------------------------------
# Context
# ----------------------------------------------------------------------------

def academy_scripts():
    return os.path.join(ac.repo_root(), "academy", "scripts")


def board_module():
    p = academy_scripts()
    if p not in sys.path:
        sys.path.insert(0, p)
    import board  # noqa: E402  (academy/scripts/board.py)
    return board


class Context(object):
    """Everything the plan needs, loaded once."""

    def __init__(self, agenda_path, board, workspace, instance, ns,
                 items_per_run=MAX_ITEMS, domains=None):
        self.agenda_path = agenda_path
        self.board = board
        self.workspace = workspace or {"instances": {}}
        self.instance = instance
        self.ns = ns or ""
        self.items_per_run = max(1, min(MAX_ITEMS, int(items_per_run or MAX_ITEMS)))
        self.domains = list(domains or [])
        self.agenda = (al.parse_agenda(al.read_text(agenda_path))
                       if agenda_path and os.path.isfile(agenda_path) else al.Agenda())
        self.tickets = {}
        if board and os.path.isdir(board):
            for path, meta, body in board_module().iter_tickets(board):
                if meta and meta.get("id"):
                    m = dict(meta)
                    m["_path"] = path
                    m["_body"] = body
                    self.tickets[m["id"]] = m


def load_context(args):
    """A Context from --home's academy.json, overridden by explicit options."""
    home = args.home
    if not home and args.instance:
        # /academy:inbox runs from anywhere: the instance names its home in workspace.json
        try:
            inst = ac.load_workspace(args.workspace)["instances"].get(args.instance) or {}
        except ac.AcademyError:
            inst = {}
        if inst.get("role") == "author":
            home = inst.get("home")
    home = home or ac.find_home(os.getcwd())
    cfg = None
    if home and os.path.isfile(os.path.join(home, ac.CONFIG_REL)):
        try:
            cfg = ac.load_config(home)
        except ac.AcademyError as exc:
            raise InboxError(str(exc))
        if cfg.get("role") != "author":
            raise InboxError("%s is a %s home, not an Author home" % (home, cfg.get("role")))
    if cfg is None and not args.agenda:
        raise InboxError("no Author home here (no .claude/academy.json with role author); "
                         "give --home, or --agenda")
    paths = (cfg or {}).get("paths", {})

    def rel(key, default):
        v = paths.get(key, default)
        v = v[0] if isinstance(v, list) else v
        return os.path.join(home, *str(v).split("/")) if home else v

    ws = None
    try:
        ws = ac.load_workspace(args.workspace)
    except ac.ConfigError:
        ws = None
    board = args.board or (ws or {}).get("board")
    instance = args.instance or (cfg or {}).get("instance")
    if not instance:
        raise InboxError("no instance name (give --instance)")
    ns = args.ns if args.ns is not None else (cfg or {}).get("ns", "")
    domains = (cfg or {}).get("domains") or ((ws or {}).get("instances", {})
                                             .get(instance, {}).get("domains")) or []
    items = args.items or ((cfg or {}).get("budget", {}).get("itemsPerRun")) or MAX_ITEMS
    return Context(args.agenda or rel("agenda", "Drafts/agenda.md"),
                   board, ws, instance, ns, items, domains)


# ----------------------------------------------------------------------------
# The plan
# ----------------------------------------------------------------------------

def _position(ctx, ref):
    """(position, note): the earliest agenda position a ticket's ``agenda`` unblocks."""
    if not ref or ref == "global":
        return INF, None
    e = ctx.agenda.lookup(ref, ctx.ns)
    if e is None:
        return INF, "agenda entry %s not found; sorted with global" % ref
    return ctx.agenda.unblock_position(e.label), None


def _num(tid):
    try:
        return int(str(tid).split("-")[1])
    except (IndexError, ValueError):
        return 0


def _released(ctx, t):
    """A ticket to this Author parked ``blocked`` on tickets only, every one of which is
    now ``delivered`` or terminal: nothing waits any more, it can be taken again."""
    if t.get("status") != "blocked" or core.is_dead_route(t):
        return False
    waits = [str(w) for w in (t.get("waiting_on") or [])]
    if not waits or not all(al.RE_TICKET_ID.match(w) for w in waits):
        return False
    return all((ctx.tickets.get(w) or {}).get("status") in ("delivered",) + ac.TERMINAL
               for w in waits)


def plan(ctx):
    """``{"land": [...], "release": [...], "notes": [...]}``.

    ``land``: the returned tickets to land, in order.
    ``release``: this Author's blocked tickets whose ``waiting_on`` tickets are all back
    (move ``blocked -> accepted``, then work them).

    A returned ticket is one this Author filed to another role (``from`` = this
    instance, ``to`` = someone else) that is now ``delivered``: its result waits to be
    landed in the tex, and the Author then closes it.
    """
    land, release, notes = [], [], []
    for tid in sorted(ctx.tickets, key=_num):
        t = ctx.tickets[tid]
        if t.get("to") == ctx.instance and _released(ctx, t):
            pos, note = _position(ctx, t.get("agenda"))
            if note:
                notes.append("%s: %s" % (tid, note))
            release.append({"ticket": tid, "kind": t.get("kind"), "title": t.get("title"),
                            "agenda": t.get("agenda"),
                            "priority": t.get("priority") or "normal",
                            "waiting_on": t.get("waiting_on"),
                            "position": None if pos == INF else pos,
                            "path": str(t.get("_path", "")).replace("\\", "/"),
                            "_key": (pos, al.PRIORITY_RANK.get(
                                t.get("priority") or "normal", 1), _num(tid))})
            continue
        if t.get("from") != ctx.instance or t.get("to") == ctx.instance:
            continue
        if t.get("status") != "delivered":
            continue
        pos, note = _position(ctx, t.get("agenda"))
        if note:
            notes.append("%s: %s" % (tid, note))
        prio = al.PRIORITY_RANK.get(t.get("priority") or "normal", 1)
        land.append({"ticket": tid, "kind": t.get("kind"), "title": t.get("title"),
                     "agenda": t.get("agenda"), "priority": t.get("priority") or "normal",
                     "result": t.get("result"), "final_to": t.get("final_to"),
                     "position": None if pos == INF else pos,
                     "path": str(t.get("_path", "")).replace("\\", "/"),
                     "_key": (pos, prio, _num(tid))})
    for lst in (land, release):
        lst.sort(key=lambda r: r["_key"])
        for r in lst:
            del r["_key"]
    return {"instance": ctx.instance, "land": land, "release": release, "notes": notes}


def land_rows(ctx, p):
    """The returned tickets to land, as inbox rows (``return: true``), in plan order."""
    rows = []
    for r in p["land"]:
        t = ctx.tickets.get(r["ticket"]) or {}
        rt = land_route(r["kind"], r.get("final_to"))
        rt["why"] += " (%s came back from %s: %s)" % (r["ticket"], t.get("to"),
                                                      r.get("result") or "no result")
        rows.append({"id": r["ticket"], "kind": r["kind"], "status": "delivered",
                     "priority": r["priority"], "from": ctx.instance, "title": r["title"],
                     "agenda": r["agenda"], "budget": t.get("budget"),
                     "refs": t.get("refs") or [], "campaign": t.get("campaign"),
                     "route": rt, "return": True, "over_budget": None, "blocked": None,
                     "path": r.get("path")})
    return rows


def release_rows(ctx, p):
    """The released blocked tickets, as inbox rows (status ``blocked``, ``released``)."""
    rows = []
    for r in p["release"]:
        t = ctx.tickets.get(r["ticket"]) or {}
        rt = dict(route(t))
        rt["why"] = ("released: %s all back; move it blocked -> accepted, then work it. "
                     % ", ".join(r["waiting_on"])) + rt["why"]
        rows.append({"id": r["ticket"], "kind": r["kind"], "status": "blocked",
                     "priority": r["priority"], "from": t.get("from"), "title": r["title"],
                     "agenda": r["agenda"], "budget": t.get("budget"),
                     "refs": t.get("refs") or [], "campaign": t.get("campaign"),
                     "route": rt, "return": False, "released": True, "over_budget": None,
                     "blocked": None, "path": r.get("path")})
    return rows


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def inbox_parser():
    ap = core.parser(__doc__.split("\n")[0], prog="inbox.py")
    for opt in ("--agenda", "--ns"):
        ap.add_argument(opt, default=None)
    return ap


def sweep_step():
    return {"how": "agent", "target": "note-sweeper",
            "why": "the machine-note sweep runs before any ticket is taken; it counts "
                   "against no item cap (/author:sweep is the standalone entry)"}


def run_inbox(args):
    """The selection: the core with the Author's extras (sweep first, landings, gaps)."""
    if args.check:
        board = args.board or ac.open_store(ac.load_workspace(args.workspace))
        return core.run(args, "", board, 3, route)
    args.items = args.n
    ctx = load_context(args)
    if not ctx.board:
        raise InboxError("no board (workspace.json 'board', or --board)")
    p = plan(ctx)
    # under --all the blocked pool already lists the released tickets
    lands = land_rows(ctx, p) + ([] if args.all else release_rows(ctx, p))
    header_text, header_json = [], {"land": len(p["land"]), "released": len(p["release"])}
    try:
        import agenda as ag  # noqa: E402  (agenda.py: the gaps)
        n_gaps = len(ag.gaps(ctx))
    except (al.AgendaError, ImportError):
        n_gaps = 0
    header_json["gaps"] = n_gaps
    if n_gaps:
        header_text.append("%d agenda gap(s) have no ticket: `agenda.py gaps --file` files "
                           "them" % n_gaps)
    if not args.all:
        header_json["sweep"] = sweep_step()
        header_text.insert(0, "SWEEP FIRST: note-sweeper, before any ticket below "
                              "(counts against no item cap)")
    after = []
    if p["notes"]:
        header_json["notes"] = p["notes"]
        after = ["", "NOTES"] + ["  " + n for n in p["notes"]] if args.all else []
    pos = lambda m: _position(ctx, m.get("agenda"))[0]  # noqa: E731
    return core.run(args, ctx.instance, ctx.board, ctx.items_per_run, route, position=pos,
                    return_legs=False, position_first=True, extra=lands,
                    header={"json": header_json, "text": header_text, "text_after": after})


def main(argv=None):
    _utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        return run_inbox(inbox_parser().parse_args(argv))
    except (InboxError, al.AgendaError, ac.AcademyError, OSError, ValueError) as exc:
        sys.stderr.write("inbox.py: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
