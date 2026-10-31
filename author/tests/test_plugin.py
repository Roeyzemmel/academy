"""The Author plugin's shape: manifest, skills (the inbox replaced next), agents, scripts."""

import json
import os
import re
import unittest

from fixtures import PLUGIN, REPO, SCRIPTS
import _academy as ac  # noqa: E402
import routes  # noqa: E402

SKILLS = ("agenda", "audit-notation", "inbox", "next", "notes", "paper-method", "presync",
          "slideshow-maker", "status", "sweep")
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
        """Since 2026-10-31 the inbox rules are academy/workflows/inbox.js; the skill names
        what the workflow does for the Author and what it hands back to the main session."""
        text = read("skills", "inbox", "SKILL.md")
        self.assertIn("workflows/inbox.js", text)
        self.assertIn("note-sweeper", text)
        self.assertIn("no cap", text)
        order = [text.index(x) for x in ("in progress", "**land**", "**released**",
                                         "agenda position")]
        self.assertEqual(order, sorted(order), "the core's order")
        self.assertIn("agenda.py gaps", text)
        for agent in routes.agents():
            self.assertIn("`%s`" % agent, text, agent)
        for how in ("`author:notes`", "`research`", "`human`", "AskUserQuestion",
                    "py $S/inbox.py --check T-NNNN", "check_paper.py",
                    "The sweep counts first"):
            self.assertIn(how, text, how)
        self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "skills", "inbox",
                                                    "references", "routing.md")))

    def test_the_workflow_handles_every_route_kind(self):
        with open(os.path.join(REPO, "academy", "workflows", "inbox.js"), encoding="utf-8") as fh:
            wf = fh.read()
        hows = {h for h, _t, _w in routes.KIND_ROUTES.values()} | {"reject", "human", "research", "skill"}
        for how in hows:
            self.assertIn("rt.how === '%s'" % how, wf, how)
        self.assertIn("row.return", wf)                 # the landing of a returned ticket
        self.assertIn("row.released", wf)               # blocked -> accepted first
        self.assertIn("note-sweeper", wf)

    def test_routing_doc_tables_are_the_generated_ones(self):
        text = read("skills", "inbox", "references", "routing.md")
        for name in routes.BLOCKS:
            self.assertEqual(routes.extract_block(text, name), routes.render_table(name), name)
        self.assertEqual(routes.sync_text(text), text)        # `routes.py --sync` is a no-op

    def test_routes_tables_parse_back_to_the_data(self):
        rows = [ln for ln in routes.render_table("kinds").split("\n")[2:]
                if not ln.startswith("| any other")]
        parsed = {}
        for ln in rows:
            k, how, target, _why = [c.strip(" `") for c in ln.strip("|").split("|")]
            parsed[k] = (how, target)
        self.assertEqual(parsed, {k: (h, t) for k, (h, t, _w) in routes.KIND_ROUTES.items()})
        out = [[c.strip(" `") for c in ln.strip("|").split("|")]
               for ln in routes.render_table("out").split("\n")[2:]]
        self.assertEqual({a: (k, r, None if ft == "-" else ft) for a, k, r, ft in out},
                         {a: (k, r, ft) for a, (r, k, ft, _d) in routes.OUT_ROUTES.items()})

    def test_the_skill_names_exactly_the_agents_the_routes_name(self):
        text = " ".join(read("skills", "inbox", "SKILL.md").split())
        sentence = text[text.index("starts each agent ticket ("):].split(")", 1)[0]
        named = set(re.findall(r"`([a-z-]+)`", sentence))
        self.assertEqual(named, {t for _h, t, _w in routes.KIND_ROUTES.values()}
                         | {"math-editor"})
        self.assertLessEqual(named, set(AGENTS))
        self.assertEqual(set(routes.agents()) - named, set())

    def test_the_other_docs_point_at_the_routes_instead_of_repeating_them(self):
        formats = read("references", "formats.md")
        self.assertIn("routes.py", formats)
        self.assertNotIn("kind `research` to the Expert", formats)
        doc = routes.__doc__
        self.assertNotIn("| write | agent", doc)             # the docstring has no table copy
        self.assertIn("--tables", doc)

    def test_status_points_at_the_inbox(self):
        self.assertIn("/author:inbox --all", read("skills", "status", "SKILL.md"))

    #: files that explain what replaced /author:next and the roadmap, or are the converter
    RETIREMENT_NOTES = {
        "author/skills/next/SKILL.md", "author/skills/inbox/SKILL.md",
        "author/skills/inbox/references/routing.md", "author/README.md",
        "author/references/formats.md",
        "author/tests/test_inbox.py",
        "author/tests/test_plugin.py", "academy/tests/test_interface_scripts.py",
        "docs/migration-campaign-mode.md",
        "scientist/tests/fixtures/lab/experiments/2026-09-24_torus_cover_periodic_growth.py",
    }
    SKIP_DIRS = {".git", "__pycache__", "golden", "goldens", "_import", "docs-notes",
                 "node_modules"}
    SKIP_FILES = {"_academy.py", "migration-log.md"}     # vendored copies; history
    STALE = re.compile(r"next\.py|/author:next|roadmap\.md|roadmap item|\bR-\d{4}\b|R-NNNN")

    def test_no_stale_next_or_roadmap_references_anywhere_in_the_repo(self):
        stale = []
        for dirpath, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS
                       and not (d == "superpowers" and os.path.basename(dirpath) == "docs")
                       # other checkouts of this repo (git worktrees), not this one
                       and not (d == "worktrees" and os.path.basename(dirpath) == ".claude")]
            for f in files:
                if f in self.SKIP_FILES or not f.endswith((".md", ".py", ".json", ".sh",
                                                           ".yml", ".yaml", ".toml")):
                    continue
                path = os.path.join(dirpath, f)
                rel = os.path.relpath(path, REPO).replace(os.sep, "/")
                if rel in self.RETIREMENT_NOTES:
                    continue
                with open(path, encoding="utf-8", errors="replace") as fh:
                    if self.STALE.search(fh.read()):
                        stale.append(rel)
        self.assertEqual(stale, [])

    def test_the_retirement_notes_really_do_mention_what_they_are_excused_for(self):
        # an allowlist entry that no longer matches anything is dead weight: drop it
        for rel in sorted(self.RETIREMENT_NOTES):
            with open(os.path.join(REPO, *rel.split("/")), encoding="utf-8") as fh:
                self.assertTrue(self.STALE.search(fh.read()), rel)

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


class VisionTests(unittest.TestCase):
    """The Author has aesthetic vision, exercised inside the role cut."""

    def test_the_reference_and_the_template_exist(self):
        ref = read("references", "aesthetic-vision.md")
        for item in ("arc", "Economy", "Notation that earns its place", "right level",
                     "Examples and figures", "promise", "voice"):
            self.assertIn(item, ref)
        self.assertIn("research", ref)              # a cleaner statement is asked for
        tpl = read("templates", "vision.md")
        self.assertIn("{{instance}}", tpl)
        self.assertIn("pending", tpl)

    def test_writers_start_from_the_vision_and_the_pinned_list(self):
        for agent in ("math-writer", "math-editor"):
            text = read("agents", agent + ".md")
            self.assertIn("Drafts/vision.md", text, agent)
            self.assertIn("pinned.py", text, agent)
        for agent in ("figure-maker", "notation-auditor"):
            self.assertIn("Drafts/vision.md", read("agents", agent + ".md"), agent)
        self.assertIn("vision mode", read("agents", "math-editor.md"))

    def test_the_aesthetic_pass_files_tickets_and_never_rewrites_pinned_statements(self):
        for skill in ("agenda", "presync"):
            text = read("skills", skill, "SKILL.md")
            self.assertIn("aesthetic pass", text, skill)
            self.assertIn("final_to: researcher", text, skill)
            self.assertIn("pinned", text, skill)
        self.assertIn("Drafts/vision.md", read("skills", "paper-method", "SKILL.md"))
        self.assertIn("Drafts/vision.md", read("README.md"))

    def test_the_referee_checks_the_vision(self):
        with open(os.path.join(REPO, "expert", "agents", "referee.md"), encoding="utf-8") as fh:
            self.assertIn("Drafts/vision.md", fh.read())


if __name__ == "__main__":
    unittest.main()
