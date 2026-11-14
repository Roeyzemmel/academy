"""maintain.py: the survey's candidates and the union check of a maintenance round."""

import os
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import maintain as mt  # noqa: E402


def git(cwd, *args):
    p = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, text=True, timeout=60,
                       stdin=subprocess.DEVNULL)
    if p.returncode:
        raise RuntimeError("git %s: %s" % (" ".join(args), p.stderr))
    return p.stdout.strip()


def configure(repo):
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "commit.gpgsign", "false")


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
        def brief(ws_path, days):
            self.assertEqual(ws["_path"], ws_path)
            return {"families": [{"family": "tickets_update: not a transition", "state": "recurring",
                                  "in_window": 3, "bursts": 2, "sessions": 2, "example": "refused"},
                                 {"family": "Read: file too large", "state": "regression",
                                  "in_window": 1, "bursts": 1, "sessions": 1, "example": "x"}]}
        s = mt.survey(ws, repo=d, run=run, brief=brief)
        kinds = [c["kind"] for c in s["candidates"]]
        self.assertEqual("definition", kinds[0])
        self.assertEqual(["ledger:Read: file too large", "ledger:tickets_update: not a transition"],
                         [c["id"] for c in s["candidates"] if c["kind"] == "error"])   # regression first
        self.assertIn("x/agents/a.md", s["candidates"][0]["evidence"])
        self.assertEqual(len(mt.PROBES), kinds.count("slow"))
        self.assertEqual(len(mt.PROBES), len(seen))
        quick = mt.survey(ws, repo=d, probes=False, run=run, brief=lambda w, n: {"families": []})
        self.assertEqual(["definition"], [c["kind"] for c in quick["candidates"]])
        broken = mt.survey(ws, repo=d, probes=False, brief=lambda w, n: 1 / 0)
        self.assertIn("error ledger not read", " ".join(broken["notes"]))      # and it goes on
        self.assertIn("probes skipped (--no-probes)", quick["notes"])
        self.assertIn("definition", mt.render_survey(s))


class Workspace(unittest.TestCase):
    def test_the_map_is_found_and_read_without_the_other_plugins(self):
        d = tempfile.mkdtemp(prefix="maintain-ws-")
        self.addCleanup(shutil.rmtree, d, True)
        deep = os.path.join(d, "home", "sub")
        os.makedirs(deep)
        with open(os.path.join(d, "workspace.json"), "w", encoding="utf-8") as fh:
            json.dump({"board": {"path": "board", "backend": "github"},
                       "instances": {"expert@e": {"role": "expert", "home": deep}, "junk": 3}}, fh)
        ws = mt.load_workspace(environ={}, cwd=deep)                 # found going up
        self.assertEqual(os.path.join(d, "board"), ws["board"])
        self.assertEqual(["expert@e"], list(ws["instances"]))
        self.assertEqual(ws, mt.load_workspace(environ={"ACADEMY_WORKSPACE": ws["_path"]}, cwd="/"))
        with self.assertRaises(mt.MaintainError):
            mt.load_workspace(environ={}, cwd=tempfile.gettempdir())
        with open(mt.__file__, encoding="utf-8") as fh:
            self.assertNotIn("import _academy", fh.read())


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
        with self.assertRaises(mt.MaintainError):
            mt.union(self.repo, "no-such-branch", ["one"], gate=lambda t: (True, []))
        self.assertEqual(before, self.state())


if __name__ == "__main__":
    unittest.main()
