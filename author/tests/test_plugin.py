"""The Author plugin's shape: manifest, skills (the inbox replaced next), agents, scripts."""

import json
import os
import re
import unittest

from fixtures import PLUGIN, REPO, SCRIPTS
import _academy as ac  # noqa: E402

SKILLS = ("agenda", "audit-notation", "inbox", "next", "notes", "paper-method", "presync",
          "status", "sweep")
AGENTS = ("figure-maker", "math-editor", "math-writer", "notation-auditor", "note-sweeper",
          "tex-engineer")


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


def read(*parts):
    with open(os.path.join(PLUGIN, *parts), encoding="utf-8") as fh:
        return fh.read()


class PluginTests(unittest.TestCase):
    def test_manifest(self):
        with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["name"], "author")

    def test_skills(self):
        self.assertEqual(sorted(SKILLS), sorted(os.listdir(os.path.join(PLUGIN, "skills"))))
        for s in SKILLS:
            with self.subTest(skill=s):
                fm, text = frontmatter(os.path.join(PLUGIN, "skills", s, "SKILL.md"))
                self.assertEqual(fm["name"], s)
                self.assertIn("Use ", fm["description"])
                if s != "paper-method":         # a writing method, not an orchestrator
                    self.assertLess(len(text.split("\n")), 120,
                                    "a SKILL.md stays a thin orchestrator")

    def test_agents_are_the_roster(self):
        with open(os.path.join(REPO, "academy", "permissions.json"), encoding="utf-8") as fh:
            roster = set(json.load(fh)["roster"]["author"])
        files = {os.path.splitext(f)[0] for f in os.listdir(os.path.join(PLUGIN, "agents"))}
        self.assertEqual(files, set(AGENTS))
        self.assertEqual(roster, set(AGENTS))

    def test_next_is_a_one_line_redirect(self):
        _, text = frontmatter(os.path.join(PLUGIN, "skills", "next", "SKILL.md"))
        body = [ln for ln in text.split("---\n", 2)[2].split("\n") if ln.strip()]
        self.assertLessEqual(len(body), 3, body)
        self.assertIn("/author:inbox", text)
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "skills", "next", "references")))

    def test_inbox_skill_states_the_author_flow(self):
        text = read("skills", "inbox", "SKILL.md")
        for needle in ("Sweep first", "note-sweeper", "inbox.py --sync", "self", "--check",
                       "return", "human", "at most `budget.itemsPerRun`"):
            self.assertIn(needle, text, needle)
        self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "skills", "inbox",
                                                    "references", "routing.md")))

    def test_status_points_at_the_inbox(self):
        self.assertIn("/author:inbox --all", read("skills", "status", "SKILL.md"))

    def test_no_stale_next_references(self):
        keep = {os.path.join("skills", "next", "SKILL.md"),
                os.path.join("skills", "inbox", "SKILL.md"),
                os.path.join("skills", "inbox", "references", "routing.md"),
                "README.md"}
        stale = []
        for top in ("skills", "agents", "references", "scripts"):
            for dirpath, _, files in os.walk(os.path.join(PLUGIN, top)):
                for f in files:
                    if not f.endswith((".md", ".py")):
                        continue
                    rel = os.path.relpath(os.path.join(dirpath, f), PLUGIN)
                    if rel in keep:
                        continue
                    with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                        if re.search(r"next\.py|/author:next", fh.read()):
                            stale.append(rel)
        self.assertEqual(stale, [])

    def test_scripts(self):
        for name in ("inbox.py", "routes.py"):
            self.assertTrue(os.path.isfile(os.path.join(SCRIPTS, name)), name)
        self.assertFalse(os.path.exists(os.path.join(SCRIPTS, "next.py")))

    def test_vendored_lib_carries_the_inbox_core(self):
        self.assertTrue(hasattr(ac, "inbox_core"))
        with open(os.path.join(REPO, "academy", "lib", "academy_common.py"), "rb") as fh:
            lib = fh.read()
        with open(os.path.join(SCRIPTS, "_academy.py"), "rb") as fh:
            self.assertEqual(fh.read(), lib)


if __name__ == "__main__":
    unittest.main()
