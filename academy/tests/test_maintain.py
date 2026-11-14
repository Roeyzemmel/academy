"""maintain.py: the survey's candidates and the union check of a maintenance round."""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import maintain as mt  # noqa: E402
from ship_fixture import configure, run as git  # noqa: E402


def result(seconds=0.1, chars=10, code=0):
    return {"seconds": seconds, "chars": chars, "exit": code}


class Probes(unittest.TestCase):
    def test_over_budget_and_failing_commands_are_candidates(self):
        c = mt.probe_candidates([("fast", result()), ("slow", result(seconds=27.8)),
                                 ("big", result(chars=189427)), ("found nothing", result(code=1)),
                                 ("broken", result(code=2)), ("hung", result(code=None))])
        self.assertEqual([("slow", "slow:slow"), ("large", "large:big"), ("error", "probe:broken"),
                          ("slow", "probe:hung")], [(x["kind"], x["id"]) for x in c])
        self.assertIn("27.8", c[0]["title"])
        self.assertIn("189427", c[1]["title"])

    def test_the_plan_runs_each_instances_inbox_from_its_home(self):
        d = tempfile.mkdtemp(prefix="maintain-")
        self.addCleanup(shutil.rmtree, d, True)
        home = os.path.join(d, "lib")
        os.makedirs(home)
        ws = {"_path": os.path.join(d, "workspace.json"),
              "instances": {"expert@e": {"role": "expert", "home": home},
                            "ghost@g": {"role": "nobody", "home": home},
                            "author@gone": {"role": "author", "home": os.path.join(d, "no")}}}
        plan = mt.probe_plan(ws)
        self.assertEqual(len(mt.PROBES) + 1, len(plan))
        name, argv, cwd = plan[-1]
        self.assertEqual(("inbox expert@e", home), (name, cwd))
        self.assertTrue(argv[1].replace(os.sep, "/").endswith("expert/scripts/inbox.py"))
        self.assertEqual(d, plan[0][2])
        for _n, argv, _c in plan:                       # every probe names a script that exists
            self.assertTrue(os.path.isfile(argv[1]), argv[1])

    def test_survey_collects_definitions_errors_and_probes(self):
        d = tempfile.mkdtemp(prefix="maintain-")
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "x", "agents"))
        with open(os.path.join(d, "x", "agents", "a.md"), "w", encoding="utf-8") as fh:
            fh.write("---\nname: a\ndescription: 'the human's word'\n---\nbody\n")
        board = os.path.join(d, "board")
        os.makedirs(board)
        ws = {"_path": os.path.join(d, "workspace.json"), "board": board, "instances": {}}
        seen = []

        def run(argv, cwd):
            seen.append(argv)
            return result(seconds=9.0)
        s = mt.survey(ws, repo=d, run=run)
        kinds = [c["kind"] for c in s["candidates"]]
        self.assertEqual("definition", kinds[0])
        self.assertIn("x/agents/a.md", s["candidates"][0]["evidence"])
        self.assertEqual(len(mt.PROBES), kinds.count("slow"))
        self.assertEqual(len(mt.PROBES), len(seen))
        quick = mt.survey(ws, repo=d, probes=False, run=run)
        self.assertEqual(["definition"], [c["kind"] for c in quick["candidates"]])
        self.assertIn("probes skipped (--no-probes)", quick["notes"])
        self.assertIn("definition", mt.render_survey(s))


class Union(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="maintain-union-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        git(self.repo, "init", "-q", "-b", "main")
        configure(self.repo)
        self.commit("main", {"a.txt": "a\n", "b.txt": "b\n"})
        self.commit("one", {"a.txt": "a one\n"}, base="main")
        self.commit("two", {"b.txt": "b two\n"}, base="main")
        self.commit("clash", {"a.txt": "a clash\n"}, base="main")
        git(self.repo, "switch", "-q", "main")

    def commit(self, branch, files, base=None):
        if base:
            git(self.repo, "switch", "-q", "-c", branch, base)
        for name, text in files.items():
            with open(os.path.join(self.repo, name), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", branch)

    def state(self):
        return (git(self.repo, "rev-parse", "HEAD"), git(self.repo, "status", "--porcelain"),
                git(self.repo, "branch", "--format=%(refname:short)"),
                git(self.repo, "worktree", "list"))

    def test_side_by_side_branches_are_gated_together_and_nothing_is_left(self):
        before, seen = self.state(), {}

        def gate(tree):
            for n in ("a.txt", "b.txt"):
                with open(os.path.join(tree, n), encoding="utf-8") as fh:
                    seen[n] = fh.read()
            return True, ["ci: suite ok", "ci: setup skipped: a setup step"]
        r = mt.union(self.repo, "main", ["one", "two"], gate=gate)
        self.assertEqual((True, ["one", "two"], None, True), (r["ok"], r["merged"], r["conflict"], r["gate_ok"]))
        self.assertEqual({"a.txt": "a one\n", "b.txt": "b two\n"}, seen)   # the gate saw both
        self.assertEqual(["ci: suite ok"], r["gate"])
        self.assertEqual(before, self.state())
        self.assertIn("union on main: ok", mt.render_union(r))

    def test_a_conflict_names_the_branch_and_a_failed_gate_is_not_ok(self):
        before = self.state()
        r = mt.union(self.repo, "main", ["one", "clash", "two"], gate=lambda t: (True, []))
        self.assertEqual((False, ["one"], "clash", None), (r["ok"], r["merged"], r["conflict"]["branch"], r["gate_ok"]))
        self.assertIn("CONFLICT merging clash", mt.render_union(r))
        r = mt.union(self.repo, "main", ["one"], gate=lambda t: (False, ["ci: suite failed (exit 1):"]))
        self.assertEqual((False, False), (r["ok"], r["gate_ok"]))
        self.assertEqual(before, self.state())
        with self.assertRaises(mt.ac.AcademyError):
            mt.union(self.repo, "no-such-branch", ["one"], gate=lambda t: (True, []))
        self.assertEqual(before, self.state())


if __name__ == "__main__":
    unittest.main()
