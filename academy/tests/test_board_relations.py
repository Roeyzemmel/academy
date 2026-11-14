"""Tests for board_relations.py (the native sub-issue / dependency mirror) and the exact
relation reads of lib/board_gh.py. No test touches the network: the fake transport is
board_store.MemoryTransport, and gh is a recorded fake.

Run from the repo root:  py -m unittest discover academy/tests
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board_github import GithubBoardCase  # noqa: E402
from test_board_push import FakeGh  # noqa: E402

import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402
import board_gh as gh  # noqa: E402
import board_relations as br  # noqa: E402
import board_store as bs  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "board_relations.py")
WRITES = ("set_parent", "remove_parent", "add_dependency", "remove_dependency")


def ops(p):
    return [(o["op"], o["issue"], o.get("parent", o.get("blocker"))) for o in p["ops"]]


class RelationsCase(GithubBoardCase):
    def setUp(self):
        GithubBoardCase.setUp(self)
        self.make()                       # T-0001; T-0002 child of T-0001; T-0003 to human
        bd.transition_ticket(self.board, "T-0001", "accepted", as_instance="expert@main")
        self.new(title="Waiting one")     # T-0004 waits on T-0001 and on the human
        bd.transition_ticket(self.board, "T-0004", "blocked", waiting_on=["T-0001", "human"],
                             reason="needs T-0001", as_instance="expert@main")
        self.new(title="Another")         # T-0005
        self.t = bs.from_file_board(self.board)

    def rewrite(self, n, **fields):
        """Change ticket ``n``'s meta line on the fake board, as a ticket write would."""
        meta, body = bc.decode(self.t.issues[n], self.t.thread_comments(n))
        meta.update(fields)
        for k in [k for k, v in meta.items() if v is None]:
            del meta[k]
        self.t.add_encoded(bc.encode(meta, body))

    def writes(self):
        return [c for c in self.t.calls if c[0] in WRITES]

    def sync(self):
        p = br.plan(self.t)
        return p, br.apply(self.t, p)


class TestPlan(RelationsCase):
    def test_plan_follows_the_meta_line_and_skips_non_ticket_tokens(self):
        p = br.plan(self.t)
        self.assertEqual([("add_sub_issue", 2, 1), ("add_blocked_by", 4, 1)], ops(p))
        self.assertEqual(1, p["tokens"])                  # 'human' has no native form
        self.assertEqual({"sub_issues": True, "dependencies": True}, p["available"])
        self.assertEqual([], self.writes())               # plan only reads

    def test_apply_then_a_second_run_is_a_no_op(self):
        _p, (done, failed) = self.sync()
        self.assertEqual((2, []), (len(done), failed))
        self.assertEqual({2: 1}, self.t.parents)
        self.assertEqual([(4, 1)], self.t.dependencies)
        self.t.calls[:] = []
        p, (done, failed) = self.sync()
        self.assertEqual(([], [], []), (p["ops"], done, failed))
        self.assertEqual([], self.writes())

    def test_a_cleared_relation_is_removed(self):
        self.sync()
        self.rewrite(2, parent=None)
        self.rewrite(4, status="accepted", waiting_on=None)
        p = br.plan(self.t)
        self.assertEqual([("remove_blocked_by", 4, 1), ("remove_sub_issue", 2, 1)], ops(p))
        br.apply(self.t, p)
        self.assertEqual(({}, []), (self.t.parents, self.t.dependencies))
        self.assertEqual([], br.plan(self.t)["ops"])

    def test_a_moved_parent_replaces_the_old_one(self):
        self.sync()
        self.rewrite(2, parent="T-0005")
        p = br.plan(self.t)
        self.assertEqual([("add_sub_issue", 2, 5)], ops(p))
        self.assertEqual("T-0001", p["ops"][0]["replaces"])
        br.apply(self.t, p)
        self.assertEqual({2: 5}, self.t.parents)

    def test_blocks_is_not_read(self):
        # T-0001 'blocks' T-0004 (bookkeeping, never pruned): only waiting_on decides
        self.rewrite(1, blocks=["T-0004", "T-0005"])
        self.assertNotIn(("add_blocked_by", 5, 1), ops(br.plan(self.t)))

    def test_dead_route_blocked_by_is_not_a_dependency(self):
        self.rewrite(5, status="blocked", blocked_by="T-0001", reopen_if="a new mechanism")
        self.assertEqual([], [o for o in br.plan(self.t)["ops"] if o["issue"] == 5])

    def test_a_target_not_on_the_board_is_reported_and_skipped(self):
        self.sync()
        self.rewrite(2, parent="T-0099")                  # never existed
        self.rewrite(5, parent="T-0005", status="blocked", waiting_on=["T-0098"])
        p = br.plan(self.t)
        self.assertEqual([], p["ops"])                    # the old native parent is kept
        got = {(u["issue"], u["field"], u["target"]) for u in p["unresolved"]}
        self.assertEqual({(2, "parent", "T-0099"), (5, "parent", "T-0005"),
                          (5, "waiting_on", "T-0098")}, got)
        self.assertEqual({2: 1}, self.t.parents)

    def test_a_placeholder_is_not_on_the_board(self):
        self.t.add_encoded(bc.placeholder(6))
        self.rewrite(5, parent="T-0006")
        p = br.plan(self.t)
        self.assertEqual([(5, "parent", "T-0006")],
                         [(u["issue"], u["field"], u["target"]) for u in p["unresolved"]])
        self.assertNotIn(5, [o["issue"] for o in p["ops"]])

    def test_links_to_issues_off_the_board_are_kept(self):
        self.sync()
        pr = self.t.add_pull_request()["number"]
        self.t.parents[3] = ("other/repo", 7)
        self.t.parents[5] = pr                            # not a board ticket
        self.t.dependencies += [(3, ("other/repo", 8)), (5, pr)]
        p = br.plan(self.t)
        self.assertEqual([], p["ops"])
        self.assertEqual({"other/repo#7", "other/repo#8", "#%d" % pr},
                         {k["target"] for k in p["kept"]})

    def test_ids_limit_the_tickets(self):
        p = br.plan(self.t, ids=["T-0004", "T-0042"])
        self.assertEqual([("add_blocked_by", 4, 1)], ops(p))
        self.assertEqual(["T-0042"], p["missing"])

    def test_the_listing_summaries_spare_the_reads(self):
        self.sync()
        self.t.summaries = True
        self.t.calls[:] = []
        self.assertEqual([], br.plan(self.t)["ops"])
        reads = [c for c in self.t.calls if c[0] in ("parent_ref", "blocker_refs")]
        self.assertEqual([("blocker_refs", 4)], reads)    # only the issue with a blocker


class TestUnavailableAndFailures(RelationsCase):
    def test_feature_unavailable_changes_nothing(self):
        self.t.unavailable = {"sub_issues", "dependencies"}
        p, (done, failed) = self.sync()
        self.assertEqual(([], [], []), (p["ops"], done, failed))
        self.assertEqual("not available on this repository", p["available"]["sub_issues"])
        self.assertEqual([], self.writes())

    def test_one_kind_unavailable_leaves_the_other(self):
        self.t.unavailable = {"dependencies"}
        p, _r = self.sync()
        self.assertEqual([("add_sub_issue", 2, 1)], ops(p))
        self.assertEqual(({2: 1}, []), (self.t.parents, self.t.dependencies))

    def test_partial_failure_then_resume(self):
        self.rewrite(5, status="blocked", waiting_on=["T-0001", "T-0003"])
        self.t.inject("add_dependency", after=1)          # the second dependency fails
        p, (done, failed) = self.sync()
        self.assertEqual(4, len(p["ops"]))
        self.assertEqual((3, 1), (len(done), len(failed)))
        self.assertIn("injected failure", failed[0][1])
        left = br.plan(self.t)
        self.assertEqual([failed[0][0]], left["ops"])     # exactly what failed is left
        _p, (done, failed) = self.sync()
        self.assertEqual((1, []), (len(done), failed))
        self.assertEqual([], br.plan(self.t)["ops"])


class TestMain(RelationsCase):
    def workspace(self, github=True):
        ws = dict(self.ws)
        ws["board"] = ({"path": self.board, "backend": "github", "repo": "o/r",
                        "transport": "_gh_seed:factory"} if github else self.board)
        path = os.path.join(self.tmp, "ws-rel.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(ws, fh)
        return path

    def run_script(self, *args):
        env = dict(os.environ, ACADEMY_TEST_SEED=self.board, PYTHONIOENCODING="utf-8",
                   PYTHONPATH=os.pathsep.join([HERE] + ([os.environ["PYTHONPATH"]]
                                                        if os.environ.get("PYTHONPATH") else [])))
        env.pop("ACADEMY_WORKSPACE", None)
        return subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True,
                              text=True, cwd=self.tmp, env=env)

    def test_plan_on_a_github_workspace(self):
        r = self.run_script("plan", "--workspace", self.workspace())
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertIn("+ T-0002 sub-issue of T-0001", r.stdout)
        self.assertIn("+ T-0004 blocked by T-0001", r.stdout)
        self.assertIn("nothing written", r.stdout)
        r = self.run_script("apply", "--json", "--workspace", self.workspace())
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertEqual(2, json.loads(r.stdout)["applied"])

    def test_a_file_board_or_a_bad_id_is_an_error(self):
        r = self.run_script("plan", "--workspace", self.workspace(github=False))
        self.assertEqual(2, r.returncode)
        self.assertIn("not on GitHub", r.stderr)
        self.assertEqual(2, self.run_script("plan", "--ids", "human").returncode)

    def test_main_reports_not_available_and_exits_cleanly(self):
        self.t.unavailable = {"sub_issues", "dependencies"}
        out = io.StringIO()
        orig = br.open_transport
        br.open_transport = lambda a: (self.t, "o/r")
        try:
            with contextlib.redirect_stdout(out):
                code = br.main(["apply"])
        finally:
            br.open_transport = orig
        self.assertEqual(0, code)
        self.assertIn("native relations not available", out.getvalue())
        self.assertEqual([], self.writes())

    def test_main_exit_1_on_a_failed_write(self):
        self.t.inject("set_parent")
        orig = br.open_transport
        br.open_transport = lambda a: (self.t, "o/r")
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = br.main(["apply"])
        finally:
            br.open_transport = orig
        self.assertEqual(1, code)
        self.assertIn("rerun apply to resume", out.getvalue())


class TestGhRelationReads(unittest.TestCase):
    def test_probe_reads_404_and_410_as_not_available(self):
        fake = FakeGh([(0, "[]", ""), (1, "", "gh: Not Found (HTTP 404)")])
        t = gh.GhTransport("me/repo", run=fake)
        self.assertEqual({"sub_issues": True, "dependencies": False}, t.relations_available(3))
        self.assertIn("repos/me/repo/issues/3/sub_issues?per_page=1", fake.calls[0][0])
        self.assertIn("repos/me/repo/issues/3/dependencies/blocked_by?per_page=1",
                      fake.calls[1][0])
        self.assertEqual(["api", "-X", "GET"], fake.calls[0][0][:3])
        t = gh.GhTransport("me/repo", run=FakeGh([(1, "", "gh: Gone (HTTP 410)")] * 2))
        self.assertEqual({"sub_issues": False, "dependencies": False}, t.relations_available(3))
        t = gh.GhTransport("me/repo", run=FakeGh([(1, "", "gh: Bad credentials (HTTP 401)")]))
        with self.assertRaises(gh.GhError):
            t.relations_available(3)

    def test_parent_and_blockers_keep_their_repository(self):
        parent = {"number": 7, "id": 70, "repository": {"full_name": "me/repo"}}
        rows = [{"number": 2, "id": 20,
                 "url": "https://api.github.com/repos/them/other/issues/2"}]
        fake = FakeGh([(0, json.dumps(parent), ""), (0, json.dumps(rows), ""),
                       (1, "", "gh: No parent issue found (HTTP 404)")])
        t = gh.GhTransport("me/repo", run=fake)
        self.assertEqual({"number": 7, "repo": "me/repo"}, t.parent_ref(5))
        self.assertEqual([{"number": 2, "repo": "them/other"}], t.blocker_refs(5))
        self.assertIn("repos/me/repo/issues/5/dependencies/blocked_by?per_page=100&page=1",
                      fake.calls[1][0])
        self.assertIsNone(t.parent_ref(6))

    def test_listed_ids_spare_the_id_read(self):
        fake = FakeGh([(0, "{}", "")])
        t = gh.GhTransport("me/repo", run=fake, write_interval=0)
        t.note_ids([{"number": 5, "id": 500}, {"number": 3, "id": 300}])
        t.add_dependency(5, 3)
        self.assertEqual(1, len(fake.calls))
        self.assertEqual({"issue_id": 300}, fake.calls[0][1])

    def test_url_ref(self):
        self.assertEqual({"number": 1198, "repo": "o/n"},
                         br._url_ref("https://api.github.com/repos/o/n/issues/1198"))
        self.assertIsNone(br._url_ref(None))


if __name__ == "__main__":
    unittest.main()
