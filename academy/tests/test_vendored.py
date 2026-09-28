"""The vendored copies <plugin>/scripts/_academy.py must equal academy/lib/academy_common.py.

Fix a failure with:  py academy/scripts/sync_common.py
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import sync_common  # noqa: E402


class VendoredTests(unittest.TestCase):
    def test_five_plugins(self):
        self.assertEqual(sync_common.PLUGINS,
                         ("academy", "author", "researcher", "expert", "scientist"))

    def test_no_drift(self):
        with open(os.path.join(PLUGIN, "lib", "academy_common.py"), "rb") as fh:
            lib = fh.read()
        for target in sync_common.targets(REPO):
            rel = os.path.relpath(target, REPO)
            with self.subTest(copy=rel):
                self.assertTrue(os.path.isfile(target), "%s is missing; run "
                                "py academy/scripts/sync_common.py" % rel)
                with open(target, "rb") as fh:
                    self.assertEqual(fh.read(), lib, "%s drifted from the lib; run "
                                     "py academy/scripts/sync_common.py" % rel)

    def test_check_mode_agrees(self):
        self.assertEqual(sync_common.drifted(REPO), [])


if __name__ == "__main__":
    unittest.main()
