"""Tests for the interface-skill scripts: usage_report, deep_dive_index,
init_instance, academy_status (and the moved session_usage).

Run from the repo root:  py -m unittest discover academy/tests
Everything runs in a temp directory with a throw-away workspace (ACADEMY_WORKSPACE).
"""

import datetime as _dt
import glob
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
SCRIPTS = os.path.join(PLUGIN, "scripts")
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, SCRIPTS)

import academy_common as ac  # noqa: E402
import academy_status  # noqa: E402
import board as boardlib  # noqa: E402
import deep_dive_index as ddi  # noqa: E402
import init_instance  # noqa: E402
import session_usage  # noqa: E402
import usage_report  # noqa: E402


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


class Sandbox(unittest.TestCase):
    """A temp dir with a workspace, a board and two homes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-iface-")
        self.board = os.path.join(self.tmp, "board").replace("\\", "/")
        os.makedirs(self.board)
        self.home_a = os.path.join(self.tmp, "PaperHome").replace("\\", "/")
        self.home_e = os.path.join(self.tmp, "library").replace("\\", "/")
        os.makedirs(self.home_a)
        os.makedirs(self.home_e)
        self.ws_path = os.path.join(self.tmp, "workspace.json")
        ws = {"instances": {
            "author@p": {"role": "author", "home": self.home_a, "domains": ["dom"],
                         "ns": "paper"},
            "expert@d": {"role": "expert", "home": self.home_e, "domains": ["dom"]}},
            "board": self.board, "human": {"name": "Roey", "noteMacro": "\\Roey"}}
        write(self.ws_path, json.dumps(ws, indent=2) + "\n")
        self._saved = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = self.ws_path

    def tearDown(self):
        if self._saved is None:
            os.environ.pop("ACADEMY_WORKSPACE", None)
        else:
            os.environ["ACADEMY_WORKSPACE"] = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)


# ----------------------------------------------------------------------------

def _assistant(mid, model, read, write_, inp=0):
    return json.dumps({"type": "assistant", "message": {
        "id": mid, "model": model, "usage": {"cache_read_input_tokens": read,
                                             "cache_creation_input_tokens": write_,
                                             "input_tokens": inp}}})


def _limit():
    return json.dumps({"type": "assistant", "message": {
        "model": "<synthetic>", "content": [{"text": "You've hit your session limit"}]}})


class UsageReportTest(Sandbox):

    def make_projects(self):
        root = os.path.join(self.tmp, "projects")
        proj = usage_report.encode_home(self.home_a)
        base = os.path.join(root, proj)
        write(os.path.join(base, "s1.jsonl"), "\n".join([
            _assistant("m1", "claude-sonnet-5", 1000, 200),
            _assistant("m1", "claude-sonnet-5", 1000, 200),   # duplicate id: counted once
            _assistant("m2", "claude-sonnet-5", 3000, 0),
        ]) + "\n")
        sub = os.path.join(base, "s1", "subagents")
        write(os.path.join(sub, "a1.meta.json"),
              json.dumps({"agentType": "academy:concierge", "spawnDepth": 1,
                          "description": "route"}))
        write(os.path.join(sub, "a1.jsonl"),
              _assistant("x1", "claude-opus-5-5", 5000, 100) + "\n")
        write(os.path.join(sub, "a2.meta.json"),
              json.dumps({"agentType": "paper:math-writer", "spawnDepth": 1}))
        write(os.path.join(sub, "a2.jsonl"),
              _assistant("y1", "claude-opus-5-5", 2000, 0) + "\n" + _limit() + "\n")
        # an unrelated project, and an old session outside the window
        write(os.path.join(root, "C--elsewhere", "s2.jsonl"),
              _assistant("z1", "claude-haiku-4-5", 10, 0) + "\n")
        old = os.path.join(root, "C--elsewhere", "old.jsonl")
        write(old, _assistant("o1", "claude-haiku-4-5", 99999, 0) + "\n")
        t = time.time() - 30 * 86400
        os.utime(old, (t, t))
        return root

    def test_encode_and_instance(self):
        ws = ac.load_workspace(self.ws_path)
        enc = usage_report.encode_home("C:/Work/Math/SomePaper")
        self.assertEqual(enc, "C--Work-Math-SomePaper")
        self.assertEqual(usage_report.instance_of_project(
            usage_report.encode_home(self.home_a), ws), "author@p")
        self.assertEqual(usage_report.instance_of_project(
            usage_report.encode_home(self.home_a) + "-academy", ws), "author@p")
        self.assertEqual(usage_report.instance_of_project("C--elsewhere", ws), "other")

    def test_role_of_agent(self):
        roster = {"concierge": "academy", "clerk": "expert"}
        self.assertEqual(usage_report.role_of_agent("academy:concierge", roster), "academy")
        self.assertEqual(usage_report.role_of_agent("clerk", roster), "expert")
        self.assertEqual(usage_report.role_of_agent("paper:math-writer", roster), "legacy:paper")
        self.assertEqual(usage_report.role_of_agent("general-purpose", roster), "builtin")
        self.assertEqual(usage_report.model_family("claude-fable-5-1"), "fable")

    def test_report(self):
        root = self.make_projects()
        agents = os.path.join(self.tmp, "repo", "academy", "agents")
        write(os.path.join(agents, "concierge.md"),
              "---\nname: concierge\nmodel: sonnet\n---\nbody\n")
        report, _s, _e = usage_report.build(days=7, projects=root,
                                            workspace_path=self.ws_path,
                                            perms={"roster": {"academy": ["concierge"]}},
                                            repo=os.path.join(self.tmp, "repo"))
        self.assertEqual(report["sessions"], 2)
        self.assertEqual(report["subagents"], 2)
        inst = report["by_instance"]["author@p"]
        self.assertEqual(inst["read"], 1000 + 3000 + 5000 + 2000)
        self.assertEqual(inst["limit_failures"], 1)
        self.assertIn("other", report["by_instance"])
        self.assertEqual(report["by_role"]["academy"]["runs"], 1)
        self.assertEqual(report["by_role"]["legacy:paper"]["limit_failures"], 1)
        kinds = sorted(f["kind"] for f in report["flags"])
        self.assertEqual(kinds, ["heavier-than-declared", "limit"])
        md = usage_report.render_markdown(report, _s, _e)
        self.assertIn("| author@p |", md)
        self.assertIn("heavier-than-declared: academy:concierge declares sonnet", md)
        brief = usage_report.render_brief(report, "7d")
        self.assertTrue(brief.startswith("usage 7d: 2 sessions, 2 subagents"))

    def test_live_window_keeps_a_transcript_written_after_now(self):
        # Windows' coarse clock can stamp a file just written with an mtime after
        # datetime.now(); the live window must not drop it (review finding).
        root = self.make_projects()
        future = time.time() + 120
        for path in glob.glob(os.path.join(root, "*", "s*.jsonl")):
            os.utime(path, (future, future))
        report, _s, _e = usage_report.build(days=7, projects=root,
                                            workspace_path=self.ws_path,
                                            perms={"roster": {"academy": ["concierge"]}},
                                            repo=os.path.join(self.tmp, "repo"))
        self.assertEqual(report["sessions"], 2)

    def test_fan_out_flag(self):
        root = self.make_projects()
        report, _s, _e = usage_report.build(days=7, projects=root, max_subagents=1,
                                            workspace_path=self.ws_path, perms={"roster": {}},
                                            repo=self.tmp)
        self.assertIn("fan-out", [f["kind"] for f in report["flags"]])

    def test_session_usage_moved(self):
        self.assertTrue(os.path.isfile(os.path.join(SCRIPTS, "session_usage.py")))
        root = self.make_projects()
        t, m = session_usage.tally(os.path.join(root, usage_report.encode_home(self.home_a),
                                                "s1.jsonl"))
        self.assertEqual(t["turns"], 2)


# ----------------------------------------------------------------------------

class DeepDiveIndexTest(Sandbox):

    def test_subject_id(self):
        self.assertEqual(ddi.subject_id("paper:lem:strip-bound"), "paper-lem-strip-bound")
        self.assertEqual(ddi.subject_id("bib:LMW16#Thm1.3"), "bib-lmw16-thm1-3")
        self.assertEqual(ddi.subject_id("::"), "deep-dive")
        import render_packets
        for subj in ("paper:lem:strip-bound", "bib:LMW16#Thm1.3", "concept:" + "x" * 120,
                     "lab:ew-check", "results/run.json"):
            self.assertEqual(ddi.subject_id(subj), render_packets.deep_dive_slug(subj), subj)

    def test_set_get_update(self):
        self.assertIsNone(ddi.get_entry(self.board, "x"))
        e = ddi.set_entry(self.board, "paper-lem-a", "https://claude.ai/code/artifact/abc",
                          kind="claim", title="Lemma A", subject="paper:lem:a",
                          date="2026-09-27")
        self.assertEqual(e["created"], "2026-09-27")
        e2 = ddi.set_entry(self.board, "paper-lem-a", "https://claude.ai/code/artifact/abc",
                           date="2026-09-28")
        self.assertEqual(e2["created"], "2026-09-27")
        self.assertEqual(e2["updated"], "2026-09-28")
        self.assertEqual(e2["kind"], "claim")
        e3 = ddi.set_entry(self.board, "paper-lem-a", "https://claude.ai/code/artifact/def")
        self.assertEqual(e3["previous_urls"], ["https://claude.ai/code/artifact/abc"])
        with open(ddi.index_path(self.board), "rb") as fh:
            raw = fh.read()
        self.assertNotIn(b"\r\n", raw)

    def test_refusals(self):
        with self.assertRaises(ac.AcademyError):
            ddi.set_entry(self.board, "Bad Id", "https://claude.ai/x")
        with self.assertRaises(ac.AcademyError):
            ddi.set_entry(self.board, "ok", "http://example.com/x")

    def test_cli(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = ddi.main(["--board", self.board, "get", "none"])
        self.assertEqual(rc, 1)
        with redirect_stdout(io.StringIO()):
            ddi.main(["--board", self.board, "set", "review-dashboard",
                      "--url", "https://claude.ai/code/artifact/d", "--kind", "dashboard"])
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = ddi.main(["--board", self.board, "get", "review-dashboard"])
        self.assertEqual((rc, buf.getvalue().strip()), (0, "https://claude.ai/code/artifact/d"))


# ----------------------------------------------------------------------------

class InitInstanceTest(Sandbox):

    def test_templates_validate(self):
        ws = ac.load_workspace(self.ws_path)
        for role in ac.ROLES:
            cfg = init_instance.build_config("%s@new" % role, ["dom"], workspace=ws)
            self.assertEqual(ac.validate_config(cfg), [], role)
            text = json.dumps(cfg)
            self.assertNotIn("{{", text, role)
        self.assertNotIn("ns", init_instance.build_config("expert@x", ["d"], workspace=ws))
        cfg = init_instance.build_config("author@x", ["d"], workspace=ws)
        self.assertEqual(cfg["author"]["noteMacros"]["human"], ["\\Roey"])
        self.assertEqual(cfg["ns"], "x")

    def test_bad_name(self):
        with self.assertRaises(ac.ConfigError):
            init_instance.build_config("wizard@x", ["d"])
        with self.assertRaises(ac.ConfigError):
            init_instance.build_config("author@x", [])

    def test_researcher_scaffold(self):
        home = os.path.join(self.tmp, "Notebook")
        os.makedirs(home)
        lines = init_instance.init_instance("researcher@nb", home, ["dom"], ns="nb",
                                            workspace_path=self.ws_path)
        self.assertTrue(any("workspace: researcher@nb added" in l for l in lines))
        cfg = ac.load_config(home)
        self.assertEqual(cfg["researcher"]["reviewsHome"], "expert@d")
        for kind in init_instance.OBJECT_KINDS:
            self.assertTrue(os.path.isdir(os.path.join(home, "objects", kind)))
        for d in ("proofs", "journal", "audits", "views"):
            self.assertTrue(os.path.isdir(os.path.join(home, d)))
        self.assertTrue(os.path.isfile(os.path.join(self.board, "researcher@nb", ".gitkeep")))
        ws = ac.load_workspace(self.ws_path)
        self.assertEqual(ws["instances"]["researcher@nb"]["ns"], "nb")
        # health agrees with the workspace row
        ok, msg = academy_status.instance_health("researcher@nb", ws["instances"]["researcher@nb"])
        self.assertTrue(ok, msg)
        # a second run is refused without --force; with --force the row is 'present'
        with self.assertRaises(ac.ConfigError):
            init_instance.init_instance("researcher@nb", home, ["dom"], ns="nb",
                                        workspace_path=self.ws_path)
        lines = init_instance.init_instance("researcher@nb", home, ["dom"], ns="nb",
                                            workspace_path=self.ws_path, force=True)
        self.assertTrue(any("present" in l for l in lines))

    def test_gitattributes(self):
        home = os.path.join(self.tmp, "Attrs")
        os.makedirs(home)
        lines = init_instance.init_instance("researcher@at", home, ["dom"], ns="at",
                                            workspace_path=self.ws_path)
        text = read(os.path.join(home, ".gitattributes"))
        self.assertIn("* text=auto eol=lf", text)
        self.assertIn("*.ps1 text eol=crlf", text)
        self.assertTrue(any(".gitattributes" in l for l in lines))
        # an Author home keeps its tex endings; only the ledgers and registry are LF
        paper = os.path.join(self.tmp, "Paper")
        os.makedirs(paper)
        init_instance.init_instance("author@pp", paper, ["dom"], ns="pp",
                                    workspace_path=self.ws_path)
        text = read(os.path.join(paper, ".gitattributes"))
        self.assertNotIn("eol=lf\n*.ps1", text)
        self.assertIn("claims/** text eol=lf", text)
        self.assertIn("Drafts/*.md text eol=lf", text)
        # an existing .gitattributes is never overwritten, even with --force
        mine = os.path.join(self.tmp, "Mine")
        os.makedirs(mine)
        with open(os.path.join(mine, ".gitattributes"), "w") as fh:
            fh.write("*.tex -text\n")
        init_instance.init_instance("scientist@mine", mine, ["dom"],
                                    workspace_path=self.ws_path, force=True)
        self.assertEqual(read(os.path.join(mine, ".gitattributes")), "*.tex -text\n")

    def test_conflicting_registration(self):
        other = os.path.join(self.tmp, "Other")
        os.makedirs(other)
        with self.assertRaises(ac.ConfigError):
            init_instance.init_instance("author@p", other, ["dom"], ns="paper",
                                        workspace_path=self.ws_path)

    def test_dry_run_writes_nothing(self):
        home = os.path.join(self.tmp, "Dry")
        os.makedirs(home)
        before = read(self.ws_path)
        lines = init_instance.init_instance("scientist@dry", home, ["dom"],
                                            workspace_path=self.ws_path, dry_run=True)
        self.assertTrue(lines[0].startswith("would write"))
        self.assertFalse(os.path.exists(os.path.join(home, ".claude")))
        self.assertEqual(read(self.ws_path), before)


# ----------------------------------------------------------------------------

class AcademyStatusTest(Sandbox):

    def test_summary(self):
        ws = ac.load_workspace(self.ws_path)
        boardlib.create_ticket(self.board, "human", "Pick an option", "Choose",
                               "An answer", as_instance="author@p", workspace=ws,
                               date="2026-09-20")
        boardlib.create_ticket(self.board, "expert@d", "Cite X", "Cite it", "A card",
                               kind="cite", as_instance="author@p", workspace=ws,
                               date="2026-09-20")
        s = academy_status.summary(self.board, ws, "2026-09-01")
        self.assertEqual(len(s["needs_you"]["tickets_to_human"]), 1)
        self.assertEqual(s["in_flight"], {"expert@d": {"open": 1}})
        self.assertFalse(s["instances"]["author@p"]["ok"])
        self.assertIn("not switched over", s["instances"]["author@p"]["message"])
        text = academy_status.render(s, "usage 7d: 0 sessions")
        self.assertIn("NEEDS YOU (1)", text)
        self.assertIn("IN FLIGHT", text)
        self.assertIn("usage 7d", text)

    def test_last_visit_default(self):
        d = academy_status.last_visit(default_days=7, today=_dt.date(2026, 9, 27))
        self.assertTrue(ac.RE_DATE.match(d))


if __name__ == "__main__":
    unittest.main()
