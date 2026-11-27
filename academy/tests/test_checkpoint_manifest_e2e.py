"""#101 part 1 end to end: the inbox snapshots the homes before a ticket, and its --check
ships the ticket's manifest with the real ship.py -- in every home the ticket wrote to
(the T-1481 case: a delivered verify ticket's review pass in the library, its evidence row
in the paper's claim record, its packet and .ids/next-packet on the board), as WIP for an
unfinished one, and never a path that was dirty before the ticket. Temp repos only."""

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
TID = "T-1481"


class ManifestEndToEnd(unittest.TestCase):
    """The Expert's library, an Author home 'paper', the board a plain directory of the
    superproject; each on a work branch (a home dirty on main is refused, as before)."""

    def setUp(self):
        import ship
        self.ship = ship
        self.tmp = tempfile.mkdtemp(prefix="manifest-e2e-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root, _, _ = make_workspace(self.tmp)
        self.lib, self.lib_remote = add_submodule(self.tmp, self.root, "library")
        self.paper, self.paper_remote = add_submodule(self.tmp, self.root, "paper")
        self.put(self.paper, "claims/paper/lem-x.md", "record\n")
        self.put(self.paper, "main.tex", "tex\n")
        run(self.paper, "add", "-A")
        run(self.paper, "commit", "-q", "-m", "paper")
        run(self.paper, "switch", "-q", "-c", "2026-11-19/notes/author")
        run(self.lib, "switch", "-q", "-c", ship.branch_name("T-1479", "expert"))
        self.board = os.path.join(self.root, "board")
        self.put(self.root, "board/.ids/next-packet", "433\n")
        self.put(self.root, ".gitignore", "workspace.json\n")
        self.ws_path = os.path.join(self.root, "workspace.json")
        with open(self.ws_path, "w") as f:
            json.dump({"board": self.board.replace("\\", "/"), "instances": {
                "expert@t": {"role": "expert", "home": self.lib, "domains": ["d"]},
                "author@t": {"role": "author", "home": self.paper, "domains": ["d"],
                             "ns": "paper"}},
                "artefactCheck": False}, f)  # checkpoint tests: #100's artefact check has its own (test_delivery_artefacts)
        self.root_remote = os.path.join(self.tmp, "root-remote.git")
        run(self.tmp, "init", "-q", "--bare", "-b", "main", self.root_remote)
        run(self.root, "remote", "add", "origin", self.root_remote)
        env = {"ACADEMY_TOUCHED_DIR": os.path.join(self.tmp, "touched"),
               "CLAUDE_PROJECT_DIR": self.root, "ACADEMY_SHIP_SCRIPT": SHIP,
               "ACADEMY_WORKSPACE": self.ws_path}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        q = mock.patch.object(core, "SHIP_SCRIPT", SHIP)
        q.start()
        self.addCleanup(q.stop)
        old = ship.ROOT
        self.addCleanup(setattr, ship, "ROOT", old)
        # no usage records from this machine's real sessions
        u = mock.patch.dict(os.environ, {"HOME": os.path.join(self.tmp, "home")})
        u.start()
        self.addCleanup(u.stop)

    def put(self, repo, rel, text="x\n"):
        path = os.path.join(repo, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def ticket(self, status, result="verdict CONFIRMED"):
        meta = {"id": TID, "title": "verify paper:lem-x", "kind": "verify", "from": "author@t",
                "to": "expert@t", "status": status, "result": result if status == "delivered" else "",
                "priority": "normal", "ask": "a", "deliverable": "d", "refs": [], "blocks": [],
                "waiting_on": [], "budget": {"runs": 1, "max_model": "sonnet"}, "packets": [],
                "created": "2026-11-19", "updated": "2026-11-19"}
        folder = os.path.join(self.board, "expert@t")
        os.makedirs(folder, exist_ok=True)
        ac.atomic_write(os.path.join(folder, ac.ticket_filename(TID, "t")), ac.new_ticket(meta))
        # the board's ticket files are the store here; committed, so they are not the ticket's
        run(self.root, "add", "-A", "--", ".gitignore", ".gitmodules", "board", "library", "paper", "sub")
        run(self.root, "commit", "-q", "-m", "board")
        if run(self.root, "branch", "--show-current") == "main":
            run(self.root, "switch", "-q", "-c", self.ship.branch_name("board-work", "human"))

    def snapshot(self):
        return ac.manifest_snapshot(self.root, TID, run="inbox-all", board=self.board)

    def work(self):
        """What T-1481's verify wrote: its pass, its packet, the packet counter, the
        evidence row in the paper's claim record."""
        self.put(self.lib, "reviews/paper/lem-x/pass-1/A.md", "CONFIRMED\n")
        self.put(self.lib, "reviews/paper/lem-x/.open", "")
        self.put(self.root, "board/packets/P-0433.md", "packet\n")
        self.put(self.root, "board/.ids/next-packet", "434\n")
        self.put(self.paper, "claims/paper/lem-x.md", "record\nevidence: expert@t review\n")

    def check(self):
        args = core.parser("d").parse_args(["--check", TID, "--workspace", self.ws_path])
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stderr", err):
            code = core.run(args, "expert@t", self.board, 3, lambda m: {}, out=out)
        return code, out.getvalue(), err.getvalue()

    def head(self, repo):
        return (run(repo, "log", "-1", "--format=%s"),
                sorted(run(repo, "show", "--name-only", "--format=", "HEAD").splitlines()))

    def test_a_delivered_verify_commits_in_every_home_it_wrote_to(self):
        self.ticket("delivered")
        self.snapshot()
        self.work()
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        name = self.ship.run_branch_name("inbox-all", "expert")    # #102: the run's branch
        self.assertEqual(self.head(self.lib), ("T-1481: checkpoint", [
            "reviews/paper/lem-x/.open", "reviews/paper/lem-x/pass-1/A.md"]))
        self.assertEqual(self.head(self.paper), ("T-1481: checkpoint", ["claims/paper/lem-x.md"]))
        self.assertEqual(self.head(self.root), ("T-1481: checkpoint", [
            "board/.ids/next-packet", "board/packets/P-0433.md"]))
        for repo, remote in ((self.lib, self.lib_remote), (self.paper, self.paper_remote),
                             (self.root, self.root_remote)):
            self.assertEqual(run(repo, "branch", "--show-current"), name)
            self.assertEqual(run(remote, "rev-parse", "refs/heads/" + name),
                             run(repo, "rev-parse", "HEAD"))
            self.assertEqual(run(repo, "rev-parse", "ticket/T-1481/1^{commit}"),
                             run(repo, "rev-parse", "HEAD"))                  # #102: tagged
            # the superproject's moved submodule pointers are never the checkpoint's
            self.assertEqual(run(repo, "status", "--porcelain", "--", "board" if repo == self.root else "."), "")
        self.assertEqual(ac.find_claim(self.root, TID), (None, None))
        self.assertIsNone(ac.load_pending(self.root, TID))
        self.assertTrue(out.strip().endswith("T-1481: delivered (delivered)"), out)

    def test_a_path_dirty_before_the_ticket_is_not_committed(self):
        self.ticket("delivered")
        run(self.lib, "switch", "-q", "-c", self.ship.run_branch_name("inbox-all", "expert"))
        self.put(self.lib, "notes/human.md", "the human's, before the ticket\n")
        self.snapshot()
        self.work()
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("notes/human.md", self.head(self.lib)[1])
        self.assertEqual(run(self.lib, "status", "--porcelain", "--untracked-files=all"), "?? notes/human.md")

    def test_a_refused_home_keeps_its_part_of_the_manifest(self):
        self.ticket("delivered")
        self.put(self.paper, "main.tex", "the human's edit, before the ticket\n")
        self.snapshot()
        self.work()
        code, out, err = self.check()
        self.assertIn("REFUSED", out)
        self.assertEqual(self.head(self.lib)[0], "T-1481: checkpoint")       # the others went
        self.assertEqual(run(self.paper, "branch", "--show-current"), "2026-11-19/notes/author")
        self.assertEqual(ac.load_pending(self.root, TID)["repos"], {"paper": ["claims/paper/lem-x.md"]})
        self.assertEqual(ac.find_claim(self.root, TID), (None, None))
        # the human commits main.tex; the next --check ships the rest
        run(self.paper, "commit", "-q", "-m", "human", "--", "main.tex")
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.head(self.paper), ("T-1481: checkpoint", ["claims/paper/lem-x.md"]))
        self.assertIsNone(ac.load_pending(self.root, TID))

    def test_a_home_unreadable_at_the_snapshot_is_reported_not_claimed(self):
        self.ticket("delivered")
        git_dir = os.path.join(self.paper, ".git")
        os.rename(git_dir, git_dir + ".away")
        with open(git_dir, "w") as f:
            f.write("gitdir: /nowhere\n")
        self.snapshot()
        os.remove(git_dir)
        os.rename(git_dir + ".away", git_dir)
        self.work()
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertIn("checkpoint for T-1481: paper was unreadable at the snapshot", out)
        self.assertEqual(run(self.paper, "branch", "--show-current"), "2026-11-19/notes/author")
        self.assertIn("claims/paper/lem-x.md", run(self.paper, "status", "--porcelain"))
        self.assertEqual(self.head(self.lib)[0], "T-1481: checkpoint")

    def test_a_stale_claim_is_removed_at_the_check(self):
        self.ticket("delivered")
        ac.manifest_snapshot(self.root, "T-0002", run="inbox-all", board=self.board,
                             now=__import__("time").time() - 7 * 3600)
        self.snapshot()
        ac.manifest_snapshot(self.root, "T-0003", run="dead", board=self.board)
        f = ac.find_claim(self.root, "T-0003")[0]
        with open(f) as fh:
            c = json.load(fh)
        c["started"] -= 7 * 3600
        with open(f, "w") as fh:
            json.dump(c, fh)
        self.check()
        self.assertEqual(ac.run_claims(self.root), [])

    def test_an_unfinished_ticket_is_committed_as_wip(self):
        self.ticket("in-progress")
        self.snapshot()
        self.work()
        code, out, err = self.check()
        self.assertEqual(code, 3, out + err)
        msg = "WIP: T-1481 unfinished (in-progress)"
        for repo in (self.lib, self.paper, self.root):
            self.assertEqual(self.head(repo)[0], msg)
        name = self.ship.run_branch_name("inbox-all", "expert")
        self.assertEqual(run(self.lib_remote, "rev-parse", "refs/heads/" + name),
                         run(self.lib, "rev-parse", "HEAD"))

    def test_without_a_snapshot_an_unfinished_ticket_ships_nothing_as_before(self):
        self.ticket("in-progress")
        self.work()
        code, out, err = self.check()
        self.assertEqual(code, 3)
        self.assertIn("reviews/", run(self.lib, "status", "--porcelain"))


if __name__ == "__main__":
    unittest.main()
