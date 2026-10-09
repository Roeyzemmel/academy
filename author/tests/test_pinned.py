"""pinned.py and the pinned_guard hook (roster-rules.md, "Role cut", rule 2).

A statement whose hash a CONFIRMED review run recorded in the library is pinned: an edit
that changes its environment is refused, an edit of its proof is not.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fixtures import Sandbox, run_hook  # noqa: E402
import pinned as pn  # noqa: E402

TEX = """\\section{Flat}

\\begin{lem}[Lifting]\\label{lem:lift}
Let $X$ be a compact flat structure. Then every flat morphism lifts.
\\begin{enumerate}
\\item\\label{it:one} uniquely;
\\end{enumerate}
\\end{lem}

\\begin{proof}
A long and winding argument.
\\end{proof}

\\begin{prop}\\label{prop:free}
An unpinned statement.
\\end{prop}
"""


def record(run, verdict, h, subject="paper:lem:lift", pass_="2026-10-08-T-0001"):
    return ("---\nsubject: %s\npass: %s\nrun: %s\nrun_id: rv-%s\nverdict: %s\nmodulo: []\n"
            "model: claude-opus-5-5\nstatement_hash: %s\nblocking:\nticket: none\n---\n\n"
            "report\n" % (subject, pass_, run, run.lower(), verdict, h))


class PinnedBase(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.sb.env.pop("ACADEMY_LIBRARY", None)
        saved = os.environ.pop("ACADEMY_LIBRARY", None)
        if saved is not None:
            self.addCleanup(os.environ.__setitem__, "ACADEMY_LIBRARY", saved)
        self.lib = os.path.join(self.sb.root, "lib")
        self.tex = os.path.join(self.sb.home, "sections", "flat.tex")
        self.sb.write(self.tex, TEX)
        self.h = pn.statement_hash(pn.env_text(TEX, "lem:lift"))

    def land(self, run, verdict, slug="lem-lift", pass_="2026-10-08-T-0001", **kw):
        self.sb.write(os.path.join(self.lib, "reviews", "paper", slug, pass_, run + ".md"),
                      record(run, verdict, kw.get("h", self.h), pass_=pass_,
                             subject=kw.get("subject", "paper:lem:lift")))

    def pins(self):
        with open(self.sb.workspace) as fh:
            ws = json.load(fh)
        return {p["label"]: p for p in pn.pins(self.sb.home, {"ns": "paper"}, ws)}


class PinsFromReviews(PinnedBase):
    def test_a_confirmed_pair_pins_verified_and_a_lone_A_pins_in_review(self):
        self.assertEqual({}, self.pins())
        self.land("A", "CONFIRMED")
        self.assertEqual("in-review", self.pins()["lem:lift"]["level"])
        self.land("B", "CONFIRMED")
        p = self.pins()["lem:lift"]
        self.assertEqual(("verified", self.h), (p["level"], p["hash"]))

    def test_a_later_gap_pass_unpins_and_unhashed_passes_are_ignored(self):
        self.land("A", "CONFIRMED")
        self.land("B", "CONFIRMED")
        self.land("A", "CONFIRMED", pass_="not-in-brief", h="")
        self.assertIn("lem:lift", self.pins())
        self.land("A", "GAP", pass_="2026-10-09-T-0002")
        self.assertNotIn("lem:lift", self.pins())

    def test_the_human_release_list_unpins(self):
        self.land("A", "CONFIRMED")
        self.sb.write(os.path.join(self.sb.home, ".claude", "pinned-release.txt"),
                      "lem:lift  # Ada: restate with compactness\n")
        self.assertTrue(self.pins()["lem:lift"]["released"])

    def test_the_environment_is_the_statement_and_a_nested_label_pins_its_lemma(self):
        env = pn.env_text(TEX, "lem:lift")
        self.assertTrue(env.startswith("\\begin{lem}") and env.endswith("\\end{lem}"))
        self.assertNotIn("winding", env)
        self.assertEqual(env, pn.env_text(TEX, "it:one", pn.statement_envs({})))

    def test_cli_lists_pins_with_the_current_hash(self):
        self.land("A", "CONFIRMED")
        self.land("B", "CONFIRMED")
        import subprocess
        res = subprocess.run([sys.executable, os.path.join(pn.HERE, "pinned.py"), "--home",
                              self.sb.home, "--json"], capture_output=True, env=self.sb.env)
        rows = json.loads(res.stdout.decode("utf-8"))
        self.assertEqual(["lem:lift"], [r["label"] for r in rows])
        self.assertTrue(rows[0]["matches"])
        self.assertEqual("sections/flat.tex", rows[0]["file"])


class PinnedGuard(PinnedBase):
    def edit(self, old, new, agent="author:math-editor", path=None):
        ev = {"tool_name": "Edit", "agent_type": agent, "cwd": self.sb.home,
              "tool_input": {"file_path": path or self.tex, "old_string": old,
                             "new_string": new}}
        return run_hook("pinned_guard.py", ev, self.sb.env)

    def denied(self, out):
        return bool(out) and out.get("hookSpecificOutput", {}).get(
            "permissionDecision") == "deny"

    def setUp(self):
        super().setUp()
        self.land("A", "CONFIRMED")
        self.land("B", "CONFIRMED")

    def test_the_guard_refuses_a_statement_edit(self):
        rc, out, _ = self.edit("Let $X$ be a compact flat structure.",
                               "Let $X$ be a flat structure.")
        self.assertEqual(0, rc)
        self.assertTrue(self.denied(out), out)
        self.assertIn("lem:lift", out["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIn("Researcher", out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_the_guard_refuses_the_main_session_too_and_a_deletion(self):
        rc, out, _ = self.edit("\\item\\label{it:one} uniquely;\n", "", agent="")
        self.assertTrue(self.denied(out))

    def test_the_guard_allows_a_proof_edit(self):
        rc, out, _ = self.edit("A long and winding argument.", "A short argument.")
        self.assertFalse(self.denied(out), out)

    def test_the_guard_allows_an_unpinned_statement_and_whitespace(self):
        rc, out, _ = self.edit("An unpinned statement.", "A changed statement.")
        self.assertFalse(self.denied(out))
        rc, out, _ = self.edit("Then every flat morphism lifts.",
                               "Then every flat\nmorphism   lifts.")
        self.assertFalse(self.denied(out))

    def test_a_released_pin_is_free_and_the_release_list_is_the_humans(self):
        rel = os.path.join(self.sb.home, ".claude", "pinned-release.txt")
        rc, out, _ = self.edit("x", "lem:lift\n", path=rel)
        self.assertTrue(self.denied(out))
        self.sb.write(rel, "lem:lift\n")
        rc, out, _ = self.edit("Let $X$ be a compact flat structure.",
                               "Let $X$ be a flat structure.")
        self.assertFalse(self.denied(out))

    def test_silent_outside_an_author_home(self):
        other = os.path.join(self.sb.other, "x.tex")
        self.sb.write(other, TEX)
        rc, out, _ = self.edit("Let $X$ be a compact flat structure.", "Let", path=other)
        self.assertIsNone(out)

    def test_the_hook_is_registered(self):
        with open(os.path.join(pn.au.PLUGIN_ROOT, "hooks", "hooks.json")) as fh:
            self.assertIn("pinned_guard.py", fh.read())


if __name__ == "__main__":
    unittest.main()
