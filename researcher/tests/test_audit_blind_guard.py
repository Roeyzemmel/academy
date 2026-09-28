"""audit_blind_guard: an experiment-reviewer run never reads another run's record."""

import os
import unittest

from _fixtures import Workspace, write, decision
import audit_blind_guard  # noqa: E402


def ev(tool, path=None, agent="researcher:experiment-reviewer", cwd=None):
    key = "file_path" if tool == "Read" else "path"
    e = {"hook_event_name": "PreToolUse", "tool_name": tool,
         "tool_input": {key: path} if path else {"pattern": "x"}}
    if cwd:
        e["cwd"] = cwd
    if agent:
        e["agent_type"] = agent
    return e


class AuditBlindGuardTests(Workspace):
    def setUp(self):
        super().setUp()
        self.rec = write(os.path.join(self.R, "audits", "lab-ew", "2026-09-28-A.md"), "x\n")
        self.old = write(os.path.join(self.O, "audits", "lab-ew", "2026-09-28-A.md"), "x\n")
        self.script = write(os.path.join(self.L, "experiments", "ew.py"), "x\n")

    def d(self, e):
        return (audit_blind_guard.decide(e) or (None,))[0]

    def test_reading_a_record_is_denied(self):
        for p in (self.rec, self.old):
            self.assertEqual(self.d(ev("Read", p)), "deny", p)
        self.assertEqual(self.d(ev("Read", self.rec, agent="experiment-reviewer")), "deny")

    def test_search_into_or_over_audits_is_denied(self):
        self.assertEqual(self.d(ev("Grep", os.path.join(self.R, "audits"))), "deny")
        self.assertEqual(self.d(ev("Glob", self.R)), "deny")
        self.assertEqual(self.d(ev("Grep", cwd=self.R)), "deny")

    def test_the_evidence_is_readable(self):
        self.assertIsNone(self.d(ev("Read", self.script)))
        self.assertIsNone(self.d(ev("Grep", os.path.join(self.L, "experiments"))))
        self.assertIsNone(self.d(ev("Read", os.path.join(self.R, "objects", "c.md"))))

    def test_other_agents_are_silent(self):
        for agent in (None, "researcher:claim-keeper", "expert:review-chair"):
            self.assertIsNone(self.d(ev("Read", self.rec, agent=agent)), agent)

    def test_through_the_hook_process(self):
        rc, out = self.run_hook("audit_blind_guard.py", ev("Read", self.rec))
        self.assertEqual((rc, decision(out)), (0, "deny"))
        rc, out = self.run_hook("audit_blind_guard.py", ev("Read", self.rec, agent=None))
        self.assertEqual((rc, out), (0, None))


if __name__ == "__main__":
    unittest.main()
