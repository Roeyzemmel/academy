"""#100 part 1: the status ``partial`` (work done, the deliverable not met) through the board
CLI, the MCP tool, the GitHub codec, the desk and /academy:decide."""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import academy_common as ac  # noqa: E402
import academy_status as st  # noqa: E402
import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402
import decisions as dc  # noqa: E402
import workplan  # noqa: E402
from test_board_github import issue_of  # noqa: E402
from test_decisions import DecisionsCase  # noqa: E402
from test_mcp import McpTestBase  # noqa: E402

DATE = "2026-11-20"


class BoardCli(DecisionsCase):
    def started(self, **kw):
        self.ticket(**kw)
        for s in ("accepted", "in-progress"):
            bd.transition_ticket(self.board, "T-0001", s, as_instance="expert@main", date=DATE)

    def test_partial_needs_a_result_and_a_reopen_needs_a_reason(self):
        self.started()
        with self.assertRaises(ac.AcademyError):
            bd.transition_ticket(self.board, "T-0001", "partial", as_instance="expert@main")
        bd.transition_ticket(self.board, "T-0001", "partial", result="attempt incomplete: step 3",
                             as_instance="expert@main", date=DATE)
        _p, meta, body = bd.get_ticket(self.board, "T-0001")
        self.assertEqual(meta["status"], "partial")
        self.assertIn("status in-progress -> partial", body)
        with self.assertRaises(ac.AcademyError):                 # the sender's move
            bd.transition_ticket(self.board, "T-0001", "closed", as_instance="expert@main")
        bd.transition_ticket(self.board, "T-0001", "in-progress", reason="finish step 3",
                             as_instance="author@main", date=DATE)
        self.assertEqual(bd.get_ticket(self.board, "T-0001")[1]["status"], "in-progress")

    def test_the_codec_round_trips_partial_and_assigns_the_human_sender(self):
        self.started(as_instance="human")
        bd.transition_ticket(self.board, "T-0001", "partial", result="half",
                             as_instance="expert@main", date=DATE)
        path, meta, body = bd.get_ticket(self.board, "T-0001")
        e = bc.encode(meta, body)
        self.assertIn("status:partial", e["labels"])
        self.assertEqual(e["state"], "open")
        self.assertTrue(e["assign_human"])                        # the human sent it: theirs now
        m2, b2 = bc.decode(issue_of(e), e["comments"])
        self.assertEqual(m2["status"], "partial")
        with open(path, encoding="utf-8", newline="") as fh:
            self.assertEqual(fh.read(), bc.render(m2, b2))
        self.assertEqual([], bc.check_transition("partial", "closed", "sender"))
        self.assertTrue(bc.check_transition("partial", "closed", "receiver"))

    def test_decide_lists_a_partial_ticket_the_human_sent_and_records_the_answer(self):
        self.started(as_instance="human")
        bd.transition_ticket(self.board, "T-0001", "partial", result="half",
                             as_instance="expert@main", date=DATE)
        items = [i for i in dc.pending_decisions(self.board) if i["id"] == "T-0001"]
        self.assertEqual(len(items), 1, items)
        self.assertEqual(items[0]["source"], "ticket-partial")
        self.assertEqual(items[0]["instance"], "expert@main")
        self.assertIn("partial", items[0]["question"])
        r = dc.record(self.board, "T-0001", "a", comment="finish it", date=DATE)
        self.assertEqual(r["status"], "in-progress")
        bd.transition_ticket(self.board, "T-0001", "partial", result="half again",
                             as_instance="expert@main", date=DATE)
        r = dc.record(self.board, "T-0001", "b", date=DATE)
        self.assertEqual(r["status"], "closed")
        self.assertEqual(dc.pending_decisions(self.board), [])

    def test_a_partial_ticket_an_instance_sent_is_not_the_humans(self):
        self.started()
        bd.transition_ticket(self.board, "T-0001", "partial", result="half",
                             as_instance="expert@main", date=DATE)
        self.assertEqual(dc.pending_decisions(self.board), [])

    def test_the_desk_shows_partial_tickets(self):
        self.started(as_instance="human")
        bd.transition_ticket(self.board, "T-0001", "partial", result="half",
                             as_instance="expert@main", date=DATE)
        s = st.summary(self.board, self.ws, "2026-01-01", include_instances=False)
        self.assertEqual([t["id"] for t in s["needs_you"]["partial_from_human"]], ["T-0001"])
        self.assertEqual([t["id"] for t in s["came_back"]["tickets"]], ["T-0001"])
        text = st.render(s)
        self.assertIn("NEEDS YOU (1)", text)
        self.assertIn("partial", text)

    def test_a_workplan_counts_partial_as_done(self):
        self.assertIn("partial", workplan.TERMINAL)


class Mcp(McpTestBase):
    def test_status_partial_needs_a_result_and_walks_from_open(self):
        author, expert = self.server("author@t"), self.server("expert@t")
        err, t = author.call("tickets_create", caller="author:math-writer", title="Check",
                             kind="verify", to="expert@t", ask="Verify paper:lem:x.",
                             deliverable="A packet.")
        r = "expert:review-chair"
        err, msg = expert.call("tickets_update", caller=r, id=t["id"], status="partial")
        self.assertTrue(err)
        self.assertIn("result", str(msg))
        err, res = expert.call("tickets_update", caller=r, id=t["id"], status="partial",
                               fields={"result": "run A only: B lost to a limit"})
        self.assertFalse(err, res)
        err, got = expert.call("tickets_get", caller=r, id=t["id"])
        self.assertEqual(got["meta"]["status"], "partial")
        self.assertEqual(got["problems"], [])


if __name__ == "__main__":
    unittest.main()
