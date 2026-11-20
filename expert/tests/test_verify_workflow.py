"""The verify workflow (workflows/verify.js) and its launch guard (2026-10-31).

The workflow holds conclude.md's sequencing in code. These tests run the script under
node with a fake ``agent()``, so the gate is checked without any model: A GAP launches
no B; A CONFIRMED with launch_b launches B with A's brief byte for byte (run B); a
moved statement hash stops B; a lost run is not relaunched; an unlanded run is
relaunched once; a reword pass runs R alone; after a CONFIRMED A the claim's falsifier
comes before B (2026-11-20): none on record files one and blocks the ticket on it, a
counterexample concludes the pass with no B. Skipped where node is not installed.
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
class FalsifierAfterATests(unittest.TestCase):
    """The human's order (2026-11-20): attempt, run A, the falsifier, run B. A falsifier is
    spent only on a proof that survived A; B launches only when it found nothing."""
    run_wf = GateTests.run_wf
    A_OK = tab("CONFIRMED", "awaiting-b", True)
    FILED = {"request": "T-0002", "blocked": True, "waiting_on": ["T-0002"], "refusal": ""}

    def test_no_falsifier_on_record_files_one_and_blocks_the_ticket_instead_of_b(self):
        out, labels, calls = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS), "run A": "r",
                                          "table A": self.A_OK, "falsifier": self.FILED})
        self.assertEqual(labels, ["prepare", "run A", "table A", "falsifier"])
        r = out["result"]
        self.assertEqual(r["outcome"], "awaiting-falsifier")
        self.assertEqual(r["falsifier_request"], "T-0002")
        self.assertEqual(r["pass"], PREP["pass"])
        self.assertIn("stays open", r["reason"])
        stage = calls[-1]
        self.assertEqual(stage["agentType"], "expert:review-chair")
        p = stage["prompt"]
        for want in ("tickets_create", "kind research", "final_to scientist", "blocked",
                     "waiting_on", "T-0001", "never state run A's verdict"):
            self.assertIn(want, p)
        self.assertNotIn("claims_propose_status {", p)

    def test_a_pending_request_is_waited_on_not_filed_again(self):
        f = dict(NO_FALS, request="T-0002", request_status="open")
        prep = dict(PREP, falsifier=f, landed=[{"run": "A", "statement_hash": "abcdef12"}])
        out, labels, calls = self.run_wf({"prepare": prep, "table A": self.A_OK, "falsifier": self.FILED})
        self.assertEqual(labels, ["prepare", "table A", "falsifier"])
        self.assertEqual(out["result"]["outcome"], "awaiting-falsifier")
        self.assertIn("file nothing", calls[-1]["prompt"])
        self.assertIn("T-0002", calls[-1]["prompt"])

    def test_a_rerun_after_a_clean_falsifier_resumes_the_pass_and_launches_b(self):
        f = {"source": "ticket", "on": "T-0002", "evidence": "T-0002 delivered: lab:x-search, nothing found",
             "found": "nothing", "request": "T-0002", "request_status": "delivered",
             "statement_hash": "abcdef12"}
        prep = dict(PREP, falsifier=f, landed=[{"run": "A", "statement_hash": "abcdef12"}])
        done = dict(DONE, run_files=["A.md", "B.md", "decision.md"])
        out, labels, calls = self.run_wf({"prepare": prep, "table A": self.A_OK, "run B": "r",
                                          "table B": tab("CONFIRMED", "confirmed", run="B"), "conclude": done})
        self.assertEqual(labels, ["prepare", "table A", "run B", "table B", "conclude"])
        self.assertIn("kept, not relaunched", " ".join(out["result"]["notes"]))
        b = next(c for c in calls if c["label"] == "run B")["prompt"]
        self.assertNotIn("falsifier", b.lower())           # B stays blind: the brief as before
        self.assertNotIn("T-0002", b)
        self.assertEqual(out["result"]["anomalies"], [])

    def test_a_counterexample_concludes_without_b_or_a_status(self):
        f = {"source": "ticket", "on": "T-0002", "evidence": "T-0002 delivered: lab:x-search found EX-L3",
             "found": "counterexample", "request": "T-0002", "request_status": "delivered",
             "statement_hash": "abcdef12"}
        prep = dict(PREP, falsifier=f, landed=[{"run": "A", "statement_hash": "abcdef12"}])
        out, labels, calls = self.run_wf({"prepare": prep, "table A": self.A_OK,
                                          "conclude": dict(DONE, outcome="falsifier-counterexample")})
        self.assertEqual(labels, ["prepare", "table A", "conclude"])
        r = out["result"]
        self.assertEqual(r["outcome"], "falsifier-counterexample")
        p = calls[-1]["prompt"]
        self.assertIn("found EX-L3", p)                    # the counterexample reaches the record
        self.assertIn("never claims_propose_status", p)
        # review V1 #6: one rule for a counterexample, the decision table's (follow_up kind
        # counterexample): a decision ticket to the human at once, never a prove ticket
        self.assertIn("kind decision", p)
        self.assertIn("to human", p)
        self.assertNotIn("kind prove", p)
        self.assertIn("run B not launched", " ".join(r["notes"]))

    def test_a_status_proposed_on_a_counterexample_is_an_anomaly(self):
        f = dict(FALS, found="counterexample")
        out, _l, _c = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r",
                                   "table A": self.A_OK, "conclude": dict(DONE, proposed_status="proved")})
        self.assertEqual(out["result"]["outcome"], "falsifier-counterexample")
        self.assertIn("ANOMALY", " ".join(out["result"]["notes"]))

    def test_a_falsifier_on_record_launches_b_at_once(self):
        for f, inputs in ((FALS, []),
                          (dict(FALS, source="input", on="s1:GEO-9"), ["GEO-9"]),
                          (dict(FALS, source="parent", on="flat:LEAD-2"), []),
                          (dict(FALS, source="waived", evidence="- 2026-11-20 human: no falsifier needed", found=""), [])):
            _o, labels, _c = self.run_wf({"prepare": dict(PREP, falsifier=f, inputs=inputs), "run A": "r",
                                          "table A": self.A_OK, "run B": "r",
                                          "table B": tab("CONFIRMED", "confirmed", run="B"), "conclude": DONE})
            self.assertEqual(labels, ["prepare", "run A", "table A", "run B", "table B", "conclude"], f)

    def test_a_falsifier_that_does_not_count_is_requested(self):
        # #117's rules, as prove.js holds them: an undeclared input, no evidence, a waiver
        # without the human's thread line do not count
        for f in (dict(FALS, source="input", on="s1:GEO-9"), dict(FALS, evidence=""),
                  dict(FALS, source="waived", evidence="the human said so")):
            out, labels, _c = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r",
                                           "table A": self.A_OK, "falsifier": self.FILED})
            self.assertEqual(labels, ["prepare", "run A", "table A", "falsifier"], f)
            self.assertEqual(out["result"]["outcome"], "awaiting-falsifier")

    def test_a_falsifier_that_did_not_come_back_clean_does_not_count(self):
        """Review V1 #2: only found 'nothing' lets B run (a waiver aside), and a falsifier
        request counts only once it is delivered or closed."""
        for f in (dict(FALS, found=""), dict(FALS, found="unknown"),
                  dict(FALS, source="ticket", on="T-0002", request="T-0002",
                       request_status="in-progress"),
                  dict(FALS, source="ticket", on="T-0002", request="T-0002",
                       request_status="cancelled")):
            out, labels, _c = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r",
                                           "table A": self.A_OK, "falsifier": self.FILED})
            self.assertEqual(labels, ["prepare", "run A", "table A", "falsifier"], f)
            self.assertEqual(out["result"]["outcome"], "awaiting-falsifier", f)
            self.assertIn("not counted", " ".join(out["result"]["notes"]), f)
        for st in ("delivered", "closed"):
            f = dict(FALS, source="ticket", on="T-0002", request="T-0002", request_status=st)
            _o, labels, _c = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r",
                                          "table A": self.A_OK, "run B": "r",
                                          "table B": tab("CONFIRMED", "confirmed", run="B"), "conclude": DONE})
            self.assertIn("run B", labels, st)

    def test_a_falsifier_on_another_wording_does_not_count(self):
        """Review V1 #3: a falsifier recorded on another statement hash never counts; one
        whose hash is unknown counts only as a waiver, with a note."""
        for f, note in ((dict(FALS, statement_hash="00000000"), "another wording"),
                        (dict(FALS, statement_hash=""), "statement hash is unknown"),
                        (dict(FALS, source="waived", found="", statement_hash="00000000",
                              evidence="- 2026-11-20 human: no falsifier needed"), "another wording")):
            out, labels, _c = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r",
                                           "table A": self.A_OK, "falsifier": self.FILED})
            self.assertEqual(labels, ["prepare", "run A", "table A", "falsifier"], f)
            self.assertIn(note, " ".join(out["result"]["notes"]), f)
        f = dict(FALS, source="waived", found="", statement_hash="",
                 evidence="- 2026-11-20 human: no falsifier needed")
        out, labels, _c = self.run_wf({"prepare": dict(PREP, falsifier=f), "run A": "r",
                                       "table A": self.A_OK, "run B": "r",
                                       "table B": tab("CONFIRMED", "confirmed", run="B"), "conclude": DONE})
        self.assertIn("run B", labels)
        self.assertIn("statement hash is unknown", " ".join(out["result"]["notes"]))

    def test_the_request_records_the_statement_hash_and_prepare_reports_it(self):
        _o, _l, calls = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS), "run A": "r",
                                     "table A": self.A_OK, "falsifier": self.FILED})
        self.assertIn("statement hash abcdef12", calls[-1]["prompt"])
        self.assertIn("statement_hash", calls[0]["prompt"])

    def test_without_a_ticket_the_falsifier_stage_is_skipped_and_b_runs(self):
        """Review V1 #4: a pass with no ticket could not be resumed (reviews.py resumes a
        ticket's own pass only), so it waits for no falsifier: B runs, with a note."""
        prep = dict(PREP, ticket="none", falsifier=NO_FALS)
        done = dict(DONE, run_files=["A.md", "B.md", "decision.md"])
        out, labels, _c = self.run_wf({"prepare": prep, "run A": "r", "table A": self.A_OK,
                                       "run B": "r", "table B": tab("CONFIRMED", "confirmed", run="B"),
                                       "conclude": done}, ticket=None)
        self.assertEqual(labels, ["prepare", "run A", "table A", "run B", "table B", "conclude"])
        self.assertNotEqual(out["result"]["outcome"], "awaiting-falsifier")
        self.assertIn("no verify ticket", " ".join(out["result"]["notes"]))

    def test_the_request_goes_to_the_researcher_the_rule_names(self):
        """Review V1 #5: the addressee is reviews.py researcher-for's answer, not a guess."""
        out, labels, calls = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS), "run A": "r",
                                          "table A": self.A_OK, "falsifier": self.FILED})
        self.assertIn("to researcher@main", calls[-1]["prompt"])
        self.assertIn("reviews.py researcher-for", calls[0]["prompt"])
        for who in ("human", ""):
            prep = dict(PREP, falsifier=NO_FALS, researcher=who,
                        researcher_why="bears_on names several Researchers")
            out, labels, calls = self.run_wf({"prepare": prep, "run A": "r", "table A": self.A_OK,
                                              "falsifier": {"request": "", "blocked": True,
                                                            "waiting_on": ["human"], "refusal": ""}})
            p = calls[-1]["prompt"]
            self.assertNotIn("tickets_create", p, who)
            self.assertIn("waiting_on [human]", p, who)
            self.assertEqual(out["result"]["outcome"], "awaiting-falsifier")
            self.assertIn("no Researcher to ask", " ".join(out["result"]["notes"]), who)

    def test_a_negative_a_or_a_reword_pass_spends_no_falsifier(self):
        out, labels, _ = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS), "run A": "r",
                                      "table A": tab("GAP", "single-negative"), "conclude": DONE})
        self.assertEqual(labels, ["prepare", "run A", "table A", "conclude"])
        prep = dict(PREP, falsifier=NO_FALS, bundle="/s/bundle.md")
        prep["pass"] = "2026-10-31-reword"
        _o, labels, _ = self.run_wf({"prepare": prep, "run R": "r", "table R": tab("CONFIRMED", "confirmed", True, run="R"),
                                     "conclude": dict(DONE, run_files=["R.md"])}, mode="reword", base_pass="2026-10-01")
        self.assertEqual(labels, ["prepare", "run R", "table R", "conclude"])

    def test_a_refused_request_parks_on_the_human(self):
        out, labels, _ = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS), "run A": "r", "table A": self.A_OK,
                                      "falsifier": {"request": "", "blocked": True, "waiting_on": ["human"],
                                                    "refusal": "chain: not a liaison"}})
        self.assertEqual(out["result"]["outcome"], "awaiting-falsifier")
        self.assertIn("not a liaison", out["result"]["reason"])
        self.assertIn("human", " ".join(out["result"]["notes"]))

    def test_the_prepare_stage_is_asked_for_the_falsifier(self):
        _o, _l, calls = self.run_wf({"prepare": dict(PREP, falsifier=NO_FALS), "run A": "r",
                                     "table A": tab("GAP", "single-negative"), "conclude": DONE})
        p = calls[0]["prompt"]
        self.assertIn("falsifier", p)
        self.assertIn("waived", p)


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
