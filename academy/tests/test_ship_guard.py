"""ship_guard: in a workspace's repos a commit, a push or a new branch by raw git is
denied with the ship.py command that does it (2026-11-13); everything else passes."""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import ship_guard as sg  # noqa: E402
from ship_fixture import configure, make_workspace, run  # noqa: E402


class ShipGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root, cls.sub, _remote = make_workspace(cls._tmp.name)
        cls.scratch = os.path.join(cls._tmp.name, "scratch")
        os.makedirs(cls.scratch)
        run(cls.scratch, "init", "-q", "-b", "main")
        configure(cls.scratch)
        cls.wt = os.path.join(cls._tmp.name, "wt")
        run(cls.sub, "worktree", "add", "-q", "-b", "side", cls.wt)
        cls.ws = {"_path": os.path.join(cls.root, "workspace.json"), "instances": {}}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def decide(self, command, cwd=None, ws=None, tool="Bash"):
        return sg.decide({"tool_name": tool, "cwd": cwd or self.root,
                          "tool_input": {"command": command}}, workspace=ws or self.ws)

    def test_commit_push_and_new_branch_in_a_submodule_are_denied_with_the_ship_command(self):
        for cmd, want in (
                ("git commit -m x", "ship.py commit sub"),
                ("git add -A && git commit -q -m 'x y'", "ship.py commit sub"),
                ("git push -u origin HEAD", "ship.py push sub"),
                ("git switch -c topic", "ship.py start sub <topic>"),
                ("git checkout -b topic origin/main", "ship.py start sub"),
                ("git branch topic", "ship.py start sub"),
                ("git -c user.name=x commit -m x", "ship.py commit sub")):
            v = self.decide(cmd, cwd=self.sub)
            self.assertIsNotNone(v, cmd)
            self.assertEqual("deny", v[0])
            self.assertIn(want, v[1], cmd)
        # named from elsewhere: cd, git -C, and a worktree of the submodule
        for cmd, cwd in (("cd sub && git commit -m x", self.root),
                         ("git -C sub push", self.root),
                         ("git -C %s commit -m x" % self.sub, self._tmp.name),
                         ("git commit -m x", self.wt)):
            v = self.decide(cmd, cwd=cwd)
            self.assertIsNotNone(v, cmd)
            self.assertIn(" sub", v[1])

    def test_the_superproject_is_the_board_target(self):
        v = self.decide("git commit -m x", cwd=self.root)
        self.assertIn("ship.py commit board", v[1])
        self.assertIn("commit workspace", v[1])

    def test_reads_and_everything_outside_the_workspace_pass(self):
        for cmd in ("git status", "git log --oneline -3", "git diff", "git fetch origin main",
                    "git add -A", "git stash", "git switch main", "git checkout main -- a.txt",
                    "git branch --show-current", "git branch -a", "git branch -d old",
                    "git branch", "git worktree list", "git merge-base --is-ancestor a b",
                    "echo git commit", "ls"):
            self.assertIsNone(self.decide(cmd, cwd=self.sub), cmd)
        for cmd in ("git commit -m x", "git push", "git switch -c t"):
            self.assertIsNone(self.decide(cmd, cwd=self.scratch), cmd)      # not a workspace repo
            self.assertIsNone(self.decide("cd %s && %s" % (self.scratch, cmd), cwd=self.sub), cmd)
        # where the command runs cannot be told: say nothing
        self.assertIsNone(self.decide("cd $SOMEWHERE && git commit -m x", cwd=self.sub))
        self.assertIsNone(self.decide("git commit -m 'unbalanced", cwd=self.sub))
        self.assertIsNone(self.decide("git commit -m x", cwd=self.sub, tool="Read"))

    def test_a_here_document_is_data_not_a_command(self):
        self.assertIsNone(self.decide("cat > notes.txt <<'E'\ngit commit -m x\nE", cwd=self.sub))

    def test_the_workspace_can_switch_it_off_and_no_workspace_means_no_guard(self):
        off = dict(self.ws, shipGuard=False)
        self.assertIsNone(self.decide("git commit -m x", cwd=self.sub, ws=off))
        self.assertIsNone(self.decide("git commit -m x", cwd=self.sub, ws={"instances": {}}))


if __name__ == "__main__":
    unittest.main()
