"""The verify workflow (workflows/verify.js) and its launch guard (2026-10-31).

The workflow holds conclude.md's sequencing in code. These tests run the script under
node with a fake ``agent()``, so the gate is checked without any model: A GAP launches
no B; A CONFIRMED with launch_b launches B with A's brief byte for byte (run B); a
moved statement hash stops B; a lost run is not relaunched; an unlanded run is
relaunched once; a reword pass runs R alone. Skipped where node is not installed.
The guard refuses a hand-launched rigor-reviewer unless the human opted out.
"""

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
SCRIPT = os.path.join(PLUGIN, "workflows", "verify.js")
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import review_launch_guard as guard  # noqa: E402

NODE = shutil.which("node")

# The harness provides agent/phase/log/args; the fake answers by stage and run label.
HARNESS = r"""
const fs = require('fs')
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^export const meta/m, 'const meta')
const plan = JSON.parse(process.argv[3])
const calls = []
async function agent(prompt, opts) {
  calls.push({ label: opts.label, agentType: opts.agentType, prompt })
  const ans = plan[opts.label]
  if (ans === undefined) throw new Error('unplanned agent ' + opts.label)
  return ans
}
const body = new Function('args', 'agent', 'phase', 'log', 'return (async () => {' + src + '})()')
body(plan.__args, agent, () => {}, () => {}).then(
  r => console.log(JSON.stringify({ result: r, calls })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""

PREP = {"ok": True, "stop_reason": "", "pass": "2026-10-31-T-0001",
        "pass_dir": "/lib/reviews/paper/x/2026-10-31-T-0001", "statement_hash": "abcdef12",
        "location": "sections/a.tex:lem:x", "bundle": "", "ticket": "T-0001"}


def tab(verdict, outcome, launch_b=False, hash_now="abcdef12", landed=True, run="A"):
    return {"landed": landed, "run_file": run + ".md", "verdict": verdict, "outcome": outcome,
            "launch_b": launch_b, "hash_now": hash_now}


DONE = {"outcome": "x", "proposed_status": "none", "record": "decision.md", "packet": "P-1",
        "tickets": [], "run_files": ["A.md"], "report": "r"}


@unittest.skipUnless(NODE, "node is not installed")
class GateTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        plan = dict(plan, __args=dict({"claim": "paper:lem:x", "ticket": "T-0001"}, **args))
        d = tempfile.mkdtemp(prefix="acad-wf-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        return out, [c["label"] for c in out["calls"]], out["calls"]

    def test_a_gap_launches_no_b(self):
        out, labels, _ = self.run_wf({"prepare": PREP, "run A": "report",
                                      "table A": tab("GAP", "single-negative"),
                                      "conclude": DONE})
        self.assertEqual(labels, ["prepare", "run A", "table A", "conclude"])
        self.assertIn("run B skipped by design", " ".join(out["result"]["notes"]))

    def test_a_confirmed_launches_b_with_the_identical_brief(self):
        done = dict(DONE, run_files=["A.md", "B.md", "decision.md"])
        out, labels, calls = self.run_wf({
            "prepare": PREP, "run A": "report", "table A": tab("CONFIRMED", "awaiting-b", True),
            "run B": "report", "table B": tab("CONFIRMED", "confirmed", run="B"),
            "conclude": done})
        self.assertEqual(labels, ["prepare", "run A", "table A", "run B", "table B", "conclude"])
        a = next(c for c in calls if c["label"] == "run A")
        b = next(c for c in calls if c["label"] == "run B")
        self.assertEqual(a["agentType"], "expert:rigor-reviewer")
        self.assertEqual(a["prompt"].replace("run: A", "run: B"), b["prompt"])
        self.assertNotIn("CONFIRMED", b["prompt"])        # B is told nothing of A
        self.assertEqual(out["result"]["anomalies"], [])

    def test_a_moved_statement_stops_b(self):
        out, labels, _ = self.run_wf({"prepare": PREP, "run A": "r",
                                      "table A": tab("CONFIRMED", "awaiting-b", True, "ffff0000"),
                                      "conclude": DONE})
        self.assertNotIn("run B", labels)
        self.assertIn("statement moved", " ".join(out["result"]["notes"]))

    def test_a_lost_run_is_not_relaunched_and_an_unlanded_one_is(self):
        _o, labels, _ = self.run_wf({"prepare": PREP, "run A": None, "conclude": DONE})
        self.assertEqual(labels, ["prepare", "run A", "conclude"])
        plan = {"prepare": PREP, "run A": "r", "table A": tab("GAP", "x", landed=False),
                "run A (relaunch)": "r", "conclude": DONE}
        # the relaunch is checked by the same table label; the fake gives one answer per
        # label, so an unlanded A twice ends the review as lost after two attempts
        out, labels, _ = self.run_wf(plan)
        self.assertEqual(labels, ["prepare", "run A", "table A", "run A (relaunch)", "table A",
                                  "conclude"])
        self.assertIn("did not land", " ".join(out["result"]["notes"]))

    def test_a_reword_pass_runs_r_alone(self):
        prep = dict(PREP, pass_="", bundle="/s/bundle.md")
        prep["pass"] = "2026-10-31-reword"
        out, labels, calls = self.run_wf({
            "prepare": prep, "run R": "r", "table R": tab("CONFIRMED", "confirmed", True, run="R"),
            "conclude": dict(DONE, run_files=["R.md"])}, mode="reword", base_pass="2026-10-01")
        self.assertEqual(labels, ["prepare", "run R", "table R", "conclude"])
        r = next(c for c in calls if c["label"] == "run R")
        self.assertIn("read the bundle /s/bundle.md first", r["prompt"])
        self.assertIn("run: R", r["prompt"])

    def test_an_unknown_run_file_is_an_anomaly(self):
        out, _l, _c = self.run_wf({"prepare": PREP, "run A": "r",
                                   "table A": tab("GAP", "single-negative"),
                                   "conclude": dict(DONE, run_files=["A.md", "B.md"])})
        self.assertEqual(out["result"]["anomalies"], ["B.md"])

    def test_a_malformed_claim_or_pass_is_refused(self):
        out, labels, _ = self.run_wf({}, claim="GEO-3")
        self.assertIn("namespaced registry id", out["error"])
        out, labels, _ = self.run_wf({"prepare": dict(PREP, statement_hash="not in brief")})
        self.assertIn("malformed", out["error"])
        self.assertEqual(labels, ["prepare"])

    def test_not_started_stops_before_any_run(self):
        out, labels, _ = self.run_wf({"prepare": dict(PREP, ok=False, stop_reason="budget")})
        self.assertEqual(labels, ["prepare"])
        self.assertEqual(out["result"]["outcome"], "not-started")


class LaunchGuardTests(unittest.TestCase):
    def ev(self, sub, tool="Agent"):
        return {"hook_event_name": "PreToolUse", "tool_name": tool,
                "tool_input": {"subagent_type": sub, "prompt": "Review x"}}

    def test_a_hand_launched_reviewer_is_denied(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ACADEMY_ALLOW_MANUAL_REVIEW", None)
            for sub in ("expert:rigor-reviewer", "rigor-reviewer"):
                for tool in ("Agent", "Task"):
                    out = guard.decide(self.ev(sub, tool))
                    self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
                    self.assertIn("workflows/verify.js",
                                  out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_other_agents_and_the_opt_out_pass(self):
        for sub in ("expert:review-chair", "researcher:experiment-reviewer", ""):
            self.assertIsNone(guard.decide(self.ev(sub)))
        self.assertIsNone(guard.decide({"tool_name": "Read", "tool_input": {}}))
        with mock.patch.dict(os.environ, {"ACADEMY_ALLOW_MANUAL_REVIEW": "1"}):
            self.assertIsNone(guard.decide(self.ev("expert:rigor-reviewer")))

    def test_relays_are_launched_only_by_the_inbox_workflow(self):
        os.environ.pop("ACADEMY_ALLOW_MANUAL_REVIEW", None)
        for sub in ('expert:research-intake', 'paper-liaison'):
            out = guard.decide(self.ev(sub))
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("workflows/inbox.js", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_the_hook_is_registered(self):
        with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]["PreToolUse"]
        self.assertTrue(any(h.get("matcher") == "Agent|Task" and "review_launch_guard.py"
                            in h["hooks"][0]["command"] for h in hooks))


if __name__ == "__main__":
    unittest.main()
