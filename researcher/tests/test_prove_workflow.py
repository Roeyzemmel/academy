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
  calls.push({ label: opts.label, agentType: opts.agentType, model: opts.model, prompt })
  const q = plan[opts.label]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned agent ' + opts.label)
  return q.shift()
}
const body = new Function('args', 'agent', 'phase', 'log', 'return (async () => {' + src + '})()')
// the stage-order tests run nested, as from the inbox (no ship stage); the ship tests pass nested: false
// the max-tier launch models as the inbox passes them (T-1682); a test passes models: null to resolve them
body(Object.assign({ nested: true, models: { 'expert:rigor-reviewer': 'fable', 'expert:referee': 'fable', 'researcher:experiment-reviewer': 'fable', 'researcher:prover': 'fable' } }, plan.__args), agent, () => {}, () => {}).then(
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

    COMPLETE = {"state": [state(attack_exists=False)], "attack": ["none"],
                "attempt path": [{"path": "proofs/GEO-3/attempt-2.md"}], "attempt": ["done"],
                "outcome": [{"exists": True, "outcome": "complete", "gaps": [], "objects": []}],
                "file verify": [{"ticket": "T-0020", "proposal": "", "refusal": ""}],
                "check verify": [{"found": True, "to": "expert@t", "kind": "verify", "refs": ["flat:GEO-3"]}],
                "close": [MOVE]}

    def test_every_prover_launch_is_on_the_max_model(self):
        """T-1682: attack, attempt and filing launch on the args' model, or one clerk stage resolves it."""
        res, labels, calls = self.run_wf(dict(self.COMPLETE))
        self.assertEqual([(c["label"], c.get("model")) for c in calls if c["agentType"] == "researcher:prover"],
                         [("attack", "fable"), ("attempt", "fable"), ("file verify", "fable")])
        res, labels, calls = self.run_wf(dict(self.COMPLETE, **{"model researcher:prover": [{"output": "fable"}]}), models=None)
        self.assertEqual(labels.count("model researcher:prover"), 1)          # resolved once per run
        self.assertEqual(calls[labels.index("model researcher:prover")]["agentType"], "researcher:review-clerk")
        self.assertEqual({c.get("model") for c in calls if c["agentType"] == "researcher:prover"}, {"fable"})

    def test_the_attack_line_follows_the_attack_run_not_the_notes(self):
        """The attempt is told to read attack.md only when this run made it, whatever notes the
        model block added (an unresolved model adds one)."""
        bad = {"model researcher:prover": [{"output": "models: workspace.json not found"}]}
        res, labels, calls = self.run_wf(dict(self.COMPLETE, state=[state(attack_exists=True)], **bad), models=None)
        self.assertIn("was not resolved", " ".join(res["notes"]))
        self.assertNotIn("attack.md first", next(c for c in calls if c["label"] == "attempt")["prompt"])
        res, labels, calls = self.run_wf(dict(self.COMPLETE, **bad), models=None)
        self.assertIn("Read proofs/<id>/attack.md first.", next(c for c in calls if c["label"] == "attempt")["prompt"])

    def test_a_lost_attempt_falls_back_to_opus_and_the_ticket_says_so(self):
        res, labels, calls = self.run_wf(dict(self.COMPLETE, attempt=[None], **{"attempt (opus fallback)": ["done"]}))
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertEqual(res["model_fallbacks"], ["attempt: fable -> opus"])
        self.assertIn("model fallback: attempt: fable -> opus", calls[-1]["prompt"])

    def test_the_outcome_comes_from_the_file_not_the_summary(self):
        res, labels, _ = self.run_wf({
            "state": [state()], "attempt path": [{"path": "p.md"}],
            "attempt": ["COMPLETE! the proof is done"],                      # the summary claims success
            "outcome": [{"exists": True, "outcome": "failed", "gaps": ["step 3"], "objects": []}],
            "close": [MOVE]})
        self.assertEqual(res["outcome"], "attempt-incomplete")
        self.assertNotIn("file verify", labels)

    def test_already_proved_and_a_bad_verify_ticket(self):
        res, labels, _ = self.run_wf({"state": [state(status="proved", repair=False)]})
        self.assertEqual(res["outcome"], "already-proved")
        self.assertTrue(res["already_proved"])
        self.assertNotIn("attempt", labels)
        self.assertNotIn("close", labels)                 # #85: never delivered with nothing done
        self.assertFalse(res.get("ticket_delivered"))
        res, labels, _ = self.run_wf({
            "state": [state(status="sketch")], "attempt path": [{"path": "p.md"}], "attempt": ["x"],
            "outcome": [{"exists": True, "outcome": "complete", "gaps": [], "objects": []}],
            "file verify": [{"ticket": "T-0020", "proposal": "", "refusal": ""}],
            "check verify": [{"found": True, "to": "author@t", "kind": "write", "refs": []}],
            "close": [MOVE]})
        self.assertIn("ANOMALY", " ".join(res["notes"]))


    def test_a_repair_of_a_proved_claim_is_attempted(self):
        """#85: a repair ticket on a proved claim (here proved on the human's word, with an
        open GAP and no falsifier on record) gets a new attempt and a verify ticket."""
        plan = dict(self.COMPLETE, state=[state(status="proved", falsified=False, repair=True,
                                                repair_ask="close the GAP in step 3 (T-1243)")])
        res, labels, calls = self.run_wf(plan)
        self.assertEqual(res["outcome"], "verify-filed")
        self.assertTrue(res["repair"])
        prompt = next(c for c in calls if c["label"] == "attempt")["prompt"]
        self.assertIn("This is a repair of a proved claim", prompt)
        self.assertIn("close the GAP in step 3", prompt)
        filed = next(c for c in calls if c["label"] == "file verify")["prompt"]
        self.assertIn("(a repair of the proved claim)", filed)
        self.assertNotIn("propose sketch", filed)

    def test_mode_repair_forces_a_repair(self):
        res, labels, _ = self.run_wf(dict(self.COMPLETE, state=[state(status="proved", repair=False)]), mode="repair")
        self.assertEqual(res["outcome"], "verify-filed")

    def test_a_repair_of_an_unreviewed_claim_still_needs_a_falsifier(self):
        res, labels, _ = self.run_wf({"state": [state(status="sketch", falsified=False, repair=True)]})
        self.assertEqual(res["outcome"], "needs-explore")


def shipped(t, line):
    return {"status": "nothing", "detail": "", "branches": [], "output": "%s: delivered (delivered)\n%s\n" % (t, line)}


@unittest.skipUnless(NODE, "node is not installed")
class ShipTests(unittest.TestCase):
    """docs/workflows.md, "Shipping is a step of the workflow": standalone ships once; nested never."""
    run_wf = ProveTests.run_wf
    PLAN = {"state": [state()], "attempt path": [{"path": "proofs/GEO-3/attempt-2.md"}], "attempt": ["done"],
            "outcome": [{"exists": True, "outcome": "partial", "gaps": ["g"], "objects": []}], "close": [MOVE]}

    def test_standalone_ships_once_and_nested_never(self):
        line = "notebook 2026-11-13/t-0010/researcher @ a (2 files) pushed"
        res, labels, calls = self.run_wf(dict(self.PLAN, ship=[shipped("T-0010", line)]), nested=False, root="/acad", instance="researcher@u")
        self.assertEqual(labels[-2:], ["close", "ship"])
        self.assertEqual(calls[-1]["agentType"], "researcher:review-clerk")
        self.assertIn("py /acad/researcher/scripts/inbox.py --instance researcher@u --check T-0010", calls[-1]["prompt"])
        self.assertEqual(res["ship"]["status"], "pushed")
        res, labels, _ = self.run_wf(dict(self.PLAN))
        self.assertNotIn("ship", labels)
        self.assertNotIn("ship", res)

    def test_a_refusal_is_returned_once(self):
        bad = shipped("T-0010", "notebook main @ a (0 files) REFUSED: dirty on main")
        res, labels, _ = self.run_wf(dict(self.PLAN, ship=[bad, bad]), nested=False)
        self.assertEqual(labels.count("ship"), 1)
        self.assertEqual(res["ship"]["status"], "refused")
        self.assertIn("ship stage was refused", " ".join(res["notes"]))

    def test_no_ticket_is_not_run_with_the_command(self):
        plan = dict(self.PLAN)
        del plan["close"]
        res, labels, _ = self.run_wf(plan, ticket=None, nested=False)
        self.assertNotIn("ship", labels)
        self.assertEqual(res["ship"]["command"],
                         "py scripts/ship.py checkpoint --ticket prove-flat-geo-3 --role researcher --only <home submodule> board")


if __name__ == "__main__":
    unittest.main()
