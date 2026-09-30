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
import _researcher as rs  # noqa: E402
from routes import RELAYS, ROUTES, route  # noqa: E402,F401

core = ac.inbox_core


def resolve_instance(instance=None, cwd=None):
    if instance:
        return instance, None
    home, cfg, inst = rs.researcher_home(cwd or os.getcwd())
    if not inst:
        raise ac.AcademyError("not in a Researcher home; give --instance")
    return inst, cfg


def main(argv=None):
    args = core.parser(__doc__.split("\n")[0]).parse_args(argv)
    try:
        inst, cfg = resolve_instance(args.instance)
        board = args.board or ac.load_workspace()["board"]
        limit = min(int(((cfg or {}).get("budget") or {}).get("itemsPerRun", 3)), 3)
        return core.run(args, inst, board, limit, route)
    except (ac.AcademyError, OSError) as exc:
        sys.stderr.write("inbox.py: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
