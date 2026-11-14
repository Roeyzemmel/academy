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
// the stage-order tests run nested, as from the inbox (no ship stage); the ship tests pass nested: false
body(Object.assign({ nested: true }, plan.__args), agent, () => {}, () => {}).then(
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

    def test_an_unreachable_source_with_a_ticket_is_parked_on_the_human(self):
        c = dict(card("unreachable", False), card="none written")
        res, labels, calls = self.run_wf({"start": [ASK], "librarian": [c], "packet": [{"packet": "P-0303", "error": ""}],
                                          "park on human": [MOVE]}, ticket="T-0904")
        self.assertEqual(labels, ["start", "librarian", "packet", "park on human"])   # no validation of a card never written
        self.assertNotIn("deliver", labels)                                            # live run 2026-10-31: it was delivered
        self.assertIn("waiting_on [human]", next(x for x in calls if x["label"] == "park on human")["prompt"])
        self.assertEqual(res["outcome"], "unreachable (on the human)")
        self.assertEqual(res["gate"]["packet"], "P-0303")

    def test_a_lost_librarian_stops(self):
        res, labels, _ = self.run_wf({"start": [ASK], "librarian": [None]}, ticket="T-0904")
        self.assertEqual(res["outcome"], "lost")
        self.assertNotIn("packet", labels)


def shipped(t, line="library 2026-11-13/t-0904/expert @ abc1234 (2 files) pushed"):
    return {"status": "pushed", "detail": "", "branches": [], "output": "%s: delivered (delivered)\n%s\n" % (t, line)}


@unittest.skipUnless(NODE, "node is not installed")
class ShipTests(unittest.TestCase):
    """docs/workflows.md, "Shipping is a step of the workflow": a standalone run ships once; a nested one never."""
    run_wf = CiteTests.run_wf
    PLAN = {"start": [ASK], "librarian": [card()], "validate": [OK], "packet": [{"packet": "P-0300", "error": ""}], "deliver": [MOVE]}

    def test_standalone_with_a_ticket_ships_once_by_the_inbox_check(self):
        res, labels, calls = self.run_wf(dict(self.PLAN, ship=[shipped("T-0904")]), ticket="T-0904", nested=False, root="/acad")
        self.assertEqual(labels, ["start", "librarian", "validate", "packet", "deliver", "ship"])
        self.assertIn("py /acad/expert/scripts/inbox.py --instance expert@t --check T-0904", calls[-1]["prompt"])
        self.assertEqual(calls[-1]["agentType"], "academy:inbox-clerk")
        self.assertEqual(res["ship"]["status"], "pushed")
        self.assertEqual(res["ship"]["branches"], ["library 2026-11-13/t-0904/expert"])

    def test_the_bib_in_the_author_home_ships_with_the_ticket(self):
        # the ticket's --check ships the bib too (the touch ledger, --touched): its line is a
        # branch like any other, and no note sends the human to ship it by hand
        out = shipped("T-0904")
        out["output"] = shipped("T-0904")["output"] + "paper 2026-11-13/t-0904/expert @ def5678 (1 files) pushed\n"
        res, labels, _ = self.run_wf(dict(self.PLAN, ship=[out]), ticket="T-0904", nested=False)
        self.assertEqual(res["ship"]["status"], "pushed")
        self.assertEqual(res["ship"]["branches"], ["library 2026-11-13/t-0904/expert",
                                                   "paper 2026-11-13/t-0904/expert"])
        self.assertNotIn("references.bib", " ".join(res["notes"]))

    def test_nested_never_ships(self):
        res, labels, _ = self.run_wf(dict(self.PLAN), ticket="T-0904", nested=True)
        self.assertNotIn("ship", labels)
        self.assertNotIn("ship", res)

    def test_a_refused_ship_is_returned_once_and_noted(self):
        bad = shipped("T-0904", "library main @ abc (0 files) REFUSED: dirty on main")
        res, labels, _ = self.run_wf(dict(self.PLAN, ship=[bad, bad]), ticket="T-0904", nested=False)
        self.assertEqual(labels.count("ship"), 1)
        self.assertEqual(res["ship"]["status"], "refused")
        self.assertIn("ship stage was refused", " ".join(res["notes"]))

    def test_no_ticket_is_not_run_with_the_command(self):
        res, labels, _ = self.run_wf({"librarian": [card()], "validate": [OK], "packet": [{"packet": "P-0302", "error": ""}]},
                                     ref="SW10", nested=False)
        self.assertNotIn("ship", labels)
        self.assertEqual(res["ship"]["status"], "not-run")
        self.assertEqual(res["ship"]["command"], "py scripts/ship.py checkpoint --ticket cite-sw10 --role expert --only library board")
        self.assertIn("--touched <that home's submodule>:references.bib", " ".join(res["notes"]))   # no ticket claims it

    def test_a_ticket_parked_on_the_human_does_not_ship(self):
        c = dict(card("unreachable", False), card="none written")
        res, labels, _ = self.run_wf({"start": [ASK], "librarian": [c], "packet": [{"packet": "P-0303", "error": ""}],
                                      "park on human": [MOVE]}, ticket="T-0904", nested=False)
        self.assertNotIn("ship", labels)
        self.assertEqual(res["ship"]["status"], "not-run")


if __name__ == "__main__":
    unittest.main()
