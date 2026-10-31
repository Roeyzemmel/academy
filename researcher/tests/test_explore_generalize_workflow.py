"""The explore and generalize workflows (workflows/explore.js, generalize.js), 2026-10-31.
Under node with a fake agent(); skipped without node."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WF = os.path.join(os.path.dirname(HERE), "workflows")
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
    d = tempfile.mkdtemp(prefix="acad-eg-")
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


DIR = {"exists": True, "lifecycle": "active", "title": "t", "items": 5}
NEXT = {"items": [{"ref": "flat:KDC-6", "kind": "claim", "status": "conjectured"},
                  {"ref": "flat:KDC-7", "kind": "claim", "status": "open"}], "remaining": 3}
JOURNAL = {"exists": True, "path": "journal/2026-10-31.md", "mentions": ["flat:KDC-6", "flat:KDC-7"]}
H = {"home": "/h/nb", "instance": "researcher@u"}


@unittest.skipUnless(NODE, "node is not installed")
class ExploreTests(unittest.TestCase):
    def test_lead_briefed_with_ids_and_steps_checked(self):
        lead = {"items": [{"item": "flat:KDC-6", "step": "falsify", "tickets": ["T-0500"], "objects": [], "note": ""},
                          {"item": "flat:KDC-7", "step": "prove", "tickets": [], "objects": [], "note": ""}],
                "report": "r", "next_picks": ["flat:KDC-8"]}
        res, labels, calls, err = run("explore.js", {
            "direction": [DIR], "next": [NEXT], "lead": [lead],
            "get T-0500": [{"found": True, "to": "expert@t", "kind": "experiment", "refs": ["flat:KDC-6"]}],
            "falsified flat:KDC-7": [{"falsified": False, "evidence": ""}], "journal": [JOURNAL]},
            dict(H, direction="DIR-1"))
        self.assertIsNone(err, err)
        lp = next(c for c in calls if c["label"] == "lead")["prompt"]
        self.assertIn("items flat:KDC-6, flat:KDC-7", lp)
        anomalies = " ".join(res["anomalies"])
        self.assertIn("not an experiment ticket to the Scientist", anomalies)   # wrong receiver
        self.assertIn("moved to prove with no falsifier", anomalies)
        self.assertEqual(res["remaining"], 3)

    def test_a_missing_direction_is_filled_first(self):
        res, labels, _, err = run("explore.js", {
            "direction": [dict(DIR, exists=False)], "fill direction": ["made it"], "direction again": [DIR],
            "next": [NEXT], "lead": [{"items": [], "report": "r", "next_picks": []}], "journal": [JOURNAL]},
            dict(H, direction="DIR-9"))
        self.assertIsNone(err, err)
        self.assertEqual(labels[:4], ["direction", "fill direction", "direction again", "next"])

    def test_a_question_ticket_is_one_item_and_delivered(self):
        res, labels, _, err = run("explore.js", {
            "start": [{"ok": True, "detail": ""}],
            "lead": [{"items": [{"item": "Q", "step": "prior-art", "tickets": ["T-1"], "objects": [], "note": ""}], "report": "r", "next_picks": []}],
            "journal": [dict(JOURNAL, mentions=["Q"])], "close": [{"ok": True, "detail": ""}]},
            dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["start", "lead", "journal", "close"])
        self.assertTrue(res["ticket_delivered"])


SRC = {"ok": True, "refusal": "", "lab_claim": "lab:ew-check", "report": "P-0009", "max": 3}
GOOD = {"ok": True, "problems": [], "failing": [], "proposals": 2}
BAD = {"ok": False, "problems": ["flat:CONJ-2: status must be conjectured"], "failing": ["flat:CONJ-2"], "proposals": 2}


@unittest.skipUnless(NODE, "node is not installed")
class GeneralizeTests(unittest.TestCase):
    def test_a_refused_source_stops_and_no_ticket_asks_for_one(self):
        res, labels, _, err = run("generalize.js", {"source": [dict(SRC, ok=False, refusal="review not cleared")]},
                                  dict(H, ref="P-0009", ticket="T-7"))
        self.assertIn("review-experiment first", res["reason"])
        self.assertEqual(labels, ["source"])
        res, labels, _, err = run("generalize.js", {"source": [SRC]}, dict(H, ref="P-0009"))
        self.assertTrue(res["needs_ticket"])

    def test_one_retry_then_drop_then_create_packet_and_to_file(self):
        res, labels, calls, err = run("generalize.js", {
            "source": [SRC], "prover": ["wrote"], "validate": [BAD], "prover (fix)": ["fixed"],
            "validate again": [BAD], "drop": [{"ok": True, "detail": ""}], "validate after drop": [dict(GOOD, proposals=1)],
            "create": [{"conjectures": ["flat:CONJ-1"], "lemmas": ["flat:LEM-1"], "error": ""}],
            "packet": [{"packet": "P-0400", "error": ""}]}, dict(H, ref="P-0009", ticket="T-7"))
        self.assertIsNone(err, err)
        self.assertEqual(labels.count("prover (fix)"), 1)
        self.assertIn("dropped after a second failure: flat:CONJ-2", " ".join(res["notes"]))
        self.assertIn("generalize.py tickets", res["to_file"][0]["command"])
        self.assertEqual(res["to_file"][0]["then"]["conjectures"], ["flat:CONJ-1"])
        self.assertIn("Write ONLY that file", next(c for c in calls if c["label"] == "prover")["prompt"])

    def test_deliver_checks_a_test_per_conjecture(self):
        args = dict(H, ref="P-0009", ticket="T-7", mode="deliver", conjectures=["flat:CONJ-1", "flat:CONJ-3"])
        res, labels, _, err = run("generalize.js", {"children": [{"tests": [{"id": "T-8", "refs": ["flat:CONJ-1"]}]}]}, args)
        self.assertEqual(res["missing"], ["flat:CONJ-3"])
        self.assertNotIn("close", labels)
        res, labels, _, err = run("generalize.js", {"children": [{"tests": [{"id": "T-8", "refs": ["flat:CONJ-1"]},
                                                                            {"id": "T-9", "refs": ["flat:CONJ-3"]}]}],
                                                    "close": [{"ok": True, "detail": ""}]}, args)
        self.assertEqual(res["outcome"], "delivered")


if __name__ == "__main__":
    unittest.main()
