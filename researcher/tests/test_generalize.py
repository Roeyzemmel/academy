"""generalize.py: the reviewed-report gate, the proposal rules, objects, tickets, packet."""

import json
import os
import unittest

from _fixtures import Workspace, write
import _academy as ac  # noqa: E402
import _researcher as rs  # noqa: E402
import generalize  # noqa: E402
import land_review  # noqa: E402
from test_reviews import report  # noqa: E402

REPORT = """---
packet: P-0007
title: EW check report
instance: scientist@t
kind: experiment-report
by: scientist@t/experimenter
ticket:
agenda:
subject: [lab:ew-check]
status_before: open
status_proposed: supported
state: open
created: 2026-09-28
decided:
---

## Summary

No counterexample over the class.

## Produced

- `file:scientist@t/results/x.json`

## Established vs assumed

- **Established:** lab:ew-check (proposed supported).

## Evidence

- commit abc123

## Conclusion

Supports: every member of the class up to size 12 has the property.
It does not establish the property for larger members.

## Decisions needed

None.

## Machine notes

None.

## Decision

"""


def proposal(i=1, **over):
    p = {"id": "s9:GEN-%d" % i, "title": "Generalization %d" % i,
         "statement": "Every member of the wider class has the property.",
         "kind": "conjecture", "status": "conjectured", "bears_on": ["lab:ew-check"],
         "falsifier": "the smallest member outside the old class",
         "pattern": "wider class", "rationale": "the data show no dependence on size"}
    p.update(over)
    return p


class GeneralizeTests(Workspace):
    def setUp(self):
        super().setUp()
        write(os.path.join(self.B, "packets", "scientist@t", "P-0007-ew-check-report.md"),
              REPORT)
        self.st = generalize.settings(self.R)

    def clear_review(self):
        for run in ("A", "B"):
            land_review.land({"agent_type": "experiment-reviewer", "cwd": self.R,
                              "agent_id": run, "last_assistant_message": report(run=run)})

    def test_source_requires_a_cleared_review(self):
        s = generalize.source(self.R, "P-0007")
        self.assertFalse(s["reviewed"])
        self.assertIn("up to size 12", s["conclusion"])
        rc, _, err = self.run_script("generalize.py", "source", "P-0007")
        self.assertEqual(rc, 2)
        self.clear_review()
        s = generalize.source(self.R, "lab:ew-check")
        self.assertEqual((s["packet"], s["reviewed"], s["lab_claims"]),
                         ("P-0007", True, ["lab:ew-check"]))

    def test_settings(self):
        self.assertEqual((self.st["instance"], self.st["ns"], self.st["lab"], self.st["max"],
                          self.st["ceiling"]),
                         ("researcher@t", "s9", "scientist@t", 3, "conjectured"))

    def test_validation_rules(self):
        ok = [proposal(1), proposal(2)]
        self.assertEqual(generalize.validate(ok, "lab:ew-check", self.st), [])
        bad = {
            "status": proposal(status="proved"),
            "bears_on": proposal(bears_on=[]),
            "falsifier": proposal(falsifier=""),
            "namespace": proposal(id="s1:GEN-1"),
            "kind": proposal(kind="claim"),
            "pattern": proposal(pattern="vibes"),
        }
        for name, p in bad.items():
            with self.subTest(rule=name):
                self.assertTrue(generalize.validate([p], "lab:ew-check", self.st))
        four = [proposal(i) for i in range(1, 5)]
        self.assertTrue(any("at most 3" in x
                            for x in generalize.validate(four, "lab:ew-check", self.st)))
        dup = [proposal(1), proposal(1)]
        self.assertTrue(any("duplicate" in x
                            for x in generalize.validate(dup, "lab:ew-check", self.st)))

    def test_create_objects(self):
        paths = generalize.create_objects(self.R, [proposal(1)], "lab:ew-check", apply=True)
        text = rs.read_text(paths[0])
        self.assertEqual(rs.frontmatter_field(text, "status")[1], "conjectured")
        self.assertEqual(rs.frontmatter_field(text, "bears_on")[1], "[lab:ew-check]")
        self.assertIn("## Falsifier", text)

    def test_ticket_commands_name_the_agent(self):
        cmds = generalize.ticket_commands([proposal(1)], "lab:x", "T-0001",
                                          "scientist@t", "researcher@t")
        self.assertIn("--agent", cmds[0])
        self.assertEqual(cmds[0][cmds[0].index("--agent") + 1], "main")

    def test_ticket_commands(self):
        cmds = generalize.ticket_commands([proposal(1)], "lab:ew-check", "T-0004",
                                          "scientist@t", "researcher@t")
        c = cmds[0]
        self.assertEqual(c[c.index("--kind") + 1], "test")
        self.assertEqual(c[c.index("--refs") + 1], "s9:GEN-1,lab:ew-check")
        self.assertEqual(c[c.index("--parent") + 1], "T-0004")
        self.assertEqual(c[c.index("--as") + 1], "researcher@t")
        self.assertIn("falsifier", c[c.index("--ask") + 1])

    def test_packet_body_is_a_valid_packet(self):
        body = generalize.packet_body([proposal(1), proposal(2)], "lab:ew-check", "P-0007")
        meta = {"packet": "P-0009", "title": "Generalizations", "instance": "researcher@t",
                "kind": "generalization", "by": "researcher@t", "subject": ["s9:GEN-1"],
                "state": "open", "created": "2026-09-28"}
        self.assertEqual(ac.validate_packet(meta, body), [])

    def test_cli_validate_and_dry_run_tickets(self):
        f = write(os.path.join(self.tmp, "p.json"), json.dumps([proposal(1)]))
        rc, out, _ = self.run_script("generalize.py", "validate", f, "--lab-claim", "lab:ew-check")
        self.assertEqual((rc, out.strip()), (0, "ok"))
        rc, out, err = self.run_script("generalize.py", "tickets", f, "--lab-claim",
                                       "lab:ew-check", "--parent", "T-0004")
        self.assertEqual(rc, 0, err)
        self.assertIn("board.py", out)
        self.assertIn("scientist@t", out)


if __name__ == "__main__":
    unittest.main()
