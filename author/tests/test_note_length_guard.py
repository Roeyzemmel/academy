"""note_length_guard: author.notes.maxLines enforced when a machine note is written (#110 point 5).

The guard judges only the notes an edit adds: an existing long note passing through an edit
unchanged is not the writer's, and narrowing a long note (shorter, still long) is progress.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fixtures import SCRIPTS, Sandbox, run_hook  # noqa: E402

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import note_length_guard as g  # noqa: E402

LONG = "x " * 60          # 120 plain characters: 4 lines at 30 a line, over the cap of 3
LONGER = "y " * 80
SHORT = "T-0001: see the thread"


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.tex = os.path.join(self.sb.home, "sections", "a.tex")
        self.sb.write(self.tex, "Intro. \\Claude{%s}\n\nText here.\n" % LONG)

    def edit(self, old, new, path=None, tool="Edit"):
        ti = {"file_path": path or self.tex}
        if tool == "Write":
            ti["content"] = new
        else:
            ti.update(old_string=old, new_string=new)
        return {"tool_name": tool, "tool_input": ti, "cwd": self.sb.home}

    def test_a_short_new_note_passes(self):
        self.assertIsNone(g.decide(self.edit("Text here.", "Text here. \\Claude{%s}" % SHORT)))

    def test_a_long_new_note_is_denied_with_the_way_out(self):
        v = g.decide(self.edit("Text here.", "Text here. \\Claude[check]{%s}" % LONGER))
        self.assertEqual(v[0], "deny")
        self.assertIn("author.notes.maxLines", v[1])
        self.assertIn("3", v[1])
        self.assertIn("pointer", v[1])
        self.assertIn("sections/a.tex", v[1])

    def test_an_existing_long_note_passing_through_is_not_judged(self):
        old = "Intro. \\Claude{%s}" % LONG
        self.assertIsNone(g.decide(self.edit(old, "Intro, reworded. \\Claude{%s}" % LONG)))

    def test_narrowing_passes_and_lengthening_is_denied(self):
        old = "\\Claude{%s}" % LONG
        self.assertIsNone(g.decide(self.edit(old, "\\Claude{%s}" % ("x " * 50))))
        self.assertIsNone(g.decide(self.edit(old, "\\Claude{%s}" % SHORT)))
        self.assertEqual(g.decide(self.edit(old, "\\Claude{%s}" % LONGER))[0], "deny")

    def test_deleting_a_note_passes(self):
        self.assertIsNone(g.decide(self.edit(" \\Claude{%s}" % LONG, "")))

    def test_write_of_a_new_file_with_a_long_note(self):
        new = os.path.join(self.sb.home, "sections", "b.tex")
        self.assertEqual(g.decide(self.edit(None, "\\Claude{%s}\n" % LONG, new, "Write"))[0],
                         "deny")
        self.assertIsNone(g.decide(self.edit(None, "\\Claude{%s}\n" % SHORT, new, "Write")))

    def test_outside_tex_or_home_or_switched_off(self):
        md = os.path.join(self.sb.home, "Drafts", "x.md")
        self.assertIsNone(g.decide(self.edit(None, "\\Claude{%s}" % LONG, md, "Write")))
        other = os.path.join(self.sb.other, "x.tex")
        self.assertIsNone(g.decide(self.edit(None, "\\Claude{%s}" % LONG, other, "Write")))
        self.sb.write_config(author=dict(self._author(), notes={"maxLines": 3,
                                                                "enforce": False}))
        self.assertIsNone(g.decide(self.edit("Text here.", "\\Claude{%s}" % LONGER)))

    def test_line_chars_and_max_lines_come_from_the_config(self):
        self.sb.write_config(author=dict(self._author(), notes={"maxLines": 2,
                                                                "lineChars": 200}))
        self.assertIsNone(g.decide(self.edit("Text here.", "\\Claude{%s}" % LONGER)))
        self.sb.write_config(author=dict(self._author(), notes={"maxLines": 1,
                                                                "lineChars": 10}))
        self.assertEqual(g.decide(self.edit("Text here.", "\\Claude{%s}" % SHORT))[0], "deny")

    def test_a_human_note_is_not_judged(self):
        self.sb.write_config(author=dict(self._author(),
                                         noteMacros={"machine": ["\\Claude"],
                                                     "human": ["\\Ada"]}))
        self.assertIsNone(g.decide(self.edit("Text here.", "\\Ada{%s}" % LONGER)))

    def test_through_the_dispatcher_hook(self):
        code, out, _err = run_hook("pre_tool_use.py", self.edit(
            "Text here.", "Text here. \\Claude{%s}" % LONGER), self.sb.env)
        self.assertEqual(code, 0)
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("note_length_guard", out["hookSpecificOutput"]["permissionDecisionReason"])

    def _author(self):
        with open(os.path.join(self.sb.home, ".claude", "academy.json"), encoding="utf-8") as fh:
            return json.load(fh)["author"]


if __name__ == "__main__":
    unittest.main()
