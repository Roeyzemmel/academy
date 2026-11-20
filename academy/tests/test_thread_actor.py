"""The actor qualifier of a 'human' thread line (#100 part 2).

When the main Claude session writes as the human (tickets_update / tickets_create from the
main thread, ``as_human``), the thread line reads ``human (via main session):``, so an
audit can tell the session's bookkeeping from the human's own decisions. The plain
``human:`` stays the human's own hand (the CLI's default) and what a session records when
it writes down the human's quoted answer (``via: "human"``).
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
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

from test_board import BoardCase, DATE  # noqa: E402
from test_mcp import McpTestBase  # noqa: E402

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402

VIA = "human (via main session)"


class TestSpeaker(unittest.TestCase):
    def test_format_who_qualifies_only_the_human(self):
        self.assertEqual(VIA, ac.HUMAN_VIA_SESSION)
        self.assertEqual(VIA, ac.format_who("human", via="session"))
        self.assertEqual("human", ac.format_who("human", via="human"))
        self.assertEqual("human", ac.format_who("human"))
        self.assertEqual("author@main/math-writer",
                         ac.format_who("author@main", "math-writer", via="session"))

    def test_an_unknown_via_is_refused(self):
        with self.assertRaises(ac.AcademyError):
            ac.format_who("human", via="somebody")

    def test_is_human_speaker(self):
        self.assertTrue(ac.is_human_speaker("human"))
        self.assertTrue(ac.is_human_speaker(VIA))
        self.assertFalse(ac.is_human_speaker("author@main"))
        self.assertFalse(ac.is_human_speaker("human (via someone)"))

    def test_qualified_line_is_written_parsed_and_valid(self):
        meta = {"id": "T-0001", "title": "t", "kind": "question", "from": "human",
                "to": "expert@main", "status": "open", "priority": "normal", "ask": "a",
                "deliverable": "d", "budget": {"runs": 1}, "created": DATE,
                "updated": DATE}
        _fm, body = ac.read_frontmatter(ac.new_ticket(meta))
        body = ac.append_thread(body, VIA, "status open -> cancelled: a mistake", DATE)
        body = ac.append_thread(body, "human", "decision: (a)", DATE)
        self.assertEqual([(DATE, VIA, "status open -> cancelled: a mistake"),
                          (DATE, "human", "decision: (a)")], ac.thread_lines(body))
        self.assertEqual([], ac.validate_ticket(meta, body))

    def test_a_forged_qualifier_is_still_a_bad_speaker(self):
        self.assertIsNone(ac.RE_WHO.match("human (via someone)"))
        with self.assertRaises(ac.AcademyError):
            ac.append_thread("", "human (via someone)", "x", DATE)


class TestBoardCli(BoardCase):
    def test_board_functions_take_via_and_default_to_human(self):
        self.new()
        bd.append_to_ticket(self.board, "T-0001", "plain", date=DATE)
        bd.append_to_ticket(self.board, "T-0001", "bookkeeping", via="session", date=DATE)
        bd.transition_ticket(self.board, "T-0001", "cancelled", reason="filed twice",
                             via="session", date=DATE)
        who = [w for _d, w, _t in ac.thread_lines(bd.get_ticket(self.board, "T-0001")[2])]
        self.assertEqual(["author@main/math-writer", "human", VIA, VIA], who)

    def test_cli_via_flag(self):
        self.new()
        with contextlib.redirect_stdout(io.StringIO()):
            rc = bd.main(["--board", self.board, "--workspace", self.ws_path, "append",
                          "T-0001", "--text", "noted", "--via", "session"])
        self.assertEqual(0, rc)
        last = ac.thread_lines(bd.get_ticket(self.board, "T-0001")[2])[-1]
        self.assertEqual((VIA, "noted"), last[1:])


class TestGithubCodec(BoardCase):
    def test_qualified_speaker_roundtrips_through_issue_comments(self):
        p = self.new()
        bd.append_to_ticket(self.board, "T-0001", "bookkeeping", via="session", date=DATE)
        _p, meta, body = bd.get_ticket(self.board, "T-0001")
        e = bc.encode(meta, body)
        issue = {k: e[k] for k in ("number", "title", "body", "labels", "state",
                                   "state_reason")}
        m2, b2 = bc.decode(issue, e["comments"])
        with open(p, encoding="utf-8", newline="") as fh:
            self.assertEqual(fh.read(), bc.render(m2, b2))

    def test_a_session_move_counts_as_the_humans_for_the_reopen_rule(self):
        self.new()
        bd.transition_ticket(self.board, "T-0001", "blocked", blocked_by="paper:lem:y",
                             reopen_if="a new invariant", reason="tried X",
                             as_instance="expert@main", date=DATE)
        _p, meta, body = bd.get_ticket(self.board, "T-0001")
        before = bc.ticket_state(meta, body)
        bd.transition_ticket(self.board, "T-0001", "in-progress", reason="my call",
                             via="session", date=DATE)
        _p, meta, body = bd.get_ticket(self.board, "T-0001")
        self.assertEqual([], bc.check_reopen(before, bc.ticket_state(meta, body), body))


class TestMcp(McpTestBase):
    def _thread(self, s, tid):
        err, g = s.call("tickets_get", id=tid)
        self.assertFalse(err, g)
        self.assertEqual([], g["problems"])
        return ac.thread_lines(g["body"])

    def test_main_session_writes_as_human_via_main_session(self):
        human = self.server()
        err, t = human.call("tickets_create", title="Session filing", kind="question",
                            to="expert@t", ask="q", deliverable="d", as_human=True)
        self.assertFalse(err, t)
        err, r = human.call("tickets_update", id=t["id"], note="bookkeeping")
        self.assertFalse(err, r)
        self.assertEqual([VIA, VIA], [w for _d, w, _t in self._thread(human, t["id"])])

    def test_via_human_records_the_humans_own_words(self):
        human = self.server()
        err, t = human.call("tickets_create", title="The human's own", kind="question",
                            to="expert@t", ask="q", deliverable="d", as_human=True,
                            via="human")
        self.assertFalse(err, t)
        err, r = human.call("tickets_update", id=t["id"], status="cancelled",
                            reason="'drop it' (asked, answered)", via="human")
        self.assertFalse(err, r)
        self.assertEqual(["human", "human"],
                         [w for _d, w, _t in self._thread(human, t["id"])])

    def test_an_agent_passing_via_is_refused(self):
        author = self.server("author@t")
        err, msg = author.call("tickets_create", caller="author:math-writer",
                               title="x", kind="question", to="expert@t", ask="a",
                               deliverable="d", via="session")
        self.assertTrue(err)
        self.assertIn("via", msg)

    def test_the_write_gate_hook_records_a_call_carrying_via(self):
        """The real mcp_write_gate hook records the whole tool input, via included, under
        the key the server claims, so the call is identified (not refused as unknown)."""
        human = self.server()
        err, t = human.call("tickets_create", title="Hooked", kind="question",
                            to="expert@t", ask="q", deliverable="d", as_human=True)
        self.assertFalse(err, t)
        args = {"id": t["id"], "note": "the human said: go", "via": "human"}
        event = {"hook_event_name": "PreToolUse",
                 "tool_name": "mcp__plugin_academy_academy__tickets_update",
                 "tool_input": args, "cwd": self.tmp}
        res = subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "scripts",
                                                           "mcp_write_gate.py")],
                             input=json.dumps(event).encode("utf-8"), capture_output=True,
                             env=self.env, timeout=60)
        self.assertEqual(0, res.returncode, res.stderr)
        self.assertEqual(b"", res.stdout.strip())                  # no deny
        err, r = human.call("tickets_update", _hook=False, **args)
        self.assertFalse(err, r)
        self.assertEqual("human", self._thread(human, t["id"])[-1][1])
        err, msg = human.call("tickets_update", _hook=False, id=t["id"], note="x",
                              via="session")                       # no record: refused
        self.assertTrue(err)
        self.assertIn("could not be identified", msg)

    def test_schemas_offer_via(self):
        s = self.server()
        tools = {t["name"]: t for t in s.request("tools/list")["result"]["tools"]}
        for name in ("tickets_create", "tickets_update"):
            prop = tools[name]["inputSchema"]["properties"]["via"]
            self.assertEqual(["session", "human"], prop["enum"])


if __name__ == "__main__":
    unittest.main()
