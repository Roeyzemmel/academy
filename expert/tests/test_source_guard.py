"""source_guard.py: the Expert's web fetches stay on its allowlist of sources (2026-10-31)."""

import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import source_guard as sg  # noqa: E402


def ev(url, agent="expert:librarian"):
    return {"hook_event_name": "PreToolUse", "tool_name": "WebFetch", "agent_type": agent,
            "tool_input": {"url": url, "prompt": "x"}}


class SourceGuardTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, {}, clear=False)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("ACADEMY_ALLOW_ANY_SOURCE", None)

    def test_listed_hosts_and_subdomains_pass(self):
        for url in ("https://arxiv.org/abs/2410.01234", "https://export.arxiv.org/api/query",
                    "https://www.ams.org/journals", "https://doi.org/10.1000/x"):
            self.assertIsNone(sg.decide(ev(url), cfg={}), url)

    def test_other_hosts_are_denied_with_the_host_named(self):
        out = sg.decide(ev("https://gauss.math.yale.edu/~x/paper.pdf"), cfg={})
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("gauss.math.yale.edu", out["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIsNotNone(sg.decide(ev("https://evilarxiv.org/x"), cfg={}))   # not a subdomain

    def test_the_library_adds_or_replaces_hosts(self):
        cfg = {"expert": {"sources": {"allow": ["math.yale.edu"]}}}
        self.assertIsNone(sg.decide(ev("https://gauss.math.yale.edu/p.pdf"), cfg=cfg))
        only = {"expert": {"sources": {"allow": ["math.yale.edu"], "only": True}}}
        self.assertIsNotNone(sg.decide(ev("https://arxiv.org/abs/1"), cfg=only))
        self.assertEqual(sg.allowlist(only), ["math.yale.edu"])

    def test_other_agents_the_human_and_the_opt_out_pass(self):
        url = "https://example.com/x"
        for agent in ("", "researcher:prover", "expert:clerk", "author:librarian"):
            self.assertIsNone(sg.decide(ev(url, agent), cfg={}), agent)
        self.assertIsNotNone(sg.decide(ev(url, "expert:related-work-scout"), cfg={}))
        with mock.patch.dict(os.environ, {"ACADEMY_ALLOW_ANY_SOURCE": "1"}):
            self.assertIsNone(sg.decide(ev(url), cfg={}))

    def test_the_hook_is_registered_and_the_defaults_parse(self):
        with open(os.path.join(PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]["PreToolUse"]
        self.assertTrue(any(h.get("matcher") == "WebFetch" and "source_guard.py"
                            in h["hooks"][0]["command"] for h in hooks))
        self.assertIn("arxiv.org", sg.default_hosts())


if __name__ == "__main__":
    unittest.main()
