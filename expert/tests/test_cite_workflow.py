"""The cite workflow (workflows/cite.js), 2026-10-31: one librarian run, the card checked by
cards.py validate with one fix, the packet and the delivery only after the check, a
mismatch and an unreachable source reported. Under node with a fake agent()."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "workflows", "cite.js")
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

ASK = {"ok": True, "detail": "", "ref": "10.1000/xyz", "pinpoint": "Thm 2", "relying": "paper:lem:x",
       "bib": "author@t:references.bib", "instance": "expert@t"}


def card(verdict="match", reachable=True):
    return {"key": "SW10", "pinpoint": "Thm 2", "card": "cards/SW10/thm-2.md", "verdict": verdict,
            "cached": True, "reachable": reachable, "bib_changed": True, "note": ""}


OK = {"ok": True, "errors": []}
BAD = {"ok": False, "errors": ["quote not found in SW10.txt"]}
MOVE = {"ok": True, "status": "delivered", "detail": ""}


@unittest.skipUnless(NODE, "node is not installed")
class CiteTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        d = tempfile.mkdtemp(prefix="acad-ct-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(dict(plan, __args=args))], capture_output=True, text=True, timeout=60)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], [c["label"] for c in out["calls"]], out["calls"]

    def test_the_happy_path_lands_after_validation(self):
        res, labels, calls = self.run_wf({"start": [ASK], "librarian": [card()], "validate": [OK],
                                          "packet": [{"packet": "P-0300", "error": ""}], "deliver": [MOVE]}, ticket="T-0904")
        self.assertEqual(labels, ["start", "librarian", "validate", "packet", "deliver"])
        lib = next(c for c in calls if c["label"] == "librarian")
        self.assertEqual(lib["agentType"], "expert:librarian")
        self.assertIn("10.1000/xyz", lib["prompt"])
        self.assertIn("Never write an entry from memory", lib["prompt"])
        self.assertIn("SW10, Thm 2, verdict match", next(c for c in calls if c["label"] == "deliver")["prompt"])
        self.assertTrue(res["validated"])

    def test_one_fix_then_a_noted_failure(self):
        res, labels, _ = self.run_wf({"start": [ASK], "librarian": [card()], "validate": [BAD],
                                      "librarian (fix)": [card()], "validate again": [BAD],
                                      "packet": [{"packet": "P-0301", "error": ""}], "deliver": [MOVE]}, ticket="T-0904")
        self.assertEqual(labels.count("librarian (fix)"), 1)
        self.assertFalse(res["validated"])
        self.assertIn("still fails validation", " ".join(res["notes"]))

    def test_mismatch_first_and_unreachable_noted_without_a_ticket(self):
        res, labels, _ = self.run_wf({"librarian": [card("the theorem needs compactness, the paper omits it", False)],
                                      "validate": [OK], "packet": [{"packet": "P-0302", "error": ""}]}, ref="SW10")
        self.assertEqual(labels, ["librarian", "validate", "packet"])
        self.assertTrue(res["notes"][0].startswith("MISMATCH"))
        self.assertIn("UNREACHABLE", " ".join(res["notes"]))

    def test_a_lost_librarian_stops(self):
        res, labels, _ = self.run_wf({"start": [ASK], "librarian": [None]}, ticket="T-0904")
        self.assertEqual(res["outcome"], "lost")
        self.assertNotIn("packet", labels)


if __name__ == "__main__":
    unittest.main()
