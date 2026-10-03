"""Tests for board_batch.py (a reviewed batch of board changes, applied as the human)."""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board import BoardCase  # noqa: E402

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import board_batch as bb  # noqa: E402

BATCH = {"title": "t", "ops": [
    {"op": "create", "as": "dec", "to": "human", "on_behalf_of": "author@main",
     "kind": "decision", "title": "Restate lemma 4.2", "ask": "choose a or b",
     "deliverable": "a decision", "why": "audit finding 4"},
    {"op": "update", "id": "T-0001", "status": "blocked", "fields": {"waiting_on": ["${dec}"]},
     "reason": "waits on ${dec}"},
    {"op": "update", "id": "T-0002", "fields": {"parent": "T-0001"},
     "note": "part of T-0001 (audit)"},
]}


class TestBatch(BoardCase):
    def setUp(self):
        BoardCase.setUp(self)
        self.new()
        self.new(title="Second")
        self.ctx = bb.human_context(self.ws, ac.FileBoardStore(self.board))

    def meta(self, tid):
        return bd.get_ticket(self.board, tid)[1]

    def test_a_batch_files_links_and_blocks_as_the_human(self):
        state = bb.run(BATCH, self.ctx, log=lambda *_: None)
        self.assertEqual({"done": 3, "names": {"dec": "T-0003"}}, state)
        self.assertEqual("blocked", self.meta("T-0001")["status"])
        self.assertEqual(["T-0003"], self.meta("T-0001")["waiting_on"])
        self.assertEqual(["T-0001"], self.meta("T-0003")["blocks"])     # mirrored
        self.assertEqual("T-0001", self.meta("T-0002")["parent"])
        self.assertEqual("author@main", self.meta("T-0003")["from"])
        _p, _m, body = bd.get_ticket(self.board, "T-0001")
        self.assertIn("human: status open -> blocked: waits on T-0003", body)

    def test_a_refusal_stops_and_a_rerun_resumes_after_the_last_done_op(self):
        bad = {"title": "t", "ops": BATCH["ops"][:2] + [
            {"op": "update", "id": "T-0009", "note": "no such ticket"}] + BATCH["ops"][2:]}
        path = os.path.join(self.tmp, "state.json")
        with self.assertRaises(bb.BatchError) as cm:
            bb.run(bad, self.ctx, state_path=path, log=lambda *_: None)
        self.assertIn("op 3", str(cm.exception))
        with open(path) as fh:
            state = json.load(fh)
        self.assertEqual(2, state["done"])
        fixed = {"title": "t", "ops": bad["ops"][:2] + [bad["ops"][3]]}
        bb.run(fixed, self.ctx, state, path, log=lambda *_: None)
        self.assertEqual("T-0001", self.meta("T-0002")["parent"])
        self.assertEqual(1, len([1 for _p, m, _b in bd.iter_tickets(self.board)
                                 if m["title"] == "Restate lemma 4.2"]))     # not filed twice

    def test_an_unknown_name_is_refused_before_anything_is_written(self):
        with self.assertRaises(bb.BatchError):
            bb.run({"title": "t", "ops": BATCH["ops"][1:]}, self.ctx, log=lambda *_: None)
        self.assertEqual("open", self.meta("T-0001")["status"])

    def test_dry_run_leaves_the_board_untouched(self):
        before = sorted(os.listdir(os.path.join(self.board, "expert@main")))
        path = os.path.join(self.tmp, "batch.json")
        with open(path, "w") as fh:
            json.dump(BATCH, fh)
        self.assertEqual(0, bb.main([path, "--dry-run", "--workspace", self.ws_path]))
        self.assertEqual(before, sorted(os.listdir(os.path.join(self.board, "expert@main"))))
        self.assertEqual("open", self.meta("T-0001")["status"])
        self.assertFalse(os.path.exists(path + ".state.json"))


if __name__ == "__main__":
    unittest.main()
