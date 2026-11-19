"""The max-tier model of the workflows (T-1682; docs/config.md, "How the map takes effect").

The workflow runtime cannot import across files, so every workflow that launches a max-tier
agent (the prover and the graders) carries the same block (``launchModel`` / ``launchMax``).
This pins that the block is identical in each, that no workflow launches a max-tier agent
around it or hard-codes its model, and runs the block under node: the launch value from
``args.models``, else from one clerk stage running ``models.py agent <name> --launch``
(once per agent and run), an unusable value launching on the agent file's model, and a run
that returns nothing relaunched once on opus, noted. The per-workflow runs are in each
plugin's workflow tests; the inbox's one resolution per run in test_inbox_workflow.py.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
LAUNCHING = ["expert/workflows/verify.js", "expert/workflows/referee.js",
             "researcher/workflows/prove.js", "researcher/workflows/review-experiment.js",
             "researcher/workflows/generalize.js", "academy/workflows/workplan.js"]
MAX_TIER = ("expert:rigor-reviewer", "expert:referee", "researcher:experiment-reviewer",
            "researcher:prover")
BLOCK = re.compile(r"^// ---- Max-tier model \(docs/config\.md.*?^const fallbackLine = [^\n]*\n",
                   re.M | re.S)

HARNESS = r"""
const block = require('fs').readFileSync(process.argv[2], 'utf8')
const plan = JSON.parse(process.argv[3])
const calls = []
async function agent(prompt, opts) {
  calls.push({ label: opts.label, agentType: opts.agentType, model: opts.model, prompt })
  const q = plan.answers[opts.label]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned agent ' + opts.label)
  return q.shift()
}
const body = new Function('agent', 'A', 'AR', 'ROOT', 'plan', 'return (async () => {' + block + `
  const s = { agentType: 'x:clerk', phase: 'P', notes: [] }
  const results = []
  for (const l of plan.launches) results.push(await launchMax('brief', { label: l.label, agentType: l.agentType, phase: 'P' }, s))
  return { results, notes: s.notes, fallbacks: MODEL_FALLBACKS, line: fallbackLine() }})()`)
body(agent, plan.A, '/acad', '/acad', plan).then(r => console.log(JSON.stringify({ result: r, calls })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""


def block_of(rel):
    m = BLOCK.search((REPO / rel).read_text(encoding="utf-8"))
    return m.group(0) if m else None


class SameBlockEverywhere(unittest.TestCase):
    def test_every_launching_workflow_carries_the_same_block(self):
        blocks = {rel: block_of(rel) for rel in LAUNCHING}
        self.assertEqual([r for r, b in blocks.items() if not b], [])
        self.assertEqual(len(set(blocks.values())), 1, "the max-tier block differs between workflows")

    def test_no_max_tier_agent_is_launched_around_the_block(self):
        """Every launch of a max-tier agent goes through launchMax, and no workflow hard-codes
        the model of one (verify.js passed model: 'opus', T-1682). A call is the text from
        ``agent(`` or ``launchMax(`` to the next one; its first agentType names the agent."""
        launchers = set()
        for path in sorted(REPO.glob("*/workflows/*.js")):
            rel = path.relative_to(REPO).as_posix()
            text = path.read_text(encoding="utf-8").replace(block_of(rel) or "", "")
            consts = dict(re.findall(r"const (\w+) = '([a-z]+:[a-z-]+)'", text))
            parts = re.split(r"(\blaunchMax\(|(?<![\w.])agent\()", text)
            for opener, seg in zip(parts[1::2], parts[2::2]):
                m = re.search(r"agentType: (\w+|'[^']+')", seg)
                if not m:
                    continue
                name = consts.get(m.group(1), m.group(1).strip("'"))
                if name in MAX_TIER:
                    self.assertEqual(opener, "launchMax(", "%s launches %s without launchMax" % (rel, name))
                    launchers.add(rel)
            if rel in LAUNCHING:
                self.assertNotRegex(text, r"model: '(opus|fable)'", rel)
        self.assertEqual(sorted(launchers), sorted(LAUNCHING))


class LaunchSites(unittest.TestCase):
    """The launch sites of every workflow, outside the block (test-engineer's review of 1f149b8)."""

    @staticmethod
    def segments():
        for path in sorted(REPO.glob("*/workflows/*.js")):
            rel = path.relative_to(REPO).as_posix()
            text = path.read_text(encoding="utf-8").replace(block_of(rel) or "", "")
            consts = dict(re.findall(r"const (\w+) = '([a-z]+:[a-z-]+)'", text))
            parts = re.split(r"(\blaunchMax\(|(?<![\w.])agent\()", text)
            for opener, seg in zip(parts[1::2], parts[2::2]):
                yield rel, opener, seg, consts, text

    def test_every_launch_names_its_agent_type(self):
        for rel, opener, seg, _c, _t in self.segments():
            self.assertIn("agentType:", seg, "%s: an %s call without agentType" % (rel, opener))

    def test_a_max_tier_agent_is_only_ever_the_agent_of_a_launch_max(self):
        for rel, opener, seg, consts, _t in self.segments():
            types = [consts.get(t, t.strip("'")) for t in re.findall(r"agentType: (\w+|'[^']+')", seg)]
            for k, name in enumerate(types):
                if name in MAX_TIER:
                    self.assertEqual((opener, k), ("launchMax(", 0), "%s: %s launched outside launchMax" % (rel, name))

    def test_no_launching_workflow_sets_a_model_outside_the_block(self):
        for rel in LAUNCHING:
            text = (REPO / rel).read_text(encoding="utf-8").replace(block_of(rel), "")
            self.assertNotRegex(text, r"\bmodel\s*:", rel)


@unittest.skipUnless(NODE, "node is not installed")
class TheBlock(unittest.TestCase):
    def run_block(self, launches, answers, models=None):
        d = tempfile.mkdtemp(prefix="acad-max-")
        self.addCleanup(shutil.rmtree, d, True)
        h, b = os.path.join(d, "h.js"), os.path.join(d, "b.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        with open(b, "w", encoding="utf-8") as fh:
            fh.write(block_of(LAUNCHING[0]))
        plan = {"A": {"models": models} if models is not None else {},
                "launches": [{"label": l, "agentType": t} for l, t in launches], "answers": answers}
        p = subprocess.run([NODE, h, b, json.dumps(plan)], capture_output=True, text=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], out["calls"]

    def test_the_args_give_the_model_and_no_stage_runs(self):
        res, calls = self.run_block([("run A", "expert:rigor-reviewer")], {"run A": ["v"]},
                                    {"expert:rigor-reviewer": "fable"})
        self.assertEqual([(c["label"], c["model"]) for c in calls], [("run A", "fable")])
        self.assertEqual(res["results"], ["v"])
        self.assertEqual(res["notes"], [])

    def test_without_args_one_clerk_stage_resolves_it_once(self):
        res, calls = self.run_block(
            [("run A", "expert:rigor-reviewer"), ("run B", "expert:rigor-reviewer")],
            {"model expert:rigor-reviewer": [{"output": "fable\n"}], "run A": ["a"], "run B": ["b"]})
        self.assertEqual([(c["label"], c.get("model")) for c in calls],
                         [("model expert:rigor-reviewer", None), ("run A", "fable"), ("run B", "fable")])
        self.assertEqual(calls[0]["agentType"], "x:clerk")
        self.assertIn("py /acad/academy/scripts/models.py agent expert:rigor-reviewer --launch", calls[0]["prompt"])

    def test_an_unusable_value_launches_on_the_file_model_and_is_noted(self):
        res, calls = self.run_block([("attempt", "researcher:prover")],
                                    {"model researcher:prover": [{"output": "models: workspace.json not found"}],
                                     "attempt": ["x"]})
        self.assertNotIn("model", calls[-1])
        self.assertIn("was not resolved", " ".join(res["notes"]))
        # a full id in args.models is no alias: resolved by the stage instead
        res, calls = self.run_block([("attempt", "researcher:prover")],
                                    {"model researcher:prover": [{"output": "fable"}], "attempt": ["x"]},
                                    {"researcher:prover": "claude-fable-5-2"})
        self.assertEqual(calls[-1]["model"], "fable")
        self.assertIn("no launch alias", " ".join(res["notes"]))

    def test_a_lost_max_run_is_relaunched_once_on_opus(self):
        res, calls = self.run_block([("referee", "expert:referee")],
                                    {"referee": [None], "referee (opus fallback)": ["report"]},
                                    {"expert:referee": "fable"})
        self.assertEqual([(c["label"], c["model"]) for c in calls],
                         [("referee", "fable"), ("referee (opus fallback)", "opus")])
        self.assertEqual(res["results"], ["report"])
        self.assertEqual(res["fallbacks"], ["referee: fable -> opus"])
        self.assertIn("relaunched once on opus", " ".join(res["notes"]))
        self.assertEqual(res["line"], "; model fallback: referee: fable -> opus")
        # the lost run may have filed or written something: the relaunch is told to check first
        self.assertEqual(calls[1]["prompt"], "A previous run of this stage was cut off: check what it already did "
                         "(files written, tickets filed) before doing it again.\nbrief")
        self.assertEqual(calls[0]["prompt"], "brief")

    def test_the_fallback_is_tried_once_and_never_from_opus(self):
        res, calls = self.run_block([("referee", "expert:referee")],
                                    {"referee": [None], "referee (opus fallback)": [None]},
                                    {"expert:referee": "fable"})
        self.assertEqual(len(calls), 2)
        self.assertEqual(res["results"], [None])
        res, calls = self.run_block([("referee", "expert:referee")], {"referee": [None]},
                                    {"expert:referee": "opus"})
        self.assertEqual([(c["label"], c["model"]) for c in calls], [("referee", "opus")])
        self.assertEqual((res["results"], res["fallbacks"], res["line"]), ([None], [], ""))


if __name__ == "__main__":
    unittest.main()
