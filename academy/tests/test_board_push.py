"""Tests for board_push.py, board_dump.py and lib/board_gh.py (the bulk migration transport).

Run from the repo root:  py -m unittest discover academy/tests
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board_github import GithubBoardCase  # noqa: E402

import board as bd  # noqa: E402
import board_dump as bdump  # noqa: E402
import board_export as be  # noqa: E402
import board_gh as gh  # noqa: E402
import board_push as bp  # noqa: E402
import board_store as bs  # noqa: E402
import board_verify as bv  # noqa: E402


def quiet(*_a):
    pass


class PushCase(GithubBoardCase):
    def setUp(self):
        GithubBoardCase.setUp(self)
        self.make()
        # T-0004 waits on T-0001: a dependency the push adds once every issue exists
        bd.transition_ticket(self.board, "T-0001", "accepted", as_instance="expert@main")
        self.new(title="Waiting one")
        bd.transition_ticket(self.board, "T-0004", "blocked", waiting_on=["T-0001"],
                             reason="needs T-0001", as_instance="expert@main")
        bd.transition_ticket(self.board, "T-0002", "cancelled", reason="not needed",
                             as_instance="author@main")
        self.m = be.build(self.board)
        self.state_path = os.path.join(self.tmp, "state.json")

    def push(self, t, state=None, **kw):
        return bp.push(t, self.m, state if state is not None else {}, self.state_path,
                       assignee="ada", log=quiet, **kw)

    def drift(self, t):
        return bv.verify(self.board, bdump.dump(t))


class TestPush(PushCase):
    def test_push_then_dump_verifies_with_zero_drift(self):
        t = bs.MemoryTransport()
        self.push(t)
        self.assertEqual([], self.drift(t))
        self.assertEqual({2: 1}, t.parents)
        self.assertEqual([(4, 1)], t.dependencies)
        self.assertEqual(["ada"], t.issues[3]["assignees"])
        self.assertEqual("closed", t.issues[2]["state"])
        self.assertEqual("not_planned", t.issues[2]["state_reason"])

    def test_labels_are_created_first_with_the_manifest_colours(self):
        t = bs.MemoryTransport()
        self.push(t)
        first_create = [c[0] for c in t.calls].index("create_issue")
        made = [c for c in t.calls[:first_create] if c[0] == "create_label"]
        self.assertEqual(len(self.m["labels"]), len(made))
        want = {d["name"]: d["color"] for d in self.m["labels"]}
        self.assertEqual(want, {k: v["color"] for k, v in t.labels.items()})

    def test_resume_after_a_failure_mid_comments(self):
        t = bs.MemoryTransport()
        t.inject("add_comment", after=1)
        with self.assertRaises(RuntimeError):
            self.push(t)
        with open(self.state_path) as fh:
            state = json.load(fh)
        self.assertEqual("comments:1", state["1"])
        self.push(t, state)
        self.assertEqual([], self.drift(t))
        self.assertEqual(1, sum(1 for c in t.calls if c[0] == "create_issue" and "T-0001" in c[1]))

    def test_a_lost_state_after_a_create_is_recovered_from_the_repo(self):
        t = bs.MemoryTransport()
        t.inject("add_comment", after=0)
        with self.assertRaises(RuntimeError):
            self.push(t)
        state = {"labels": "done"}            # the "1": "created" write was lost
        self.push(t, state)
        self.assertEqual([], self.drift(t))
        self.assertEqual(4, len(t.issues))

    def test_a_lost_state_after_the_parent_link_does_not_link_twice(self):
        t = bs.MemoryTransport()
        t.inject("update_issue", after=0)     # T-0002 is closed after its parent link
        with self.assertRaises(RuntimeError):
            self.push(t)
        with open(self.state_path) as fh:
            state = json.load(fh)
        self.assertEqual("parent", state["2"])
        n = len([i for i in self.m["issues"] if i["number"] == 2][0]["comments"])
        state["2"] = "comments:%d" % n        # pretend the "parent" write was lost
        self.push(t, state)
        self.assertEqual(1, sum(1 for c in t.calls if c[0] == "set_parent"))
        self.assertEqual([], self.drift(t))

    def test_a_lagging_newest_issue_listing_does_not_stop_the_run(self):
        # live rehearsal: right after creating #65 the REST listing still said #64
        class Lagging(bs.MemoryTransport):
            def last_number(self):
                return max(max(self.issues, default=0) - 1, 0)
        t = Lagging()
        self.push(t)
        self.assertEqual([], self.drift(t))

    def test_the_dump_reads_past_a_lagging_listing(self):
        t = bs.MemoryTransport()
        self.push(t)
        real = t.list_issues
        t.list_issues = lambda **kw: [i for i in real(**kw) if i["number"] < 4]
        self.assertEqual([1, 2, 3, 4], [r["issue"]["number"] for r in bdump.dump(t)])

    def test_a_non_empty_repo_is_refused(self):
        t = bs.MemoryTransport()
        t.add_pull_request()
        with self.assertRaises(bp.PushStop):
            self.push(t)
        self.assertNotIn("create_issue", [c[0] for c in t.calls])

    def test_numbering_drift_stops_before_creating(self):
        t = bs.MemoryTransport()
        self.push(t, limit=2)
        t.add_pull_request()                  # someone opened a PR mid-run: it took #3
        with open(self.state_path) as fh:
            state = json.load(fh)
        with self.assertRaises(bp.PushStop):
            self.push(t, state)
        self.assertEqual(3, len(t.issues))

    def test_human_tickets_need_an_assignee(self):
        with self.assertRaises(bp.PushStop):
            bp.push(bs.MemoryTransport(), self.m, {}, None, assignee=None, log=quiet)

    def test_limit_makes_a_partial_run(self):
        t = bs.MemoryTransport()
        state = self.push(t, limit=2)
        self.assertEqual([1, 2], sorted(t.issues))
        self.assertNotIn("dependencies", state)
        self.push(t, state)
        self.assertEqual([], self.drift(t))

    def test_verify_flags_a_missing_assignee(self):
        t = bs.MemoryTransport()
        self.push(t)
        t.issues[3]["assignees"] = []
        self.assertTrue(any("#3: assignees" in d for d in self.drift(t)))

    def test_cli_refuses_a_manifest_for_another_repo(self):
        path = os.path.join(self.tmp, "m.json")
        m = dict(self.m, repo="me/one")
        with open(path, "w") as fh:
            json.dump(m, fh)
        self.assertEqual(2, bp.main(["--manifest", path, "--repo", "me/two",
                                     "--state", self.state_path, "--dry-run"]))


class FakeGh(object):
    """Records ``gh api`` invocations; answers from a queue of (code, stdout, stderr)."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, args, stdin):
        self.calls.append((args, json.loads(stdin) if stdin else None))
        return self.answers.pop(0)


class TestGhTransport(unittest.TestCase):
    def test_create_sends_the_body_verbatim_on_stdin(self):
        body = "<!-- academy:meta {\"a\":\"x \\u003e y\"} -->\n\n## Ask\n\n"
        fake = FakeGh([(0, json.dumps({"number": 1, "id": 99}), "")])
        t = gh.GhTransport("me/repo", run=fake)
        t.create_issue("T-0001: x", body, ["status:open"], assignees=["ada"])
        args, payload = fake.calls[0]
        self.assertEqual(["api", "-X", "POST"], args[:3])
        self.assertIn("repos/me/repo/issues", args)
        self.assertEqual(body, payload["body"])
        self.assertEqual(["ada"], payload["assignees"])

    def test_parent_and_dependency_use_issue_ids(self):
        fake = FakeGh([(0, json.dumps({"number": 5, "id": 500}), ""),
                       (0, "{}", ""),
                       (0, json.dumps({"number": 2, "id": 200}), ""),
                       (0, "{}", "")])
        t = gh.GhTransport("me/repo", run=fake)
        t.set_parent(5, 3)
        t.add_dependency(5, 2)
        self.assertIn("repos/me/repo/issues/3/sub_issues", fake.calls[1][0])
        self.assertEqual({"sub_issue_id": 500, "replace_parent": True}, fake.calls[1][1])
        self.assertIn("repos/me/repo/issues/5/dependencies/blocked_by", fake.calls[3][0])
        self.assertEqual({"issue_id": 200}, fake.calls[3][1])

    def test_a_new_parent_replaces_the_old_and_a_parent_can_be_removed(self):
        fake = FakeGh([(0, json.dumps({"number": 5, "id": 500}), ""), (0, "{}", ""),
                       (0, "{}", "")])
        t = gh.GhTransport("me/repo", run=fake, write_interval=0)
        t.set_parent(5, 3)
        t.remove_parent(5, 3)
        self.assertEqual({"sub_issue_id": 500, "replace_parent": True}, fake.calls[1][1])
        self.assertEqual(["api", "-X", "DELETE"], fake.calls[2][0][:3])
        self.assertIn("repos/me/repo/issues/3/sub_issue", fake.calls[2][0])
        self.assertEqual({"sub_issue_id": 500}, fake.calls[2][1])

    def test_transient_errors_are_retried_and_others_raise(self):
        slept = []
        fake = FakeGh([(1, "", "gh: Server Error (HTTP 502)"), (0, "[]", "")])
        t = gh.GhTransport("me/repo", run=fake, sleep=slept.append)
        self.assertEqual(0, t.last_number())
        self.assertEqual([2], slept)
        t = gh.GhTransport("me/repo", run=FakeGh([(1, "", "gh: Validation Failed (HTTP 422)")]))
        with self.assertRaises(gh.GhError) as e:
            t.create_label("x")
        self.assertEqual(422, e.exception.status)

    def test_a_secondary_rate_limit_is_waited_out(self):
        slept = []
        msg = ("gh: You have exceeded a secondary rate limit and have been temporarily "
               "blocked from content creation. (HTTP 403)")
        fake = FakeGh([(1, "", msg), (0, json.dumps({"id": 1}), "")])
        t = gh.GhTransport("me/repo", run=fake, sleep=slept.append, write_interval=0)
        t.add_comment(3, "x")
        self.assertEqual([gh.RATE_LIMIT_DELAYS[0]], slept)

    def test_writes_are_spaced(self):
        slept, now = [], [100.0]
        fake = FakeGh([(0, "{}", "")] * 3)
        t = gh.GhTransport("me/repo", run=fake, sleep=slept.append, clock=lambda: now[0],
                           write_interval=1.0)
        t.add_comment(1, "a")
        t.add_comment(1, "b")                 # no time passed: waits a full interval
        now[0] += 5
        t.add_comment(1, "c")                 # enough time passed: no wait
        self.assertEqual([1.0], slept)

    def test_missing_parent_is_none(self):
        t = gh.GhTransport("me/repo", run=FakeGh([(1, "", "gh: Not Found (HTTP 404)")]))
        self.assertIsNone(t.get_parent(7))


if __name__ == "__main__":
    unittest.main()
