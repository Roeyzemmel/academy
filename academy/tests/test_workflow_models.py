"""The workflows launch every agent on the workspace's model for its tier (T-0350, item 3).

A workflow script cannot read workspace.json, so the skill that runs it passes
``args.models``, the JSON object of ``models.py launches`` (the agents whose tier this
workspace maps away from their file's ``model:``). Every workflow carries the same
``Models`` block (docs/workflows.md, "Models"), launches every agent through its
``launch()``, and hands the same map to the workflows it nests. This pins the block, that
no agent is launched around it, that nested workflows get the map, what ``launch()`` does
with it (under node), and that every skill that runs a workflow says to pass it.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "academy" / "lib"))
import academy_common as ac  # noqa: E402

NODE = shutil.which("node")
WORKFLOWS = sorted(Path(p).relative_to(REPO).as_posix()
                   for p in glob.glob(str(REPO / "*" / "workflows" / "*.js")))
BLOCK = re.compile(r"^// ---- Models \(docs/workflows\.md.*?^// ---- end Models\n", re.M | re.S)
BARE_AGENT = re.compile(r"(?<![\w.$])agent\(")
NESTED = re.compile(r"(?<![\w.$])workflow\(")
#: a model named in a script: the tier decides instead (an agent file's, or ``tier:``)
LITERAL_MODEL = re.compile(r"(?<![\w.$])model:\s*['\"`]")
SCRIPT_TIER = re.compile(r"(?<![\w.$])tier:\s*['\"`](\w*)")
#: a skill's Workflow call: the map is the first key of its args
SKILL_ARGS = re.compile(r'args: \{models: <the JSON object that py "\$\{CLAUDE_PLUGIN_ROOT\}([^"]*)/models\.py" launches prints>')

HARNESS = r"""
const block = require('fs').readFileSync(process.argv[2], 'utf8')
const plan = JSON.parse(process.argv[3])
const calls = []
const prompts = []
let answers = {}
async function agent(prompt, opts) {
  calls.push(opts); prompts.push(prompt)
  return Object.prototype.hasOwnProperty.call(answers, opts.label) ? answers[opts.label] : 'ok'
}
const body = new Function('A', 'agent', block + '\nreturn { launch, TIER_MODELS, TIER_DEFAULTS, MODELS, LAUNCH_LIMIT }')
const out = []
;(async () => {
  for (const c of plan.cases) {
    calls.length = 0; prompts.length = 0; answers = c.answers || {}
    try {
      const { launch, TIER_MODELS, TIER_DEFAULTS, MODELS, LAUNCH_LIMIT } = body(c.args, agent)
      const n = c.times || 1
      let results = []
      if (c.parallel) results = await Promise.all(Array.from({ length: n }, () => launch('p', c.opts)))
      else for (let i = 0; i < n; i++) results.push(await launch('p', c.opts))
      const last = calls[calls.length - 1]
      out.push({ opts: last, first: calls[0], labels: calls.map(x => x.label), prompts: prompts.slice(),
                 map: TIER_MODELS, defaults: TIER_DEFAULTS, same: last === c.opts, source: MODELS.source,
                 results, stopped: LAUNCH_LIMIT.stopped })
    } catch (e) { out.push({ error: String(e), calls: calls.length }) }
  }
  console.log(JSON.stringify(out))
})().catch(e => console.log(JSON.stringify({ error: String(e) })))
"""


def text(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def block_of(rel):
    m = BLOCK.search(text(rel))
    return m.group(0) if m else None


class TheBlock(unittest.TestCase):
    def test_there_are_workflows(self):
        self.assertGreaterEqual(len(WORKFLOWS), 15, WORKFLOWS)

    def test_every_workflow_carries_the_same_block(self):
        blocks = {rel: block_of(rel) for rel in WORKFLOWS}
        self.assertEqual([r for r, b in blocks.items() if not b], [])
        self.assertEqual(len(set(blocks.values())), 1, "the Models block differs between workflows")

    def test_no_agent_is_launched_around_launch(self):
        for rel in WORKFLOWS:
            rest = BLOCK.sub("", text(rel))
            bare = [rest[max(0, m.start() - 40):m.end() + 20] for m in BARE_AGENT.finditer(rest)]
            self.assertEqual(bare, [], "%s launches agent() directly" % rel)
            self.assertIn("launch(", rest, rel)

    def test_no_script_reads_a_clock_or_randomness(self):
        """The workflow runtime throws on Date.now(), an argless new Date() and
        Math.random() (they would break resume); a test harness under node does not."""
        bad = re.compile(r"Date\.now\(|new Date\(\s*\)|Math\.random\(")
        for rel in WORKFLOWS:
            hits = [m.group(0) for m in bad.finditer(text(rel))]
            self.assertEqual(hits, [], rel)

    def test_no_script_names_a_model(self):
        for rel in WORKFLOWS:
            rest = BLOCK.sub("", text(rel))
            named = [rest[max(0, m.start() - 60):m.end() + 20] for m in LITERAL_MODEL.finditer(rest)]
            self.assertEqual(named, [], "%s names a model: give the agent a tier" % rel)

    def test_a_tier_a_script_names_is_a_tier(self):
        seen = []
        for rel in WORKFLOWS:
            for m in SCRIPT_TIER.finditer(BLOCK.sub("", text(rel))):
                seen.append(m.group(1))
                self.assertIn(m.group(1), ac.TIERS, rel)
        self.assertIn("medium", seen)                # notes.js's general-purpose filer

    def test_the_block_points_at_a_section_that_exists(self):
        docs = (REPO / "academy" / "docs" / "workflows.md").read_text(encoding="utf-8")
        self.assertRegex(docs, r"(?m)^## Models\b")
        section = re.search(r"(?ms)^## Models\b.*?(?=^## )", docs).group(0)
        for needle in ("args.models", "models.py launches", "launch(", "tier:", "nested", "not given",
                       "no override", "modelsMap()"):
            self.assertIn(needle.lower(), section.lower())
        config = (REPO / "academy" / "docs" / "config.md").read_text(encoding="utf-8")
        self.assertIn("models.py launches", config)
        self.assertIn('docs/workflows.md, "Models"', config)

    def test_nested_workflows_get_the_map(self):
        seen = 0
        for rel in WORKFLOWS:
            src = text(rel)
            for m in NESTED.finditer(src):
                seen += 1
                call = src[m.start():m.start() + 260]
                self.assertIn("models: await modelsMap()", call, "%s: %s" % (rel, call))
        self.assertGreaterEqual(seen, 11)          # inbox.js's routes and workplan.js's inbox


@unittest.skipUnless(NODE, "node not installed")
class LaunchUnderNode(unittest.TestCase):
    def run_cases(self, cases):
        block = block_of("expert/workflows/verify.js")
        tmp = REPO / "academy" / "tests" / ("_models_block_%d.js" % os.getpid())
        tmp.write_text(block, encoding="utf-8")
        self.addCleanup(tmp.unlink)
        h = REPO / "academy" / "tests" / ("_models_harness_%d.js" % os.getpid())
        h.write_text(HARNESS, encoding="utf-8")
        self.addCleanup(h.unlink)
        proc = subprocess.run([NODE, str(h), str(tmp), json.dumps({"cases": cases})],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertNotIn("error", out if isinstance(out, dict) else {}, out)
        return out

    def test_the_map_sets_the_model_of_its_agents_only(self):
        fable = {"expert:rigor-reviewer": "fable"}
        out = self.run_cases([
            {"args": {"models": fable},
             "opts": {"label": "run A", "agentType": "expert:rigor-reviewer"}},
            # the map wins over a model the script names
            {"args": {"models": fable},
             "opts": {"label": "run A", "agentType": "expert:rigor-reviewer", "model": "opus"}},
            # an agent the map does not name keeps its options, untouched
            {"args": {"models": fable},
             "opts": {"label": "c", "agentType": "expert:clerk", "model": "haiku"}},
            {"args": {"models": fable}, "opts": {"label": "g", "agentType": "general-purpose"}},
        ])
        self.assertEqual(out[0]["opts"], {"label": "run A", "agentType": "expert:rigor-reviewer",
                                          "model": "fable"})
        self.assertEqual(out[1]["opts"]["model"], "fable")
        self.assertFalse(out[0]["same"])            # a copy: the caller's options unchanged
        self.assertEqual(out[2]["opts"], {"label": "c", "agentType": "expert:clerk", "model": "haiku"})
        self.assertTrue(out[2]["same"])
        self.assertNotIn("model", out[3]["opts"])

    def test_bad_entries_of_a_given_map_change_nothing(self):
        opts = {"label": "run A", "agentType": "expert:rigor-reviewer", "model": "opus"}
        out = self.run_cases([
            {"args": {"models": {"expert:rigor-reviewer": 3}}, "opts": opts},
            {"args": {"models": {"expert:rigor-reviewer": ""}}, "opts": opts},
            {"args": {"models": {"constructor": "fable"}},
             "opts": {"label": "x", "agentType": "constructor"}},
            {"args": {"models": {"toString": "fable"}}, "opts": {"label": "y", "agentType": "hasOwnProperty"}},
        ])
        for o in out[:2]:
            self.assertEqual(o["opts"]["model"], "opus")
            self.assertTrue(o["same"])
            self.assertEqual(o["labels"], ["run A"])        # a given map: no stage
        self.assertEqual(out[2]["opts"]["model"], "fable")   # an own key is a key
        self.assertNotIn("model", out[3]["opts"])            # an inherited name is not

    def test_an_empty_map_given_is_no_override_and_runs_no_stage(self):
        """#83: {} is what models.py launches prints when the workspace maps nothing away;
        given, it is the map, not a missing one."""
        opts = {"label": "run A", "agentType": "expert:rigor-reviewer", "model": "opus"}
        out = self.run_cases([{"args": {"models": {}}, "opts": opts, "times": 2}])
        self.assertEqual(out[0]["labels"], ["run A", "run A"])
        self.assertTrue(out[0]["same"])
        self.assertEqual((out[0]["map"], out[0]["source"]), ({}, "args"))

    def test_a_map_not_given_is_resolved_once_by_models_py_launches(self):
        """#83: a run started without args.models (the 2026-11-20 inbox run) resolved
        nothing and launched the max-tier agents on their file's opus."""
        printed = '{"expert:rigor-reviewer": "fable", "tier:max": "fable"}\n'
        opts = {"label": "run A", "agentType": "expert:rigor-reviewer"}
        out = self.run_cases([
            {"args": {"root": "/acad/"}, "opts": opts, "times": 2, "answers": {"models": {"output": printed}}},
            {"args": {"models": None}, "opts": opts, "answers": {"models": {"output": "```json\n" + printed + "```"}}},
            {"args": {}, "opts": opts, "times": 3, "parallel": True, "answers": {"models": {"output": printed}}},
        ])
        for o in out:
            self.assertNotIn("error", o, o.get("error"))
            self.assertEqual(o["labels"][0], "models")
            self.assertEqual(o["labels"].count("models"), 1)          # once per run
            self.assertEqual(o["opts"]["model"], "fable")
            self.assertEqual(o["map"], {"expert:rigor-reviewer": "fable", "tier:max": "fable"})
            self.assertEqual(o["source"], "resolved")
            stage = o["first"]
            self.assertEqual((stage["agentType"], stage["model"]), ("general-purpose", "haiku"))
            self.assertNotIn("tier", stage)
        self.assertEqual(out[0]["labels"], ["models", "run A", "run A"])
        self.assertIn("`py /acad/academy/scripts/models.py launches`", out[0]["prompts"][0])
        self.assertIn("<academy repo>/academy/scripts/models.py launches", out[1]["prompts"][0])
        self.assertIn("workspace_get", out[1]["prompts"][0])

    def test_a_map_that_cannot_be_resolved_is_refused_loudly(self):
        opts = {"label": "run A", "agentType": "expert:rigor-reviewer"}
        out = self.run_cases([
            {"args": {"root": "/acad"}, "opts": opts,
             "answers": {"models": {"output": "models: workspace.json not found"}}},
            {"args": {"root": "/acad"}, "opts": opts, "answers": {"models": {"output": "[1, 2]"}}},
            # a map inside prose is refused, never guessed (review of abf478f)
            {"args": {"root": "/acad"}, "opts": opts,
             "answers": {"models": {"output": 'The map is {"expert:rigor-reviewer": "fable"} I think'}}},
        ])
        for o in out:
            self.assertIn("args.models was not given", o.get("error", ""))
            self.assertIn("rerun with args.models", o["error"])
            self.assertIn("py /acad/academy/scripts/models.py launches", o["error"])
            self.assertEqual(o["calls"], 1)                         # the stage only: nothing launched
        self.assertIn("workspace.json not found", out[0]["error"])

    def test_a_lookup_that_returns_nothing_stops_the_run_like_a_usage_limit(self):
        """Review of abf478f: a null lookup (a usage limit at the start) must stop the run the
        way three null launches do (#115), not throw: the inbox then returns stopped."""
        opts = {"label": "run A", "agentType": "expert:rigor-reviewer"}
        out = self.run_cases([{"args": {"root": "/acad"}, "opts": opts, "times": 2,
                               "answers": {"models": None}}])
        o = out[0]
        self.assertNotIn("error", o, o.get("error"))
        self.assertEqual([None, None], o["results"])
        self.assertTrue(o["stopped"])
        self.assertNotIn("run A", o["labels"])                    # nothing launched after it
        self.assertIn("python3 /acad/academy/scripts/models.py launches", o["prompts"][0])

    def test_a_malformed_map_is_refused_before_anything_is_launched(self):
        opts = {"label": "run A", "agentType": "expert:rigor-reviewer"}
        out = self.run_cases([{"args": {"models": bad}, "opts": opts}
                              for bad in (["fable"], "fable", 3, True, "[1]")])
        for o in out:
            self.assertIn("args.models is no JSON object", o.get("error", ""))
            self.assertIn("models.py launches", o["error"])
            self.assertEqual(o["calls"], 0)

    def test_a_map_given_as_json_text_is_read(self):
        out = self.run_cases([{"args": {"models": '{"expert:rigor-reviewer": "fable"}'},
                               "opts": {"label": "run A", "agentType": "expert:rigor-reviewer"}}])
        self.assertEqual((out[0]["labels"], out[0]["opts"]["model"], out[0]["source"]), (["run A"], "fable", "args"))

    def test_an_agent_with_no_file_is_launched_by_tier(self):
        gp = {"label": "file", "agentType": "general-purpose", "tier": "medium"}
        out = self.run_cases([
            {"args": {"models": {}}, "opts": gp},
            {"args": {"models": {"tier:medium": "opus"}}, "opts": gp},
            {"args": {"models": {"tier:max": "fable"}}, "opts": gp},
            {"args": {"models": {}}, "opts": {"label": "x", "agentType": "general-purpose", "tier": "huge"}},
            {"args": {"models": {}}, "opts": {"label": "x", "agentType": "general-purpose", "tier": "constructor"}},
        ])
        self.assertEqual(out[0]["opts"], {"label": "file", "agentType": "general-purpose", "model": "sonnet"})
        self.assertEqual(out[1]["opts"]["model"], "opus")
        self.assertEqual(out[2]["opts"]["model"], "sonnet")   # another tier's key is not this one's
        for o in out[3:]:
            self.assertIn("unknown tier", o["error"])
            self.assertEqual(o["calls"], 0)                    # nothing launched

    def test_the_tier_defaults_are_the_academy_default_map(self):
        out = self.run_cases([{"args": {"models": {}}, "opts": {"label": "x"}}])
        self.assertEqual(out[0]["defaults"],
                         {t: ac.launch_model(ac.DEFAULT_MODEL_TIERS[t]) for t in ac.TIERS})


class SkillsPassTheMap(unittest.TestCase):
    def test_every_skill_that_runs_a_workflow_passes_models_in_its_args(self):
        """The map is the first key of the Workflow call's ``args``, from the base plugin's
        models.py (the path as the skill writes it, from its own plugin root)."""
        want = (REPO / "academy" / "scripts" / "models.py").resolve()
        missing = []
        for p in sorted(glob.glob(str(REPO / "*" / "skills" / "*" / "SKILL.md"))):
            src = Path(p).read_text(encoding="utf-8")
            if "workflows/" in src and "scriptPath" in src:
                calls = SKILL_ARGS.findall(src)
                plugin_root = Path(p).parents[2]
                if not calls or any((plugin_root / c.lstrip("/") / "models.py").resolve() != want
                                    for c in calls):
                    missing.append(Path(p).relative_to(REPO).as_posix())
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
