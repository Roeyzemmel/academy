"""The plugin's shape: agent frontmatter per plan section 3.3, the grader rule, hooks,
skills, the vendored lib, and no domain mathematics in the role plugin."""

import json
import os
import re
import unittest

from _fixtures import PLUGIN, REPO, SCRIPTS
import _academy as ac  # noqa: E402

AGENTS = {
    # name: (model, fallback, readonly)
    "lead-researcher": ("sonnet", "opus", False),
    "prover": ("fable", "opus", False),
    "experiment-reviewer": ("fable", "opus", True),
    "claim-keeper": ("haiku", "sonnet", False),
    "experiment-spec": ("sonnet", "opus", False),
    "lit-request": ("haiku", "sonnet", False),
}
SKILLS = ("explore", "campaign", "prove", "corollaries", "generalize", "claims", "review-experiment",
          "settle", "inbox", "status")
SHELL_AND_WRITE = {"Bash", "PowerShell", "Write", "Edit", "MultiEdit", "NotebookEdit"}
#: words that would mean domain mathematics leaked into the role plugin
DOMAIN_WORDS = ("translation surface", "origami", "flatsurf", "sage", "veech", "saddle",
                "billiard", "wollmilchsau", "christoffel", "stratum", "surface_dynamics",
                "lingo", "slope1", "kb.py")


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


class PluginTests(unittest.TestCase):
    def test_manifest(self):
        with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["name"], "researcher")

    def test_agents(self):
        perms = ac.load_permissions(os.path.join(REPO, "academy", "permissions.json"))
        roster = set(perms["roster"]["researcher"])
        files = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(PLUGIN, "agents"))}
        self.assertEqual(files, set(AGENTS))
        self.assertEqual(roster, set(AGENTS))
        for name, (model, fallback, readonly) in AGENTS.items():
            with self.subTest(agent=name):
                fm, _ = frontmatter(os.path.join(PLUGIN, "agents", name + ".md"))
                self.assertEqual(fm["name"], name)
                self.assertEqual((fm["model"], fm["fallback"]), (model, fallback))
                self.assertTrue(fm.get("effort"))
                self.assertIn("Use ", fm["description"])
                tools = {t.strip() for t in fm["tools"].split(",")}
                self.assertIn("academy:", fm.get("skills", ""))
                if readonly:
                    self.assertFalse(tools & SHELL_AND_WRITE, tools & SHELL_AND_WRITE)
                    self.assertFalse([t for t in tools if re.search(
                        r"__(claims_(new|attach_evidence|propose_status|set_status)|"
                        r"tickets_(create|update)|packets_(create|decide)|queue_add)$", t)])
                    self.assertIn(name, perms["groups"]["readonly"])
                else:
                    self.assertTrue(fm.get("maxTurns"))
        self.assertEqual(frontmatter(os.path.join(PLUGIN, "agents",
                                                  "experiment-reviewer.md"))[0]["effort"], "xhigh")

    def test_only_claim_keeper_may_set_status(self):
        for name in AGENTS:
            fm, _ = frontmatter(os.path.join(PLUGIN, "agents", name + ".md"))
            has = "claims_set_status" in fm["tools"]
            self.assertEqual(has, name == "claim-keeper", name)
        fm, _ = frontmatter(os.path.join(PLUGIN, "agents", "claim-keeper.md"))
        self.assertFalse({t.strip() for t in fm["tools"].split(",")} & SHELL_AND_WRITE)

    def test_mcp_tool_names_exist_on_the_server(self):
        names = set()
        tools_dir = os.path.join(REPO, "academy", "mcp", "tools")
        for f in os.listdir(tools_dir):
            if f.endswith(".py"):
                with open(os.path.join(tools_dir, f), encoding="utf-8") as fh:
                    names.update(re.findall(r'Tool\("([a-z_]+)"', fh.read()))
        self.assertTrue(names)
        for name in AGENTS:
            fm, _ = frontmatter(os.path.join(PLUGIN, "agents", name + ".md"))
            for t in fm["tools"].split(","):
                t = t.strip()
                if t.startswith("mcp__"):
                    with self.subTest(agent=name, tool=t):
                        self.assertIn(t.rsplit("__", 1)[1], names)

    def test_skills(self):
        found = sorted(os.listdir(os.path.join(PLUGIN, "skills")))
        self.assertEqual(sorted(SKILLS), found)
        for s in SKILLS:
            with self.subTest(skill=s):
                fm, text = frontmatter(os.path.join(PLUGIN, "skills", s, "SKILL.md"))
                self.assertEqual(fm["name"], s)
                self.assertIn("Use ", fm["description"])
                self.assertLess(len(text.split("\n")), 120, "a SKILL.md stays a thin orchestrator")
        self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "skills", "review-experiment",
                                                    "checklist.md")))

    def campaign_text(self):
        out = []
        for rel in (("skills", "campaign", "SKILL.md"), ("references", "campaign-dispatch.md")):
            with open(os.path.join(PLUGIN, *rel), encoding="utf-8") as fh:
                out.append(fh.read())
        return out

    def test_campaign_skill_states_its_caps_and_serial_dispatch(self):
        skill, ref = self.campaign_text()
        for flag in ("--rounds", "--agents", "--runs"):
            self.assertIn(flag, skill)
        self.assertRegex(skill, r"K = 0 if omitted")
        self.assertRegex(skill, r"(?i)forced to\s+0")
        self.assertRegex(skill, r"(?i)serial")
        self.assertRegex(skill, r"(?i)one subagent at a time")
        self.assertIn("references/campaign-dispatch.md", skill)
        self.assertRegex(ref, r"(?i)strictly one subagent at a time")
        self.assertIn("--campaign", ref)
        self.assertIn("--campaign", skill)

    def test_campaign_names_no_agent_outside_the_existing_set(self):
        others = set()
        for role in ("academy", "author", "expert", "scientist"):
            d = os.path.join(REPO, role, "agents")
            others |= {os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith(".md")}
        others -= set(AGENTS)
        for text in self.campaign_text():
            for name in others:
                self.assertNotRegex(text, r"\b%s\b" % re.escape(name), name)
            # every agent-shaped backticked name is one of the researcher's own
            for name in re.findall(r"`([a-z]+(?:-[a-z]+)+)`", text):
                if name in ("lead-researcher", "prover", "claim-keeper"):
                    continue
                self.assertNotIn(name, others)
        self.assertEqual({f[:-3] for f in os.listdir(os.path.join(PLUGIN, "agents"))},
                         set(AGENTS))

    def test_hooks_point_at_scripts(self):
        with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        self.assertEqual(set(hooks), {"PreToolUse", "PostToolUse", "SubagentStop"})
        for event, groups in hooks.items():
            for g in groups:
                for h in g["hooks"]:
                    m = re.match(r'^py "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([a-z_]+\.py)"$',
                                 h["command"])
                    self.assertTrue(m, h["command"])
                    self.assertTrue(os.path.isfile(os.path.join(SCRIPTS, m.group(1))))

    def test_vendored_lib_is_in_sync(self):
        with open(os.path.join(REPO, "academy", "lib", "academy_common.py"), "rb") as fh:
            lib = fh.read()
        with open(os.path.join(SCRIPTS, "_academy.py"), "rb") as fh:
            self.assertEqual(fh.read(), lib)

    def test_no_domain_mathematics(self):
        hits = []
        for dirpath, dirs, files in os.walk(PLUGIN):
            dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__")]
            for f in files:
                if not f.endswith((".md", ".py", ".json")) or f == "_academy.py":
                    continue
                path = os.path.join(dirpath, f)
                with open(path, encoding="utf-8") as fh:
                    low = fh.read().lower()
                for w in DOMAIN_WORDS:
                    if re.search(r"\b%s\b" % re.escape(w), low):
                        hits.append("%s: %s" % (os.path.relpath(path, PLUGIN), w))
        self.assertEqual(hits, [])

    def test_new_files_are_lf(self):
        for dirpath, dirs, files in os.walk(PLUGIN):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                with open(os.path.join(dirpath, f), "rb") as fh:
                    self.assertNotIn(b"\r\n", fh.read(), os.path.join(dirpath, f))


if __name__ == "__main__":
    unittest.main()
