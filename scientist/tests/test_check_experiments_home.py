"""The plugin's check_experiments.py finds the lab from --home / $ACADEMY_LAB_HOME /
the cwd, and reads the experiments and results directories from academy.json
(docs/config.md: paths.experiments, paths.results), instead of from its own location.
The rules themselves are the lab's (legacy/check_experiments.py) and are tested there
(SciLab tests/test_check_experiments.py, which loads the lab's shim).

E7 (a ``Claims:`` id missing from the registry) reads the lab's registry through the
academy registry engine (``academy/registry/profiles/fsl.py``, the engine of rule set
``lab``), not through a ``scripts/claims.py`` in the lab (removed 2026-09-28, T-0177)."""

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

# One record of the lab registry (claims/lab/probe.md), in the fsl-claims dialect.
PROBE_RECORD = """---
id: lab:probe
kind: claim
title: "Measure: horizontal cylinders of 3-square origamis"
status: open
lifecycle: active
domain: translation-surfaces
evidence: []
history:
  - 2026-10-10 | open | created (test fixture)
---

A fixture record for the checker's E7 test.
"""


class CheckerHomeTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="chk-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.home = os.path.join(self.root, "lab")
        os.makedirs(os.path.join(self.home, "exps"))
        os.makedirs(os.path.join(self.home, "out"))
        os.makedirs(os.path.join(self.home, ".claude"))
        with open(os.path.join(self.home, ".claude", "academy.json"), "w") as fh:
            json.dump({"schema": 1, "role": "scientist", "instance": "scientist@main",
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
        os.makedirs(os.path.join(self.home, "claims", "lab"))
        with open(os.path.join(self.home, "claims", "lab", "probe.md"), "w",
                  encoding="utf-8") as fh:
            fh.write(PROBE_RECORD)
        # A workspace naming no instance, so a namespace's rule set is its own name
        # (``lab`` is checked) whatever workspace the machine running the tests has.
        self.workspace = os.path.join(self.root, "workspace.json")
        with open(self.workspace, "w") as fh:
            json.dump({"instances": {}}, fh)

    def run_checker(self, *args, cwd=None, env=None):
        e = dict(os.environ, PYTHONIOENCODING="utf-8")
        for var in ("ACADEMY_LAB_HOME", "ACADEMY_ROOT", "ACADEMY_ENV_WORKSPACE"):
            e.pop(var, None)
        e["ACADEMY_WORKSPACE"] = self.workspace
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

    def test_e7_flags_an_id_missing_from_the_registry(self):
        with open(os.path.join(self.home, "exps", "2026-09-30_unknown.py"), "w") as fh:
            fh.write(GOOD.replace("Claims:         lab:probe",
                                  "Claims:         lab:probe, lab:no-such-claim"))
        rc, out = self.run_checker("--home", self.home)
        self.assertEqual(rc, 1, out)
        self.assertIn("exps/2026-09-30_unknown.py:5: ERROR: [E7] claim 'lab:no-such-claim' "
                      "is not in the registry", out)
        e7 = [line for line in out.splitlines() if "[E7]" in line]
        self.assertEqual(len(e7), 1, out)   # lab:probe is in the registry: no E7 for it

    def test_e7_reads_only_the_claims_field_not_a_following_free_field(self):
        # A header field outside the contract (here ``Tests:``) ends ``Claims:``; its
        # indented continuation lines are not read as more claim ids.
        with open(os.path.join(self.home, "exps", "2026-09-30_free.py"), "w") as fh:
            fh.write(GOOD.replace(
                "Claims:         lab:probe\n",
                "Claims:         lab:probe\n"
                "Tests:          flat:other, file proofs/x.md, Example 3 (the\n"
                "                counterexample), not (S), (W)\n"))
        rc, out = self.run_checker("--home", self.home,
                                   os.path.join(self.home, "exps", "2026-09-30_free.py"))
        self.assertEqual(rc, 0, out)
        self.assertNotIn("[E7]", out)

    def test_e7_quiet_when_every_id_is_in_the_registry(self):
        rc, out = self.run_checker("--home", self.home,
                                   os.path.join(self.home, "exps", "2026-09-30_good.py"))
        self.assertEqual(rc, 0, out)
        self.assertNotIn("[E7]", out)

    def test_e7_in_process_beside_another_module_named_academy(self):
        # A lab's tests load the checker in process with their own tests/_academy.py
        # (a helper that finds the academy repo) already imported as ``_academy``; the
        # checker must still reach its vendored copy, the registry and the rule sets.
        import importlib.util
        import types
        saved = sys.modules.get("_academy")
        sys.modules["_academy"] = types.ModuleType("_academy")   # the lab's helper
        old_ws = os.environ.get("ACADEMY_WORKSPACE")
        os.environ["ACADEMY_WORKSPACE"] = self.workspace
        try:
            spec = importlib.util.spec_from_file_location("chk_under_test", CHECKER)
            chk = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(chk)
            chk.set_home(self.home)
            self.assertEqual(chk.registry_ids(), {"lab:probe"})
            script = os.path.join(self.home, "exps", "2026-09-30_unknown.py")
            with open(script, "w") as fh:
                fh.write(GOOD.replace("Claims:         lab:probe",
                                      "Claims:         lab:probe, lab:no-such-claim"))
            report = chk.Report()
            chk.check_script(chk.Path(script), report, set(), chk.registry_ids())
            e7 = [line for line in report.errors if "[E7]" in line]
            self.assertEqual(len(e7), 1, report.errors)
            self.assertIn("'lab:no-such-claim'", e7[0])
        finally:
            if saved is None:
                sys.modules.pop("_academy", None)
            else:
                sys.modules["_academy"] = saved
            if old_ws is None:
                os.environ.pop("ACADEMY_WORKSPACE", None)
            else:
                os.environ["ACADEMY_WORKSPACE"] = old_ws


if __name__ == "__main__":
    unittest.main()
