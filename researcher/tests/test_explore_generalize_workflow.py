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
  calls.push({ label: opts.label, agentType: opts.agentType, model: opts.model, prompt, schema: opts.schema })
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
JOURNAL = {"exists": True, "path": "journal/2026-10-31.md", "mentions": ["flat:KDC-6", "flat:KDC-7"], "found": []}
H = {"home": "/h/nb", "instance": "researcher@u"}
OK = {"ok": True, "detail": ""}
FAILED = {"exists": True, "kind": "attempt", "outcome": "failed", "gaps": 1, "verdict": ""}
GOOD_FALSIFIER = {"found": True, "to": "scientist@lab", "kind": "experiment", "refs": ["flat:KDC-6", "Q"]}


def item(ref, step, tickets=(), objects=(), updated=(), claim="", after=""):
    return {"item": ref, "step": step, "tickets": list(tickets), "objects": list(objects), "updated": list(updated),
            "claim": claim, "after": after, "note": ""}


@unittest.skipUnless(NODE, "node is not installed")
class ExploreTests(unittest.TestCase):
    def test_lead_briefed_with_ids_and_steps_checked(self):
        lead = {"items": [item("flat:KDC-6", "falsify", tickets=["T-0500"], after="proofs/KDC-6/attempt-1.md"),
                          item("flat:KDC-7", "prior-art", tickets=["T-0501"])],
                "report": "r", "next_picks": ["flat:KDC-8"]}
        res, labels, calls, err = run("explore.js", {
            "direction": [DIR], "next": [NEXT], "lead": [lead],
            "trigger flat:KDC-6": [FAILED],
            "get T-0500": [{"found": True, "to": "expert@t", "kind": "experiment", "refs": ["flat:KDC-6"]}],
            "journal": [JOURNAL]},
            dict(H, direction="DIR-1"))
        self.assertIsNone(err, err)
        lp = next(c for c in calls if c["label"] == "lead")["prompt"]
        self.assertIn("items flat:KDC-6, flat:KDC-7", lp)
        anomalies = " ".join(res["anomalies"])
        self.assertIn("not an experiment ticket to the Scientist", anomalies)   # wrong receiver
        self.assertNotIn("flat:KDC-7", anomalies)
        self.assertFalse([c for c in labels if c.startswith("falsified")])
        self.assertIn("does not wait for a falsifier", lp)
        self.assertNotIn("survived falsification", lp)
        self.assertEqual(res["remaining"], 3)

    def test_the_order_is_prove_s_prior_art_then_prove_falsify_only_after_an_attempt(self):
        """#87, the human's ruling of 2026-11-20: explore uses prove's order. No stage text
        or meta line puts a falsifier before an attempt."""
        res, labels, calls, err = run("explore.js", {"direction": [DIR], "next": [NEXT], "journal": [JOURNAL],
                                                     "lead": [{"items": [], "report": "r", "next_picks": []}]}, dict(H, direction="DIR-1"))
        self.assertIsNone(err, err)
        lp = next(c for c in calls if c["label"] == "lead")["prompt"]
        order = lp[lp.index("ONE step"):]
        self.assertLess(order.index("prior art first"), order.index("then prove"))
        self.assertLess(order.index("then prove"), order.index("Only then falsify"))
        self.assertIn("never file a falsifier for an item with no such attempt and no GAP verdict", lp)
        self.assertIn("[fix-unclear] or [needs-assumption]", lp)                # #126
        with open(os.path.join(WF, "explore.js"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("falsify, prior art", src)
        self.assertNotIn("in this order: falsify", src)
        for c in calls:                       # every stage text: a falsifier comes after an attempt
            t = c["prompt"]
            if "falsif" in t:
                first = [i for i in (t.find("prove"), t.find("attempt")) if i >= 0]
                self.assertTrue(first, c["label"])
                self.assertLess(min(first), t.find("falsif"), c["label"])

    def test_a_falsify_step_before_an_attempt_is_an_anomaly_and_no_artefact(self):
        lead = {"items": [item("Q", "falsify", tickets=["T-1"])], "report": "r", "next_picks": []}
        res, labels, _, err = run("explore.js", {"start": [OK], "lead": [lead], "journal": [dict(JOURNAL, mentions=["Q"], found=["T-1"])],
                                                 "get T-1": [GOOD_FALSIFIER], "note": [OK]}, dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertIn("before an attempt", " ".join(res["anomalies"]))
        self.assertNotIn("trigger Q", labels)                   # nothing named: nothing to read
        self.assertNotIn("close", labels)                       # a premature falsifier is no artefact to deliver on
        self.assertFalse(res["ticket_delivered"])
        # a named trigger the clerk reads as a complete attempt with no gaps does not count either
        lead = {"items": [item("Q", "falsify", tickets=["T-1"], after="proofs/Q/attempt-2.md")], "report": "r", "next_picks": []}
        res, labels, _, err = run("explore.js", {"start": [OK], "lead": [lead], "journal": [dict(JOURNAL, mentions=["Q"], found=["T-1"])],
                                                 "trigger Q": [dict(FAILED, outcome="complete", gaps=0)], "get T-1": [GOOD_FALSIFIER], "note": [OK]},
                                  dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertIn("before an attempt", " ".join(res["anomalies"]))
        # #126: an incomplete attempt whose gaps are all fix-known (or rest on declared inputs) does not either
        lead = {"items": [item("Q", "falsify", tickets=["T-1"], after="proofs/Q/attempt-2.md")], "report": "r", "next_picks": []}
        res, labels, _, err = run("explore.js", {"start": [OK], "lead": [lead], "journal": [dict(JOURNAL, mentions=["Q"], found=["T-1"])],
                                                 "trigger Q": [dict(FAILED, outcome="partial", gaps=2, falsifying_gaps=0)], "get T-1": [GOOD_FALSIFIER], "note": [OK]},
                                  dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertIn("no fix-unclear or needs-assumption gap", " ".join(res["anomalies"]))
        # ... and one with a needs-assumption gap does
        res, labels, _, err = run("explore.js", {"start": [OK], "lead": [lead], "journal": [dict(JOURNAL, mentions=["Q"], found=["T-1"])],
                                                 "trigger Q": [dict(FAILED, outcome="partial", gaps=2, falsifying_gaps=1)], "get T-1": [GOOD_FALSIFIER], "close": [OK]},
                                  dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertEqual(res["anomalies"], [])
        # ... and a clerk answer without falsifying_gaps is read as none, with an anomaly saying so
        res, labels, _, err = run("explore.js", {"start": [OK], "lead": [lead], "journal": [dict(JOURNAL, mentions=["Q"], found=["T-1"])],
                                                 "trigger Q": [dict(FAILED, outcome="partial", gaps=1)], "get T-1": [GOOD_FALSIFIER], "note": [OK]},
                                  dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertIn("did not report falsifying_gaps", " ".join(res["anomalies"]))
        # a GAP verdict does
        lead = {"items": [item("Q", "falsify", tickets=["T-1"], after="T-0900")], "report": "r", "next_picks": []}
        res, labels, _, err = run("explore.js", {"start": [OK], "lead": [lead], "journal": [dict(JOURNAL, mentions=["Q"], found=["T-1"])],
                                                 "trigger Q": [{"exists": True, "kind": "verdict", "outcome": "", "gaps": 0, "verdict": "GAP"}],
                                                 "get T-1": [GOOD_FALSIFIER], "close": [OK]}, dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertEqual(res["anomalies"], [])
        self.assertTrue(res["ticket_delivered"])

    def test_a_falsifier_after_an_incomplete_attempt_marks_the_ticket_partial(self):
        """#100 part 1: the attempt is not complete, so the deliverable is not met (its gap is
        a falsifying one, #126: only then does an incomplete attempt call for a falsifier)."""
        lead = {"items": [item("Q", "falsify", tickets=["T-1"], after="proofs/Q/attempt-2.md")], "report": "r", "next_picks": []}
        res, labels, calls, err = run("explore.js", {"start": [OK], "lead": [lead], "journal": [dict(JOURNAL, mentions=["Q"], found=["T-1"])],
                                                     "trigger Q": [dict(FAILED, outcome="incomplete", gaps=1, falsifying_gaps=1)], "get T-1": [GOOD_FALSIFIER], "close": [OK]},
                                      dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertEqual(res["outcome"], "partial")
        self.assertTrue(res["ticket_partial"])
        self.assertFalse(res["ticket_delivered"])
        p = next(c for c in calls if c["label"] == "close")["prompt"]
        self.assertIn("status partial", p)
        self.assertIn("proofs/Q/attempt-2.md incomplete", p)

    def test_a_prove_step_is_handed_back_never_delivered(self):
        """#87: the lead cannot launch prover inside the run; the prove step comes back as
        /researcher:prove with its args, the way the inbox hands back a lead (T-1271)."""
        lead = {"items": [item("Q", "prove", claim="s1:CEX-9")], "report": "r", "next_picks": []}
        res, labels, calls, err = run("explore.js", {"start": [OK], "lead": [lead], "claim s1:CEX-9": [{"exit": 0, "output": "CEX-9: ..."}],
                                                     "journal": [dict(JOURNAL, mentions=["Q"])]}, dict(H, ticket="T-0600", root="/r"))
        self.assertIsNone(err, err)
        self.assertNotIn("close", labels)
        self.assertFalse(res["ticket_delivered"])
        self.assertEqual(res["outcome"], "handed-back")
        fm = res["for_main"]
        self.assertEqual((fm["skill"], fm["handback"], fm["ticket"]), ("researcher:prove", "lead-researcher", "T-0600"))
        self.assertEqual(fm["args"], {"claim": "s1:CEX-9", "ticket": "T-0600", "home": "/h/nb", "instance": "researcher@u", "root": "/r"})
        self.assertIn("/researcher:prove s1:CEX-9 with ticket T-0600", fm["why"])
        self.assertIn("registry.py statement s1:CEX-9", next(c for c in calls if c["label"] == "claim s1:CEX-9")["prompt"])
        lp = next(c for c in calls if c["label"] == "lead")["prompt"]
        self.assertIn("cannot launch prover", lp)

    def test_two_prove_items_of_a_direction_hand_back_two_runs(self):
        lead = {"items": [item("flat:KDC-6", "prove", claim="flat:KDC-6"), item("flat:KDC-7", "prove", claim="flat:KDC-7")],
                "report": "r", "next_picks": []}
        res, labels, _, err = run("explore.js", {"direction": [DIR], "next": [NEXT], "lead": [lead],
                                                 "claim flat:KDC-6": [{"exit": 0, "output": "x"}], "claim flat:KDC-7": [{"exit": 0, "output": "x"}],
                                                 "journal": [JOURNAL]}, dict(H, direction="DIR-1"))
        self.assertIsNone(err, err)
        fm = res["for_main"]
        self.assertEqual([r["claim"] for r in fm["runs"]], ["flat:KDC-6", "flat:KDC-7"])
        self.assertEqual(fm["args"], fm["runs"][0]["args"])
        self.assertNotIn("ticket", fm["runs"][1]["args"])

    def test_a_prove_claim_that_does_not_resolve_comes_back_without_args(self):
        lead = {"items": [item("Q", "prove", claim="s1:NOPE-1")], "report": "r", "next_picks": []}
        res, labels, _, err = run("explore.js", {"start": [OK], "lead": [lead],
                                                 "claim s1:NOPE-1": [{"exit": 1, "output": "s1:NOPE-1 does not resolve"}],
                                                 "journal": [dict(JOURNAL, mentions=["Q"])]}, dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertNotIn("args", res["for_main"])
        self.assertIn("claims_new", res["for_main"]["why"])
        self.assertNotIn("close", labels)
        lead = {"items": [item("Q", "prove", claim="")], "report": "r", "next_picks": []}       # no claim named at all
        res, labels, _, err = run("explore.js", {"start": [OK], "lead": [lead], "journal": [dict(JOURNAL, mentions=["Q"])]}, dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertNotIn("args", res["for_main"])
        self.assertIn("names no registry claim", " ".join(res["anomalies"]))

    def test_a_ticket_with_no_artefact_is_not_delivered(self):
        """#87: T-1668 was delivered with nothing behind it. Every artefact-less ending
        (no items, step none, a prior-art step that filed nothing, artefacts the clerk cannot find)."""
        for items, found in (([], []), ([item("Q", "none")], []), ([item("Q", "prior-art")], []),
                             ([item("Q", "prior-art", tickets=["T-77"])], [])):
            res, labels, calls, err = run("explore.js", {"start": [OK], "lead": [{"items": items, "report": "r", "next_picks": []}],
                                                         "journal": [dict(JOURNAL, mentions=["Q"], found=found)], "note": [OK]},
                                          dict(H, ticket="T-0600"))
            self.assertIsNone(err, err)
            self.assertNotIn("close", labels, items)
            self.assertFalse(res["ticket_delivered"])
            self.assertEqual(res["outcome"], "no-artefact")
            self.assertIn("not delivered", next(c for c in calls if c["label"] == "note")["prompt"])

    def test_the_ticket_itself_is_no_artefact_and_the_check_asks_for_change(self):
        """Review of 1bbcc77: a lead naming the question ticket itself, or a file that merely
        exists, could deliver it with nothing behind it."""
        lead = {"items": [item("Q", "prior-art", tickets=["T-0600"])], "report": "r", "next_picks": []}
        res, labels, calls, err = run("explore.js", {"start": [OK], "lead": [lead], "note": [OK],
                                                     "journal": [dict(JOURNAL, mentions=["Q"], found=[])]},
                                      dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertNotIn("close", labels)
        self.assertIn("the ticket itself", " ".join(res["notes"]))
        lead = {"items": [item("Q", "prior-art", updated=["objects/direction/DIR-2.md"])], "report": "r", "next_picks": []}
        res, labels, calls, err = run("explore.js", {"start": [OK], "lead": [lead], "note": [OK],
                                                     "journal": [dict(JOURNAL, mentions=["Q"], found=[])]},
                                      dict(H, ticket="T-0600"))
        self.assertIn("changed today", next(c for c in calls if c["label"] == "journal")["prompt"])

    def test_a_lost_check_is_lost_not_no_artefact(self):
        lead = {"items": [item("Q", "prior-art", tickets=["T-77"])], "report": "r", "next_picks": []}
        res, labels, calls, err = run("explore.js", {"start": [OK], "lead": [lead], "journal": [None]},
                                      dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertEqual("lost", res["outcome"])
        self.assertNotIn("note", labels)

    def test_a_delivered_ticket_names_its_artefacts(self):
        lead = {"items": [item("Q", "prior-art", tickets=["T-77"], updated=["objects/direction/DIR-2.md"])], "report": "r", "next_picks": []}
        res, labels, calls, err = run("explore.js", {"start": [OK], "lead": [lead], "close": [OK],
                                                     "journal": [dict(JOURNAL, mentions=["Q"], found=["T-77", "objects/direction/DIR-2.md"])]},
                                      dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        jp = next(c for c in calls if c["label"] == "journal")["prompt"]
        self.assertIn("T-77", jp)
        cp = next(c for c in calls if c["label"] == "close")["prompt"]
        self.assertIn("T-77", cp)
        self.assertIn("objects/direction/DIR-2.md", cp)
        self.assertEqual(res["artefacts"], ["T-77", "objects/direction/DIR-2.md"])
        self.assertTrue(res["ticket_delivered"])

    def test_clerk_schemas_require_no_free_text_and_a_bare_refusal_has_a_default(self):
        lead = {"items": [item("flat:KDC-6", "falsify", tickets=["T-0500"], after="proofs/KDC-6/attempt-1.md"),
                          item("flat:KDC-7", "prove", claim="flat:KDC-7")], "report": "r", "next_picks": []}
        res, labels, calls, err = run("explore.js", {"start": [OK], "direction": [DIR], "next": [NEXT], "lead": [lead],
                                                     "trigger flat:KDC-6": [FAILED], "get T-0500": [GOOD_FALSIFIER],
                                                     "claim flat:KDC-7": [{"exit": 0, "output": "x"}], "journal": [JOURNAL]},
                                      dict(H, direction="DIR-1", ticket="T-0600"))
        self.assertIsNone(err, err)
        clerks = [c for c in calls if c["agentType"] == "researcher:review-clerk"]
        self.assertGreaterEqual(len({c["label"] for c in clerks}), 6)
        for c in clerks:
            req = set((c["schema"] or {}).get("required", []))
            self.assertFalse(req & {"detail", "why", "error", "reason"}, c["label"])
        res, labels, _, err = run("explore.js", {"start": [{"ok": False}]}, dict(H, ticket="T-0600"))
        self.assertIsNone(err, err)
        self.assertEqual(res["outcome"], "not-started")
        self.assertTrue(res["reason"])
    def test_a_missing_direction_is_filled_first(self):
        res, labels, _, err = run("explore.js", {
            "direction": [dict(DIR, exists=False)], "fill direction": ["made it"], "direction again": [DIR],
            "next": [NEXT], "lead": [{"items": [], "report": "r", "next_picks": []}], "journal": [JOURNAL]},
            dict(H, direction="DIR-9"))
        self.assertIsNone(err, err)
        self.assertEqual(labels[:4], ["direction", "fill direction", "direction again", "next"])

    def test_a_question_ticket_is_one_item_and_delivered(self):
        res, labels, _, err = run("explore.js", {
            "start": [OK],
            "lead": [{"items": [item("Q", "prior-art", tickets=["T-1"])], "report": "r", "next_picks": []}],
            "journal": [dict(JOURNAL, mentions=["Q"], found=["T-1"])], "close": [OK]},
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
            "packet": [{"packet": "P-0400", "error": ""}],
            "test specs": [{"specs": [{"to": "scientist@t", "kind": "test", "refs": ["flat:CONJ-1"]}]}],
            "file tests": [{"tickets": ["T-8"], "refusals": []}],
            "children": [{"tests": [{"id": "T-8", "refs": ["flat:CONJ-1"]}]}], "close": [{"ok": True, "detail": ""}]},
            dict(H, ref="P-0009", ticket="T-7"))
        self.assertIsNone(err, err)
        self.assertEqual(labels.count("prover (fix)"), 1)
        self.assertEqual([c.get("model") for c in calls if c["agentType"] == "researcher:prover"], ["fable", "fable"])  # T-1682
        self.assertIn("dropped after a second failure: flat:CONJ-2", " ".join(res["notes"]))
        self.assertEqual(next(c for c in calls if c["label"] == "file tests")["agentType"], "researcher:lead-researcher")
        self.assertIn("WITHOUT --apply", next(c for c in calls if c["label"] == "test specs")["prompt"])
        self.assertEqual(res["outcome"], "delivered")
        self.assertEqual(res["tests"], ["T-8"])

    def test_a_test_the_lead_did_not_file_comes_back_to_file(self):
        res, labels, calls, err = run("generalize.js", {
            "source": [SRC], "prover": ["wrote"], "validate": [GOOD],
            "create": [{"conjectures": ["flat:CONJ-1", "flat:CONJ-3"], "lemmas": [], "error": ""}],
            "packet": [{"packet": "P-0400", "error": ""}], "test specs": [{"specs": []}],
            "file tests": [{"tickets": ["T-8"], "refusals": ["chain: no"]}],
            "children": [{"tests": [{"id": "T-8", "refs": ["flat:CONJ-1"]}]}]}, dict(H, ref="P-0009", ticket="T-7"))
        self.assertIsNone(err, err)
        self.assertEqual(res["to_file"][0]["missing"], ["flat:CONJ-3"])
        self.assertNotIn("close", labels)
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


def shipped(t, line):
    return {"status": "nothing", "detail": "", "branches": [], "output": "%s: delivered (delivered)\n%s\n" % (t, line)}


@unittest.skipUnless(NODE, "node is not installed")
class ShipTests(unittest.TestCase):
    """docs/workflows.md, "Shipping is a step of the workflow": standalone ships once; nested never."""
    Q = {"start": [OK], "journal": [dict(JOURNAL, mentions=["Q"], found=["T-1"])], "close": [OK],
         "lead": [{"items": [item("Q", "prior-art", tickets=["T-1"])], "report": "r", "next_picks": []}]}
    LINE = "Slope 2026-11-13/t-0600/researcher @ a (1 files) pushed"

    def test_explore_standalone_ships_once_nested_never_refusal_once(self):
        res, labels, _, err = run("explore.js", dict(self.Q, ship=[shipped("T-0600", self.LINE)]), dict(H, ticket="T-0600", nested=False))
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["start", "lead", "journal", "close", "ship"])
        self.assertEqual(res["ship"]["branches"], ["Slope 2026-11-13/t-0600/researcher"])
        res, labels, _, err = run("explore.js", dict(self.Q), dict(H, ticket="T-0600", nested=True))
        self.assertNotIn("ship", labels)
        bad = shipped("T-0600", "Slope x @ a (1 files) REFUSED: off-template")
        res, labels, _, err = run("explore.js", dict(self.Q, ship=[bad, bad]), dict(H, ticket="T-0600", nested=False))
        self.assertEqual((labels.count("ship"), res["ship"]["status"]), (1, "refused"))

    def test_explore_by_direction_ships_the_slug_once(self):
        # #136 item 4: through inbox.py --ship-slug, under --check's guards and scope
        res, labels, _, err = run("explore.js", {"direction": [DIR], "next": [NEXT], "journal": [JOURNAL],
                                                 "lead": [{"items": [], "report": "r", "next_picks": []}],
                                                 "ship": [{"status": "pushed", "output": "home 2026-11-27/explore-dir-1/researcher @ abc1234 (1 files) pushed\nexplore-dir-1: delivered (no ticket)\n"}]}, dict(H, direction="DIR-1", nested=False))
        self.assertIsNone(err, err)
        self.assertEqual(labels.count("ship"), 1)
        self.assertEqual(res["ship"]["status"], "pushed")

    def test_generalize_ships_on_delivery_only(self):
        args = dict(H, ref="P-0009", ticket="T-7", mode="deliver", conjectures=["flat:CONJ-1"], nested=False)
        res, labels, _, err = run("generalize.js", {"children": [{"tests": [{"id": "T-8", "refs": ["flat:CONJ-1"]}]}],
                                                    "close": [{"ok": True, "detail": ""}], "ship": [shipped("T-7", self.LINE)]}, args)
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["children", "close", "ship"])
        self.assertEqual(res["ship"]["status"], "pushed")
        res, labels, _, err = run("generalize.js", {
            "source": [SRC], "prover": ["wrote"], "validate": [GOOD],
            "create": [{"conjectures": ["flat:CONJ-1", "flat:CONJ-3"], "lemmas": [], "error": ""}],
            "packet": [{"packet": "P-0400", "error": ""}], "test specs": [{"specs": []}],
            "file tests": [{"tickets": ["T-8"], "refusals": []}],
            "children": [{"tests": [{"id": "T-8", "refs": ["flat:CONJ-1"]}]}]}, dict(H, ref="P-0009", ticket="T-7", nested=False))
        self.assertIsNone(err, err)
        self.assertNotIn("ship", labels)                       # tests missing: the ticket is not delivered yet
        self.assertEqual(res["ship"]["status"], "not-run")
        self.assertIn("--check T-7", res["ship"]["command"])


if __name__ == "__main__":
    unittest.main()
