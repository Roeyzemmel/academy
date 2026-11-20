"""The verify workflow (workflows/verify.js) and its launch guard (2026-10-31).

The workflow holds conclude.md's sequencing in code. These tests run the script under
node with a fake ``agent()``, so the gate is checked without any model: A GAP launches
no B; A CONFIRMED with launch_b launches B with A's brief byte for byte (run B); a
moved statement hash stops B; a lost run is not relaunched; an unlanded run is
relaunched once; a reword pass runs R alone; a GAP verdict of A, or of B after a
CONFIRMED A, files a falsifier request when none is on record or pending, blocking nothing,
and a counterexample on record concludes the pass with no B (2026-11-20). Skipped where node
is not installed.
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
  calls.push({ label: opts.label, agentType: opts.agentType, model: opts.model, prompt })
  const ans = plan[opts.label]
  if (ans === undefined) throw new Error('unplanned agent ' + opts.label)
  return ans
}
const body = new Function('args', 'agent', 'phase', 'log', 'return (async () => {' + src + '})()')
// the stage-order tests run nested, as from the inbox (no ship stage); the ship tests pass nested: false
// the max-tier launch models as the inbox passes them (T-1682); a test passes models: null to resolve them
body(Object.assign({ nested: true, models: { 'expert:rigor-reviewer': 'fable', 'expert:referee': 'fable', 'researcher:experiment-reviewer': 'fable', 'researcher:prover': 'fable' } }, plan.__args), agent, () => {}, () => {}).then(
  r => console.log(JSON.stringify({ result: r, calls })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""

# the claim's falsifier as the prepare stage reports it (2026-11-20): on record, found nothing
FALS = {"source": "claim", "on": "", "evidence": "lab:x-search (results/x.json): nothing found",
        "found": "nothing", "request": "", "request_status": "", "statement_hash": "abcdef12"}
NO_FALS = {"source": "none", "on": "", "evidence": "", "found": "", "request": "",
           "request_status": "", "statement_hash": ""}
PREP = {"ok": True, "stop_reason": "", "pass": "2026-10-31-T-0001",
        "pass_dir": "/lib/reviews/paper/x/2026-10-31-T-0001", "statement_hash": "abcdef12",
        "location": "sections/a.tex:lem:x", "bundle": "", "ticket": "T-0001",
        "falsifier": FALS, "inputs": [],
        "researcher": "researcher@main", "researcher_why": "the Researcher owning the namespace"}


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

    def test_a_resumed_pass_concludes_what_landed(self):
        """#89: a rerun of the ticket resumes its open pass: A (GAP) landed on this
        statement is tabled and concluded, not relaunched."""
        prep = dict(PREP, landed=[{"run": "A", "statement_hash": "abcdef12"}])
        out, labels, _ = self.run_wf({"prepare": prep, "table A": tab("GAP", "single-negative"),
                                      "conclude": DONE})
        self.assertEqual(labels, ["prepare", "table A", "conclude"])
        self.assertIn("kept, not relaunched", " ".join(out["result"]["notes"]))

    def test_a_landed_file_on_another_statement_is_never_concluded_on(self):
        """#89 review: prepare listed nothing, but the table reads an older A.md: stop."""
        t = dict(tab("GAP", "single-negative"), run_hash="00000000")
        out, labels, _ = self.run_wf({"prepare": PREP, "run A": "r", "table A": t})
        self.assertEqual(out["result"]["outcome"], "stale-pass")
        self.assertNotIn("conclude", labels)
        self.assertIn("reviews.py abandon", out["result"]["reason"])

    def test_a_resumed_pass_with_b_but_no_a_is_not_resumed(self):
        prep = dict(PREP, landed=[{"run": "B", "statement_hash": "abcdef12"}])
        out, labels, _ = self.run_wf({"prepare": prep})
        self.assertEqual((labels, out["result"]["outcome"]), (["prepare"], "not-started"))

    def test_a_resumed_pass_keeps_its_earlier_files_without_an_anomaly(self):
        prep = dict(PREP, landed=[{"run": "A", "statement_hash": "abcdef12"}])
        done = dict(DONE, run_files=["A.md", "A-2.md", "A-noverdict.md", "decision.md"])
        out, labels, _ = self.run_wf({"prepare": prep, "table A": tab("GAP", "single-negative"),
                                      "conclude": done})
        self.assertEqual(out["result"]["anomalies"], [])

    def test_a_resumed_pass_on_another_statement_is_not_mixed(self):
        prep = dict(PREP, landed=[{"run": "A.md", "statement_hash": "00000000"}])
        out, labels, _ = self.run_wf({"prepare": prep})
        self.assertEqual(labels, ["prepare"])
        self.assertEqual(out["result"]["outcome"], "not-started")
        self.assertIn("reviews.py abandon", out["result"]["reason"])

    def test_a_moved_statement_stops_b(self):
        out, labels, _ = self.run_wf({"prepare": PREP, "run A": "r",
                                      "table A": tab("CONFIRMED", "awaiting-b", True, "ffff0000"),
                                      "conclude": DONE})
        self.assertNotIn("run B", labels)
        self.assertIn("statement moved", " ".join(out["result"]["notes"]))

    def test_a_lost_run_is_not_relaunched_and_an_unlanded_one_is(self):
        # lost on the max model: one relaunch on opus (T-1682); lost again: nothing further
        out, labels, calls = self.run_wf({"prepare": PREP, "run A": None, "run A (opus fallback)": None,
                                          "conclude": DONE})
        self.assertEqual(labels, ["prepare", "run A", "run A (opus fallback)", "conclude"])
        self.assertEqual([c.get("model") for c in calls[1:3]], ["fable", "opus"])
        self.assertIn("run A lost", " ".join(out["result"]["notes"]))
        # lost on opus itself: never relaunched
        _o, labels, _ = self.run_wf({"prepare": PREP, "run A": None, "conclude": DONE},
                                    models={"expert:rigor-reviewer": "opus"})
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

    def test_the_hash_is_the_engine_hash_of_the_claim(self):
        # T-0464, T-1179: prepare and the table hash the claim through the registry engine
        # (`reviews.py hash --claim`), never a hand-copied extract (`hash --file`), which
        # for s1 records dropped the '## Statement' heading the engine hashes
        _o, _l, calls = self.run_wf({
            "prepare": PREP, "run A": "report", "table A": tab("CONFIRMED", "awaiting-b", True),
            "run B": "report", "table B": tab("CONFIRMED", "confirmed", run="B"),
            "conclude": DONE})
        for label in ("prepare", "table A", "table B"):
            p = next(c for c in calls if c["label"] == label)["prompt"]
            self.assertIn("reviews.py hash --claim paper:lem:x", p, label)
            self.assertNotIn("hash --file", p, label)

    def test_a_reword_pass_hashes_the_new_statement_through_the_engine(self):
        prep = dict(PREP, bundle="/s/bundle.md")
        prep["pass"] = "2026-10-31-reword"
        _o, _l, calls = self.run_wf({
            "prepare": prep, "run R": "r", "table R": tab("CONFIRMED", "confirmed", True, run="R"),
            "conclude": dict(DONE, run_files=["R.md"])}, mode="reword", base_pass="2026-10-01")
        p = next(c for c in calls if c["label"] == "prepare")["prompt"]
        self.assertIn("reviews.py hash --claim paper:lem:x", p)
        t = next(c for c in calls if c["label"] == "table R")["prompt"]
        self.assertIn("reviews.py hash --claim paper:lem:x", t)

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


@unittest.skipUnless(NODE, "node is not installed")
class FalsifierOnGapTests(unittest.TestCase):
    """The human's design (2026-11-20, revised the same day): a falsifier is triggered by a
    GAP verdict, never a gate between A and B. A GAP of run A (or of B after a CONFIRMED A)
    with no clean falsifier on record for this statement hash and none pending files the
    request, naming the gap, alongside the follow-up repair; it blocks nothing."""
    run_wf = GateTests.run_wf
    A_OK = tab("CONFIRMED", "awaiting-b", True)
    A_GAP = dict(tab("GAP", "single-negative"), blocking_step="Step 3: the lift is not shown to be injective")
    FILED = {"request": "T-0002", "refusal": ""}

    def test_a_confirmed_a_launches_b_at_once_with_no_falsifier_stage(self):
        for f in (NO_FALS, FALS):
            done = dict(DONE, run_files=["A.md", "B.md", "decision.md"])
            out, labels, calls = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r",
                                              "table A": self.A_OK, "run B": "r",
                                              "table B": tab("CONFIRMED", "confirmed", run="B"),
                                              "conclude": done})
            self.assertEqual(labels, ["prepare", "run A", "table A", "run B", "table B", "conclude"], f)
            self.assertNotEqual(out["result"]["outcome"], "awaiting-falsifier")
            self.assertIsNone(out["result"]["falsifier_request"])
            b = next(c for c in calls if c["label"] == "run B")["prompt"]
            self.assertNotIn("falsifier", b.lower())           # B stays blind: the brief as before

    def test_an_a_gap_with_none_on_record_files_the_request_and_concludes(self):
        out, labels, calls = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS), "run A": "r",
                                          "table A": self.A_GAP, "falsifier": self.FILED,
                                          "conclude": DONE})
        self.assertEqual(labels, ["prepare", "run A", "table A", "falsifier", "conclude"])
        r = out["result"]
        self.assertEqual(r["outcome"], "x")                    # the concluder's outcome, as before
        self.assertEqual(r["falsifier_request"], "T-0002")
        p = next(c for c in calls if c["label"] == "falsifier")["prompt"]
        self.assertIn("tickets_create", p)
        self.assertIn("to researcher@main", p)
        self.assertIn("final_to scientist", p)
        self.assertIn("statement hash abcdef12", p)
        self.assertIn("Step 3: the lift is not shown to be injective", p)   # the request targets the gap
        self.assertIn("never block", p)
        self.assertNotIn("status blocked", p)
        c = calls[-1]["prompt"]
        self.assertIn("T-0002", c)                             # named in the record, beside the repair
        self.assertIn("sections 2-6", c)                       # the conclusion as before
        self.assertIn("blocking step", next(x for x in calls if x["label"] == "table A")["prompt"])

    def test_an_a_gap_with_a_clean_falsifier_on_record_or_one_pending_files_none(self):
        pending = dict(NO_FALS, source="none", request="T-0009", request_status="in-progress",
                       statement_hash="abcdef12")
        unknown = dict(NO_FALS, request="T-0009", request_status="open")
        for f in (FALS, pending, unknown):
            out, labels, _c = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r",
                                           "table A": self.A_GAP, "conclude": DONE})
            self.assertEqual(labels, ["prepare", "run A", "table A", "conclude"], f)
            self.assertIsNone(out["result"]["falsifier_request"])
            self.assertIn("no falsifier request", " ".join(out["result"]["notes"]))

    def test_a_falsifier_that_does_not_count_is_requested_again(self):
        """The clean/hash checks decide whether a request is needed: one on another wording,
        one that has not come back clean, a pending request on another wording."""
        for f in (dict(FALS, statement_hash="00ff00ff"), dict(FALS, statement_hash=""),
                  dict(FALS, found=""), dict(FALS, source="input", on="flat:GEO-9"),
                  dict(NO_FALS, request="T-0009", request_status="open", statement_hash="00ff00ff")):
            out, labels, _c = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r",
                                           "table A": self.A_GAP, "falsifier": self.FILED,
                                           "conclude": DONE})
            self.assertEqual(labels, ["prepare", "run A", "table A", "falsifier", "conclude"], f)

    def test_a_b_gap_after_a_confirmed_a_files_the_request(self):
        done = dict(DONE, run_files=["A.md", "B.md", "decision.md"])
        out, labels, calls = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS), "run A": "r",
                                          "table A": self.A_OK, "run B": "r",
                                          "table B": dict(tab("GAP", "disagreement", run="B"), blocking_step="Lemma 2 case b"),
                                          "falsifier": self.FILED, "conclude": done})
        self.assertEqual(labels, ["prepare", "run A", "table A", "run B", "table B", "falsifier", "conclude"])
        self.assertEqual(out["result"]["falsifier_request"], "T-0002")
        self.assertIn("Lemma 2 case b", next(c for c in calls if c["label"] == "falsifier")["prompt"])

    def test_disproved_is_unchanged(self):
        out, labels, _c = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS), "run A": "r",
                                       "table A": tab("DISPROVED", "disproved"), "conclude": DONE})
        self.assertEqual(labels, ["prepare", "run A", "table A", "conclude"])
        self.assertIsNone(out["result"]["falsifier_request"])

    def test_no_researcher_files_nothing_and_notes_it(self):
        for who in ("human", ""):
            prep = dict(PREP, falsifier=NO_FALS, researcher=who, researcher_why="no rule names one")
            out, labels, _c = self.run_wf({"prepare": prep, "run A": "r", "table A": self.A_GAP, "conclude": DONE})
            self.assertEqual(labels, ["prepare", "run A", "table A", "conclude"], who)
            self.assertIn("no Researcher to ask", " ".join(out["result"]["notes"]))

    def test_without_a_ticket_the_request_is_still_filed(self):
        out, labels, calls = self.run_wf({"prepare": dict(PREP, ticket="none", falsifier=NO_FALS), "run A": "r",
                                          "table A": self.A_GAP, "falsifier": self.FILED, "conclude": DONE},
                                         ticket=None)
        self.assertEqual(labels, ["prepare", "run A", "table A", "falsifier", "conclude"])
        self.assertNotIn("parent", next(c for c in calls if c["label"] == "falsifier")["prompt"].split("refs [")[1][:40])

    def test_a_refused_or_lost_request_is_noted_and_the_pass_concludes(self):
        for ans, word in (({"request": "", "refusal": "chain: not a liaison"}, "not a liaison"),
                          (None, "returned nothing")):
            out, labels, _c = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS), "run A": "r",
                                           "table A": self.A_GAP, "falsifier": ans, "conclude": DONE})
            self.assertEqual(labels[-1], "conclude")
            self.assertIsNone(out["result"]["falsifier_request"])
            self.assertIn(word, " ".join(out["result"]["notes"]))

    def test_a_counterexample_on_record_still_concludes_without_b_or_a_status(self):
        f = {"source": "ticket", "on": "T-0002", "evidence": "T-0002 delivered: lab:x-search found EX-L3",
             "found": "counterexample", "request": "T-0002", "request_status": "delivered",
             "statement_hash": "abcdef12"}
        out, labels, calls = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r", "table A": self.A_OK,
                                          "conclude": dict(DONE, outcome="falsifier-counterexample")})
        self.assertEqual(labels, ["prepare", "run A", "table A", "conclude"])
        r = out["result"]
        self.assertEqual(r["outcome"], "falsifier-counterexample")
        p = calls[-1]["prompt"]
        self.assertIn("found EX-L3", p)
        self.assertIn("never claims_propose_status", p)
        self.assertIn("kind decision", p)
        self.assertIn("to human", p)
        self.assertNotIn("kind prove", p)

    def test_a_status_proposed_on_a_counterexample_is_an_anomaly(self):
        f = dict(FALS, found="counterexample")
        out, _l, _c = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r",
                                   "table A": self.A_OK, "conclude": dict(DONE, proposed_status="proved")})
        self.assertEqual(out["result"]["outcome"], "falsifier-counterexample")
        self.assertIn("ANOMALY", " ".join(out["result"]["notes"]))

    def test_a_reword_pass_spends_no_falsifier(self):
        prep = dict(PREP, falsifier=NO_FALS, bundle="/s/bundle.md")
        prep["pass"] = "2026-10-31-reword"
        _o, labels, _ = self.run_wf({"prepare": prep, "run R": "r", "table R": tab("GAP", "gap", run="R"),
                                     "conclude": dict(DONE, run_files=["R.md"])}, mode="reword", base_pass="2026-10-01")
        self.assertEqual(labels, ["prepare", "run R", "table R", "conclude"])

    def test_the_prepare_stage_is_asked_for_the_falsifier_and_a_pending_request(self):
        _o, _l, calls = self.run_wf({"prepare": dict(PREP, falsifier=FALS), "run A": "r",
                                     "table A": tab("GAP", "single-negative"), "conclude": DONE})
        p = calls[0]["prompt"]
        self.assertIn("falsifier", p)
        self.assertIn("waived", p)
        self.assertIn("Falsifier for paper:lem:x", p)
        self.assertNotIn("awaiting its falsifier", p)


@unittest.skipUnless(NODE, "node is not installed")
class AmendAfterATests(unittest.TestCase):
    """The human's design (2026-11-20): A CONFIRMED with a suggested dependency pauses the
    pass; the producer adds it (a prove ticket, mode repair); on the rerun B reviews the
    amended proof in amend mode, told the suggestion only."""
    run_wf = GateTests.run_wf
    A_SUG = dict(tab("CONFIRMED", "awaiting-amendment", False), add_dependency=["paper:lem:lift"])
    FILED = {"request": "T-0003", "blocked": True, "waiting_on": ["T-0003"], "refusal": ""}
    NO_AM = {"request": "", "request_status": "", "attempt": ""}
    DONE_AM = {"request": "T-0003", "request_status": "delivered",
               "attempt": "proofs/lem-x/attempt-3.md",
               "reviewed_attempt": "proofs/lem-x/attempt-2.md"}
    LANDED_A = [{"run": "A", "statement_hash": "abcdef12"}]
    BUNDLE = {"bundle": "/lib/scratch/amend-T-0001.md", "refusal": ""}

    def test_a_suggestion_files_the_repair_and_blocks_the_ticket_instead_of_b(self):
        am = dict(self.NO_AM, attempt="proofs/lem-x/attempt-2.md")     # the attempt A reviews
        out, labels, calls = self.run_wf({"prepare": dict(PREP, amendment=am), "run A": "r",
                                          "table A": self.A_SUG, "amendment": self.FILED})
        self.assertEqual(labels, ["prepare", "run A", "table A", "amendment"])
        self.assertIn("run A reviewed proofs/lem-x/attempt-2.md", calls[-1]["prompt"])
        r = out["result"]
        self.assertEqual(r["outcome"], "awaiting-amendment")
        self.assertEqual(r["amendment_request"], "T-0003")
        self.assertEqual(r["add_dependency"], ["paper:lem:lift"])
        self.assertIn("stays open", r["reason"])
        stage = calls[-1]
        self.assertEqual(stage["agentType"], "expert:review-chair")
        for want in ("tickets_create", "kind prove", "mode repair", "paper:lem:lift",
                     "depends_on", "blocked", "waiting_on", "T-0001"):
            self.assertIn(want, stage["prompt"])
        self.assertNotIn("run B", labels)

    def test_a_placeholder_attempt_is_no_record_and_no_attempt_files_no_repair(self):
        """Second look at 7044d82: '(no attempt reported)' always 'differed' from the current
        attempt; and a repair asked for with no attempt on record cannot be checked."""
        am = dict(self.DONE_AM, reviewed_attempt="(no attempt reported)")
        prep = dict(PREP, amendment=am, landed=self.LANDED_A, inputs=["paper:lem:lift"])
        out, labels, calls = self.run_wf({"prepare": prep, "table A": self.A_SUG,
                                          "amendment": [{"request": "", "blocked": True, "waiting_on": ["human"], "refusal": ""}]})
        self.assertNotIn("run B", labels)
        self.assertIn("did not record the attempt run A reviewed", " ".join(out["result"]["notes"]) + out["result"].get("reason", ""))
        prep = dict(PREP, amendment=dict(self.NO_AM, attempt=""))
        out, labels, calls = self.run_wf({"prepare": prep, "run A": "r", "table A": self.A_SUG,
                                          "amendment": [{"request": "", "blocked": True, "waiting_on": ["human"], "refusal": ""}]})
        amend = next(c for c in calls if c["label"] == "amendment")["prompt"]
        self.assertIn("file nothing", amend)
        self.assertIn("is not on record", amend)

    def test_a_pending_amendment_is_waited_on_not_filed_again(self):
        am = dict(self.NO_AM, request="T-0003", request_status="open")
        prep = dict(PREP, amendment=am, landed=self.LANDED_A)
        out, labels, calls = self.run_wf({"prepare": prep, "table A": self.A_SUG, "amendment": self.FILED})
        self.assertEqual(labels, ["prepare", "table A", "amendment"])
        self.assertEqual(out["result"]["outcome"], "awaiting-amendment")
        self.assertIn("file nothing", calls[-1]["prompt"])

    def test_a_rerun_after_the_amendment_launches_b_in_amend_mode(self):
        prep = dict(PREP, amendment=self.DONE_AM, landed=self.LANDED_A, inputs=["paper:lem:lift"])
        done = dict(DONE, run_files=["A.md", "B.md", "decision.md"])
        out, labels, calls = self.run_wf({"prepare": prep, "table A": self.A_SUG,
                                          "amend-brief": self.BUNDLE, "run B": "r",
                                          "table B": tab("CONFIRMED", "confirmed-modulo", run="B"),
                                          "conclude": done})
        self.assertEqual(labels, ["prepare", "table A", "amend-brief", "run B", "table B", "conclude"])
        brief = next(c for c in calls if c["label"] == "amend-brief")["prompt"]
        self.assertIn("reviews.py amend-brief", brief)
        self.assertIn("proofs/lem-x/attempt-3.md", brief)
        b = next(c for c in calls if c["label"] == "run B")["prompt"]
        self.assertIn("amend mode", b)
        self.assertIn(self.BUNDLE["bundle"], b)
        self.assertIn("run: B", b)
        self.assertNotIn("CONFIRMED", b)                 # told the suggestion only, via the bundle
        tb = next(c for c in calls if c["label"] == "table B")["prompt"]
        self.assertIn("A.md", tb)                        # the amend B is tabled against A
        self.assertIn("mode amend", calls[-1]["prompt"])
        self.assertEqual(out["result"]["anomalies"], [])

    def test_an_amendment_that_does_not_list_the_dependency_is_not_taken(self):
        prep = dict(PREP, amendment=self.DONE_AM, landed=self.LANDED_A, inputs=["paper:lem:other"])
        out, labels, calls = self.run_wf({"prepare": prep, "table A": self.A_SUG, "amendment": self.FILED})
        self.assertEqual(labels, ["prepare", "table A", "amendment"])
        self.assertEqual(out["result"]["outcome"], "awaiting-amendment")
        self.assertIn("paper:lem:lift", " ".join(out["result"]["notes"]))

    def test_no_falsifier_stage_comes_before_the_amendment(self):
        am = dict(self.NO_AM, attempt="proofs/lem-x/attempt-2.md")
        out, labels, _ = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS, amendment=am),
                                      "run A": "r", "table A": self.A_SUG, "amendment": self.FILED})
        self.assertEqual(labels, ["prepare", "run A", "table A", "amendment"])
        self.assertEqual(out["result"]["outcome"], "awaiting-amendment")

    def test_a_landed_amend_b_is_tabled_not_rebriefed(self):
        prep = dict(PREP, amendment=self.DONE_AM, inputs=["paper:lem:lift"],
                    landed=self.LANDED_A + [{"run": "B", "statement_hash": "abcdef12"}])
        _o, labels, _ = self.run_wf({"prepare": prep, "table A": self.A_SUG,
                                     "table B": tab("CONFIRMED", "confirmed-modulo", run="B"),
                                     "conclude": dict(DONE, run_files=["A.md", "B.md"])})
        self.assertEqual(labels, ["prepare", "table A", "table B", "conclude"])

    def _not_done(self, am, inputs=("paper:lem:lift",), a_tab=None):
        prep = dict(PREP, amendment=dict(self.DONE_AM, **am), landed=self.LANDED_A,
                    inputs=list(inputs))
        out, labels, calls = self.run_wf({"prepare": prep, "table A": a_tab or self.A_SUG,
                                          "amendment": self.FILED})
        self.assertEqual(labels, ["prepare", "table A", "amendment"], out)
        self.assertEqual(out["result"]["outcome"], "awaiting-amendment")
        return out, calls[-1]["prompt"]

    def test_no_b_without_a_repair_this_pass_filed(self):
        """Review fix 3: the dependencies being declared already is not the amendment."""
        _o, p = self._not_done({"request": "", "request_status": ""})
        self.assertIn("tickets_create", p)

    def test_no_b_when_the_repair_did_not_end_delivered_or_closed(self):
        _o, p = self._not_done({"request_status": "rejected"})
        self.assertIn("human", p)
        self.assertIn("rejected", p)

    def test_no_b_when_the_attempt_is_the_one_a_reviewed(self):
        _o, p = self._not_done({"attempt": "proofs/lem-x/attempt-2.md"})
        self.assertIn("human", p)
        self.assertIn("attempt", p)
        _o, p = self._not_done({"reviewed_attempt": ""})
        self.assertIn("human", p)

    def test_the_pinpoint_counts(self):
        sug = dict(self.A_SUG, add_dependency=["bib:LMW16#Thm11"])
        out, _p = self._not_done({}, inputs=["bib:LMW16"], a_tab=sug)
        self.assertIn("bib:LMW16#Thm11", " ".join(out["result"]["notes"]))
        out, _p = self._not_done({}, inputs=["LMW16#Thm11"], a_tab=sug)    # the namespace counts too
        prep = dict(PREP, amendment=self.DONE_AM, landed=self.LANDED_A, inputs=["bib:LMW16#Thm-11"])
        _o, labels, _ = self.run_wf({"prepare": prep, "table A": sug, "amend-brief": self.BUNDLE,
                                     "run B": "r", "table B": tab("CONFIRMED", "confirmed-modulo", run="B"),
                                     "conclude": dict(DONE, run_files=["A.md", "B.md"])})
        self.assertIn("run B", labels)                   # canonical spelling: Thm-11 == Thm11

    def test_the_repair_ask_records_the_attempt_and_the_verify_marker(self):
        am = dict(self.NO_AM, attempt="proofs/lem-x/attempt-2.md")
        _o, _l, calls = self.run_wf({"prepare": dict(PREP, amendment=am), "run A": "r",
                                     "table A": self.A_SUG, "amendment": self.FILED})
        p = calls[-1]["prompt"]
        self.assertIn("amendment for verify T-0001 pass 2026-10-31-T-0001", p)
        self.assertIn("run A reviewed proofs/lem-x/attempt-2.md", p)
        self.assertIn("no verify ticket", p)

    def test_the_table_decides_amending_not_the_verdict_alone(self):
        """Review fix 6 (and 5): a CONFIRMED A whose suggestion the table refused is not an
        amend pass."""
        t = dict(tab("CONFIRMED", "single-negative", False), add_dependency=["a lemma in words"])
        out, labels, _ = self.run_wf({"prepare": dict(PREP, amendment=self.NO_AM), "run A": "r",
                                      "table A": t, "conclude": DONE})
        self.assertEqual(labels, ["prepare", "run A", "table A", "conclude"])
        t = dict(tab("CONFIRMED", "awaiting-amendment", False), add_dependency=[])
        out, labels, _ = self.run_wf({"prepare": dict(PREP, amendment=self.NO_AM), "run A": "r",
                                      "table A": t, "conclude": DONE})
        self.assertEqual(labels, ["prepare", "run A", "table A", "conclude"])
        self.assertTrue(any("ANOMALY" in n for n in out["result"]["notes"]), out["result"]["notes"])

    def test_the_prepare_stage_is_asked_for_the_amendment(self):
        _o, _l, calls = self.run_wf({"prepare": PREP, "run A": "r",
                                     "table A": tab("GAP", "single-negative"), "conclude": DONE})
        self.assertIn("amendment", calls[0]["prompt"])
        tab_a = next(c for c in calls if c["label"] == "table A")["prompt"]
        self.assertIn("add_dependency", tab_a)


@unittest.skipUnless(NODE, "node is not installed")
class MaxTierModelTests(unittest.TestCase):
    """T-1682: the reviewers launch on the workspace's max tier, never a hard-coded opus."""
    run_wf = GateTests.run_wf
    PLAN = {"prepare": PREP, "run A": "r", "table A": tab("CONFIRMED", "awaiting-b", True),
            "run B": "r", "table B": tab("CONFIRMED", "confirmed", run="B"),
            "conclude": dict(DONE, run_files=["A.md", "B.md"])}

    def test_both_runs_launch_on_the_model_the_args_give(self):
        _o, _l, calls = self.run_wf(dict(self.PLAN))
        self.assertEqual([c.get("model") for c in calls if c["label"].startswith("run ")], ["fable", "fable"])

    def test_without_args_one_chair_stage_resolves_it(self):
        for said, want in (("fable\n", "fable"), ("opus", "opus")):
            out, labels, calls = self.run_wf(dict(self.PLAN, **{"model expert:rigor-reviewer": {"output": said}}),
                                             models=None)
            self.assertEqual(labels, ["prepare", "model expert:rigor-reviewer", "run A", "table A",
                                      "run B", "table B", "conclude"])
            stage = calls[1]
            self.assertEqual(stage["agentType"], "expert:review-chair")
            self.assertIn("models.py agent expert:rigor-reviewer --launch", stage["prompt"])
            self.assertEqual([c.get("model") for c in calls if c["label"].startswith("run ")], [want, want])
            self.assertEqual(out["result"]["launch_models"], {"expert:rigor-reviewer": want})

    def test_a_fallback_reaches_the_record_and_the_ticket(self):
        out, labels, calls = self.run_wf({"prepare": PREP, "run A": None, "run A (opus fallback)": "r",
                                          "table A": tab("GAP", "single-negative"), "conclude": DONE})
        self.assertEqual(labels, ["prepare", "run A", "run A (opus fallback)", "table A", "conclude"])
        self.assertEqual(out["result"]["model_fallbacks"], ["run A: fable -> opus"])
        conclude = calls[-1]["prompt"]
        self.assertIn("relaunched once on opus", conclude)             # the process notes, for the record
        self.assertIn("say so in the record, the ticket result and its thread", conclude)
        self.assertEqual(out["result"]["anomalies"], [])


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


@unittest.skipUnless(NODE, "node is not installed")
class ShipTests(unittest.TestCase):
    """docs/workflows.md, "Shipping is a step of the workflow": a standalone pass ships once, by the
    inbox's own --check (which reads the ticket's state itself); a nested pass never."""
    run_wf = GateTests.run_wf
    PLAN = {"prepare": PREP, "run A": "r", "table A": tab("GAP", "single-negative"), "conclude": DONE}
    OUT = "T-0001: delivered (delivered)\nlibrary 2026-11-13/t-0001/expert @ abc (3 files) pushed\n"

    def test_standalone_ships_once_after_conclude(self):
        out, labels, calls = self.run_wf(dict(self.PLAN, ship={"status": "pushed", "detail": "", "branches": [], "output": self.OUT}),
                                         nested=False, root="/acad")
        self.assertEqual(labels, ["prepare", "run A", "table A", "conclude", "ship"])
        self.assertEqual(calls[-1]["agentType"], "expert:review-chair")
        self.assertIn("py /acad/expert/scripts/inbox.py --check T-0001", calls[-1]["prompt"])
        self.assertEqual(out["result"]["ship"]["status"], "pushed")

    def test_nested_never_ships(self):
        out, labels, _ = self.run_wf(dict(self.PLAN))
        self.assertNotIn("ship", labels)
        self.assertNotIn("ship", out["result"])

    def test_a_refusal_is_returned_and_noted_once(self):
        bad = {"status": "pushed", "detail": "", "branches": [],
               "output": "T-0001: delivered (delivered)\nlibrary 2026-11-13/t-0001/expert @ abc (3 files) PUSH FAILED: gate\n"}
        out, labels, _ = self.run_wf(dict(self.PLAN, ship=bad), nested=False)
        self.assertEqual(labels.count("ship"), 1)
        self.assertEqual(out["result"]["ship"]["status"], "refused")
        self.assertIn("ship stage was refused", " ".join(out["result"]["notes"]))

    def test_no_ticket_is_not_run(self):
        out, labels, _ = self.run_wf(dict(self.PLAN, prepare=dict(PREP, ticket="none")), ticket=None, nested=False)
        self.assertNotIn("ship", labels)
        self.assertEqual(out["result"]["ship"]["command"],
                         "py scripts/ship.py checkpoint --ticket verify-paper-lem-x --role expert --only library board")


if __name__ == "__main__":
    unittest.main()
