"""A ``board.transport`` factory for subprocess tests: a MemoryTransport seeded from the file
board named by $ACADEMY_TEST_SEED ("_gh_seed:factory")."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import board_store as bs  # noqa: E402


def factory(cfg=None):
    return bs.from_file_board(os.environ["ACADEMY_TEST_SEED"])
