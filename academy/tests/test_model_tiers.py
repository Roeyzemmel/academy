"""Model tiers (T-0350): every agent file declares a tier (base / medium / large / max);
workspace.json ``models.tiers`` maps each tier to a model, over the academy default;
``grading.minTier`` is the graders' tier floor; ``academy/scripts/models.py`` resolves
agent -> tier -> model for a workspace. docs/config.md, "models"."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
SCRIPTS = os.path.join(PLUGIN, "scripts")
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, SCRIPTS)

import academy_common as ac  # noqa: E402
import models  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


#: the tier each agent had before tiers, read off its model (T-0350): haiku -> base,
#: sonnet -> medium, opus -> large; the four that ran on Fable until f9d490a -> max
FORMER_FABLE = ("expert:rigor-reviewer", "expert:referee", "researcher:experiment-reviewer",
                "researcher:prover")


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-tiers-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def ws_file(self, **extra):
        ws = {"instances": {
            "expert@a": {"role": "expert", "home": os.path.join(self.tmp, "a"),
                         "domains": ["d"]}},
            "board": os.path.join(self.tmp, "board")}
        ws.update(extra)
        return write(os.path.join(self.tmp, "workspace.json"), json.dumps(ws))

    def workspace(self, **extra):
        return ac.load_workspace(self.ws_file(**extra))


class TestTierMap(Tmp):
    def test_the_academy_default(self):
        self.assertEqual(ac.TIERS, ("base", "medium", "large", "max"))
        self.assertEqual(ac.DEFAULT_MODEL_TIERS,
                         {"base": "haiku", "medium": "sonnet", "large": "claude-opus-5-5",
                          "max": "claude-opus-5-5"})
        ws = self.workspace()
        self.assertEqual(ws["models"]["tiers"], ac.DEFAULT_MODEL_TIERS)
        self.assertEqual(ac.model_tiers(ws), ac.DEFAULT_MODEL_TIERS)
        self.assertEqual(ac.model_tiers({}), ac.DEFAULT_MODEL_TIERS)

    def test_a_partial_map_is_merged_over_the_default(self):
        ws = self.workspace(models={"tiers": {"medium": "opus", "max": "fable"}})
        self.assertEqual(ac.model_tiers(ws), {"base": "haiku", "medium": "opus",
                                              "large": "claude-opus-5-5", "max": "fable"})
        self.assertEqual(ac.tier_model("medium", ws), "opus")

    def test_bad_maps_are_refused(self):
        bad = [
            {"models": "opus"},
            {"models": {"tiers": ["haiku"]}},
            {"models": {"tiers": {"huge": "opus"}}},                 # unknown tier
            {"models": {"tiers": {"medium": "connect"}}},            # not a model
            {"models": {"tiers": {"medium": ""}}},
            {"models": {"tiers": {"base": "inherit"}}},              # a tier names a model
            {"models": {"tiers": {"base": "opus", "medium": "haiku"}}},  # lighter above
            {"grading": {"minTier": "huge"}},
        ]
        for extra in bad:
            with self.subTest(extra=extra):
                self.assertTrue(ac.model_problems(extra), extra)
                with self.assertRaises(ac.ConfigError):
                    self.workspace(**extra)

    def test_good_maps_have_no_problems(self):
        for extra in ({}, {"models": {"tiers": {"large": "opus", "max": "opus"}}},
                      {"models": {"tiers": {"max": "claude-fable-5-1"}}},
                      {"grading": {"minTier": "none"}}):
            with self.subTest(extra=extra):
                self.assertEqual(ac.model_problems(extra), [])

    def test_launch_model_is_the_agent_tool_alias(self):
        self.assertEqual(ac.launch_model("claude-opus-5-5"), "opus")
        self.assertEqual(ac.launch_model("claude-fable-5-1"), "fable")
        self.assertEqual(ac.launch_model("sonnet"), "sonnet")
        self.assertEqual(ac.launch_model("claude-haiku-4-5"), "haiku")

    def test_tier_order(self):
        self.assertTrue(ac.tier_at_least("max", "large"))
        self.assertTrue(ac.tier_at_least("large", "large"))
        self.assertFalse(ac.tier_at_least("medium", "large"))


class TestGradingFloor(Tmp):
    def test_default_primaries_unchanged(self):
        ws = self.workspace()
        self.assertEqual(ws["grading"]["minTier"], "large")
        self.assertEqual(ac.primary_models(ws), ("fable", "opus-5.5"))
        self.assertEqual(ac.primary_models(ws), ac.DEFAULT_PRIMARY_MODELS)

    def test_the_floor_follows_the_tier_map(self):
        tiers = {"large": "claude-opus-5-5", "max": "claude-fable-5-1"}
        ws = self.workspace(models={"tiers": tiers}, grading={"primaryModels": []})
        self.assertEqual(ac.primary_models(ws), ("opus-5.5", "fable"))
        ws = self.workspace(models={"tiers": tiers},
                            grading={"minTier": "max", "primaryModels": []})
        self.assertEqual(ac.primary_models(ws), ("fable",))

    def test_a_bare_alias_names_no_version_and_grants_nothing(self):
        # roster-rules.md: a bare "opus" names no version and is read as a fallback; so
        # does a model id the labeller cannot version yet (model_label)
        for model in ("opus", "claude-opus-6-0"):
            ws = self.workspace(models={"tiers": {"large": model, "max": model}})
            self.assertEqual(ac.primary_models(ws), ("fable",), model)

    def test_model_label(self):
        for name, want in (("claude-opus-5-5[1m]", "opus-5.5"), ("Opus 5.5", "opus-5.5"),
                           ("claude-fable-5-1", "fable"), ("opus", "opus"),
                           ("claude-sonnet-4-5", "sonnet"), ("", ""), ("x", "x")):
            self.assertEqual(ac.model_label(name), want, name)

    def test_named_primaries_add_to_the_floor_and_none_switches_it_off(self):
        ws = self.workspace(grading={"primaryModels": ["claude-fable-5-1"]})
        self.assertEqual(ac.primary_models(ws), ("claude-fable-5-1", "opus-5.5"))
        ws = self.workspace(grading={"primaryModels": ["fable"], "minTier": "none"})
        self.assertEqual(ac.primary_models(ws), ("fable",))
        with self.assertRaises(ac.ConfigError):
            self.workspace(grading={"primaryModels": [], "minTier": "none"})


class TestAgentFiles(unittest.TestCase):
    """The shape every academy agent file has: a tier, and a ``model:`` that is the
    academy default of that tier (the model Claude Code uses when no override is passed)."""

    def test_every_agent_declares_a_tier_and_its_default_model(self):
        files = ac.agent_files(REPO)
        self.assertGreater(len(files), 25)
        for agent, path in files.items():
            with self.subTest(agent=agent):
                fm = ac.read_agent_frontmatter(path)
                self.assertIn(fm.get("tier"), ac.TIERS, agent)
                self.assertEqual(fm.get("model"),
                                 ac.launch_model(ac.DEFAULT_MODEL_TIERS[fm["tier"]]), agent)

    def test_tiers_carry_the_former_models(self):
        files = ac.agent_files(REPO)
        for agent in FORMER_FABLE:
            self.assertEqual(ac.read_agent_frontmatter(files[agent])["tier"], "max", agent)
        want = {"academy:usage-analyst": "base", "expert:clerk": "base",
                "academy:concierge": "medium", "expert:review-chair": "medium",
                "academy:explainer": "large", "author:math-writer": "large",
                "scientist:developer": "large"}
        for agent, tier in want.items():
            self.assertEqual(ac.read_agent_frontmatter(files[agent])["tier"], tier, agent)


class TestResolver(Tmp):
    def test_resolve_an_agent(self):
        ws = self.workspace()
        r = ac.resolve_agent("expert:rigor-reviewer", ws, REPO)
        self.assertEqual((r["agent"], r["tier"], r["model"], r["launch"], r["override"]),
                         ("expert:rigor-reviewer", "max", "claude-opus-5-5", "opus", False))
        self.assertEqual(ac.resolve_agent("rigor-reviewer", ws, REPO)["agent"],
                         "expert:rigor-reviewer")
        with self.assertRaises(ac.ConfigError):
            ac.resolve_agent("no-such-agent", ws, REPO)

    def test_a_workspace_that_differs_needs_the_override(self):
        ws = self.workspace(models={"tiers": {"medium": "opus"}})
        r = ac.resolve_agent("academy:concierge", ws, REPO)
        self.assertEqual((r["tier"], r["frontmatter"], r["launch"], r["override"]),
                         ("medium", "sonnet", "opus", True))

    def test_cli(self):
        path = self.ws_file(models={"tiers": {"base": "sonnet"}})
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(models.main(["agent", "expert:clerk", "--launch",
                                          "--workspace", path]), 0)
        self.assertEqual(out.getvalue().strip(), "sonnet")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(models.main(["list", "--json", "--workspace", path]), 0)
        rows = json.loads(out.getvalue())
        clerk = [r for r in rows["agents"] if r["agent"] == "expert:clerk"][0]
        self.assertTrue(clerk["override"])
        self.assertEqual(rows["tiers"]["base"], "sonnet")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(models.main(["check", "--workspace", path]), 0)
        self.assertIn("expert:clerk", out.getvalue())          # named as an override
        # a tier the grading floor reaches whose model the labeller cannot version
        path = self.ws_file(models={"tiers": {"large": "claude-opus-6-0",
                                              "max": "claude-opus-6-0"}})
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(models.main(["check", "--workspace", path]), 0)
        self.assertIn("claude-opus-6-0", out.getvalue())
        self.assertIn("no grading authority", out.getvalue())

    def test_cli_as_a_process(self):
        path = self.ws_file()
        proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "models.py"), "agent",
                               "researcher:prover", "--workspace", path],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("max", proc.stdout)
        self.assertIn("claude-opus-5-5", proc.stdout)


if __name__ == "__main__":
    unittest.main()
