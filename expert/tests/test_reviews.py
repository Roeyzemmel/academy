"""reviews.py new-pass: one open pass per statement (workflow fix 8, 2026-10-09)."""

import os
import unittest

import fixtures

SUBJ = "paper:lem:strip-bound"


class NewPassTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        self.addCleanup(self.sb.close)

    def run_cli(self, *args):
        return fixtures.run_script("reviews.py", args=list(args) + ["--home", self.sb.lib])

    def test_second_concurrent_pass_refused(self):
        code, name, err = self.run_cli("new-pass", SUBJ, "--ticket", "T-0007")
        self.assertEqual(code, 0, err)
        self.assertTrue(str(name).endswith("-T-0007"))
        # the same step again: the same pass, not a refusal
        code, again, err = self.run_cli("new-pass", SUBJ, "--ticket", "T-0007")
        self.assertEqual((code, again), (0, name), err)
        code, out, err = self.run_cli("new-pass", SUBJ, "--ticket", "T-0009")
        self.assertEqual(code, 1)
        self.assertIn("already has an open pass", err)
        # another statement is not affected
        code, out, err = self.run_cli("new-pass", "paper:lem:other", "--ticket", "T-0009")
        self.assertEqual(code, 0, err)

    def test_a_concluded_or_abandoned_pass_is_closed(self):
        code, name, err = self.run_cli("new-pass", SUBJ, "--ticket", "T-0007")
        code, d, err = self.run_cli("dir", SUBJ, name)
        os.makedirs(d)
        with open(os.path.join(d, "decision.md"), "w") as fh:
            fh.write("decided\n")
        code, out, err = self.run_cli("new-pass", SUBJ, "--ticket", "T-0009")
        self.assertEqual(code, 0, err)
        code, out2, err = self.run_cli("new-pass", SUBJ, "--ticket", "T-0011")
        self.assertEqual(code, 1)
        code, path, err = self.run_cli("abandon", SUBJ, out, "--reason", "relaunched")
        self.assertEqual(code, 0, err)
        self.assertTrue(str(path).endswith("abandoned.md"))
        code, out3, err = self.run_cli("new-pass", SUBJ, "--ticket", "T-0011")
        self.assertEqual(code, 0, err)

    def test_landed_runs_without_decision_count_as_open(self):
        d = os.path.join(self.sb.lib, "reviews", "paper", "lem-strip-bound", "2026-09-28-x")
        os.makedirs(d)
        with open(os.path.join(d, "A.md"), "w") as fh:
            fh.write("---\nrun: A\n---\n")
        code, out, err = self.run_cli("new-pass", SUBJ)
        self.assertEqual(code, 1)
        self.assertIn("2026-09-28-x", err)


if __name__ == "__main__":
    unittest.main()
