"""The referee and domain workflows (workflows/referee.js, domain.js), 2026-10-31. Under node
with a fake agent(); skipped without node. The guard refuses a hand-launched referee."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
WF = os.path.join(PLUGIN, "workflows")
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
import review_launch_guard as guard  # noqa: E402

NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs')
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^export const meta/m, 'const meta')
const plan = JSON.parse(process.argv[3])
const calls = []
async function agent(prompt, opts) {
  calls.push({ label: opts.label, agentType: opts.agentType, prompt })
  const q = plan[opts.label]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned agent ' + opts.label)
  return q.shift()
}
const body = new Function('args', 'agent', 'phase', 'log', 'return (async () => {' + src + '})()')
body(plan.__args, agent, () => {}, () => {}).then(
  r => console.log(JSON.stringify({ result: r, calls })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""


def run(name, plan, args):
    d = tempfile.mkdtemp(prefix="acad-rd-")
    try:
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, os.path.join(WF, name), json.dumps(dict(plan, __args=args))],
                           capture_output=True, text=True, timeout=60)
    finally:
        shutil.rmtree(d, True)
    out = json.loads(p.stdout.strip().splitlines()[-1])
    return out.get("result"), [c["label"] for c in out["calls"]], out["calls"], out.get("error")


MOVE = {"ok": True, "status": "delivered", "detail": ""}
PDF = {"ok": True, "stop_reason": "", "pdf": "/w/BI/.build/main.pdf", "built": "2026-10-31", "rebuilt": True,
       "vision": "/w/BI/Drafts/vision.md", "last_report": "reviews/referee/author@t/2026-10-01.md",
       "last_date": "2026-10-01", "changed_since": "sections/markings.tex, sections/billiards.tex"}


@unittest.skipUnless(NODE, "node is not installed")
class RefereeTests(unittest.TestCase):
    def test_the_brief_is_facts_only_and_the_packet_is_found(self):
        res, labels, calls, err = run("referee.js", {
            "start": [{"ok": True, "detail": "", "instance": "author@t", "acted_as": "expert@t"}],
            "pdf": [PDF], "referee": ["report ... REFEREE block"],
            "find packet": [{"packet": "P-0500", "blocking": 2, "copy": "reviews/referee/author@t/2026-10-31.md"}],
            "deliver": [MOVE]}, {"ticket": "T-0700"})
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["start", "pdf", "referee", "find packet", "deliver"])
        brief = next(c for c in calls if c["label"] == "referee")
        self.assertEqual(brief["agentType"], "expert:referee")
        self.assertEqual(brief["prompt"],
                         "Referee author@t cold. The PDF is /w/BI/.build/main.pdf, built 2026-10-31. The last report is "
                         "2026-10-01; changed since: sections/markings.tex, sections/billiards.tex. Do not read the agenda or "
                         "tickets before your cold reading. After it, check the paper against its vision, "
                         "/w/BI/Drafts/vision.md. Ticket: T-0700.")
        self.assertIn("referee packet P-0500; 2 blocking", next(c for c in calls if c["label"] == "deliver")["prompt"])
        self.assertIn("rebuilt", " ".join(res["notes"]))

    def test_a_held_build_lock_stops_before_the_referee(self):
        res, labels, _, err = run("referee.js", {"pdf": [dict(PDF, ok=False, stop_reason="LaTeX Workshop is building")]},
                                  {"instance": "author@t"})
        self.assertEqual(labels, ["pdf"])
        self.assertIn("LaTeX Workshop", res["reason"])

    def test_focus_only_when_given_and_unlanded_reported(self):
        res, labels, calls, err = run("referee.js", {"pdf": [dict(PDF, last_report="none: reviews/referee/author@t/ does not exist", vision="")], "referee": ["r"],
                                                     "find packet": [{"packet": "", "blocking": 0, "copy": ""}]},
                                      {"instance": "author@t", "focus": "section 4"})
        p = next(c for c in calls if c["label"] == "referee")["prompt"]
        self.assertIn("look hardest at: section 4", p)
        self.assertIn("There is no earlier report", p)
        self.assertIn("vision, there is none", p)
        self.assertEqual(res["outcome"], "unlanded")


START = {"ok": True, "detail": "", "pack": "translation-surfaces", "changes": ["add the Veech dichotomy entry"],
         "acted_as": "expert@t", "academy_root": "/a", "diff_before": []}
EDIT = {"files": ["theorems/dynamics.md"], "changelog": "- 2026-10-31 T-0800: theorems/dynamics.md Veech dichotomy",
        "card": "cards/V89/thm-1.md", "unverified": False, "shared": False, "clash": ""}


@unittest.skipUnless(NODE, "node is not installed")
class DomainTests(unittest.TestCase):
    def test_a_clean_change_is_delivered(self):
        res, labels, calls, err = run("domain.js", {
            "start": [START], "librarian": [EDIT],
            "diff": [{"changed": ["theorems/dynamics.md", "CHANGELOG.md"], "changelog_last": EDIT["changelog"]}],
            "close": [MOVE]}, {"ticket": "T-0800"})
        self.assertIsNone(err, err)
        self.assertEqual(res["anomalies"], [])
        self.assertIn("deliver: deliver: true", next(c for c in calls if c["label"] == "close")["prompt"])
        self.assertNotIn("packet", labels)

    def test_an_extra_file_parks_the_ticket_on_the_human(self):
        res, labels, calls, err = run("domain.js", {
            "start": [START], "librarian": [EDIT],
            "diff": [{"changed": ["theorems/dynamics.md", "notation.md", "CHANGELOG.md"], "changelog_last": EDIT["changelog"]}],
            "close": [MOVE]}, {"ticket": "T-0800"})
        self.assertIn("notation.md", " ".join(res["anomalies"]))
        self.assertIn("block-human", next(c for c in calls if c["label"] == "close")["prompt"])

    def test_two_changes_are_split_and_a_shared_change_gets_a_packet(self):
        res, labels, calls, err = run("domain.js", {
            "start": [dict(START, changes=["a", "b"], diff_before=["domains/translation-surfaces/examples.md"])],
            "split note": [MOVE], "librarian": [dict(EDIT, shared=True, clash="the paper writes Λ for the lattice")],
            "diff": [{"changed": ["examples.md", "theorems/dynamics.md", "CHANGELOG.md"], "changelog_last": EDIT["changelog"]}],
            "packet": [{"packet": "P-0600", "error": ""}], "close": [MOVE]}, {"ticket": "T-0800"})
        self.assertIsNone(err, err)
        self.assertIn("split note", labels)
        self.assertEqual(res["anomalies"], [])                    # examples.md was dirty before the run
        self.assertIn("clash", next(c for c in calls if c["label"] == "packet")["prompt"])
        self.assertEqual(res["packet"], "P-0600")

    def test_no_ticket_is_refused(self):
        res, labels, _, err = run("domain.js", {}, {})
        self.assertIn("args.ticket is required", err)


class RefereeGuardTests(unittest.TestCase):
    def test_a_hand_launched_referee_is_denied(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ACADEMY_ALLOW_MANUAL_REVIEW", None)
            os.environ.pop("EVAL_ACADEMY_ALLOW_LAUNCH", None)
            out = guard.decide({"tool_name": "Agent", "tool_input": {"subagent_type": "expert:referee"}})
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("workflows/referee.js", out["hookSpecificOutput"]["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
