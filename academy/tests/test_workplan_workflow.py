"""The workplan workflow (academy/workflows/workplan.js), campaign and cowork with shared
components, and the inbox's nested mode, 2026-10-31. Under node with fake agent() and
workflow(); skipped without node."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
WORKPLAN = os.path.join(PLUGIN, "workflows", "workplan.js")
INBOX = os.path.join(PLUGIN, "workflows", "inbox.js")
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
const budget = { total: null, spent: () => 0, remaining: () => Infinity }
const body = new Function('args', 'agent', 'phase', 'log', 'workflow', 'budget', 'return (async () => {' + src + '})()')
body(plan.__args, agent, () => {}, () => {}, workflow, budget).then(
  r => console.log(JSON.stringify({ result: r, calls })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""


def run(script, plan, args):
    d = tempfile.mkdtemp(prefix="acad-wp-")
    try:
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, script, json.dumps(dict(plan, __args=args))],
                           capture_output=True, text=True, timeout=60)
    finally:
        shutil.rmtree(d, True)
    out = json.loads(p.stdout.strip().splitlines()[-1])
    return out.get("result"), [c["label"] for c in out["calls"]], out["calls"], out.get("error")


def st(state="ACTIVE", approaches=None, ok=True, target="open", receivers=("researcher@u",), **kw):
    s = {"state": state, "decision": [], "out": [], "own": [], "receivers": list(receivers),
         "approaches": approaches or [], "approach_count_ok": ok, "target_status": target,
         "target_statement": "S"}
    s.update(kw)
    return s


def ap(name, state="ACTIVE", life="active", dirs=("D-1",)):
    return {"approach": name, "lifecycle": life, "state": state, "directions": list(dirs),
            "waiting_tickets": [], "decision_tickets": []}


CAPS = {"ok": True, "error": "", "rounds": 2, "agents": 2, "runs": 0, "profile": None}
INB = {"taken": [], "notes": [], "count": 0}
LEAD = {"updates": ["AP-1 continue"], "tickets_filed": [], "notes": ""}
CAMPAIGN = {"kind": "campaign", "root": "/academy", "home": "/h/nb", "instance": "researcher@u",
            "target": "flat:T-1", "rounds": 2, "agents": 2}


@unittest.skipUnless(NODE, "node is not installed")
class SharedStopRules(unittest.TestCase):
    """One set of stop rules, both kinds."""

    def test_pause_and_done_stop_both_kinds(self):
        for kind, args in (("campaign", CAMPAIGN), ("cowork", {"kind": "cowork", "root": "/a", "slug": "s"})):
            # a campaign first takes what came back (it may lift the pause), then checks
            plan = {"state": [st("ACTIVE", [ap("AP-1")])], "workflow inbox.js": [INB],
                    "state round 1": [st("PAUSE", [ap("AP-1")], decision=["T-9"])],
                    "state before": [st("PAUSE", decision=["T-9"])],
                    "caps": [CAPS], "state final": [st("PAUSE")]}
            res, labels, _, err = run(WORKPLAN, plan, args)
            self.assertIsNone(err, err)
            self.assertIn("PAUSE", res["stopped"], kind)
            self.assertEqual(res["for_main"][0]["tickets"], ["T-9"])

    def test_missing_caps_stop_and_ask(self):
        res, labels, _, err = run(WORKPLAN, {"caps": [dict(CAPS, ok=False, error="--rounds is required")]}, CAMPAIGN)
        self.assertIn("suggest 3 rounds and 4 agents", res["stopped"])
        self.assertEqual(labels, ["caps"])


@unittest.skipUnless(NODE, "node is not installed")
class CampaignTests(unittest.TestCase):
    def test_seed_then_blind_provers_per_round_under_the_agents_cap(self):
        aps = [ap("AP-1"), ap("AP-2"), ap("AP-3", "WAITING"), ap("AP-4")]
        art = lambda n: {"artifact": "objects/claim/%s.md" % n, "kind": "lemma", "summary": "s"}
        plan = {"caps": [CAPS], "state": [st(ok=False)], "seed": [LEAD], "state after seeding": [st(approaches=aps)],
                "workflow inbox.js": [INB, INB],
                "state round 1": [st(approaches=aps)], "state round 2": [st(approaches=aps)],
                "next D-1": [{"items": ["try X"]}] * 6,
                "prover AP-1 r1": [art("L1")], "prover AP-2 r1": [art("L2")],
                "prover AP-1 r2": [art("L3")], "prover AP-2 r2": [art("L4")],
                "exists AP-1 r1": [{"exists": True}], "exists AP-2 r1": [{"exists": False}],
                "exists AP-1 r2": [{"exists": True}], "exists AP-2 r2": [{"exists": True}],
                "lead r1": [LEAD], "lead r2": [LEAD], "state final": [st(approaches=aps)]}
        res, labels, calls, err = run(WORKPLAN, plan, CAMPAIGN)
        self.assertIsNone(err, err)
        provers = [l for l in labels if l.startswith("prover")]
        self.assertEqual(provers, ["prover AP-1 r1", "prover AP-2 r1", "prover AP-1 r2", "prover AP-2 r2"])
        self.assertNotIn("prover AP-3 r1", labels)               # WAITING gets no prover
        self.assertNotIn("prover AP-4 r1", labels)               # --agents 2 per round
        self.assertIn("wasted slot", " ".join(res["notes"]))
        p = next(c for c in calls if c["label"] == "prover AP-1 r1")
        self.assertNotIn("AP-2", p["prompt"])                    # blind to the other approaches
        # AP-3 (waiting) and AP-4 (over the cap) never had a prover: no survivor-wide two rounds
        for r in ("lead r1", "lead r2"):
            self.assertIn("No cross-pollination", next(c for c in calls if c["label"] == r)["prompt"])
        inbox = next(c for c in calls if c["label"] == "workflow inbox.js")
        self.assertEqual(inbox["args"]["campaign"], "flat:T-1")
        self.assertTrue(inbox["args"]["nested"])
        self.assertIn("--rounds (2) reached", res["stopped"])

    def test_cross_pollination_after_every_survivor_had_two_rounds(self):
        aps = [ap("AP-1"), ap("AP-2")]
        art = {"artifact": "a.md", "kind": "lemma", "summary": "s"}
        plan = {"caps": [CAPS], "state": [st(approaches=aps)], "workflow inbox.js": [INB, INB],
                "state round 1": [st(approaches=aps)], "state round 2": [st(approaches=aps)],
                "next D-1": [{"items": ["x"]}] * 4,
                "prover AP-1 r1": [art], "prover AP-2 r1": [art], "prover AP-1 r2": [art], "prover AP-2 r2": [art],
                "exists AP-1 r1": [{"exists": True}], "exists AP-2 r1": [{"exists": True}],
                "exists AP-1 r2": [{"exists": True}], "exists AP-2 r2": [{"exists": True}],
                "lead r1": [LEAD], "lead r2": [LEAD], "state final": [st(approaches=aps)]}
        res, labels, calls, err = run(WORKPLAN, plan, CAMPAIGN)
        self.assertIsNone(err, err)
        self.assertIn("No cross-pollination", next(c for c in calls if c["label"] == "lead r1")["prompt"])
        self.assertIn("may call cross-pollination", next(c for c in calls if c["label"] == "lead r2")["prompt"])

    def test_a_proved_target_stops_and_a_failed_wave_reseeds(self):
        aps = [ap("AP-1")]
        plan = {"caps": [CAPS], "state": [st(approaches=aps)], "workflow inbox.js": [INB, INB],
                "state round 1": [st(approaches=aps)], "next D-1": [{"items": ["x"]}] * 3,
                "prover AP-1 r1": [{"artifact": "", "kind": "none", "summary": "nothing"}],
                "lead r1": [LEAD], "state round 2": [st(approaches=aps)],
                "reseed 2": [LEAD], "state round 2 reseeded": [st(approaches=aps)],
                "prover AP-1 r2": [{"artifact": "a.md", "kind": "lemma", "summary": "s"}],
                "exists AP-1 r2": [{"exists": True}], "lead r2": [LEAD], "state final": [st(approaches=aps)]}
        res, labels, _, err = run(WORKPLAN, plan, CAMPAIGN)
        self.assertIsNone(err, err)
        self.assertIn("reseed 2", labels)
        plan = {"caps": [CAPS], "state": [st(approaches=aps)], "workflow inbox.js": [INB],
                "state round 1": [st(approaches=aps, target="proved")], "state final": [st(target="proved")]}
        res, labels, _, err = run(WORKPLAN, plan, CAMPAIGN)
        self.assertIn("target is proved", res["stopped"])
        self.assertFalse(any(l.startswith("prover") for l in labels))


@unittest.skipUnless(NODE, "node is not installed")
class CoworkTests(unittest.TestCase):
    def test_one_pass_runs_the_next_actors_within_agents(self):
        plan = {"state before": [st(receivers=["author@t", "expert@t", "human"], out=["T-1", "T-2"])],
                "workflow inbox.js": [{"taken": [{"id": "T-1", "instance": "author@t", "outcome": "worked", "detail": "d"}],
                                       "notes": [], "count": 1}],
                "state after": [st("WAITING", out=["T-2"])]}
        res, labels, calls, err = run(WORKPLAN, plan, {"kind": "cowork", "root": "/a", "slug": "flat-foundations", "agents": 1})
        self.assertIsNone(err, err)
        inbox = next(c for c in calls if c["label"] == "workflow inbox.js")
        self.assertEqual(inbox["args"]["only"], ["author@t", "expert@t"])   # never 'human'
        self.assertEqual((inbox["args"]["cap"], inbox["args"]["cowork"]), (1, "flat-foundations"))
        self.assertEqual(res["plan_log"], ["T-1 (author@t): worked - d"])
        self.assertIn("/author:sweep", " ".join(res["notes"]))
        self.assertFalse(any(l.startswith("prover") for l in labels))


@unittest.skipUnless(NODE, "node is not installed")
class InboxNestedTests(unittest.TestCase):
    def test_nested_routes_come_back_for_main(self):
        row = {"id": "T-1", "kind": "verify", "status": "open", "from": "a", "to": "expert@t", "final_to": "",
               "refs": ["paper:lem:x"], "budget_runs": 1, "route": {"how": "skill", "target": "expert:verify", "why": ""},
               "return": False, "released": False, "over_budget": None}
        listed = {"instances": [{"name": "expert@t", "role": "expert", "home": "/h", "waiting": 1, "rows": [row]}]}
        res, labels, _, err = run(INBOX, {"list": [listed]}, {"root": "/a", "nested": True})
        self.assertIsNone(err, err)
        self.assertEqual(res["for_main"]["skill"], "expert:verify")
        self.assertNotIn("workflow verify.js", labels)

    def test_a_prove_ticket_runs_prove_nested(self):
        row = {"id": "T-2", "kind": "prove", "status": "open", "from": "a", "to": "researcher@u", "final_to": "",
               "refs": ["flat:GEO-3"], "budget_runs": 1, "route": {"how": "skill", "target": "researcher:prove", "why": ""},
               "return": False, "released": False, "over_budget": None}
        listed = {"instances": [{"name": "researcher@u", "role": "researcher", "home": "/h/nb", "waiting": 1, "rows": [row]}]}
        res, labels, calls, err = run(INBOX, {"list": [listed],
                                              "workflow prove.js": [{"outcome": "verify-filed", "verify_ticket": "T-9"}],
                                              "check T-2": [{"exit": 0, "status": "delivered", "detail": ""}]},
                                      {"root": "/a"})
        self.assertIsNone(err, err)
        wf = next(c for c in calls if c["label"] == "workflow prove.js")
        self.assertEqual(wf["args"]["claim"], "flat:GEO-3")
        self.assertEqual(res["taken"][0]["outcome"], "verify-filed")


if __name__ == "__main__":
    unittest.main()
