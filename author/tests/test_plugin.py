"""The Author plugin's shape: manifest, skills (the inbox replaced next), agents, scripts."""

import json
import os
import re
import unittest

from fixtures import PLUGIN, REPO, SCRIPTS
import _academy as ac  # noqa: E402
import routes  # noqa: E402

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

    def sections(self):
        text = read("skills", "inbox", "SKILL.md")
        parts = re.split(r"^## (\d)\. ", text, flags=re.M)
        return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}

    def test_inbox_skill_states_the_author_flow(self):
        sec = self.sections()
        self.assertEqual(sorted(sec), [1, 2, 3, 4, 5])
        heads = [sec[n].split("\n", 1)[0] for n in sorted(sec)]
        self.assertTrue(heads[0].startswith("Sweep first"), heads)
        self.assertTrue(heads[1].startswith("Plan"), heads)
        self.assertIn("note-sweeper", sec[1])
        self.assertIn("no item cap", sec[1])
        # the plan: in-progress, land (return), released (blocked -> accepted), open
        plan = sec[2]
        order = [plan.index(x) for x in ("in progress", "`\"return\": true`", "released",
                                         "blocked -> accepted", "open and accepted")]
        self.assertEqual(order, sorted(order), "the plan lists its groups in the core's order")
        self.assertIn("py $S/inbox.py", plan)
        self.assertIn("agenda.py gaps", plan)
        # the run: every route of routes.py is handled, each checkpointed by --check
        run = sec[3]
        for agent in routes.agents():
            if agent != "author:notes":
                self.assertIn("`%s`" % agent, run, agent)
        for how in ("`agent`", "`skill`", "`human`"):
            self.assertIn("| %s" % how, run)
        self.assertIn("`author:notes`", run)
        self.assertIn('"return": true', run)
        rows = [run.index(r) for r in ("\n| `agent` (", "\n| `agent` with `\"return\"",
                                       "\n| `skill` (", "\n| `human` |",
                                       "py $S/inbox.py --check T-NNNN")]
        self.assertEqual(rows, sorted(rows), "rows: agent, landing, skill, human, checkpoint")
        self.assertIn("Exit 3", run)
        self.assertIn("Limit stop", run)
        # self-tickets are closed at the end, then the report
        self.assertIn("check_paper.py", sec[4])
        self.assertIn("closed", sec[4])
        self.assertIn("The sweep counts first", sec[5])
        self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "skills", "inbox",
                                                    "references", "routing.md")))

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
        text = read("skills", "inbox", "SKILL.md")
        row = next(ln for ln in text.split("\n") if ln.startswith("| `agent` (`"))
        named = set(re.findall(r"`([a-z-]+)`", row.split("|")[1])) - {"agent"}
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
        "author/references/formats.md", "author/references/scripts.md",
        "author/scripts/agenda_migrate.py", "author/tests/test_agenda_migrate.py",
        "author/tests/test_agenda.py", "author/tests/test_inbox.py",
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


if __name__ == "__main__":
    unittest.main()
