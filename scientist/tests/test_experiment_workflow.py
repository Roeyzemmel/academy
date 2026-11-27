"""The experiment workflow (workflows/experiment.js), 2026-10-31: the human gates are
unskippable (design stops at the header, build at the commit, queue refuses an uncommitted
script, report stops at the rendered packet). Under node with a fake agent()."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "workflows", "experiment.js")
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
  return q.shift()
}
const body = new Function('args', 'agent', 'phase', 'log', 'return (async () => {' + src + '})()')
// the stage-order tests run nested, as from the inbox (no ship stage); the ship tests pass nested: false
// as the skills pass it (models.py launches prints {} under the default map); null: not given (#83)
body(Object.assign({ nested: true, models: {} }, plan.__args), agent, () => {}, () => {}).then(
  r => console.log(JSON.stringify({ result: r, calls })),
  e => console.log(JSON.stringify({ error: String(e), calls })))
"""

HOME = {"ok": True, "instance": "scientist@t", "home": "/h/lab", "run_profile": "remote", "detail": ""}
DESIGN = {"path": "experiment", "argument": "", "stem": "2026-10-31_x", "header": "Kind: search\nClaims: lab:x",
          "if_false": "a member violating the bound", "api_unfamiliar": []}
OK = {"ok": True, "errors": []}
BAD = {"ok": False, "errors": ["header: Claims: missing"]}


@unittest.skipUnless(NODE, "node is not installed")
class ExperimentTests(unittest.TestCase):
    def run_wf(self, plan, **args):
        d = tempfile.mkdtemp(prefix="acad-ex-")
        self.addCleanup(shutil.rmtree, d, True)
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, SCRIPT, json.dumps(dict(plan, __args=args))], capture_output=True, text=True, timeout=60)
        out = json.loads(p.stdout.strip().splitlines()[-1])
        return out.get("result"), [c["label"] for c in out["calls"]], out["calls"], out.get("error")

    def test_design_stops_at_the_header_gate(self):
        res, labels, calls, err = self.run_wf({"lab home": [HOME], "design": [DESIGN]}, mode="design", claim="lab:x", ticket="T-1")
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["lab home", "design"])
        self.assertTrue(res["for_main"]["gate"])
        self.assertIn("approve the header", res["for_main"]["why"])
        self.assertEqual(res["for_main"]["next"]["mode"], "build")
        self.assertIn("HEADER ONLY", next(c for c in calls if c["label"] == "design")["prompt"])

    def test_an_argument_instead_of_a_header_goes_to_the_human(self):
        """#88: the argument is the human's call (accept, prove instead, run anyway),
        never a leg left unfinished with the ticket in-progress."""
        res, labels, _, err = self.run_wf({"lab home": [HOME], "design": [dict(DESIGN, path="argument", argument="by parity")]}, mode="design", claim="c", ticket="T-1")
        self.assertIsNone(err, err)
        self.assertNotIn("build", labels)
        self.assertEqual(res["for_main"]["outcome"], "argument-instead")
        self.assertEqual(res["for_main"]["argument"], "by parity")
        self.assertIn("prove instead", res["for_main"]["options"])
        self.assertEqual(res["for_main"]["ticket"], "T-1")

    def test_a_design_without_a_header_is_retried_once_then_fails(self):
        bad = dict(DESIGN, header="The claim holds because ... (a hand argument)\ndef f(): pass")
        res, labels, calls, err = self.run_wf({"lab home": [HOME], "design": [bad], "design (retry)": [DESIGN]},
                                              mode="design", claim="c")
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["lab home", "design", "design (retry)"])
        retry = next(c for c in calls if c["label"] == "design (retry)")["prompt"]
        self.assertIn("no Kind: line", retry)
        self.assertIn("Read the statement from its owner", retry)      # the full brief again
        self.assertIn("a hand argument", retry)                        # and what came back
        self.assertIn("approve the header", res["for_main"]["why"])
        res, labels, _, err = self.run_wf({"lab home": [HOME], "design": [bad], "design (retry)": [bad]},
                                          mode="design", claim="c")
        self.assertEqual(res["for_main"]["outcome"], "no-header")     # asks someone (review of 641a695)
        self.assertTrue(res["for_main"]["gate"])
        probe = dict(DESIGN, path="probe", header="Kind: probe\nGoal: is it fast")
        res, labels, _, err = self.run_wf({"lab home": [HOME], "design": [probe], "design (retry)": [probe]},
                                          mode="design", claim="c")
        self.assertIn("Goal: and Decides:", res["reason"])

    def test_the_header_check_reads_prose_and_markup_as_a_header(self):
        """review of 641a695: 'class v = ...' in a wrapped sentence is prose; markup around
        Kind is allowed; a probe path needs Kind: probe; an empty argument is no argument."""
        good = [dict(DESIGN, header="Kind: verify\nGoal: for each M in the\n   class below, decide"),
                dict(DESIGN, header="**Kind:** search\nClaims: lab:x"),
                dict(DESIGN, header='"""Kind: measure\nClaims: lab:x')]
        for d in good:
            res, labels, _, err = self.run_wf({"lab home": [HOME], "design": [d]}, mode="design", claim="c")
            self.assertNotIn("design (retry)", labels, d["header"])
        bad = [dict(DESIGN, header="Kind:\nClaims: lab:x"),
               dict(DESIGN, header="Kind: search\nimport numpy as np"),
               dict(DESIGN, path="probe", header="Kind: search\nGoal: g\nDecides: d"),
               dict(DESIGN, path="experiment", header="Kind: probe\nGoal: g\nDecides: d"),
               dict(DESIGN, path="argument", argument="  ")]
        for d in bad:
            res, labels, _, err = self.run_wf({"lab home": [HOME], "design": [d], "design (retry)": [d]},
                                              mode="design", claim="c")
            self.assertEqual(res["for_main"]["outcome"], "no-header", d)

    def test_force_asks_for_the_experiment_and_never_offers_the_argument_again(self):
        res, labels, calls, err = self.run_wf({"lab home": [HOME], "design": [dict(DESIGN, path="argument", argument="by parity")],
                                               "design (retry)": [DESIGN]}, mode="design", claim="c", force=True)
        self.assertIn("do not answer with an argument", next(c for c in calls if c["label"] == "design")["prompt"])
        self.assertIn("approve the header", res["for_main"]["why"])
        res, _, _, _ = self.run_wf({"lab home": [HOME], "design": [dict(DESIGN, path="argument", argument="by parity")]},
                                   mode="design", claim="c", ticket="T-1")
        self.assertEqual(res["for_main"]["next"], {"mode": "design", "force": True, "claim": "c", "ticket": "T-1", "kind": None})

    def test_build_checks_with_one_fix_and_stops_for_the_commit(self):
        built = {"script": "experiments/2026-10-31_x.py", "lab_claim": "lab:x", "tests": [], "note": ""}
        res, labels, _, err = self.run_wf({"build": [built], "check": [BAD], "build (fix)": [built], "check again": [OK]},
                                          mode="build", header="Kind: search", stem="2026-10-31_x")
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["build", "check", "build (fix)", "check again"])
        self.assertIn("commit the experiment script", res["for_main"]["why"])
        res, labels, _, err = self.run_wf({"build": [built], "check": [BAD], "build (fix)": [built], "check again": [BAD]},
                                          mode="build", header="h", stem="s")
        self.assertEqual(res["outcome"], "check-failed")
        _r, _l, _c, err = self.run_wf({}, mode="build", stem="s")
        self.assertIn("approved text", err)

    def test_queue_refuses_an_uncommitted_script(self):
        res, labels, _, err = self.run_wf({"committed?": [{"committed": False, "commit": "", "dirty": ["experiments/s.py"]}]}, mode="queue", stem="s")
        self.assertIn("not committed", res["for_main"]["why"])
        self.assertNotIn("queue", labels)
        res, labels, _, err = self.run_wf({"committed?": [{"committed": True, "commit": "abc", "dirty": []}],
                                           "queue": [{"ok": True, "job": "j1", "command": "c", "detail": ""}]}, mode="queue", stem="s")
        self.assertEqual((res["outcome"], res["job"]), ("queued", "j1"))

    def test_report_stops_at_the_rendered_packet_and_file_delivers(self):
        dr = {"report": "reports/s.md", "result_line": "no counterexample below 9 over class C"}
        res, labels, _, err = self.run_wf({"report draft": [dr], "report check": [OK], "render": [{"ok": True, "rendered": "<packet>", "errors": []}]},
                                          mode="report", stem="s", job="j1")
        self.assertEqual(labels, ["report draft", "report check", "render"])
        self.assertEqual(res["for_main"]["rendered"], "<packet>")
        self.assertEqual(res["for_main"]["next"]["mode"], "file")
        res, labels, calls, err = self.run_wf({"file": [{"packet": "P-1", "review_ticket": "T-9", "researcher": "researcher@u", "why": "owns lab:", "error": ""}],
                                               "deliver": [{"ok": True, "detail": ""}]}, mode="file", stem="s", ticket="T-1")
        self.assertEqual(res["outcome"], "filed")
        self.assertIn("--ticket T-1", next(c for c in calls if c["label"] == "file")["prompt"])

    # ---- #124 follow-up: a clerk that leaves out 'detail' costs no run ------------------------
    # (review of 0881c94: the 23 'must have required property detail' rows of academy:inbox-clerk
    # are not only inbox.js's; this workflow's clerk stages HOME, QUEUED and MOVE required it too)

    def schema_of(self, calls, label):
        return next(c for c in calls if c["label"] == label)["schema"]

    def assert_detail_optional(self, schema, label, required):
        self.assertIn("detail", schema["properties"], label)          # still asked for
        self.assertNotIn("detail", schema["required"], label)
        self.assertEqual(set(schema["required"]), required, label)   # what the code reads stays required

    def test_the_home_schema_does_not_require_detail(self):
        _res, _labels, calls, err = self.run_wf({"lab home": [HOME], "design": [DESIGN]}, mode="design", claim="lab:x", ticket="T-1")
        self.assertIsNone(err, err)
        self.assert_detail_optional(self.schema_of(calls, "lab home"), "lab home", {"ok", "instance", "home", "run_profile"})

    def test_the_queued_schema_does_not_require_detail(self):
        _res, _labels, calls, err = self.run_wf({"committed?": [{"committed": True, "commit": "abc", "dirty": []}],
                                                 "queue": [{"ok": True, "job": "j1", "command": "c", "detail": ""}]}, mode="queue", stem="s")
        self.assertIsNone(err, err)
        self.assert_detail_optional(self.schema_of(calls, "queue"), "queue", {"ok", "job", "command"})

    def test_the_move_schema_does_not_require_detail(self):
        _res, _labels, calls, err = self.run_wf({"file": [{"packet": "P-1", "review_ticket": "T-9", "researcher": "researcher@u", "why": "w", "error": ""}],
                                                 "deliver": [{"ok": True, "detail": ""}]}, mode="file", stem="s", ticket="T-1")
        self.assertIsNone(err, err)
        self.assert_detail_optional(self.schema_of(calls, "deliver"), "deliver", {"ok"})

    def test_answers_without_detail_lose_nothing(self):
        home = {k: v for k, v in HOME.items() if k != "detail"}
        res, labels, _, err = self.run_wf({"lab home": [home], "design": [DESIGN]}, mode="design", claim="lab:x", ticket="T-1")
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["lab home", "design"])
        self.assertIn("approve the header", res["for_main"]["why"])
        res, labels, _, err = self.run_wf({"committed?": [{"committed": True, "commit": "abc", "dirty": []}],
                                           "queue": [{"ok": True, "job": "j1", "command": "c"}]}, mode="queue", stem="s")
        self.assertEqual((res["outcome"], res["job"]), ("queued", "j1"))
        res, labels, _, err = self.run_wf({"file": [{"packet": "P-1", "review_ticket": "T-9", "researcher": "researcher@u", "why": "w", "error": ""}],
                                           "deliver": [{"ok": True}]}, mode="file", stem="s", ticket="T-1")
        self.assertEqual(res["outcome"], "filed")
        self.assertTrue(res["ticket_delivered"])

    def test_the_filed_schema_does_not_require_why_or_error(self):
        """#124 follow-up 2: FILED asks for why and error and requires neither."""
        res, _labels, calls, err = self.run_wf({"file": [{"packet": "P-1", "review_ticket": "T-9", "researcher": "researcher@u"}],
                                                "deliver": [{"ok": True}]}, mode="file", stem="s", ticket="T-1")
        self.assertIsNone(err, err)
        schema = self.schema_of(calls, "file")
        for field in ("why", "error"):
            self.assertIn(field, schema["properties"])
            self.assertNotIn(field, schema["required"])
        self.assertEqual(set(schema["required"]), {"packet", "review_ticket", "researcher"})
        self.assertEqual((res["outcome"], res["why"]), ("filed", "no reason given"))
        res, _labels, _calls, err = self.run_wf({"file": [{"packet": "", "review_ticket": "", "researcher": ""}]},
                                                mode="file", stem="s", ticket="T-1")
        self.assertEqual((res["outcome"], res["reason"]), ("not-filed", "no reason given"))

    def test_a_refusal_without_detail_says_so_plainly(self):
        res, labels, _, err = self.run_wf({"lab home": [{"ok": False, "instance": "", "home": "", "run_profile": ""}]},
                                          mode="design", claim="lab:x")
        self.assertIsNone(err, err)
        self.assertEqual((res["outcome"], res["reason"]), ("not-started", "no reason given"))
        res, labels, _, err = self.run_wf({"committed?": [{"committed": True, "commit": "abc", "dirty": []}],
                                           "queue": [{"ok": False, "job": "", "command": "c"}]}, mode="queue", stem="s")
        self.assertEqual((res["outcome"], res["reason"]), ("not-queued", "no reason given"))
        # a detail given is still the reason
        res, _, _, _ = self.run_wf({"committed?": [{"committed": True, "commit": "abc", "dirty": []}],
                                    "queue": [{"ok": False, "job": "", "command": "c", "detail": "gateway down"}]}, mode="queue", stem="s")
        self.assertEqual(res["reason"], "gateway down")


@unittest.skipUnless(NODE, "node is not installed")
class ShipTests(unittest.TestCase):
    """docs/workflows.md, "Shipping is a step of the workflow": only the file leg ships (the others end at
    a human gate), standalone once, nested never."""
    run_wf = ExperimentTests.run_wf
    FILE = {"file": [{"packet": "P-1", "review_ticket": "T-9", "researcher": "researcher@u", "why": "w", "error": ""}],
            "deliver": [{"ok": True, "detail": ""}]}

    @staticmethod
    def out(line):
        return {"status": "nothing", "detail": "", "branches": [], "output": "T-1: delivered (delivered)\n%s\n" % line}

    def test_the_file_leg_ships_once_standalone(self):
        res, labels, calls, err = self.run_wf(dict(self.FILE, ship=[self.out("lab 2026-11-13/t-1/scientist @ a (3 files) pushed")]),
                                              mode="file", stem="s", ticket="T-1", root="/acad", nested=False)
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["file", "deliver", "ship"])
        self.assertIn("py /acad/scientist/scripts/inbox.py --check T-1", calls[-1]["prompt"])
        self.assertEqual(res["ship"]["branches"], ["lab 2026-11-13/t-1/scientist"])
        res, labels, _, err = self.run_wf(dict(self.FILE), mode="file", stem="s", ticket="T-1", nested=True)
        self.assertNotIn("ship", labels)

    def test_a_refusal_is_returned_once(self):
        bad = self.out("lab main @ a (0 files) REFUSED: dirty on main")
        res, labels, _, err = self.run_wf(dict(self.FILE, ship=[bad, bad]), mode="file", stem="s", ticket="T-1", nested=False)
        self.assertEqual(labels.count("ship"), 1)
        self.assertEqual(res["ship"]["status"], "refused")
        self.assertIn("ship stage was refused", " ".join(res["notes"]))

    def test_other_legs_never_ship_and_no_ticket_is_not_run(self):
        res, labels, _, err = self.run_wf({"lab home": [HOME], "design": [DESIGN]}, mode="design", claim="lab:x", ticket="T-1", nested=False)
        self.assertNotIn("ship", res)
        # #136 item 4: the file leg with no ticket ships its slug once (inbox.py --ship-slug)
        res, labels, _, err = self.run_wf({"file": self.FILE["file"], "ship": [{"status": "pushed", "output": "home 2026-11-27/report-2026-11-13-x/scientist @ abc1234 (1 files) pushed\nreport-2026-11-13-x: delivered (no ticket)\n"}]},
                                          mode="file", stem="2026-11-13_x", nested=False)
        self.assertEqual(labels.count("ship"), 1)
        self.assertEqual(res["ship"]["status"], "pushed")


if __name__ == "__main__":
    unittest.main()
