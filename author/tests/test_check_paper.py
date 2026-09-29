"""check_paper.py in the plugin: the self-test, the academy.json parameterisation, and
the phase-0 equivalence against goldens/check_paper.txt (read-only on BI)."""

import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
import unittest

from fixtures import SCRIPTS, REPO

sys.path.insert(0, SCRIPTS)
import check_paper as cp  # noqa: E402

BI = os.environ.get("ACADEMY_HOME_AUTHOR_BI", "")   # set by the workspace bootstrap
GOLDEN = os.path.join(REPO, "goldens", "check_paper.txt")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
ENV.pop("PYTHONIOENCODING", None)          # the script must be UTF-8-safe on its own


def run(*args, cwd=None):
    res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_paper.py")] + list(args),
                         capture_output=True, env=ENV, cwd=cwd, timeout=600)
    return res.returncode, res.stdout.decode("utf-8").replace("\r\n", "\n"), \
        res.stderr.decode("utf-8", "replace")


class SelfTest(unittest.TestCase):
    def test_self_test(self):
        code, out, err = run("--self-test")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Self-test: 0 checks failed.", out)


class ConfigTests(unittest.TestCase):
    MAIN = "\\documentclass{amsart}\n\\begin{document}\n\\section{A}\n\\input{sections/a}\n" \
           "\\end{document}\n"
    A = ("\\begin{entwurf}\n\\begin{satz}\\label{satz:x}\nA.\n\\end{satz}\n\\end{entwurf}\n\n"
         "\\begin{satz}\\label{satz:y}\nB, by \\cref{satz:x}. \\Maschine{note}\n\\end{satz}\n"
         "\\begin{proof}\nOk.\n\\end{proof}\n")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cp-config-")
        os.makedirs(os.path.join(self.tmp, "sections"))
        os.makedirs(os.path.join(self.tmp, ".claude"))
        with open(os.path.join(self.tmp, "main.tex"), "w", newline="\n") as fh:
            fh.write(self.MAIN)
        with open(os.path.join(self.tmp, "sections", "a.tex"), "w", newline="\n") as fh:
            fh.write(self.A)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        cp.configure(None)

    def write_config(self, author):
        with open(os.path.join(self.tmp, ".claude", "academy.json"), "w") as fh:
            json.dump({"role": "author", "author": author}, fh)

    def test_defaults_do_not_know_the_custom_envs(self):
        code, out, _err = run("--root", self.tmp, "--no-log", "--no-registry", "--defaults")
        self.assertIn("Parsed 0 theorem-like statements.", out)

    def test_custom_vocabulary_from_academy_json(self):
        self.write_config({"theorems": {"all": ["satz"], "provable": ["satz"],
                                        "commentary": []},
                           "envs": {"entwurf": "sketch"},
                           "colourCommands": {"\\Entwurf": "sketch"},
                           "noteMacros": {"machine": ["\\Maschine"]},
                           "checker": {"statements": "Drafts/reg.md"}})
        code, out, err = run("--root", self.tmp, "--no-log")
        self.assertIn("Parsed 2 theorem-like statements.", out, err)
        self.assertIn("satz:y: [R1]", out)                 # rests on the sketched satz:x
        reg = os.path.join(self.tmp, "Drafts", "reg.md")
        self.assertTrue(os.path.isfile(reg))
        with open(reg, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("satz:x", text)

    def test_configure_resets(self):
        cp.configure({"theorems": {"all": ["satz"]}, "noteMacros": {"machine": ["\\M"]}})
        self.assertEqual(cp.THEOREM_ENVS, {"satz"})
        self.assertTrue(cp.RE_CLAUDE.search("\\M{x}"))
        cp.configure(None)
        self.assertIn("thm", cp.THEOREM_ENVS)
        self.assertTrue(cp.RE_CLAUDE.search("\\Claude {x}"))
        self.assertTrue(cp.RE_CLAUDE.search("\\cl{x}"))
        self.assertEqual(cp.COLOUR_COMMANDS, {"\\Sketch{": "sketch",
                                              "\\Conjectural{": "conjectural",
                                              "\\Meta{": "meta"})

    def test_config_file_with_explicit_defaults_changes_nothing(self):
        explicit = {"main": "main.tex", "build": {"dir": ".build"},
                    "theorems": {"all": list(cp.DEFAULT_THEOREM_ENVS),
                                 "provable": list(cp.DEFAULT_PROVABLE_ENVS),
                                 "commentary": list(cp.DEFAULT_COMMENTARY_ENVS)},
                    "envs": dict(cp.DEFAULT_COLOUR_ENVS),
                    "colourCommands": dict(cp.DEFAULT_COLOUR_COMMANDS),
                    "noteMacros": {"machine": ["\\Claude", "\\cl"]}}
        cfg = os.path.join(self.tmp, "explicit.json")
        with open(cfg, "w") as fh:
            json.dump({"role": "author", "author": explicit}, fh)
        a = run("--root", self.tmp, "--no-log", "--no-registry", "--defaults")[1]
        b = run("--root", self.tmp, "--no-log", "--no-registry", "--config", cfg)[1]
        self.assertEqual(a, b)


def _without_r7(text):
    """Drop the R7 lines and the tex line numbers: findings are compared by file, label and
    rule, because line numbers move with every edit."""
    return [re.sub(r"\.tex:\d+:", ".tex:", ln) for ln in text.splitlines()
            if "[R7]" not in ln and not ln.startswith("WARNINGS (")]


@unittest.skipUnless(os.path.isfile(os.path.join(BI, "main.tex")) and os.path.isfile(GOLDEN),
                     "BilliardIllumination or the golden is not present")
class GoldenEquivalenceTests(unittest.TestCase):
    """plan 3.6 / 9.0: the plugin copy reproduces the phase-0 golden (modulo R7)."""

    def test_matches_golden_modulo_r7(self):
        code, out, err = run("--root", BI, "--no-log", "--no-registry")
        with open(GOLDEN, encoding="utf-8") as fh:
            golden = fh.read().replace("\r\n", "\n")
        self.assertTrue(golden.rstrip().endswith("exit=%d" % code), (code, err))
        self.assertEqual(_without_r7(out), _without_r7(golden.rsplit("exit=", 1)[0]))


if __name__ == "__main__":
    unittest.main()
