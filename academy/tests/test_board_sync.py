"""Tests for board_sync.plan (the pure part of the GitHub board backstop)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board_github import GithubBoardCase, issue_of  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
