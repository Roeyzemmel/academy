"""The Author plugin's PreToolUse dispatcher (pre_tool_use.py): one process for the four
edit guards, selecting by tool in the old registration order, first denial wins.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fixtures import SCRIPTS, run_hook  # noqa: E402
from test_pinned import PinnedBase  # noqa: E402

if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import pre_tool_use as d  # noqa: E402

GUARDS = ("bib_gate", "pinned_guard", "preamble_guard", "notation_scope_guard")


class DispatcherTests(unittest.TestCase):
    def test_tool_selects_the_guards_of_the_former_matchers(self):
        for tool in ("Edit", "Write", "MultiEdit"):
            self.assertEqual(d.guards_for(tool), GUARDS)
        self.assertEqual(d.guards_for("NotebookEdit"), ("notation_scope_guard",))
        for tool in ("Bash", "PowerShell", "Read", "Agent", ""):
            self.assertEqual(d.guards_for(tool), (), tool)
        for name in GUARDS:
            self.assertTrue(callable(getattr(__import__(name), "decide")), name)

    def fakes(self, verdicts, calls):
        def make(name):
            def fn(event):
                calls.append(name)
                v = verdicts.get(name)
                if isinstance(v, Exception):
                    raise v
                return v
            return fn
        return {n: make(n) for n in GUARDS}

    def test_order_and_all_pass(self):
        calls = []
        self.assertIsNone(d.decide({"tool_name": "Edit"}, self.fakes({}, calls)))
        self.assertEqual(calls, list(GUARDS))
        calls.clear()
        self.assertIsNone(d.decide({"tool_name": "NotebookEdit"}, self.fakes({}, calls)))
        self.assertEqual(calls, ["notation_scope_guard"])
        calls.clear()
        self.assertIsNone(d.decide({"tool_name": "Bash"}, self.fakes({}, calls)))
        self.assertEqual(calls, [])

    def test_first_denial_wins_and_stops(self):
        calls = []
        v = {"pinned_guard": ("deny", "pin"), "preamble_guard": ("deny", "pre")}
        self.assertEqual(d.decide({"tool_name": "Write"}, self.fakes(v, calls)),
                         ("deny", "pin"))
        self.assertEqual(calls, ["bib_gate", "pinned_guard"])

    def test_a_crashing_guard_is_skipped(self):
        calls, errors = [], []
        v = {"bib_gate": RuntimeError("boom"), "preamble_guard": ("deny", "pre")}
        self.assertEqual(d.decide({"tool_name": "Edit"}, self.fakes(v, calls), errors),
                         ("deny", "pre"))
        self.assertEqual(calls, ["bib_gate", "pinned_guard", "preamble_guard"])
        self.assertEqual([n for n, _ in errors], ["bib_gate"])
        # a guard missing from the map (an import failure) is skipped the same way
        self.assertIsNone(d.decide({"tool_name": "Edit"}, {}))


class EndToEndTests(PinnedBase):
    """Real events through ``pre_tool_use.py``: one pass-through and one denial per guard."""

    def setUp(self):
        super().setUp()
        self.land("A", "CONFIRMED")
        self.land("B", "CONFIRMED")
        self.main = os.path.join(self.sb.home, "main.tex")
        self.sb.write(self.main, "\\documentclass{amsart}\n\\begin{document}\nBody.\n"
                                 "\\end{document}\n")
        self.bib = os.path.join(self.sb.home, "references.bib")
        self.decisions = os.path.join(self.sb.home, ".claude", "rules",
                                      "notation-decisions.md")

    def run_event(self, tool, tool_input, agent="author:math-editor"):
        ev = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
              "cwd": self.sb.home}
        if agent:
            ev["agent_type"] = agent
        rc, out, err = run_hook("pre_tool_use.py", ev, self.sb.env)
        self.assertEqual(rc, 0, err)
        return out

    def edit(self, path, old, new, **kw):
        return self.run_event("Edit", {"file_path": path, "old_string": old,
                                       "new_string": new}, **kw)

    def reason(self, out):
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny", out)
        return out["hookSpecificOutput"]["permissionDecisionReason"]

    def test_pass_through(self):
        self.assertIsNone(self.edit(self.main, "Body.", "Other."))
        self.assertIsNone(self.edit(self.tex, "A long and winding argument.", "Short."))
        self.assertIsNone(self.run_event("Read", {"file_path": self.bib}))

    def test_bib_gate_denies(self):
        self.assertIn("bibliography", self.reason(self.edit(self.bib, "a", "b")))
        self.assertIsNone(self.edit(self.bib, "a", "b", agent="expert:librarian"))

    def test_pinned_guard_denies(self):
        why = self.reason(self.edit(self.tex, "Let $X$ be a compact flat structure.",
                                    "Let $X$ be a flat structure."))
        self.assertIn("pinned_guard", why)
        self.assertIn("lem:lift", why)

    def test_preamble_guard_denies(self):
        why = self.reason(self.edit(self.main, "\\documentclass{amsart}",
                                    "\\documentclass{article}"))
        self.assertIn("preamble_guard", why)

    def test_notation_scope_guard_denies(self):
        why = self.reason(self.edit(self.tex, "Short", "x", agent="author:notation-auditor"))
        self.assertIn("notation-auditor", why)
        out = self.run_event("NotebookEdit", {"notebook_path": self.tex, "new_source": "y"},
                             agent="author:notation-auditor")
        self.assertIn("notation-auditor", self.reason(out))
        self.assertIsNone(self.edit(self.decisions, "a", "b", agent="author:notation-auditor"))

    def test_first_denial_speaks_when_two_guards_deny(self):
        # the bib is denied by bib_gate before notation_scope_guard would speak
        why = self.reason(self.edit(self.bib, "a", "b", agent="author:notation-auditor"))
        self.assertIn("bibliography", why)

    def test_bad_input_exits_silently(self):
        import subprocess
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "pre_tool_use.py")],
                             input=b"not json", capture_output=True, timeout=60,
                             env=self.sb.env)
        self.assertEqual((res.returncode, res.stdout.strip()), (0, b""))


if __name__ == "__main__":
    unittest.main()
