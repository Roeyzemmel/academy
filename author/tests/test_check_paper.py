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


class RegistryViewTests(unittest.TestCase):
    """Every parsed statement has a row in the generated view (2026-11-13: the statements
    of a file that opens its own \\section, input after another section of main.tex,
    were checked but had no row)."""

    def test_a_file_with_its_own_section_keeps_its_rows(self):
        tmp = tempfile.mkdtemp(prefix="cp-view-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "sections"))
        with open(os.path.join(tmp, "main.tex"), "w", encoding="utf-8") as fh:
            fh.write("\\documentclass{amsart}\n\\begin{document}\n\\section{Body}\n"
                     "\\input{sections/a}\n\\appendix\n\\input{sections/b}\n\\end{document}\n")
        with open(os.path.join(tmp, "sections", "a.tex"), "w", encoding="utf-8") as fh:
            fh.write("\\begin{lem}\\label{lem:a}\nA.\n\\end{lem}\n")
        with open(os.path.join(tmp, "sections", "b.tex"), "w", encoding="utf-8") as fh:
            fh.write("\\section{Basics}\n\\begin{lem}\\label{lem:b}\nB.\n\\end{lem}\n")
        view = os.path.join(tmp, "statements.md")
        code, out, err = run("--root", tmp, "--registry", view, "--no-log")
        with open(view, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("| `lem:a` |", text)
        self.assertIn("## Basics", text)
        self.assertIn("| `lem:b` |", text, out + err)
        self.assertLess(text.index("## Body"), text.index("## Basics"))


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
        # #110: a typed note, \\Claude[kind]{...}, is a machine note too
        self.assertTrue(cp.RE_CLAUDE.search("\\Claude[await]{T-0001}"))
        self.assertTrue(cp.RE_CLAUDE.search("\\Claude [prov] {x}"))
        self.assertFalse(cp.RE_CLAUDE.search("\\claim{x}"))
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



class LabelPrefixTests(unittest.TestCase):
    """W4: opt-in prefix rule (author.labels.enforcePrefixes)."""
    MAIN = "\\documentclass{amsart}\n\\begin{document}\n\\section{A}\\label{sec:a}\n" \
           "\\input{sections/a}\n\\end{document}\n"
    A = ("\\begin{thm}\\label{thm:x}\nA.\n\\end{thm}\n\\begin{proof}\nOk.\\end{proof}\n"
         "\\begin{lem}\\label{foo:y}\nB.\n\\end{lem}\n\\begin{proof}\nOk.\\end{proof}\n"
         "\\begin{lem}\\label{bare}\nC.\n\\end{lem}\n\\begin{proof}\nOk.\\end{proof}\n")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cp-prefix-")
        os.makedirs(os.path.join(self.tmp, "sections"))
        os.makedirs(os.path.join(self.tmp, ".claude"))
        for rel, text in (("main.tex", self.MAIN), ("sections/a.tex", self.A)):
            with open(os.path.join(self.tmp, rel), "w", newline="\n") as fh:
                fh.write(text)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        cp.configure(None)

    def run_with(self, labels):
        with open(os.path.join(self.tmp, ".claude", "academy.json"), "w") as fh:
            json.dump({"role": "author", "author": {"labels": labels}}, fh)
        return run("--root", self.tmp, "--no-log", "--no-registry")[1]

    def test_off_by_default(self):
        out = self.run_with({"prefixes": ["thm", "lem", "sec"]})
        self.assertNotIn("[W4]", out)

    def test_enforced_flags_unlisted_and_bare_labels(self):
        out = self.run_with({"prefixes": ["thm", "lem", "sec"], "enforcePrefixes": True})
        self.assertIn("foo:y: [W4]", out)
        self.assertIn("bare: [W4]", out)
        self.assertNotIn("thm:x: [W4]", out)
        self.assertNotIn("sec:a: [W4]", out)


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

    def test_the_note_switches_are_typed(self):
        self.assertEqual([], self.probs(notes={"maxLines": 3, "lineChars": 40,
                                               "enforce": True, "typed": False}))
        text = "\n".join(self.probs(notes={"lineChars": 0, "enforce": "false",
                                           "typed": "yes"}))
        for frag in ("notes.lineChars", "notes.enforce", "notes.typed"):
            self.assertIn(frag, text)
        self.assertIn("notes.lineChars", "\n".join(self.probs(notes={"lineChars": True})))
        self.assertEqual([], self.probs(notes={"maxAge": 0}))
        self.assertIn("notes.maxAge", "\n".join(self.probs(notes={"maxAge": -1})))
        self.assertIn("notes.maxAge", "\n".join(self.probs(notes={"maxAge": "14"})))
        self.assertIn("kind must be one of",
                      "\n".join(self.probs(statusLevels=[{"name": "x", "kind": "draft"}])))


#: the reword level (#137): a mark on a settled statement, generated from the stale list
REWORDED = {"name": "reworded", "kind": "mark", "command": "\\Reworded",
            "strike": "\\Struck", "colour": "violet", "requires": "stale",
            "generated": True, "statuses": ["proved", "proved-modulo"]}


class MarkLevelConfig(unittest.TestCase):
    """#137: ``author.statusLevels`` may hold one level of kind ``mark`` (``requires:
    "stale"``, ``generated: true``): no colour of a statement, so neither R1 nor the
    colour machinery reads it."""

    def setUp(self):
        import _academy as ac
        self.ac = ac
        self.addCleanup(cp.configure, None)

    def levels(self, **mark):
        return [dict(lv) for lv in cp.DEFAULT_STATUS_LEVELS] + [dict(REWORDED, **mark)]

    def test_the_reworded_level_validates(self):
        self.assertEqual([], self.ac.validate_author({"statusLevels": self.levels()}))
        lv = self.ac.author_mark_level({"statusLevels": self.levels()})
        self.assertEqual(("reworded", "\\Reworded", "\\Struck"),
                         (lv["name"], lv["command"], lv["strike"]))
        self.assertIsNone(self.ac.author_mark_level({}))          # opt-in: not a default
        self.assertIsNone(self.ac.author_mark_level(
            {"statusLevels": [dict(lv) for lv in cp.DEFAULT_STATUS_LEVELS]}))

    def test_a_bad_mark_level_is_named(self):
        cases = ((dict(requires="proved"), "requires must be \"stale\""),
                 (dict(generated=False), "generated must be true"),
                 (dict(env="reworded"), "a mark level has no env"),
                 (dict(command="\\Violet"), "command must be \\Reworded"),
                 (dict(strike="\\Gone"), "strike must be \\Struck"))
        for change, frag in cases:
            text = "\n".join(self.ac.validate_author({"statusLevels": self.levels(**change)}))
            self.assertIn(frag, text, change)
        two = self.levels() + [dict(REWORDED, name="again")]
        self.assertIn("at most one level of kind mark",
                      "\n".join(self.ac.validate_author({"statusLevels": two})))

    def test_the_mark_is_no_colour_of_a_statement(self):
        cp.configure({"statusLevels": self.levels()})
        self.assertNotIn("reworded", cp.LEVEL_KIND)
        self.assertNotIn("reworded", cp.LEVEL_ORDER)
        self.assertNotIn("\\Reworded{", cp.COLOUR_COMMANDS)
        self.assertEqual("reworded", cp.MARK_LEVEL["name"])
        cp.configure(None)
        self.assertIsNone(cp.MARK_LEVEL)


class RewordMarkRules(unittest.TestCase):
    """#137: with the mark level, W5 (a stale settled claim without marks) and R8 (marks
    on a claim that is not stale); the stale list is the registry's (injected here)."""

    BODY = ("\\begin{prop}\\label{prop:a}\nA \\Struck{old} \\Reworded{new} one.\n"
            "\\end{prop}\n\\begin{proof}\nOk.\n\\end{proof}\n"
            "\\begin{lem}\\label{lem:b}\nPlain.\n\\end{lem}\n"
            "\\begin{proof}\nOk.\n\\end{proof}\n")

    def paper(self):
        tmp = tempfile.mkdtemp(prefix="cp-marks-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "sections"))
        with open(os.path.join(tmp, "main.tex"), "w", encoding="utf-8") as fh:
            fh.write("\\documentclass{amsart}\n\\begin{document}\n"
                     "\\input{sections/a}\n\\end{document}\n")
        with open(os.path.join(tmp, "sections", "a.tex"), "w", encoding="utf-8") as fh:
            fh.write(self.BODY)
        return tmp, cp.build_paper(tmp)

    def setUp(self):
        self.addCleanup(cp.configure, None)
        cp.configure({"statusLevels": [dict(lv) for lv in cp.DEFAULT_STATUS_LEVELS]
                      + [dict(REWORDED)]})

    def stale(self, *labels):
        return {lab: {"status": "proved", "pass": "2026-11-01-T-0001"} for lab in labels}

    def test_marks_on_a_stale_claim_pass_and_a_stale_claim_without_them_warns(self):
        root, paper = self.paper()
        got = cp.rule_reword_marks(paper, root, stale=self.stale("prop:a", "lem:b"))
        self.assertEqual([(f.kind, f.severity, f.label) for f in got], [("W5", "W", "lem:b")])

    def test_marks_on_a_claim_that_is_not_stale_are_a_violation(self):
        root, paper = self.paper()
        got = cp.rule_reword_marks(paper, root, stale=self.stale())
        self.assertEqual([(f.kind, f.severity, f.label) for f in got], [("R8", "V", "prop:a")])

    def test_any_label_of_the_statement_names_its_claim(self):
        # a statement keeps an old label: the stale record may be the second one
        self.BODY = ("\\begin{prop}\\label{prop:new}\\label{prop:old}\nA \\Reworded{b}.\n"
                     "\\end{prop}\n\\begin{proof}\nOk.\n\\end{proof}\n"
                     "\\begin{lem}\\label{lem:c}\\label{lem:d}\nC.\n\\end{lem}\n"
                     "\\begin{proof}\nOk.\n\\end{proof}\n")
        root, paper = self.paper()
        got = cp.rule_reword_marks(paper, root, stale=self.stale("prop:old", "lem:d"))
        self.assertEqual([(f.kind, f.label) for f in got], [("W5", "lem:c")])

    def test_without_the_mark_level_nothing_is_checked(self):
        root, paper = self.paper()
        cp.configure(None)
        self.assertEqual(cp.rule_reword_marks(paper, root, stale=self.stale()), [])

    def test_the_marks_colour_nothing(self):
        _root, paper = self.paper()
        st = paper.by_label["prop:a"]
        self.assertEqual((st.colour, st.partly), (cp.ESTABLISHED, []))


class MarginOverflowScan(unittest.TestCase):
    """R7 must not run one synctex lookup per clipped fragment (a paper with
    ~1600 clipped margin lines took a quarter of an hour: the scan 'hung')."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        with open(os.path.join(self.root, "main.tex"), "w") as fh:
            fh.write("\\documentclass{article}\n")
        build = os.path.join(self.root, cp._build_rel("pdf").rsplit("/", 1)[0])
        os.makedirs(build, exist_ok=True)
        with open(cp._build_path(self.root, "pdf"), "wb") as fh:
            fh.write(b"%PDF")
        later = os.path.getmtime(os.path.join(self.root, "main.tex")) + 10
        os.utime(cp._build_path(self.root, "pdf"), (later, later))

    def scan(self, fragments):
        from unittest import mock
        calls = []

        def fake_synctex(root, page, x, y):
            calls.append(page)
            return "sections/a.tex", 100 + page

        with mock.patch.object(cp.shutil, "which", return_value="pdftohtml"),              mock.patch.object(cp, "_pdftohtml_fragments", return_value=fragments),              mock.patch.object(cp, "_resolve_synctex", side_effect=fake_synctex):
            return cp.rule_margin_overflow(self.root), calls

    def test_one_lookup_and_one_finding_per_page(self):
        frs = [(p, 26.0, 800.0 + i, "line %d" % i)
               for p in (4, 7) for i in range(500)]
        out, calls = self.scan(frs)
        self.assertEqual(sorted(calls), [4, 7])
        self.assertEqual(len(out), 2)
        self.assertEqual([(f.file, f.line) for f in out],
                         [("sections/a.tex", 104), ("sections/a.tex", 107)])
        self.assertIn("500 clipped fragments on p.4", out[0].message)

    def test_single_fragment_and_clean_pdf(self):
        out, calls = self.scan([(3, 1.0, 2.0, "x")])
        self.assertEqual(len(out), 1)
        self.assertIn("clipped text on p.3", out[0].message)
        out, calls = self.scan([])
        self.assertEqual((out, calls), ([], []))

    def test_budget_exhausted_falls_back_to_page_number(self):
        from unittest import mock
        with mock.patch.object(cp, "SYNCTEX_BUDGET_SECONDS", -1.0):
            out, calls = self.scan([(5, 1.0, 2.0, "x")])
        self.assertEqual(calls, [])
        self.assertEqual((out[0].file, out[0].line), ("", 0))
        self.assertIn("(p.5)", out[0].message)


if __name__ == "__main__":
    unittest.main()


class QuestionTests(unittest.TestCase):
    """A dependence on a question, or of a question, is undefined (the human, 2026-11-14):
    a lemma and a question that refer to each other are not a cycle, while two lemmas
    that do still are."""

    def check(self, body):
        tmp = tempfile.mkdtemp(prefix="cp-quest-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "sections"))
        with open(os.path.join(tmp, "main.tex"), "w", encoding="utf-8") as fh:
            fh.write("\\documentclass{amsart}\n\\begin{document}\n"
                     "\\input{sections/a}\n\\end{document}\n")
        with open(os.path.join(tmp, "sections", "a.tex"), "w", encoding="utf-8") as fh:
            fh.write(body)
        code, out, err = run("--root", tmp, "--no-log")
        self.assertIn("Parsed 2 theorem-like statements", out)
        return out + err

    def test_a_question_neither_depends_nor_is_depended_on(self):
        out = self.check(
            "\\begin{quest}\\label{quest:q}\nIs \\cref{lem:a} sharp?\n\\end{quest}\n"
            "\\begin{lem}\\label{lem:a}\nA, as asked in \\cref{quest:q}.\n\\end{lem}\n")
        self.assertNotIn("circular dependency", out)

    def test_two_lemmas_still_make_a_cycle(self):
        out = self.check(
            "\\begin{lem}\\label{lem:b}\nB, by \\cref{lem:a}.\n\\end{lem}\n"
            "\\begin{lem}\\label{lem:a}\nA, by \\cref{lem:b}.\n\\end{lem}\n")
        self.assertIn("circular dependency", out)


class ItemReferenceTests(unittest.TestCase):
    """#127: R1 on a reference to an item (``\\cref{it:x}``) of another statement: the
    item's registry status when the record has ``items``, else the statement's colour
    (a warning)."""

    BODY = ("\\begin{sketch}\n\\begin{prop}\\label{prop:u}\nThen\n\\begin{enumerate}\n"
            "\\item compact \\label{it:compact}\n\\item finite \\label{it:finite}\n"
            "\\end{enumerate}\n\\end{prop}\n\\end{sketch}\n"
            "\\begin{lem}\\label{lem:a}\nBy \\cref{it:compact}, A.\n\\end{lem}\n"
            "\\begin{proof}\nDone.\n\\end{proof}\n"
            "\\begin{lem}\\label{lem:b}\nBy \\cref{it:finite}, B.\n\\end{lem}\n"
            "\\begin{proof}\nDone.\n\\end{proof}\n")

    def check(self, record=None):
        tmp = tempfile.mkdtemp(prefix="cp-items-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "sections"))
        with open(os.path.join(tmp, "main.tex"), "w", encoding="utf-8") as fh:
            fh.write("\\documentclass{amsart}\n\\begin{document}\n"
                     "\\input{sections/a}\n\\end{document}\n")
        with open(os.path.join(tmp, "sections", "a.tex"), "w", encoding="utf-8") as fh:
            fh.write(self.BODY)
        if record is not None:
            os.makedirs(os.path.join(tmp, "claims", "paper"))
            with open(os.path.join(tmp, "claims", "paper", "prop__u.md"), "w",
                      encoding="utf-8") as fh:
                fh.write(record)
        code, out, err = run("--root", tmp, "--no-log", "--no-registry")
        return out + err

    def test_without_item_statuses_the_colour_gives_a_warning(self):
        out = self.check()
        self.assertIn("lem:a: [R1] established lem references item it:compact of sketch "
                      "prop:u", out)
        self.assertIn("no item status in the registry", out)

    def test_the_item_status_decides(self):
        out = self.check("---\nid: paper:prop:u\nstatus: sketch\nitems:\n"
                         "  compact: [proved]\n  finite: [sketch]\nlifecycle: active\n"
                         "---\n")
        self.assertNotIn("lem:a: [R1]", out)
        self.assertIn("lem:b: [R1] established lem references item it:finite of prop:u, "
                      "whose registry status is sketch", out)
