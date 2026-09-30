"""inbox.py -- which of the lab's tickets to take this run, and who takes each.

Usage::

    py inbox.py [--home DIR] [--board DIR] [--n N | --limit N] [--all] [--json]
                [--campaign TARGET]
    py inbox.py --check T-NNNN          the serial checkpoint of a ticket just handled

A thin wrapper over the academy's ``inbox_core`` (``_academy.py``): the tickets addressed
to this Scientist instance, in-progress ones first (resume), then ``open`` and
``accepted`` ones in the protocol's order (priority, agenda position, id); never
dead-route or pending blocked ones. It keeps the first ``budget.itemsPerRun`` (at most 3);
``--all`` lists everything without the cut. Each row carries the route, decided here and
not by the model, from ``routes.py`` (the routing table lives there), and ``over_budget``
when the routed agent is heavier than the ticket's ``max_model``. Exit 0 with rows, 1
with nothing to take, 2 on error.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _common as c  # noqa: E402
from _common import ac  # noqa: E402
from routes import route  # noqa: E402

core = ac.inbox_core


def select(board, instance, limit=3, take_all=False):
    """``(rows, total)`` as ``inbox_core.select`` gives them (no return legs here)."""
    return core.select(board, instance, limit, all=take_all, route=route,
                       return_legs=False)


def main(argv=None):
    args = core.parser(__doc__.split("\n")[0], prog="inbox.py").parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        lab = c.resolve_lab(args.home, os.getcwd(), args.workspace)
        board = args.board or ac.open_store(ac.load_workspace(args.workspace))
        limit = (lab["cfg"].get("budget") or {}).get("itemsPerRun", 3)
        return core.run(args, args.instance or lab["instance"], board, min(int(limit), 3), route,
                        return_legs=False)
    except ac.AcademyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
