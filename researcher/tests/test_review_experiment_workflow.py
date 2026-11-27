"""The review-experiment workflow (workflows/review-experiment.js) and its launch guard.

The workflow holds the experiment review's sequencing in code (2026-10-31). The script
runs under node with a fake ``agent()`` keyed by label, so the gate is checked without a
model: A BROKEN -> no B; A SOUND -> B, with reviews.py brief's text for run B and nothing
of A; an unlanded run -> one relaunch; a lost run -> stop; a clean clear -> claim-keeper
gets decide's grounds verbatim; grounds problems -> evidence only; settle-audit plans
candidates only after a cleared audit, at most three. The script's brief is pinned byte
for byte to reviews.brief. Skipped where node is not installed.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import _fixtures  # noqa: F401  (puts the plugin's scripts on sys.path)
import reviews  # noqa: E402
import review_launch_guard as guard  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SCRIPT = os.path.join(PLUGIN, "workflows", "review-experiment.js")
NODE = shutil.which("node")
SUBJ = "lab:ew-check"

# answers per label are lists, consumed in order (a label called twice gets the next one)
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


def dec(state, verdicts=(), grounds=None, problems=(), status=None, repro=""):
    return {"state": state, "next": "", "verdicts": list(verdicts), "proposed_status": status,
            "grounds": grounds, "grounds_problems": list(problems), "reasons": [],
            "reproduction": repro}


def prep(state="need-A", **kw):
    p = {"ok": True, "stop_reason": "", "report": "P-0009", "result": "results/x.json",
         "has_candidates": False, "decide": dec(state)}
    p.update(kw)
    return p


GROUNDS = {"basis": "computation", "commit": "abc123", "outcome": "supports",
           "verdicts": [{"verdict": "SOUND", "run_id": "a"}, {"verdict": "SOUND", "run_id": "b"}]}
OK = {"ok": True, "detail": "done"}


@unittest.skipUnless(NODE, "node is not installed")
class GateTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        a = {"subject": SUBJ, "ticket": "T-0003"}
        a.update(args)
        plan = dict(plan, __args=a)
        d = tempfile.mkdtemp(prefix="acad-rewf-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], out["calls"]

    @staticmethod
    def labels(calls):
        return [c["label"] for c in calls]

    # ---- #124 follow-up 2: free text asked, never required; the packet id is its own field ----

    def test_prep_and_done_require_no_free_text(self):
        p = prep()
        del p["stop_reason"]
        res, calls = self.run_wf({"prepare": [p], "run A": ["r"], "decide": [dec("not-cleared", ["BROKEN"])],
                                  "claim-keeper evidence": ["rows"], "close": [{"ok": True}]})
        for label, field in (("prepare", "stop_reason"), ("close", "detail")):
            schema = next(c for c in calls if c["label"] == label)["schema"]
            self.assertIn(field, schema["properties"], label)
            self.assertNotIn(field, schema["required"], label)
        self.assertTrue(res["ticket_closed"])
        res, _calls = self.run_wf({"prepare": [dict(p, ok=False)]})
        self.assertEqual((res["outcome"], res["reason"]), ("not-started", "no reason given"))

    def test_the_decision_packet_id_is_read_from_its_own_field(self):
        plan = {"prepare": [prep()], "run A": ["r"], "decide": [dec("unresolved", ["SOUND"])],
                "claim-keeper evidence": ["rows"], "close": [OK]}
        res, calls = self.run_wf(dict(plan, packet=[{"ok": True, "packet": "P-0042"}]))
        schema = next(c for c in calls if c["label"] == "packet")["schema"]
        self.assertIn("packet", schema["required"])
        self.assertNotIn("detail", schema["required"])
        self.assertEqual(res["packet"], "P-0042")
        self.assertIn("packet P-0042", next(c for c in calls if c["label"] == "close")["prompt"])
        res, calls = self.run_wf(dict(plan, packet=[{"ok": False, "packet": ""}]))
        self.assertNotIn("packet", res)
        self.assertIn("the decision packet was not filed: no reason given", res["notes"])
        res, calls = self.run_wf(dict(plan, packet=[{"ok": True, "packet": "filed it"}]))
        self.assertNotIn("packet", res)
        self.assertIn("not a packet id: filed it", " ".join(res["notes"]))

    def test_a_broken_launches_no_b(self):
        res, calls = self.run_wf({"prepare": [prep()], "run A": ["r"],
                                  "decide": [dec("not-cleared", ["BROKEN"])],
                                  "claim-keeper evidence": ["rows"], "close": [OK]})
        self.assertEqual(self.labels(calls), ["prepare", "run A", "decide",
                                              "claim-keeper evidence", "close"])
        self.assertIn("run B skipped by design", " ".join(res["notes"]))

    def test_a_sound_launches_b_with_the_scripts_brief_and_a_clean_clear_sets_status(self):
        res, calls = self.run_wf({
            "prepare": [prep()], "run A": ["a"], "run B": ["b"],
            "decide": [dec("need-B", ["SOUND"]),
                       dec("cleared", ["SOUND", "SOUND"], GROUNDS, status="supported")],
            "claim-keeper status": ["set"], "close": [OK]})
        self.assertEqual(self.labels(calls), ["prepare", "run A", "decide", "run B", "decide",
                                              "claim-keeper status", "close"])
        b = next(c for c in calls if c["label"] == "run B")
        self.assertEqual(b["agentType"], "researcher:experiment-reviewer")
        self.assertEqual(b["prompt"], reviews.brief(SUBJ, "B", result="results/x.json",
                                                    ticket="T-0003", report="P-0009"))
        keeper = next(c for c in calls if c["label"] == "claim-keeper status")
        self.assertIn(json.dumps(GROUNDS, separators=(",", ":")), keeper["prompt"])
        self.assertIn("supported", keeper["prompt"])
        self.assertTrue(res["ticket_closed"])

    def test_the_script_brief_is_reviews_brief_byte_for_byte(self):
        _res, calls = self.run_wf({"prepare": [prep(report="", result="")], "run A": ["a"],
                                   "decide": [dec("not-cleared", ["GAP"])],
                                   "claim-keeper evidence": ["rows"], "close": [OK]},
                                  ticket="T-0003")
        a = next(c for c in calls if c["label"] == "run A")
        self.assertEqual(a["prompt"], reviews.brief(SUBJ, "A", ticket="T-0003"))

    def test_grounds_problems_attach_evidence_only(self):
        _res, calls = self.run_wf({
            "prepare": [prep("need-B")], "run B": ["b"],
            "decide": [dec("cleared", ["SOUND", "SOUND"], GROUNDS, ["no commit hash"], "supported")],
            "claim-keeper evidence": ["rows"], "close": [OK]})
        self.assertIn("claim-keeper evidence", self.labels(calls))
        self.assertNotIn("claim-keeper status", self.labels(calls))

    def test_an_unlanded_run_is_relaunched_once_and_a_lost_run_stops(self):
        res, calls = self.run_wf({"prepare": [prep()], "run A": ["a"], "run A (relaunch)": ["a"],
                                  "decide": [dec("need-A"), dec("not-cleared", ["GAP"])],
                                  "claim-keeper evidence": ["rows"], "close": [OK]})
        self.assertEqual(self.labels(calls)[:5], ["prepare", "run A", "decide",
                                                  "run A (relaunch)", "decide"])
        self.assertIn("the kept run is the relaunch", " ".join(res["notes"]))
        # lost on the max model: one relaunch on opus (T-1682); lost again: the pass stops
        res, calls = self.run_wf({"prepare": [prep()], "run A": [None], "run A (opus fallback)": [None]})
        self.assertEqual(self.labels(calls), ["prepare", "run A", "run A (opus fallback)"])
        self.assertIn("lost", " ".join(res["notes"]))
        self.assertNotIn("ticket_closed", res)            # still waiting on run A
        res, calls = self.run_wf({"prepare": [prep()], "run A": [None]},
                                 models={"researcher:experiment-reviewer": "opus"})
        self.assertEqual(self.labels(calls), ["prepare", "run A"])

    def test_a_run_kept_unparsed_is_not_relaunched(self):
        """#93: the hook kept this run's report unparsed: stop with its problems, no blind relaunch."""
        stuck = dict(dec("need-A"), unparsed=["audits/_unparsed/2026-11-19-ag-1.md: no Verdict line"])
        res, calls = self.run_wf({"prepare": [prep()], "run A": ["a"], "decide": [stuck]})
        self.assertEqual(self.labels(calls), ["prepare", "run A", "decide"])
        self.assertEqual(res["outcome"], "unlanded")
        self.assertIn("no Verdict line", res["reason"])
        # a copy that was there at prepare is an earlier run's: relaunched as before
        old = dict(prep(), unparsed_before=["2026-11-19-ag-1.md"])
        res, calls = self.run_wf({"prepare": [old], "run A": ["a"], "run A (relaunch)": ["a"],
                                  "decide": [stuck, dec("not-cleared", ["GAP"])],
                                  "claim-keeper evidence": ["rows"], "close": [OK]})
        self.assertIn("run A (relaunch)", self.labels(calls))

    def test_the_reviewer_launches_on_the_max_model(self):
        """T-1682: the args' model, or one clerk stage; a lost run falls back to opus once, noted in the result."""
        plan = {"prepare": [prep()], "run A": ["a"], "decide": [dec("not-cleared", ["GAP"])],
                "claim-keeper evidence": ["rows"], "close": [OK]}
        res, calls = self.run_wf(dict(plan))
        self.assertEqual(next(c for c in calls if c["label"] == "run A")["model"], "fable")
        res, calls = self.run_wf(dict(plan, **{"model researcher:experiment-reviewer": [{"output": "opus"}]}),
                                 models={"researcher:experiment-reviewer": "claude-opus-5-5"})
        self.assertEqual(self.labels(calls)[:3], ["prepare", "model researcher:experiment-reviewer", "run A"])
        self.assertEqual(next(c for c in calls if c["label"] == "run A")["model"], "opus")
        # no map given (#83): the Models block resolves it once, first
        res, calls = self.run_wf(dict(plan, models=[{"output": '{"researcher:experiment-reviewer": "fable"}'}]), models=None)
        self.assertEqual(self.labels(calls)[:3], ["models", "prepare", "run A"])
        self.assertEqual(next(c for c in calls if c["label"] == "run A")["model"], "fable")
        res, calls = self.run_wf(dict(plan, **{"run A": [None], "run A (opus fallback)": ["a"]}))
        self.assertEqual(res["model_fallbacks"], ["run A: fable -> opus"])
        self.assertIn("model fallback: run A: fable -> opus", next(c for c in calls if c["label"] == "close")["prompt"])

    def test_candidates_in_review_mode_send_it_to_settle(self):
        res, calls = self.run_wf({"prepare": [prep(has_candidates=True)]})
        self.assertEqual(res["outcome"], "needs-settle")
        self.assertEqual(self.labels(calls), ["prepare"])

    def test_settle_audit_plans_only_after_a_cleared_audit(self):
        cands = [{"name": "m%d" % i, "rank": i, "ref": "lab:x#m%d" % i, "detail": "d"}
                 for i in range(1, 5)]
        plan = {"audit": "cleared", "file_now": cands, "waiting": [], "deferred": [], "notes": []}
        res, calls = self.run_wf({
            "prepare": [prep("need-B")], "run B": ["b"],
            "decide": [dec("cleared", ["SOUND", "SOUND"], GROUNDS, status="refuted")],
            "claim-keeper status": ["set"], "settle-plan": [plan],
            "rederive m1": [{"ticket": "T-11", "refusal": ""}], "rederive m2": [{"ticket": "T-12", "refusal": ""}],
            "rederive m3": [{"ticket": "T-13", "refusal": ""}],
            "get T-11": [{"found": True, "to": "scientist@t", "kind": "experiment", "status": "open", "refs": ["lab:x#m1"]}],
            "get T-12": [{"found": True, "to": "expert@t", "kind": "experiment", "status": "open", "refs": ["lab:x#m2"]}],
            "get T-13": [{"found": True, "to": "scientist@t", "kind": "experiment", "status": "open", "refs": ["lab:x#m3"]}],
            "record tickets": [OK]},
            mode="settle-audit", candidates="/s/c.json")
        self.assertEqual(res["to_file"], [])                    # filed by the lead, not handed back
        self.assertEqual([r["ticket"] for r in res["rederivations"]], ["T-11", "T-12", "T-13"])
        self.assertNotIn("rederive m4", self.labels(calls))     # the cap of three
        self.assertIn("ANOMALY: T-12", " ".join(res["notes"]))   # the wrong receiver is caught
        self.assertEqual(next(c for c in calls if c["label"] == "rederive m1")["agentType"], "researcher:lead-researcher")
        self.assertNotIn("close", self.labels(calls))       # waits on the tickets
        res, calls = self.run_wf({
            "prepare": [prep("need-B")], "run B": ["b"],
            "decide": [dec("not-cleared", ["SOUND", "BROKEN"])],
            "claim-keeper evidence": ["rows"],
            "settle-plan": [dict(plan, audit="not-cleared")], "close": [OK]},
            mode="settle-audit", candidates="/s/c.json")
        self.assertEqual(res["to_file"], [])
        self.assertIn("no candidate ticket is filed", " ".join(res["notes"]))

    def test_settle_review_files_verify_only_after_the_rederivation_is_back(self):
        st = {"candidates": [
            {"name": "m1", "ref": "lab:x#m1", "rederivation": "T-11", "status": "delivered", "report": "P-0050", "verify": "", "detail": ""},
            {"name": "m2", "ref": "lab:x#m2", "rederivation": "T-12", "status": "in-progress", "report": "", "verify": "", "detail": ""},
            {"name": "m3", "ref": "lab:x#m3", "rederivation": "T-13", "status": "delivered", "report": "P-0051", "verify": "T-30", "detail": ""}]}
        res, calls = self.run_wf({
            "decide": [prep("cleared", decide=dec("cleared", ["SOUND", "SOUND"], GROUNDS, status="refuted"))],
            "candidates state": [st], "verify m1": [{"ticket": "T-21", "refusal": ""}],
            "get T-21": [{"found": True, "to": "expert@t", "kind": "verify", "status": "open", "refs": ["lab:x#m1"]}],
            "record verifies": [OK]}, mode="settle-review", candidates="/s/c.json", checklist=".claude/rules/verification-checklist.md")
        labels = self.labels(calls)
        self.assertIn("verify m1", labels)
        self.assertNotIn("verify m2", labels)                    # its re-derivation is not back
        self.assertNotIn("verify m3", labels)                    # already filed
        self.assertNotIn("claim-keeper status", labels)          # the audit is not re-recorded
        v = next(c for c in calls if c["label"] == "verify m1")["prompt"]
        self.assertIn("completeness of the enumeration first", v)
        self.assertIn("verification-checklist.md", v)

    def test_settle_conclude_sends_only_recordable_candidates_to_the_keeper(self):
        settled = {"recordable": ["m1"], "rows": [{"name": "m1", "decision": "REFUTATION CLEARED"},
                                                  {"name": "m2", "decision": "UNRESOLVED"}],
                   "record": "audits/x/2026-10-31-settle.md", "note": "n"}
        res, calls = self.run_wf({
            "decide": [prep("cleared", decide=dec("cleared", ["SOUND", "SOUND"], GROUNDS, status="refuted"))],
            "settle-decide": [settled], "claim-keeper m1": ["set"], "close": [OK]},
            mode="settle-conclude", candidates="/s/c.json", verdicts=[{"name": "m1"}])
        self.assertEqual(self.labels(calls), ["decide", "settle-decide", "claim-keeper m1", "close"])
        self.assertNotIn("run A", self.labels(calls))

    def test_malformed_args_are_refused(self):
        for args in ({"subject": "ew-check"}, {"mode": "settle-audit"}):
            plan = dict({}, __args=dict({"subject": SUBJ}, **args))
            d = tempfile.mkdtemp(prefix="acad-rewf-")
            self.addCleanup(shutil.rmtree, d, True)
            h = os.path.join(d, "h.js")
            with open(h, "w", encoding="utf-8") as fh:
                fh.write(HARNESS)
            p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True,
                               text=True, timeout=60)
            self.assertIn("error", json.loads(p.stdout.strip().splitlines()[-1]))


def shipped(line):
    return {"status": "nothing", "detail": "", "branches": [], "output": "T-0003: delivered (delivered)\n%s\n" % line}


@unittest.skipUnless(NODE, "node is not installed")
class ShipTests(unittest.TestCase):
    """docs/workflows.md, "Shipping is a step of the workflow": standalone ships once; nested never."""
    run_wf = GateTests.run_wf
    PLAN = {"prepare": [prep()], "run A": ["r"], "decide": [dec("not-cleared", ["BROKEN"])],
            "claim-keeper evidence": ["rows"], "close": [OK]}

    def test_standalone_ships_once_nested_never_refusal_once(self):
        res, calls = self.run_wf(dict(self.PLAN, ship=[shipped("Slope 2026-11-13/t-0003/researcher @ a (1 files) pushed")]),
                                 nested=False, root="/acad")
        labels = [c["label"] for c in calls]
        self.assertEqual(labels[-2:], ["close", "ship"])
        self.assertIn("py /acad/researcher/scripts/inbox.py --check T-0003", calls[-1]["prompt"])
        self.assertEqual(res["ship"]["status"], "pushed")
        res, calls = self.run_wf(dict(self.PLAN))
        self.assertNotIn("ship", [c["label"] for c in calls])
        bad = shipped("Slope x @ a (1 files) PUSH FAILED: gate")
        res, calls = self.run_wf(dict(self.PLAN, ship=[bad, bad]), nested=False)
        self.assertEqual([c["label"] for c in calls].count("ship"), 1)
        self.assertEqual(res["ship"]["status"], "refused")
        self.assertIn("ship stage was refused", " ".join(res["notes"]))

    def test_no_ticket_ships_the_slug_once(self):
        # #136 item 4: through inbox.py --ship-slug, under --check's guards and scope
        plan = dict(self.PLAN, ship=[{"status": "pushed", "output": "home 2026-11-27/review-lab-ew-check/researcher @ abc1234 (1 files) pushed\nreview-lab-ew-check: delivered (no ticket)\n"}])
        del plan["close"]
        res, calls = self.run_wf(plan, ticket=None, nested=False)
        self.assertEqual([c["label"] for c in calls].count("ship"), 1)
        self.assertIn("--ship-slug review-lab-ew-check", [c for c in calls if c["label"] == "ship"][0]["prompt"])
        self.assertEqual(res["ship"]["status"], "pushed")


class LaunchGuardTests(unittest.TestCase):
    def ev(self, sub, tool="Agent"):
        return {"hook_event_name": "PreToolUse", "tool_name": tool,
                "tool_input": {"subagent_type": sub, "prompt": "Review"}}

    def test_a_hand_launched_reviewer_is_denied(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ACADEMY_ALLOW_MANUAL_REVIEW", None)
            for sub in ("researcher:experiment-reviewer", "experiment-reviewer"):
                out = guard.decide(self.ev(sub))
                self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
                self.assertIn("review-experiment.js",
                              out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_other_agents_and_the_opt_out_pass(self):
        for sub in ("researcher:claim-keeper", "expert:rigor-reviewer", ""):
            self.assertIsNone(guard.decide(self.ev(sub)))
        with mock.patch.dict(os.environ, {"ACADEMY_ALLOW_MANUAL_REVIEW": "1"}):
            self.assertIsNone(guard.decide(self.ev("researcher:experiment-reviewer")))

    def test_relays_are_launched_only_by_the_inbox_workflow(self):
        os.environ.pop("ACADEMY_ALLOW_MANUAL_REVIEW", None)
        for sub in ('researcher:experiment-spec', 'lit-request'):
            out = guard.decide(self.ev(sub))
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("workflows/inbox.js", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_the_hook_is_registered(self):
        with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]["PreToolUse"]
        self.assertTrue(any(h.get("matcher") == "Agent|Task" and "review_launch_guard.py"
                            in h["hooks"][0]["command"] for h in hooks))


if __name__ == "__main__":
    unittest.main()
