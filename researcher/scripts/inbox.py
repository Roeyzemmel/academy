"""inbox.py -- the Researcher instance's inbox: which tickets to take, and where each goes.

docs/protocol.md section 4 (execution) and references/budget.md: the receiver's
``open`` and ``accepted`` tickets, ordered by priority, then agenda position, then id;
at most ``budget.itemsPerRun`` (never more than 3), run serially. This script only
reads the board; the skill moves the tickets (``board.py transition``) and runs them.

Usage:

    py inbox.py [--instance researcher@x] [--n N] [--all] [--json] [--campaign TARGET]
    py inbox.py --check T-NNNN          the serial checkpoint of a ticket just handled

A thin wrapper over the academy's ``inbox_core`` (``_academy.py``): in-progress tickets
first (resume), then relay parents ready for their return leg (``"return": true``),
then ``open`` and ``accepted`` tickets; never dead-route or pending blocked ones.
``--all`` lists every open/accepted/in-progress/blocked ticket without taking any.
Without ``--instance`` the instance is the Researcher home containing the cwd.
The routing table (kind -> skill or agent) is ``routes.py``.

Agenda position: a ticket's ``agenda`` field names an Author agenda entry; tickets with
one come before tickets without, in id order (the Author's own ordering is not visible
from here).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
from routes import RELAYS, ROUTES, route  # noqa: E402,F401

core = ac.inbox_core


def resolve(args):
    """``(instance, config)``: ``--instance``/``--home``/``--workspace``, else the
    Researcher home containing the cwd."""
    return core.resolve_instance(args, "researcher")


def main(argv=None):
    return core.main(argv, __doc__.split("\n")[0], resolve, route)


if __name__ == "__main__":
    sys.exit(main())
