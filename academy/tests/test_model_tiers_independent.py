"""Independent tests for model tiers (T-0350, test-engineer review).

Expected values come from the specification, not from the code's output:

- the human's rule quoted in T-0350 (Roey, 2026-10-12): tiers ``base``, ``medium``,
  ``large``, ``max``; this workspace base = haiku, medium = sonnet (``connect`` read as
  Sonnet), large = max = Opus 5.5; the assignment is workspace dependent;
- docs/config.md, "``models``: agent tiers" and the ``grading`` row (minTier floor,
  default ``large``; named primaryModels, default ``["fable"]``, added to the floor's;
  a tier whose model names no version grants nothing; ``minTier: none`` switches the
  floor off; the list of agents per tier);
- academy/references/roster-rules.md, "Model fallback" / "Graders degrade" (the labels
  ``fable``, ``opus-5.5``, else the family; a verdict on Sonnet, Haiku or an older Opus
  is degraded).

Hand computations are written in each test's docstring.
"""

import importlib.util
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
import usage_report  # noqa: E402

#: the ticket's literal map for this workspace (aliases, as Roey worded it)
LITERAL = {"base": "haiku", "medium": "sonnet", "large": "opus", "max": "opus"}
#: the same map with Opus 5.5 named by its id
VERSIONED = {"base": "haiku", "medium": "sonnet", "large": "claude-opus-5-5",
             "max": "claude-opus-5-5"}

#: docs/config.md: "base for the clerical agents (clerk, paper-liaison, claim-keeper,
#: lit-request, usage-analyst), max for the graders and the prover (rigor-reviewer,
#: referee, experiment-reviewer, prover ...), large for explainer, math-writer and
#: developer, medium for the rest"
SPEC_BASE = {"expert:clerk", "expert:paper-liaison", "researcher:claim-keeper",
             "researcher:lit-request", "academy:usage-analyst"}
SPEC_MAX = {"expert:rigor-reviewer", "expert:referee", "researcher:experiment-reviewer",
            "researcher:prover"}
SPEC_LARGE = {"academy:explainer", "author:math-writer", "scientist:developer"}
#: the 29 agent files of the five plugins (counted in the tree at f9d490a)
SPEC_MEDIUM = {"academy:concierge", "academy:secretary", "author:figure-maker",
               "author:math-editor", "author:notation-auditor", "author:note-sweeper",
               "author:tex-engineer", "expert:librarian", "expert:related-work-scout",
               "expert:research-intake", "expert:review-chair", "researcher:experiment-spec",
               "researcher:lead-researcher", "scientist:api-prober",
               "scientist:experimenter", "scientist:test-engineer",
               "scientist:upstream-contributor"}


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return path


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-tiers-ind-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def ws_file(self, **extra):
        ws = {"instances": {"expert@a": {"role": "expert",
                                         "home": os.path.join(self.tmp, "a"),
                                         "domains": ["d"]}},
              "board": os.path.join(self.tmp, "board")}
        ws.update(extra)
        return _write(os.path.join(self.tmp, "workspace.json"), json.dumps(ws))

    def load(self, **extra):
        return ac.load_workspace(self.ws_file(**extra))


class TestTheHumansRule(Tmp):
    def test_four_tiers_in_order(self):
        """The rule names four tiers, base < medium < large < max."""
        self.assertEqual(tuple(ac.TIERS), ("base", "medium", "large", "max"))

    def test_the_literal_map_of_this_workspace_loads(self):
        """base = haiku, medium = sonnet, large = max = opus is a valid map: aliases,
        non-decreasing (haiku < sonnet < opus = opus)."""
        ws = self.load(models={"tiers": dict(LITERAL)})
        self.assertEqual(ac.model_tiers(ws), LITERAL)

    def test_the_default_is_this_workspace_with_opus_5_5_named(self):
        """The academy default equals the rule with Opus 5.5 named by id."""
        self.assertEqual(ac.model_tiers(self.load()), VERSIONED)

    def test_workspace_dependent(self):
        """Two workspaces with different maps resolve the same agent differently: a
        base-tier agent (clerk) runs on sonnet where base = sonnet."""
        a = ac.resolve_agent("expert:clerk", self.load(), REPO)
        b = ac.resolve_agent("expert:clerk",
                             self.load(models={"tiers": {"base": "sonnet"}}), REPO)
        self.assertEqual((a["tier"], a["launch"], a["override"]), ("base", "haiku", False))
        self.assertEqual((b["tier"], b["launch"], b["override"]), ("base", "sonnet", True))

    def test_connect_is_not_a_model(self):
        """'connect' (the human's word) is neither an alias nor a claude-... id."""
        with self.assertRaises(ac.ConfigError):
            self.load(models={"tiers": {"medium": "connect"}})


class TestValidation(Tmp):
    BAD = [
        ("non-dict models", "fast"),
        ("tiers a list", {"tiers": ["haiku", "sonnet"]}),
        ("unknown tier", {"tiers": {"xl": "opus"}}),
        ("inherit", {"tiers": {"base": "inherit"}}),
        ("empty value", {"tiers": {"base": ""}}),
        ("non-string value", {"tiers": {"base": 3}}),
        ("id of no family", {"tiers": {"large": "claude-foo-1"}}),
        ("large lighter than medium", {"tiers": {"medium": "opus", "large": "sonnet"}}),
        ("max lighter than large (default large opus)", {"tiers": {"max": "haiku"}}),
        ("base heavier than medium (default sonnet)", {"tiers": {"base": "opus"}}),
    ]

    def test_bad_maps_are_refused(self):
        for why, models in self.BAD:
            with self.subTest(why=why):
                self.assertTrue(ac.model_problems({"models": models}))
                with self.assertRaises(ac.ConfigError):
                    self.load(models=models)

    GOOD = [
        ("ids with a context suffix", {"tiers": {"large": "claude-opus-5-5[1m]",
                                                 "max": "claude-opus-5-5[1m]"}}),
        ("fable at max", {"tiers": {"max": "fable"}}),
        ("all opus", {"tiers": {t: "opus" for t in ("base", "medium", "large", "max")}}),
        ("upper-case alias", {"tiers": {"base": "Haiku"}}),
        ("empty tiers", {"tiers": {}}),
        ("no tiers", {}),
    ]

    def test_good_maps_load(self):
        for why, models in self.GOOD:
            with self.subTest(why=why):
                self.assertEqual(ac.model_problems({"models": models}), [])
                self.load(models=models)

    def test_grading_keys(self):
        """minTier is a tier or none; primaryModels a list of non-empty strings."""
        for g in ({"minTier": "huge"}, {"minTier": "Large"}, {"primaryModels": "fable"},
                  {"primaryModels": [""]}, {"primaryModels": [None]}):
            with self.subTest(grading=g):
                with self.assertRaises(ac.ConfigError):
                    self.load(grading=g)


class TestGradingPrimaries(Tmp):
    def prim(self, **extra):
        return ac.primary_models(self.load(**extra))

    def test_nothing_configured_keeps_todays_primaries(self):
        """No models, no grading: Fable (named default) and Opus 5.5 (the default map's
        large and max) - the list before T-0350."""
        self.assertEqual(set(self.prim()), {"fable", "opus-5.5"})

    def test_floor_max_and_floor_base_with_the_default_map(self):
        """Default map: max -> opus-5.5; from base, haiku and sonnet are bare aliases
        (no version) and add nothing. Both give {fable, opus-5.5}."""
        self.assertEqual(set(self.prim(grading={"minTier": "max"})), {"fable", "opus-5.5"})
        self.assertEqual(set(self.prim(grading={"minTier": "base"})), {"fable", "opus-5.5"})

    def test_a_versioned_sonnet_below_the_floor_grants_nothing(self):
        """medium = claude-sonnet-4-5 is below the floor large: not a primary."""
        p = self.prim(models={"tiers": {"medium": "claude-sonnet-4-5"}})
        self.assertNotIn("sonnet", p)

    def test_a_sonnet_large_tier_does_not_make_sonnet_a_grader(self):
        """large = claude-sonnet-4-5 (max stays Opus 5.5): the label 'sonnet' is a bare
        family, and roster-rules says a verdict on Sonnet is degraded; so only Fable and
        Opus 5.5 count."""
        p = self.prim(models={"tiers": {"large": "claude-sonnet-4-5"}})
        self.assertEqual(set(p), {"fable", "opus-5.5"})

    def test_fable_at_max_is_not_listed_twice(self):
        p = self.prim(models={"tiers": {"max": "fable"}})
        self.assertEqual(sorted(p), ["fable", "opus-5.5"])

    def test_none_switches_the_floor_off(self):
        """minTier none: the named list alone; default named list is ['fable']."""
        self.assertEqual(self.prim(grading={"minTier": "none"}), ("fable",))
        self.assertEqual(self.prim(grading={"minTier": "none",
                                            "primaryModels": ["opus-5.5"]}), ("opus-5.5",))

    def test_empty_effective_list_is_refused(self):
        with self.assertRaises(ac.ConfigError):
            self.load(grading={"minTier": "none", "primaryModels": []})

    def test_an_empty_named_list_still_has_the_floor(self):
        """primaryModels [] (refused before T-0350) now means 'no named primaries': the
        floor's Opus 5.5 alone."""
        self.assertEqual(self.prim(grading={"primaryModels": []}), ("opus-5.5",))

    def test_the_literal_map_drops_opus_5_5_from_the_primaries(self):
        """Pins the documented behaviour (docs/config.md: a bare 'opus' names no version
        and gives no grading authority) on the ticket's literal map: the primaries are
        Fable alone, so a grader run recorded as claude-opus-5-5 is NOT a primary in such
        a workspace. Finding 1 of the review: load_workspace and the bootstrap accept
        this map silently; only models.py check warns."""
        ws = self.load(models={"tiers": dict(LITERAL)})
        self.assertEqual(ac.primary_models(ws), ("fable",))
        self.assertNotIn(ac.model_label("claude-opus-5-5"), ac.primary_models(ws))

    @unittest.expectedFailure
    def test_primary_models_of_an_unloaded_workspace_dict_has_the_floor(self):
        """Finding 3: docs/config.md says named primaryModels are added to the floor's.
        load_workspace applies that; ac.primary_models on a workspace dict not passed
        through load_workspace returns the named list alone, so the same configuration
        gives two answers. Expected (spec): ('fable', 'opus-5.5') for both."""
        raw = {"grading": {"primaryModels": ["fable"]}}
        loaded = self.load(grading={"primaryModels": ["fable"]})
        self.assertEqual(ac.primary_models(loaded), ("fable", "opus-5.5"))
        self.assertEqual(ac.primary_models(raw), ("fable", "opus-5.5"))


class TestModelLabel(unittest.TestCase):
    #: roster-rules.md: fable, opus-5.5, else the family; '' when empty
    CASES = [("claude-opus-5-5", "opus-5.5"), ("claude-opus-5-5[1m]", "opus-5.5"),
             ("Opus 5.5", "opus-5.5"), ("opus-5.5", "opus-5.5"), ("opus_5_5", "opus-5.5"),
             ("claude-opus-5-5-20261001", "opus-5.5"), ("claude-opus-5-50", "opus"),
             ("opus", "opus"), ("  OPUS ", "opus"), ("claude-opus-4-1", "opus"),
             ("claude-sonnet-4-5", "sonnet"), ("claude-haiku-4-5", "haiku"),
             ("claude-fable-5-1", "fable"), ("Fable", "fable"), ("", ""), (None, ""),
             ("gpt-4", "gpt-4")]

    def test_known_labels(self):
        for name, want in self.CASES:
            with self.subTest(name=name):
                self.assertEqual(ac.model_label(name), want)

    def _load(self, plugin, module):
        spec = importlib.util.spec_from_file_location(
            "t0350_%s_%s" % (plugin, module),
            os.path.join(REPO, plugin, "scripts", module + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, os.path.join(REPO, plugin, "scripts"))
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path.remove(os.path.join(REPO, plugin, "scripts"))
        return mod

    def test_the_two_former_copies_agree_with_the_one(self):
        """decision_table.model_label and _researcher.model_label now delegate; they
        give the same labels on the same inputs."""
        dt = self._load("expert", "decision_table")
        rs = self._load("researcher", "_researcher")
        for name, want in self.CASES:
            with self.subTest(name=name):
                self.assertEqual(dt.model_label(name), want)
                self.assertEqual(rs.model_label(name), want)


class TestAgentFiles(unittest.TestCase):
    def test_every_agent_has_the_spec_tier(self):
        files = ac.agent_files(REPO)
        want = {}
        for group, tier in ((SPEC_BASE, "base"), (SPEC_MEDIUM, "medium"),
                            (SPEC_LARGE, "large"), (SPEC_MAX, "max")):
            want.update({a: tier for a in group})
        self.assertEqual(len(want), 29)
        self.assertEqual(set(files), set(want))
        for agent, path in files.items():
            fm = ac.read_agent_frontmatter(path)
            with self.subTest(agent=agent):
                self.assertEqual(fm.get("tier"), want[agent])
                # the model: line is the tier's alias in the default map
                self.assertEqual(fm.get("model"), {"base": "haiku", "medium": "sonnet",
                                                   "large": "opus", "max": "opus"}[want[agent]])
                self.assertIn(fm.get("fallback"), ("haiku", "sonnet", "opus"))

    def test_the_graders_launch_on_opus_in_this_workspace_with_no_override(self):
        for agent in sorted(SPEC_MAX):
            for tiers in (LITERAL, VERSIONED):
                with self.subTest(agent=agent, tiers=tiers["large"]):
                    r = ac.resolve_agent(agent, {"models": {"tiers": tiers}}, REPO)
                    self.assertEqual((r["tier"], r["launch"], r["override"]),
                                     ("max", "opus", False))

    def test_bare_name_and_unknown(self):
        self.assertEqual(ac.resolve_agent("rigor-reviewer", {}, REPO)["agent"],
                         "expert:rigor-reviewer")
        with self.assertRaises(ac.ConfigError):
            ac.resolve_agent("no-such-agent", {}, REPO)
        with self.assertRaises(ac.ConfigError):
            ac.resolve_agent("author:rigor-reviewer", {}, REPO)


class TestUsageAgainstTier(Tmp):
    def sess(self, agent, model):
        return [{"session": "s", "instance": "i", "main": {"counts": {}, "models": {}},
                 "subagents": [{"agent_type": agent, "depth": 1, "description": "",
                                "counts": {}, "models": {model: 1}}]}]

    def flags(self, agent, model, ws=None):
        dec = usage_report.declared_models(REPO, ws)
        return usage_report.aggregate(self.sess(agent, model), {}, dec)["flags"]

    def test_a_grader_on_opus_5_5_is_as_declared(self):
        """rigor-reviewer is tier max = Opus 5.5 here: a run on claude-opus-5-5 is not
        heavier; a run on Fable is (fable > opus) and the flag names the tier max."""
        self.assertEqual(self.flags("expert:rigor-reviewer", "claude-opus-5-5"), [])
        f = self.flags("expert:rigor-reviewer", "claude-fable-5-1")
        self.assertEqual([(x["kind"], x["tier"]) for x in f],
                         [("heavier-than-declared", "max")])

    def test_where_max_is_fable_a_fable_grader_is_as_declared(self):
        ws = {"models": {"tiers": {"max": "fable"}}}
        self.assertEqual(self.flags("expert:rigor-reviewer", "claude-fable-5-1", ws), [])

    def test_a_base_agent_on_sonnet_is_heavier(self):
        f = self.flags("expert:clerk", "claude-sonnet-4-5")
        self.assertEqual([(x["kind"], x["declared"], x["tier"]) for x in f],
                         [("heavier-than-declared", "haiku", "base")])


class TestResolverCli(Tmp):
    def run_models(self, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "models.py")] + list(args),
                              capture_output=True, text=True, timeout=60)

    def test_check_warns_on_the_literal_map_and_passes(self):
        """models.py check: exit 0 on the shipped agent files; on the literal map it
        warns that tiers large and max give no grading authority."""
        res = self.run_models("check", "--workspace",
                              self.ws_file(models={"tiers": dict(LITERAL)}))
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("WARNING: tier large", res.stdout)
        self.assertIn("WARNING: tier max", res.stdout)
        res = self.run_models("check", "--workspace", self.ws_file())
        self.assertEqual(res.returncode, 0)
        self.assertNotIn("WARNING", res.stdout)

    def test_launch_value(self):
        ws = self.ws_file(models={"tiers": {"medium": "claude-opus-5-5"}})
        res = self.run_models("agent", "academy:concierge", "--launch", "--workspace", ws)
        self.assertEqual((res.returncode, res.stdout.strip()), (0, "opus"))

    def test_bad_workspace_exits_2(self):
        ws = self.ws_file(models={"tiers": {"medium": "connect"}})
        res = self.run_models("tiers", "--workspace", ws)
        self.assertEqual(res.returncode, 2)


if __name__ == "__main__":
    unittest.main()
