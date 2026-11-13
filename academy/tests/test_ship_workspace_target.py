"""ship.py's ``workspace`` target: the workspace repo's own files, never the board's,
a submodule's, or a submodule pointer (2026-11-13: with the ship guard on, these files
had no way to be committed but the human's git)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ship  # noqa: E402
from ship_fixture import run  # noqa: E402
from test_ship import Base  # noqa: E402


class WorkspaceTarget(Base):
    def setUp(self):
        super().setUp()
        self.put("board/README.md", "board\n")
        self.put("CLAUDE.md", "one\n")
        run(self.root, "add", ".gitmodules", "board", "CLAUDE.md", "sub")
        run(self.root, "commit", "-q", "-m", "init")
        bare = os.path.join(self._tmp.name, "root-remote.git")
        run(self._tmp.name, "init", "-q", "--bare", "-b", "main", bare)
        run(self.root, "remote", "add", "origin", bare)
        run(self.root, "push", "-q", "-u", "origin", "main")
        self.bare = bare

    def put(self, rel, text):
        full = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)

    def committed(self):
        return sorted(run(self.root, "show", "--name-only", "--format=", "HEAD").split())

    def test_all_takes_the_workspaces_own_files_and_nothing_else(self):
        self.assertEqual(0, self.ship("start", "workspace", "docs", "--role", "human")[0])
        self.assertTrue(ship.BRANCH.match(ship.current(self.root)))
        self.put("CLAUDE.md", "two\n")
        self.put("scripts/tool.sh", "echo\n")
        self.put("board/packet.md", "a packet\n")              # the board's
        self.write("a.txt", "changed in the submodule\n")       # the submodule's
        run(self.sub, "commit", "-q", "-am", "move the pointer")
        rc, out, err = self.ship("ship", "workspace", "-m", "docs", "--all")
        self.assertEqual(0, rc, err)
        self.assertEqual(["CLAUDE.md", "scripts/tool.sh"], self.committed())
        self.assertIn("board/packet.md", run(self.root, "status", "--porcelain"))
        self.assertTrue(run(self.root, "ls-remote", self.bare,
                            "refs/heads/" + ship.current(self.root)))
        # the pointer moved in the checkout and was not committed
        self.assertNotEqual(run(self.root, "rev-parse", "HEAD:sub"), run(self.sub, "rev-parse", "HEAD"))

    def test_paths_of_another_target_are_refused(self):
        self.ship("start", "workspace", "docs", "--role", "human")
        self.put("board/packet.md", "a packet\n")
        rc, out, err = self.ship("commit", "workspace", "-m", "x", "--paths", "board/packet.md")
        self.assertEqual(1, rc)
        self.assertIn("is the target board, not workspace", err)
        rc, out, err = self.ship("commit", "workspace", "-m", "x", "--paths", "sub/a.txt")
        self.assertEqual(1, rc)
        self.assertIn("is the target sub", err)
        self.put("CLAUDE.md", "three\n")
        rc, out, err = self.ship("commit", "workspace", "-m", "x", "--paths", "CLAUDE.md")
        self.assertEqual(0, rc, err)
        self.assertEqual(["CLAUDE.md"], self.committed())

    def test_status_lists_it_and_checkpoint_leaves_it_alone(self):
        self.put("CLAUDE.md", "dirty\n")
        rc, out, err = self.ship("status")
        row = [ln for ln in out.splitlines() if ln.startswith("workspace ")]
        self.assertEqual(1, len(row), out)
        self.assertIn("dirty=1", row[0])
        self.assertNotIn("workspace", ship.targets())
        self.ship("checkpoint", "--ticket", "T-0007")
        self.assertIn("CLAUDE.md", run(self.root, "status", "--porcelain"))


if __name__ == "__main__":
    unittest.main()
