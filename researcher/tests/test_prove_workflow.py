"""The prove workflow (workflows/prove.js), 2026-10-31: no attempt without a falsifier, an
attack-only run first when none exists, the outcome read from the attempt file, a verify
ticket only for a complete attempt (filed by the prover, checked), nothing above sketch.
Under node with a fake agent(); skipped without node."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "workflows", "prove.js")
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


def state(**kw):
    s = {"ok": True, "stop_reason": "", "status": "open", "unsettled_inputs": [], "attempts": [],
         "falsified": True, "falsifier_evidence": "explore D-1", "attack_exists": True}
    s.update(kw)
    return s


MOVE = {"ok": True, "detail": ""}


@unittest.skipUnless(NODE, "node is not installed")
class ProveTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        a = {"claim": "flat:GEO-3", "home": "/h/nb", "ticket": "T-0010"}
        a.update(args)
        plan = dict(plan, __args=a)
        d = tempfile.mkdtemp(prefix="acad-pv-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], [c["label"] for c in out["calls"]], out["calls"]

    def test_no_falsifier_means_explore_first(self):
        res, labels, _ = self.run_wf({"state": [state(falsified=False)]})
        self.assertTrue(res["needs_explore"])
        self.assertEqual(labels, ["state"])

    def test_a_complete_attempt_files_a_checked_verify_ticket(self):
        res, labels, calls = self.run_wf({
            "state": [state(attack_exists=False)], "attack": ["no counterexample"],
            "attempt path": [{"path": "proofs/GEO-3/attempt-2.md"}], "attempt": ["done, complete"],
            "outcome": [{"exists": True, "outcome": "complete", "gaps": [], "objects": []}],
            "file verify": [{"ticket": "T-0020", "proposal": "T-0021", "refusal": ""}],
            "check verify": [{"found": True, "to": "expert@t", "kind": "verify", "refs": ["flat:GEO-3", "file:x"]}],
            "close": [MOVE]})
        self.assertEqual(labels, ["state", "attack", "attempt path", "attempt", "outcome", "file verify",
                                  "check verify", "close"])
        self.assertEqual(res["outcome"], "verify-filed")
        f = next(c for c in calls if c["label"] == "file verify")
        self.assertEqual(f["agentType"], "researcher:prover")
        self.assertIn("propose sketch", f["prompt"])          # the claim was open
        self.assertIn("T-0020", next(c for c in calls if c["label"] == "close")["prompt"])

    def test_the_outcome_comes_from_the_file_not_the_summary(self):
        res, labels, _ = self.run_wf({
            "state": [state()], "attempt path": [{"path": "p.md"}],
            "attempt": ["COMPLETE! the proof is done"],                      # the summary claims success
            "outcome": [{"exists": True, "outcome": "failed", "gaps": ["step 3"], "objects": []}],
            "close": [MOVE]})
        self.assertEqual(res["outcome"], "attempt-incomplete")
        self.assertNotIn("file verify", labels)

    def test_already_proved_and_a_bad_verify_ticket(self):
        res, labels, _ = self.run_wf({"state": [state(status="proved")], "close": [MOVE]})
        self.assertEqual(res["outcome"], "already-proved")
        self.assertNotIn("attempt", labels)
        res, labels, _ = self.run_wf({
            "state": [state(status="sketch")], "attempt path": [{"path": "p.md"}], "attempt": ["x"],
            "outcome": [{"exists": True, "outcome": "complete", "gaps": [], "objects": []}],
            "file verify": [{"ticket": "T-0020", "proposal": "", "refusal": ""}],
            "check verify": [{"found": True, "to": "author@t", "kind": "write", "refs": []}],
            "close": [MOVE]})
        self.assertIn("ANOMALY", " ".join(res["notes"]))


if __name__ == "__main__":
    unittest.main()
