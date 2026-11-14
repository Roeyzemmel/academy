"""Every agent and skill frontmatter value is one YAML scalar, read whole (2026-11-13).

Two agents were found mis-read by the harness, with no error anywhere:

* ``rigor-reviewer``: a single-quoted description with one apostrophe not doubled
  (``the human's``). The frontmatter did not parse, so the agent was listed as "Agent from
  expert plugin" with **all tools**: the blind, read-only reviewer had lost its tool list,
  its model and its turn limit.
* ``experimenter``: a plain description holding `` ## Conclusion``. `` #`` starts a
  comment, so the description ended there and lost its last two sentences.

The check itself is ``maintain.py``'s (``scalar_problem``, ``frontmatter_problems``), which
the survey of a maintenance round runs too. The suites are standard-library only, so this
is not a YAML parser: it checks the ways a one-line scalar goes wrong. A plain scalar holding ``: `` is refused too (strict YAML
reads a mapping there), although the harness has tolerated it.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

from maintain import frontmatter_files, frontmatter_problems, scalar_problem  # noqa: E402


class Scalars(unittest.TestCase):
    def test_the_checker_itself(self):
        ok = ["plain words, with commas", "'it''s quoted'", "'quoted'  # a comment",
              '"double \\" quoted"', "[a, b]", "", "a:b and c#d", "sonnet"]
        bad = ["'the human's word'", "'never closed", "its ## Conclusion", "to: someone else",
               '"two" "strings"', "ends with a colon:", "*starred"]
        self.assertEqual([], [v for v in ok if scalar_problem(v)])
        self.assertEqual([], [v for v in bad if not scalar_problem(v)])

    def test_every_agent_and_skill_frontmatter_is_read_whole(self):
        self.assertGreater(len(frontmatter_files(REPO)), 60)
        self.assertEqual([], frontmatter_problems(REPO))


if __name__ == "__main__":
    unittest.main()
