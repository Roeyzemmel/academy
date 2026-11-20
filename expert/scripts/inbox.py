"""inbox.py -- the Expert's inbox: which tickets to take this run, and where each goes.

    py inbox.py [--instance expert@main] [--n N | --limit N] [--all] [--json]
                [--campaign TARGET | --cowork SLUG]
    py inbox.py --check T-NNNN          the serial checkpoint of a ticket just handled

A thin wrapper over the academy's ``inbox_core`` (``_academy``): the tickets addressed
to the Expert instance, in-progress ones first (resume), then blocked relay parents ready
for their return leg (``final_to`` routes them to a relay, ``waiting_on`` holds only
ticket ids, and every child is ``delivered`` or terminal; the row carries
``"return": true``), then ``open`` and ``accepted`` tickets by priority, agenda position
and id; never dead-route or pending blocked ones. A blocked ticket that is no relay
parent (a verify ticket waiting on its falsifier request) is *released* once every ticket
it waits on is back (``delivered``/``closed``; the row carries ``"released": true`` and the
inbox workflow moves it ``blocked -> accepted``, then routes it); a wait that was
``rejected`` or ``cancelled`` releases it to the human instead (route ``human``, the row's
``dead_waits`` naming them), never silently into the next step. It takes at most ``--n`` (``--limit`` is
an alias; default: the home's ``budget.itemsPerRun``, never more than 3); ``--all`` lists
everything without the cut. Each ticket gets its route by kind from ``routes.py`` (the
routing table lives there).

The skill follows the route; this script decides nothing else and writes nothing.
Exit 0 with a plan, 1 when the inbox is empty, 2 on an error.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402
from routes import BELONGS, RELAYS, ROUTES, route  # noqa: E402,F401

core = ac.inbox_core


DEAD = ("rejected", "cancelled")


def release_rows(board, instance, campaign=None, cowork=None):
    """The released rows (review V1 #1): this instance's blocked tickets, no dead route and
    no relay return leg (``select`` lists those), whose ``waiting_on`` tickets are all back
    (``ac.released_waits``, the shared wait rule). One with a rejected or cancelled wait is
    released to the human: its waits will never deliver what it waited for."""
    store = ac.as_store(board)
    status_of = ac.status_lookup(store)
    rows = []
    for m in store.read_all(instance):
        if m.get("status") != "blocked" or ac.is_dead_route(m):
            continue
        if campaign and m.get("campaign") != campaign:
            continue
        if cowork and m.get("cowork") != cowork:
            continue
        if ac.relay_return_ready(m, status_of) or not ac.released_waits(m, status_of):
            continue
        waits = [str(w) for w in m.get("waiting_on") or []]
        dead = [w for w in waits if status_of(w) in DEAD]
        if dead:
            rt = {"how": "human", "target": "human",
                  "why": "released to the human: %s; it waited for what will now never come "
                         "back, so its next step (a verify ticket's run B included) is the "
                         "human's call: re-file the request, waive it on the ticket, or "
                         "reject the ticket" % "; ".join("%s was %s" % (w, status_of(w))
                                                         for w in dead)}
        else:
            rt = dict(route(m))
            rt["why"] = ("released: %s all back; move it blocked -> accepted, then work it. "
                         % ", ".join(waits)) + (rt.get("why") or "")
        rows.append(core.extra_row(m, rt, released=True, status="blocked",
                                   dead_waits=dead))
    rows.sort(key=lambda r: (core.PRIORITY.get(r.get("priority") or "normal", 1),
                             core.num(r.get("id"))))
    return rows


def plan(board, instance, limit):
    """The inbox as a dict (the shape of ``--json``)."""
    rows, total = core.select(board, instance, limit, route=route,
                              extra=release_rows(board, instance))
    return {"instance": instance, "limit": limit, "waiting": total, "take": rows,
            "remaining": max(0, total - len(rows)), "unfinished": core.unfinished(rows)}


def resolve(args):
    """``(instance, config)``: ``--instance``/``--home``/``--workspace``, else the Expert
    home containing the cwd, else the only Expert instance."""
    return core.resolve_instance(args, "expert")


def main(argv=None, out=None):
    """``core.main``, with the released rows (``release_rows``) as the selection's extra;
    under ``--all`` the blocked pool already lists them (as the Author's inbox does)."""
    ex.utf8_stdout()
    prog = "inbox.py"
    args = core.parser(__doc__.split("\n")[0], prog).parse_args(argv)
    try:
        inst, cfg = resolve(args)
        board = core.open_inbox_store(args)
        limit = ((cfg or {}).get("budget") or {}).get("itemsPerRun")
        extra = None
        if not args.check and not args.all:
            extra = release_rows(board, inst, getattr(args, "campaign", None),
                                 getattr(args, "cowork", None))
        return core.run(args, inst, board, limit, route, out=out, extra=extra)
    except (ac.AcademyError, OSError) as exc:
        sys.stderr.write("%s: %s\n" % (prog, exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
