"""script_path_guard: an academy script called at a path where it is not (the 2026-11-13
error-ledger round, 22 "can't open file" failures) is answered with where it is."""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import script_path_guard as g  # noqa: E402


class ScriptPathGuard(unittest.TestCase):
    def setUp(self):
        self.cwd = tempfile.mkdtemp(prefix="spg-")
        self.addCleanup(shutil.rmtree, self.cwd, True)

    def decide(self, command, tool="Bash"):
        return g.decide({"tool_name": tool, "cwd": self.cwd,
                         "tool_input": {"command": command}}, roots=[REPO])

    def test_the_ledgers_guesses_are_answered_with_the_real_path(self):
        real = os.path.realpath(os.path.join(PLUGIN, "scripts", "cowork.py")).replace("\\", "/")
        for cmd in ("python3 academy/scripts/cowork.py status x --json",
                    "py scripts/cowork.py status x --json 2>&1 || python3 scripts/cowork.py status x",
                    "cd sub && py 'scripts/cowork.py' status x",
                    "ls academy/scripts | head && py academy/scripts/cowork.py status x"):
            verdict = self.decide(cmd)
            self.assertIsNotNone(verdict, cmd)
            self.assertEqual("deny", verdict[0])
            self.assertIn(real, verdict[1])
        v = self.decide("python3 scripts/notebook.py --home . journal --json")
        self.assertIn("/researcher/scripts/notebook.py", v[1])
        v = self.decide("py 'C:\\\\x\\\\academy\\\\0.1.0\\\\scripts\\\\cards.py' validate c.md",
                        tool="PowerShell")
        self.assertIn("/expert/scripts/cards.py", v[1])

    def test_a_script_of_several_plugins_lists_them(self):
        v = self.decide("python3 scripts/inbox.py --json")
        self.assertIn("several plugins", v[1])
        self.assertIn("/expert/scripts/inbox.py", v[1])
        self.assertIn("/author/scripts/inbox.py", v[1])

    def test_everything_else_passes(self):
        real = os.path.join(PLUGIN, "scripts", "cowork.py")
        with open(os.path.join(self.cwd, "mine.py"), "w") as fh:
            fh.write("")
        for cmd in ("py %s status x" % real,                     # the right path
                    "python3 mine.py",                             # an existing file
                    "python3 nothere.py",                          # not an academy script
                    "py $S/cowork.py status x",                    # a variable: not ours to judge
                    "py \"${CLAUDE_PLUGIN_ROOT}/scripts/cowork.py\" list",
                    "cat > cowork.py <<'E'\nprint(1)\nE\npython3 cowork.py",   # written first
                    "python3 - <<'E'\nimport cowork.py\nE",
                    "git status", "echo cowork.py"):
            self.assertIsNone(self.decide(cmd), cmd)
        self.assertIsNone(g.decide({"tool_name": "Read", "tool_input": {"command": "py x.py"}}))

    def test_the_store_stub_is_named_only_where_it_is_one(self):
        ev = lambda c: {"tool_name": "Bash", "cwd": self.cwd, "tool_input": {"command": c}}
        for cmd in ("python - <<'EOF'\nprint(1)\nEOF", "cd x && python3 -c 'print(1)'",
                    "curl -s u | python -m json.tool"):
            v = g.decide(ev(cmd), roots=[REPO], stub=True)
            self.assertEqual("deny", v[0], cmd)
            self.assertIn("`py`", v[1])
            self.assertIsNone(g.decide(ev(cmd), roots=[REPO], stub=False), cmd)
        self.assertIsNone(g.decide(ev("py -c 1; echo python"), roots=[REPO], stub=True))
        self.assertFalse(g.store_stub(windows=False))
        self.assertTrue(g.store_stub(which=lambda n: {"py": "C:/py.exe"}.get(n), windows=True))
        self.assertTrue(g.store_stub(which=lambda n: {
            "py": "C:/py.exe", "python": "C:/Users/x/AppData/Local/Microsoft/WindowsApps/"
            "python.exe"}.get(n), windows=True))
        self.assertFalse(g.store_stub(which=lambda n: "C:/Python310/%s.exe" % n, windows=True))


if __name__ == "__main__":
    unittest.main()
