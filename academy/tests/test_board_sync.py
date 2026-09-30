"""Tests for board_sync.plan (the pure part of the GitHub board backstop)."""

import json
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


API = "https://api.github.com/repos/o/r/issues/1"
CURL = "https://api.github.com/repos/o/r/issues/comments/%d"
BOT = bs.BOT_LOGIN


class FakeGithub(object):
    """Just enough REST for ``board_sync.sync``: records the calls, keeps comments. Comment
    URLs and the issue URL look like the real ones; a call to an unknown URL fails."""

    def __init__(self, comments):
        self.comments = [dict(c) for c in comments]
        self.calls = []
        self.next_id = 1000

    def __call__(self, method, url, payload=None):
        self.calls.append((method, url, payload))
        if method == "POST" and url == API + "/comments":
            self.next_id += 1
            self.comments.append({"body": payload["body"], "url": CURL % self.next_id,
                                  "user": {"login": BOT}})
        elif method == "PATCH" and "/comments/" in url:
            hit = [c for c in self.comments if c["url"] == url]
            assert hit, "PATCH of unknown comment " + url
            hit[0]["body"] = payload["body"]
        elif method == "DELETE" and "/comments/" in url:
            assert any(c["url"] == url for c in self.comments), "DELETE of unknown " + url
            self.comments = [c for c in self.comments if c["url"] != url]
        elif method == "PATCH" and url == API:
            pass
        else:
            raise AssertionError("unexpected call %s %s" % (method, url))

    def of(self, mark):
        return [c for c in self.comments if c["body"].startswith(mark)]


def state_comment(state, login=BOT, n=1):
    return {"body": bs.STATE_MARK + (state if isinstance(state, str) else json.dumps(state))
            + bs.STATE_END, "url": CURL % n, "user": {"login": login}}


class TestSyncRun(ReopenBase):
    def api_comments(self, cs):
        return [{"body": c, "url": CURL % i, "user": {"login": "roey"}}
                for i, c in enumerate(cs)]

    def hand_reopened(self):
        """The issue after a hand edit: accepted, the dead-route fields gone, no entry."""
        m, b = self.ticket()
        m = dict(m, status="accepted")
        m.pop("blocked_by"); m.pop("reopen_if")
        return self.issue_for(m, b)

    def test_state_comment_is_written_then_used_to_catch_a_hand_reopen(self):
        gh = FakeGithub(self.api_comments(self.cs))
        bs.sync(self.iss, gh.comments, gh, API)
        states = gh.of(bs.STATE_MARK)
        self.assertEqual(1, len(states))
        self.assertEqual(BOT, states[0]["user"]["login"])
        # next event: the hand edit; the stored state says the ticket was a dead route
        iss, cs = self.hand_reopened()
        gh.comments = self.api_comments(cs) + states
        p = bs.sync(iss, gh.comments, gh, API)
        self.assertTrue(p["problems"])
        self.assertTrue(gh.of(bs.PROBLEM_MARK))
        # the state did not advance to the violation
        self.assertIn('"dead":true', gh.of(bs.STATE_MARK)[0]["body"])

    def test_state_advances_after_a_proper_reopen(self):
        gh = FakeGithub(self.api_comments(self.cs))
        bs.sync(self.iss, gh.comments, gh, API)
        bd.transition_ticket(self.board, "T-0001", "accepted", reopen="new lemma",
                             as_instance="expert@main", date="2026-09-30")
        iss, cs = self.issue_for(*self.ticket())
        gh.comments = self.api_comments(cs) + gh.of(bs.STATE_MARK)
        p = bs.sync(iss, gh.comments, gh, API)
        self.assertEqual([], p["problems"])
        st = gh.of(bs.STATE_MARK)
        self.assertEqual(1, len(st))
        self.assertIn('"dead":false', st[0]["body"])
        self.assertIn('"reopened":1', st[0]["body"])

    # -- finding 1: a forged or malformed state comment must not turn the backstop off ------
    def test_malformed_state_comments_never_crash_and_are_reported(self):
        for forged in ("5", "[1]", '"issue"', "null",
                       '{"status":"blocked","dead":true,"entries":"a","reopened":0}',
                       '{"status":"nonsense","dead":true,"entries":1,"reopened":0}',
                       '{"status":"blocked","dead":"yes","entries":1,"reopened":0}',
                       '{"status":"blocked","dead":true,"entries":1,"reopened":true}',
                       "{not json"):
            iss, cs = self.hand_reopened()
            gh = FakeGithub(self.api_comments(cs) + [state_comment(forged, n=99)])
            p = bs.sync(iss, gh.comments, gh, API)        # must not raise
            self.assertTrue(any("malformed" in x for x in p["problems"]), (forged, p))
            # the bot's own malformed comment is rewritten in place, not duplicated
            self.assertEqual(1, len(gh.of(bs.STATE_MARK)), forged)

    def test_plan_survives_malformed_previous_and_bad_issues(self):
        iss, cs = self.hand_reopened()
        for prev in (5, [1], "issue", {"status": "blocked", "dead": True, "entries": "a",
                                       "reopened": 0}, {"issue": 5}, {"issue": {"x": 1}}):
            p = bs.plan(iss, cs, prev)
            self.assertIsInstance(p["problems"], list, prev)
        p = bs.plan({"number": 1, "title": 5, "body": None, "labels": 7}, [])
        self.assertTrue(p["problems"])

    def test_a_state_comment_by_anyone_but_the_bot_is_ignored(self):
        iss, cs = self.hand_reopened()
        forged = state_comment({"status": "accepted", "dead": False, "reopened": 0,
                                "entries": 1}, login="mallory", n=77)
        gh = FakeGithub(self.api_comments(cs) + [forged])
        p = bs.sync(iss, gh.comments, gh, API)
        self.assertTrue(any("ignored" in x for x in p["problems"]), p)
        # with no trusted state the unreopened dead route is still seen
        self.assertTrue(any("state missing" in x for x in p["problems"]), p)
        self.assertIn(forged["body"], [c["body"] for c in gh.comments])  # not touched

    def test_the_last_bot_state_comment_counts_and_duplicates_are_deleted(self):
        gh = FakeGithub(self.api_comments(self.cs))
        bs.sync(self.iss, gh.comments, gh, API)
        good = gh.of(bs.STATE_MARK)[0]
        stale = state_comment({"status": "accepted", "dead": False, "reopened": 0,
                               "entries": 1}, n=50)            # an older, different state
        iss, cs = self.hand_reopened()
        gh.comments = [stale] + self.api_comments(cs) + [good]
        gh.comments[-1]["url"] = CURL % 51
        p = bs.sync(iss, gh.comments, gh, API)
        self.assertTrue(any("without a new 'reopened" in x for x in p["problems"]), p)
        self.assertIn(("DELETE", CURL % 50, None), gh.calls)
        self.assertEqual(1, len(gh.of(bs.STATE_MARK)))

    def test_duplicate_states_collapse_when_the_rule_holds(self):
        a = state_comment(bc.ticket_state(*self.ticket()), n=50)
        b = state_comment(bc.ticket_state(*self.ticket()), n=51)
        gh = FakeGithub(self.api_comments(self.cs) + [a, b])
        bs.sync(self.iss, gh.comments, gh, API)
        self.assertEqual([CURL % 51], [c["url"] for c in gh.of(bs.STATE_MARK)])
        self.assertIn(("DELETE", CURL % 50, None), gh.calls)

    # -- finding 2: deleting or rewriting the state, editing the thread --------------------
    def test_deleted_state_on_a_hand_reopened_dead_route_is_reported(self):
        iss, cs = self.hand_reopened()
        gh = FakeGithub(self.api_comments(cs))                  # no state comment at all
        p = bs.sync(iss, gh.comments, gh, API)
        self.assertTrue(any("state missing" in x for x in p["problems"]), p)
        self.assertEqual([], gh.of(bs.STATE_MARK))              # and no fresh state is blessed

    def test_first_sync_of_a_clean_dead_route_writes_state_without_complaint(self):
        gh = FakeGithub(self.api_comments(self.cs))
        p = bs.sync(self.iss, gh.comments, gh, API)
        self.assertEqual([], p["problems"])
        self.assertEqual(1, len(gh.of(bs.STATE_MARK)))
        self.assertEqual([], gh.of(bs.PROBLEM_MARK))

    def test_first_sync_of_an_already_violating_ticket_is_flagged(self):
        self.assertTrue(bs.plan(*self.hand_reopened())["problems"])
        # but a properly reopened ticket on its first sync is clean
        bd.transition_ticket(self.board, "T-0001", "accepted", reopen="new lemma",
                             as_instance="expert@main", date="2026-09-30")
        self.assertEqual([], bs.plan(*self.issue_for(*self.ticket()))["problems"])

    def test_an_edited_thread_entry_with_the_same_count_is_reported(self):
        m, b = self.ticket()
        iss, cs = self.issue_for(m, b)
        cs = list(cs)
        cs[-1] = cs[-1].replace("status blocked", "status BLOCKED") \
            if "status blocked" in cs[-1] else cs[-1] + "\nrewritten"
        self.assertNotEqual(self.cs, cs)
        probs = bs.plan(iss, cs, self.prev)["problems"]
        self.assertTrue(any("edited or replaced" in x for x in probs), probs)
        # an appended entry is fine
        b2 = ac.append_thread(b, "expert@main", "note: still thinking", "2026-09-30")
        iss, cs = self.issue_for(m, b2)
        self.assertEqual([], bs.plan(iss, cs, self.prev)["problems"])

    def test_a_replaced_thread_comment_is_reported(self):
        m, b = self.ticket()
        iss, cs = self.issue_for(m, b)
        forged = bc.encode_comment("2026-09-30", "expert@main", "tried: something else")
        probs = bs.plan(iss, list(cs[:-1]) + [forged], self.prev)["problems"]
        self.assertTrue(any("edited or replaced" in x for x in probs), probs)

    def test_a_forged_reopened_entry_passes_the_limit_is_documented(self):
        """The server checks the state, not the person: GitHub identity is one account."""
        iss, cs = self.hand_reopened()
        forged = bc.encode_comment("2026-09-30", "expert@main", "reopened: trust me")
        self.assertEqual([], bs.plan(iss, list(cs) + [forged], self.prev)["problems"])
        for f in ("github", "x y"):                     # but not a non-speaker name
            bad = bc.encode_comment("2026-09-30", f, "reopened: trust me")
            p = bs.plan(iss, list(cs) + [bad], self.prev)["problems"]
            self.assertTrue(p, f)
        self.assertIn("one account", bs.__doc__)

    # -- finding 3: stale problem comments -----------------------------------------------
    def test_a_problem_comment_becomes_resolved_when_the_problem_clears(self):
        gh = FakeGithub(self.api_comments(self.cs))
        bs.sync(self.iss, gh.comments, gh, API)
        iss, cs = self.hand_reopened()
        gh.comments = self.api_comments(cs) + gh.of(bs.STATE_MARK)
        bs.sync(iss, gh.comments, gh, API)
        probs = gh.of(bs.PROBLEM_MARK)
        self.assertEqual(1, len(probs))
        self.assertIn("does not pass", probs[0]["body"])
        # undone: back to the dead route
        gh.comments = self.api_comments(self.cs) + gh.of(bs.STATE_MARK) + probs
        p = bs.sync(self.iss, gh.comments, gh, API)
        self.assertEqual([], p["problems"])
        self.assertEqual(bs.RESOLVED, gh.of(bs.PROBLEM_MARK)[0]["body"])
        n = len(gh.calls)
        bs.sync(self.iss, gh.comments, gh, API)                  # idempotent: no more writes
        self.assertEqual([], [c for c in gh.calls[n:] if c[0] != "PATCH" or c[1] != API])
        self.assertEqual(1, len(gh.of(bs.PROBLEM_MARK)))

    # -- finding 6: the human's exemption ------------------------------------------------
    def test_the_human_may_leave_a_dead_route_by_any_move(self):
        m, b = self.ticket()
        m = dict(m, status="in-progress")
        m.pop("blocked_by"); m.pop("reopen_if")
        iss, cs = self.issue_for(m, b)
        self.assertTrue(bs.plan(iss, cs, self.prev)["problems"])          # unknown editor
        self.assertEqual([], bs.plan(iss, cs, self.prev, human=True)["problems"])
        b2 = ac.append_thread(b, "human", "status blocked -> in-progress: my call",
                              "2026-09-30")
        iss, cs = self.issue_for(m, b2)                                   # human speaker
        self.assertEqual([], bs.plan(iss, cs, self.prev)["problems"])
        # the human exemption does not cover a removed or edited thread
        self.assertTrue(bs.plan(iss, list(cs[:-2]), self.prev, human=True)["problems"])

    def test_sync_passes_the_human_flag_and_advances_the_state(self):
        m, b = self.ticket()
        m = dict(m, status="in-progress")
        m.pop("blocked_by"); m.pop("reopen_if")
        iss, cs = self.issue_for(m, b)
        gh = FakeGithub(self.api_comments(cs) + [state_comment(self.prev)])
        p = bs.sync(iss, gh.comments, gh, API, human=True)
        self.assertEqual([], p["problems"])
        self.assertIn('"status":"in-progress"', gh.of(bs.STATE_MARK)[0]["body"])

    def test_cancelling_is_accepted_whoever_does_it(self):
        self.assertIn("cannot tell", bc.check_reopen.__doc__)


if __name__ == "__main__":
    unittest.main()
