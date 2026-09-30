"""inbox.py -- the Expert's inbox: which tickets to take this run, and where each goes.

    py inbox.py [--instance expert@main] [--n N | --limit N] [--all] [--json]
                [--campaign TARGET]
    py inbox.py --check T-NNNN          the serial checkpoint of a ticket just handled

A thin wrapper over the academy's ``inbox_core`` (``_academy.py``): the tickets addressed
to the Expert instance, in-progress ones first (resume), then blocked relay parents ready
for their return leg (``final_to`` routes them to a relay, ``waiting_on`` holds only
ticket ids, and every child is ``delivered`` or terminal; the row carries
``"return": true``), then ``open`` and ``accepted`` tickets by priority, agenda position
and id; never dead-route or pending blocked ones. It takes at most ``--n`` (``--limit`` is
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


def plan(board, instance, limit):
    """The inbox as a dict (the shape of ``--json``)."""
    rows, total = core.select(board, instance, limit, route=route)
    return {"instance": instance, "limit": limit, "waiting": total, "take": rows,
            "remaining": max(0, total - len(rows)), "unfinished": core.unfinished(rows)}


def main(argv=None):
    ex.utf8_stdout()
    args = core.parser(__doc__.split("\n")[0]).parse_args(argv)
    ws = ex.load_workspace_or_none()
    if not ws:
        sys.stderr.write("inbox: workspace.json not found\n")
        return 2
    home = ac.find_home(os.getcwd())
    instance = args.instance
    if not instance and home:
        instance = ex.expert_instance_for_home(ws, home)
    if not instance:
        names = ex.expert_instances(ws)
        instance = names[0] if len(names) == 1 else None
    if not instance or instance not in ws["instances"]:
        sys.stderr.write("inbox: name the Expert instance (--instance)\n")
        return 2
    cfg = ex.expert_config(ws["instances"][instance]["home"])
    limit = ((cfg or {}).get("budget") or {}).get("itemsPerRun") or 3
    board = os.path.abspath(args.board or ws["board"])
    try:
        return core.run(args, instance, board, min(int(limit), 3), route)
    except (ac.AcademyError, OSError) as exc:
        sys.stderr.write("inbox: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
