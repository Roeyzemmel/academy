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
import gaps as gp  # noqa: E402
from routes import land_route, route  # noqa: E402

core = ac.inbox_core

INF = 10 ** 9


class InboxError(Exception):
    pass


# ----------------------------------------------------------------------------
# Context
# ----------------------------------------------------------------------------

class Context(object):
    """Everything the plan needs, loaded once.

    ``board`` is a BoardStore (a path becomes the file store): the same code reads a file
    board and a github one. ``tickets`` maps every ticket id of the board to its meta
    (``_path`` = the store's ref); a body is read on demand (``body(tid)``).
    """

    def __init__(self, agenda_path, board, workspace, instance, ns,
                 items_per_run=core.MAX, domains=None, require_agenda=True):
        self.agenda_path = agenda_path
        self.board = ac.as_store(board) if board else None
        self.workspace = workspace or {"instances": {}}
        self.instance = instance
        self.ns = ns or ""
        self.items_per_run = core.clamp(items_per_run)
        self.domains = list(domains or [])
        if agenda_path and os.path.isfile(agenda_path):
            self.agenda = al.parse_agenda(al.read_text(agenda_path))
        elif require_agenda:
            raise al.AgendaError(
                "the agenda file %s does not exist (paths.agenda); create it or give "
                "--agenda" % (agenda_path or "(none configured)"))
        else:
            self.agenda = al.Agenda()
        self.agenda_missing = not (agenda_path and os.path.isfile(agenda_path))
        self.tickets = {}
        if self.board is not None:
            for ref, meta in self.board.iter_meta():
                if meta and meta.get("id"):
                    m = dict(meta)
                    m["_path"] = ref
                    self.tickets[m["id"]] = m

    def body(self, tid):
        """The body of ticket ``tid`` (its thread included)."""
        return self.board.get(tid)[2]

    def status_of(self, tid):
        return (self.tickets.get(tid) or {}).get("status")


def load_context(args, require_agenda=True):
    """A Context from --home's academy.json, overridden by explicit options."""
    inst, cfg = core.resolve_instance(args, "author") if (
        args.home or args.instance or not args.agenda) else (args.instance, None)
    home = args.home
    ws = None
    try:
        ws = ac.load_workspace(args.workspace)
    except ac.ConfigError:
        ws = None
    if not home and args.instance and ws:
        h = (ws["instances"].get(args.instance) or {})
        home = h.get("home") if h.get("role") == "author" else None
    home = home or ac.find_home(os.getcwd())
    if cfg is None and not args.agenda:
        raise InboxError("no Author home here (no .claude/academy.json with role author); "
                         "give --home, or --agenda")
    paths = (cfg or {}).get("paths", {})

    def rel(key, default):
        v = paths.get(key, default)
        v = v[0] if isinstance(v, list) else v
        return os.path.join(home, *str(v).split("/")) if home else v

    if args.board:
        board = ac.FileBoardStore(os.path.abspath(args.board))
    elif ws:
        board = core.open_inbox_store(args)
    else:
        board = None
    instance = inst or (cfg or {}).get("instance")
    if not instance:
        raise InboxError("no instance name (give --instance)")
    ns = args.ns if args.ns is not None else (cfg or {}).get("ns", "")
    domains = (cfg or {}).get("domains") or ((ws or {}).get("instances", {})
                                             .get(instance, {}).get("domains")) or []
    items = args.items or ((cfg or {}).get("budget", {}).get("itemsPerRun")) or core.MAX
    return Context(args.agenda or rel("agenda", "Drafts/agenda.md"),
                   board, ws, instance, ns, items, domains, require_agenda)


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


def wait_notes(ctx, t):
    """NOTES lines about the tickets a blocked ticket ``t`` waits on: one that is not on
    the board, one that was rejected or cancelled (it will never be delivered: the wait
    cannot end by itself)."""
    out = []
    for w in (str(x) for x in (t.get("waiting_on") or [])):
        if not al.RE_TICKET_ID.match(w):
            continue
        st = ctx.status_of(w)
        if st is None:
            out.append("%s waits on %s, which is not on the board" % (t["id"], w))
        elif st in gp.DEAD:
            out.append("%s waits on %s, which was %s and will never be delivered: decide "
                       "whether to re-file it, or reject or repoint %s"
                       % (t["id"], w, st, t["id"]))
    return out


def released(ctx, t):
    """A blocked ticket of this Author whose ``waiting_on`` tickets are all back
    (``ac.released_waits``, the shared wait rule). A wait on a rejected or cancelled
    ticket is not back: the ticket stays blocked, with a NOTE (``wait_notes``)."""
    def status(w):
        st = ctx.status_of(w)
        return None if st in gp.DEAD else st
    return ac.released_waits(t, status)


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
    for tid in sorted(ctx.tickets, key=core.num):
        t = ctx.tickets[tid]
        if t.get("to") == ctx.instance and t.get("status") == "blocked" \
                and not core.is_dead_route(t):
            notes += wait_notes(ctx, t)
        if t.get("to") == ctx.instance and released(ctx, t):
            pos, note = _position(ctx, t.get("agenda"))
            if note:
                notes.append("%s: %s" % (tid, note))
            release.append({"ticket": tid, "kind": t.get("kind"), "title": t.get("title"),
                            "agenda": t.get("agenda"),
                            "priority": t.get("priority") or "normal",
                            "waiting_on": t.get("waiting_on"),
                            "position": None if pos == INF else pos,
                            "path": str(t.get("_path", "")).replace("\\", "/"),
                            "_key": (pos, core.prio(t), core.num(tid))})
            continue
        if t.get("from") != ctx.instance or t.get("to") == ctx.instance:
            continue
        if t.get("status") != "delivered":
            continue
        pos, note = _position(ctx, t.get("agenda"))
        if note:
            notes.append("%s: %s" % (tid, note))
        land.append({"ticket": tid, "kind": t.get("kind"), "title": t.get("title"),
                     "agenda": t.get("agenda"), "priority": t.get("priority") or "normal",
                     "result": t.get("result"), "final_to": t.get("final_to"),
                     "position": None if pos == INF else pos,
                     "path": str(t.get("_path", "")).replace("\\", "/"),
                     "_key": (pos, core.prio(t), core.num(tid))})
    for lst in (land, release):
        lst.sort(key=lambda r: r["_key"])
        for r in lst:
            del r["_key"]
    return {"instance": ctx.instance, "land": land, "release": release, "notes": notes}


def land_rows(ctx, p, campaign=None):
    """The returned tickets to land, as inbox rows (``return: true``), in plan order; with
    ``campaign`` only those carrying it."""
    rows = []
    for r in p["land"]:
        t = ctx.tickets.get(r["ticket"]) or {}
        if campaign and t.get("campaign") != campaign:
            continue
        rt = land_route(r["kind"])
        rt["why"] += " (%s came back from %s: %s)" % (r["ticket"], t.get("to"),
                                                      r.get("result") or "no result")
        rows.append(core.extra_row(t, rt, returned=True, status="delivered",
                                   **{"from": ctx.instance}))
    return rows


def release_rows(ctx, p, campaign=None):
    """The released blocked tickets, as inbox rows (status ``blocked``, ``released``); with
    ``campaign`` only those carrying it."""
    rows = []
    for r in p["release"]:
        t = ctx.tickets.get(r["ticket"]) or {}
        if campaign and t.get("campaign") != campaign:
            continue
        rt = dict(route(t))
        rt["why"] = ("released: %s all back; move it blocked -> accepted, then work it. "
                     % ", ".join(r["waiting_on"])) + rt["why"]
        rows.append(core.extra_row(t, rt, released=True, status="blocked"))
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
        store = core.open_inbox_store(args)
        return core.run(args, "", store, 3, route, role="author")
    args.items = args.n
    ctx = load_context(args, require_agenda=False)     # the tickets need no agenda
    if not ctx.board:
        raise InboxError("no board (workspace.json 'board', or --board)")
    p = plan(ctx)
    lands = land_rows(ctx, p, args.campaign)
    # under --all the blocked pool already lists the released tickets
    released_rows = [] if args.all else release_rows(ctx, p, args.campaign)
    header_text, header_json = [], {"land": len(lands), "released": len(released_rows)}
    if args.all:
        header_json["released"] = len(release_rows(ctx, p, args.campaign))
    gap_rows = [] if ctx.agenda_missing else gp.gaps(ctx)
    header_json["gaps"] = None if ctx.agenda_missing else len(gap_rows)
    if ctx.agenda_missing:
        header_json["agenda_missing"] = ctx.agenda_path
        header_text.append("NOTE: the agenda file %s does not exist: agenda gaps and ticket "
                           "positions are unknown (tickets are listed by priority)"
                           % ctx.agenda_path)
    fileable = [g for g in gap_rows if g["proposed_tag"] != gp.HOLD]
    if fileable:
        header_text.append("%d agenda gap(s) have no ticket: `agenda.py gaps --file` files "
                           "them" % len(fileable))
    if len(gap_rows) > len(fileable):
        header_text.append("%d agenda gap(s) wait for Roey (refuted or no registry record): "
                           "`agenda.py gaps` says which" % (len(gap_rows) - len(fileable)))
    if not args.all:
        header_json["sweep"] = sweep_step()
        header_text.insert(0, "SWEEP FIRST: note-sweeper, before any ticket below "
                              "(counts against no item cap)")
    after = []
    if p["notes"]:
        header_json["notes"] = p["notes"]
        after = ["", "NOTES"] + ["  " + n for n in p["notes"]]
    pos = lambda m: _position(ctx, m.get("agenda"))[0]  # noqa: E731
    return core.run(args, ctx.instance, ctx.board, ctx.items_per_run, route, position=pos,
                    return_legs=False, position_first=True, extra=lands + released_rows,
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
