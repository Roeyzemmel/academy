"""The generic configuration keys (docs/config.md): workspace.json ``human.login``,
``grading.primaryModels`` and ``plugins``; academy.json ``registry.prefixes`` /
``assumptionGroups``, ``paths.verifyChecklist``, ``author.provenance``; the rule-set
names and their old aliases."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))

import academy_common as ac  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-generic-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def workspace(self, **extra):
        ws = {"instances": {
            "researcher@a": {"role": "researcher", "home": os.path.join(self.tmp, "a"),
                             "domains": ["translation-surfaces"], "ns": "nb"},
            "author@p": {"role": "author", "home": os.path.join(self.tmp, "p"),
                         "domains": ["some-pack"], "ns": "paper"}},
            "board": os.path.join(self.tmp, "board")}
        ws.update(extra)
        return ac.load_workspace(write(os.path.join(self.tmp, "workspace.json"),
                                       json.dumps(ws)))


class TestWorkspaceKeys(Tmp):
    def test_defaults_keep_todays_behaviour(self):
        ws = self.workspace()
        self.assertEqual(ws["human"]["name"], "human")
        self.assertIsNone(ws["human"]["login"])
        self.assertEqual(ws["grading"]["primaryModels"], ["fable", "opus-5.5"])
        self.assertEqual(ac.primary_models(ws), ("fable", "opus-5.5"))
        self.assertEqual(ac.human_name(ws), "the human")
        self.assertIsNone(ac.human_login(ws))

    def test_plugins_derived_from_roles_and_domains(self):
        ws = self.workspace()
        # the marketplace names domains/translation-surfaces "ts-domain"; an unknown
        # pack keeps its own name
        self.assertEqual(ws["plugins"], ["academy", "author", "researcher", "ts-domain",
                                         "some-pack"])
        self.assertEqual(self.workspace(plugins=["academy"])["plugins"], ["academy"])
        with self.assertRaises(ac.ConfigError):
            self.workspace(plugins="academy")

    def test_human_and_grading_from_the_file(self):
        ws = self.workspace(human={"name": "Ada", "login": "ada-l"},
                            grading={"primaryModels": ["fable"]})
        self.assertEqual(ac.human_name(ws), "Ada")
        self.assertEqual(ac.human_login(ws), "ada-l")
        self.assertEqual(ac.primary_models(ws), ("fable",))
        with self.assertRaises(ac.ConfigError):
            self.workspace(grading={"primaryModels": []})

    def test_login_falls_back_to_the_board_assignee(self):
        ws = self.workspace(board={"path": os.path.join(self.tmp, "board"),
                                   "backend": "files", "assignee": "ada-gh"})
        self.assertEqual(ws["human"]["login"], "ada-gh")
        self.assertEqual(ac.human_login(ws), "ada-gh")

    def test_no_workspace_means_the_defaults(self):
        old = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = os.path.join(self.tmp, "missing.json")
        try:
            # repo_root()/workspace.json may exist on a developer machine: only the
            # fallbacks are asserted when nothing is readable
            try:
                ac.load_workspace(os.path.join(self.tmp, "missing.json"))
                has_ws = True
            except ac.ConfigError:
                has_ws = False
            if not has_ws:
                self.assertEqual(ac.primary_models(), ac.DEFAULT_PRIMARY_MODELS)
                self.assertEqual(ac.human_name(), "the human")
        finally:
            if old is None:
                os.environ.pop("ACADEMY_WORKSPACE", None)
            else:
                os.environ["ACADEMY_WORKSPACE"] = old


class TestHomeKeys(unittest.TestCase):
    def test_verify_checklist_default_and_override(self):
        self.assertEqual(ac.verify_checklist_path({}),
                         ".claude/rules/verification-checklist.md")
        self.assertEqual(ac.verify_checklist_path({"paths": {"verifyChecklist": "docs/c.md"}}),
                         "docs/c.md")

    def test_author_provenance(self):
        self.assertIsNone(ac.author_provenance({"author": {}}))
        self.assertIsNone(ac.author_provenance({"author": {"provenance": {"enabled": False}}}))
        p = ac.author_provenance({"author": {"provenance": {"env": "new"}}})
        self.assertEqual(p["env"], "new")
        self.assertEqual(p["command"], "\\Added")
        self.assertEqual(p["removedBy"], "human")

    def test_rule_set_aliases_validate(self):
        base = {"schema": 1, "role": "researcher", "instance": "researcher@a",
                "domains": ["d"], "ns": "a",
                "paths": {k: k for k in ac.REQUIRED_PATHS["researcher"]},
                "budget": {"itemsPerRun": 3, "orchestratorModel": "sonnet",
                           "maxModel": "fable"},
                "gate": {"commit": "normal"}, "researcher": {}}
        for prof in ("notebook", "s1", "s1-kb", "lab", "paper"):
            cfg = dict(base, registry={"profile": prof, "root": "objects"})
            self.assertEqual(ac.validate_config(cfg), [], prof)
        cfg = dict(base, registry={"profile": "kb"})
        self.assertTrue(ac.validate_config(cfg))
        cfg = dict(base, registry={"profile": "notebook", "prefixes": "GEO"})
        self.assertTrue(any("registry.prefixes" in p for p in ac.validate_config(cfg)))
        self.assertEqual(ac.registry_rule_set("s1"), "notebook")
        self.assertEqual(ac.registry_rule_set("s1-kb"), "notebook")
        self.assertIsNone(ac.registry_rule_set("nope"))


class TestRegistryRules(Tmp):
    """The notebook rule set reads its id prefixes and groups from the home."""

    def setUp(self):
        super().setUp()
        mod = sys.modules.get("registry")
        if mod is not None and not hasattr(mod, "__path__"):
            del sys.modules["registry"]       # scripts/registry.py, not the package
        if sys.path[0] != PLUGIN:
            sys.path.insert(0, PLUGIN)
        from registry.core import workspace
        from registry.profiles import s1kb
        self.workspace_mod, self.s1kb = workspace, s1kb
        self.root = Path(self.tmp) / "nb"
        o = self.root / "objects"
        claim = ("---\nid: {id}\nkind: claim\nform: prop\ntitle: t\nstatus: open\n"
                 "lifecycle: active\nevidence: []\nhistory:\n  - 2026-09-24 | open | c\n"
                 "---\n## Statement\nx\n")
        write(str(o / "claim" / "doubling-z2-class.md"), claim.format(id="doubling-z2-class"))
        write(str(o / "claim" / "GEO-1.md"), claim.format(id="GEO-1"))
        write(str(o / "assumption" / "PA-1.md"),
              "---\nid: PA-1\nkind: assumption\ntitle: a\nlifecycle: active\n---\nx\n")

    def config(self, **reg):
        r = {"profile": "notebook", "root": "objects"}
        r.update(reg)
        write(str(self.root / ".claude" / "academy.json"), json.dumps({"ns": "nb", "registry": r}))

    def id_errors(self):
        kb = self.s1kb.load_kb(self.root)
        errors, _ = self.s1kb.run_check(kb)
        return [e for e in errors if "id '" in e or "prefix '" in e]

    def test_without_prefixes_any_slug_is_an_id(self):
        self.config()
        self.assertEqual(self.id_errors(), [])
        kb = self.s1kb.load_kb(self.root)
        self.assertIn("PA-1", self.s1kb.view_assumptions(kb))

    def test_configured_prefixes_reject_other_ids(self):
        self.config(prefixes={"GEO": "geometry", "PA": "assumptions"},
                    assumptionGroups={"PA": "Parking garage"})
        errs = self.id_errors()
        self.assertEqual(len(errs), 1, errs)
        self.assertIn("doubling-z2-class", errs[0])
        kb = self.s1kb.load_kb(self.root)
        self.assertIn("- **PA** — Parking garage", self.s1kb.view_assumptions(kb))
        self.assertEqual(kb.rules.ns, "nb")

    def test_assumption_prefix_must_be_a_group(self):
        self.config(prefixes={"GEO": "g", "PA": "a", "OA": "o"},
                    assumptionGroups={"OA": "Origami"})
        errs = self.id_errors()
        self.assertTrue(any("prefix 'PA' does not belong in assumption files" in e
                            for e in errs), errs)

    def test_rule_set_names_and_aliases(self):
        ws = self.workspace_mod
        self.assertEqual(ws.canonical_rule_set("s1"), "notebook")
        self.assertEqual(ws.canonical_rule_set("s1-kb"), "notebook")
        self.assertEqual(ws.canonical_rule_set("paper"), "paper")
        self.assertIsNone(ws.canonical_rule_set("flat"))
        for prof in ("notebook", "s1", "s1-kb"):
            self.config(profile=prof)
            self.assertEqual(ws.rule_set("nb", self.root), "notebook")
            self.assertEqual(ws.engine_profile("nb", self.root), "s1-kb")
        self.assertEqual(ws.rule_set("s1"), "notebook")      # no home: the ns's own name
        self.assertEqual(ws.rule_set("elsewhere"), "lab")


if __name__ == "__main__":
    unittest.main()
