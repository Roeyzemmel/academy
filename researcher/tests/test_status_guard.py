"""status_guard: only claim-keeper (or the human) changes a registry record's status line."""

import os
import unittest

from _fixtures import Workspace, write, record, decision
import status_guard  # noqa: E402


def edit(path, old, new, agent=None, tool="Edit", **extra):
    ev = {"hook_event_name": "PreToolUse", "tool_name": tool,
          "tool_input": {"file_path": path, "old_string": old, "new_string": new}}
    ev["tool_input"].update(extra)
    if agent:
        ev["agent_type"] = agent
    return ev


def write_ev(path, content, agent=None):
    ev = {"hook_event_name": "PreToolUse", "tool_name": "Write",
          "tool_input": {"file_path": path, "content": content}}
    if agent:
        ev["agent_type"] = agent
    return ev


class StatusGuardTests(Workspace):
    def setUp(self):
        super().setUp()
        self.rec = write(os.path.join(self.R, "objects", "claim", "C-1.md"), record("sketch"))

    def d(self, ev):
        return status_guard.decide(ev)[0]

    def test_prover_changing_status_is_denied(self):
        ev = edit(self.rec, "status: sketch", "status: proved", "researcher:prover")
        self.assertEqual(self.d(ev), "deny")

    def test_denied_through_the_hook_process(self):
        ev = edit(self.rec, "status: sketch", "status: proved", "researcher:prover")
        rc, out = self.run_hook("status_guard.py", ev)
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), "deny")
        self.assertIn("claims_propose_status", out["hookSpecificOutput"]
                      ["permissionDecisionReason"])

    def test_bare_and_other_plugin_names_are_denied(self):
        for agent in ("prover", "author:math-editor", "lead-researcher"):
            with self.subTest(agent=agent):
                ev = edit(self.rec, "status: sketch", "status: open", agent)
                self.assertEqual(self.d(ev), "deny")

    def test_claim_keeper_and_human_pass(self):
        for agent in ("researcher:claim-keeper", "claim-keeper", None):
            with self.subTest(agent=agent):
                ev = edit(self.rec, "status: sketch", "status: proved", agent)
                self.assertIsNone(self.d(ev))

    def test_edit_elsewhere_in_the_record_passes(self):
        ev = edit(self.rec, "## Remarks\n", "## Remarks\n\nMore.\n", "researcher:prover")
        self.assertIsNone(self.d(ev))

    def test_status_word_in_history_is_not_the_field(self):
        ev = edit(self.rec, "| status: created", "| status: changed", "researcher:prover")
        self.assertIsNone(self.d(ev))

    def test_removing_the_status_line_is_denied(self):
        ev = edit(self.rec, "status: sketch\n", "", "researcher:prover")
        self.assertEqual(self.d(ev), "deny")

    def test_multiedit_is_simulated(self):
        ev = {"tool_name": "MultiEdit", "agent_type": "researcher:prover",
              "tool_input": {"file_path": self.rec, "edits": [
                  {"old_string": "## Remarks", "new_string": "## Remarks!"},
                  {"old_string": "status: sketch", "new_string": "status: proved"}]}}
        self.assertEqual(self.d(ev), "deny")

    def test_write_over_a_record_changing_status_is_denied(self):
        ev = write_ev(self.rec, record("proved"), "researcher:prover")
        self.assertEqual(self.d(ev), "deny")

    def test_write_keeping_status_passes(self):
        ev = write_ev(self.rec, record("sketch", extra="tags: [x]\n"), "researcher:prover")
        self.assertIsNone(self.d(ev))

    def test_new_record_unsettled_passes_settled_denied(self):
        new = os.path.join(self.R, "objects", "conjecture", "G-1.md")
        self.assertIsNone(self.d(write_ev(new, record("conjectured"), "researcher:prover")))
        self.assertIsNone(self.d(write_ev(new, record(None, kind="definition"),
                                          "researcher:prover")))
        self.assertEqual(self.d(write_ev(new, record("proved"), "researcher:prover")), "deny")

    def test_non_records_are_silent(self):
        other = write(os.path.join(self.R, "journal", "2026-09-28.md"), record("sketch"))
        index = write(os.path.join(self.R, "objects", "INDEX.md"), record("sketch"))
        outside = write(os.path.join(self.tmp, "elsewhere", "x.md"), record("sketch"))
        for p in (other, index, outside):
            with self.subTest(path=p):
                ev = edit(p, "status: sketch", "status: proved", "researcher:prover")
                self.assertIsNone(self.d(ev))

    def test_legacy_home_without_config_is_guarded(self):
        lab = write(os.path.join(self.L, "claims", "lab", "ew.md"), record("open", "ew"))
        ev = edit(lab, "status: open", "status: supported", "scientist:experimenter")
        self.assertEqual(self.d(ev), "deny")
        old = write(os.path.join(self.O, "claims", "Q-1.md"),
                    record("Not settled", "Q-1"))
        ev = edit(old, "status: Not settled", "status: Proved", "prover")
        self.assertEqual(self.d(ev), "deny")

    def test_legacy_status_keeper_passes_only_before_switch_over(self):
        # Slope1's own status-keeper keeps working until phase 6 retires it
        old = write(os.path.join(self.O, "claims", "Q-2.md"),
                    record("Not settled", "Q-2"))
        ev = edit(old, "status: Not settled", "status: Proved", "status-keeper")
        self.assertIsNone(self.d(ev))
        # a switched-over home accepts only its configured keeper
        ev = edit(self.rec, "status: sketch", "status: proved", "status-keeper")
        self.assertEqual(self.d(ev), "deny")

    def test_crlf_record(self):
        p = os.path.join(self.R, "objects", "claim", "C-2.md")
        with open(p, "w", encoding="utf-8", newline="\r\n") as fh:
            fh.write(record("open", "C-2"))
        ev = edit(p, "status: open", "status: proved", "researcher:prover")
        self.assertEqual(self.d(ev), "deny")

    def test_unsimulable_edit_is_silent(self):
        ev = edit(self.rec, "no such text", "status: proved", "researcher:prover")
        self.assertIsNone(self.d(ev))

    def test_bad_event_is_silent(self):
        rc, out = self.run_hook("status_guard.py", {"tool_name": "Edit"})
        self.assertEqual((rc, out), (0, None))


if __name__ == "__main__":
    unittest.main()
