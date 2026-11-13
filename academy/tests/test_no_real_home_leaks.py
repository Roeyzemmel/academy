"""Guard: a test file may not locate REAL workspace data except through the opt-in helper.

The suites are hermetic (README, "Tests"): outcomes depend on the repo, not on the machine.
A test that compares the code with a real home (real library, real registries) must take it
from ``_env.real_home`` (a ``tests/_env.py`` of its own tree), which returns '' unless
``ACADEMY_TEST_REAL=1`` is set and ``CI`` is not. This test fails when a test file in any
plugin mentions a real-home selector -- ``_real_home(``, ``ACADEMY_LIBRARY``,
``ACADEMY_HOME_``, ``ACADEMY_BOARD`` (the variable itself, not ``ACADEMY_BOARD_COMMIT``),
or ``open(os.environ["ACADEMY_..."])`` (reading a file a variable names) -- without importing
``_env``. Fix a failure by using the helper. A file that only uses those names as test DATA
(it asserts on the variable names, or sets them in a fixture's private environment) goes on
ALLOWED below, with the reason. ``ACADEMY_WORKSPACE`` itself is set by almost every fixture
and is only caught where it is read as a path (``open(os.environ["ACADEMY_WORKSPACE"])``).
Also checks that the per-plugin copies of ``_env.py`` are identical.
"""
import glob
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TREES = ["academy/tests", "academy/registry/tests", "author/tests", "expert/tests",
         "researcher/tests", "scientist/tests", "domains/*/tests"]
SELECTORS = re.compile(r"_real_home\(|ACADEMY_LIBRARY|ACADEMY_HOME_|ACADEMY_BOARD\b|"
                       r"open\(\s*os\.environ\[['\"]ACADEMY_")
USES_HELPER = re.compile(r"^\s*(import _env\b|from _env import)", re.M)

# file (relative to the repo) -> why it may mention the names
ALLOWED = {
    "academy/tests/test_common.py": "asserts on the variable names the library defines; sets them in a fixture",
    "academy/tests/test_bootstrap_board.py": "asserts on the variables the bootstrap writes",
    "academy/tests/test_ship_permissions.py": "builds a fixture environment with those variables",
    "academy/tests/test_no_real_home_leaks.py": "this file",
    "author/tests/test_pinned.py": "removes the variable so the fixture library is used",
    "expert/tests/test_decision_table.py": "reads the workspace.json its own fixture set",
}


def test_files():
    for tree in TREES:
        for path in sorted(glob.glob(os.path.join(REPO, tree, "*.py"))):
            yield os.path.relpath(path, REPO).replace(os.sep, "/"), path


class NoRealHomeLeaks(unittest.TestCase):
    def test_real_home_selectors_go_through_the_opt_in_helper(self):
        bad = []
        for rel, path in test_files():
            if rel in ALLOWED or os.path.basename(path) == "_env.py":
                continue
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            hits = sorted(set(SELECTORS.findall(text)))
            if hits and not USES_HELPER.search(text):
                bad.append("%s: %s" % (rel, ", ".join(hits)))
        self.assertEqual(bad, [], "a test locates real workspace data without tests/_env.py "
                                  "(ACADEMY_TEST_REAL=1, never on CI); see this file's docstring")

    def test_the_allow_list_has_no_stale_entries(self):
        present = {rel for rel, _ in test_files()}
        self.assertEqual(sorted(set(ALLOWED) - present), [])

    def test_the_copies_of_the_helper_are_identical(self):
        copies = {}
        for rel, path in test_files():
            if os.path.basename(path) == "_env.py":
                with open(path, "rb") as fh:
                    copies[rel] = fh.read()
        self.assertGreaterEqual(len(copies), 2, copies.keys())
        self.assertEqual(len(set(copies.values())), 1, "differing copies: %s" % sorted(copies))


if __name__ == "__main__":
    unittest.main()
