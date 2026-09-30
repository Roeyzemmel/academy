"""Tests for board_sync.plan (the pure part of the GitHub board backstop)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board_github import GithubBoardCase, issue_of  # noqa: E402

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402
import board_sync as bs  # noqa: E402


class TestPlan(GithubBoardCase):
    def first(self):
        self.make()
        _p, m, b = next(iter(bd.iter_tickets(self.board)))
        e = bc.encode(m, b)
        return issue_of(e), e["comments"]

    def test_consistent_issue_needs_nothing(self):
        iss, cs = self.first()
        p = bs.plan(iss, cs)
        self.assertEqual({"labels": None, "state": None, "problems": []}, p)

    def test_wrong_role_is_rewritten(self):
        iss, cs = self.first()
        iss["labels"] = [("role:author" if l.startswith("role:") else l) for l in iss["labels"]]
        p = bs.plan(iss, cs)
        self.assertIn("role:expert", p["labels"])
        self.assertNotIn("role:author", p["labels"])
        self.assertEqual([], p["problems"])

    def test_state_follows_status(self):
        iss, cs = self.first()
        iss["labels"] = [("status:closed" if l.startswith("status:") else l) for l in iss["labels"]]
        p = bs.plan(iss, cs)
        self.assertEqual(("closed", "completed"), p["state"])
        self.assertTrue(any("needs result" in x for x in p["problems"]))

    def test_two_status_labels_are_a_problem_not_a_guess(self):
        iss, cs = self.first()
        iss["labels"] = iss["labels"] + ["status:accepted"]
        p = bs.plan(iss, cs)
        self.assertTrue(p["problems"])
        self.assertIsNone(p["labels"])

    def test_placeholder_is_left_alone(self):
        p = bs.plan(bc.placeholder(4), [])
        self.assertEqual({"labels": None, "state": None, "problems": []}, p)


class ReopenBase(GithubBoardCase):
    def setUp(self):
        super().setUp()
        self.new(title="Dead route", campaign="paper:thm:x")
        bd.transition_ticket(self.board, "T-0001", "accepted", as_instance="expert@main",
                             date="2026-09-30")
        bd.transition_ticket(self.board, "T-0001", "blocked", blocked_by="paper:lem:y",
                             reopen_if="a new invariant", reason="tried the induction",
                             as_instance="expert@main", date="2026-09-30")
        self.meta, self.body = self.ticket()
        e = bc.encode(self.meta, self.body)
        self.iss, self.cs = issue_of(e), e["comments"]
        self.prev = bc.ticket_state(self.meta, self.body)

    def ticket(self):
        _p, m, b = next(iter(bd.iter_tickets(self.board)))
        return m, b

    def issue_for(self, meta, body):
        e = bc.encode(meta, body)
        return issue_of(e), e["comments"]


class TestRouteAndReopen(ReopenBase):
    def test_state_is_compact_and_says_dead(self):
        self.assertTrue(self.prev["dead"])
        self.assertEqual("blocked", self.prev["status"])
        self.assertEqual(0, self.prev["reopened"])

    def test_route_label_is_rewritten_when_missing_or_spurious(self):
        self.iss["labels"] = [l for l in self.iss["labels"] if l != "route:dead"]
        p = bs.plan(self.iss, self.cs)
        self.assertIn("route:dead", p["labels"])
        self.assertEqual(1, sum(1 for l in p["labels"] if l.startswith("role:")))
        self.assertEqual([], p["problems"])
        m, b = self.ticket()
        bd.transition_ticket(self.board, "T-0001", "accepted", reopen="new lemma",
                             as_instance="expert@main", date="2026-09-30")
        m, b = self.ticket()
        iss, cs = self.issue_for(m, b)
        iss["labels"] = iss["labels"] + ["route:dead"]
        p = bs.plan(iss, cs)
        self.assertNotIn("route:dead", p["labels"])

    def test_consistent_dead_route_needs_nothing(self):
        self.assertEqual({"labels": None, "state": None, "problems": []},
                         bs.plan(self.iss, self.cs, self.prev))

    def test_proper_reopen_passes(self):
        bd.transition_ticket(self.board, "T-0001", "accepted", reopen="new lemma L",
                             as_instance="expert@main", date="2026-09-30")
        iss, cs = self.issue_for(*self.ticket())
        self.assertEqual([], bs.plan(iss, cs, self.prev)["problems"])
        self.assertIn("route:dead", "".join(self.iss["labels"]))
        self.assertNotIn("route:dead", iss["labels"])

    def test_hand_edited_reopen_without_thread_entry_is_reported(self):
        m, b = self.ticket()
        m = dict(m, status="accepted")
        m.pop("blocked_by"); m.pop("reopen_if")
        iss, cs = self.issue_for(m, b)
        probs = bs.plan(iss, cs, self.prev)["problems"]
        self.assertTrue(any("without a new 'reopened: <the new mechanism>'" in x for x in probs), probs)
        # the same edit is accepted once the thread says how it reopened
        b2 = ac.append_thread(b, "human", "reopened: a new mechanism", "2026-09-30")
        iss, cs = self.issue_for(m, b2)
        self.assertEqual([], bs.plan(iss, cs, self.prev)["problems"])

    def test_dead_route_turned_pending_by_editing_meta_is_reported(self):
        m, b = self.ticket()
        m = dict(m, waiting_on=["T-0009"])
        m.pop("blocked_by"); m.pop("reopen_if")
        iss, cs = self.issue_for(m, b)
        self.assertEqual([], bs.plan(iss, cs)["problems"])          # fine without history
        probs = bs.plan(iss, cs, self.prev)["problems"]
        self.assertTrue(any("changed to pending" in x for x in probs), probs)

    def test_dead_route_to_another_status_is_reported(self):
        m, b = self.ticket()
        m = dict(m, status="in-progress")
        m.pop("blocked_by"); m.pop("reopen_if")
        iss, cs = self.issue_for(m, b)
        probs = bs.plan(iss, cs, self.prev)["problems"]
        self.assertTrue(any("left blocked for in-progress" in x for x in probs), probs)

    def test_cancelling_a_dead_route_is_allowed(self):
        m, b = self.ticket()
        m = dict(m, status="cancelled")
        m.pop("blocked_by"); m.pop("reopen_if")
        b = ac.append_thread(b, "author@main", "status blocked -> cancelled: moot", "2026-09-30")
        iss, cs = self.issue_for(m, b)
        self.assertEqual([], bs.plan(iss, cs, self.prev)["problems"])

    def test_no_longer_blocked_must_not_carry_dead_route_fields(self):
        """Label edit to accepted while the meta line still carries blocked_by/reopen_if."""
        iss = dict(self.iss, labels=[("status:accepted" if l.startswith("status:") else l)
                                     for l in self.iss["labels"]])
        probs = bs.plan(iss, self.cs)["problems"]
        self.assertTrue(any("must be empty unless status is blocked" in x for x in probs), probs)
        self.assertTrue(any("reopened" in x for x in bs.plan(iss, self.cs, self.prev)["problems"]))

    def test_removed_thread_entries_are_reported(self):
        m, b = self.ticket()
        entries = ac.thread_lines(b)
        iss, cs = self.issue_for(m, b)
        probs = bs.plan(iss, cs[:-1], self.prev)["problems"]
        self.assertTrue(any("append-only" in x for x in probs), (len(entries), probs))

    def test_previous_may_be_a_snapshot(self):
        m, b = self.ticket()
        snap = {"issue": self.iss, "comments": self.cs}
        m2 = dict(m, status="accepted")
        m2.pop("blocked_by"); m2.pop("reopen_if")
        iss, cs = self.issue_for(m2, b)
        self.assertTrue(bs.plan(iss, cs, snap)["problems"])
        self.assertEqual(bs.previous_state(snap), self.prev)
        self.assertIsNone(bs.previous_state(None))

    def test_offline_cli_prints_the_plan_and_exits_1_on_problems(self):
        import io, json, tempfile
        from contextlib import redirect_stdout
        m, b = self.ticket()
        m2 = dict(m, status="accepted")
        m2.pop("blocked_by"); m2.pop("reopen_if")
        iss, cs = self.issue_for(m2, b)
        files = {}
        for name, data in (("issue", iss), ("comments", cs), ("previous", self.prev)):
            fd, path = tempfile.mkstemp(dir=self.tmp, suffix=".json")
            with os.fdopen(fd, "w") as fh:
                json.dump(data, fh)
            files[name] = path
        out = io.StringIO()
        with redirect_stdout(out):
            rc = bs.main(["--issue", files["issue"], "--comments", files["comments"],
                          "--previous", files["previous"]])
        self.assertEqual(1, rc)
        self.assertTrue(json.loads(out.getvalue())["problems"])


class FakeGithub(object):
    """Just enough REST for ``board_sync.sync``: records the calls, keeps comments."""

    def __init__(self, comments):
        self.comments = [dict(c) for c in comments]
        self.calls = []

    def __call__(self, method, url, payload=None):
        self.calls.append((method, url, payload))
        if method == "POST" and url.endswith("/comments"):
            self.comments.append({"body": payload["body"], "url": "u%d" % len(self.comments)})
        elif method == "PATCH" and url.startswith("u"):
            for c in self.comments:
                if c["url"] == url:
                    c["body"] = payload["body"]


class TestSyncRun(ReopenBase):
    def api_comments(self, cs):
        return [{"body": c, "url": "c%d" % i} for i, c in enumerate(cs)]

    def test_state_comment_is_written_then_used_to_catch_a_hand_reopen(self):
        gh = FakeGithub(self.api_comments(self.cs))
        bs.sync(self.iss, gh.comments, gh, "api")
        states = [c for c in gh.comments if c["body"].startswith(bs.STATE_MARK)]
        self.assertEqual(1, len(states))
        # next event: the hand edit; the stored state says the ticket was a dead route
        m, b = self.ticket()
        m = dict(m, status="accepted")
        m.pop("blocked_by"); m.pop("reopen_if")
        iss, cs = self.issue_for(m, b)
        gh.comments = [c for c in gh.comments if not c["body"].startswith("<!--")] + states
        gh.comments = self.api_comments(cs) + states
        p = bs.sync(iss, gh.comments, gh, "api")
        self.assertTrue(p["problems"])
        self.assertTrue(any(c["body"].startswith(bs.PROBLEM_MARK) for c in gh.comments))
        # the state did not advance to the violation
        st = [c for c in gh.comments if c["body"].startswith(bs.STATE_MARK)]
        self.assertIn('"dead":true', st[0]["body"])

    def test_state_advances_after_a_proper_reopen(self):
        gh = FakeGithub(self.api_comments(self.cs))
        bs.sync(self.iss, gh.comments, gh, "api")
        bd.transition_ticket(self.board, "T-0001", "accepted", reopen="new lemma",
                             as_instance="expert@main", date="2026-09-30")
        iss, cs = self.issue_for(*self.ticket())
        states = [c for c in gh.comments if c["body"].startswith(bs.STATE_MARK)]
        gh.comments = self.api_comments(cs) + states
        p = bs.sync(iss, gh.comments, gh, "api")
        self.assertEqual([], p["problems"])
        st = [c for c in gh.comments if c["body"].startswith(bs.STATE_MARK)]
        self.assertIn('"dead":false', st[0]["body"])
        self.assertIn('"reopened":1', st[0]["body"])


if __name__ == "__main__":
    unittest.main()
