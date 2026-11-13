"""academy_common.subagent_report / transcript_report: a finished subagent's report (T-1194).

A subagent whose caller asked for a hand-off ends its run with a ``SubagentHandback``
tool call; its report is that call's ``message``, not a text block, and the SubagentStop
event's ``last_assistant_message`` is then empty. The landing hooks (expert
land_verdict / land_referee, researcher land_review) read the report through these.

Run from the repo root:  py -m unittest discover academy/tests
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))

import academy_common as ac  # noqa: E402

REPORT = "Verdict: CONFIRMED.\n\nVERDICT\nsubject: s1:GEO-73\nrun: A\n"


def assistant(*blocks, model="claude-opus-5-5"):
    return {"type": "assistant", "isSidechain": True,
            "message": {"role": "assistant", "model": model, "content": list(blocks)}}


def text(t):
    return {"type": "text", "text": t}


def handback(message, name="SubagentHandback"):
    return {"type": "tool_use", "id": "toolu_1", "name": name, "input": {"message": message}}


def tool_result():
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_1",
         "content": [{"type": "text",
                      "text": '{"success":true,"message":"Report delivered to your caller."}'}]}]}}


def attachment():
    return {"type": "attachment", "attachment": {"type": "hook_success",
                                                 "hookEvent": "SubagentStop"}}


class TranscriptReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def transcript(self, *records):
        path = os.path.join(self.tmp, "agent.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return path

    def test_the_shape_that_was_lost(self):
        # T-1193 run A: the last assistant block is the hand-off, then its tool result
        # and the hook attachments; no assistant text anywhere after the brief
        tr = self.transcript(
            {"type": "user", "message": {"role": "user", "content": "the brief"}},
            assistant(text("Reading the attempt.")),
            assistant(handback(REPORT)), tool_result(), attachment(), attachment())
        self.assertEqual(ac.transcript_report(tr), (REPORT, "handback"))
        ev = {"agent_transcript_path": tr, "last_assistant_message": ""}
        self.assertEqual(ac.subagent_report(ev), REPORT)
        del ev["last_assistant_message"]
        self.assertEqual(ac.subagent_report(ev), REPORT)

    def test_a_handback_beats_the_preamble_of_its_own_message(self):
        # a text block written in the same turn as the hand-off is not the report,
        # even when the event carries it as last_assistant_message
        tr = self.transcript(assistant(text("Handing back now."), handback(REPORT)),
                             tool_result())
        ev = {"agent_transcript_path": tr, "last_assistant_message": "Handing back now."}
        self.assertEqual(ac.subagent_report(ev), REPORT)

    def test_blocks_split_one_per_record_are_read_in_order(self):
        # Claude Code writes each content block of one message as its own record
        tr = self.transcript(assistant(text("Handing back now.")), assistant(handback(REPORT)))
        self.assertEqual(ac.transcript_report(tr), (REPORT, "handback"))

    def test_plain_text_ending_is_unchanged(self):
        tr = self.transcript(assistant(text(REPORT)))
        self.assertEqual(ac.transcript_report(tr), (REPORT, "text"))
        self.assertEqual(ac.subagent_report({"agent_transcript_path": tr}), REPORT)
        # the event's own message still wins over a transcript that ends in text
        ev = {"agent_transcript_path": tr, "last_assistant_message": "Amended.\n" + REPORT}
        self.assertEqual(ac.subagent_report(ev), "Amended.\n" + REPORT)

    def test_text_after_a_handback_wins(self):
        # a resumed agent that ended its later run in plain text
        tr = self.transcript(assistant(handback("old report")), tool_result(),
                             assistant(text(REPORT)))
        self.assertEqual(ac.transcript_report(tr), (REPORT, "text"))
        ev = {"agent_transcript_path": tr, "last_assistant_message": REPORT}
        self.assertEqual(ac.subagent_report(ev), REPORT)

    def test_the_last_of_two_handbacks_wins(self):
        tr = self.transcript(assistant(handback("first")), tool_result(),
                             assistant(handback(REPORT)), tool_result())
        self.assertEqual(ac.transcript_report(tr), (REPORT, "handback"))

    def test_other_tool_calls_and_empty_handbacks_are_not_reports(self):
        tr = self.transcript(assistant(text(REPORT)),
                             assistant(handback("x", name="Read")),
                             assistant(handback("   ")),
                             assistant({"type": "tool_use", "name": "SubagentHandback",
                                        "input": "not a dict"}))
        self.assertEqual(ac.transcript_report(tr), (REPORT, "text"))

    def test_no_transcript_falls_back_to_the_event(self):
        self.assertEqual(ac.transcript_report(None), ("", ""))
        self.assertEqual(ac.transcript_report(os.path.join(self.tmp, "missing.jsonl")),
                         ("", ""))
        self.assertEqual(ac.subagent_report({"last_assistant_message": REPORT}), REPORT)
        self.assertEqual(ac.subagent_report({"lastAssistantMessage": [text(REPORT)]}), REPORT)
        self.assertEqual(ac.subagent_report({}), "")

    def test_the_camel_case_path_key_and_an_explicit_path(self):
        tr = self.transcript(assistant(handback(REPORT)))
        self.assertEqual(ac.subagent_report({"agentTranscriptPath": tr}), REPORT)
        self.assertEqual(ac.subagent_report({}, path=tr), REPORT)

    def test_bad_lines_are_skipped(self):
        path = os.path.join(self.tmp, "agent.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not json\n\n" + json.dumps(["a", "list"]) + "\n"
                     + json.dumps(assistant(handback(REPORT))) + "\n{truncated")
        self.assertEqual(ac.transcript_report(path), (REPORT, "handback"))


if __name__ == "__main__":
    unittest.main()
