"""The plugin's check_experiments.py finds the lab from --home / $ACADEMY_LAB_HOME /
the cwd, and reads the experiments and results directories from academy.json
(docs/config.md: paths.experiments, paths.results), instead of from its own location.
The rules themselves are the lab's (legacy/check_experiments.py) and are tested there
(FlatSurfLab tests/test_check_experiments.py, which loads the lab's shim)."""

import json
import os
import subprocess
import sys
import tempfile
import shutil
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKER = os.path.join(os.path.dirname(HERE), "scripts", "check_experiments.py")

GOOD = '''#!/usr/bin/env python3
"""A measure.

Kind:           measure
Claims:         lab:probe
Goal:           count cylinders
Class:          3-square origamis
Quantity:       number of horizontal cylinders
Validation:     the 3-square L has two
Needs Sage:     no

Result:
"""

from fslab import env


def run():
    env.banner(__file__)
    env.save_result("x", {}, script=__file__, outcome=env.measure_outcome())
'''


class CheckerHomeTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="chk-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.home = os.path.join(self.root, "lab")
        os.makedirs(os.path.join(self.home, "exps"))
        os.makedirs(os.path.join(self.home, "out"))
        os.makedirs(os.path.join(self.home, ".claude"))
        with open(os.path.join(self.home, ".claude", "academy.json"), "w") as fh:
            json.dump({"schema": 1, "role": "scientist", "instance": "scientist@ts",
                       "domains": ["translation-surfaces"], "ns": "lab",
                       "paths": {"package": "fslab", "experiments": "exps/*.py",
                                 "results": "out", "queue": "queue", "records": "claims",
                                 "views": []},
                       "registry": {"profile": "lab", "root": "claims"},
                       "scientist": {"envs": {"l": {"kind": "local"}},
                                     "policy": {"probe": "l", "test": "l", "run": "l"}}},
                      fh)
        with open(os.path.join(self.home, "exps", "2026-09-30_good.py"), "w") as fh:
            fh.write(GOOD)
        with open(os.path.join(self.home, "exps", "bad_name.py"), "w") as fh:
            fh.write(GOOD)
        with open(os.path.join(self.home, "out", "orphan.json"), "w") as fh:
            fh.write("{}")

    def run_checker(self, *args, cwd=None, env=None):
        e = dict(os.environ, PYTHONIOENCODING="utf-8")
        e.pop("ACADEMY_LAB_HOME", None)
        e.update(env or {})
        p = subprocess.run([sys.executable, CHECKER] + list(args), capture_output=True,
                           text=True, encoding="utf-8", cwd=cwd or self.root, env=e)
        return p.returncode, p.stdout + p.stderr

    def test_home_flag_and_configured_dirs(self):
        rc, out = self.run_checker("--home", self.home)
        self.assertEqual(rc, 1, out)
        self.assertIn("exps/bad_name.py:1: ERROR: [E1]", out)
        self.assertIn("out/orphan.json:1: WARN: [W2]", out)
        self.assertNotIn("2026-09-30_good.py:1: ERROR", out)
        self.assertIn("over 2 script(s)", out)

    def test_env_var_and_cwd(self):
        rc1, out1 = self.run_checker(env={"ACADEMY_LAB_HOME": self.home})
        rc2, out2 = self.run_checker(cwd=os.path.join(self.home, "exps"))
        self.assertEqual(out1, out2)
        self.assertIn("over 2 script(s)", out2)


if __name__ == "__main__":
    unittest.main()
