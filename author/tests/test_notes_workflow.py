"""The notes workflow (workflows/notes.js) and routes.py --check-filed, 2026-10-31. Under node
with a fake agent(); skipped without node."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SCRIPT = os.path.join(PLUGIN, "workflows", "notes.js")
ROUTES = os.path.join(PLUGIN, "scripts", "routes.py")
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

N1 = {"id": "sections/a.tex:10", "file": "sections/a.tex", "line": 10, "macro": "\\human", "label": "lem:x", "text": "prove the k=3 case"}
N2 = {"id": "sections/a.tex:20", "file": "sections/a.tex", "line": 20, "macro": "\\human", "label": "defn:y", "text": "rename H to G"}
N3 = {"id": "sections/b.tex:5", "file": "sections/b.tex", "line": 5, "macro": "\\coauthor", "label": "", "text": "same as T-0100"}
INV = {"ok": True, "detail": "", "ns": "paper", "new": [N1, N2, N3], "inventory": 40, "inventory_notes": []}


def prop(to, kind, final_to="", park_on=""):
    return {"to": to, "kind": kind, "title": "t", "ask": "a", "deliverable": "d", "agenda": "paper:lem:x",
            "refs": ["paper:lem:x"], "final_to": final_to, "detail": "x", "park_on": park_on}


def dec(note, decision, proposed=None, ticket="", judgement=False):
    d = {"note": note, "decision": decision, "ticket": ticket, "words": "w", "judgement": judgement, "claim_vs_file": ""}
    if proposed:
        d["proposed"] = proposed
    return d


@unittest.skipUnless(NODE, "node is not installed")
class NotesTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        a = {"home": "/h/bi", "instance": "author@t"}
        a.update(args)
        d = tempfile.mkdtemp(prefix="acad-nt-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(dict(plan, __args=a))], capture_output=True, text=True, timeout=60)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], [c["label"] for c in out["calls"]], out["calls"]

    def test_a_proof_note_filed_as_write_is_sent_back_and_corrected(self):
        bad = [dec(N1["id"], "new", prop("author@t", "write")), dec(N2["id"], "new", prop("author@t", "apply")),
               dec(N3["id"], "covered", ticket="T-0100")]
        good = [dec(N1["id"], "new", prop("expert@t", "research", "researcher")), dec(N2["id"], "new", prop("author@t", "apply")),
                dec(N3["id"], "covered", ticket="T-0100")]
        res, labels, calls = self.run_wf({
            "collect": [INV], "classify": [{"decisions": bad}],
            "check-filed": [{"problems": [["a missing argument is not a `write` ticket"], []]}, {"problems": [[], []]}],
            "classify again": [{"decisions": good}],
            "file": [{"filed": [{"note": N1["id"], "ticket": "T-1"}, {"note": N2["id"], "ticket": "T-2"}], "appended": ["T-0100"], "refused": []}],
            "read back": [{"tickets": [{"id": "T-1", "to": "expert@t", "kind": "research", "final_to": "researcher", "status": "open", "waiting_on": []},
                                       {"id": "T-2", "to": "author@t", "kind": "apply", "final_to": "", "status": "open", "waiting_on": []}]}]})
        self.assertEqual(labels, ["collect", "classify", "check-filed", "classify again", "check-filed", "file", "read back"])
        self.assertEqual(res["anomalies"], [])
        self.assertEqual(res["covered"], [N3["id"] + " -> T-0100"])
        self.assertIn("sent back once", " ".join(res["notes"]))
        f = next(c for c in calls if c["label"] == "file")["prompt"]
        self.assertIn('"kind":"research"', f)
        self.assertNotIn('"kind":"write"', f)

    def test_a_judgement_point_must_be_parked_and_a_readback_mismatch_is_caught(self):
        d1 = dec(N1["id"], "new", prop("author@t", "apply"), judgement=True)          # not parked on human
        res, labels, _ = self.run_wf({
            "collect": [dict(INV, new=[N1])], "classify": [{"decisions": [d1]}],
            "check-filed": [{"problems": [[]]}, {"problems": [[]]}], "classify again": [{"decisions": [d1]}]})
        self.assertIn("parked on human", " ".join(res["unfiled"]))
        self.assertNotIn("file", labels)
        d2 = dec(N2["id"], "new", prop("author@t", "apply"))
        res, labels, _ = self.run_wf({
            "collect": [dict(INV, new=[N2])], "classify": [{"decisions": [d2]}], "check-filed": [{"problems": [[]]}],
            "file": [{"filed": [{"note": N2["id"], "ticket": "T-2"}], "appended": [], "refused": []}],
            "read back": [{"tickets": [{"id": "T-2", "to": "expert@t", "kind": "write", "final_to": "", "status": "open", "waiting_on": []}]}]})
        self.assertIn("not as checked", " ".join(res["anomalies"]))

    def test_nothing_new_and_a_referee_packet(self):
        res, labels, _ = self.run_wf({"collect": [dict(INV, new=[])]})
        self.assertEqual(res["outcome"], "nothing-new")
        res, labels, calls = self.run_wf({"collect": [dict(INV, new=[])]}, referee_ticket="T-0700")
        self.assertIn("packets field of T-0700", next(c for c in calls if c["label"] == "collect")["prompt"])


class CheckFiledCli(unittest.TestCase):
    def test_one_problem_list_per_ticket(self):
        d = tempfile.mkdtemp(prefix="acad-cf-")
        self.addCleanup(shutil.rmtree, d, True)
        f = os.path.join(d, "p.json")
        with open(f, "w", encoding="utf-8") as fh:
            json.dump([{"kind": "write", "to": "author@t", "title": "Fill the gap in the proof", "ask": "give a new proof"},
                       {"kind": "research", "to": "expert@t", "final_to": "researcher", "title": "Prove x", "ask": "prove that x"},
                       {"kind": "apply", "to": "author@t", "title": "rename", "ask": "rename H to G"}], fh)
        p = subprocess.run([sys.executable, ROUTES, "--check-filed", f], capture_output=True, text=True)
        out = json.loads(p.stdout)
        self.assertEqual(len(out), 3)
        self.assertTrue(out[0])
        self.assertEqual(out[1:], [[], []])


if __name__ == "__main__":
    unittest.main()
