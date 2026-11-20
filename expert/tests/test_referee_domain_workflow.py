"""The referee and domain workflows (workflows/referee.js, domain.js), 2026-10-31. Under node
with a fake agent(); skipped without node. The guard refuses a hand-launched referee."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
WF = os.path.join(PLUGIN, "workflows")
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
import review_launch_guard as guard  # noqa: E402

NODE = shutil.which("node")

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


def run(name, plan, args):
    d = tempfile.mkdtemp(prefix="acad-rd-")
    try:
        h = os.path.join(d, "h.js")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        p = subprocess.run([NODE, h, os.path.join(WF, name), json.dumps(dict(plan, __args=args))],
                           capture_output=True, text=True, timeout=60)
    finally:
        shutil.rmtree(d, True)
    out = json.loads(p.stdout.strip().splitlines()[-1])
    return out.get("result"), [c["label"] for c in out["calls"]], out["calls"], out.get("error")


MOVE = {"ok": True, "status": "delivered", "detail": ""}
PDF = {"ok": True, "stop_reason": "", "pdf": "/w/BI/.build/main.pdf", "built": "2026-10-31", "rebuilt": True,
       "vision": "/w/BI/Drafts/vision.md", "last_report": "reviews/referee/author@t/2026-10-01.md",
       "last_date": "2026-10-01", "changed_since": "sections/markings.tex, sections/billiards.tex"}


@unittest.skipUnless(NODE, "node is not installed")
class RefereeTests(unittest.TestCase):
    def test_the_brief_is_facts_only_and_the_packet_is_found(self):
        res, labels, calls, err = run("referee.js", {
            "start": [{"ok": True, "detail": "", "instance": "author@t", "acted_as": "expert@t"}],
            "pdf": [PDF], "referee": ["report ... REFEREE block"],
            "find packet": [{"packet": "P-0500", "blocking": 2, "copy": "reviews/referee/author@t/2026-10-31.md"}],
            "deliver": [MOVE]}, {"ticket": "T-0700"})
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["start", "pdf", "referee", "find packet", "deliver"])
        brief = next(c for c in calls if c["label"] == "referee")
        self.assertEqual(brief["agentType"], "expert:referee")
        self.assertEqual(brief["prompt"],
                         "Referee author@t cold. The PDF is /w/BI/.build/main.pdf, built 2026-10-31. The last report is "
                         "2026-10-01; changed since: sections/markings.tex, sections/billiards.tex. Do not read the agenda or "
                         "tickets before your cold reading. After it, check the paper against its vision, "
                         "/w/BI/Drafts/vision.md. Ticket: T-0700.")
        self.assertIn("referee packet P-0500; 2 blocking", next(c for c in calls if c["label"] == "deliver")["prompt"])
        self.assertIn("rebuilt", " ".join(res["notes"]))

    def test_a_held_build_lock_stops_before_the_referee(self):
        res, labels, _, err = run("referee.js", {"pdf": [dict(PDF, ok=False, stop_reason="LaTeX Workshop is building")]},
                                  {"instance": "author@t"})
        self.assertEqual(labels, ["pdf"])
        self.assertIn("LaTeX Workshop", res["reason"])

    def test_focus_only_when_given_and_unlanded_reported(self):
        res, labels, calls, err = run("referee.js", {"pdf": [dict(PDF, last_report="none: reviews/referee/author@t/ does not exist", vision="")], "referee": ["r"],
                                                     "find packet": [{"packet": "", "blocking": 0, "copy": ""}]},
                                      {"instance": "author@t", "focus": "section 4"})
        p = next(c for c in calls if c["label"] == "referee")["prompt"]
        self.assertIn("look hardest at: section 4", p)
        self.assertIn("There is no earlier report", p)
        self.assertIn("vision, there is none", p)
        self.assertEqual(res["outcome"], "unlanded")

    def test_clerk_stages_without_detail_or_stop_reason_lose_nothing(self):
        """#124 follow-up 2: START, PDF and MOVE ask for their free text and do not require it."""
        pdf = {k: v for k, v in PDF.items() if k != "stop_reason"}
        res, labels, calls, err = run("referee.js", {
            "start": [{"ok": True, "instance": "author@t", "acted_as": "expert@t"}], "pdf": [pdf], "referee": ["r"],
            "find packet": [{"packet": "P-0500", "blocking": 0, "copy": "c"}],
            "deliver": [{"ok": True, "status": "delivered"}]}, {"ticket": "T-0700"})
        self.assertIsNone(err, err)
        for label, field in (("start", "detail"), ("pdf", "stop_reason"), ("deliver", "detail")):
            schema = next(c for c in calls if c["label"] == label)["schema"]
            self.assertIn(field, schema["properties"], label)
            self.assertNotIn(field, schema["required"], label)
        self.assertTrue(res["ticket_delivered"])
        res, _, _, err = run("referee.js", {"start": [{"ok": False, "instance": "", "acted_as": ""}]}, {"ticket": "T-0700"})
        self.assertEqual(res["reason"], "no reason given")
        res, _, _, err = run("referee.js", {"pdf": [dict(pdf, ok=False)]}, {"instance": "author@t"})
        self.assertEqual(res["reason"], "no reason given")


@unittest.skipUnless(NODE, "node is not installed")
class RefereeMaxTierTests(unittest.TestCase):
    """T-1682: the referee launches on the workspace's max tier; a lost run falls back to opus once."""
    BASE = {"start": [{"ok": True, "detail": "", "instance": "author@t", "acted_as": "expert@t"}], "pdf": [PDF],
            "find packet": [{"packet": "P-0500", "blocking": 2, "copy": "c"}], "deliver": [MOVE]}

    def test_the_model_from_the_args_or_one_clerk_stage(self):
        res, labels, calls, err = run("referee.js", dict(self.BASE, referee=["r"]), {"ticket": "T-0700"})
        self.assertIsNone(err, err)
        self.assertEqual(next(c for c in calls if c["label"] == "referee")["model"], "fable")
        res, labels, calls, err = run("referee.js", dict(self.BASE, referee=["r"], **{"model expert:referee": [{"output": "opus"}]}),
                                      {"ticket": "T-0700", "models": None})
        self.assertIsNone(err, err)
        self.assertEqual(labels, ["start", "pdf", "model expert:referee", "referee", "find packet", "deliver"])
        self.assertEqual(next(c for c in calls if c["label"] == "referee")["model"], "opus")

    def test_a_lost_run_falls_back_and_the_ticket_says_so(self):
        res, labels, calls, err = run("referee.js", dict(self.BASE, referee=[None], **{"referee (opus fallback)": ["r"]}),
                                      {"ticket": "T-0700"})
        self.assertIsNone(err, err)
        self.assertEqual(res["outcome"], "refereed")
        self.assertIn("model fallback: referee: fable -> opus", next(c for c in calls if c["label"] == "deliver")["prompt"])


START = {"ok": True, "detail": "", "pack": "translation-surfaces", "changes": ["add the Veech dichotomy entry"],
         "acted_as": "expert@t", "academy_root": "/a", "diff_before": []}
EDIT = {"files": ["theorems/dynamics.md"], "changelog": "- 2026-10-31 T-0800: theorems/dynamics.md Veech dichotomy",
        "card": "cards/V89/thm-1.md", "unverified": False, "shared": False, "clash": "",
        "already_present": False, "where": ""}


@unittest.skipUnless(NODE, "node is not installed")
class DomainTests(unittest.TestCase):
    def test_a_clean_change_is_delivered(self):
        res, labels, calls, err = run("domain.js", {
            "start": [START], "librarian": [EDIT],
            "diff": [{"changed": ["theorems/dynamics.md", "CHANGELOG.md"], "changelog_last": EDIT["changelog"]}],
            "close": [MOVE]}, {"ticket": "T-0800"})
        self.assertIsNone(err, err)
        self.assertEqual(res["anomalies"], [])
        self.assertIn("deliver: deliver: true", next(c for c in calls if c["label"] == "close")["prompt"])
        self.assertNotIn("packet", labels)

    def test_clerk_stages_without_detail_lose_nothing(self):
        """#124 follow-up 2: START and MOVE ask for detail and do not require it."""
        start = {k: v for k, v in START.items() if k != "detail"}
        res, labels, calls, err = run("domain.js", {
            "start": [start], "librarian": [EDIT],
            "diff": [{"changed": ["theorems/dynamics.md", "CHANGELOG.md"], "changelog_last": EDIT["changelog"]}],
            "close": [{"ok": True, "status": "delivered"}]}, {"ticket": "T-0800"})
        self.assertIsNone(err, err)
        for label in ("start", "close"):
            schema = next(c for c in calls if c["label"] == label)["schema"]
            self.assertIn("detail", schema["properties"], label)
            self.assertNotIn("detail", schema["required"], label)
        self.assertEqual(res["outcome"], "edited")
        res, _, _, err = run("domain.js", {"start": [dict(start, ok=False)]}, {"ticket": "T-0800"})
        self.assertEqual((res["outcome"], res["reason"]), ("not-started", "no reason given"))

    def test_a_change_already_present_is_delivered_as_such(self):
        """#118 (T-0997): a re-run whose row was already present must not log a second line
        and block; nothing changed is delivered as 'already present'."""
        same = dict(EDIT, files=[], changelog="", card="", already_present=True,
                    where="notation.md row 'saddle connection'")
        res, labels, calls, err = run("domain.js", {
            "start": [START], "librarian": [same],
            "diff": [{"changed": [], "changelog_last": "- 2026-10-31 T-0800: notation.md row",
                      "logged_before": ["- 2026-10-31 T-0800: notation.md row"]}],
            "close": [MOVE]}, {"ticket": "T-0800"})
        self.assertIsNone(err, err)
        self.assertEqual((res["outcome"], res["anomalies"]), ("already-present", []))
        close = next(c for c in calls if c["label"] == "close")["prompt"]
        self.assertIn("deliver: deliver: true", close)
        self.assertIn("already present", close)
        self.assertIn("edit nothing and append no line", next(c for c in calls if c["label"] == "librarian")["prompt"])
        # reported present, but a line was appended anyway: the check catches it
        res, labels, calls, err = run("domain.js", {
            "start": [START], "librarian": [same],
            "diff": [{"changed": ["CHANGELOG.md"], "changelog_last": "- 2026-10-31 T-0800: again",
                      "logged_before": ["- 2026-10-31 T-0800: notation.md row"]}],
            "close": [MOVE]}, {"ticket": "T-0800"})
        self.assertEqual(res["outcome"], "blocked-on-check")
        self.assertIn("CHANGELOG.md", " ".join(res["anomalies"]))
        # never logged, or no place named: not taken on the librarian's word
        for lib, logged in ((dict(same, where=""), ["x T-0800"]), (same, [])):
            res, labels, calls, err = run("domain.js", {
                "start": [START], "librarian": [dict(lib, shared=True)],
                "diff": [{"changed": [], "changelog_last": "x", "logged_before": logged}],
                "close": [MOVE]}, {"ticket": "T-0800"})
            self.assertEqual(res["outcome"], "blocked-on-check")
            self.assertNotIn("packet", labels)

    def test_an_extra_file_parks_the_ticket_on_the_human(self):
        res, labels, calls, err = run("domain.js", {
            "start": [START], "librarian": [EDIT],
            "diff": [{"changed": ["theorems/dynamics.md", "notation.md", "CHANGELOG.md"], "changelog_last": EDIT["changelog"]}],
            "close": [MOVE]}, {"ticket": "T-0800"})
        self.assertIn("notation.md", " ".join(res["anomalies"]))
        self.assertIn("block-human", next(c for c in calls if c["label"] == "close")["prompt"])

    def test_two_changes_are_split_and_a_shared_change_gets_a_packet(self):
        res, labels, calls, err = run("domain.js", {
            "start": [dict(START, changes=["a", "b"], diff_before=["domains/translation-surfaces/examples.md"])],
            "split note": [MOVE], "librarian": [dict(EDIT, shared=True, clash="the paper writes Λ for the lattice")],
            "diff": [{"changed": ["examples.md", "theorems/dynamics.md", "CHANGELOG.md"], "changelog_last": EDIT["changelog"]}],
            "packet": [{"packet": "P-0600", "error": ""}], "close": [MOVE]}, {"ticket": "T-0800"})
        self.assertIsNone(err, err)
        self.assertIn("split note", labels)
        self.assertEqual(res["anomalies"], [])                    # examples.md was dirty before the run
        self.assertIn("clash", next(c for c in calls if c["label"] == "packet")["prompt"])
        self.assertEqual(res["packet"], "P-0600")

    def test_no_ticket_is_refused(self):
        res, labels, _, err = run("domain.js", {}, {})
        self.assertIn("args.ticket is required", err)


def shipped(t, line):
    return {"status": "nothing", "detail": "", "branches": [], "output": "%s: delivered (delivered)\n%s\n" % (t, line)}


@unittest.skipUnless(NODE, "node is not installed")
class ShipTests(unittest.TestCase):
    """docs/workflows.md, "Shipping is a step of the workflow": standalone ships once; nested never."""
    REF = {"start": [{"ok": True, "detail": "", "instance": "author@t", "acted_as": "expert@t"}], "pdf": [PDF], "referee": ["r"],
           "find packet": [{"packet": "P-0500", "blocking": 2, "copy": "c.md"}], "deliver": [MOVE]}
    DOM = {"start": [START], "librarian": [EDIT], "close": [MOVE],
           "diff": [{"changed": ["theorems/dynamics.md", "CHANGELOG.md"], "changelog_last": EDIT["changelog"]}]}

    def test_referee_standalone_ships_once_and_nested_never(self):
        res, labels, calls, err = run("referee.js", dict(self.REF, ship=[shipped("T-0700", "board 2026-11-13/t-0700/expert @ a (1 files) pushed")]),
                                      {"ticket": "T-0700", "nested": False, "root": "/acad"})
        self.assertIsNone(err, err)
        self.assertEqual(labels[-1], "ship")
        self.assertIn("py /acad/expert/scripts/inbox.py --instance expert@t --check T-0700", calls[-1]["prompt"])
        self.assertEqual(res["ship"]["branches"], ["board 2026-11-13/t-0700/expert"])
        res, labels, _, err = run("referee.js", dict(self.REF), {"ticket": "T-0700", "nested": True})
        self.assertIsNone(err, err)
        self.assertNotIn("ship", labels)

    def test_referee_without_a_ticket_is_not_run(self):
        res, labels, _, err = run("referee.js", {"pdf": [PDF], "referee": ["r"], "find packet": [{"packet": "P-0500", "blocking": 0, "copy": "c"}]},
                                  {"instance": "author@t", "nested": False})
        self.assertNotIn("ship", labels)
        self.assertEqual(res["ship"]["command"], "py scripts/ship.py checkpoint --ticket referee-author-t --role expert --only library board")

    def test_domain_standalone_ships_once_refusal_returned(self):
        res, labels, _, err = run("domain.js", dict(self.DOM, ship=[shipped("T-0800", "library x @ a (0 files) REFUSED: off-template branch")] * 2),
                                  {"ticket": "T-0800", "nested": False})
        self.assertIsNone(err, err)
        self.assertEqual(labels.count("ship"), 1)
        self.assertEqual(res["ship"]["status"], "refused")
        self.assertIn("ship stage was refused", " ".join(res["notes"]))

    def test_domain_parked_on_the_human_does_not_ship(self):
        dom = dict(self.DOM, diff=[{"changed": ["notation.md", "CHANGELOG.md"], "changelog_last": EDIT["changelog"]}],
                   close=[dict(MOVE, status="blocked")])
        res, labels, _, err = run("domain.js", dom, {"ticket": "T-0800", "nested": False})
        self.assertNotIn("ship", labels)
        self.assertEqual(res["ship"]["status"], "not-run")


class RefereeGuardTests(unittest.TestCase):
    def test_a_hand_launched_referee_is_denied(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ACADEMY_ALLOW_MANUAL_REVIEW", None)
            os.environ.pop("EVAL_ACADEMY_ALLOW_LAUNCH", None)
            out = guard.decide({"tool_name": "Agent", "tool_input": {"subagent_type": "expert:referee"}})
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("workflows/referee.js", out["hookSpecificOutput"]["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
