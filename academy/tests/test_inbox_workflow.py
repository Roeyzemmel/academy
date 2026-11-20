"""The inbox workflow (academy/workflows/inbox.js), 2026-10-31.

The inbox rules and the relays' legs are code. The script runs under node with a fake
``agent()`` (answers queued per label) and a fake nested ``workflow()``, so the rules are
checked without a model: the instance order and one cap over the run, the sweep first
and outside the cap, a relay's forward leg concluded by the script after it checked the
child (and refused when the child breaks the chain), a fail-fast delivered, a return leg
made without the relay, a for_main stop, an unfinished ticket skipping only itself (two close the instance), a
lost agent stopping the run, verify and review-experiment run nested, the developer's
diff reviewed by test-engineer, the run's budget (a route's declared cost; a ticket that does not fit waits), the
lead-researcher's proof work handed back to the main session as /researcher:prove (T-1271). Skipped
where node is not installed.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SCRIPT = os.path.join(PLUGIN, "workflows", "inbox.js")
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs')
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^export const meta/m, 'const meta')
const plan = JSON.parse(process.argv[3])
const calls = []
async function agent(prompt, opts) {
  calls.push({ label: opts.label, agentType: opts.agentType, prompt, schema: opts.schema })
  const q = plan[opts.label]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned agent ' + opts.label)
  const v = q.shift()
  if (v && v.__throw) throw new Error(v.__throw)     // a run that ended without its structured output
  return v
}
async function workflow(ref, a) {
  const name = ref.scriptPath.split('/').pop()
  calls.push({ label: 'workflow ' + name, args: a })
  const q = plan['workflow ' + name]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned workflow ' + name)
  return q.shift()
}
const body = new Function('args', 'agent', 'phase', 'log', 'workflow', 'return (async () => {' + src + '})()')
body(plan.__args, agent, () => {}, () => {}, workflow).then(
  r => console.log(JSON.stringify({ result: r, calls })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""

OK = {"ok": True, "status": "x", "detail": ""}
MAXMAP = {"expert:referee": "fable", "expert:rigor-reviewer": "fable", "researcher:experiment-reviewer": "fable", "researcher:prover": "fable"}
DONE = {"exit": 0, "status": "delivered", "detail": ""}
LEAD_DONE = {"decision": "delivered", "claim": "", "created": False, "brief": "", "falsifier": "",
             "pending": [], "report": "worked"}
FALSIFIED = "T-9 delivered: no counterexample up to 12 squares"


def row(tid, how="agent", target="math-writer", kind="write", ret=False, frm="author@t",
        to="author@t", final_to="", refs=(), runs=1, released=False, over=None):
    return {"id": tid, "kind": kind, "status": "open", "from": frm, "to": to,
            "final_to": final_to, "refs": list(refs), "budget_runs": runs,
            "route": {"how": how, "target": target, "why": "because"}, "return": ret,
            "released": released, "over_budget": over}


def inst(name, rows, waiting=0):
    return {"name": name, "role": name.split("@")[0], "home": "/h/" + name, "waiting": waiting,
            "rows": rows}


def child(cid, parent, frm, to, kind, final_to):
    return {"found": True, "id": cid, "from": frm, "to": to, "kind": kind, "status": "open",
            "parent": parent, "final_to": final_to, "packets": []}


@unittest.skipUnless(NODE, "node is not installed")
class InboxWorkflowTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        a = {"root": "/academy", "models": {}}   # as the skills pass it; models=None: not given
        a.update(args)
        plan = dict(plan, __args=a)
        d = tempfile.mkdtemp(prefix="acad-inwf-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], [c["label"] for c in out["calls"]], out["calls"]

    def test_order_cap_and_sweep_first(self):
        listed = {"instances": [
            inst("expert@t", [row("T-2", target="research-intake", kind="research", ret=True,
                                   to="expert@t")]),
            inst("author@t", [row("T-1"), row("T-3"), row("T-4"), row("T-5")])]}
        plan = {"list": [listed], "sweep author@t": ["0 notes"],
                "T-1 start": [OK], "math-writer T-1": ["done"], "check T-1": [DONE],
                "T-3 start": [OK], "math-writer T-3": ["done"], "check T-3": [DONE],
                "T-4 start": [OK], "math-writer T-4": ["done"], "check T-4": [DONE],
                "close author@t": [OK]}
        res, labels, _ = self.run_wf(plan)
        self.assertEqual(labels[:2], ["list", "sweep author@t"])     # the sweep comes first
        self.assertEqual([t["id"] for t in res["taken"]], ["T-1", "T-3", "T-4"])   # cap 3
        self.assertNotIn("T-2 return leg", labels)                   # Author before Expert
        self.assertEqual(res["count"], 3)

    def test_relay_forward_with_a_good_child_is_blocked_on_it(self):
        r = row("T-7", target="research-intake", kind="research", frm="author@t",
                to="expert@t", final_to="researcher")
        plan = {"list": [{"instances": [inst("expert@t", [r])]}],
                "T-7 start": [OK],
                "research-intake T-7": [{"decision": "forward", "result": "relayed",
                                         "result_detail": "", "child": "T-8", "notes": []}],
                "get T-8": [child("T-8", "T-7", "expert@t", "researcher@u", "research",
                                  "researcher")],
                "T-7 block-on": [OK], "check T-7": [DONE]}
        res, labels, calls = self.run_wf(plan)
        self.assertIn("T-7 block-on", labels)
        relay = next(c for c in calls if c["label"] == "research-intake T-7")
        self.assertEqual(relay["agentType"], "expert:research-intake")
        self.assertIn("Make no status move on T-7", relay["prompt"])
        self.assertEqual(res["taken"][0]["outcome"], "relayed as T-8")

    def test_relay_child_breaking_the_chain_is_refused(self):
        r = row("T-7", target="experiment-spec", kind="research", frm="expert@t",
                to="researcher@u", final_to="scientist")
        plan = {"list": [{"instances": [inst("researcher@u", [r])]}],
                "T-7 start": [OK],
                "experiment-spec T-7": [{"decision": "forward", "result": "x", "result_detail": "",
                                         "child": "T-8", "notes": []}],
                "get T-8": [child("T-8", "T-7", "researcher@u", "expert@t", "experiment",
                                  "scientist")],
                "T-7 block-human": [OK], "check T-7": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertIn("T-7 block-human", labels)
        self.assertNotIn("T-7 block-on", labels)
        self.assertIn("not a scientist instance", " ".join(res["notes"]))

    def test_relay_fail_fast_is_delivered_and_a_return_leg_needs_no_relay(self):
        r1 = row("T-7", target="lit-request", kind="cite", frm="scientist@t",
                 to="researcher@u", final_to="expert")
        r2 = row("T-9", target="lit-request", kind="cite", ret=True, to="researcher@u")
        plan = {"list": [{"instances": [inst("researcher@u", [r1, r2])]}],
                "T-7 start": [OK],
                "lit-request T-7": [{"decision": "fail-fast", "result": "card AB12 Thm 3",
                                     "result_detail": "the library has it", "child": "", "notes": []}],
                "T-7 deliver": [OK], "check T-7": [DONE],
                "T-9 return leg": [OK], "check T-9": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertEqual(labels, ["list", "T-7 start", "lit-request T-7", "T-7 deliver",
                                  "check T-7", "T-9 return leg", "check T-9"])
        self.assertEqual(res["taken"][1]["outcome"], "delivered (return leg)")

    def test_for_main_stops_in_order(self):
        rows = [row("T-1", how="skill", target="researcher:settle", kind="review-experiment", to="expert@t"),
                row("T-2", how="human", target="human", kind="decision", to="expert@t")]
        res, labels, _ = self.run_wf({"list": [{"instances": [inst("expert@t", rows)]}]})
        self.assertEqual(res["for_main"]["ticket"], "T-1")
        self.assertEqual(res["count"], 0)
        self.assertEqual(labels, ["list"])

    def test_unfinished_closes_the_instance_and_lost_stops_the_run(self):
        rows = [row("T-1", how="human", target="human", kind="decision", to="expert@t"),
                row("T-2", how="reject", target=None, kind="prove", to="expert@t")]
        other = [row("T-5", how="reject", target=None, kind="prove", to="researcher@u")]
        # one unfinished ticket skips only itself; a second of the same instance closes it
        rows.append(row("T-3", how="reject", target=None, kind="prove", to="expert@t"))
        plan = {"list": [{"instances": [inst("expert@t", rows), inst("researcher@u", other)]}],
                "T-1 block-human": [OK], "check T-1": [{"exit": 3, "status": "open", "detail": ""}],
                "T-2 reject": [OK], "check T-2": [{"exit": 3, "status": "open", "detail": ""}],
                "T-5 reject": [OK], "check T-5": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertIn("T-2 reject", labels)                      # T-1 did not close the Expert
        self.assertNotIn("T-3 reject", labels)                   # two unfinished did
        self.assertIn("T-5 reject", labels)
        self.assertEqual(["unfinished", "unfinished", "rejected"], [t["outcome"] for t in res["taken"]])
        self.assertIn("expert@t left 2 tickets unfinished", " ".join(res["notes"]))
        rows = [row("T-1", target="lead-researcher", kind="research", to="researcher@u"),
                row("T-2", how="reject", target=None, kind="prove", to="researcher@u")]
        plan = {"list": [{"instances": [inst("researcher@u", rows)]}],
                "T-1 start": [OK], "lead-researcher T-1": [None], "T-1 interrupted": [OK]}
        res, labels, _ = self.run_wf(plan)
        self.assertIn("nothing further launched", res["stopped"])
        self.assertNotIn("T-2 reject", labels)

    def test_a_blocked_ticket_is_parked_and_a_twice_unfinished_one_goes_to_the_human(self):
        # 2026-11-14: one ticket waiting on a decision, first in every listing, closed its
        # instance in every run
        old = row("T-1", how="reject", target=None, kind="prove", to="expert@t")
        old["status"] = "in-progress"                            # left so by an earlier run
        rows = [old, row("T-2", how="human", target="human", kind="decision", to="expert@t"),
                row("T-3", how="reject", target=None, kind="prove", to="expert@t")]
        plan = {"list": [{"instances": [inst("expert@t", rows)]}],
                "T-1 reject": [OK], "check T-1": [{"exit": 3, "status": "in-progress", "detail": ""}],
                "T-1 park": [OK],
                "T-2 block-human": [OK], "check T-2": [{"exit": 3, "status": "blocked", "detail": ""}],
                "T-3 reject": [OK], "check T-3": [DONE]}
        res, labels, calls = self.run_wf(plan)
        got = [t["outcome"] for t in res["taken"]]
        self.assertEqual(("parked on the human", "rejected"), (got[0], got[2]))
        self.assertNotEqual("unfinished", res["taken"][1]["outcome"])   # blocked is parked
        self.assertIn("T-3 reject", labels)                              # the instance stayed open
        park = [c for c in calls if c["label"] == "T-1 park"][0]["prompt"]
        self.assertIn('waiting_on ["human"]', park)
        self.assertIn("unfinished after two inbox runs", park)
        self.assertIn("/academy:decide", " ".join(res["notes"]))

    def test_verify_and_review_experiment_run_nested(self):
        rows = [row("T-1", how="skill", target="expert:verify", kind="verify", to="expert@t",
                    refs=["T-0003", "paper:lem:x"])]
        res, labels, calls = self.run_wf({
            "list": [{"instances": [inst("expert@t", rows)]}],
            "workflow verify.js": [{"outcome": "confirmed", "proposed_status": "proved"}],
            "check T-1": [DONE]}, models={"expert:rigor-reviewer": "fable"})
        wf = next(c for c in calls if c["label"] == "workflow verify.js")
        self.assertEqual(wf["args"], {"nested": True, "root": "/academy", "claim": "paper:lem:x", "ticket": "T-1",
                                      "models": {"expert:rigor-reviewer": "fable"}})   # the map passed on
        rows = [row("T-2", how="skill", target="researcher:review-experiment",
                    kind="review-experiment", to="researcher@u", refs=["lab:x", "P-0009"])]
        res, labels, calls = self.run_wf({
            "list": [{"instances": [inst("researcher@u", rows)]}],
            "workflow review-experiment.js": [{"outcome": "needs-settle"}, {"outcome": "cleared", "notes": []}],
            "check T-2": [DONE]})
        wfs = [c for c in calls if c["label"] == "workflow review-experiment.js"]
        self.assertEqual(wfs[0]["args"]["subject"], "lab:x")
        self.assertEqual(wfs[0]["args"]["report"], "P-0009")
        self.assertEqual(wfs[1]["args"]["mode"], "settle-audit")        # settle chained, no hand-back
        self.assertEqual([w["args"]["models"] for w in wfs], [{}, {}])   # {} given: no override, passed on
        self.assertNotIn("models", labels)

    def test_a_run_without_the_map_resolves_it_once_and_passes_it_down(self):
        """#83: the 2026-11-20 run was started without args.models; the inbox passed {} down
        and verify.js took it for the workspace's map, so the graders ran on opus."""
        rows = [row("T-1", how="skill", target="expert:verify", kind="verify", to="expert@t",
                    refs=["paper:lem:x"]),
                row("T-2", how="skill", target="researcher:review-experiment",
                    kind="review-experiment", to="researcher@u", refs=["lab:x", "P-0009"])]
        res, labels, calls = self.run_wf({
            "models": [{"output": json.dumps(MAXMAP) + "\n"}],
            "list": [{"instances": [inst("expert@t", rows[:1]), inst("researcher@u", rows[1:])]}],
            "workflow verify.js": [{"outcome": "confirmed", "proposed_status": "proved"}],
            "workflow review-experiment.js": [{"outcome": "cleared", "notes": []}],
            "check T-1": [DONE], "check T-2": [DONE]}, models=None)
        self.assertEqual(labels[0], "models")                        # before anything else
        self.assertEqual(labels.count("models"), 1)                  # once per run
        stage = calls[0]
        self.assertEqual(stage["agentType"], "general-purpose")
        self.assertIn("py /academy/academy/scripts/models.py launches", stage["prompt"])
        wfs = [c for c in calls if c["label"].startswith("workflow ")]
        self.assertEqual(len(wfs), 2)
        self.assertEqual([w["args"]["models"] for w in wfs], [MAXMAP, MAXMAP])   # the resolved map

    def test_a_run_whose_map_cannot_be_resolved_is_refused(self):
        p = os.path.join(tempfile.mkdtemp(prefix="acad-inwf-"), "h.js")
        self.addCleanup(shutil.rmtree, os.path.dirname(p), True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        plan = {"models": [{"output": "Traceback: workspace.json not found"}],
                "list": [{"instances": []}], "__args": {"root": "/academy"}}
        out = subprocess.run([NODE, p, SCRIPT, json.dumps(plan)], capture_output=True, text=True, timeout=60)
        res = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertIn("args.models was not given", res.get("error", ""))
        self.assertIn("py /academy/academy/scripts/models.py launches", res["error"])
        self.assertEqual([c["label"] for c in res["calls"]], ["models"])   # nothing else ran

    def test_a_usage_limit_at_the_map_lookup_returns_stopped(self):
        """Review of abf478f: no map and a usage limit at the start (the lookup returns
        nothing) ends the run as a usage limit does (stopped, usage_limit), not a throw."""
        p = os.path.join(tempfile.mkdtemp(prefix="acad-inwf-"), "h.js")
        self.addCleanup(shutil.rmtree, os.path.dirname(p), True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        plan = {"models": [None], "__args": {"root": "/academy"}}
        out = subprocess.run([NODE, p, SCRIPT, json.dumps(plan)], capture_output=True, text=True, timeout=60)
        res = json.loads(out.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", res, res.get("error"))
        self.assertIn("usage limit", res["result"]["stopped"])
        self.assertTrue(res["result"]["usage_limit"])
        self.assertEqual([c["label"] for c in res["calls"]], ["models"])

    def test_a_nested_explore_hand_back_reaches_the_main_session(self):
        """#87: explore hands its prove step back as for_main; the inbox passes it on with
        the ticket instead of reading the run as unfinished."""
        rows = [row("T-3", how="skill", target="researcher:explore", kind="question",
                    to="researcher@u", refs=["DIR-2"])]
        fm = {"skill": "researcher:prove", "handback": "lead-researcher",
              "args": {"claim": "s1:GEO-1", "ticket": "T-3"}, "why": "the prove step"}
        res, labels, calls = self.run_wf({
            "list": [{"instances": [inst("researcher@u", rows)]}],
            "workflow explore.js": [{"outcome": "handed-back", "for_main": fm}]})
        self.assertEqual("researcher:prove", res["for_main"]["skill"])
        self.assertEqual("T-3", res["for_main"]["ticket"])
        self.assertEqual("researcher@u", res["for_main"]["instance"])
        self.assertNotIn("check T-3", labels)

    def test_verify_takes_the_claim_its_title_names(self):
        """#89: the first namespaced ref is often the parent; the title decides, several
        refs and none in the title go back to the main session, a title-only claim is used."""
        def one(title, refs):
            r = dict(row("T-1", how="skill", target="expert:verify", kind="verify", to="expert@t", refs=refs),
                     title=title)
            plan = {"list": [{"instances": [inst("expert@t", [r])]}],
                    "workflow verify.js": [{"outcome": "x"}], "check T-1": [DONE]}
            return self.run_wf(plan)
        res, labels, calls = one("Verify lem:child after the restyle", ["T-0003", "paper:lem:parent", "paper:lem:child"])
        self.assertEqual(next(c for c in calls if c["label"] == "workflow verify.js")["args"]["claim"], "paper:lem:child")
        res, labels, calls = one("Verify the lemma", ["paper:lem:parent", "paper:lem:child"])
        self.assertNotIn("workflow verify.js", labels)
        self.assertIn("naming no single claim", res["for_main"]["why"])
        # a lone ref is often the parent: the id the title names wins (#89 review)
        res, labels, calls = one("Verify s1:CHILD-2", ["s1:PARENT-1"])
        self.assertEqual(next(c for c in calls if c["label"] == "workflow verify.js")["args"]["claim"], "s1:CHILD-2")
        res, labels, calls = one("Verify s1:CLASS-5: the lemma", ["s1:CLASS-1", "s1:CLASS-5", "lab:2026-11-01_x"])
        self.assertEqual(next(c for c in calls if c["label"] == "workflow verify.js")["args"]["claim"], "s1:CLASS-5")
        self.assertFalse(any("read from the title" in n for n in res["notes"]))
        res, labels, calls = one("Verify lem:strip-bound", [])
        self.assertNotIn("workflow verify.js", labels)
        res, labels, calls = one("Verify s1:GEO-3 (reword)", ["T-0003"])
        self.assertEqual(next(c for c in calls if c["label"] == "workflow verify.js")["args"]["claim"], "s1:GEO-3")
        self.assertIn("read from the title", " ".join(res["notes"]))

    def test_a_reword_verify_ticket_runs_verify_in_reword_mode(self):
        """#85: prove.js files a repair's reword verify titled "Verify <claim> (reword of
        <pass>)"; the inbox passes mode reword and that base pass. Any other title is blind."""
        def args(title, refs=("s1:GEO-3", "T-0003")):
            r = dict(row("T-1", how="skill", target="expert:verify", kind="verify", to="expert@t", refs=list(refs)),
                     title=title)
            res, labels, calls = self.run_wf({"list": [{"instances": [inst("expert@t", [r])]}],
                                              "workflow verify.js": [{"outcome": "x"}], "check T-1": [DONE]})
            return res, next(c for c in calls if c["label"] == "workflow verify.js")["args"]
        res, a = args("Verify s1:GEO-3 (reword of 2026-11-01-T-0007)")
        self.assertEqual((a["claim"], a.get("mode"), a.get("base_pass")), ("s1:GEO-3", "reword", "2026-11-01-T-0007"))
        self.assertIn("reword", " ".join(res["notes"]))
        for title in ("Verify s1:GEO-3", "Verify s1:GEO-3 (reword)", "Verify s1:GEO-3 (reword of the old text)",
                      "Verify s1:GEO-3 (reword of 2026-11-01-T-0007-reword)"):
            _res, a = args(title)
            self.assertNotIn("mode", a, title)
            self.assertNotIn("base_pass", a, title)

    def test_a_reword_pass_that_does_not_start_says_a_blind_verify_is_needed(self):
        """Review of 62be9fa: new-pass --reword-of refuses a base that is not CONFIRMED x2."""
        r = dict(row("T-1", how="skill", target="expert:verify", kind="verify", to="expert@t", refs=["s1:GEO-3"]),
                 title="Verify s1:GEO-3 (reword of 2026-11-01-T-0007)")
        res, labels, calls = self.run_wf({"list": [{"instances": [inst("expert@t", [r])]}],
                                          "workflow verify.js": [{"outcome": "not-started", "reason": "base pass not confirmed x2"}],
                                          "check T-1": [DONE]})
        notes = " ".join(res["notes"])
        self.assertIn("not CONFIRMED x2 needs a blind verify instead", notes)
        self.assertIn("base pass not confirmed x2", notes)
        # a blind verify that does not start gets no such line
        r = dict(r, title="Verify s1:GEO-3")
        res, labels, calls = self.run_wf({"list": [{"instances": [inst("expert@t", [r])]}],
                                          "workflow verify.js": [{"outcome": "not-started", "reason": "an open pass"}],
                                          "check T-1": [DONE]})
        self.assertNotIn("blind verify instead", " ".join(res["notes"]))

    def test_the_inbox_passes_its_map_and_resolves_no_model_itself(self):
        """T-0350 with T-1682: the inbox runs no model stage; the map it was given goes to
        every nested workflow as it is, whose launchMax resolves a max-tier agent the map
        leaves out (an empty map: one clerk stage there, test_workflow_max_tier.py)."""
        rows = [row("T-1", how="skill", target="expert:verify", kind="verify", to="expert@t", refs=["paper:lem:x"]),
                row("T-2", how="skill", target="expert:verify", kind="verify", to="expert@t", refs=["paper:lem:y"])]
        res, labels, calls = self.run_wf({
            "list": [{"instances": [inst("expert@t", rows)]}],
            "workflow verify.js": [{"outcome": "x"}, {"outcome": "x"}], "check T-1": [DONE], "check T-2": [DONE]},
            models=MAXMAP)
        self.assertNotIn("models", labels)
        self.assertEqual([c["args"]["models"] for c in calls if c["label"] == "workflow verify.js"], [MAXMAP, MAXMAP])
        self.assertIsNone(res["for_main"])
        res, labels, calls = self.run_wf({"list": [{"instances": [inst("expert@t", rows[:1])]}],
                                          "workflow verify.js": [{"outcome": "x"}], "check T-1": [DONE]})
        self.assertNotIn("models", labels)
        self.assertEqual(next(c for c in calls if c["label"] == "workflow verify.js")["args"]["models"], {})

    def test_developer_is_reviewed_by_test_engineer(self):
        rows = [row("T-1", target="developer", kind="code", to="scientist@t", runs=4)]
        plan = {"list": [{"instances": [inst("scientist@t", rows)]}],
                "T-1 start": [OK],
                "developer T-1": ["diff 1"],
                "test-engineer T-1": [{"verdict": "findings", "findings": ["cite.js:12 crashes on an empty ref"]},
                                      {"verdict": "approved", "findings": []}],
                "developer T-1 (round 2)": ["diff 2"],
                "T-1 review note": [OK, OK], "T-1 deliver": [OK], "check T-1": [DONE]}
        res, labels, calls = self.run_wf(plan)
        self.assertEqual([l for l in labels if l.startswith(("developer", "test-engineer"))],
                         ["developer T-1", "test-engineer T-1", "developer T-1 (round 2)",
                          "test-engineer T-1"])
        self.assertEqual(res["taken"][0]["outcome"], "delivered")
        # the findings go back to the developer from the structured list
        self.assertIn("cite.js:12 crashes on an empty ref",
                      next(c for c in calls if c["label"] == "developer T-1 (round 2)")["prompt"])

    # #94 (2026-11-19, T-0181): the review's text mentioned settings.json, the harness
    # neutralised it, and the prose check /^APPROVED/ read an approval as findings three times.
    # The verdict is a structured field; the text never decides it.
    def test_the_review_verdict_is_a_structured_field(self):
        rows = [row("T-1", target="developer", kind="code", to="scientist@t", runs=4)]
        neutralised = {"verdict": "approved", "findings": [],
                       "summary": "[content neutralised: instruction-shaped text (settings-json)]"}
        plan = {"list": [{"instances": [inst("scientist@t", rows)]}], "T-1 start": [OK],
                "developer T-1": ["diff 1"], "test-engineer T-1": [neutralised],
                "T-1 review note": [OK], "T-1 deliver": [OK], "check T-1": [DONE]}
        res, labels, calls = self.run_wf(plan)
        te = next(c for c in calls if c["label"] == "test-engineer T-1")
        self.assertEqual(te["schema"]["properties"]["verdict"]["enum"], ["approved", "findings"])
        self.assertEqual(te["schema"]["required"], ["verdict"])          # #124: no free text required
        self.assertNotIn("begin your answer with", te["prompt"])
        self.assertEqual(res["taken"][0]["outcome"], "delivered")
        self.assertNotIn("T-1 block-human", labels)
        note = next(c for c in calls if c["label"] == "T-1 review note")["prompt"]
        self.assertIn("test-engineer: approved", note)

    def test_prose_that_begins_with_approved_is_not_an_approval(self):
        rows = [row("T-1", target="developer", kind="code", to="scientist@t", runs=4)]
        plan = {"list": [{"instances": [inst("scientist@t", rows)]}], "T-1 start": [OK],
                "developer T-1": ["diff 1"], "developer T-1 (round 2)": ["diff 2"],
                "test-engineer T-1": [{"verdict": "findings", "findings": [], "summary": "APPROVED? no: two findings"},
                                      {"verdict": "findings", "findings": ["x.py:3 wrong"]}],
                "T-1 review note": [OK, OK], "T-1 block-human": [OK], "check T-1": [DONE]}
        res, labels, calls = self.run_wf(plan)
        self.assertNotIn("T-1 deliver", labels)
        self.assertEqual(res["taken"][0]["outcome"], "blocked on human (review)")
        self.assertIn("x.py:3 wrong", res["taken"][0]["detail"])
        # findings with no list still go back with the summary the reviewer gave
        self.assertIn("two findings", next(c for c in calls if c["label"] == "developer T-1 (round 2)")["prompt"])

    def test_a_review_with_no_verdict_is_asked_once_more_before_a_developer_round(self):
        rows = [row("T-1", target="developer", kind="code", to="scientist@t", runs=4)]
        plan = {"list": [{"instances": [inst("scientist@t", rows)]}], "T-1 start": [OK],
                "developer T-1": ["diff 1"], "developer T-1 (round 2)": ["diff 2"],
                "test-engineer T-1": ["APPROVED", {"verdict": "approved"}],
                "test-engineer T-1 (again)": ["still prose"],
                "T-1 review note": [OK, OK], "T-1 deliver": [OK], "check T-1": [DONE]}
        res, labels, calls = self.run_wf(plan)
        self.assertEqual([l for l in labels if l.startswith(("developer", "test-engineer"))],
                         ["developer T-1", "test-engineer T-1", "test-engineer T-1 (again)",
                          "developer T-1 (round 2)", "test-engineer T-1"])
        self.assertIn("no verdict", next(c for c in calls if c["label"] == "developer T-1 (round 2)")["prompt"])
        self.assertEqual(res["taken"][0]["outcome"], "delivered")

    # #94 review: a reviewer that ends without its structured output throws (T-1614); the
    # throw must not end the inbox run: it is no verdict, asked once more
    def test_a_review_that_throws_is_asked_once_more_and_then_approves(self):
        rows = [row("T-1", target="developer", kind="code", to="scientist@t", runs=4)]
        boom = {"__throw": "agent({schema}): subagent completed without calling StructuredOutput (after in-conversation nudge)"}
        plan = {"list": [{"instances": [inst("scientist@t", rows)]}], "T-1 start": [OK],
                "developer T-1": ["diff 1"], "test-engineer T-1": [boom],
                "test-engineer T-1 (again)": [{"verdict": "approved", "findings": []}],
                "T-1 review note": [OK], "T-1 deliver": [OK], "check T-1": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertNotIn("developer T-1 (round 2)", labels)
        self.assertEqual(res["taken"][0]["outcome"], "delivered")
        self.assertIsNone(res.get("stopped"))

    def test_a_review_that_throws_twice_is_no_verdict_not_the_end_of_the_run(self):
        rows = [row("T-1", target="developer", kind="code", to="scientist@t", runs=4)]
        boom = {"__throw": "subagent completed without calling StructuredOutput"}
        plan = {"list": [{"instances": [inst("scientist@t", rows)]}], "T-1 start": [OK],
                "developer T-1": ["diff 1"], "developer T-1 (round 2)": ["diff 2"],
                "test-engineer T-1": [boom, {"verdict": "approved"}], "test-engineer T-1 (again)": [boom],
                "T-1 review note": [OK, OK], "T-1 deliver": [OK], "check T-1": [DONE]}
        res, labels, calls = self.run_wf(plan)
        self.assertIn("developer T-1 (round 2)", labels)
        self.assertIn("no verdict", next(c for c in calls if c["label"] == "developer T-1 (round 2)")["prompt"])
        self.assertEqual(res["taken"][0]["outcome"], "delivered")

    def test_a_review_that_returns_nothing_is_still_lost(self):
        rows = [row("T-1", target="developer", kind="code", to="scientist@t", runs=4)]
        plan = {"list": [{"instances": [inst("scientist@t", rows)]}], "T-1 start": [OK],
                "developer T-1": ["diff 1"], "test-engineer T-1": [None], "T-1 interrupted": [OK]}
        res, labels, _ = self.run_wf(plan)
        self.assertEqual(res["taken"][0]["outcome"], "lost")
        self.assertNotIn("test-engineer T-1 (again)", labels)

    # #94 review: an approval with minor findings kept them only in the agent's answer
    def test_an_approval_with_findings_writes_them_into_the_thread_note(self):
        rows = [row("T-1", target="developer", kind="code", to="scientist@t", runs=4)]
        long = "b.py:9 " + "x" * 300
        plan = {"list": [{"instances": [inst("scientist@t", rows)]}], "T-1 start": [OK],
                "developer T-1": ["diff 1"],
                "test-engineer T-1": [{"verdict": "approved", "findings": ["a.py:3 a \"minor\" thing", long]}],
                "T-1 review note": [OK], "T-1 deliver": [OK], "check T-1": [DONE]}
        res, labels, calls = self.run_wf(plan)
        note = next(c for c in calls if c["label"] == "T-1 review note")["prompt"]
        self.assertIn("test-engineer: approved", note)
        self.assertIn("a.py:3 a 'minor' thing", note)
        self.assertIn("b.py:9 xxx", note)
        self.assertNotIn("x" * 200, note)                     # shortened, one line each
        self.assertEqual(res["taken"][0]["outcome"], "delivered")

    def test_an_experiment_runs_its_design_leg_and_stops_at_the_header_gate(self):
        rows = [row("T-1", target="experimenter", kind="experiment", to="scientist@t")]
        gate = {"for_main": {"gate": True, "why": "approve the header", "header": "Kind: search ...", "next": {"mode": "build"}}}
        res, labels, calls = self.run_wf({"list": [{"instances": [inst("scientist@t", rows)]}],
                                          "workflow experiment.js": [gate]})
        self.assertEqual(next(c for c in calls if c["label"] == "workflow experiment.js")["args"]["mode"], "design")
        self.assertEqual(res["for_main"]["skill"], "scientist:experiment")
        self.assertEqual(res["for_main"]["header"], "Kind: search ...")

    def test_a_scientist_question_is_answered_without_compute(self):
        rows = [row("T-2", target="experimenter", kind="question", to="scientist@t")]
        res, labels, calls = self.run_wf({"list": [{"instances": [inst("scientist@t", rows)]}],
                                          "T-2 start": [OK], "experimenter T-2": ["answered"], "check T-2": [DONE]})
        self.assertIn("no new compute", next(c for c in calls if c["label"] == "experimenter T-2")["prompt"])

    def test_loop_sets_gates_aside_and_goes_on_until_quiet(self):
        rows = [row("T-1", target="experimenter", kind="experiment", to="scientist@t"),
                row("T-2", how="reject", target=None, kind="prove", to="scientist@t")]
        gate = {"for_main": {"gate": True, "why": "approve the header", "next": {"mode": "build"}}}
        plan = {"list": [{"instances": [inst("scientist@t", rows)]}],
                "workflow experiment.js": [gate], "T-2 reject": [OK], "check T-2": [DONE],
                "list 2": [{"instances": [inst("scientist@t", rows[:1])]}]}
        res, labels, _ = self.run_wf(plan, loop=True)
        self.assertEqual(labels, ["list", "workflow experiment.js", "T-2 reject", "check T-2", "list 2"])
        self.assertEqual([g["ticket"] for g in res["gates"]], ["T-1"])
        self.assertIn("wait on the human", res["for_main"]["why"])
        self.assertEqual(res["passes"], 2)                     # pass 2 moved nothing: quiet

    def test_a_later_listing_that_returns_nothing_ends_the_run_cleanly(self):
        """#114: the weekly limit hit during a loop; list 2 returned nothing and the
        close-out crashed on 'insts.some' of null."""
        rows = [row("T-2", how="reject", target=None, kind="write", to="author@t")]
        plan = {"list": [{"instances": [inst("author@t", rows)]}], "sweep author@t": ["0"],
                "T-2 reject": [OK], "check T-2": [DONE], "list 2": [None], "close author@t": [OK]}
        res, labels, _ = self.run_wf(plan, loop=True)
        self.assertIn("returned nothing", res["stopped"])
        self.assertIn("check_paper.py", " ".join(res["notes"]))     # the close-out ran on the last listing

    def test_three_launches_returning_nothing_stop_the_run(self):
        """#115: under a usage limit every launch fails; after three in a row nothing more is
        launched and the result says why."""
        rows = [row("T-1", target="clerk", kind="lookup", to="expert@t"),
                row("T-2", target="clerk", kind="lookup", to="expert@t")]
        plan = {"list": [{"instances": [inst("expert@t", rows)]}], "T-1 start": [None], "check T-1": [None],
                "T-2 start": [None]}
        res, labels, _ = self.run_wf(plan)
        self.assertTrue(res.get("usage_limit"), res)
        self.assertIn("usage limit", res["stopped"])
        self.assertEqual(labels, ["list", "T-1 start", "check T-1", "T-2 start"])   # nothing after the third
        self.assertNotIn("check T-2", labels)

    def test_a_later_listing_with_an_empty_home_keeps_the_home_seen_before(self):
        """#94 (the fix of 26b28cd): pass 2's listing came back with home '' and the
        nested prove threw 'args.home must be the Researcher home', ending the run."""
        first = [row("T-2", how="reject", target=None, kind="prove", to="researcher@u")]
        later = [row("T-3", how="skill", target="researcher:prove", kind="prove", to="researcher@u",
                     refs=["flat:GEO-3"])]
        lost = dict(inst("researcher@u", later), home="")
        plan = {"list": [{"instances": [inst("researcher@u", first)]}], "T-2 reject": [OK], "check T-2": [DONE],
                "list 2": [{"instances": [lost]}],
                "workflow prove.js": [{"outcome": "verify-filed", "verify_ticket": "T-9"}], "check T-3": [DONE],
                "list 3": [{"instances": [inst("researcher@u", [])]}]}
        res, labels, calls = self.run_wf(plan, loop=True)
        wf = next(c for c in calls if c["label"] == "workflow prove.js")
        self.assertEqual(wf["args"]["home"], "/h/researcher@u")

    # #94 (2026-11-19 21:17): the list stage returned {"instances": []} and the run did
    # nothing, while inbox.py listed 24 waiting tickets for the Author a minute later. Every
    # instance is one entry of the listing, and waiting > 0 means rows: an empty listing is a
    # failed stage, listed once more, and said so in the result, never "nothing to do".
    def test_an_empty_listing_is_listed_once_more(self):
        rows = [row("T-2", how="reject", target=None, kind="prove", to="scientist@t")]
        plan = {"list": [{"instances": []}], "list (retry)": [{"instances": [inst("scientist@t", rows, waiting=1)]}],
                "T-2 reject": [OK], "check T-2": [DONE]}
        res, labels, calls = self.run_wf(plan)
        self.assertEqual(labels[:2], ["list", "list (retry)"])
        self.assertIn("no instance", next(c for c in calls if c["label"] == "list (retry)")["prompt"])
        self.assertEqual([t["id"] for t in res["taken"]], ["T-2"])
        self.assertIn("listed once more", " ".join(res["notes"]))

    def test_an_empty_listing_twice_is_a_failed_stage_not_nothing_to_do(self):
        plan = {"list": [{"instances": []}], "list (retry)": [{"instances": []}]}
        res, labels, _ = self.run_wf(plan)
        self.assertEqual(labels, ["list", "list (retry)"])
        self.assertTrue(res.get("list_failed"))
        self.assertIn("failed stage", res["stopped"])
        self.assertEqual(res["taken"], [])

    def test_waiting_tickets_with_no_rows_are_listed_once_more(self):
        rows = [row("T-2", how="reject", target=None, kind="prove", to="author@t")]
        plan = {"list": [{"instances": [inst("author@t", [], waiting=24), inst("expert@t", [])]}],
                "list (retry)": [{"instances": [inst("author@t", rows, waiting=24), inst("expert@t", [])]}],
                "sweep author@t": ["0"], "T-2 reject": [OK], "check T-2": [DONE], "close author@t": [OK]}
        res, labels, calls = self.run_wf(plan)
        self.assertEqual(labels[:2], ["list", "list (retry)"])
        self.assertIn("author@t: 24 waiting, no rows", next(c for c in calls if c["label"] == "list (retry)")["prompt"])
        self.assertEqual([t["id"] for t in res["taken"]], ["T-2"])

    def test_waiting_with_no_rows_twice_is_an_anomaly_and_the_others_go_on(self):
        rows = [row("T-3", how="reject", target=None, kind="prove", to="expert@t")]
        listed = {"instances": [inst("author@t", [], waiting=24), inst("expert@t", rows, waiting=1)]}
        plan = {"list": [listed], "list (retry)": [listed], "sweep author@t": ["0"],
                "T-3 reject": [OK], "check T-3": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertEqual([t["id"] for t in res["taken"]], ["T-3"])
        self.assertIn("ANOMALY: author@t", " ".join(res["notes"]))

    def test_only_with_none_of_its_instances_listed_twice_is_a_failed_stage(self):
        listed = {"instances": [inst("expert@t", [])]}
        res, labels, _ = self.run_wf({"list": [listed], "list (retry)": [listed]}, only=["author@t"])
        self.assertEqual(labels, ["list", "list (retry)"])
        self.assertTrue(res.get("list_failed"))

    def test_a_quiet_listing_is_not_retried(self):
        res, labels, _ = self.run_wf({"list": [{"instances": [inst("expert@t", []), inst("scientist@t", [])]}]})
        self.assertEqual(labels, ["list"])
        self.assertNotIn("list_failed", res)

    def test_with_ids_waiting_without_rows_is_not_retried(self):
        # --ids filters the rows in the script while waiting counts the whole inbox
        res, labels, _ = self.run_wf({"list": [{"instances": [inst("expert@t", [], waiting=5)]}]}, ids=["T-9"])
        self.assertEqual(labels, ["list"])

    def test_a_later_empty_listing_is_retried_and_then_a_failed_stage(self):
        rows = [row("T-2", how="reject", target=None, kind="prove", to="scientist@t")]
        plan = {"list": [{"instances": [inst("scientist@t", rows, waiting=1)]}], "T-2 reject": [OK], "check T-2": [DONE],
                "list 2": [{"instances": []}], "list 2 (retry)": [{"instances": []}]}
        res, labels, _ = self.run_wf(plan, loop=True)
        self.assertEqual(labels[-2:], ["list 2", "list 2 (retry)"])
        self.assertIn("failed stage", res["stopped"])
        self.assertTrue(res.get("list_failed"))

    def test_an_author_research_route_is_filed_by_math_writer_and_checked(self):
        rows = [row("T-5", how="research", target="expert", kind="write", to="author@t")]
        plan = {"list": [{"instances": [inst("author@t", rows)]}], "sweep author@t": ["0"],
                "T-5 start": [OK], "math-writer T-5 (research)": [{"ticket": "T-6", "refusal": ""}],
                "get T-6": [child("T-6", "T-5", "author@t", "expert@t", "research", "researcher")],
                "T-5 block-on": [OK], "check T-5": [DONE], "close author@t": [OK]}
        res, labels, calls = self.run_wf(plan)
        self.assertIsNone(res["for_main"])
        self.assertEqual(next(c for c in calls if c["label"] == "math-writer T-5 (research)")["agentType"], "author:math-writer")
        self.assertEqual(res["taken"][0]["outcome"], "asked as T-6")

    def test_follow_takes_the_children_of_handled_tickets(self):
        r = row("T-7", target="research-intake", kind="research", frm="author@t", to="expert@t", final_to="researcher")
        kid = dict(row("T-8", target="lead-researcher", kind="research", frm="expert@t", to="researcher@u", final_to="researcher"), parent="T-7")
        other = row("T-9", target="lead-researcher", kind="research", to="researcher@u")
        plan = {"list": [{"instances": [inst("expert@t", [r]), inst("researcher@u", [other])]}],
                "T-7 start": [OK],
                "research-intake T-7": [{"decision": "forward", "result": "relayed", "result_detail": "", "child": "T-8", "notes": []}],
                "get T-8": [child("T-8", "T-7", "expert@t", "researcher@u", "research", "researcher")],
                "T-7 block-on": [OK], "check T-7": [DONE],
                "list 2": [{"instances": [inst("expert@t", []), inst("researcher@u", [kid, other])]}],
                "T-8 start": [OK], "lead-researcher T-8": [LEAD_DONE], "check T-8": [DONE],
                "list 3": [{"instances": [inst("researcher@u", [other])]}]}
        res, labels, _ = self.run_wf(plan, loop=True, cap=3, ids=["T-7"], follow=True)
        self.assertEqual([t["id"] for t in res["taken"]], ["T-7", "T-8"])     # T-9 is outside the scope
        self.assertNotIn("lead-researcher T-9", labels)

    def test_a_parked_relay_keeps_its_instance_open_and_its_child_is_followed_by_id(self):
        # live run 2026-10-31: the forward's blocked --check closed the Expert, and the child
        # (no parent in the row, listed under the wrong instance) was never taken
        r = row("T-7", target="research-intake", kind="research", frm="author@t", to="expert@t", final_to="researcher")
        r2 = row("T-5", how="reject", target=None, kind="prove", to="expert@t")
        kid = row("T-8", target="lead-researcher", kind="research", frm="expert@t", to="researcher@u", final_to="researcher")
        stray = dict(kid, id="T-8")
        plan = {"list": [{"instances": [inst("expert@t", [r, r2])]}],
                "T-7 start": [OK],
                "research-intake T-7": [{"decision": "forward", "result": "relayed", "result_detail": "", "child": "T-8", "notes": []}],
                "get T-8": [child("T-8", "T-7", "expert@t", "researcher@u", "research", "researcher")],
                "T-7 block-on": [OK], "check T-7": [{"exit": 3, "status": "blocked", "detail": ""}],
                "T-5 reject": [OK], "check T-5": [DONE],
                "list 2": [{"instances": [inst("researcher@u", [kid]), inst("scientist@t", [stray])]}],
                "T-8 start": [OK], "lead-researcher T-8": [LEAD_DONE], "check T-8": [DONE]}
        res, labels, _ = self.run_wf(plan, loop=True, cap=3, ids=["T-7", "T-5"], follow=True)
        self.assertEqual([t["id"] for t in res["taken"]], ["T-7", "T-5", "T-8"])
        self.assertEqual(res["taken"][0]["outcome"], "relayed as T-8")
        self.assertIn("listed under scientist@t but is addressed to researcher@u", " ".join(res["notes"]))

    def test_a_return_leg_listed_under_its_sender_is_landed_not_dropped(self):
        # live run 2026-11-13: two return legs (delivered back to the Author, addressed to the Expert) were dropped as anomalies
        r = row("T-5", target="math-editor", kind="verify", ret=True, frm="author@t", to="expert@t")
        plan = {"list": [{"instances": [inst("author@t", [r])]}], "sweep author@t": ["0"],
                "math-editor T-5 (land)": ["landed"], "check T-5": [{"exit": 0, "status": "closed", "output": "T-5: closed (closed)", "detail": ""}],
                "close author@t": [OK]}
        res, labels, _ = self.run_wf(plan)
        self.assertIn("math-editor T-5 (land)", labels)
        self.assertEqual(res["taken"][0]["outcome"], "landed")
        self.assertNotIn("ANOMALY", " ".join(res["notes"]))

    def test_the_check_is_read_from_its_own_line_not_the_clerks_verdict(self):
        r = row("T-5", how="reject", target=None, kind="prove", to="expert@t")
        r2 = row("T-6", how="reject", target=None, kind="prove", to="expert@t")
        out = "T-5: delivered (delivered)\nboard ... REFUSED: on 'claude/x'\nship: refused: checkpoint incomplete"
        plan = {"list": [{"instances": [inst("expert@t", [r, r2])]}],
                "T-5 reject": [OK], "check T-5": [{"exit": 3, "status": "unfinished", "output": out, "detail": ""}],
                "T-6 reject": [OK], "check T-6": [{"exit": 0, "status": "x", "output": "T-6: unfinished (in-progress)", "detail": ""}]}
        res, labels, _ = self.run_wf(plan)
        self.assertEqual([(t["id"], t["outcome"], t["status"]) for t in res["taken"]],
                         [("T-5", "rejected", "delivered"), ("T-6", "unfinished", "in-progress")])
        self.assertIn("T-5: the checkpoint did not ship everything", " ".join(res["notes"]))

    def test_an_unreachable_cite_is_a_gate(self):
        r = row("T-3", how="skill", target="expert:cite", kind="cite", to="expert@t")
        plan = {"list": [{"instances": [inst("expert@t", [r])]}],
                "workflow cite.js": [{"outcome": "unreachable (on the human)", "key": "Va10", "pinpoint": "", "verdict": "unreachable",
                                      "gate": {"why": "source unreachable", "source": "Va10", "pinpoint": "", "relying": "", "packet": "P-1"}}],
                "check T-3": [{"exit": 3, "status": "blocked", "detail": ""}],
                "list 2": [{"instances": [inst("expert@t", [])]}]}
        res, _, _ = self.run_wf(plan, loop=True, ids=["T-3"])
        self.assertEqual(res["taken"][0]["outcome"], "unreachable (on the human)")
        self.assertEqual(res["gates"][0]["ticket"], "T-3")
        self.assertIn("wait on the human", res["for_main"]["why"])

    def test_ids_list_all_and_skip_pending_blocked(self):
        rows = [dict(row("T-1", how="reject", target=None, kind="prove", to="expert@t"), blocked="pending"),
                row("T-2", how="reject", target=None, kind="prove", to="expert@t")]
        res, labels, calls = self.run_wf({"list": [{"instances": [inst("expert@t", rows)]}], "T-2 reject": [OK], "check T-2": [DONE]},
                                         ids=["T-1", "T-2"])
        self.assertIn("--ids T-1,T-2", calls[0]["prompt"])          # filtered in the script, not transcribed whole
        self.assertEqual([t["id"] for t in res["taken"]], ["T-2"])

    def test_a_row_listed_with_a_status_the_inbox_cannot_take_is_skipped(self):
        """#92: a blocked or delivered ticket whose row lost its blocked field is not taken."""
        rows = [dict(row("T-1", how="reject", target=None, kind="prove", to="expert@t"), status="blocked"),
                dict(row("T-3", how="reject", target=None, kind="prove", to="expert@t"), status="delivered"),
                row("T-2", how="reject", target=None, kind="prove", to="expert@t")]
        res, labels, calls = self.run_wf({"list": [{"instances": [inst("expert@t", rows)]}], "T-2 reject": [OK], "check T-2": [DONE]})
        self.assertEqual([t["id"] for t in res["taken"]], ["T-2"])
        self.assertIn("T-1 was listed with status blocked: not taken", res["notes"])

    def test_the_budget_is_the_runs_and_a_ticket_that_does_not_fit_waits(self):
        # 2026-11-14: no ticket is blocked "for budget"; the run counts what its routes cost
        rows = [row("T-1", target="clerk", kind="lookup", to="expert@t", runs=1)]
        plan = {"list": [{"instances": [inst("expert@t", rows)]}],
                "T-1 start": [OK], "clerk T-1": ["ESCALATE: not cached"],
                "librarian T-1": ["AB12 Thm 3 says ..."], "T-1 deliver": [OK], "check T-1": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertIn("librarian T-1", labels)                    # budget.runs 1 on the ticket gates nothing
        self.assertNotIn("T-1 block-human", labels)
        self.assertEqual({"runs": 12, "spent": 2, "deferred": []}, res["budget"])
        # an answered look-up gives back the escalation it did not need
        plan = {"list": [{"instances": [inst("expert@t", rows)]}],
                "T-1 start": [OK], "clerk T-1": ["It says X."], "T-1 deliver": [OK], "check T-1": [DONE]}
        self.assertEqual(1, self.run_wf(plan)[0]["budget"]["spent"])
        # a run of two agent runs: the look-up fits, the next one waits, the reject costs nothing
        rows = [row("T-1", target="clerk", kind="lookup", to="expert@t"),
                row("T-2", target="clerk", kind="lookup", to="expert@t"),
                row("T-3", how="reject", target=None, kind="prove", to="expert@t")]
        plan = {"list": [{"instances": [inst("expert@t", rows)]}],
                "T-1 start": [OK], "clerk T-1": ["ESCALATE"], "librarian T-1": ["X"], "T-1 deliver": [OK],
                "check T-1": [DONE], "T-3 reject": [OK], "check T-3": [DONE]}
        res, labels, _ = self.run_wf(plan, runs=2)
        self.assertEqual(["T-1", "T-3"], [t["id"] for t in res["taken"]])
        self.assertEqual([{"ticket": "T-2", "instance": "expert@t", "needs": 2, "left": 0}],
                         res["budget"]["deferred"])
        self.assertNotIn("T-2 start", labels)                     # not started, not blocked
        self.assertIn("T-2 waits for the next run", " ".join(res["notes"]))

    def test_an_expensive_ticket_needs_the_humans_word_once(self):
        rows = [row("T-1", how="skill", target="expert:verify", kind="verify", to="expert@t",
                    refs=["paper:lem:x"]),
                row("T-2", how="reject", target=None, kind="prove", to="expert@t")]
        plan = {"list": [{"instances": [inst("expert@t", rows)]}], "T-2 reject": [OK], "check T-2": [DONE]}
        res, labels, _ = self.run_wf(plan, big=2)                # a verify costs 3
        self.assertEqual(["T-2"], [t["id"] for t in res["taken"]])    # and holds nothing else back
        self.assertIn('approve: ["T-1"]', res["gates"][0]["why"])
        self.assertEqual("T-1", res["for_main"]["ticket"])

    def test_an_over_budget_row_of_an_older_listing_is_not_blocked(self):
        rows = [row("T-1", how="reject", target=None, kind="prove", to="expert@t", over="needs 2 runs")]
        plan = {"list": [{"instances": [inst("expert@t", rows)]}], "T-1 reject": [OK], "check T-1": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertEqual("rejected", res["taken"][0]["outcome"])
        self.assertNotIn("T-1 block-human", labels)

    # ---- T-1271: the lead-researcher cannot launch prover inside the inbox run ----------------
    # (live 2026-11-14/15: T-1257 blocked on the human, T-1264 left in-progress twice, nothing proved)

    def _lead(self, answer, registry=None, rows=None, **args):
        rows = rows or [row("T-1", target="lead-researcher", kind="research", frm="expert@t",
                            to="researcher@u", final_to="researcher", refs=["paper:lem:x"]),
                        row("T-2", how="reject", target=None, kind="prove", to="researcher@u")]
        plan = {"list": [{"instances": [inst("researcher@u", rows)]}],
                "T-1 start": [OK], "lead-researcher T-1": [answer]}
        if answer.get("decision") == "prove" and answer.get("falsifier"):
            plan["T-1 falsifier note"] = [OK]
        if registry is not None:
            plan["claim " + answer["claim"]] = [registry]
        plan.update(args.pop("plan", {}))
        return self.run_wf(plan, **args)

    @staticmethod
    def _ask(**kw):
        a = {"decision": "prove", "claim": "flat:FND-2", "created": False, "brief": "b",
             "falsifier": FALSIFIED, "pending": [], "report": "r"}
        a.update(kw)
        return a

    def test_a_lead_that_needs_prover_hands_prove_to_the_main_session(self):
        ask = self._ask(brief="journal/2026-11-16.md (T-1 brief)", report="needs a proof attempt")
        res, labels, calls = self._lead(ask, {"exit": 0, "output": "hash: ab\n## Statement\n..."})
        fm = res["for_main"]
        self.assertEqual("researcher:prove", fm["skill"])
        self.assertEqual("lead-researcher", fm["handback"])
        self.assertEqual(("T-1", "researcher@u", "flat:FND-2"), (fm["ticket"], fm["instance"], fm["claim"]))
        self.assertEqual({"claim": "flat:FND-2", "ticket": "T-1", "home": "/h/researcher@u",
                          "instance": "researcher@u", "root": "/academy"}, fm["args"])
        self.assertIn("/researcher:prove flat:FND-2", fm["why"])
        self.assertEqual("journal/2026-11-16.md (T-1 brief)", fm["brief"])
        self.assertEqual(FALSIFIED, fm["falsifier"])
        # never blocked, never checked as unfinished, and nothing overtakes it
        self.assertFalse(any(l.startswith(("T-1 block", "T-1 park", "check T-1")) for l in labels))
        self.assertNotIn("T-2 reject", labels)
        self.assertEqual(0, res["count"])
        lead = next(c for c in calls if c["label"] == "lead-researcher T-1")
        self.assertEqual("researcher:lead-researcher", lead["agentType"])
        for words in ("cannot launch prover", "claims_new", "decision prove", "never block",
                      "falsifier on record", "read the ticket's thread", "a second time"):
            self.assertIn(words, lead["prompt"])
        reg = next(c for c in calls if c["label"] == "claim flat:FND-2")
        self.assertIn("registry.py statement flat:FND-2", reg["prompt"])
        # the falsifier goes on the ticket's thread, where prove.js's state stage reads it
        note = next(c for c in calls if c["label"] == "T-1 falsifier note")
        self.assertIn(FALSIFIED, note["prompt"])
        self.assertIn("flat:FND-2", note["prompt"])
        self.assertLess(labels.index("T-1 falsifier note"), labels.index("claim flat:FND-2"))

    def test_a_claim_the_lead_registered_is_handed_back_too(self):
        ask = self._ask(claim="flat:GEO-40", created=True, brief="journal/x.md", report="registered the statement")
        res, _, _ = self._lead(ask, {"exit": 0, "output": "hash: cd"})
        self.assertEqual("flat:GEO-40", res["for_main"]["args"]["claim"])
        self.assertTrue(res["for_main"]["created"])
        self.assertIn("registered by the lead in this run", res["for_main"]["why"])

    def test_a_prove_handback_without_a_registry_claim_still_does_not_block(self):
        # no claim named: the session registers it first (claims_new), then proves
        ask = self._ask(claim="", brief="journal/x.md")
        res, labels, _ = self._lead(ask)
        self.assertEqual("researcher:prove", res["for_main"]["skill"])
        self.assertNotIn("args", res["for_main"])
        self.assertIn("claims_new", res["for_main"]["why"])
        self.assertIn("ANOMALY", " ".join(res["notes"]))
        self.assertFalse(any(l.startswith(("T-1 block", "claim ")) for l in labels))
        # a claim the registry does not resolve: the same, after the check
        ask = dict(ask, claim="flat:NOPE-9")
        res, labels, _ = self._lead(ask, {"exit": 1, "output": "statement: `flat:NOPE-9` does not resolve (missing)"})
        self.assertNotIn("args", res["for_main"])
        self.assertIn("does not resolve", res["for_main"]["why"])
        self.assertIn("claims_new", res["for_main"]["why"])
        self.assertFalse(any(l.startswith("T-1 block") for l in labels))

    def test_a_registry_check_that_fails_otherwise_is_not_reported_as_missing(self):
        # a crash of registry.py statement (exit 2, a traceback) says nothing about the claim
        res, labels, _ = self._lead(self._ask(), {"exit": 2, "output": "Traceback (most recent call last):\n  ImportError: x"})
        fm = res["for_main"]
        self.assertNotIn("args", fm)
        self.assertNotIn("does not resolve", fm["why"])
        self.assertIn("registry check", fm["why"])
        self.assertIn("exit 2", fm["why"])
        self.assertNotIn("claims_new in", fm["why"])          # registering it again could duplicate it
        self.assertNotIn("does not resolve", " ".join(res["notes"]))
        self.assertFalse(any(l.startswith("T-1 block") for l in labels))

    def test_a_lost_claim_check_or_note_stops_the_run(self):
        # budget.md rule 4: a stage that returns nothing (a limit, an API error) is lost, not "missing"
        for plan in ({"claim flat:FND-2": [None]}, {"T-1 falsifier note": [None]}):
            res, labels, _ = self._lead(self._ask(), plan=dict(plan, **{"T-1 interrupted": [OK]}))
            self.assertIsNone(res["for_main"])
            self.assertEqual("lost", res["taken"][0]["outcome"])
            self.assertIn("returned nothing", res["stopped"])
            self.assertIn("T-1 interrupted", labels)
            self.assertNotIn("T-2 reject", labels)
            self.assertNotIn("does not resolve", " ".join(res["notes"]))

    # 2026-11-20 (the human's design): prove.js attempts without a falsifier and a failed attempt or a GAP
    # verdict triggers one, so the lead's hand-back no longer waits for one. These two
    # replace ..._parks_the_ticket_on_the_pending_falsifier and ..._hands_back_explore_not_prove.
    def test_no_falsifier_on_record_still_hands_prove_back_with_a_pending_one(self):
        ask = self._ask(claim="flat:GEO-40", created=True, falsifier="", pending=["T-9"])
        res, labels, calls = self._lead(ask, {"exit": 0, "output": "hash: cd"})
        fm = res["for_main"]
        self.assertEqual("researcher:prove", fm["skill"])
        self.assertEqual("flat:GEO-40", fm["args"]["claim"])
        self.assertEqual(["T-9"], fm["pending"])
        self.assertIn("no falsifier on record", fm["why"])
        self.assertFalse(any(l.startswith(("T-1 block", "T-1 falsifier note")) for l in labels))   # never parked, no note
        lead = next(c for c in calls if c["label"] == "lead-researcher T-1")
        self.assertIn("does not wait for a falsifier", lead["prompt"])
        self.assertNotIn("attempts nothing without one", lead["prompt"])

    def test_no_falsifier_and_nothing_pending_hands_back_prove_not_explore(self):
        ask = self._ask(falsifier="", pending=[])
        res, labels, _ = self._lead(ask, {"exit": 0, "output": "hash: ab"})
        fm = res["for_main"]
        self.assertEqual("researcher:prove", fm["skill"])
        self.assertEqual("lead-researcher", fm["handback"])
        self.assertEqual("flat:FND-2", fm["args"]["claim"])
        self.assertNotIn("pending", fm)
        self.assertNotIn("ANOMALY", " ".join(res["notes"]))
        self.assertFalse(any(l.startswith(("T-1 block", "T-1 falsifier note")) for l in labels))

    def test_a_lead_that_delivers_or_blocks_is_checked_as_before(self):
        res, labels, _ = self._lead(dict(LEAD_DONE, report="delivered: falsifier T-9 filed\nmore"),
                                    plan={"check T-1": [DONE], "T-2 reject": [OK], "check T-2": [DONE]})
        self.assertIsNone(res["for_main"])
        self.assertEqual(("worked", "delivered: falsifier T-9 filed"), (res["taken"][0]["outcome"], res["taken"][0]["detail"]))
        self.assertIn("T-2 reject", labels)

    def test_in_a_loop_the_prove_handback_is_a_gate_and_the_rest_goes_on(self):
        ask = self._ask()
        res, labels, _ = self._lead(ask, {"exit": 0, "output": "hash: ab"}, loop=True,
                                    plan={"T-2 reject": [OK], "check T-2": [DONE],
                                          "list 2": [{"instances": [inst("researcher@u", [])]}]})
        self.assertIn("T-2 reject", labels)
        gate = res["gates"][0]
        self.assertEqual(("T-1", "researcher:prove", "flat:FND-2"), (gate["ticket"], gate["skill"], gate["args"]["claim"]))

    def test_another_roles_agent_route_is_unchanged(self):
        rows = [row("T-1", target="math-writer", kind="write")]
        res, labels, calls = self.run_wf({"list": [{"instances": [inst("author@t", rows)]}], "sweep author@t": ["0"],
                                          "T-1 start": [OK], "math-writer T-1": ["done"], "check T-1": [DONE],
                                          "close author@t": [OK]})
        self.assertNotIn("cannot launch prover", next(c for c in calls if c["label"] == "math-writer T-1")["prompt"])
        self.assertEqual("worked", res["taken"][0]["outcome"])

    # ---- #124: a clerk that leaves out 'detail' costs no run -----------------------------

    def _author_one(self, start, check):
        rows = [row("T-1", target="math-writer", kind="write")]
        return self.run_wf({"list": [{"instances": [inst("author@t", rows)]}], "sweep author@t": ["0"],
                            "T-1 start": [start], "math-writer T-1": ["done"], "check T-1": [check],
                            "close author@t": [OK]})

    def test_move_and_check_schemas_do_not_require_detail(self):
        """#124: 23 inbox-clerk runs failed 'must have required property detail' (ledger since
        2026-11-14): MOVE and CHECK keep the property but no longer require it."""
        _res, _labels, calls = self._author_one(OK, DONE)
        for label in ("T-1 start", "check T-1", "close author@t"):
            schema = next(c for c in calls if c["label"] == label)["schema"]
            self.assertIn("detail", schema["properties"], label)
            self.assertNotIn("detail", schema["required"], label)
        # what the code reads stays required
        self.assertEqual(set(next(c for c in calls if c["label"] == "T-1 start")["schema"]["required"]), {"ok", "status"})
        self.assertEqual(set(next(c for c in calls if c["label"] == "check T-1")["schema"]["required"]), {"exit", "status", "output"})

    def test_a_move_and_a_check_without_detail_lose_nothing(self):
        res, labels, calls = self._author_one({"ok": True, "status": "in-progress"},
                                              {"exit": 0, "status": "delivered", "output": "T-1: delivered (delivered)"})
        self.assertEqual(res["taken"][0]["outcome"], "worked")
        prompt = next(c for c in calls if c["label"] == "math-writer T-1")["prompt"]
        self.assertNotIn("undefined", prompt)
        self.assertIn("pinned.py", prompt)              # the writer is told to read them itself
        self.assertNotIn("undefined", json.dumps(res))

    def test_a_failed_start_without_detail_says_so_plainly(self):
        res, _labels, _calls = self._author_one({"ok": False, "status": "open"},
                                                {"exit": 3, "status": "open", "output": "T-1: open (open)"})
        self.assertEqual(res["taken"][0]["outcome"], "unfinished")
        self.assertNotIn("undefined", json.dumps(res))

    def test_a_route_without_why_loses_nothing(self):
        """#124 follow-up 2: the LIST schema asks for route.why but does not require it; a
        block-human route without it says 'no reason given', never undefined; a reject
        without it is not made (a terminal move needs its reason: review of 0da42c3) and
        goes to the main session."""
        r1 = row("T-1", how="reject", target=None, kind="prove", to="expert@t")
        r2 = row("T-2", how="human", target="human", kind="decision", to="expert@t")
        for r in (r1, r2):
            del r["route"]["why"]
        res, labels, calls = self.run_wf({"list": [{"instances": [inst("expert@t", [r2, r1])]}],
                                          "T-2 block-human": [OK], "check T-2": [DONE]})
        route = next(c for c in calls if c["label"] == "list")["schema"]["properties"]["instances"]["items"]["properties"]["rows"]["items"]["properties"]["route"]
        self.assertIn("why", route["properties"])
        self.assertNotIn("why", route["required"])
        self.assertEqual(["blocked on human"], [t["outcome"] for t in res["taken"]])
        self.assertIn('reason "no reason given"', next(c for c in calls if c["label"] == "T-2 block-human")["prompt"])
        self.assertNotIn("T-1 reject", labels)
        self.assertIn("gives no reason", res["for_main"]["why"])
        self.assertNotIn("undefined", json.dumps(res))

    def test_root_is_required(self):
        plan = {"__args": {}}
        d = tempfile.mkdtemp(prefix="acad-inwf-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True, text=True)
        self.assertIn("args.root", json.loads(p.stdout.strip().splitlines()[-1])["error"])


class ClerkMoveVocabularyTests(unittest.TestCase):
    """The clerks' move lists name the receiver's put back of a started ticket (#123
    follow-up): in-progress -> accepted is one direct step since feba39f, and a move the
    vocabulary does not name is one a clerk guesses (20 refusals 2026-11-14..19 of the
    old hint, in-progress -> blocked -> accepted)."""

    PUT_BACK = ("put back: in-progress -> accepted (receiver, a ticket started but not "
                "worked this run)")
    CLERKS = (os.path.join(PLUGIN, "agents", "inbox-clerk.md"),
              os.path.join(os.path.dirname(PLUGIN), "researcher", "agents", "review-clerk.md"))

    @staticmethod
    def text(path):
        with open(path, encoding="utf-8") as fh:
            # markdown code and emphasis marks are not part of the words
            return " ".join(fh.read().replace("`", "").replace("**", "").split())

    def workflows(self):
        repo = os.path.dirname(PLUGIN)
        for plugin in sorted(os.listdir(repo)):
            d = os.path.join(repo, plugin, "workflows")
            if os.path.isdir(d):
                for name in sorted(os.listdir(d)):
                    if name.endswith(".js"):
                        yield os.path.join(d, name)

    def test_every_clerk_names_the_put_back(self):
        for path in self.CLERKS:
            self.assertTrue(self.PUT_BACK in self.text(path), path)

    def test_the_inbox_clerks_description_lists_it_with_the_release(self):
        desc = self.text(self.CLERKS[0]).split(" description: ", 1)[1].split(" tools: ", 1)[0]
        self.assertIn("release, put back,", desc)

    def test_the_release_of_a_blocked_ticket_is_unchanged(self):
        self.assertIn("release: blocked -> accepted", self.text(self.CLERKS[0]))
        self.assertIn("'release: blocked -> accepted (everything it waited on is back)'",
                      self.text(SCRIPT))

    def test_no_clerk_or_workflow_offers_the_route_through_blocked(self):
        for path in list(self.CLERKS) + list(self.workflows()):
            self.assertFalse("in-progress -> blocked -> accepted" in self.text(path), path)


if __name__ == "__main__":
    unittest.main()
