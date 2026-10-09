"""check_paper.py in the plugin: the self-test and the academy.json parameterisation. (The
phase-0 equivalence against a real paper's golden output moved out of the marketplace
with the goldens.)"""

import json
import os
import subprocess
import sys
import tempfile
import shutil
import unittest

from fixtures import SCRIPTS

sys.path.insert(0, SCRIPTS)
import check_paper as cp  # noqa: E402


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



class StatusLevelTests(unittest.TestCase):
    """``author.statusLevels`` drives R1, the sketched proof and the registry; without it
    the levels are derived from ``envs`` / ``colourCommands`` / ``colours``."""

    MAIN = "\\documentclass{amsart}\n\\begin{document}\n\\section{I}\n" \
           "\\input{sections/intro}\n\\end{document}\n"
    INTRO = ("\\begin{entwurf}\n\\begin{lem}\\label{lem:draft}\nA.\n\\end{lem}\n"
             "\\end{entwurf}\n\n"
             "\\begin{sketch}\n\\begin{lem}\\label{lem:oldblue}\nB.\n\\end{lem}\n"
             "\\end{sketch}\n\n"
             "\\begin{thm}\\label{thm:a}\nBy \\cref{lem:draft}.\n\\end{thm}\n"
             "\\begin{proof}\nOk.\n\\end{proof}\n\n"
             "\\begin{thm}\\label{thm:b}\nBy \\cref{lem:oldblue}.\n\\end{thm}\n"
             "\\begin{proof}\n\\Entwurf{roughly}.\n\\end{proof}\n")
    LEVELS = [{"name": "final", "colour": "black", "kind": "established",
               "statuses": ["proved"]},
              {"name": "draft", "env": "entwurf", "command": "\\Entwurf", "colour": "orange",
               "kind": "unestablished", "statuses": ["open", "sketch"]}]

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cp-levels-")
        os.makedirs(os.path.join(self.tmp, "sections"))
        os.makedirs(os.path.join(self.tmp, ".claude"))
        with open(os.path.join(self.tmp, "main.tex"), "w", newline="\n") as fh:
            fh.write(self.MAIN)
        with open(os.path.join(self.tmp, "sections", "intro.tex"), "w", newline="\n") as fh:
            fh.write(self.INTRO)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        cp.configure(None)

    def write_config(self, author):
        with open(os.path.join(self.tmp, ".claude", "academy.json"), "w") as fh:
            json.dump({"role": "author", "author": author}, fh)

    def test_a_custom_scheme_drives_r1(self):
        self.write_config({"statusLevels": self.LEVELS,
                           "mainResults": {"file": "sections/intro.tex",
                                           "labels": ["thm:b"]}})
        code, out, err = run("--root", self.tmp, "--no-log")
        self.assertIn("thm:a: [R1] final thm references draft lem:draft", out, err)
        # `sketch` is not a level of this home: lem:oldblue is final, thm:b rests on it
        self.assertNotIn("references sketch", out)
        self.assertIn("thm:b: [R1] final thm has a sketched proof (contains draft spans)",
                      out)
        with open(os.path.join(self.tmp, "Drafts", "statements.md"), encoding="utf-8") as fh:
            reg = fh.read()
        self.assertIn("classDef draft fill:#fde8d0", reg)
        self.assertIn("classDef final fill:#ffffff", reg)
        self.assertIn("(and `thm:b` in particular)", reg)
        self.assertIn("- `lem:draft`", reg)               # a draft with no dependants

    def test_derived_levels_equal_the_defaults(self):
        cp.configure(None)
        default = (dict(cp.LEVEL_KIND), dict(cp.LEVEL_COLOUR), dict(cp.COLOUR_ENVS),
                   dict(cp.COLOUR_COMMANDS), set(cp.SKETCH_LEVELS), cp.ESTABLISHED)
        for block in ({"envs": dict(cp.DEFAULT_COLOUR_ENVS),
                       "colourCommands": dict(cp.DEFAULT_COLOUR_COMMANDS),
                       "colours": {"established": "black", "sketch": "blue",
                                   "conjectural": "red", "meta": "brown"}},
                      {"statusLevels": [dict(lv) for lv in cp.DEFAULT_STATUS_LEVELS]}):
            cp.configure(block)
            self.assertEqual(default, (dict(cp.LEVEL_KIND), dict(cp.LEVEL_COLOUR),
                                       dict(cp.COLOUR_ENVS), dict(cp.COLOUR_COMMANDS),
                                       set(cp.SKETCH_LEVELS), cp.ESTABLISHED))
        self.assertEqual({"sketch", "conjectural"},
                         {n for n, k in default[0].items() if k == "unestablished"})
        self.assertEqual("commentary", default[0]["meta"])
        self.assertEqual(cp.mermaid_classes().splitlines()[1].strip(),
                         "classDef sketch fill:#dce8fb,stroke:#2c61b5,color:#10305e;")

    def test_an_old_custom_level_name_is_commentary(self):
        cp.configure({"envs": {"entwurf": "entwurf"}})
        self.assertEqual("commentary", cp.LEVEL_KIND["entwurf"])

    def test_main_results_from_config(self):
        self.write_config({"mainResults": {"file": "sections/intro.tex",
                                           "labels": ["lem:oldblue"]}})
        run("--root", self.tmp, "--no-log")
        with open(os.path.join(self.tmp, "Drafts", "statements.md"), encoding="utf-8") as fh:
            reg = fh.read()
        self.assertIn("- **`lem:oldblue`**", reg)
        self.assertIn("- **`thm:b`** (established", reg)
        self.assertIn("  - `lem:oldblue` (sketch lem", reg)
        self.write_config({"mainResults": {"file": "sections/elsewhere.tex"}})
        run("--root", self.tmp, "--no-log")
        with open(os.path.join(self.tmp, "Drafts", "statements.md"), encoding="utf-8") as fh:
            reg = fh.read()
        self.assertIn("_No `thm:` statements found in `sections/elsewhere.tex`._", reg)

    def test_accepted_bib_warnings_and_ref_command(self):
        os.makedirs(os.path.join(self.tmp, ".build"))
        with open(os.path.join(self.tmp, ".build", "main.blg"), "w") as fh:
            fh.write("Warning--empty journal in St84\nWarning--empty year in Xy01\n")
        self.write_config({"bib": {"acceptedWarnings": ["St84"]},
                           "labels": {"refCommand": "autoref"}})
        out = run("--root", self.tmp, "--no-registry")[1]
        self.assertIn("bibtex warnings 1 (+1 accepted)", out)
        cp.configure({"labels": {"refCommand": "autoref"}})
        self.assertTrue(cp.RE_REF.search("\\autoref{lem:x}"))
        self.assertTrue(cp.RE_REF.search("\\Autoref{lem:x}"))
        self.assertTrue(cp.RE_REF.search("\\cref{lem:x}"))


class ConfigValidation(unittest.TestCase):
    def setUp(self):
        import _academy as ac
        self.ac = ac

    def probs(self, **author):
        return self.ac.validate_author(author)

    def test_the_defaults_and_a_custom_scheme_validate(self):
        self.assertEqual([], self.probs())
        self.assertEqual([], self.probs(statusLevels=StatusLevelTests.LEVELS,
                                        preamble={"policy": "locked",
                                                  "extraFiles": ["macros.tex"]},
                                        labels={"prefixes": ["thm"], "refCommand": "cref"},
                                        notes={"maxLines": 2},
                                        figures={"dir": "fig", "include": "\\input"},
                                        bib={"acceptedWarnings": ["St84"]},
                                        mainResults={"file": "intro.tex", "labels": []}))

    def test_bad_keys_are_named(self):
        bad = self.probs(statusLevels=[{"name": "a", "kind": "unestablished"}],
                         preamble={"policy": "sometimes"}, notes={"maxLines": 0},
                         bib={"acceptedWarnings": "St84"}, labels=["thm"],
                         mainResults={"labels": [1]})
        text = "\n".join(bad)
        for frag in ("needs an env or a command", "exactly one level of kind established",
                     "preamble.policy", "notes.maxLines", "bib.acceptedWarnings",
                     "author.labels must be an object", "mainResults.labels"):
            self.assertIn(frag, text)
        self.assertIn("kind must be one of",
                      "\n".join(self.probs(statusLevels=[{"name": "x", "kind": "draft"}])))


if __name__ == "__main__":
    unittest.main()
