"""ship.py: stacked branches (start --on, stack) and the push gate (ship.json), 2026-11-13.

No CI runs behind the repos, so what CI would run is run before a push; and a stack of
pull requests is built with the tool, each branch knowing its base.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ship  # noqa: E402
from ship_fixture import run  # noqa: E402
from test_ship import Base  # noqa: E402

PY_OK = ["{python}", "-c", "print('fine')"]
PY_FAIL = ["{python}", "-c", "import sys; print('boom: 2 tests failed'); sys.exit(3)"]


class TestStack(Base):
    def commit(self, name):
        self.write(name)
        rc, out, err = self.ship("commit", "sub", "-m", name, "--paths", name)
        self.assertEqual(0, rc, err)

    def test_a_second_start_stacks_on_the_first_and_stack_names_the_pull_requests(self):
        self.assertEqual(0, self.ship("start", "sub", "one", "--role", "human")[0])
        one = ship.current(self.sub)
        self.commit("a1.txt")
        rc, out, err = self.ship("start", "sub", "two", "--role", "human")
        self.assertEqual(0, rc, err)
        two = ship.current(self.sub)
        self.assertIn("stacked on %s" % one, out)
        self.commit("a2.txt")
        self.assertEqual(one, ship.base_of(self.sub, two))
        self.assertEqual("main", ship.base_of(self.sub, one))
        chain = ship.stack_of(self.sub)
        self.assertEqual([(two, one, 1, False), (one, "main", 1, False)],
                         [(r["branch"], r["base"], r["ahead"], r["pushed"]) for r in chain])
        rc, out, err = self.ship("stack", "sub")
        self.assertEqual(0, rc, err)
        lines = out.splitlines()
        self.assertIn("a stack of 2 branch(es), bottom first", lines[0])
        self.assertIn("1/2  %s" % one, lines[1])
        self.assertIn("pull request: head %s -> base main" % one, lines[2])
        self.assertIn("pull request: head %s -> base %s" % (two, one), lines[4])
        self.assertIn("NOT pushed", lines[3])
        # pushing says what the pull request's base is, and stack then says pushed
        rc, out, err = self.ship("push", "sub")
        self.assertEqual(0, rc, err)
        self.assertIn("its pull request's base is %s" % one, out)
        self.assertTrue(json.loads(self.ship("stack", "sub", "--json")[1])[0]["pushed"])

    def test_start_on_names_the_base_whatever_the_checkout_is_on(self):
        self.assertEqual(0, self.ship("start", "sub", "one", "--role", "human")[0])
        one = ship.current(self.sub)
        self.commit("a1.txt")
        run(self.sub, "switch", "-q", "main")
        rc, out, err = self.ship("start", "sub", "three", "--role", "human", "--on", one)
        self.assertEqual(0, rc, err)
        self.assertEqual(one, ship.base_of(self.sub, ship.current(self.sub)))
        self.assertTrue(os.path.isfile(os.path.join(self.sub, "a1.txt")))
        rc, out, err = self.ship("start", "sub", "four", "--role", "human", "--on", "nope")
        self.assertEqual(1, rc)
        self.assertIn("not a branch or commit", err)
        # --on an existing branch name is refused: it names the base of a NEW branch
        rc, out, err = self.ship("start", "sub", "three", "--role", "human", "--on", "main")
        self.assertEqual(1, rc)

    def test_a_session_branch_with_nothing_of_its_own_is_not_a_base(self):
        # a cloud session's own branch points at main: a start from it is not a stack
        run(self.sub, "switch", "-q", "-c", "session-abc")
        self.assertEqual(0, self.ship("start", "sub", "one", "--role", "human")[0])
        self.assertEqual("main", ship.base_of(self.sub, ship.current(self.sub)))

    def test_a_branch_started_on_main_has_no_recorded_base(self):
        self.on_branch()
        self.assertEqual("", ship.git(self.sub, "config", "--get",
                                      "branch.%s.ship-base" % ship.current(self.sub), check=False))
        rc, out, err = self.ship("stack", "sub")
        self.assertIn("a stack of 1 branch(es)", out)
        run(self.sub, "switch", "-q", "main")
        self.assertEqual(1, self.ship("stack", "sub")[0])


class TestPushGate(Base):
    def gate(self, *steps):
        with open(os.path.join(self.sub, "ship.json"), "w", encoding="utf-8") as f:
            json.dump({"pushGate": list(steps)}, f)

    def branch_with_commit(self, *steps):
        self.on_branch()
        self.gate(*steps)
        self.write("a2.txt")
        rc, out, err = self.ship("commit", "sub", "-m", "x", "--all")
        self.assertEqual(0, rc, err)

    def remote_has(self, branch):
        return bool(run(self.root, "ls-remote", self.remote, "refs/heads/" + branch))

    def test_a_failing_step_refuses_the_push_and_keeps_the_commit(self):
        self.branch_with_commit({"name": "lint", "run": PY_OK}, {"name": "tests", "run": PY_FAIL})
        b = ship.current(self.sub)
        tip = run(self.sub, "rev-parse", "HEAD")
        rc, out, err = self.ship("push", "sub")
        self.assertEqual(1, rc)
        self.assertIn("push gate: tests failed (exit 3)", err)
        self.assertIn("boom: 2 tests failed", err)
        self.assertIn("lint ok", err)
        self.assertFalse(self.remote_has(b))
        self.assertEqual(tip, run(self.sub, "rev-parse", "HEAD"))
        # --no-gate pushes, with a warning
        rc, out, err = self.ship("push", "sub", "--no-gate")
        self.assertEqual(0, rc, err)
        self.assertIn("--no-gate given, the push gate is skipped", err)
        self.assertTrue(self.remote_has(b))

    def test_a_passing_tree_is_pushed_and_not_gated_twice(self):
        self.branch_with_commit({"name": "tests", "run": PY_OK})
        rc, out, err = self.ship("push", "sub")
        self.assertEqual(0, rc, err)
        self.assertIn("push gate: tests ok", err)
        self.assertTrue(self.remote_has(ship.current(self.sub)))
        # the same tree again, now with a gate that would fail: remembered as passed
        ok, lines = ship.run_push_gate(self.sub)
        self.assertEqual((True, True), (ok, "passed before" in lines[0]))
        # a new commit is a new tree: the gate runs again
        self.gate({"name": "tests", "run": PY_FAIL})
        rc, out, err = self.ship("ship", "sub", "-m", "gate now fails", "--all")
        self.assertEqual(1, rc)
        self.assertIn("tests failed", err)

    def test_a_missing_tool_fails_unless_the_step_is_optional(self):
        self.branch_with_commit({"name": "lint", "run": ["no-such-linter-xyz", "."], "optional": True},
                                {"name": "tests", "run": PY_OK})
        rc, out, err = self.ship("push", "sub")
        self.assertEqual(0, rc, err)
        self.assertIn("lint skipped (no-such-linter-xyz is not installed)", err)
        self.gate({"name": "lint", "run": ["no-such-linter-xyz", "."]})
        self.ship("commit", "sub", "-m", "y", "--all")
        rc, out, err = self.ship("push", "sub")
        self.assertEqual(1, rc)
        self.assertIn("no-such-linter-xyz is not installed", err)

    def test_no_ship_json_no_gate_and_the_workspace_can_switch_it_off(self):
        self.on_branch()
        self.write("a2.txt")
        self.ship("commit", "sub", "-m", "x", "--all")
        self.assertEqual((True, []), ship.run_push_gate(self.sub))
        self.gate({"name": "tests", "run": PY_FAIL})
        self.assertFalse(ship.run_push_gate(self.sub)[0])
        with open(os.path.join(self.root, "workspace.json"), "w", encoding="utf-8") as f:
            json.dump({"pushGate": False}, f)
        self.assertEqual((True, []), ship.run_push_gate(self.sub))

    def test_the_step_environment_and_the_dirty_tree_note(self):
        self.branch_with_commit({"name": "env", "env": {"SHIP_GATE_X": "1"}, "run": [
            "{python}", "-c", "import os, sys; sys.exit(0 if os.environ.get('SHIP_GATE_X') == '1' else 5)"]})
        self.write("a.txt", "changed, uncommitted\n")
        ok, lines = ship.run_push_gate(self.sub)
        self.assertTrue(ok, lines)
        self.assertIn("uncommitted changes in tracked files", lines[0])
        # a dirty tree's pass is not remembered
        self.assertFalse(any("passed before" in ln for ln in ship.run_push_gate(self.sub)[1]))

    def test_checkpoint_does_not_push_past_a_failing_gate(self):
        self.gate({"name": "tests", "run": PY_FAIL})
        self.write("a2.txt")
        rc, out, err = self.ship("checkpoint", "--ticket", "T-0007")
        self.assertEqual(1, rc, out + err)
        self.assertIn("not pushed, the commit is kept", out + err)
        b = ship.current(self.sub)
        self.assertTrue(ship.BRANCH.match(b))
        self.assertFalse(self.remote_has(b))
        self.assertEqual("", run(self.sub, "status", "--porcelain"))


if __name__ == "__main__":
    unittest.main()
