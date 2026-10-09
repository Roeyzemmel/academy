"""Tests for the interface-skill scripts: usage_report, deep_dive_index,
init_instance, academy_status (and the moved session_usage).

Run from the repo root:  py -m unittest discover academy/tests
Everything runs in a temp directory with a throw-away workspace (ACADEMY_WORKSPACE).
"""

import datetime as _dt
import glob
import io
import json
import re
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

    def test_author_template_has_no_roadmap_path_but_an_old_config_validates(self):
        ws = ac.load_workspace(self.ws_path)
        cfg = init_instance.build_config("author@x", ["d"], workspace=ws)
        self.assertNotIn("roadmap", cfg["paths"])
        self.assertNotIn("roadmap", ac.REQUIRED_PATHS["author"])
        # the roadmap was dropped (the board is the only queue): an old config that still
        # names it is accepted and the key is ignored
        cfg["paths"]["roadmap"] = "Drafts/roadmap.md"
        self.assertEqual(ac.validate_config(cfg), [])

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

    def test_author_scaffold_writes_the_vision_file_once(self):
        home = os.path.join(self.tmp, "Paper")
        os.makedirs(home)
        lines = init_instance.init_instance("author@pp", home, ["dom"], ns="pp",
                                            workspace_path=self.ws_path)
        path = os.path.join(home, "Drafts", "vision.md")
        self.assertTrue(any(l.startswith("vision: wrote") for l in lines), lines)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("# Vision: author@pp", text)
        self.assertNotIn("{{", text)
        for head in ("## The arc", "## Statements", "## Proofs", "## Decisions log"):
            self.assertIn(head, text)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("kept\n")
        lines = init_instance.init_instance("author@pp", home, ["dom"], ns="pp",
                                            workspace_path=self.ws_path, force=True)
        self.assertIn("vision: present, left alone", lines)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual("kept\n", fh.read())

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

    def test_scientist_scaffold_writes_the_lab(self):
        home = os.path.join(self.tmp, "Lab")
        os.makedirs(home)
        lines = init_instance.init_instance("scientist@lab2", home, ["dom"], ns="lab2",
                                            workspace_path=self.ws_path)
        self.assertTrue(any(l.startswith("lab: ") and not l.startswith("lab: 0")
                            for l in lines), lines)
        pkg = ac.load_config(home)["paths"]["package"]
        self.assertTrue(os.path.isfile(os.path.join(home, pkg, "env.py")))
        tpl = read(os.path.join(home, "experiments", "_template.py"))
        self.assertIn("from %s import env" % pkg, tpl)
        self.assertIn("lab2:foo", tpl)
        self.assertNotIn("{{", read(os.path.join(home, "experiments", "README.md")))

    def test_expert_scaffold_writes_the_library_readme_once(self):
        home = os.path.join(self.tmp, "Lib")
        os.makedirs(home)
        lines = init_instance.init_instance("expert@lib", home, ["dom"],
                                            workspace_path=self.ws_path)
        self.assertTrue(any(l.startswith("library README: wrote") for l in lines), lines)
        text = read(os.path.join(home, "README.md"))
        self.assertIn("`expert@lib`", text)
        self.assertNotIn("{{", text)
        with open(os.path.join(home, "README.md"), "w") as fh:
            fh.write("mine\n")
        lines = init_instance.init_instance("expert@lib", home, ["dom"],
                                            workspace_path=self.ws_path, force=True)
        self.assertIn("library README: present, left alone", lines)
        self.assertEqual(read(os.path.join(home, "README.md")), "mine\n")

    def test_board_readme_lists_the_instances_and_is_regenerated(self):
        home = os.path.join(self.tmp, "Nb1")
        os.makedirs(home)
        lines = init_instance.init_instance("researcher@nb1", home, ["dom"], ns="nb1",
                                            workspace_path=self.ws_path)
        self.assertIn("board README: wrote", lines)
        path = os.path.join(self.board, "README.md")
        text = read(path)
        self.assertNotIn("{{", text)
        for name in ("author@p", "expert@d", "researcher@nb1"):
            self.assertIn("`%s/`" % name, text)
        # a hand edit outside the markers survives; the table follows the workspace
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\nLocal note.\n")
        home2 = os.path.join(self.tmp, "Nb2")
        os.makedirs(home2)
        lines = init_instance.init_instance("researcher@nb2", home2, ["dom"], ns="nb2",
                                            workspace_path=self.ws_path)
        self.assertIn("board README: updated", lines)
        text = read(path)
        self.assertIn("`researcher@nb2/`", text)
        self.assertIn("Local note.", text)
        # a README without the markers is left alone
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# ours\n")
        self.assertEqual(init_instance.write_board_readme(self.board, {"a@b": {}}), "present")
        self.assertEqual(read(path), "# ours\n")

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


class AsHumanLintTests(unittest.TestCase):
    ALLOWED = {os.path.join("academy", "skills", s, "SKILL.md")
               for s in ("board", "desk", "decide", "cowork")}
    PATTERN = re.compile(r"as_human|--as\s+human")

    def test_only_board_desk_decide_file_as_human(self):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        bad, seen = [], set()
        for plugin in ("academy", "author", "expert", "researcher", "scientist"):
            for sub in ("skills", "agents", "scripts", "hooks"):
                root = os.path.join(repo, plugin, sub)
                for dp, _dn, fns in os.walk(root):
                    for fn in fns:
                        if not fn.endswith((".md", ".py", ".json")) or fn == "_academy.py":
                            continue
                        rel = os.path.relpath(os.path.join(dp, fn), repo)
                        with open(os.path.join(dp, fn), encoding="utf-8") as fh:
                            text = fh.read()
                        if self.PATTERN.search(text):
                            seen.add(rel)
                            if rel not in self.ALLOWED and rel != os.path.join(
                                    "academy", "scripts", "board.py"):
                                bad.append(rel)
        self.assertEqual(bad, [], "only /academy:board, desk, decide and cowork (the "
                                  "orchestrator, after the human approved the plan) "
                                  "file as human")
        self.assertTrue(self.ALLOWED <= seen, "the four skills must say --as human")


class ChainDocsTests(unittest.TestCase):
    """No skill or agent tells a role to file to a non-neighbour."""
    REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    CASES = {
        os.path.join("author", "agents", "math-writer.md"): "final_to",
        os.path.join("author", "agents", "figure-maker.md"): "final_to",
        os.path.join("author", "skills", "inbox", "references", "routing.md"): "final_to",
        os.path.join("expert", "skills", "verify", "references", "conclude.md"): "final_to",
        os.path.join("expert", "agents", "review-chair.md"): "final_to",
        os.path.join("scientist", "skills", "examples-audit", "SKILL.md"): "final_to",
        os.path.join("academy", "skills", "citation-discipline", "SKILL.md"): "neighbour",
    }

    def test_rerouted_docs_mention_the_relay(self):
        for rel, word in self.CASES.items():
            with open(os.path.join(self.REPO, rel), encoding="utf-8") as fh:
                self.assertIn(word, fh.read(), rel)

    def test_prover_no_longer_files_experiments(self):
        with open(os.path.join(self.REPO, "researcher", "agents", "prover.md"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotRegex(text, r"(?i)ticket[^.\n]*to (the )?scientist")

    OLD_ROUTE = re.compile(r"(?i)prove ticket|Researcher ticket|"
                           r"ticket[^.\n]*to (the )?(Researcher|Scientist)")

    def test_author_plugin_files_nothing_past_the_expert(self):
        """A line that files to the Researcher or Scientist must say final_to."""
        author = os.path.join(self.REPO, "author")
        paths = [os.path.join(author, "README.md")]
        for sub in ("agents", "skills"):
            for dp, _dn, fns in os.walk(os.path.join(author, sub)):
                paths += [os.path.join(dp, f) for f in fns if f.endswith(".md")]
        self.assertGreater(len(paths), 10)
        bad = []
        for path in paths:
            with open(path, encoding="utf-8") as fh:
                for n, line in enumerate(fh, 1):
                    if self.OLD_ROUTE.search(line) and "final_to" not in line:
                        bad.append("%s:%d" % (os.path.relpath(path, self.REPO), n))
        self.assertEqual(bad, [])

    def read(self, *parts):
        with open(os.path.join(self.REPO, *parts), encoding="utf-8") as fh:
            return fh.read()

    RELAYS = (("expert", "research-intake"), ("expert", "paper-liaison"),
              ("researcher", "experiment-spec"), ("researcher", "lit-request"))

    def test_relays_describe_the_return_leg(self):
        """F1: close the child, then blocked -> in-progress -> delivered."""
        for plugin, name in self.RELAYS:
            text = self.read(plugin, "agents", name + ".md")
            self.assertIn("return leg", text, name)
            self.assertRegex(text, r"`closed`", name)
            self.assertRegex(text, r"`blocked` to `in-progress`,? then `delivered`", name)

    def test_inbox_skills_take_the_return_leg(self):
        for plugin in ("expert", "researcher"):
            text = self.read(plugin, "skills", "inbox", "SKILL.md")
            self.assertIn("return leg", text, plugin)
            self.assertIn("`delivered` or terminal", text, plugin)

    def test_research_intake_reads_a_missing_final_to_as_researcher(self):
        text = self.read("expert", "agents", "research-intake.md")
        self.assertRegex(text, r"(?i)no `final_to`[^.]*final_to: researcher`")

    def test_tex_engineer_hands_citations_back(self):
        """F2: tex-engineer is no author->expert liaison."""
        text = self.read("author", "agents", "tex-engineer.md")
        self.assertNotRegex(text, r"(?i)file a `cite` ticket")
        self.assertIn("`cite` request", text)

    def test_lead_researcher_reaches_paper_owners_through_the_expert(self):
        text = self.read("researcher", "agents", "lead-researcher.md")
        self.assertIn("final_to: author", text)

    def test_verify_by_hand_leaves_repairs_to_review_chair(self):
        """M9: the Expert main session is no expert->author/researcher liaison."""
        text = self.read("expert", "skills", "verify", "SKILL.md")
        self.assertRegex(text, r"(?i)`main` is not a liaison")

    def section(self, text, start, end):
        return text[text.index(start):text.index(end)]

    def test_protocol_research_flow_names_the_research_kind(self):
        """M4: research-intake forwards a `research` child; /author:inbox files as main."""
        flow = self.section(self.read("docs", "protocol.md"),
                            "### 6.4", "### 6.5")
        self.assertNotIn("`lead`", flow)
        self.assertIn("child `research` ticket", flow)
        self.assertIn("`main`", flow)

    def test_protocol_chain_section_warns_about_nesting_and_the_cli(self):
        """M6, M7: relay-within-relay and the self-declared CLI identity."""
        chain = self.section(self.read("docs", "protocol.md"), "### 5.1", "## 6.")
        self.assertIn("fresh chain", chain)
        self.assertIn("self-declared", chain)
        self.assertIn("advisory", chain)
        self.assertIn("return leg", chain)
        scripts = self.read("academy", "references", "scripts.md")
        self.assertIn("self-declared", scripts)
        self.assertIn("advisory", scripts)


if __name__ == "__main__":
    unittest.main()
