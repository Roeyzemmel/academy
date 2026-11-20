"""``inbox.py --check`` refuses delivery while the ticket's branch is unpushed (#101, 2a).

T-1673's developer reported "Neither is pushed" and the ticket was still delivered; ten
academy branches had commits only in the container. After the checkpoint, ``--check`` of
a delivered ticket looks in every checked-out submodule and the superproject for local
branches whose name names the ticket (``t-1673``, ``t1673``, ``T-1673``, as a word of the
name) with commits on no remote-tracking branch, or a linked worktree on such a branch
with uncommitted changes: then the ticket is reported unfinished (exit 3, the status line
``T-NNNN: unfinished (delivered, unpushed)``) with the branch and the push command.
Temp repos and bare remotes only; the real ship.py runs the checkpoint before the scan."""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import academy_common as ac  # noqa: E402
from ship_fixture import add_submodule, make_workspace, run  # noqa: E402

core = ac.inbox_core
SHIP = os.path.join(PLUGIN, "scripts", "ship.py")
INST = "scientist@t"
DEV = "2026-11-19/t-0007-fix/scientist"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="unpushed-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root, self.code, self.code_remote = make_workspace(self.tmp)   # 'sub': the academy
        self.lab, _ = add_submodule(self.tmp, self.root, "lab")
        self.board = os.path.join(self.tmp, "board")   # outside the root: not a target here
        os.makedirs(self.board)
        self.ws_path = os.path.join(self.root, "workspace.json")
        self.write_ws()
        env = {"ACADEMY_TOUCHED_DIR": os.path.join(self.tmp, "touched"),
               "CLAUDE_PROJECT_DIR": self.root, "ACADEMY_SHIP_SCRIPT": SHIP}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        q = mock.patch.object(core, "SHIP_SCRIPT", SHIP)
        q.start()
        self.addCleanup(q.stop)

    def write_ws(self, **extra):
        ws = {"board": self.board.replace("\\", "/"), "instances": {
            INST: {"role": "scientist", "home": self.lab, "domains": ["d"]}}}
        ws.update(extra)
        with open(self.ws_path, "w") as f:
            json.dump(ws, f)

    def put(self, tid, status="delivered"):
        meta = {"id": tid, "title": "t", "kind": "code", "from": "human", "to": INST,
                "status": status, "result": "done", "priority": "normal", "ask": "a",
                "deliverable": "d", "refs": [], "blocks": [], "waiting_on": [],
                "budget": {"runs": 1, "max_model": "sonnet"}, "packets": [],
                "created": "2026-11-19", "updated": "2026-11-19"}
        folder = os.path.join(self.board, INST)
        os.makedirs(folder, exist_ok=True)
        ac.atomic_write(os.path.join(folder, ac.ticket_filename(tid, "t")), ac.new_ticket(meta))

    def check(self, tid="T-0007"):
        args = core.parser("d").parse_args(["--check", tid, "--workspace", self.ws_path])
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stderr", err):
            code = core.run(args, INST, self.board, 3, lambda m: {}, out=out)
        return code, out.getvalue(), err.getvalue()

    def worktree(self, branch, repo=None):
        """A developer's worktree of ``repo`` (default: the academy) on a new ``branch``."""
        repo = repo or self.code
        wt = os.path.join(repo, ".claude", "worktrees", branch.replace("/", "-"))
        run(repo, "worktree", "add", "-q", "-b", branch, wt)
        return wt

    def commit(self, repo, name="fix.py"):
        with open(os.path.join(repo, name), "w", encoding="utf-8") as f:
            f.write("x = 1\n")
        run(repo, "add", name)
        run(repo, "commit", "-q", "-m", "work in " + name)


class RefusalTests(Base):
    def test_a_delivered_ticket_with_an_unpushed_branch_is_unfinished(self):
        self.put("T-0007")
        wt = self.worktree(DEV)
        self.commit(wt)
        code, out, err = self.check()
        self.assertEqual(code, 3, out + err)
        first = [l for l in out.splitlines() if l.startswith("T-0007: ")][0]
        self.assertEqual(first, "T-0007: unfinished (delivered, unpushed); work of T-0007 "
                                "is not on a remote")
        self.assertIn("sub %s unpushed=1 dirty=0" % DEV, out)
        self.assertIn("py scripts/ship.py push sub --repo %s" % wt, out)

    def test_pushed_it_is_delivered(self):
        self.put("T-0007")
        wt = self.worktree(DEV)
        self.commit(wt)
        run(wt, "push", "-q", "origin", DEV)
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertRegex(out, r"(?m)^T-0007: delivered \(delivered\)$")
        self.assertNotIn("unpushed", out)

    def test_uncommitted_work_in_its_worktree_is_unfinished_too(self):
        self.put("T-0007")
        wt = self.worktree("2026-11-19/t0007/scientist")
        with open(os.path.join(wt, "half.py"), "w") as f:
            f.write("unfinished\n")
        code, out, err = self.check()
        self.assertEqual(code, 3, out + err)
        self.assertIn("sub 2026-11-19/t0007/scientist unpushed=0 dirty=1", out)
        self.assertIn("commit it first", out)

    def test_a_branch_in_the_main_checkout_without_a_worktree_counts(self):
        self.put("T-0007")
        run(self.code, "branch", "T-0007-old")
        run(self.code, "switch", "-q", "T-0007-old")
        self.commit(self.code)
        run(self.code, "switch", "-q", "main")
        code, out, err = self.check()
        self.assertEqual(code, 3, out + err)
        self.assertIn("sub T-0007-old unpushed=1", out)
        self.assertIn("not a <date>/<topic>/<role> branch", out)

    def test_other_tickets_branches_and_main_do_not_count(self):
        self.put("T-0007")
        for branch in ("2026-11-19/t-0070/scientist", "t-00071", "t-1007", "at-0007"):
            self.commit(self.worktree(branch))
        self.commit(self.code)                      # main, unpushed: not a ticket's branch
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("unpushed", out)

    def test_the_superproject_is_scanned(self):
        self.put("T-0007")
        wt = self.worktree("t-0007", repo=self.root)
        self.commit(wt)
        code, out, err = self.check()
        self.assertEqual(code, 3, out + err)
        self.assertIn("workspace t-0007 unpushed=1", out)

    def test_a_template_branch_of_the_superproject_is_pushed_as_workspace(self):
        self.put("T-0007")
        wt = self.worktree(DEV, repo=self.root)
        self.commit(wt)
        code, out, err = self.check()
        self.assertEqual(code, 3, out + err)
        self.assertIn("py scripts/ship.py push workspace --repo %s" % wt, out)

    def test_a_rejected_ticket_is_not_refused(self):
        self.put("T-0007", status="rejected")
        self.commit(self.worktree(DEV))
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertRegex(out, r"(?m)^T-0007: rejected \(rejected\)$")

    def test_the_checkpoints_own_branch_once_pushed_does_not_count(self):
        # the lab's dirty work is committed and pushed by the checkpoint on
        # <date>/t-0007/scientist, which then is on the remote: delivered
        self.put("T-0007")
        run(self.lab, "switch", "-q", "-c", "2026-11-19/other/scientist")
        with open(os.path.join(self.lab, "result.json"), "w") as f:
            f.write("{}\n")
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertRegex(out, r"(?m)^lab \S+/t-0007/scientist @ \S+ \(1 files\) pushed$")

    def test_unpushed_check_false_switches_it_off(self):
        self.write_ws(unpushedCheck=False)
        self.put("T-0007")
        self.commit(self.worktree(DEV))
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)

    def test_a_board_that_is_not_the_workspaces_is_not_scanned(self):
        other = os.path.join(self.tmp, "other-board")
        os.makedirs(other)
        self.board, keep = other, self.board
        self.put("T-0007")
        self.commit(self.worktree(DEV))
        self.assertEqual(self.check()[0], 0)
        self.board = keep


class PatternTests(unittest.TestCase):
    def test_names_that_name_the_ticket(self):
        hit = core.ticket_branch_re("T-0007")
        for name in ("t-0007", "t0007", "T-0007-fix", "2026-11-19/t-0007/scientist"):
            self.assertTrue(hit.search(name), name)
        # the board's four-digit form only: an academy issue branch (t7-x, t121-...) is not
        # the board ticket of the same number (review of 9f53a6e: T-0121 was held by
        # 2026-11-20/t121-ruling-followup/scientist)
        for name in ("t-0070", "t-00071", "t-1007", "at-0007", "main", "2026-11-19/x/human",
                     "t-0007a1", "2026-11-19/t7-x/scientist", "fix-t-07", "t-7"):
            self.assertFalse(hit.search(name), name)

    def test_an_issue_branch_does_not_hold_the_board_ticket_of_its_number(self):
        hit = core.ticket_branch_re("T-0121")
        self.assertFalse(hit.search("2026-11-20/t121-ruling-followup/scientist"))
        self.assertTrue(hit.search("2026-11-20/t-0121/expert"))

    def test_no_ticket_id_no_pattern(self):
        self.assertIsNone(core.ticket_branch_re("P-0001"))
        self.assertIsNone(core.ticket_branch_re("nonsense"))


if __name__ == "__main__":
    unittest.main()
