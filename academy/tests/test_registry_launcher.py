"""scripts/registry.py: the registry command line, callable from any directory."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(os.path.dirname(HERE), "scripts", "registry.py")


def run(args, cwd):
    return subprocess.run([sys.executable, LAUNCHER] + args, cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", timeout=60)


class TestLauncher(unittest.TestCase):
    def test_help_runs_from_a_foreign_directory(self):
        with tempfile.TemporaryDirectory() as d:
            r = run(["--help"], d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("the one command line for every registry", r.stdout)

    def test_a_directory_that_is_no_registry_is_refused_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            r = run(["check"], d)
        self.assertEqual(r.returncode, 2)
        self.assertIn("is not a registry home", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
