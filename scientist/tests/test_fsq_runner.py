"""Runs the runner's own test suite, scripts/legacy/test_fsq.sh, against the deployed
scripts/fsq.sh (plan section 3.6: fsq.sh is a byte copy of the legacy runner, pinned by
test_env.py's test_runner_copy_is_the_legacy_runner; this is the runner's *behaviour*
check, which that byte-identity test does not exercise).

test_fsq.sh needs a real Linux shell: bash, git, pgrep, and /dev/shm for its lock
directory. None of that exists on the Windows laptop this suite usually runs on, so
this test skips cleanly there and actually runs under WSL and on a remote worker, where all of
it is present.

Run: py -m unittest discover -s tests -t tests   (from the plugin folder; skips on
Windows unless run under WSL's own Python) or, explicitly, bash scripts/legacy/
test_fsq.sh <workdir> from a Linux shell.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
LEGACY = os.path.join(PLUGIN, "scripts", "legacy")
TEST_FSQ = os.path.join(LEGACY, "test_fsq.sh")

REQUIRED_TOOLS = ("bash", "git", "pgrep")


def _missing_tools():
    return [t for t in REQUIRED_TOOLS if shutil.which(t) is None]


def _linux_like():
    # test_fsq.sh hard-codes /dev/shm for its lock directory and shells out to
    # pgrep/pkill; Git Bash on Windows has neither, only a real Linux (or WSL) shell
    # does, so this is a better gate than "bash is somewhere on PATH".
    return sys.platform != "win32" and os.path.isdir("/dev/shm")


@unittest.skipUnless(_linux_like(), "needs a real Linux shell (WSL or a remote worker), not "
                                    "Windows: test_fsq.sh uses /dev/shm and pgrep")
class FsqRunnerTests(unittest.TestCase):
    def setUp(self):
        missing = _missing_tools()
        if missing:
            self.skipTest("missing on PATH: %s" % ", ".join(missing))
        self.assertTrue(os.path.isfile(TEST_FSQ), TEST_FSQ)

    def test_fsq_sh_behaviour(self):
        """cap / once / fifo / tree / lost / cancel / pause / idle, from test_fsq.sh's
        own fake-job harness; see its header comment for what each checks."""
        with tempfile.TemporaryDirectory(prefix="fsq-runner-test-") as workdir:
            proc = subprocess.run(["bash", TEST_FSQ, workdir], cwd=LEGACY,
                                  capture_output=True, text=True, timeout=180)
            report = proc.stdout + proc.stderr
            self.assertEqual(proc.returncode, 0, report)
            self.assertIn("passed", report)
            self.assertNotIn("FAIL ", report, report)


if __name__ == "__main__":
    unittest.main()
