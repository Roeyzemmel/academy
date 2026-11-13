"""The touch ledger (academy_common._touched), its Edit hook (touch_record.py) and the
end-to-end path: a role writes in another role's home, the inbox's --check of its
finished ticket ships exactly that file with the real ship.py, on the acting role's
branch, and never an unrelated file. Temp repos and bare remotes only."""

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


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="touched-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        p = mock.patch.dict(os.environ, {"ACADEMY_TOUCHED_DIR": os.path.join(self.tmp, "t")})
        p.start()
        self.addCleanup(p.stop)
        self.root = os.path.join(self.tmp, "ws")

    def test_claim_takes_the_roles_unclaimed_entries_once(self):
        ac.record_touch(self.root, ["/x/a.bib"], "expert")
        ac.record_touch(self.root, ["/x/b.md"], "researcher")
        ac.record_touch(self.root, ["/x/c.md"], "expert", "expert@other")
        mine = ac.claim_touches(self.root, "T-0001", "expert", "expert@t")
        self.assertEqual([r["path"] for _, r in mine], [os.path.abspath("/x/a.bib")])
        self.assertEqual(ac.claim_touches(self.root, "T-0002", "expert", "expert@t"), [])
        again = ac.claim_touches(self.root, "T-0001", "expert", "expert@t")
        self.assertEqual([r["ticket"] for _, r in again], ["T-0001"])
        ac.drop_touches([f for f, _ in again])
        self.assertEqual(sorted(r["path"] for _, r in ac.touch_entries(self.root)),
                         [os.path.abspath("/x/b.md"), os.path.abspath("/x/c.md")])

    def test_workspaces_do_not_share_a_ledger(self):
        ac.record_touch(self.root, ["/x/a.bib"], "expert")
        self.assertEqual(ac.touch_entries(os.path.join(self.tmp, "other")), [])

    def test_old_entries_are_pruned(self):
        ac.record_touch(self.root, ["/x/a.bib"], "expert", now=1000.0)
        self.assertEqual(ac.touch_entries(self.root, now=1000.0 + 15 * 86400), [])
        self.assertEqual(os.listdir(ac.touched_dir(self.root)), [])

    def test_is_cross_home(self):
        ws = {"instances": {"author@t": {"role": "author", "home": "/w/paper"},
                            "expert@t": {"role": "expert", "home": "/w/library"}}}
        self.assertTrue(ac.is_cross_home(ws, "/w/paper/references.bib", "expert"))
        self.assertFalse(ac.is_cross_home(ws, "/w/library/cards/x.md", "expert"))
        self.assertFalse(ac.is_cross_home(ws, "/w/elsewhere/x", "expert"))
        self.assertFalse(ac.is_cross_home(ws, "/w/paper-two/x", "expert"))


class TouchRecordHookTests(unittest.TestCase):
    def setUp(self):
        import touch_record
        self.hook = touch_record
        self.tmp = tempfile.mkdtemp(prefix="touch-hook-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ws = {"_path": os.path.join(self.tmp, "workspace.json"),
                   "instances": {"author@t": {"role": "author",
                                              "home": os.path.join(self.tmp, "paper")},
                                 "expert@t": {"role": "expert",
                                              "home": os.path.join(self.tmp, "library")}}}
        for h in ("paper", "library"):
            os.makedirs(os.path.join(self.tmp, h))

    def event(self, path, agent="expert:librarian", cwd="library"):
        e = {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(self.tmp, path)},
             "cwd": os.path.join(self.tmp, cwd)}
        if agent:
            e["agent_type"] = agent
        return e

    def test_an_agents_write_in_another_roles_home_is_recorded(self):
        hit = self.hook.decide(self.event("paper/references.bib"), perms={}, ws=self.ws)
        self.assertEqual(hit, (self.tmp, os.path.join(self.tmp, "paper", "references.bib"),
                               "expert", "expert@t", "expert:librarian", "Edit"))

    def test_own_home_the_human_and_the_opt_out_are_not(self):
        self.assertIsNone(self.hook.decide(self.event("library/cards/x.md"), {}, self.ws))
        self.assertIsNone(self.hook.decide(self.event("paper/references.bib", agent=""),
                                           {}, self.ws))
        ws = dict(self.ws, shipCheckpoint=False)
        self.assertIsNone(self.hook.decide(self.event("paper/references.bib"), {}, ws))

    def test_main_never_raises(self):
        with mock.patch.object(self.hook.ac, "read_event", side_effect=RuntimeError("x")):
            self.assertEqual(self.hook.main(), 0)


class EndToEndTests(unittest.TestCase):
    """A workspace with the Expert's library and an Author home ('paper'), real ship.py."""

    BRANCH = "2026-11-12/notes/author"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="touch-e2e-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root, _, _ = make_workspace(self.tmp)
        self.lib, _ = add_submodule(self.tmp, self.root, "library")
        self.paper, self.paper_remote = add_submodule(self.tmp, self.root, "paper")
        for name, text in (("references.bib", "@book{A,}\n"), ("main.tex", "tex\n")):
            with open(os.path.join(self.paper, name), "w", encoding="utf-8") as f:
                f.write(text)
        run(self.paper, "add", "-A")
        run(self.paper, "commit", "-q", "-m", "paper")
        run(self.paper, "push", "-q", "origin", "main")
        run(self.paper, "switch", "-q", "-c", self.BRANCH)
        self.board = os.path.join(self.tmp, "board")   # outside the root: not a target here
        os.makedirs(self.board)
        ws = {"board": self.board.replace("\\", "/"), "instances": {
            "expert@t": {"role": "expert", "home": self.lib, "domains": ["d"]},
            "author@t": {"role": "author", "home": self.paper, "domains": ["d"], "ns": "paper"}}}
        self.ws_path = os.path.join(self.root, "workspace.json")
        with open(self.ws_path, "w") as f:
            json.dump(ws, f)
        env = {"ACADEMY_TOUCHED_DIR": os.path.join(self.tmp, "touched"),
               "CLAUDE_PROJECT_DIR": self.root, "ACADEMY_SHIP_SCRIPT": SHIP}
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        q = mock.patch.object(core, "SHIP_SCRIPT", SHIP)
        q.start()
        self.addCleanup(q.stop)
        self.put("T-0001")

    def put(self, tid, kind="cite"):
        meta = {"id": tid, "title": "t", "kind": kind, "from": "author@t", "to": "expert@t",
                "status": "delivered", "result": "done", "priority": "normal", "ask": "a",
                "deliverable": "d", "refs": [], "blocks": [], "waiting_on": [],
                "budget": {"runs": 1, "max_model": "sonnet"}, "packets": [],
                "created": "2026-11-13", "updated": "2026-11-13"}
        folder = os.path.join(self.board, "expert@t")
        os.makedirs(folder, exist_ok=True)
        ac.atomic_write(os.path.join(folder, ac.ticket_filename(tid, "t")), ac.new_ticket(meta))

    def write(self, rel, text):
        path = os.path.join(self.paper, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def check(self, tid="T-0001"):
        args = core.parser("d").parse_args(["--check", tid, "--workspace", self.ws_path])
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stderr", err):
            code = core.run(args, "expert@t", self.board, 3, lambda m: {}, out=out)
        return code, out.getvalue(), err.getvalue()

    def branch(self):
        import ship
        return ship.branch_name("T-0001", "expert")

    def test_a_cite_ships_the_bib_on_the_experts_branch_in_the_author_home(self):
        bib = self.write("references.bib", "@book{A,}\n@book{B,}\n")
        ac.record_touch(self.root, [bib], "expert", "expert@t", "expert:librarian", "Edit")
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        name = self.branch()
        self.assertEqual(run(self.paper, "branch", "--show-current"), name)
        self.assertEqual(run(self.paper, "show", "--name-only", "--format=", "HEAD"),
                         "references.bib")
        self.assertEqual(run(self.paper_remote, "rev-parse", "refs/heads/" + name),
                         run(self.paper, "rev-parse", "HEAD"))
        self.assertRegex(out, r"(?m)^paper %s @ \S+ \(1 files\) pushed$" % name)
        self.assertEqual(ac.touch_entries(self.root), [])

    def test_a_verify_ships_the_record_its_evidence_changed(self):
        rec = self.write("claims/paper/lem-x.md", "evidence row\n")
        ac.record_touch(self.root, [rec], "expert", "expert@t", "expert:review-chair",
                        "claims_attach_evidence")
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(run(self.paper, "show", "--name-only", "--format=", "HEAD"),
                         "claims/paper/lem-x.md")
        self.assertRegex(out, r"(?m)^paper \S+ @ \S+ \(1 files\) pushed$")

    def test_an_unrelated_dirty_file_there_is_not_committed(self):
        bib = self.write("references.bib", "@book{A,}\n@book{B,}\n")
        self.write("main.tex", "the human's edit\n")
        ac.record_touch(self.root, [bib], "expert", "expert@t")
        code, out, err = self.check()
        self.assertIn("REFUSED", out)
        self.assertEqual(run(self.paper, "branch", "--show-current"), self.BRANCH)
        self.assertEqual(run(self.paper, "rev-parse", "HEAD"), run(self.paper, "rev-parse",
                                                                   self.BRANCH))
        self.assertEqual(run(self.paper_remote, "for-each-ref", "--format=%(refname)"),
                         "refs/heads/main")
        self.assertEqual([r["ticket"] for _, r in ac.touch_entries(self.root)], ["T-0001"])

    def test_nothing_extra_without_a_cross_home_write(self):
        self.write("main.tex", "the human's edit\n")
        code, out, err = self.check()
        self.assertEqual(code, 0, out + err)
        self.assertNotIn("paper", out)
        self.assertEqual(run(self.paper, "branch", "--show-current"), self.BRANCH)

    def test_ship_checkpoint_false_switches_it_off(self):
        with open(self.ws_path) as f:
            ws = json.load(f)
        ws["shipCheckpoint"] = False
        with open(self.ws_path, "w") as f:
            json.dump(ws, f)
        bib = self.write("references.bib", "@book{A,}\n@book{B,}\n")
        ac.record_touch(self.root, [bib], "expert", "expert@t")
        code, out, err = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "T-0001: delivered (delivered)")
        self.assertEqual(run(self.paper, "branch", "--show-current"), self.BRANCH)


if __name__ == "__main__":
    unittest.main()
