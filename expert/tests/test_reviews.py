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


OLD = "Let $M$ be a compact translation surface. Then every point is illuminated."
NEW = "Let $M$ be a translation surface. Then every point of $M$ is illuminated."


class RewordPassTests(unittest.TestCase):
    """T-0347: a reword pass on a statement reworded after a CONFIRMED x2 pass."""

    def setUp(self):
        import decision_table as dt
        self.dt = dt
        self.sb = fixtures.Sandbox()
        self.addCleanup(self.sb.close)
        self.old_hash = dt.statement_hash(OLD)
        self.base = "2026-09-28-T-0007"
        self.bdir = os.path.join(self.sb.lib, "reviews", "paper", "lem-strip-bound",
                                 self.base)
        os.makedirs(self.bdir)
        for run in ("A", "B"):
            self.write_run(run, "CONFIRMED")
        with open(os.path.join(self.bdir, "decision.md"), "w", encoding="utf-8") as fh:
            fh.write("# decision\noutcome: confirmed\n")

    def write_run(self, run, verdict, h=None):
        with open(os.path.join(self.bdir, run + ".md"), "w", encoding="utf-8") as fh:
            fh.write("---\nsubject: %s\npass: %s\nrun: %s\nrun_id: rv-%s\n"
                     "verdict: %s\nmodulo: []\nmodel: claude-opus-5-5\n"
                     "statement_hash: %s\n---\n\nRun %s report: the proof uses "
                     "compactness in step 2.\n"
                     % (SUBJ, self.base, run, run, verdict, h or self.old_hash, run))

    def run_cli(self, *args):
        return fixtures.run_script("reviews.py", args=list(args) + ["--home", self.sb.lib])

    def test_reword_pass_opens_on_a_confirmed_base(self):
        code, name, err = self.run_cli("new-pass", SUBJ, "--ticket", "T-0347",
                                       "--reword-of", self.base)
        self.assertEqual(code, 0, err)
        self.assertTrue(str(name).endswith("-T-0347-reword"), name)
        # one open pass per statement still holds
        code, out, err = self.run_cli("new-pass", SUBJ, "--ticket", "T-0400")
        self.assertEqual(code, 1)

    def test_reword_pass_refused_without_a_confirmed_base(self):
        code, out, err = self.run_cli("new-pass", SUBJ, "--reword-of", "2026-01-01-none")
        self.assertEqual(code, 1)
        self.assertIn("base pass", err)
        self.write_run("B", "GAP")
        code, out, err = self.run_cli("new-pass", SUBJ, "--reword-of", self.base)
        self.assertEqual(code, 1)
        self.assertIn("not CONFIRMED x2", err)
        self.write_run("B", "CONFIRMED")
        with open(os.path.join(self.bdir, "abandoned.md"), "w", encoding="utf-8") as fh:
            fh.write("dead\n")
        code, out, err = self.run_cli("new-pass", SUBJ, "--reword-of", self.base)
        self.assertEqual(code, 1)

    def test_the_brief_bundle(self):
        code, name, err = self.run_cli("new-pass", SUBJ, "--ticket", "T-0347",
                                       "--reword-of", self.base)
        old = self.sb.write("scratch/old.txt", OLD)
        new = self.sb.write("scratch/new.txt", NEW)
        finding = self.sb.write("scratch/finding.md", "Wording: compact is redundant.")
        out_path = self.sb.path("scratch/bundle.md")
        code, out, err = self.run_cli("reword-brief", SUBJ, name, "--old-file", old,
                                      "--new-file", new, "--findings", finding,
                                      "--findings", "T-0301 thread, 2026-10-11",
                                      "--ticket", "T-0347", "--out", out_path)
        self.assertEqual(code, 0, err)
        with open(out_path, encoding="utf-8") as fh:
            b = fh.read()
        for want in ("run: R", "mode: reword", "base_pass: %s" % self.base,
                     "base_hash: %s" % self.old_hash,
                     "statement_hash: %s" % self.dt.statement_hash(NEW),
                     "pass: %s" % name, "ticket: T-0347", OLD, NEW,
                     "[-compact-]", "{+of $M$+}", "decision.md", "A.md", "B.md",
                     "uses compactness in step 2", "compact is redundant",
                     "T-0301 thread"):
            self.assertIn(want, b)

    def test_the_brief_refuses_a_wrong_old_statement(self):
        code, name, err = self.run_cli("new-pass", SUBJ, "--reword-of", self.base)
        code, out, err = self.run_cli("reword-brief", SUBJ, name, "--old-text", "other",
                                      "--new-text", NEW)
        self.assertEqual(code, 1)
        self.assertIn("base_hash", err)
        code, out, err = self.run_cli("reword-brief", SUBJ, name, "--old-text", OLD,
                                      "--new-text", OLD + "  ")
        self.assertEqual(code, 1)
        self.assertIn("did not change", err)
        # a pass that is not a reword pass has no bundle
        code, out, err = self.run_cli("reword-brief", SUBJ, self.base, "--old-text", OLD,
                                      "--new-text", NEW)
        self.assertEqual(code, 1)

    def test_word_diff(self):
        import reviews
        self.assertEqual(reviews.word_diff("a b c", "a x c"), "a [-b-] {+x+} c")
        self.assertEqual(reviews.word_diff("a b", "a b"), "a b")



class RewordStatusTests(unittest.TestCase):
    """T-0347 review, finding 7: expert_status lists an undecided reword pass."""

    def test_an_undecided_reword_pass_is_listed(self):
        import expert_status
        sb = fixtures.Sandbox()
        self.addCleanup(sb.close)
        d = os.path.join(sb.lib, "reviews", "paper", "lem-x", "2026-10-12-T-0347-reword")
        os.makedirs(d)
        with open(os.path.join(d, "R.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nrun: R\nmode: reword\nverdict: CONFIRMED\n---\n")
        st = expert_status.review_state(sb.lib)
        self.assertEqual((st["passes"], st["undecided"]),
                         (1, ["paper/lem-x/2026-10-12-T-0347-reword"]))
        with open(os.path.join(d, "decision.md"), "w", encoding="utf-8") as fh:
            fh.write("decided\n")
        self.assertEqual(expert_status.review_state(sb.lib)["undecided"], [])


if __name__ == "__main__":
    unittest.main()
