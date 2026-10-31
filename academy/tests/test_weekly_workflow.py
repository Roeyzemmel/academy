"""The weekly usage and settle workflow (academy/workflows/weekly.js), 2026-10-31.

Under node with a fake ``agent()``: the script drops a grader's downgrade and a
downgrade that is not a lower tier, keeps at most three decisions with regressions
first, writes exactly those, and settles only after a filed packet (a failed filing or a
malformed id settles nothing; no instance files nothing). Skipped where node is absent.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "workflows", "weekly.js")
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


def prop(kind, q, **kw):
    p = {"kind": kind, "question": q, "options": ["(a) yes", "(b) no"], "recommendation": "(a)",
         "evidence": "e"}
    p.update(kw)
    return p


def data(proposals=()):
    return {"ok": True, "error": "", "start": "2026-10-24", "end": "2026-10-31", "summary": "s",
            "open_classes": 3, "regressions": [], "limit_failures": 0, "proposals": list(proposals)}


@unittest.skipUnless(NODE, "node is not installed")
class WeeklyTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        a = {"instance": "expert@t"}
        a.update(args)
        plan = dict(plan, __args=a)
        d = tempfile.mkdtemp(prefix="acad-wk-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True, text=True,
                           timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], out["calls"]

    def test_the_rules_filter_the_proposals_and_the_ledger_settles_after_filing(self):
        props = [prop("downgrade", "rigor-reviewer lighter?", agent="expert:rigor-reviewer",
                      from_tier="max", to_tier="large"),
                 prop("downgrade", "clerk heavier?", agent="clerk", from_tier="base", to_tier="medium"),
                 prop("downgrade", "librarian lighter?", agent="librarian", from_tier="medium",
                      to_tier="base"),
                 prop("budget", "more runs?"),
                 prop("error-family", "fix X?", family="X", state="recurring"),
                 prop("error-family", "fix Y?", family="Y", state="regression")]
        res, calls = self.run_wf({"gather": [data(props)],
                                  "write and file": [{"ok": True, "packet": "P-0200", "error": ""}],
                                  "settle": [{"ok": True, "closed": 4, "detail": ""}]})
        self.assertEqual([p["question"] for p in res["decisions"]],
                         ["fix Y?", "fix X?", "librarian lighter?"])
        dropped = " ".join(res["dropped"])
        self.assertIn("grader expert:rigor-reviewer", dropped)
        self.assertIn("not a lower tier", dropped)
        self.assertIn("over the cap of three", dropped)
        self.assertEqual([c["label"] for c in calls], ["gather", "write and file", "settle"])
        self.assertTrue(res["filed"] and res["settled"])
        write = calls[1]["prompt"]
        self.assertNotIn("rigor-reviewer lighter?", write)
        self.assertIn("Usage 2026-10-24..2026-10-31", write)
        self.assertIn("packets.py show P-0200", calls[2]["prompt"])

    def test_no_settle_without_a_filed_packet(self):
        for filed in ({"ok": False, "packet": "", "error": "packets.py: invalid"},
                      {"ok": True, "packet": "not an id", "error": ""}, None):
            res, calls = self.run_wf({"gather": [data()], "write and file": [filed]})
            self.assertEqual([c["label"] for c in calls], ["gather", "write and file"])
            self.assertFalse(res["settled"])
            self.assertIn("nothing settled", res["reason"])

    def test_a_failed_script_or_no_instance_files_nothing(self):
        res, calls = self.run_wf({"gather": [dict(data(), ok=False, error="usage_report: boom")]})
        self.assertEqual([c["label"] for c in calls], ["gather"])
        self.assertIn("boom", res["reason"])
        res, calls = self.run_wf({}, instance="")
        self.assertEqual(calls, [])
        self.assertIn("file no packet", res["reason"])


if __name__ == "__main__":
    unittest.main()
