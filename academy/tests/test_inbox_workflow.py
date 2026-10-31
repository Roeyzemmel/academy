"""The inbox workflow (academy/workflows/inbox.js), 2026-10-31.

The inbox rules and the relays' legs are code. The script runs under node with a fake
``agent()`` (answers queued per label) and a fake nested ``workflow()``, so the rules are
checked without a model: the instance order and one cap over the run, the sweep first
and outside the cap, a relay's forward leg concluded by the script after it checked the
child (and refused when the child breaks the chain), a fail-fast delivered, a return leg
made without the relay, a for_main stop, an unfinished ticket closing its instance, a
lost agent stopping the run, verify and review-experiment run nested, the developer's
diff reviewed by test-engineer, the clerk's escalation bounded by budget.runs. Skipped
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
  calls.push({ label: opts.label, agentType: opts.agentType, prompt })
  const q = plan[opts.label]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned agent ' + opts.label)
  return q.shift()
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
DONE = {"exit": 0, "status": "delivered", "detail": ""}


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
        a = {"root": "/academy"}
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
        plan = {"list": [{"instances": [inst("expert@t", rows), inst("researcher@u", other)]}],
                "T-1 block-human": [OK], "check T-1": [{"exit": 3, "status": "open", "detail": ""}],
                "T-5 reject": [OK], "check T-5": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertNotIn("T-2 reject", labels)
        self.assertIn("T-5 reject", labels)
        rows = [row("T-1", target="lead-researcher", kind="research", to="researcher@u"),
                row("T-2", how="reject", target=None, kind="prove", to="researcher@u")]
        plan = {"list": [{"instances": [inst("researcher@u", rows)]}],
                "T-1 start": [OK], "lead-researcher T-1": [None], "T-1 interrupted": [OK]}
        res, labels, _ = self.run_wf(plan)
        self.assertIn("nothing further launched", res["stopped"])
        self.assertNotIn("T-2 reject", labels)

    def test_verify_and_review_experiment_run_nested(self):
        rows = [row("T-1", how="skill", target="expert:verify", kind="verify", to="expert@t",
                    refs=["T-0003", "paper:lem:x"])]
        res, labels, calls = self.run_wf({
            "list": [{"instances": [inst("expert@t", rows)]}],
            "workflow verify.js": [{"outcome": "confirmed", "proposed_status": "proved"}],
            "check T-1": [DONE]})
        wf = next(c for c in calls if c["label"] == "workflow verify.js")
        self.assertEqual(wf["args"], {"claim": "paper:lem:x", "ticket": "T-1"})
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
        self.assertIsNone(res["for_main"])

    def test_developer_is_reviewed_by_test_engineer(self):
        rows = [row("T-1", target="developer", kind="code", to="scientist@t", runs=4)]
        plan = {"list": [{"instances": [inst("scientist@t", rows)]}],
                "T-1 start": [OK],
                "developer T-1": ["diff 1"], "test-engineer T-1": ["FINDINGS: x", "APPROVED"],
                "developer T-1 (round 2)": ["diff 2"],
                "T-1 review note": [OK, OK], "T-1 deliver": [OK], "check T-1": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertEqual([l for l in labels if l.startswith(("developer", "test-engineer"))],
                         ["developer T-1", "test-engineer T-1", "developer T-1 (round 2)",
                          "test-engineer T-1"])
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
                "T-8 start": [OK], "lead-researcher T-8": ["worked"], "check T-8": [DONE],
                "list 3": [{"instances": [inst("researcher@u", [other])]}]}
        res, labels, _ = self.run_wf(plan, loop=True, cap=3, ids=["T-7"], follow=True)
        self.assertEqual([t["id"] for t in res["taken"]], ["T-7", "T-8"])     # T-9 is outside the scope
        self.assertNotIn("lead-researcher T-9", labels)

    def test_ids_list_all_and_skip_pending_blocked(self):
        rows = [dict(row("T-1", how="reject", target=None, kind="prove", to="expert@t"), blocked="pending"),
                row("T-2", how="reject", target=None, kind="prove", to="expert@t")]
        res, labels, calls = self.run_wf({"list": [{"instances": [inst("expert@t", rows)]}], "T-2 reject": [OK], "check T-2": [DONE]},
                                         ids=["T-1", "T-2"])
        self.assertIn("--all", calls[0]["prompt"])
        self.assertEqual([t["id"] for t in res["taken"]], ["T-2"])

    def test_clerk_escalation_is_bounded_by_budget(self):
        rows = [row("T-1", target="clerk", kind="lookup", to="expert@t", runs=1)]
        plan = {"list": [{"instances": [inst("expert@t", rows)]}],
                "T-1 start": [OK], "clerk T-1": ["ESCALATE: not cached"],
                "T-1 block-human": [OK], "check T-1": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertNotIn("librarian T-1", labels)
        self.assertEqual(res["taken"][0]["outcome"], "blocked on human (budget)")
        plan = {"list": [{"instances": [inst("expert@t", [dict(rows[0], budget_runs=2)])]}],
                "T-1 start": [OK], "clerk T-1": ["ESCALATE: not cached"],
                "librarian T-1": ["AB12 Thm 3 says ..."], "T-1 deliver": [OK], "check T-1": [DONE]}
        res, labels, _ = self.run_wf(plan)
        self.assertIn("librarian T-1", labels)

    def test_root_is_required(self):
        plan = {"__args": {}}
        d = tempfile.mkdtemp(prefix="acad-inwf-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True, text=True)
        self.assertIn("args.root", json.loads(p.stdout.strip().splitlines()[-1])["error"])


if __name__ == "__main__":
    unittest.main()
