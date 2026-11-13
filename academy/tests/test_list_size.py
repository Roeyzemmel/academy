"""The listing commands a session reads stay small (2026-11-13: ``board.py list`` printed
149 000 characters and ``packets.py list --open --json``, which a review reads, 189 000)."""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board import BoardCase, DATE, DECISION_BODY, INFO_BODY  # noqa: E402

import board as bd  # noqa: E402
import packets as pk  # noqa: E402


class ListSize(BoardCase):
    def run_cli(self, mod, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = mod.main(["--board", self.board, "--workspace", self.ws_path] + list(args))
        self.assertEqual(0, rc)
        return out.getvalue()

    def test_board_list_is_cut_and_says_how_many_there_are(self):
        for i in range(60):
            self.new(title="ticket %d" % i)
        lines = self.run_cli(bd, "list").splitlines()
        self.assertEqual(52, len(lines))
        self.assertEqual("60 ticket(s)", lines[50])
        self.assertIn("the first 50; open 60;", lines[51])
        self.assertEqual(61, len(self.run_cli(bd, "list", "--limit", "0").splitlines()))
        self.assertEqual(6, len(self.run_cli(bd, "list", "--limit", "5").splitlines()) - 1)
        self.assertEqual(60, len(json.loads(self.run_cli(bd, "list", "--json"))))   # unchanged

    def packet(self, title, body):
        return pk.create_packet(self.board, "expert@main", title, kind="verification",
                                body=body, date=DATE, workspace=self.ws)

    def test_packets_brief_is_what_a_review_needs(self):
        self.packet("to decide", DECISION_BODY)
        self.packet("to acknowledge", INFO_BODY)
        broken = self.packet("broken", INFO_BODY)
        with open(broken, encoding="utf-8") as fh:
            text = fh.read()
        with open(broken, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text.replace("## Summary", "## Summery"))
        d = json.loads(self.run_cli(pk, "list", "--open", "--json", "--brief"))
        self.assertEqual(3, d["count"])
        self.assertEqual([{"packet": "P-0001", "title": "to decide", "instance": "expert@main",
                           "kind": "verification", "pending": [1, 2]}], d["decide"])
        self.assertEqual(["P-0002"], d["acknowledge"])
        self.assertEqual("P-0003", d["problems"][0]["packet"])
        self.assertTrue(d["problems"][0]["problems"])
        full = json.loads(self.run_cli(pk, "list", "--open", "--json"))
        self.assertIn("_path", full[0])                                    # unchanged
        self.assertIn("P-0001", self.run_cli(pk, "list", "--pending"))
        self.assertNotIn("P-0002", self.run_cli(pk, "list", "--pending"))

    def test_packets_text_list_shows_the_newest(self):
        for i in range(55):
            self.packet("p%d" % i, DECISION_BODY)
        lines = self.run_cli(pk, "list").splitlines()
        self.assertIn("the newest 50 of 55", lines[0])
        self.assertTrue(lines[-2].startswith("P-0055"))
        self.assertEqual("55 packet(s)", lines[-1])
        self.assertEqual(56, len(self.run_cli(pk, "list", "--limit", "0").splitlines()))


if __name__ == "__main__":
    unittest.main()
