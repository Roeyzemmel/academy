"""preamble_guard: the preamble changes as ``author.preamble.policy`` says (docs/config.md).

Under ``propose`` (the default) and ``locked`` a tool edit of the preamble region, or of a
``preamble.extraFiles`` file, is refused; an edit of the body passes; ``free`` has no
guard; the human releases a file by hand in ``.claude/preamble-release.txt``.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fixtures import Sandbox, author_config, run_hook  # noqa: E402
import _author as au  # noqa: E402

MAIN = ("\\documentclass{amsart}\n\\usepackage{amsthm}\n\\newcommand{\\R}{\\mathbb R}\n"
        "\\begin{document}\n\\section{One}\nBody text.\n\\end{document}\n")


class PreambleGuard(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.main = os.path.join(self.sb.home, "main.tex")
        self.sb.write(self.main, MAIN)
        self.sb.write(os.path.join(self.sb.home, "macros.tex"), "\\newcommand{\\Z}{}\n")

    def configure(self, preamble=None):
        cfg = author_config(self.sb.home, self.sb.tools)
        if preamble is not None:
            cfg["author"]["preamble"] = preamble
        self.sb.write_config(author=cfg["author"])

    def edit(self, old, new, path=None, agent="author:tex-engineer"):
        ev = {"tool_name": "Edit", "agent_type": agent, "cwd": self.sb.home,
              "tool_input": {"file_path": path or self.main, "old_string": old,
                             "new_string": new}}
        rc, out, _ = run_hook("preamble_guard.py", ev, self.sb.env)
        self.assertEqual(0, rc)
        return out

    @staticmethod
    def reason(out):
        if out and out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny":
            return out["hookSpecificOutput"]["permissionDecisionReason"]
        return None

    def test_propose_is_the_default_and_refuses_a_preamble_edit(self):
        self.configure()
        why = self.reason(self.edit("\\usepackage{amsthm}", "\\usepackage{amsthm,tikz}"))
        self.assertIsNotNone(why)
        self.assertIn("proposal", why)
        self.assertIsNotNone(self.reason(self.edit("\\usepackage{amsthm}\n", "", agent="")))

    def test_a_body_edit_passes(self):
        self.configure()
        self.assertIsNone(self.reason(self.edit("Body text.", "Other text.")))

    def test_free_has_no_guard_and_locked_refuses(self):
        self.configure({"policy": "free"})
        self.assertIsNone(self.reason(self.edit("\\usepackage{amsthm}", "\\usepackage{x}")))
        self.configure({"policy": "locked"})
        why = self.reason(self.edit("\\usepackage{amsthm}", "\\usepackage{x}"))
        self.assertIn("locked", why)

    def test_extra_files_and_a_custom_end(self):
        self.configure({"extraFiles": ["macros.tex"], "end": "\\section{One}"})
        macros = os.path.join(self.sb.home, "macros.tex")
        self.assertIsNotNone(self.reason(self.edit("\\Z", "\\ZZ", path=macros)))
        # \begin{document} now lies inside the region
        self.assertIsNotNone(self.reason(self.edit("\\begin{document}\n",
                                                   "\\begin{document}\n%x\n")))
        self.assertIsNone(self.reason(self.edit("Body text.", "Other.")))

    def test_the_release_file_is_the_humans_and_releases(self):
        self.configure()
        rel = os.path.join(self.sb.home, ".claude", "preamble-release.txt")
        self.assertIsNotNone(self.reason(self.edit("x", "main.tex\n", path=rel)))
        self.sb.write(rel, "# released by the human\nmain.tex\n")
        self.assertIsNone(self.reason(self.edit("\\usepackage{amsthm}", "\\usepackage{x}")))

    def test_silent_outside_an_author_home_and_for_other_files(self):
        self.configure()
        other = os.path.join(self.sb.other, "main.tex")
        self.sb.write(other, MAIN)
        self.assertIsNone(self.edit("\\usepackage{amsthm}", "", path=other))
        sec = os.path.join(self.sb.home, "sections", "a.tex")
        self.sb.write(sec, "\\usepackage{amsthm}\n")
        self.assertIsNone(self.reason(self.edit("\\usepackage{amsthm}", "", path=sec)))

    def test_the_hook_is_registered(self):
        with open(os.path.join(au.PLUGIN_ROOT, "hooks", "hooks.json")) as fh:
            self.assertIn("preamble_guard.py", fh.read())


if __name__ == "__main__":
    unittest.main()
