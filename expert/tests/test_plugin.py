"""The plugin's shape: agent frontmatter (models per plan section 3.4, read-only
graders), skills, hooks, the vendored lib, and the inbox router."""

import json
import os
import re
import unittest

import fixtures
import _academy as ac
import inbox

PLUGIN = fixtures.PLUGIN
LIB = os.path.join(fixtures.REPO, "academy", "lib", "academy_common.py")

# plan section 3.4: model, effort, fallback
PLAN = {
    "clerk": ("haiku", None),
    "librarian": ("sonnet", "opus"),
    "related-work-scout": ("sonnet", "opus"),
    "review-chair": ("sonnet", "opus"),
    "rigor-reviewer": ("fable", "opus"),
    "referee": ("fable", "opus"),
}
EFFORT = {"rigor-reviewer": "xhigh", "referee": "high"}
READ_ONLY = ("clerk", "rigor-reviewer", "referee")
FORBIDDEN = ("Bash", "PowerShell", "Write", "Edit", "MultiEdit", "NotebookEdit")
MCP_WRITES = ("claims_new", "claims_attach_evidence", "claims_propose_status",
              "claims_set_status", "queue_add", "tickets_create", "tickets_update",
              "packets_create", "packets_decide")
SKILLS = ("lookup", "cite", "verify", "litwatch", "referee", "library-index", "domain",
          "inbox", "status")


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, path
    out = {}
    for ln in m.group(1).split("\n"):
        k, _, v = ln.partition(":")
        out[k.strip()] = v.strip()
    return out, text


class AgentTests(unittest.TestCase):
    def agents(self):
        d = os.path.join(PLUGIN, "agents")
        return {f[:-3]: frontmatter(os.path.join(d, f)) for f in os.listdir(d)
                if f.endswith(".md")}

    def test_roster_matches_permissions(self):
        with open(os.path.join(fixtures.REPO, "academy", "permissions.json"),
                  encoding="utf-8") as fh:
            perms = json.load(fh)
        self.assertEqual(sorted(self.agents()), sorted(perms["roster"]["expert"]))
        self.assertEqual(sorted(PLAN), sorted(perms["roster"]["expert"]))

    def test_models_per_plan(self):
        for name, (fm, _text) in self.agents().items():
            model, fallback = PLAN[name]
            self.assertEqual(fm["name"], name)
            self.assertEqual(fm["model"], model, name)
            if fallback:
                self.assertEqual(fm["fallback"], fallback, name)
            if name in EFFORT:
                self.assertEqual(fm["effort"], EFFORT[name], name)
            for key in ("description", "tools", "effort", "fallback", "skills"):
                self.assertTrue(fm.get(key), "%s lacks %s" % (name, key))

    def test_read_only_agents_have_no_shell_or_writes(self):
        agents = self.agents()
        for name in READ_ONLY:
            tools = [t.strip() for t in agents[name][0]["tools"].split(",")]
            for bad in FORBIDDEN:
                self.assertNotIn(bad, tools, "%s must not have %s" % (name, bad))
            for t in tools:
                for w in MCP_WRITES:
                    self.assertFalse(t.endswith("__" + w), "%s has %s" % (name, t))

    def test_clerk_has_no_web(self):
        tools = self.agents()["clerk"][0]["tools"]
        self.assertNotIn("WebFetch", tools)
        self.assertNotIn("WebSearch", tools)

    def test_mcp_tool_names_exist_on_the_server(self):
        import _expert as ex
        names = set()
        for mod in ("claims", "library", "tickets", "packets", "domain", "config", "queue"):
            names |= {t.name for t in ex.mcp_module(mod).TOOLS}
        for name, (fm, _t) in self.agents().items():
            for t in fm["tools"].split(","):
                t = t.strip()
                m = re.match(r"^mcp__(?:plugin_academy_)?academy__(\w+)$", t)
                if t.startswith("mcp__"):
                    self.assertTrue(m, t)
                    self.assertIn(m.group(1), names, "%s: %s" % (name, t))

    def test_verdict_block_documented_in_reviewer(self):
        text = self.agents()["rigor-reviewer"][1]
        for key in ("subject:", "pass:", "run:", "verdict:", "modulo:", "model:",
                    "statement_hash:", "blocking:", "ticket:"):
            self.assertIn(key, text.split("VERDICT")[-1])

    def test_only_skills_that_exist_are_preloaded(self):
        base = os.path.join(fixtures.REPO, "academy", "skills")
        for name, (fm, _t) in self.agents().items():
            for s in re.findall(r"[\w-]+:[\w-]+", fm["skills"]):
                plugin, skill = s.split(":")
                root = base if plugin == "academy" else os.path.join(PLUGIN, "skills")
                self.assertTrue(os.path.isfile(os.path.join(root, skill, "SKILL.md")),
                                "%s preloads missing %s" % (name, s))


class SkillTests(unittest.TestCase):
    def test_skills_present_with_frontmatter(self):
        for s in SKILLS:
            fm, text = frontmatter(os.path.join(PLUGIN, "skills", s, "SKILL.md"))
            self.assertEqual(fm["name"], s)
            self.assertTrue(fm["description"])
        self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "skills", "verify",
                                                    "references", "conclude.md")))

    def test_no_domain_mathematics(self):
        """Role plugins name the pack only through its contract file names."""
        banned = re.compile(r"translation surface|Veech|saddle connection|billiard|"
                            r"illuminat|origami|stratum", re.I)
        for dp, dn, fn in os.walk(PLUGIN):
            if "tests" in dp or "__pycache__" in dp:
                continue
            for f in fn:
                if f.endswith(".md"):
                    with open(os.path.join(dp, f), encoding="utf-8") as fh:
                        hits = banned.findall(fh.read())
                    self.assertEqual(hits, [], os.path.join(dp, f))


class HookConfigTests(unittest.TestCase):
    def test_hooks_reference_existing_scripts(self):
        with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as fh:
            cfg = json.load(fh)
        seen = set()
        for event, groups in cfg["hooks"].items():
            for g in groups:
                for h in g["hooks"]:
                    m = re.match(r'^py "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/(\w+\.py)"$',
                                 h["command"])
                    self.assertTrue(m, h["command"])
                    self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "scripts",
                                                                m.group(1))))
                    seen.add((event, m.group(1)))
        self.assertIn(("SubagentStop", "land_verdict.py"), seen)
        self.assertIn(("SubagentStop", "land_referee.py"), seen)
        self.assertIn(("PostToolUse", "library_edit_check.py"), seen)

    def test_vendored_lib_is_current(self):
        with open(LIB, "rb") as a, open(os.path.join(PLUGIN, "scripts", "_academy.py"),
                                         "rb") as b:
            self.assertEqual(a.read(), b.read(), "run py academy/scripts/sync_common.py")

    def test_new_files_are_lf(self):
        for dp, dn, fn in os.walk(PLUGIN):
            if "__pycache__" in dp:
                continue
            for f in fn:
                if f.endswith((".py", ".md", ".json")):
                    with open(os.path.join(dp, f), "rb") as fh:
                        self.assertNotIn(b"\r\n", fh.read(), os.path.join(dp, f))


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        for i, (kind, status, prio) in enumerate([
                ("verify", "open", "normal"), ("cite", "accepted", "high"),
                ("lookup", "open", "low"), ("prove", "open", "normal"),
                ("referee", "closed", "high"), ("notation", "open", "normal")], 1):
            meta = {"id": "T-%04d" % i, "title": "t%d" % i, "kind": kind,
                    "from": "author@bi", "to": "expert@ts", "status": status,
                    "priority": prio, "ask": "a", "deliverable": "d", "refs": [],
                    "blocks": [], "waiting_on": [],
                    "budget": {"runs": 2, "max_model": "fable"}, "packets": [],
                    "created": "2026-09-28", "updated": "2026-09-28"}
            if status == "closed":
                meta["result"] = "done"
            ac.atomic_write(os.path.join(self.sb.board, "expert@ts", "T-%04d-t.md" % i),
                            ac.new_ticket(meta))

    def tearDown(self):
        self.sb.close()

    def test_plan_orders_limits_and_routes(self):
        res = inbox.plan(self.sb.board, "expert@ts", 3)
        self.assertEqual(res["waiting"], 5)
        self.assertEqual([t["id"] for t in res["take"]], ["T-0002", "T-0001", "T-0004"])
        self.assertEqual(res["take"][0]["route"]["target"], "expert:cite")
        self.assertEqual(res["take"][1]["route"]["target"], "expert:verify")
        self.assertEqual(res["take"][2]["route"]["how"], "reject")
        self.assertIn("researcher", res["take"][2]["route"]["why"])
        self.assertEqual(res["left"], 2)

    def test_cli_caps_at_three(self):
        code, out, err = fixtures.run_script("inbox.py", None, ["--instance", "expert@ts",
                                                                "--limit", "9", "--json"])
        self.assertEqual(code, 0, err)
        self.assertEqual(out["limit"], 3)
        self.assertEqual(len(out["take"]), 3)


if __name__ == "__main__":
    unittest.main()
