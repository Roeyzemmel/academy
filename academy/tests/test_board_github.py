"""Tests for board_codec.py, board_export.py, board_verify.py, board_import.py.

Run from the repo root:  py -m unittest discover academy/tests
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board import BoardCase  # noqa: E402

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402
import board_export as be  # noqa: E402
import board_import as bi  # noqa: E402
import board_verify as bv  # noqa: E402


def slurp(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def issue_of(e):
    return {k: e[k] for k in bv.KEYS}


class GithubBoardCase(BoardCase):
    def make(self):
        """Three tickets: an open one, a child, and a human-addressed decision."""
        p1 = self.new(title="Check lemma 4.2 with: colon")
        p2 = self.new(title="Child ticket", parent="T-0001",
                      ask="multi\nline ask", detail="Line one.\n\n  indented > arrow --> here")
        p3 = self.new(to="human", title="A decision", kind="decision", as_instance="author@main")
        bd.append_to_ticket(self.board, "T-0001", "first\nsecond line", as_instance="expert@main")
        return p1, p2, p3


class TestCodec(GithubBoardCase):
    def test_roundtrip_is_byte_identical(self):
        self.make()
        for path, meta, body in bd.iter_tickets(self.board):
            e = bc.encode(meta, body)
            m2, b2 = bc.decode(issue_of(e), e["comments"])
            with open(path, encoding="utf-8", newline="") as fh:
                self.assertEqual(fh.read(), bc.render(m2, b2), path)
            self.assertEqual([], bc.validate_issue(issue_of(e), e["comments"]))

    def test_labels_and_role(self):
        self.make()
        got = {m["id"]: bc.encode(m, b) for _p, m, b in bd.iter_tickets(self.board)}
        self.assertIn("to:expert@main", got["T-0001"]["labels"])
        self.assertIn("role:expert", got["T-0001"]["labels"])
        self.assertIn("role:human", got["T-0003"]["labels"])
        self.assertTrue(got["T-0003"]["assign_human"])
        self.assertFalse(got["T-0001"]["assign_human"])
        self.assertEqual("T-0001", got["T-0002"]["parent"])

    def test_dead_route_campaign_and_new_kinds_roundtrip(self):
        """Campaign design sections 4 and 9: the new fields ride the meta line."""
        self.new(title="Self item", kind="write", to="author@main", campaign="paper:thm:x")
        self.new(title="Dead route", campaign="paper:thm:x")
        bd.transition_ticket(self.board, "T-0002", "blocked", blocked_by="paper:lem:y",
                             reopen_if="a new invariant", reason="tried the induction; circular",
                             as_instance="expert@main", date="2026-09-30")
        for path, meta, body in bd.iter_tickets(self.board):
            e = bc.encode(meta, body)
            self.assertEqual([], e["waits_on"], "dead route is not a native dependency")
            m2, b2 = bc.decode(issue_of(e), e["comments"])
            with open(path, encoding="utf-8", newline="") as fh:
                self.assertEqual(fh.read(), bc.render(m2, b2), path)
            self.assertEqual([], bc.validate_issue(issue_of(e), e["comments"]))
        dead = [m for _p, m, _b in bd.iter_tickets(self.board) if m["id"] == "T-0002"][0]
        self.assertEqual("paper:lem:y", dead["blocked_by"])
        self.assertIn("status:blocked", bc.encode(dead, "")["labels"])
        self.assertIn("kind:write", bc.encode(
            [m for _p, m, _b in bd.iter_tickets(self.board) if m["id"] == "T-0001"][0], "")["labels"])

    def test_meta_line_never_closes_the_html_comment_early(self):
        self.make()
        for _p, m, b in bd.iter_tickets(self.board):
            first = bc.encode(m, b)["body"].split("\n")[0]
            self.assertEqual(1, first.count("-->"))

    def test_terminal_status_maps_to_closed_state(self):
        self.assertEqual(("closed", "completed"), bc.state_of("closed"))
        self.assertEqual(("closed", "not_planned"), bc.state_of("rejected"))
        self.assertEqual(("closed", "not_planned"), bc.state_of("cancelled"))
        self.assertEqual(("open", None), bc.state_of("blocked"))

    def test_role_mismatch_and_state_drift_are_reported(self):
        self.make()
        _p, m, b = next(iter(bd.iter_tickets(self.board)))
        e = bc.encode(m, b)
        iss = issue_of(e)
        iss["labels"] = [("role:author" if l.startswith("role:") else l) for l in iss["labels"]]
        self.assertTrue(any("role label" in p for p in bc.validate_issue(iss, e["comments"])))
        iss = issue_of(e)
        iss["state"] = "closed"
        self.assertTrue(any("issue is closed" in p for p in bc.validate_issue(iss, e["comments"])))

    def test_two_status_labels_are_refused(self):
        self.make()
        _p, m, b = next(iter(bd.iter_tickets(self.board)))
        e = bc.encode(m, b)
        iss = issue_of(e)
        iss["labels"] = iss["labels"] + ["status:accepted"]
        with self.assertRaises(bc.CodecError):
            bc.decode(iss, e["comments"])

    def test_number_must_match_title(self):
        self.make()
        _p, m, b = next(iter(bd.iter_tickets(self.board)))
        iss = issue_of(bc.encode(m, b))
        iss["number"] = 9
        with self.assertRaises(bc.CodecError):
            bc.decode(iss, [])

    def test_unmarked_comments_are_not_thread(self):
        self.make()
        _p, m, b = next(iter(bd.iter_tickets(self.board)))
        e = bc.encode(m, b)
        _m2, b2 = bc.decode(issue_of(e), e["comments"] + ["lgtm, thanks"])
        self.assertEqual(ac.thread_lines(b), ac.thread_lines(b2))

    def test_check_transition_follows_the_protocol_table(self):
        self.assertEqual([], bc.check_transition("open", "accepted", "receiver"))
        self.assertTrue(bc.check_transition("open", "accepted", "sender"))
        self.assertTrue(bc.check_transition("open", "closed", "receiver"))
        self.assertEqual([], bc.check_transition("open", "closed", "sender", human=True))


class TestExportVerifyImport(GithubBoardCase):
    def test_manifest_counts_and_gaps(self):
        self.make()
        m = be.build(self.board, "o/r")
        s = m["summary"]
        self.assertEqual(3, s["tickets"])
        self.assertEqual(0, s["placeholders"])
        self.assertEqual([1, 2, 3], [i["number"] for i in m["issues"]])
        self.assertEqual([{"type": "sub_issue", "parent": 1, "child": 2}], m["relations"])

    def test_gap_becomes_closed_placeholder(self):
        p = self.new()
        p2 = self.new()
        os.remove(p)                       # T-0001 disappears: a gap
        m = be.build(self.board)
        self.assertEqual([1], m["summary"]["gaps"])
        self.assertEqual("closed", m["issues"][0]["state"])
        self.assertEqual(["placeholder"], m["issues"][0]["labels"])
        self.assertEqual(1, m["summary"]["placeholders"])
        self.assertEqual([], bv.verify(self.board, bv.from_manifest(m)))
        self.assertTrue(os.path.exists(p2))

    def test_verify_clean_then_detects_edit(self):
        self.make()
        m = be.build(self.board)
        self.assertEqual([], bv.verify(self.board, bv.from_manifest(m)))
        m["issues"][0]["body"] = m["issues"][0]["body"] + "\nsneaky edit\n"
        drift = bv.verify(self.board, bv.from_manifest(m))
        self.assertTrue(any("differs" in d for d in drift))

    def test_verify_flags_missing_and_extra(self):
        self.make()
        m = be.build(self.board)
        recs = bv.from_manifest(m)[:2]
        self.assertTrue(any("no issue" in d for d in bv.verify(self.board, recs)))

    def test_import_rebuilds_the_board_files(self):
        self.make()
        m = be.build(self.board)
        before = {os.path.basename(p): slurp(p)
                  for p, _m, _b in bd.iter_tickets(self.board)}
        for p, _m, _b in list(bd.iter_tickets(self.board)):
            os.remove(p)
        bi.run(self.board, bv.from_manifest(m))
        after = {os.path.basename(p): slurp(p)
                 for p, _m, _b in bd.iter_tickets(self.board)}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
