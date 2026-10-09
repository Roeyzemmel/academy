"""inbox.py -- which of the lab's tickets to take this run, and who takes each.

Usage::

    py inbox.py [--home DIR] [--board DIR] [--n N | --limit N] [--all] [--json]
                [--campaign TARGET | --cowork SLUG]
    py inbox.py --check T-NNNN          the serial checkpoint of a ticket just handled

A thin wrapper over the academy's ``inbox_core`` (``_academy.py``): the tickets addressed
to this Scientist instance, in-progress ones first (resume), then ``open`` and
``accepted`` ones in the protocol's order (priority, agenda position, id); never
dead-route or pending blocked ones. It keeps the first ``budget.itemsPerRun`` (at most 3);
``--all`` lists everything without the cut. Each row carries the route, decided here and
not by the model, from ``routes.py`` (the routing table lives there). The routed agent
runs on its agent file's model; a ticket's ``budget.max_model``, if present, is an
advisory note from the sender and never blocks a route; the ticket's limit is
``budget.runs`` (academy references/budget.md rules 6 and 7). Exit 0 with rows, 1 with
nothing to take, 2 on error.
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


def resolve(args):
    """``(instance, config)`` of the lab: ``--home``, else the lab containing the cwd, else
    workspace.json's Scientist; ``--instance`` overrides the name."""
    lab = c.resolve_lab(args.home, os.getcwd(), args.workspace)
    return args.instance or lab["instance"], lab["cfg"]


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    return core.main(argv, __doc__.split("\n")[0], resolve, route, return_legs=False)


if __name__ == "__main__":
    sys.exit(main())
