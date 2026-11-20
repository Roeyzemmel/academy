"""The maintenance-round workflow (academy/workflows/maintain.js).

Under node with a fake ``agent()``: tasks that share a file share a lane and are stacked,
the others run in lanes of their own; a blocking finding gets one fix round and a second
look, and a task that still has one is not pushed, nor is anything stacked on it; the
lanes' tips are gated together; the plan's rules (a usable topic, a file, a measure, the
cap as waves) are applied in code; a lost develop stage is salvaged and a stage that throws
loses no lane; ``after`` and ``on`` stack tasks explicitly. Skipped where node is absent.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "workflows", "maintain.js")
NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs')
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^export const meta/m, 'const meta')
const plan = JSON.parse(process.argv[3])
const calls = [], logs = []
async function agent(prompt, opts) {
  calls.push({ label: opts.label, agentType: opts.agentType, prompt })
  const q = plan[opts.label]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned agent ' + opts.label)
  return q.shift()
}
async function pipeline(items, ...stages) {
  return Promise.all(items.map(async (it, i) => {
    let v = it
    try { for (const s of stages) v = await s(v, it, i) } catch (e) { return null }
    return v
  }))
}
const body = new Function('args', 'agent', 'phase', 'log', 'pipeline', 'return (async () => {' + src + '})()')
// as the skills pass it (models.py launches prints {} under the default map); null: not given (#83)
body(Object.assign({ models: {} }, plan.__args), agent, () => {}, m => logs.push(m), pipeline).then(
  r => console.log(JSON.stringify({ result: r, calls, logs })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""

ARGS = {"root": "/acad", "workspace": "/ws", "base": "2026-11-14/base/human"}


def task(slug, files, **kw):
    t = {"slug": slug, "title": "Fix " + slug, "kind": "slow", "files": files,
         "measure": "time x", "why": "it is slow"}
    t.update(kw)
    return t


def done(slug, ok=True, **kw):
    d = {"ok": ok, "reason": "" if ok else "not in this repo", "branch": "2026-11-14/%s/human" % slug,
         "worktree": "/acad/.claude/worktrees/" + slug, "sha": "abc" + slug[:1], "before": "27 s",
         "after": "1 s", "tests": "Ran 5 tests OK", "files": ["x.py"], "summary": "fixed " + slug}
    d.update(kw)
    return d


def review(*severities):
    return {"examined": "the diff and its callers",
            "findings": [{"severity": s, "file": "x.py", "line": 3, "what": "wrong", "trigger": "t"}
                         for s in severities]}


def pushed(ok=True):
    return {"ok": ok, "sha": "def", "detail": "pushed" if ok else "push gate: suite failed"}


@unittest.skipUnless(NODE, "node is not installed")
class MaintainWorkflow(unittest.TestCase):
    def run_wf(self, plan, **args):
        plan = dict(plan, __args=dict(ARGS, **args))
        d = tempfile.mkdtemp(prefix="acad-mt-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(plan)], capture_output=True, text=True,
                           timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        return out["result"], out["calls"]

    def prompt(self, calls, label):
        return [c for c in calls if c["label"] == label][0]["prompt"]

    def test_tasks_sharing_a_file_are_stacked_and_the_lanes_are_gated_together(self):
        tasks = [task("aaa", ["academy/scripts/x.py"]), task("bbb", ["expert/scripts"]),
                 task("ccc", ["academy/scripts/x.py", "academy/tests/t.py"]),
                 task("ddd", ["expert/scripts/y.py"])]
        plan = {"union": [{"ok": True, "merged": ["m"], "conflict": "", "gate": ["ci: ok"]}]}
        for s in ("aaa", "bbb", "ccc", "ddd"):
            plan.update({"develop " + s: [done(s)], "review " + s: [review("minor")],
                         "push " + s: [pushed()]})
        r, calls = self.run_wf(plan, tasks=tasks)
        self.assertTrue(r["ok"], r)
        self.assertEqual([["aaa", "ccc"], ["bbb", "ddd"]], r["lanes"])
        self.assertIn("--on 2026-11-14/base/human", self.prompt(calls, "develop aaa"))
        self.assertIn("--on 2026-11-14/aaa/human", self.prompt(calls, "develop ccc"))   # stacked
        self.assertIn("--on 2026-11-14/bbb/human", self.prompt(calls, "develop ddd"))
        self.assertIn("--branches 2026-11-14/ccc/human 2026-11-14/ddd/human", self.prompt(calls, "union"))
        self.assertEqual([("2026-11-14/aaa/human", "2026-11-14/base/human"),
                          ("2026-11-14/ccc/human", "2026-11-14/aaa/human"),
                          ("2026-11-14/bbb/human", "2026-11-14/base/human"),
                          ("2026-11-14/ddd/human", "2026-11-14/bbb/human")],
                         [(p["head"], p["base"]) for p in r["pull_requests"]])
        self.assertIn("before: 27 s", r["pull_requests"][0]["body"])
        # the writer never reviews: two agent types, and the reviewer is told to change nothing
        self.assertEqual({"scientist:developer"}, {c["agentType"] for c in calls if c["label"].startswith(("develop", "push"))})
        self.assertEqual({"scientist:test-engineer"}, {c["agentType"] for c in calls if c["label"].startswith("review")})
        self.assertIn("Read-only", self.prompt(calls, "review aaa"))
        self.assertNotIn("survey", [c["label"] for c in calls])        # tasks were given
        self.assertEqual(4, len(r["cleanup"]))

    def test_a_blocking_finding_gets_one_fix_round_and_a_second_look(self):
        plan = {"develop aaa": [done("aaa")], "review aaa": [review("blocking", "minor")],
                "fix aaa": [done("aaa", sha="fixed1", summary="handled the empty board")],
                "re-review aaa": [review()], "push aaa": [pushed()]}
        r, calls = self.run_wf(plan, tasks=[task("aaa", ["x.py"])])
        self.assertTrue(r["ok"], r)
        t = r["tasks"][0]
        self.assertEqual(("clean after one fix", True), (t["review"], t["pushed"]))
        self.assertIn('"severity":"blocking"', self.prompt(calls, "fix aaa"))
        self.assertNotIn('"severity":"minor"', self.prompt(calls, "fix aaa"))
        self.assertIn("fix round: handled the empty board", r["pull_requests"][0]["body"])
        self.assertNotIn("union", [c["label"] for c in calls])          # one lane: its own gate
        self.assertTrue(r["union"]["ok"])

    def test_what_is_still_blocked_is_not_pushed_and_nothing_is_built_on_it(self):
        plan = {"develop aaa": [done("aaa")], "review aaa": [review("blocking")],
                "fix aaa": [done("aaa")], "re-review aaa": [review("blocking")],
                "develop bbb": [done("bbb")], "review bbb": [review()], "push bbb": [pushed(False)],
                "develop ddd": [done("ddd", ok=False)]}
        tasks = [task("aaa", ["x.py"]), task("ccc", ["x.py"]), task("bbb", ["y.py"]), task("ddd", ["z.py"])]
        r, calls = self.run_wf(plan, tasks=tasks)
        self.assertFalse(r["ok"])
        by = {t["slug"]: t for t in r["tasks"]}
        self.assertEqual([False] * 4, [by[s]["pushed"] for s in ("aaa", "ccc", "bbb", "ddd")])
        self.assertIn("remain after one fix round", by["aaa"]["reason"])
        self.assertIn("not started: aaa", by["ccc"]["reason"])
        self.assertIn("push gate: suite failed", by["bbb"]["reason"])
        self.assertEqual("not in this repo", by["ddd"]["reason"])
        labels = [c["label"] for c in calls]
        self.assertNotIn("push aaa", labels)
        self.assertNotIn("develop ccc", labels)
        self.assertNotIn("review ddd", labels)
        self.assertEqual([], r["pull_requests"])
        self.assertIn("some tasks were not pushed", r["reason"])

    def test_a_lost_review_is_never_a_push_and_a_failed_union_is_not_ok(self):
        plan = {"develop aaa": [done("aaa")], "review aaa": [None],
                "develop bbb": [done("bbb")], "review bbb": [review()], "push bbb": [pushed()],
                "develop ccc": [done("ccc")], "review ccc": [review()], "push ccc": [pushed()],
                "union": [{"ok": False, "merged": ["2026-11-14/bbb/human"],
                           "conflict": "2026-11-14/ccc/human: CONFLICT in t.py", "gate": []}]}
        r, calls = self.run_wf(plan, tasks=[task("aaa", ["x.py"]), task("bbb", ["y.py"]), task("ccc", ["z.py"])])
        self.assertFalse(r["ok"])
        self.assertIn("not pushed unreviewed", r["tasks"][0]["reason"])
        self.assertNotIn("push aaa", [c["label"] for c in calls])
        self.assertIn("do not pass together: 2026-11-14/ccc/human: CONFLICT", r["reason"])
        self.assertEqual(2, len(r["pull_requests"]))

    def test_the_survey_feeds_the_plan_and_the_plans_rules_are_applied_in_code(self):
        cands = [{"kind": "slow", "id": "slow:x", "title": "x takes 27 s", "evidence": "budget 5"}]
        tasks = [task("ok-one", ["a.py"]), task("Bad Slug", ["b.py"]), task("ok-one", ["c.py"]),
                 task("nofile", []), task("nomeasure", ["d.py"], measure=""),
                 task("ok-two", ["e.py"]), task("ok-three", ["f.py"])]
        plan = {"survey": [{"ok": True, "error": "", "candidates": cands, "notes": ["n"]}],
                "plan": [{"tasks": tasks, "skipped": [{"id": "ledger:net", "reason": "the network"}]}],
                "union": [{"ok": True, "merged": [], "conflict": "", "gate": []}]}
        for s in ("ok-one", "ok-two", "ok-three"):
            plan.update({"develop " + s: [done(s)], "review " + s: [review()], "push " + s: [pushed()]})
        r, calls = self.run_wf(plan, cap=2)
        self.assertIn("maintain.py survey --days 7 --json", self.prompt(calls, "survey"))
        self.assertIn("slow:x", self.prompt(calls, "plan"))
        # the cap bounds the lanes at a time: the third task runs in a second wave
        self.assertEqual(["ok-one", "ok-two", "ok-three"], [t["slug"] for t in r["tasks"]])
        self.assertEqual(4, len(r["dropped"]), r["dropped"])
        self.assertNotIn("ok-three", " ".join(r["dropped"]))
        self.assertEqual([{"id": "ledger:net", "reason": "the network"}], r["skipped"])
        self.assertTrue(r["ok"])

    def test_a_lost_develop_stage_is_salvaged_and_a_lost_salvage_loses_no_lane(self):
        """2026-11-20: a developer that ended without its structured output threw, and the
        whole lane was lost with its work uncommitted. Now the stage is lost, a salvage run
        commits what passes, and the lane records what happened."""
        # 'develop aaa' is unplanned: the fake agent throws, as the runtime did
        plan = {"salvage aaa": [done("aaa", summary="salvaged: the change and its tests")],
                "review aaa": [review()], "push aaa": [pushed()],
                "develop bbb": [None], "salvage bbb": [None]}
        r, calls = self.run_wf(plan, tasks=[task("aaa", ["x.py"]), task("bbb", ["y.py"])])
        by = {t["slug"]: t for t in r["tasks"]}
        self.assertTrue(by["aaa"]["pushed"])
        self.assertTrue(by["aaa"]["salvaged"])
        self.assertIn("ended without its result", self.prompt(calls, "salvage aaa"))
        self.assertIn("--all", self.prompt(calls, "salvage aaa"))
        self.assertFalse(by["bbb"]["pushed"])
        self.assertIn("the develop stage and its salvage returned nothing", by["bbb"]["reason"])
        self.assertNotIn("lane failed", " ".join(t["reason"] for t in r["tasks"] if "reason" in t))

    def test_a_stage_that_throws_after_develop_is_a_lost_stage_not_a_lost_lane(self):
        plan = {"develop aaa": [done("aaa")]}             # 'review aaa' throws
        r, calls = self.run_wf(plan, tasks=[task("aaa", ["x.py"])])
        self.assertIn("not pushed unreviewed", r["tasks"][0]["reason"])

    def test_after_stacks_tasks_that_share_no_file_and_on_stacks_on_a_pushed_branch(self):
        tasks = [task("ccc", ["c.py"], after="aaa"), task("aaa", ["a.py"]),
                 task("bbb", ["b.py"], on="2026-11-13/earlier/human"),
                 task("eee", ["e.py"], after="nope")]
        plan = {"union": [{"ok": True, "merged": [], "conflict": "", "gate": []}]}
        for s in ("aaa", "bbb", "ccc"):
            plan.update({"develop " + s: [done(s)], "review " + s: [review()], "push " + s: [pushed()]})
        r, calls = self.run_wf(plan, tasks=tasks)
        self.assertEqual([["aaa", "ccc"], ["bbb"]], r["lanes"])
        self.assertIn("--on 2026-11-14/aaa/human", self.prompt(calls, "develop ccc"))
        self.assertIn("--on 2026-11-13/earlier/human", self.prompt(calls, "develop bbb"))
        self.assertIn("eee: after nope", " ".join(r["dropped"]))

    def test_a_throw_in_a_lanes_second_task_keeps_the_first_tasks_record(self):
        """Review of eed6eba: a malformed review of the second task threw inside one() and
        took the pushed first task's record with it."""
        plan = {"develop aaa": [done("aaa")], "review aaa": [review()], "push aaa": [pushed()],
                "develop bbb": [done("bbb")], "review bbb": [{"examined": "x"}]}
        r, calls = self.run_wf(plan, tasks=[task("aaa", ["a.py"]), task("bbb", ["a.py"])])
        by = {t["slug"]: t for t in r["tasks"]}
        self.assertTrue(by["aaa"]["pushed"])
        self.assertIn("no findings list", by["bbb"]["reason"])

    def test_a_lost_union_stage_still_returns_the_round(self):
        plan = {}
        for s in ("aaa", "bbb"):
            plan.update({"develop " + s: [done(s)], "review " + s: [review()], "push " + s: [pushed()]})
        r, calls = self.run_wf(plan, tasks=[task("aaa", ["a.py"]), task("bbb", ["b.py"])])
        self.assertFalse(r["ok"])
        self.assertEqual("the union stage returned nothing", r["union"]["conflict"])
        self.assertEqual(2, len(r["pull_requests"]))

    def test_after_chains_cycles_and_on_are_validated(self):
        tasks = [task("aaa", ["a.py"], after="bbb"), task("bbb", ["b.py"], after="nope"),
                 task("ccc", ["c.py"], after="ddd"), task("ddd", ["d.py"], after="ccc"),
                 task("eee", ["e.py"], after="fff", on="2026-11-13/x/human"), task("fff", ["f.py"]),
                 task("ggg", ["f.py"], on="2026-11-13/y/human")]
        plan = {}
        for s in ("fff", "ggg"):
            plan.update({"develop " + s: [done(s)], "review " + s: [review()], "push " + s: [pushed()]})
        r, calls = self.run_wf(plan, tasks=tasks, cap=8)
        dropped = " ".join(r["dropped"])
        self.assertIn("bbb: after nope", dropped)
        self.assertIn("aaa: after bbb", dropped)            # its target was dropped
        self.assertIn("a cycle", dropped)
        self.assertIn("eee: both after fff and on", dropped)
        self.assertIn("ggg: on 2026-11-13/y/human ignored", dropped)
        self.assertEqual([["fff", "ggg"]], r["lanes"])

    def test_the_develop_brief_asks_for_early_commits(self):
        plan = {"develop aaa": [done("aaa")], "review aaa": [review()], "push aaa": [pushed()]}
        r, calls = self.run_wf(plan, tasks=[task("aaa", ["x.py"])])
        self.assertIn("after every step whose tests pass", self.prompt(calls, "develop aaa"))

    def test_nothing_to_do_and_missing_arguments(self):
        r, calls = self.run_wf({"survey": [{"ok": True, "error": "", "candidates": [], "notes": []}]})
        self.assertTrue(r["ok"])
        self.assertIn("no candidate", r["reason"])
        self.assertEqual(["survey"], [c["label"] for c in calls])
        r, calls = self.run_wf({"survey": [{"ok": False, "error": "no workspace", "candidates": [], "notes": []}]})
        self.assertFalse(r["ok"])
        r, calls = self.run_wf({}, base="")
        self.assertEqual((False, []), (r["ok"], calls))


if __name__ == "__main__":
    unittest.main()
