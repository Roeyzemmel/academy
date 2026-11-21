"""The inbox and workplan runs read their code from a pin (#97).

A merge, a branch switch or a publish during a run changed the scripts and nested
workflows it read from the academy checkout. Both workflows now start with a ``pin`` stage
(``run_pin.py start``: a worktree at the checkout's HEAD), give the pinned root to every
script command and nested workflow, record ``out.code`` (sha, root), and end with an
``unpin`` stage (``run_pin.py end``) on every way out, a throw included. A pin the caller
gives (``args.code``) is used as given and ended by the caller; a nested run (``nested:
true``) never pins; ``pin: false`` runs on the live checkout. A pin stage that returns no
pin is a note, never a failed run. Under node with a fake ``agent()``; skipped without node.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
INBOX = os.path.join(PLUGIN, "workflows", "inbox.js")
WORKPLAN = os.path.join(PLUGIN, "workflows", "workplan.js")
NODE = shutil.which("node")
BLOCK = re.compile(r"^// ---- Code pin \(docs/workflows\.md.*?^// ---- end Code pin\n", re.M | re.S)

HARNESS = r"""
const fs = require('fs')
const src = fs.readFileSync(process.argv[2], 'utf8').replace(/^export const meta/m, 'const meta')
const plan = JSON.parse(process.argv[3])
const calls = []
async function agent(prompt, opts) {
  calls.push({ label: opts.label, agentType: opts.agentType, model: opts.model, prompt })
  const q = plan[opts.label]
  if (!Array.isArray(q) || !q.length) throw new Error('unplanned agent ' + opts.label)
  const v = q.shift()
  if (v && v.__throw) throw new Error(v.__throw)
  return v
}
async function workflow(ref, a) {
  const name = ref.scriptPath.split('/').pop()
  calls.push({ label: 'workflow ' + name, scriptPath: ref.scriptPath, args: a })
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

SHA = "0123456789abcdef0123456789abcdef01234567"
PIN = "/academy/.worktrees/run-0123456789ab"
RUN = "inbox-all-20261121T100000-77"
PINNED = {"pinned": True, "root": PIN, "sha": SHA, "run": RUN, "source": "/academy",
          "reused": False, "dirty": 0, "cleaned": [], "why": "pinned at 0123456789ab"}
ENDED = {"exit": 0, "output": json.dumps({"ended": True, "run": RUN, "sha": SHA, "root": PIN})}
OK = {"ok": True, "status": "x", "detail": ""}
DONE = {"exit": 0, "status": "delivered", "detail": ""}


def pin_out(doc):
    return {"exit": 0, "output": json.dumps(doc)}


def row(tid, how="agent", target="math-writer", kind="write", to="author@t", refs=()):
    return {"id": tid, "kind": kind, "status": "open", "from": "author@t", "to": to,
            "final_to": "", "refs": list(refs), "budget_runs": 1,
            "route": {"how": how, "target": target, "why": "because"}, "return": False,
            "released": False, "over_budget": None}


def listing(rows, name="author@t"):
    return {"instances": [{"name": name, "role": name.split("@")[0], "home": "/h/" + name,
                           "waiting": len(rows), "rows": rows}]}


def run_wf(script, plan, args):
    d = tempfile.mkdtemp(prefix="acad-pin-")
    try:
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        a = dict({"models": {}, "snapshot": False}, **args)
        p = subprocess.run([NODE, h, script, json.dumps(dict(plan, __args=a))],
                           capture_output=True, text=True, timeout=60)
    finally:
        shutil.rmtree(d, True)
    if p.returncode:
        raise AssertionError(p.stderr)
    out = json.loads(p.stdout.strip().splitlines()[-1])
    return out.get("result"), [c["label"] for c in out["calls"]], out["calls"], out.get("error")


def prompt(calls, label):
    return next(c["prompt"] for c in calls if c["label"] == label)


class TheBlock(unittest.TestCase):
    def test_inbox_and_workplan_carry_the_same_block(self):
        blocks = []
        for f in (INBOX, WORKPLAN):
            with open(f, encoding="utf-8") as fh:
                m = BLOCK.search(fh.read())
            self.assertIsNotNone(m, f)
            blocks.append(m.group(0))
        self.assertEqual(blocks[0], blocks[1])

    def test_the_block_points_at_a_section_that_exists(self):
        with open(os.path.join(PLUGIN, "docs", "workflows.md"), encoding="utf-8") as fh:
            self.assertIn("\n## Pinned code\n", fh.read())


@unittest.skipUnless(NODE, "node is not installed")
class InboxPin(unittest.TestCase):
    def plan(self, **kw):
        p = {"pin": [pin_out(PINNED)], "list": [listing([row("T-1")])], "sweep author@t": ["0 notes"],
             "T-1 start": [OK], "math-writer T-1": ["done"], "check T-1": [DONE],
             "close author@t": [OK], "unpin": [ENDED]}
        p.update(kw)
        return p

    def test_the_run_pins_first_uses_the_pin_everywhere_and_ends_it(self):
        res, labels, calls, err = run_wf(INBOX, self.plan(), {"root": "/academy/"})
        self.assertIsNone(err, err)
        self.assertEqual("pin", labels[0])
        self.assertEqual("unpin", labels[-1])
        self.assertIn("`py /academy/academy/scripts/run_pin.py start --label inbox-all --json`", prompt(calls, "pin"))
        self.assertIn("(academy = %s)" % PIN, prompt(calls, "list"))
        self.assertIn("py %s/author/scripts/inbox.py --instance author@t --check T-1" % PIN, prompt(calls, "check T-1"))
        self.assertIn("py /academy/academy/scripts/run_pin.py end --run %s" % RUN, prompt(calls, "unpin"))
        self.assertEqual({"sha": SHA, "root": PIN, "pinned": True, "run": RUN, "ended": True},
                         {k: res["code"][k] for k in ("sha", "root", "pinned", "run", "ended")})

    def test_a_nested_workflow_gets_the_pinned_root_and_script_path(self):
        rows = [row("T-2", how="skill", target="expert:verify", kind="verify", to="expert@t",
                    refs=["paper:lem:x"])]
        plan = self.plan(**{"list": [listing(rows, "expert@t")],
                            "workflow verify.js": [{"outcome": "confirmed"}], "check T-2": [DONE]})
        del plan["sweep author@t"], plan["close author@t"]
        res, labels, calls, err = run_wf(INBOX, plan, {"root": "/academy"})
        self.assertIsNone(err, err)
        wf = next(c for c in calls if c["label"] == "workflow verify.js")
        self.assertEqual(PIN + "/expert/workflows/verify.js", wf["scriptPath"])
        self.assertEqual(PIN, wf["args"]["root"])

    def test_an_early_return_still_ends_the_pin(self):
        plan = {"pin": [pin_out(PINNED)], "list": [None], "unpin": [ENDED]}
        res, labels, _, err = run_wf(INBOX, plan, {"root": "/academy"})
        self.assertIsNone(err, err)
        self.assertEqual(["pin", "list", "unpin"], labels)
        self.assertTrue(res["code"]["ended"])

    def test_a_throw_still_ends_the_pin(self):
        plan = {"pin": [pin_out(PINNED)], "list": [{"__throw": "boom"}], "unpin": [ENDED]}
        res, labels, _, err = run_wf(INBOX, plan, {"root": "/academy"})
        self.assertIn("boom", err)
        self.assertEqual(["pin", "list", "unpin"], labels)

    def test_a_usage_limit_still_tries_the_unpin(self):
        # three launches in a row lost (#115): nothing else runs, the unpin (a record stage) still does
        rows = [row("T-1", how="reject", target=None, kind="prove"), row("T-2", how="reject", target=None, kind="prove")]
        plan = {"pin": [pin_out(PINNED)], "list": [listing(rows)], "sweep author@t": ["0 notes"],
                "T-1 reject": [None], "check T-1": [None], "T-2 reject": [None], "unpin": [ENDED]}
        res, labels, _, err = run_wf(INBOX, plan, {"root": "/academy"})
        self.assertIsNone(err, err)
        self.assertTrue(res["usage_limit"])
        self.assertEqual(["T-2 reject", "unpin"], labels[-2:])
        self.assertTrue(res["code"]["ended"])

    def test_a_throwing_unpin_keeps_the_runs_result(self):
        # review of 09ba2f2, 3: agent() throws on budget exhaustion or abort
        res, labels, _, err = run_wf(INBOX, self.plan(unpin=[{"__throw": "budget exhausted"}]), {"root": "/academy"})
        self.assertIsNone(err, err)
        self.assertEqual("unpin", labels[-1])
        self.assertEqual("worked", res["taken"][0]["outcome"])
        self.assertFalse(res["code"]["ended"])
        self.assertIn("budget exhausted", res["code"]["end_error"])

    def test_a_run_that_hands_back_holds_its_pin_and_says_until_when(self):
        # review of 09ba2f2, 5: a for_main's args carry the pin's root
        rows = [row("T-3", how="none", target=None, kind="other")]
        ended = {"exit": 0, "output": json.dumps({"ended": True, "run": RUN, "held": True, "expires": 1.0,
                                                  "expires_iso": "2026-11-28T10:00:00Z"})}
        plan = {"pin": [pin_out(PINNED)], "list": [listing(rows)], "sweep author@t": ["0 notes"], "unpin": [ended]}
        res, labels, calls, err = run_wf(INBOX, plan, {"root": "/academy"})
        self.assertIsNone(err, err)
        self.assertTrue(res["for_main"])
        self.assertIn("end --run %s --hold --json" % RUN, prompt(calls, "unpin"))
        self.assertEqual("2026-11-28T10:00:00Z", res["code"]["expires"])
        # no hand-back: no hold
        _, _, calls, err = run_wf(INBOX, self.plan(), {"root": "/academy"})
        self.assertIsNone(err, err)
        self.assertNotIn("--hold", prompt(calls, "unpin"))

    def test_a_pin_stage_with_no_pin_is_a_note_and_the_run_goes_on_live(self):
        for answer, why in ((None, "returned nothing"), ({"exit": 1, "output": "Traceback: boom"}, "printed no pin"),
                            (pin_out(dict(PINNED, sha="nothex")), "printed no pin")):
            plan = self.plan(pin=[answer])
            del plan["unpin"]
            res, labels, calls, err = run_wf(INBOX, plan, {"root": "/academy"})
            self.assertIsNone(err, err)
            self.assertNotIn("unpin", labels)
            self.assertIn("(academy = /academy)", prompt(calls, "list"))
            self.assertFalse(res["code"]["pinned"])
            self.assertIn(why, res["code"]["why"])
            self.assertTrue(any("not pinned" in n for n in res["notes"]), res["notes"])

    def test_a_checkout_that_is_no_git_repo_runs_as_it_is(self):
        no = {"pinned": False, "root": "/cache/academy", "sha": None, "run": None,
              "why": "/cache/academy is no git checkout"}
        plan = self.plan(pin=[pin_out(no)])
        del plan["unpin"]
        res, labels, calls, err = run_wf(INBOX, plan, {"root": "/cache/academy"})
        self.assertIsNone(err, err)
        self.assertNotIn("unpin", labels)
        self.assertEqual("/cache/academy", res["code"]["root"])
        self.assertIn("no git checkout", res["code"]["why"])

    def test_a_pin_the_caller_gives_is_used_and_not_ended(self):
        plan = self.plan()
        del plan["pin"], plan["unpin"]
        for code in (PINNED, json.dumps(PINNED)):
            res, labels, calls, err = run_wf(INBOX, plan, {"root": "/academy", "code": code})
            self.assertIsNone(err, err)
            self.assertNotIn("pin", labels)
            self.assertNotIn("unpin", labels)
            self.assertIn("(academy = %s)" % PIN, prompt(calls, "list"))
            self.assertEqual(SHA, res["code"]["sha"])

    def test_a_malformed_given_pin_is_refused_before_anything_runs(self):
        res, labels, _, err = run_wf(INBOX, {}, {"root": "/academy", "code": [1]})
        self.assertIn("args.code", err)
        self.assertEqual([], labels)

    def test_a_nested_run_and_pin_false_never_pin(self):
        plan = self.plan()
        del plan["pin"], plan["unpin"]
        for extra, why in (({"nested": True}, "nested"), ({"pin": False}, "pin false")):
            res, labels, _, err = run_wf(INBOX, plan, dict({"root": "/academy"}, **extra))
            self.assertIsNone(err, err)
            self.assertNotIn("pin", labels)
            self.assertEqual("/academy", res["code"]["root"])
            self.assertIn(why, res["code"]["why"])

    def test_uncommitted_changes_left_out_of_the_pin_are_noted(self):
        plan = self.plan(pin=[pin_out(dict(PINNED, dirty=2, why="pinned at x; 2 uncommitted change(s)"))])
        res, _, _, err = run_wf(INBOX, plan, {"root": "/academy"})
        self.assertIsNone(err, err)
        self.assertTrue(any("2 uncommitted" in n for n in res["notes"]), res["notes"])


@unittest.skipUnless(NODE, "node is not installed")
class WorkplanPin(unittest.TestCase):
    def test_a_cowork_pass_pins_and_hands_the_pin_to_its_inbox(self):
        state = {"state": "ACTIVE", "decision": [], "out": [], "own": ["T-1"], "receivers": ["author@t"]}
        plan = {"pin": [pin_out(dict(PINNED, run="workplan-x"))], "state before": [state],
                "workflow inbox.js": [{"taken": [], "notes": [], "count": 0}],
                "state after": [dict(state, state="WAITING")],
                "unpin": [{"exit": 0, "output": json.dumps({"ended": True, "run": "workplan-x"})}]}
        res, labels, calls, err = run_wf(WORKPLAN, plan, {"kind": "cowork", "root": "/academy", "slug": "s"})
        self.assertIsNone(err, err)
        self.assertEqual("pin", labels[0])
        self.assertEqual("unpin", labels[-1])
        self.assertIn("--label workplan-cowork-s", prompt(calls, "pin"))
        self.assertIn("py %s/academy/scripts/cowork.py" % PIN, prompt(calls, "state before"))
        inbox = next(c for c in calls if c["label"] == "workflow inbox.js")
        self.assertEqual(PIN + "/academy/workflows/inbox.js", inbox["scriptPath"])
        self.assertEqual(PIN, inbox["args"]["root"])
        self.assertEqual(SHA, inbox["args"]["code"]["sha"])
        self.assertEqual(SHA, res["code"]["sha"])
        self.assertTrue(res["code"]["ended"])


if __name__ == "__main__":
    unittest.main()
