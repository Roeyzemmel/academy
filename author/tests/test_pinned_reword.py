"""pinned.py with a reword pass (T-0347), tested by test-engineer.

pinned.py's own rule: the latest hashed pass decides the pin; all runs CONFIRMED pins it
(``verified`` for the two agreeing reviews), a later pass that is not all CONFIRMED
unpins. A reword pass holds one run, ``R.md``. Read with the T-0347 rule (R CONFIRMED on a
CONFIRMED x2 base is the two agreeing reviews of the new wording), a reword pass should
move the pin to the new hash at ``verified``, and a reword GAP should unpin.

Today ``RE_RUN_FILE`` matches only ``A``/``B`` files, so a reword pass is invisible: the
pin stays on the base pass and the old hash. The two ``expectedFailure`` tests below
state the expected behaviour (a review finding on T-0347); the plain test records what
does hold today.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_pinned import PinnedBase, TEX  # noqa: E402
import pinned as pn  # noqa: E402

NEW_TEX = TEX.replace("Then every flat morphism lifts.",
                      "Then every flat morphism of $X$ lifts.")
RW_PASS = "2026-10-12-T-0347-reword"


class PinsWithARewordPass(PinnedBase):
    def setUp(self):
        super().setUp()
        self.land("A", "CONFIRMED")
        self.land("B", "CONFIRMED")
        self.sb.write(self.tex, NEW_TEX)
        self.h_new = pn.statement_hash(pn.env_text(NEW_TEX, "lem:lift"))
        self.assertNotEqual(self.h_new, self.h)

    def land_r(self, verdict):
        rec = ("---\nsubject: paper:lem:lift\npass: %s\nrun: R\nrun_id: rv-r\n"
               "verdict: %s\nmodulo: []\nmodel: claude-opus-5-5\nstatement_hash: %s\n"
               "mode: reword\nbase_pass: 2026-10-08-T-0001\nbase_hash: %s\n"
               "reword_scope: equivalent\nblocking:\nticket: T-0347\n---\n\nreport\n"
               % (RW_PASS, verdict, self.h_new, self.h))
        self.sb.write(os.path.join(self.lib, "reviews", "paper", "lem-lift", RW_PASS,
                                   "R.md"), rec)

    def test_the_base_pin_survives_without_error(self):
        self.land_r("CONFIRMED")
        self.assertIn("lem:lift", self.pins())

    @unittest.expectedFailure
    def test_finding_a_confirmed_reword_moves_the_pin_to_the_new_wording(self):
        self.land_r("CONFIRMED")
        p = self.pins()["lem:lift"]
        self.assertEqual((p["pass"], p["hash"], p["level"]),
                         (RW_PASS, self.h_new, "verified"))

    @unittest.expectedFailure
    def test_finding_a_reword_gap_unpins(self):
        self.land_r("GAP")
        self.assertNotIn("lem:lift", self.pins())


if __name__ == "__main__":
    unittest.main()
