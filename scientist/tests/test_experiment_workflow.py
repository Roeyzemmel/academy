"""The experiment workflow (workflows/experiment.js), 2026-10-31: the human gates are
unskippable (design stops at the header, build at the commit, queue refuses an uncommitted
script, report stops at the rendered packet). Under node with a fake agent()."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "workflows", "experiment.js")
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

HOME = {"ok": True, "instance": "scientist@t", "home": "/h/lab", "run_profile": "remote", "detail": ""}
DESIGN = {"path": "experiment", "argument": "", "stem": "2026-10-31_x", "header": "Kind: search\nClaims: lab:x",
          "if_false": "a member violating the bound", "api_unfamiliar": []}
OK = {"ok": True, "errors": []}
BAD = {"ok": False, "errors": ["header: Claims: missing"]}


@unittest.skipUnless(NODE, "node is not installed")
class ExperimentTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        d = tempfile.mkdtemp(prefix="acad-ex-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(dict(plan, __args=args))], capture_output=True, text=True, timeout=60)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        return out.get("result"), [c["label"] for c in out["calls"]], out["calls"], out.get("error")

    def test_design_stops_at_the_header_gate(self):
        res, labels, calls, err = self.run_wf({"lab home": [HOME], "design": [DESIGN]}, mode="design", claim="lab:x", ticket="T-1")
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["lab home", "design"])
        self.assertTrue(res["for_main"]["gate"])
        self.assertIn("approve the header", res["for_main"]["why"])
        self.assertEqual(res["for_main"]["next"]["mode"], "build")
        self.assertIn("HEADER ONLY", next(c for c in calls if c["label"] == "design")["prompt"])

    def test_a_two_line_argument_stops_without_a_script(self):
        res, labels, _, err = self.run_wf({"lab home": [HOME], "design": [dict(DESIGN, path="argument", argument="by parity")]}, mode="design", claim="c")
        self.assertEqual(res["outcome"], "argument")
        self.assertNotIn("for_main", res)

    def test_build_checks_with_one_fix_and_stops_for_the_commit(self):
        built = {"script": "experiments/2026-10-31_x.py", "lab_claim": "lab:x", "tests": [], "note": ""}
        res, labels, _, err = self.run_wf({"build": [built], "check": [BAD], "build (fix)": [built], "check again": [OK]},
                                          mode="build", header="Kind: search", stem="2026-10-31_x")
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["build", "check", "build (fix)", "check again"])
        self.assertIn("commit the experiment script", res["for_main"]["why"])
        res, labels, _, err = self.run_wf({"build": [built], "check": [BAD], "build (fix)": [built], "check again": [BAD]},
                                          mode="build", header="h", stem="s")
        self.assertEqual(res["outcome"], "check-failed")
        _r, _l, _c, err = self.run_wf({}, mode="build", stem="s")
        self.assertIn("approved text", err)

    def test_queue_refuses_an_uncommitted_script(self):
        res, labels, _, err = self.run_wf({"committed?": [{"committed": False, "commit": "", "dirty": ["experiments/s.py"]}]}, mode="queue", stem="s")
        self.assertIn("not committed", res["for_main"]["why"])
        self.assertNotIn("queue", labels)
        res, labels, _, err = self.run_wf({"committed?": [{"committed": True, "commit": "abc", "dirty": []}],
                                           "queue": [{"ok": True, "job": "j1", "command": "c", "detail": ""}]}, mode="queue", stem="s")
        self.assertEqual((res["outcome"], res["job"]), ("queued", "j1"))

    def test_report_stops_at_the_rendered_packet_and_file_delivers(self):
        dr = {"report": "reports/s.md", "result_line": "no counterexample below 9 over class C"}
        res, labels, _, err = self.run_wf({"report draft": [dr], "report check": [OK], "render": [{"ok": True, "rendered": "<packet>", "errors": []}]},
                                          mode="report", stem="s", job="j1")
        self.assertEqual(labels, ["report draft", "report check", "render"])
        self.assertEqual(res["for_main"]["rendered"], "<packet>")
        self.assertEqual(res["for_main"]["next"]["mode"], "file")
        res, labels, calls, err = self.run_wf({"file": [{"packet": "P-1", "review_ticket": "T-9", "researcher": "researcher@u", "why": "owns lab:", "error": ""}],
                                               "deliver": [{"ok": True, "detail": ""}]}, mode="file", stem="s", ticket="T-1")
        self.assertEqual(res["outcome"], "filed")
        self.assertIn("--ticket T-1", next(c for c in calls if c["label"] == "file")["prompt"])


if __name__ == "__main__":
    unittest.main()
