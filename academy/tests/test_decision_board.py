"""Tests for the decision board v2 (#86): decisions.py's routine policy, real options,
multi-select batches, pinned releases, folded rulings, leads and the session files.

Run from the repo root:  py -m unittest discover academy/tests
"""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import decisions as dc  # noqa: E402
from test_decisions import DATE, DecisionsCase  # noqa: E402

LATER = "2026-09-29"


def texts(board, tid):
    _m, body = bd.read_ticket(ac.find_ticket(board, tid))
    return [t for _d, _w, t in ac.thread_lines(body)]


def meta_of(board, tid):
    return bd.read_ticket(ac.find_ticket(board, tid))[0]


class BoardCase(DecisionsCase):
    def policy(self, *cats):
        self.ws["decisions"] = {"routine": list(cats)}

    def blocked(self, **kw):
        kw.setdefault("to", "expert@main")
        kw.setdefault("as_instance", "human")
        path = self.ticket(**kw)
        tid = bd.read_ticket(path)[0]["id"]
        bd.transition_ticket(self.board, tid, "blocked", waiting_on=["human"],
                             as_instance=kw["to"], date=DATE)
        return tid


# ----------------------------------------------------------------------------
# (1) the routine policy, its digest and the undo window
# ----------------------------------------------------------------------------

class RoutinePolicyTests(BoardCase):
    def test_no_policy_accepts_nothing(self):
        self.blocked(kind="verify")
        self.assertEqual(dc.routine_policy(self.ws), [])
        self.assertEqual(dc.apply_policy(self.board, self.ws, date=DATE), [])
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "blocked")

    def test_policy_kinds_are_accepted_and_the_rest_stay_asked(self):
        self.policy("verify", "cite")
        self.blocked(kind="verify", title="Verify lem:a")
        self.blocked(kind="cite", title="Cite X")
        self.blocked(kind="review-experiment", title="Review lab:x", to="researcher@r1")
        self.blocked(kind="prove", title="Prove lem:b", to="researcher@r1")
        done = dc.apply_policy(self.board, self.ws, date=DATE)
        self.assertEqual([d["id"] for d in done], ["T-0001", "T-0002"])
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "accepted")
        self.assertEqual(meta_of(self.board, "T-0003")["status"], "blocked")
        left = [i["id"] for i in dc.pending_decisions(self.board, workspace=self.ws)]
        self.assertEqual(left, ["T-0003", "T-0004"])
        self.assertTrue(any(t.startswith(dc.POLICY_MARK) for t in texts(self.board, "T-0001")))

    def test_dry_run_writes_nothing(self):
        self.policy("verify")
        self.blocked(kind="verify")
        done = dc.apply_policy(self.board, self.ws, date=DATE, dry_run=True)
        self.assertEqual([d["id"] for d in done], ["T-0001"])
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "blocked")

    def test_review_experiment_is_never_routine(self):
        with self.assertRaises(ac.AcademyError):
            dc.routine_policy({"decisions": {"routine": ["review-experiment"]}})
        with self.assertRaises(ac.AcademyError):
            dc.routine_policy({"decisions": {"routine": ["no-such-kind"]}})

    def test_claim_status_and_repair_categories(self):
        self.policy("claim-status", "repair")
        self.blocked(kind="decision", title="Status of s1:GEO-3 -> sketch", to="researcher@r1")
        self.blocked(kind="prove", title="Repair the proof of s1:GEO-4", to="researcher@r1")
        self.blocked(kind="prove", title="Prove s1:GEO-5", to="researcher@r1")
        self.blocked(kind="decision", title="Which modulo list?", to="researcher@r1")
        done = dc.apply_policy(self.board, self.ws, date=DATE)
        self.assertEqual([(d["id"], d["category"]) for d in done],
                         [("T-0001", "claim-status"), ("T-0002", "repair")])

    def test_a_ticket_to_the_human_is_accepted_from_open(self):
        self.policy("cite")
        self.ticket(to="human", kind="cite", as_instance="expert@main")
        done = dc.apply_policy(self.board, self.ws, date=DATE)
        self.assertEqual(done[0]["was"], "open")
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "accepted")

    def test_digest_one_line_per_kind_with_ids(self):
        done = [{"id": "T-0001", "category": "verify"}, {"id": "T-0002", "category": "cite"},
                {"id": "T-0003", "category": "verify"}]
        self.assertEqual(dc.digest(done),
                         "accepted under the policy: 2 verify (T-0001, T-0003), "
                         "1 cite (T-0002)")
        self.assertEqual(dc.digest([]), "")


class UndoTests(BoardCase):
    def test_undo_restores_a_blocked_ticket(self):
        self.policy("verify")
        self.blocked(kind="verify")
        dc.apply_policy(self.board, self.ws, date=DATE)
        out = dc.undo(self.board, "T-0001", date=LATER)
        self.assertEqual(out["status"], "blocked")
        m = meta_of(self.board, "T-0001")
        self.assertEqual((m["status"], m["waiting_on"]), ("blocked", ["human"]))
        self.assertEqual([i["id"] for i in dc.pending_decisions(self.board,
                                                                 workspace=self.ws)],
                         ["T-0001"])

    def test_undo_restores_an_open_ticket_to_the_human(self):
        self.policy("cite")
        self.ticket(to="human", kind="cite", as_instance="expert@main")
        dc.apply_policy(self.board, self.ws, date=DATE)
        self.assertEqual(dc.undo(self.board, "T-0001", date=LATER)["status"], "open")

    def test_undo_refused_once_an_inbox_run_touched_it(self):
        self.policy("verify")
        self.blocked(kind="verify")
        dc.apply_policy(self.board, self.ws, date=DATE)
        bd.transition_ticket(self.board, "T-0001", "in-progress", as_instance="expert@main",
                             date=LATER)
        with self.assertRaises(ac.AcademyError):
            dc.undo(self.board, "T-0001", date=LATER)

    def test_undo_refused_after_a_line_by_an_instance(self):
        self.policy("verify")
        self.blocked(kind="verify")
        dc.apply_policy(self.board, self.ws, date=DATE)
        bd.append_to_ticket(self.board, "T-0001", "picked up", as_instance="expert@main")
        with self.assertRaises(ac.AcademyError):
            dc.undo(self.board, "T-0001", date=LATER)

    def test_undo_refused_for_an_answer_the_human_gave(self):
        self.blocked(kind="verify")
        dc.record(self.board, "T-0001", "proceed", date=DATE)
        with self.assertRaises(ac.AcademyError):
            dc.undo(self.board, "T-0001", date=LATER)

    def test_undo_twice_refused(self):
        self.policy("verify")
        self.blocked(kind="verify")
        dc.apply_policy(self.board, self.ws, date=DATE)
        dc.undo(self.board, "T-0001", date=LATER)
        with self.assertRaises(ac.AcademyError):
            dc.undo(self.board, "T-0001", date=LATER)


class PolicyCLITests(BoardCase):
    def test_policy_cli_prints_the_digest(self):
        self.policy("verify")
        with open(self.ws_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        raw["decisions"] = {"routine": ["verify"]}
        with open(self.ws_path, "w", encoding="utf-8") as fh:
            json.dump(raw, fh)
        self.blocked(kind="verify")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = dc.main(["--board", self.board, "--workspace", self.ws_path, "policy"])
        self.assertEqual(rc, 0)
        self.assertIn("accepted under the policy: 1 verify (T-0001)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
