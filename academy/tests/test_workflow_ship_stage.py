"""The ship stage of the workflows (docs/workflows.md, "Shipping is a step of the workflow").

The workflow runtime cannot import across files, so every workflow that ships carries the
same block (``const SHIP`` and ``async function ship``). This pins that the block is
identical in each, and reads ``inbox.py --check``'s output the way the inbox does: the
ticket's state from its first line, the repos from ship.py's lines, a refusal returned (never
retried), nothing run for an unfinished ticket or under ``"shipCheckpoint": false``, and the
command for the session when no ticket exists. The per-workflow runs (standalone ships once,
nested never) are in each plugin's workflow tests.
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
SHIPPING = ["expert/workflows/cite.js", "expert/workflows/verify.js", "expert/workflows/referee.js",
            "expert/workflows/domain.js", "researcher/workflows/prove.js", "researcher/workflows/explore.js",
            "researcher/workflows/generalize.js", "researcher/workflows/review-experiment.js",
            "scientist/workflows/experiment.js"]
NOT_RUN = ["expert/workflows/litwatch.js", "author/workflows/notes.js", "academy/workflows/weekly.js",
           "academy/workflows/workplan.js"]
BLOCK = re.compile(r"^// ---- Ship \(docs/workflows\.md.*?^  return res\n}\n", re.M | re.S)

HARNESS = r"""
const block = require('fs').readFileSync(process.argv[2], 'utf8')
const plan = JSON.parse(process.argv[3])
const calls = []
async function agent(prompt, opts) {
  calls.push({ label: opts.label, agentType: opts.agentType, prompt })
  const q = plan.answers
  if (!q.length) throw new Error('unplanned agent ' + opts.label)
  return q.shift()
}
const body = new Function('agent', 'AR', 'ROOT', 's', block + '\nreturn ship(s)')
body(agent, '/acad', '/acad', plan.s).then(r => console.log(JSON.stringify({ result: r, calls, notes: plan.s.notes })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""


def block_of(rel):
    m = BLOCK.search((REPO / rel).read_text(encoding="utf-8"))
    return m.group(0) if m else None


class SameBlockEverywhere(unittest.TestCase):
    def test_every_shipping_workflow_carries_the_same_block(self):
        blocks = {rel: block_of(rel) for rel in SHIPPING}
        self.assertEqual([r for r, b in blocks.items() if not b], [])
        self.assertEqual(len(set(blocks.values())), 1, "the ship block differs between workflows")

    def test_ticket_free_workflows_name_the_command_and_never_ship_themselves(self):
        for rel in NOT_RUN:
            text = (REPO / rel).read_text(encoding="utf-8")
            self.assertIn("status: 'not-run'", text, rel)
            self.assertIn("py scripts/ship.py checkpoint --ticket ", text, rel)
            self.assertNotIn("inbox.py --check", text.replace("// ", ""), rel)

    def test_the_inbox_calls_every_child_nested(self):
        text = (REPO / "academy/workflows/inbox.js").read_text(encoding="utf-8")
        calls = re.findall(r"await workflow\(\{ scriptPath: NESTED\[[^\]]+\] \}, (?:Object\.assign\()?\{([^}]*)", text)
        self.assertTrue(calls)
        self.assertEqual([c for c in calls if "nested: true" not in c], [])


T = "T-0904"
FIRST = T + ": delivered (delivered)\n"


@unittest.skipUnless(NODE, "node is not installed")
class ReadTheCheck(unittest.TestCase):
    def ship(self, s, answers=()):
        d = tempfile.mkdtemp(prefix="acad-ship-")
        self.addCleanup(shutil.rmtree, d, True)
        h, b = os.path.join(d, "h.js"), os.path.join(d, "b.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        with open(b, "w", encoding="utf-8") as fh:
            fh.write(block_of(SHIPPING[0]))
        s = dict({"role": "expert", "ticket": T, "done": True, "topic": "cite-SW10", "only": "library board",
                  "agentType": "academy:inbox-clerk", "phase": "Land", "notes": []}, **s)
        p = subprocess.run([NODE, h, b, json.dumps({"s": s, "answers": list(answers)})],
                           capture_output=True, text=True, timeout=60)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        self.assertNotIn("error", out, out.get("error"))
        self.notes = out["notes"]
        return out["result"], out["calls"]

    def out(self, text, status="pushed"):
        return {"status": status, "detail": "", "branches": [], "output": text}

    def test_a_finished_ticket_runs_the_inbox_check_once_and_reads_the_branches(self):
        text = FIRST + ("library 2026-11-13/t-0904/expert @ abc1234 (2 files) pushed\n    cards/SW10.md\n"
                        "board 2026-11-13/t-0904/expert @ def5678 (1 files) unchanged\n")
        res, calls = self.ship({"instance": "expert@t"}, [self.out(text, "nothing")])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["agentType"], "academy:inbox-clerk")
        self.assertIn("`py /acad/expert/scripts/inbox.py --instance expert@t --check T-0904 2>&1`", calls[0]["prompt"])
        self.assertIn("Never run it again", calls[0]["prompt"])
        self.assertEqual(res["status"], "pushed")                   # read from the output, not the clerk's word
        self.assertEqual(res["branches"], ["library 2026-11-13/t-0904/expert"])
        self.assertNotIn("command", res)

    def test_unchanged_everywhere_is_nothing(self):
        res, _ = self.ship({}, [self.out(FIRST + "library 2026-11-13/t-0904/expert @ abc (0 files) unchanged\n")])
        self.assertEqual(res["status"], "nothing")

    def test_a_refusal_is_returned_with_the_command_and_a_note_never_retried(self):
        text = FIRST + ("library main @ abc (0 files) REFUSED: dirty on main; start a branch first\n"
                        "warning: checkpoint for T-0904 exited 1 (see its output).\n")
        res, calls = self.ship({}, [self.out(text)])
        self.assertEqual(len(calls), 1)
        self.assertEqual(res["status"], "refused")
        self.assertIn("REFUSED: dirty on main", res["detail"])
        self.assertIn("--check T-0904", res["command"])
        self.assertEqual(len(self.notes), 1)                      # one sentence in the caller's notes
        self.assertIn("refused", self.notes[0])

    def test_push_gate_and_timeout_are_refusals(self):
        for line in ("board 2026-11-13/t-0904/expert @ abc (1 files) PUSH FAILED: gate: tests failed",
                     "warning: ship.py checkpoint for T-0904 timed out after 90s; run it by hand: ..."):
            res, _ = self.ship({}, [self.out(FIRST + line + "\n")])
            self.assertEqual(res["status"], "refused", line)

    def test_ship_checkpoint_false_runs_nothing_and_says_so(self):
        # inbox.py --check prints only its own line when workspace.json says "shipCheckpoint": false
        res, _ = self.ship({}, [self.out(FIRST, "pushed")])
        self.assertEqual(res["status"], "not-run")
        self.assertIn('"shipCheckpoint": false', res["detail"])

    def test_a_session_outside_the_workspace_is_not_run(self):
        res, _ = self.ship({}, [self.out(FIRST + "checkpoint not run: session is outside /ws; run it by hand: py scripts/ship.py ...\n")])
        self.assertEqual(res["status"], "not-run")
        self.assertIn("session is outside", res["detail"])

    def test_an_unfinished_ticket_is_not_run(self):
        res, _ = self.ship({}, [self.out(T + ": unfinished (in-progress)\n")])
        self.assertEqual(res["status"], "not-run")
        self.assertIn("unfinished", res["detail"])

    def test_known_unfinished_launches_nothing(self):
        res, calls = self.ship({"done": False})
        self.assertEqual(calls, [])
        self.assertEqual(res["status"], "not-run")
        self.assertIn("--check T-0904", res["command"])

    def test_no_ticket_launches_nothing_and_names_a_template_branch_command(self):
        res, calls = self.ship({"ticket": "", "topic": "cite-Masur Tabachnikov:2002"})
        self.assertEqual(calls, [])
        self.assertEqual(res["command"],
                         "py scripts/ship.py checkpoint --ticket cite-masur-tabachnikov-2002 --role expert --only library board")

    def test_a_lost_stage_is_not_run(self):
        res, _ = self.ship({}, [None])
        self.assertEqual(res["status"], "not-run")


if __name__ == "__main__":
    unittest.main()
