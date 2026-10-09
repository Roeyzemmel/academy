"""The lab scaffold (templates/lab/, written by /academy:init scientist@x): the provenance
module works without Sage, and an experiment filled in from _template.py passes the
experiment checker (E2/E3 header, E5 save_result, E6 banner, E10 outcome=)."""

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
CHECKER = os.path.join(PLUGIN, "scripts", "check_experiments.py")
sys.path.insert(0, os.path.join(os.path.dirname(PLUGIN), "academy", "scripts"))

import init_instance  # noqa: E402

FILLED = {
    "<One-line title of the experiment.>": "Search for small examples.",
    "<registry ids, comma-separated, e.g. mylab:foo, paper:prop:bar>": "mylab:demo",
    "<the phenomenon, as a checkable property P(X); a falsifier: \"violates claim C\">":
        "a graph with an odd cycle",
    "- <constraint> [<feasibility | setting | excludes ...>]\n"
    "                - <constraint> [<feasibility | setting | excludes ...>]":
        "- at most 5 vertices [feasibility]",
    "<required: P; recorded: the extra properties saved for each example>":
        "required: has an odd cycle; recorded: size",
    "<what is saved per example so it can be rechecked without the search>":
        "the edge list",
    "<a known example AND a known non-example that P must classify correctly>":
        "the triangle (example) and the square (non-example)",
    "yes / no": "no",
    "<after the run: \"found k ...\" or \"not found ...\", over the constraints>": "",
}


class LabTemplateTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="lab-tpl-")
        self.addCleanup(shutil.rmtree, self.home, True)
        cfg = {"schema": 1, "role": "scientist", "instance": "scientist@mylab",
               "domains": ["dom"], "ns": "mylab",
               "paths": {"package": "mylab", "experiments": "experiments/*.py",
                         "results": "results", "queue": "queue", "records": "claims",
                         "views": []},
               "registry": {"profile": "lab", "root": "claims"},
               "scientist": {"envs": {"l": {"kind": "local"}},
                             "policy": {"probe": "l", "test": "l", "run": "l"}}}
        os.makedirs(os.path.join(self.home, ".claude"))
        with open(os.path.join(self.home, ".claude", "academy.json"), "w") as fh:
            json.dump(cfg, fh)
        self.made = init_instance.scaffold_lab(self.home, cfg)

    def read(self, *parts):
        with open(os.path.join(self.home, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_layout_and_placeholders(self):
        for rel in (("mylab", "env.py"), ("mylab", "__init__.py"),
                    ("experiments", "_template.py"), ("experiments", "README.md"),
                    ("results", ".gitkeep")):
            self.assertTrue(os.path.isfile(os.path.join(self.home, *rel)), rel)
        tpl = self.read("experiments", "_template.py")
        self.assertIn("from mylab import env", tpl)
        for rel in (("experiments", "_template.py"), ("experiments", "README.md")):
            self.assertNotIn("{{", self.read(*rel), rel)
        # a second run creates nothing and keeps the lab's edits
        with open(os.path.join(self.home, "mylab", "env.py"), "a") as fh:
            fh.write("# edited\n")
        self.assertEqual(init_instance.scaffold_lab(self.home, json.loads(
            self.read(".claude", "academy.json"))), [])
        self.assertTrue(self.read("mylab", "env.py").endswith("# edited\n"))

    def test_env_outcomes_and_save_result(self):
        sys.path.insert(0, self.home)
        self.addCleanup(sys.path.remove, self.home)
        env = importlib.import_module("mylab.env")
        self.addCleanup(sys.modules.pop, "mylab.env", None)
        self.addCleanup(sys.modules.pop, "mylab", None)
        o = env.search_outcome([], {"n": 3})
        self.assertEqual((o["status"], o["count"]), ("not found", 0))
        with self.assertRaises(ValueError):
            env.search_outcome([{"recorded": {}}], {})
        self.assertEqual(env.verify_outcome("x", {"a": True, "b": False})["status"], "fails")
        p = env.save_result("demo", {"raw": 1}, claims=["mylab:demo"], outcome=o,
                            base=os.path.join(self.home, "results"))
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertEqual(list(d)[:3], ["claims", "outcome", "provenance"])
        self.assertIn("python", d["provenance"])
        with self.assertRaises(ValueError):
            env.save_result("bad", {}, outcome={"kind": "guess"},
                            base=os.path.join(self.home, "results"))

    def test_filled_template_passes_the_checker(self):
        text = self.read("experiments", "_template.py")
        for old, new in FILLED.items():
            self.assertIn(old, text, old)
            text = text.replace(old, new)
        self.assertIsNone(re.search(r"<[A-Za-z][^<>=]*>", text.split('"""')[1]))
        path = os.path.join(self.home, "experiments", "2026-10-09_demo.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        proc = subprocess.run([sys.executable, CHECKER, "--home", self.home, path],
                              capture_output=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("0 error(s)", proc.stdout)


if __name__ == "__main__":
    unittest.main()
