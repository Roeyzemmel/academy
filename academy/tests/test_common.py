"""Unit tests for academy/lib/academy_common.py and the contracts it implements.

Run from the repo root:  py -m unittest discover academy/tests
"""

import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))

import academy_common as ac  # noqa: E402


def read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def fenced(md_text, lang):
    """All fenced code blocks of language ``lang`` in a Markdown text."""
    return re.findall(r"^```%s\n(.*?)^```" % re.escape(lang), md_text, re.M | re.S)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return path

    def fixture_workspace(self):
        """A workspace.json for the five standard instances, homes under the temp dir."""
        spec = {"expert@main": ("library", None), "scientist@main": ("lab", "lab"),
                "researcher@alpha": ("slope1", "s1"), "researcher@beta": ("flat", "flat"),
                "author@main": ("paper", "paper")}
        inst = {}
        for name, (home, ns) in spec.items():
            inst[name] = {"role": name.split("@")[0], "home": os.path.join(self.tmp, home),
                          "domains": ["translation-surfaces"]}
            if ns:
                inst[name]["ns"] = ns
        return self.write("fixture/workspace.json", json.dumps(
            {"instances": inst, "board": os.path.join(self.tmp, "board"),
             "human": {"name": "Roey"}}))

    def fixture_workspace(self):
        """A workspace.json for the five standard instances, homes under the temp dir."""
        spec = {"expert@main": ("library", None), "scientist@main": ("lab", "lab"),
                "researcher@alpha": ("slope1", "s1"), "researcher@beta": ("flat", "flat"),
                "author@main": ("paper", "paper")}
        inst = {}
        for name, (home, ns) in spec.items():
            inst[name] = {"role": name.split("@")[0], "home": os.path.join(self.tmp, home),
                          "domains": ["translation-surfaces"]}
            if ns:
                inst[name]["ns"] = ns
        return self.write("fixture/workspace.json", json.dumps(
            {"instances": inst, "board": os.path.join(self.tmp, "board"),
             "human": {"name": "Roey"}}))


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def config_examples():
    """{instance: config} for every '### Example: <instance>' block in docs/config.md."""
    text = read(os.path.join(REPO, "docs", "config.md"))
    out = {}
    for m in re.finditer(r"^### Example: (\S+)\n\n```json\n(.*?)^```", text, re.M | re.S):
        out[m.group(1)] = json.loads(m.group(2))
    return out


class ConfigTests(TempDir):
    def make_home(self, cfg, rel="home"):
        home = os.path.join(self.tmp, rel)
        os.makedirs(os.path.join(home, ".claude"), exist_ok=True)
        with open(os.path.join(home, ".claude", "academy.json"), "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        return home

    def test_docs_examples_are_the_four_homes_and_valid(self):
        ex = config_examples()
        self.assertEqual(sorted(ex), ["author@main", "expert@main", "researcher@alpha",
                                      "scientist@main"])
        for name, cfg in ex.items():
            merged = ac._deep_merge(ac.CONFIG_DEFAULTS, cfg)
            self.assertEqual(ac.validate_config(merged), [], name)
            self.assertEqual(cfg["instance"], name)

    def test_docs_examples_agree_with_workspace(self):
        ws = ac.load_workspace(self.fixture_workspace())
        for name, cfg in config_examples().items():
            inst = ws["instances"][name]
            self.assertEqual(inst["role"], cfg["role"])
            self.assertEqual(inst["domains"], cfg["domains"])
            self.assertEqual(inst.get("ns"), cfg.get("ns"))

    def test_load_config_merges_defaults_and_sets_home(self):
        cfg = dict(config_examples()["expert@main"])
        del cfg["budget"]
        del cfg["gate"]
        home = self.make_home(cfg)
        loaded = ac.load_config(home)
        self.assertEqual(loaded["budget"]["itemsPerRun"], 3)
        self.assertEqual(loaded["gate"]["commit"], "normal")
        self.assertEqual(loaded["_home"], os.path.abspath(home).replace("\\", "/"))

    def test_load_config_errors(self):
        with self.assertRaises(ac.ConfigError):
            ac.load_config(os.path.join(self.tmp, "nowhere"))
        bad = dict(config_examples()["scientist@main"])
        bad["scientist"] = dict(bad["scientist"], policy={"probe": "laptop-wsl",
                                                          "test": "laptop-wsl",
                                                          "run": "mars"})
        home = self.make_home(bad)
        with self.assertRaises(ac.ConfigError) as cm:
            ac.load_config(home)
        self.assertIn("policy.run", str(cm.exception))
        home2 = self.make_home({"schema": 1}, "h2")
        with self.assertRaises(ac.ConfigError):
            ac.load_config(home2)
        home3 = os.path.join(self.tmp, "h3")
        self.write("h3/.claude/academy.json", "{not json")
        with self.assertRaises(ac.ConfigError):
            ac.load_config(home3)

    def test_validate_config_catches_each_rule(self):
        base = ac._deep_merge(ac.CONFIG_DEFAULTS, config_examples()["author@main"])
        cases = [
            ({"role": "poet"}, "role"),
            ({"instance": "researcher@other"}, "does not start with role"),
            ({"instance": "Author@BI"}, "instance must look like"),
            ({"domains": []}, "domains"),
            ({"ns": None}, "ns is required"),
            ({"budget": dict(base["budget"], itemsPerRun=5)}, "itemsPerRun"),
            ({"budget": dict(base["budget"], maxModel="gpt")}, "maxModel"),
            ({"gate": dict(base["gate"], commit="sometimes")}, "gate.commit"),
            ({"paths": {"tex": "main.tex"}}, "paths.bib"),
            ({"author": None}, "'author' block"),
            ({"schema": 2}, "schema"),
        ]
        for patch, needle in cases:
            cfg = dict(base)
            cfg.update(patch)
            probs = ac.validate_config(cfg)
            self.assertTrue(any(needle in p for p in probs), (patch, probs))

    def test_scientist_env_kinds(self):
        base = ac._deep_merge(ac.CONFIG_DEFAULTS, config_examples()["scientist@main"])
        sci = dict(base["scientist"])
        sci["envs"] = dict(sci["envs"], cloud={"kind": "k8s"}, bad={"kind": "ssh"},
                           w={"kind": "wsl"})
        cfg = dict(base, scientist=sci)
        probs = " ".join(ac.validate_config(cfg))
        self.assertIn("cloud.kind", probs)
        self.assertIn("bad: kind ssh needs host", probs)
        self.assertIn("w: kind wsl needs distro", probs)

    def test_gate_mode_branch_override(self):
        cfg = config_examples()["author@main"]
        self.assertEqual(ac.gate_mode(cfg, "main"), "normal")
        self.assertEqual(ac.gate_mode(cfg, "academy-migration"), "off")
        self.assertEqual(ac.gate_mode(cfg), "normal")

    def test_gate_mode_glob_matches_template_branch(self):
        cfg = {"gate": {"commit": "normal",
                        "branches": {"????-??-??/*/*": {"commit": "warn"}}}}
        self.assertEqual(ac.gate_mode(cfg, "2026-09-30/t-0059/author"), "warn")
        self.assertEqual(ac.gate_mode(cfg, "main"), "normal")

    def test_gate_mode_exact_beats_glob(self):
        # the exact key comes after the glob in dict order and still wins
        cfg = {"gate": {"commit": "normal",
                        "branches": {"????-??-??/*/*": {"commit": "warn"},
                                     "2026-09-30/release/author": {"commit": "strict"}}}}
        self.assertEqual(ac.gate_mode(cfg, "2026-09-30/release/author"), "strict")
        self.assertEqual(ac.gate_mode(cfg, "2026-09-30/other/author"), "warn")

    def test_gate_mode_no_match_falls_back_to_default(self):
        cfg = {"gate": {"commit": "strict",
                        "branches": {"????-??-??/*/*": {"commit": "warn"},
                                     "academy-migration": {"commit": "off"}}}}
        self.assertEqual(ac.gate_mode(cfg, "feature/x"), "strict")
        self.assertEqual(ac.gate_mode(cfg, None), "strict")
        self.assertEqual(ac.gate_mode({}, "2026-09-30/a/b"), "normal")

    def test_gate_mode_glob_first_match_wins(self):
        cfg = {"gate": {"commit": "normal",
                        "branches": {"*/*/author": {"commit": "off"},
                                     "????-??-??/*/*": {"commit": "warn"}}}}
        self.assertEqual(ac.gate_mode(cfg, "2026-09-30/t/author"), "off")
        self.assertEqual(ac.gate_mode(cfg, "2026-09-30/t/expert"), "warn")

    def test_gate_mode_glob_is_case_sensitive(self):
        cfg = {"gate": {"commit": "normal", "branches": {"WIP/*": {"commit": "off"}}}}
        self.assertEqual(ac.gate_mode(cfg, "wip/x"), "normal")
        self.assertEqual(ac.gate_mode(cfg, "WIP/x"), "off")

    def test_validate_config_accepts_warn(self):
        base = ac._deep_merge(ac.CONFIG_DEFAULTS, config_examples()["author@main"])
        cfg = dict(base, gate=dict(base["gate"], commit="warn",
                                   branches={"????-??-??/*/*": {"commit": "warn"}}))
        self.assertEqual(ac.validate_config(cfg), [])

    def test_find_home(self):
        home = self.make_home(config_examples()["expert@main"])
        deep = os.path.join(home, "a", "b")
        os.makedirs(deep)
        self.assertEqual(ac.find_home(deep), home)
        self.assertEqual(ac.find_home(os.path.join(deep, "file.md")), home)  # file, absent
        self.assertEqual(ac.find_home(home), home)
        other = os.path.join(self.tmp, "other")
        os.makedirs(other)
        self.assertIsNone(ac.find_home(other))
        self.assertIsNone(ac.find_home(""))

    def test_find_home_skips_user_home(self):
        fake_user = self.make_home({"schema": 1}, "user")
        sub = os.path.join(fake_user, "proj")
        os.makedirs(sub)
        saved = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
        try:
            os.environ["HOME"] = fake_user
            os.environ["USERPROFILE"] = fake_user
            self.assertIsNone(ac.find_home(sub))
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_path_in_role(self):
        home = self.make_home(config_examples()["author@main"])
        cfg = ac.load_config(home)
        j = lambda *p: os.path.join(home, *p)  # noqa: E731
        self.assertTrue(ac.path_in_role(j("sections", "billiards.tex"), cfg, "tex"))
        self.assertTrue(ac.path_in_role("main.tex", cfg, "tex"))
        self.assertFalse(ac.path_in_role(j("sections", "sub", "x.tex"), cfg, "tex"))
        self.assertTrue(ac.path_in_role(j("Drafts", "x", "y.md"), cfg, "drafts"))
        self.assertFalse(ac.path_in_role(j("Draftsy", "y.md"), cfg, "drafts"))
        self.assertTrue(ac.path_in_role(j("claims", "INDEX.md"), cfg, "views"))
        self.assertTrue(ac.path_in_role(j("anything.txt"), cfg, "author"))
        self.assertFalse(ac.path_in_role(j("anything.txt"), cfg, "expert"))
        self.assertFalse(ac.path_in_role(os.path.join(self.tmp, "x.tex"), cfg, "author"))
        self.assertFalse(ac.path_in_role(j("main.tex"), cfg, "nosuchkey"))
        if os.name == "nt":
            self.assertTrue(ac.path_in_role(j("SECTIONS", "A.TEX"), cfg, "tex"))

    def test_glob_double_star(self):
        rx = ac._glob_regex("*.src/**")
        self.assertTrue(rx.match("AW21.src/main.tex"))
        self.assertTrue(rx.match("AW21.src/a/b.tex"))
        self.assertFalse(rx.match("sub/AW21.src/a.tex"))
        self.assertTrue(ac._match_path("x/y/z.md", "**/z.md"))
        self.assertTrue(ac._match_path("z.md", "**/z.md"))


class WorkspaceTests(TempDir):
    def test_repo_workspace(self):
        ws = ac.load_workspace(self.fixture_workspace())
        self.assertEqual(set(ws["instances"]), {"expert@main", "scientist@main",
                                                "researcher@alpha", "researcher@beta",
                                                "author@main"})
        self.assertEqual(ac.instance_for_home(ws, os.path.join(self.tmp, "paper")), "author@main")
        self.assertIsNone(ac.instance_for_home(ws, self.tmp))

    def test_env_overrides_homes_and_board(self):
        path = self.fixture_workspace()
        other = os.path.join(self.tmp, "elsewhere")
        env = {"ACADEMY_HOME_AUTHOR_MAIN": other, "ACADEMY_BOARD": os.path.join(self.tmp, "b2")}
        saved = {k: os.environ.get(k) for k in list(env) + ["ACADEMY_ENV_WORKSPACE"]}
        os.environ.update(env)

        def load(env_ws):
            os.environ["ACADEMY_ENV_WORKSPACE"] = env_ws
            return ac.load_workspace(path)
        try:
            ws = load(path)
            unrelated = load(path + ".other")     # the variables belong to another file
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.assertEqual(ws["instances"]["author@main"]["home"], other)
        self.assertEqual(ws["board"], env["ACADEMY_BOARD"])
        self.assertEqual(unrelated["instances"]["author@main"]["home"],
                         os.path.join(self.tmp, "paper"))
        self.assertEqual(ac.env_home_name("researcher@alpha"), "ACADEMY_HOME_RESEARCHER_ALPHA")

    def test_default_lookup_is_beside_the_academy(self):
        # the workspace layout: <workspace>/workspace.json and <workspace>/academy
        os.makedirs(os.path.join(self.tmp, "academy"))
        with open(self.fixture_workspace(), encoding="utf-8") as fh:
            self.write("workspace.json", fh.read())
        saved = {k: os.environ.get(k) for k in ("ACADEMY_WORKSPACE", "ACADEMY_ROOT")}
        os.environ.pop("ACADEMY_WORKSPACE", None)
        os.environ["ACADEMY_ROOT"] = os.path.join(self.tmp, "academy")
        try:
            ws = ac.load_workspace()
            self.assertEqual(ws["_path"], os.path.join(self.tmp, "workspace.json").replace("\\", "/"))
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_bad_workspace(self):
        for text in ('{"instances": {}}',
                     '{"instances": {"Bad Name": {}}, "board": "b"}',
                     '{"instances": {"author@x": {"role": "expert", "home": "h", '
                     '"domains": ["d"]}}, "board": "b"}',
                     '{"instances": {"author@x": {"role": "author"}}, "board": "b"}'):
            p = self.write("ws.json", text)
            with self.assertRaises(ac.ConfigError):
                ac.load_workspace(p)


# ---------------------------------------------------------------------------
# Agents and permissions
# ---------------------------------------------------------------------------

class IdentityTests(unittest.TestCase):
    def test_variants(self):
        self.assertEqual(ac.agent_identity({"agent_type": "author:math-writer"}),
                         ("author", "math-writer"))
        self.assertEqual(ac.agent_identity({"subagent_type": "prover"}), ("", "prover"))
        self.assertEqual(ac.agent_identity({"agentType": " Expert:Librarian "}),
                         ("expert", "librarian"))
        self.assertEqual(ac.agent_identity({"subagentType": "a:b:clerk"}), ("a:b", "clerk"))
        self.assertEqual(ac.agent_identity('{"agent_type": "scientist:developer"}'),
                         ("scientist", "developer"))

    def test_precedence_and_human(self):
        ev = {"agent_type": "x:first", "subagent_type": "second"}
        self.assertEqual(ac.agent_identity(ev)[1], "first")
        self.assertEqual(ac.agent_identity({"agent_type": "  ", "agentType": "y"})[1], "y")
        self.assertEqual(ac.agent_identity({}), ("", ""))
        self.assertEqual(ac.agent_identity("not json"), ("", ""))
        self.assertEqual(ac.agent_identity([1, 2]), ("", ""))
        self.assertTrue(ac.is_human({"cwd": "x"}))

    def test_launched_agent_is_not_the_caller(self):
        ev = {"tool_name": "Task", "tool_input": {"subagent_type": "librarian"}}
        self.assertEqual(ac.agent_identity(ev), ("", ""))


class PermissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = ac.load_permissions(os.path.join(PLUGIN, "permissions.json"))

    def test_roster_matches_plan(self):
        ros = ac.roster(self.p)
        self.assertEqual(len(ros), 29)
        count = {}
        for plugin in self.p["roster"]:
            count[plugin] = len(self.p["roster"][plugin])
        self.assertEqual(count, {"academy": 4, "author": 6, "researcher": 6, "expert": 8,
                                 "scientist": 5})
        all_names = [a for v in self.p["roster"].values() for a in v]
        self.assertEqual(len(all_names), len(set(all_names)), "bare names must be unique")
        for g, names in self.p["groups"].items():
            for n in names:
                self.assertIn(n, ros, "group %s names unknown agent %s" % (g, n))

    def test_tools_listed(self):
        self.assertEqual(set(self.p["tools"]), {
            "claims_new", "claims_attach_evidence", "claims_propose_status",
            "claims_set_status", "queue_add", "tickets_create", "tickets_update",
            "packets_create", "packets_decide"})
        ros = ac.roster(self.p)
        for tool, spec in self.p["tools"].items():
            for n in spec.get("allow", []) + spec.get("deny", []):
                if not n.startswith("@"):
                    self.assertIn(n, ros, "%s names unknown agent %s" % (tool, n))

    def test_may_call(self):
        ok = lambda t, a: ac.may_call(self.p, t, a)[0]  # noqa: E731
        for tool in self.p["tools"]:
            self.assertTrue(ok(tool, ""), tool)
        self.assertTrue(ok("claims_set_status", "claim-keeper"))
        for a in ("rigor-reviewer", "prover", "review-chair", "experiment-reviewer"):
            self.assertFalse(ok("claims_set_status", a), a)
        self.assertTrue(ok("queue_add", "experimenter"))
        self.assertTrue(ok("queue_add", "developer"))
        self.assertFalse(ok("queue_add", "math-writer"))
        self.assertTrue(ok("claims_new", "prover"))
        self.assertTrue(ok("tickets_create", "prover"))
        self.assertTrue(ok("tickets_create", "math-writer"))
        for tool in self.p["tools"]:
            for grader in ("rigor-reviewer", "experiment-reviewer", "referee", "explainer",
                           "clerk"):
                self.assertFalse(ok(tool, grader), (tool, grader))
        self.assertFalse(ok("packets_decide", "concierge"))
        self.assertFalse(ok("tickets_create", "stranger"))
        self.assertTrue(ok("claims_show", "clerk"))

    def test_ticket_tables_mirror_the_lib(self):
        t = self.p["tickets"]
        table = {}
        for old, targets in t["transitions"].items():
            for new, who in targets.items():
                table[(old, new)] = tuple(who)
        self.assertEqual(table, ac.TRANSITIONS)
        self.assertEqual(set(t["transitions"]), set(ac.TICKET_STATUSES))
        self.assertEqual({k: tuple(v) for k, v in t["fields"].items()}, ac.TICKET_FIELDS)
        owned = [f for v in ac.TICKET_FIELDS.values() for f in v]
        self.assertEqual(sorted(owned), sorted(ac.TICKET_KEY_ORDER))


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------

class FrontmatterTests(unittest.TestCase):
    def test_types(self):
        text = ("---\na: plain text\nb: 42\nc: -3\nd: 1.5\ne: true\nf: false\ng:\nh: ~\n"
                "i: null\nj: \"quoted: yes\"\nk: 'it''s'\nl: [x, \"y, z\", 3, null]\n"
                "m: []\nn: 2026-09-27\no: {runs: 2, max_model: opus}\np:\n  runs: 1\n"
                "  max_model: sonnet\nq:\n  - one\n  - 2\nr: a # comment\n"
                "s: \"has # hash\"\n---\nbody\n")
        meta, body = ac.read_frontmatter(text)
        self.assertEqual(meta, {
            "a": "plain text", "b": 42, "c": -3, "d": 1.5, "e": True, "f": False,
            "g": None, "h": None, "i": None, "j": "quoted: yes", "k": "it's",
            "l": ["x", "y, z", 3, None], "m": [], "n": "2026-09-27",
            "o": {"runs": 2, "max_model": "opus"}, "p": {"runs": 1, "max_model": "sonnet"},
            "q": ["one", 2], "r": "a", "s": "has # hash"})
        self.assertEqual(body, "body\n")

    def test_no_frontmatter_and_crlf(self):
        self.assertEqual(ac.read_frontmatter("# Title\n"), ({}, "# Title\n"))
        meta, body = ac.read_frontmatter("---\r\nid: T-0001\r\n---\r\nx\r\n")
        self.assertEqual(meta, {"id": "T-0001"})
        self.assertEqual(body, "x\n")
        meta, _ = ac.read_frontmatter("\ufeff---\nid: 1\n---\n")
        self.assertEqual(meta, {"id": 1})

    def test_errors(self):
        for bad in ("---\na: 1\n",                      # unclosed
                    "---\na: [x, [y]]\n---\n",          # nested
                    "---\na: 1\na: 2\n---\n",           # duplicate
                    "---\njust words\n---\n",           # not key: value
                    "---\n  a: 1\n---\n",               # stray indentation
                    "---\na: [x, y\n---\n",             # unterminated list
                    "---\na: \"open\n---\n",            # bad quote
                    "---\na:\n  b: [1]\n---\n"):        # nested under block map
            with self.assertRaises(ac.FrontmatterError, msg=bad):
                ac.read_frontmatter(bad)

    def test_hand_written_apostrophes(self):
        meta, _ = ac.read_frontmatter("---\na: it's fine # note\nb: [it's, x]\n"
                                      "c: say \"hi\" there\n---\n")
        self.assertEqual(meta, {"a": "it's fine", "b": ["it's", "x"],
                                "c": "say \"hi\" there"})

    def test_write_rejects_nesting(self):
        with self.assertRaises(ac.FrontmatterError):
            ac.write_frontmatter({"a": [[1]]})
        with self.assertRaises(ac.FrontmatterError):
            ac.write_frontmatter({"a": {"b": {"c": 1}}})
        with self.assertRaises(ac.FrontmatterError):
            ac.write_frontmatter({"bad key": 1})
        with self.assertRaises(ac.FrontmatterError):
            ac.write_frontmatter({"a": object()})

    def test_tricky_strings_round_trip(self):
        tricky = ["", " lead", "trail ", "a: b", "ends:", "#x", "a #b", "[x]", "{y}",
                  "-dash", "- item", "true", "False", "null", "~", "12", "-3", "1.5",
                  "it's", "say \"hi\"", "comma, here", "@at", "*star", "!bang", "|pipe",
                  ">gt", "%pct", "`tick`", "?q", "&amp", "π unicode", "back\\slash",
                  "line\nbreak", "tab\there", "paper:lem:x", "file:author@main/a b.tex",
                  "2026-09-27", "T-0001"]
        for s in tricky:
            meta = {"k": s, "l": [s, "x"], "m": {"v": s}}
            text = ac.write_frontmatter(meta, "")
            back, _ = ac.read_frontmatter(text)
            self.assertEqual(back, meta, repr(s))

    def test_canonical_round_trip(self):
        meta = {"id": "T-0003", "title": "A title", "refs": ["paper:lem:x", "T-0001"],
                "parent": None, "blocks": [], "budget": {"runs": 2, "max_model": "opus"},
                "empty": {}, "flag": True, "n": 7}
        text = ac.write_frontmatter(meta, "\n## Thread\n")
        self.assertEqual(ac.write_frontmatter(*ac.read_frontmatter(text)), text)
        self.assertIn("parent:\n", text)
        self.assertIn("refs: [paper:lem:x, T-0001]\n", text)
        self.assertIn("budget:\n  runs: 2\n  max_model: opus\n", text)
        back, _ = ac.read_frontmatter(text)
        self.assertEqual(back, meta)


# ---------------------------------------------------------------------------
# Files and ids
# ---------------------------------------------------------------------------

class FileTests(TempDir):
    def raw(self, path):
        with open(path, "rb") as fh:
            return fh.read()

    def test_atomic_write_lf_and_crlf(self):
        p = os.path.join(self.tmp, "sub", "a.md")
        ac.atomic_write(p, "one\r\ntwo\nthree")
        self.assertEqual(self.raw(p), b"one\ntwo\nthree")
        ac.atomic_write(p, "x\ny\n", newline="\r\n")
        self.assertEqual(self.raw(p), b"x\r\ny\r\n")
        ac.atomic_write(p, "\u03c0\n")
        self.assertEqual(self.raw(p), "\u03c0\n".encode("utf-8"))
        self.assertEqual(sorted(os.listdir(os.path.dirname(p))), ["a.md"])

    def test_allocate_sequential_and_counter(self):
        board = self.tmp
        self.assertEqual(ac.allocate_id(board, "ticket"), "T-0001")
        self.assertEqual(ac.allocate_id(board, "T"), "T-0002")
        self.assertEqual(ac.allocate_id(board, "packet"), "P-0001")
        self.assertEqual(read(os.path.join(board, ".ids", "next-ticket")), "3\n")
        self.assertFalse(os.path.exists(os.path.join(board, ".ids", "lock")))
        with self.assertRaises(ac.AcademyError):
            ac.allocate_id(board, "verdict")

    def test_allocate_never_reissues_ids_on_disk(self):
        self.write("author@main/T-0041-x.md", "")
        self.write("packets/expert@main/P-0009-y.md", "")
        self.write(".ids/next-ticket", "5\n")
        self.assertEqual(ac.allocate_id(self.tmp, "ticket"), "T-0042")
        self.assertEqual(ac.allocate_id(self.tmp, "packet"), "P-0010")
        # a corrupt counter falls back to the disk: P-0010 was allocated but never
        # written, so it may be reissued; nothing on disk ever is
        self.write(".ids/next-packet", "garbage")
        self.assertEqual(ac.allocate_id(self.tmp, "packet"), "P-0010")

    def test_wide_ids(self):
        self.write(".ids/next-ticket", "10000\n")
        self.assertEqual(ac.allocate_id(self.tmp, "ticket"), "T-10000")

    def test_concurrent_allocation_unique(self):
        got, errors = [], []

        def worker():
            try:
                for _ in range(5):
                    got.append(ac.allocate_id(self.tmp, "ticket"))
            except Exception as exc:        # pragma: no cover
                errors.append(exc)
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(got), 40)
        self.assertEqual(len(set(got)), 40)
        self.assertEqual(sorted(got), ["T-%04d" % i for i in range(1, 41)])

    def test_lock_timeout_and_stale(self):
        lock = self.write(".ids/lock", "999 0\n")
        with self.assertRaises(ac.LockTimeout):
            with ac.IdLock(self.tmp, timeout=0.2):
                pass
        old = time.time() - ac.LOCK_STALE_SECONDS - 5
        os.utime(lock, (old, old))
        self.assertEqual(ac.allocate_id(self.tmp, "ticket"), "T-0001")
        self.assertFalse(os.path.exists(lock))


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

def protocol_example():
    text = read(os.path.join(REPO, "docs", "protocol.md"))
    blocks = [b for b in fenced(text, "markdown") if b.startswith("---\nid: T-0007")]
    assert len(blocks) == 1
    return blocks[0]


class TicketTests(TempDir):
    def test_budget_max_model_is_optional(self):
        # T-0071: the model comes from the agent file; budget.max_model is an
        # optional advisory note, and a budget of runs alone is valid.
        meta, body = ac.read_frontmatter(protocol_example())
        for budget in ({"runs": 2}, {"runs": 1, "max_model": "haiku"}):
            m = dict(meta, budget=budget)
            self.assertEqual(ac.validate_ticket(m, body), [], budget)

    def test_default_ticket_budget_is_runs_only(self):
        self.assertEqual(ac.CONFIG_DEFAULTS["budget"]["ticketDefault"], {"runs": 1})
        self.assertEqual(ac.default_ticket_budget(None), {"runs": 1})
        self.assertEqual(ac.default_ticket_budget({}), {"runs": 1})
        # a home's ticketDefault written before T-0071 still carries max_model: ignored
        cfg = {"budget": {"ticketDefault": {"runs": 2, "max_model": "opus"}}}
        self.assertEqual(ac.default_ticket_budget(cfg), {"runs": 2})
        self.assertEqual(ac.default_ticket_budget({"budget": {"ticketDefault": None}}),
                         {"runs": 1})

    def test_protocol_example_is_valid(self):
        meta, body = ac.read_frontmatter(protocol_example())
        self.assertEqual(ac.validate_ticket(meta, body), [])
        self.assertEqual(list(meta), [k for k in ac.TICKET_KEY_ORDER if k in meta])
        th = ac.thread_lines(body)
        self.assertEqual(len(th), 3)
        self.assertEqual(th[2][1], "expert@main/review-chair")
        self.assertIn("\nRun A dispatched", th[2][2])

    def test_validate_catches(self):
        meta, body = ac.read_frontmatter(protocol_example())
        cases = [
            ({"status": "blocked"}, "needs waiting_on"),
            ({"waiting_on": ["T-0001"]}, "waiting_on must be empty"),
            ({"status": "delivered"}, "needs result"),
            ({"kind": "chat"}, "kind"),
            ({"to": "bob"}, "to must be"),
            ({"id": "T-7"}, "id must look like"),
            ({"priority": "urgent"}, "priority"),
            ({"budget": {"runs": 0, "max_model": "opus"}}, "budget.runs"),
            ({"budget": {"runs": 1, "max_model": "gpt"}}, "budget.max_model"),
            ({"budget": "lots"}, "budget must be"),
            ({"extra": 1}, "unknown field extra"),
            ({"created": "27/09/2026"}, "created"),
            ({"parent": "P-0001"}, "parent"),
            ({"blocks": ["x"]}, "blocks entry"),
            ({"packets": ["T-0001"]}, "packets entry"),
            ({"refs": "paper:x"}, "refs must be a list"),
            ({"ask": ""}, "missing ask"),
        ]
        for patch, needle in cases:
            m = dict(meta)
            m.update(patch)
            probs = ac.validate_ticket(m, body)
            self.assertTrue(any(needle in p for p in probs), (patch, probs))
        self.assertIn("missing '## Thread' section",
                      ac.validate_ticket(meta, "## Ask\n\nx\n"))
        probs = ac.validate_ticket(meta, body + "- 2026-09-28 Bob Smith: hi\n")
        self.assertTrue(any("malformed thread line" in p for p in probs))
        probs = ac.validate_ticket(meta, body + "- 2026-09-28 bob: hi\n")
        self.assertTrue(any("bad speaker" in p for p in probs))

    def test_transitions(self):
        ok = lambda o, n, p, h=False: ac.can_transition(o, n, p, h)[0]  # noqa: E731
        self.assertTrue(ok("open", "accepted", {"receiver"}))
        self.assertFalse(ok("open", "accepted", {"sender"}))
        self.assertTrue(ok("open", "cancelled", {"sender"}))
        self.assertFalse(ok("open", "cancelled", {"receiver"}))
        self.assertTrue(ok("delivered", "closed", {"sender"}))
        self.assertFalse(ok("delivered", "closed", {"receiver"}))
        self.assertTrue(ok("delivered", "in-progress", {"sender"}))
        self.assertFalse(ok("open", "delivered", {"receiver", "sender"}))
        self.assertFalse(ok("closed", "open", {"sender", "receiver"}))
        self.assertTrue(ok("closed", "open", set(), True))
        self.assertTrue(ok("open", "delivered", set(), True))
        self.assertFalse(ok("open", "done", set(), True))
        self.assertTrue(ok("open", "open", set()))
        for term in ac.TERMINAL:
            self.assertFalse(any(o == term for o, _ in ac.TRANSITIONS))

    def test_parties_and_fields(self):
        meta = {"from": "author@main", "to": "expert@main"}
        self.assertEqual(ac.parties(meta, "author@main"), {"sender"})
        self.assertEqual(ac.parties(meta, "expert@main"), {"receiver"})
        self.assertEqual(ac.parties(meta, "scientist@main"), set())
        self.assertEqual(ac.parties({"from": "a@x", "to": "a@x"}, "a@x"),
                         {"sender", "receiver"})
        self.assertIn("ask", ac.editable_fields({"sender"}))
        self.assertNotIn("result", ac.editable_fields({"sender"}))
        self.assertIn("result", ac.editable_fields({"receiver"}))
        self.assertNotIn("to", ac.editable_fields({"sender", "receiver"}))
        self.assertIn("to", ac.editable_fields(set(), human=True))

    def test_slug_and_names(self):
        self.assertEqual(ac.slugify("Check Lemma 4.2 — really?"), "check-lemma-4-2-really")
        self.assertEqual(ac.slugify("!!!"), "ticket")
        self.assertEqual(len(ac.slugify("x" * 100)), 40)
        self.assertFalse(ac.slugify("a" * 39 + " b").endswith("-"))
        self.assertEqual(ac.ticket_filename("T-0007", "Hi there"), "T-0007-hi-there.md")
        self.assertEqual(ac.packet_filename("P-0001", ""), "P-0001-packet.md")
        self.assertEqual(ac.format_who("human", "concierge"), "human")
        self.assertEqual(ac.format_who("author@main", "math-writer"), "author@main/math-writer")
        self.assertEqual(ac.format_who("author@main"), "author@main")

    def test_find(self):
        p = self.write("expert@main/T-0007-check.md", "x")
        self.write("expert@main/T-00070-other.md", "x")
        q = self.write("packets/author@main/P-0003-z.md", "x")
        self.assertEqual(os.path.normcase(ac.find_ticket(self.tmp, "T-0007")),
                         os.path.normcase(p))
        self.assertEqual(os.path.normcase(ac.find_packet(self.tmp, "P-0003")),
                         os.path.normcase(q))
        self.assertIsNone(ac.find_ticket(self.tmp, "T-0008"))

    def test_new_ticket_and_thread(self):
        meta = {"updated": "2026-09-27", "id": "T-0001", "title": "Test a generalization",
                "kind": "test", "from": "researcher@alpha", "to": "scientist@main",
                "status": "open", "priority": "normal",
                "ask": "Test s1:G-3 on its falsifier first.",
                "deliverable": "An experiment report packet.",
                "refs": ["s1:G-3", "lab:ew-check"], "parent": "T-0000",
                "budget": {"runs": 1, "max_model": "sonnet"}, "created": "2026-09-27"}
        text = ac.new_ticket(meta)
        m, body = ac.read_frontmatter(text)
        self.assertEqual(list(m)[0], "id")
        self.assertEqual(ac.validate_ticket(m, body), [])
        self.assertEqual(ac.thread_lines(body), [])
        b1 = ac.append_thread(body, "researcher@alpha/prover", "opened", "2026-09-27")
        b2 = ac.append_thread(b1, "scientist@main/experimenter", "status open -> accepted\n"
                              "falsifier first", "2026-09-28")
        self.assertEqual(ac.thread_lines(b2), [
            ("2026-09-27", "researcher@alpha/prover", "opened"),
            ("2026-09-28", "scientist@main/experimenter",
             "status open -> accepted\nfalsifier first")])
        self.assertIn("\n  falsifier first\n", b2)
        self.assertTrue(b2.endswith("\n"))
        self.assertEqual(ac.validate_ticket(m, b2), [])
        self.assertTrue(ac.thread_is_append_only(b1, b2))
        self.assertFalse(ac.thread_is_append_only(b2, b1))
        tampered = b2.replace("opened", "edited")
        self.assertFalse(ac.thread_is_append_only(b2, tampered))
        with self.assertRaises(ac.AcademyError):
            ac.append_thread(body, "Bob Smith", "x")

    def test_append_thread_creates_section_and_keeps_later_sections(self):
        b = ac.append_thread("## Ask\n\nx\n", "human", "hello", "2026-09-27")
        self.assertTrue(b.endswith("## Thread\n\n- 2026-09-27 human: hello\n"))
        weird = "## Thread\n\n- 2026-09-27 human: a\n\n## Later\n\ntext\n"
        out = ac.append_thread(weird, "human", "b", "2026-09-28")
        self.assertIn("- 2026-09-27 human: a\n- 2026-09-28 human: b\n\n## Later", out)


# ---------------------------------------------------------------------------
# Packets
# ---------------------------------------------------------------------------

def packet_doc_example():
    text = read(os.path.join(REPO, "docs", "packet-template.md"))
    blocks = [b for b in fenced(text, "markdown") if b.startswith("---\npacket: P-0012")]
    assert len(blocks) == 1
    return blocks[0]


class PacketTests(unittest.TestCase):
    def test_template_shape(self):
        meta, body = ac.read_frontmatter(read(os.path.join(PLUGIN, "templates", "packet.md")))
        self.assertEqual(tuple(meta), ac.PACKET_KEY_ORDER)
        heads = [ln for ln in body.split("\n") if ln.startswith("## ")]
        self.assertEqual(tuple(heads), ac.PACKET_SECTIONS)
        probs = ac.validate_packet(meta, body)
        # the template's placeholders are the only problems
        self.assertEqual([p for p in probs if "packet must" not in p], [])

    def test_doc_example_valid_and_decided(self):
        meta, body = ac.read_frontmatter(packet_doc_example())
        self.assertEqual(ac.validate_packet(meta, body), [])
        asked = ac.packet_decisions(body)
        self.assertEqual(list(asked), [1])
        self.assertEqual(sorted(asked[1]["options"]), ["a", "b"])
        self.assertTrue(asked[1]["recommendation"].startswith("(a)"))
        self.assertEqual(ac.packet_answers(body)[1][0], "(a)")
        self.assertTrue(ac.packet_is_decided(body))

    def test_record_decision(self):
        meta, body = ac.read_frontmatter(packet_doc_example())
        body = body.split("## Decision\n")[0] + "## Decision\n"
        self.assertFalse(ac.packet_is_decided(body))
        b1 = ac.record_decision(body, 1, "b", "wait for 1.3", date="2026-09-29")
        self.assertIn("- D1: (b) | 2026-09-29 | human | wait for 1.3\n", b1)
        self.assertTrue(ac.packet_is_decided(b1))
        b2 = ac.record_decision(b1, 1, "other", "ask Barak", date="2026-09-30")
        self.assertEqual(ac.packet_answers(b2)[1], ("other", "2026-09-30", "human",
                                                    "ask Barak"))
        self.assertEqual(ac.validate_packet(meta, b2), [])
        for bad in ((1, "e", ""), (1, "other", " "), (1, "ack", ""), (0, "a", "")):
            with self.assertRaises(ac.AcademyError):
                ac.record_decision(body, *bad)

    def test_informational_packet(self):
        meta, body = ac.read_frontmatter(packet_doc_example())
        head, rest = body.split("## Decisions needed\n")
        tail = rest[rest.index("## Machine notes"):]
        info = head + "## Decisions needed\n\nNone.\n\n" + tail.split("## Decision\n")[0] \
            + "## Decision\n"
        self.assertEqual(ac.validate_packet(meta, info), [])
        self.assertFalse(ac.packet_is_decided(info))
        acked = ac.record_decision(info, 0, "ack", date="2026-09-29")
        self.assertIn("- D0: ack | 2026-09-29 | human\n", acked)
        self.assertTrue(ac.packet_is_decided(acked))

    def test_validate_packet_catches(self):
        meta, body = ac.read_frontmatter(packet_doc_example())
        for patch, needle in (({"kind": "memo"}, "kind"), ({"state": "done"}, "state"),
                              ({"status_proposed": "true"}, "status_proposed"),
                              ({"ticket": "P-1"}, "ticket"), ({"by": "Roey"}, "by"),
                              ({"instance": "human"}, "instance"),
                              ({"extra": 1}, "unknown field")):
            m = dict(meta)
            m.update(patch)
            self.assertTrue(any(needle in p for p in ac.validate_packet(m, body)), patch)
        cases = [
            (body.replace("## Evidence", "## Proof"), "missing section '## Evidence'"),
            (body.replace("## Summary\n", "## Summary\n\n1\n2\n3\n"), "more than three"),
            (body.replace("### D1.", "### D2."), "without gaps"),
            (body.replace("- (b) Wait", "- Wait"), "2-4 options"),
            (body.replace("- Recommendation:", "- Rec:"), "Recommendation"),
            (body.replace("- D1: (a) |", "- D1: yes |"), "malformed decision line"),
            (body + "\n## Appendix\n", "extra sections"),
            (body.replace("## Decisions needed\n", "## Decisions needed\n\nmaybe\n", 1)
             .replace("### D1.", "#### D1."), "'None.' or D1"),
        ]
        for text, needle in cases:
            probs = ac.validate_packet(meta, text)
            self.assertTrue(any(needle in p for p in probs), (needle, probs))
        extra = body.replace("## Decisions needed", "## Conclusion\n\nsupports\n\n"
                             "## Decisions needed")
        self.assertEqual(ac.validate_packet(meta, extra), [])


# ---------------------------------------------------------------------------
# Hook I/O
# ---------------------------------------------------------------------------

class HookIOTests(unittest.TestCase):
    def test_read_event(self):
        self.assertEqual(ac.read_event(io.StringIO('{"cwd": "x"}')), {"cwd": "x"})
        self.assertEqual(ac.read_event(io.StringIO("")), {})
        self.assertEqual(ac.read_event(io.StringIO("[1]")), {})
        self.assertEqual(ac.read_event(io.StringIO("{oops")), {})
        self.assertEqual(ac.read_event(io.BytesIO(b'{"a": 1}')), {"a": 1})

    def test_emitters(self):
        out = io.StringIO()
        self.assertEqual(ac.emit_permission("deny", "no", out), 0)
        self.assertEqual(json.loads(out.getvalue()), {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "no"}})
        out = io.StringIO()
        ac.emit_permission("allow", stream=out)
        self.assertNotIn("permissionDecisionReason", out.getvalue())
        with self.assertRaises(ValueError):
            ac.emit_permission("maybe")
        out = io.StringIO()
        ac.emit_context("SessionStart", "3 tickets", out)
        self.assertEqual(json.loads(out.getvalue())["hookSpecificOutput"],
                         {"hookEventName": "SessionStart", "additionalContext": "3 tickets"})
        out = io.StringIO()
        ac.emit_block("build failed", out)
        self.assertEqual(json.loads(out.getvalue()), {"decision": "block",
                                                      "reason": "build failed"})

    def test_event_accessors(self):
        ev = {"tool_name": "mcp__academy__tickets_create",
              "tool_input": {"file_path": "a.tex", "command": "git commit -m x"}}
        self.assertEqual(ac.tool_name(ev), "mcp__academy__tickets_create")
        self.assertEqual(ac.mcp_tool(ev), "tickets_create")
        self.assertEqual(ac.mcp_tool({"tool_name": "mcp__plugin_academy_academy__claims_new"}),
                         "claims_new")
        self.assertEqual(ac.mcp_tool({"tool_name": "mcp__other__claims_new"}), "")
        self.assertEqual(ac.mcp_tool({"tool_name": "Bash"}), "")
        self.assertEqual(ac.edited_path(ev), "a.tex")
        self.assertEqual(ac.edited_path({"tool_input": {"notebook_path": "n.ipynb"}}),
                         "n.ipynb")
        self.assertIsNone(ac.edited_path({"tool_input": "x"}))
        self.assertEqual(ac.shell_command(ev), "git commit -m x")
        self.assertEqual(ac.shell_command({}), "")
        self.assertEqual(ac.event_cwd({"cwd": "/definitely/not/here"}), os.getcwd())

    def test_is_git_commit(self):
        yes = ["git commit -m x", "cd a && git -C . commit", "git.exe commit -m x",
               "& git commit -m 'x'", "Set-Location x; git commit -F msg.txt",
               "git add .\ngit commit -m y", "git log --grep commit"]
        no = ["git status", "echo commit", "git add . ; echo commit", "gitk", ""]
        for c in yes:
            self.assertTrue(ac.is_git_commit(c), c)
        for c in no:
            self.assertFalse(ac.is_git_commit(c), c)



class ShellParserTests(unittest.TestCase):
    """The shared commit-target parser (author and scientist gates vendor it)."""
    base = r"C:\Work\Math\paper" if os.name == "nt" else "/work/paper"

    def t(self, cmd):
        return [os.path.normcase(d) for d in ac.commit_targets_or_cwd(cmd, self.base)]

    def at(self, *parts):
        return os.path.normcase(os.path.normpath(os.path.join(self.base, *parts)))

    def test_cd_git_C_and_work_tree(self):
        self.assertEqual(self.t("cd ../lab && git commit -m x"), [self.at("..", "lab")])
        self.assertEqual(self.t("git -C ../lab commit"), [self.at("..", "lab")])
        self.assertEqual(self.t("git --work-tree=../lab commit"), [self.at("..", "lab")])

    @unittest.skipUnless(os.name == "nt", "Git Bash drive paths are a Windows form")
    def test_git_bash_drive(self):
        self.assertEqual(self.t("cd /c/Work/Math/SciLab && git commit -m x"),
                         [os.path.normcase(r"C:\Work\Math\SciLab")])

    def test_heredoc_and_nested_shell(self):
        self.assertEqual(self.t("git commit -F - <<EOF\ncd x\ngit commit\nEOF"),
                         [self.at()])
        self.assertEqual(self.t('bash -c "cd ../lab && git commit"'), [self.at("..", "lab")])

    def test_parse_failure_falls_back(self):
        with self.assertRaises(ac.ShellParseFailure):
            ac.commit_targets('git commit -m "x', self.base)
        self.assertEqual(self.t('git commit -m "x'), [self.at()])
        self.assertEqual(self.t('echo "x'), [])


EDGE_PERMS = {
    "roster": {}, "tools": {},
    "tickets": {"edges": {
        "chain": ["author", "expert", "researcher", "scientist"],
        "maxHops": 3,
        "liaisons": {
            "author->expert": ["main", "math-writer", "notation-auditor", "figure-maker"],
            "expert->author": ["librarian", "review-chair", "research-intake", "paper-liaison"],
            "expert->researcher": ["research-intake", "review-chair"],
            "researcher->expert": ["main", "lead-researcher", "prover", "lit-request"],
            "researcher->scientist": ["main", "lead-researcher", "experiment-spec"],
            "scientist->researcher": ["main", "experimenter"]},
        "exempt": ["claim-keeper", "usage-analyst", "concierge"]}}}


class TicketEdgeTests(unittest.TestCase):
    def ok(self, frm, to, agent, **kw):
        return ac.ticket_edge_allowed(frm, to, agent, EDGE_PERMS, **kw)[0]

    def test_human_either_end(self):
        self.assertTrue(self.ok("human", "scientist@main", ""))
        self.assertTrue(self.ok("author@main", "human", "math-writer"))

    def test_same_role(self):
        self.assertTrue(self.ok("researcher@a", "researcher@b", "prover"))
        self.assertTrue(self.ok("expert@main", "expert@main", "clerk"))

    def test_neighbour_needs_liaison(self):
        self.assertTrue(self.ok("author@main", "expert@main", "math-writer"))
        self.assertTrue(self.ok("author@main", "expert@main", "main"))
        self.assertFalse(self.ok("author@main", "expert@main", "tex-engineer"))
        self.assertTrue(self.ok("researcher@s1", "scientist@main", "lead-researcher"))
        self.assertFalse(self.ok("researcher@s1", "scientist@main", "prover"))

    def test_directions_differ(self):
        self.assertTrue(self.ok("expert@main", "researcher@s1", "research-intake"))
        self.assertFalse(self.ok("expert@main", "researcher@s1", "paper-liaison"))
        self.assertTrue(self.ok("expert@main", "author@main", "paper-liaison"))

    def test_non_neighbour_refused_with_next_hop(self):
        ok, why = ac.ticket_edge_allowed("author@main", "researcher@s1", "main", EDGE_PERMS)
        self.assertFalse(ok)
        self.assertIn("expert", why)
        self.assertIn("final_to researcher", why)
        ok, why = ac.ticket_edge_allowed("scientist@main", "author@main", "main", EDGE_PERMS)
        self.assertFalse(ok)
        self.assertIn("researcher", why)

    def test_non_neighbour_refusal_names_the_relay(self):
        cases = {("author@main", "researcher@s1"): "research-intake",
                 ("author@main", "scientist@main"): "research-intake",
                 ("expert@main", "scientist@main"): "experiment-spec",
                 ("scientist@main", "expert@main"): "lit-request",
                 ("scientist@main", "author@main"): "lit-request",
                 ("researcher@s1", "author@main"): "paper-liaison"}
        for (frm, to), relay in cases.items():
            ok, why = ac.ticket_edge_allowed(frm, to, "main", EDGE_PERMS)
            self.assertFalse(ok)
            self.assertIn("%s relays it" % relay, why, (frm, to))

    def test_exempt_and_clerical(self):
        self.assertTrue(self.ok("author@main", "researcher@s1", "claim-keeper"))
        self.assertTrue(self.ok("author@main", "researcher@s1", "math-editor", clerical=True))

    def test_final_to_must_lie_beyond_to(self):
        self.assertTrue(self.ok("author@main", "expert@main", "main", final_to="researcher"))
        self.assertTrue(self.ok("author@main", "expert@main", "main", final_to="scientist"))
        self.assertFalse(self.ok("author@main", "expert@main", "main", final_to="author"))
        self.assertFalse(self.ok("author@main", "expert@main", "main", final_to="nobody"))
        self.assertTrue(self.ok("scientist@main", "researcher@s1", "main", final_to="author"))
        self.assertTrue(self.ok("human", "expert@main", "", final_to="researcher"))

    def test_hop_limit(self):
        self.assertTrue(self.ok("researcher@s1", "scientist@main", "experiment-spec",
                                final_to="scientist", depth=2))
        self.assertFalse(self.ok("researcher@s1", "scientist@main", "experiment-spec",
                                 final_to="scientist", depth=3))

    def test_role_of(self):
        ws = {"instances": {"lab@x": {"role": "scientist"}}}
        self.assertEqual(ac.role_of("author@main"), "author")
        self.assertEqual(ac.role_of("lab@x", ws), "scientist")
        self.assertIsNone(ac.role_of("human"))

    def test_defaults_without_edges_block(self):
        e = ac.ticket_edges({"roster": {}, "tools": {}})
        self.assertEqual(e["chain"], list(ac.CHAIN_DEFAULT))
        self.assertEqual(e["maxHops"], 3)

    def test_final_to_field_validated(self):
        meta = {"id": "T-0001", "title": "t", "kind": "research", "from": "author@main",
                "to": "expert@main", "status": "open", "ask": "a", "deliverable": "d",
                "priority": "normal", "budget": {"runs": 1, "max_model": "sonnet"},
                "created": "2026-09-28", "updated": "2026-09-28", "final_to": "researcher"}
        self.assertEqual(ac.validate_ticket(meta), [])
        meta["final_to"] = "nowhere"
        self.assertTrue(any("final_to" in p for p in ac.validate_ticket(meta)))
        meta["final_to"] = "researcher"
        meta["kind"] = "note"
        self.assertEqual(ac.validate_ticket(meta), [])

    def _blocked(self, **extra):
        meta = {"id": "T-0001", "title": "t", "kind": "prove", "from": "author@main",
                "to": "expert@main", "status": "blocked", "ask": "a", "deliverable": "d",
                "priority": "normal", "budget": {"runs": 1, "max_model": "sonnet"},
                "created": "2026-09-29", "updated": "2026-09-29"}
        meta.update(extra)
        return meta

    def test_blocked_needs_one_of_the_two_kinds(self):
        self.assertTrue(ac.validate_ticket(self._blocked()))                 # neither
        self.assertEqual(ac.validate_ticket(self._blocked(waiting_on=["human"])), [])
        self.assertTrue(ac.validate_ticket(self._blocked(blocked_by="T-0009")))
        self.assertTrue(ac.validate_ticket(self._blocked(reopen_if="new")))  # dead-route half
        self.assertEqual(ac.validate_ticket(
            self._blocked(blocked_by="T-0009", reopen_if="a new construction")), [])

    def test_both_kinds_at_once_is_an_error(self):
        probs = ac.validate_ticket(self._blocked(
            waiting_on=["human"], blocked_by="T-0009", reopen_if="new"))
        self.assertTrue(any("both" in p for p in probs))

    def test_dead_route_needs_a_tried_thread_line(self):
        meta = self._blocked(blocked_by="T-0009", reopen_if="new")
        head = "## Ask\n\nx\n\n## Thread\n\n- 2026-09-29 expert@main: opened\n"
        self.assertTrue(any("tried" in p for p in ac.validate_ticket(meta, head)))
        ok = head + "- 2026-09-29 expert@main: tried: the induction, circular\n"
        self.assertEqual(ac.validate_ticket(meta, ok), [])

    def test_dead_route_fields_only_on_blocked_and_one_line(self):
        meta = self._blocked(blocked_by="T-0009", reopen_if="new")
        meta["status"] = "accepted"
        self.assertTrue(ac.validate_ticket(meta))
        meta = self._blocked(blocked_by="T-0009", reopen_if="two\nlines")
        self.assertTrue(ac.validate_ticket(meta))

    def test_new_fields_are_receiver_writable_and_ordered(self):
        for f in ("blocked_by", "reopen_if"):
            self.assertIn(f, ac.TICKET_FIELDS["receiver"])
            self.assertIn(f, ac.TICKET_KEY_ORDER)

    def test_hop_limit_counts_only_relay_ancestors(self):
        board = tempfile.mkdtemp(prefix="edges-")
        def put(tid, parent, final_to):
            meta = {"id": tid, "title": "t", "kind": "other", "from": "author@main",
                    "to": "expert@main", "status": "open", "ask": "a", "deliverable": "d",
                    "priority": "normal", "budget": {"runs": 1, "max_model": "sonnet"},
                    "created": "2026-09-28", "updated": "2026-09-28",
                    "parent": parent, "final_to": final_to}
            os.makedirs(os.path.join(board, "expert@main"), exist_ok=True)
            ac.atomic_write(os.path.join(board, "expert@main", ac.ticket_filename(tid, "t")),
                            ac.new_ticket(meta))
        put("T-0001", None, "scientist")
        put("T-0002", "T-0001", "scientist")
        put("T-0003", "T-0002", "scientist")
        put("T-0004", "T-0003", None)          # the experiment's own ticket, no final_to
        self.assertEqual(ac.relay_depth(board, "T-0003"), 3)
        self.assertEqual(ac.relay_depth(board, "T-0004"), 0)
        self.assertEqual(ac.relay_depth(board, None), 0)

    def test_relay_return_ready(self):
        parent = {"id": "T-0001", "to": "expert@main", "status": "blocked",
                  "final_to": "researcher", "waiting_on": ["T-0002"]}
        st = {"T-0002": "delivered"}.get
        self.assertTrue(ac.relay_return_ready(parent, st))
        self.assertTrue(ac.relay_return_ready(parent, {"T-0002": "closed"}.get))
        self.assertFalse(ac.relay_return_ready(parent, {"T-0002": "open"}.get))
        self.assertFalse(ac.relay_return_ready(parent, {}.get))         # child not found
        self.assertFalse(ac.relay_return_ready(dict(parent, waiting_on=["T-0002", "human"]),
                                               st))
        self.assertFalse(ac.relay_return_ready(dict(parent, waiting_on=[]), st))
        self.assertFalse(ac.relay_return_ready(dict(parent, status="open"), st))
        self.assertFalse(ac.relay_return_ready(dict(parent, final_to=None), st))
        self.assertFalse(ac.relay_return_ready(dict(parent, final_to="expert"), st))
        self.assertTrue(ac.relay_return_ready(dict(parent, final_to="researcher@s1"), st))
        research = dict(parent, kind="research", final_to=None)   # read as researcher
        self.assertTrue(ac.relay_return_ready(research, st))
        self.assertTrue(ac.relay_return_ready(dict(research, final_to="expert"), st))
        self.assertFalse(ac.relay_return_ready(dict(research, to="researcher@s1"), st))


if __name__ == "__main__":
    unittest.main()


class ResolveWorkspaceEnvTests(unittest.TestCase):
    """Several workspaces on one machine: the machine-wide variables are tagged."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.none = os.path.join(self.tmp, "no-such-environment-file")

    def tagged(self, tag, root):
        return {"ACADEMY_WS__%s__WORKSPACE" % tag: root + "/workspace.json",
                "ACADEMY_WS__%s__BOARD" % tag: root + "-board",
                "ACADEMY_WS__%s__HOME_AUTHOR_X" % tag: root + "-paper",
                "ACADEMY_WS__%s__ROOT" % tag: "/opt/academy"}

    def resolve(self, env, cwd, etc=None):
        tag = ac.resolve_workspace_env(env, etc or self.none, cwd)
        return tag, env

    def test_only_workspace_is_used_from_anywhere(self):
        tag, env = self.resolve(self.tagged("A", "/w/a"), "/somewhere/else")
        self.assertEqual(tag, "A")
        self.assertEqual(env["ACADEMY_WORKSPACE"], "/w/a/workspace.json")
        self.assertEqual(env["ACADEMY_HOME_AUTHOR_X"], "/w/a-paper")
        self.assertEqual(env["ACADEMY_ROOT"], "/opt/academy")

    def test_two_workspaces_chosen_by_directory(self):
        base = dict(self.tagged("A", "/w/a"), **self.tagged("B", "/w/b"))
        tag, env = self.resolve(dict(base), "/w/b-paper/sub")
        self.assertEqual((tag, env["ACADEMY_WORKSPACE"]), ("B", "/w/b/workspace.json"))
        tag, env = self.resolve(dict(base), "/w/a")
        self.assertEqual(tag, "A")

    def test_two_workspaces_ambiguous_outside_both(self):
        base = dict(self.tagged("A", "/w/a"), **self.tagged("B", "/w/b"))
        tag, env = self.resolve(base, "/elsewhere")
        self.assertIsNone(tag)
        self.assertNotIn("ACADEMY_WORKSPACE", env)
        self.assertEqual(ac.WORKSPACE_TAGS, ["A", "B"])

    def test_explicit_tag_wins(self):
        base = dict(self.tagged("A", "/w/a"), **self.tagged("B", "/w/b"),
                    ACADEMY_WORKSPACE_TAG="A")
        tag, env = self.resolve(base, "/w/b")
        self.assertEqual(tag, "A")

    def test_unprefixed_set_is_left_alone(self):
        env = dict(self.tagged("A", "/w/a"), ACADEMY_WORKSPACE="/mine/workspace.json")
        tag, env = self.resolve(env, "/w/a")
        self.assertIsNone(tag)
        self.assertEqual(env["ACADEMY_WORKSPACE"], "/mine/workspace.json")
        self.assertNotIn("ACADEMY_BOARD", env)

    def test_reads_etc_environment_and_process_env_wins(self):
        etc = os.path.join(self.tmp, "environment")
        with open(etc, "w") as fh:
            fh.write("".join('%s="%s"\n' % kv for kv in self.tagged("A", "/w/a").items()))
        env = {"ACADEMY_ROOT": "/mine"}
        tag, env = self.resolve(env, "/x", etc)
        self.assertEqual(tag, "A")
        self.assertEqual(env["ACADEMY_ROOT"], "/mine")
        self.assertEqual(env["ACADEMY_BOARD"], "/w/a-board")
