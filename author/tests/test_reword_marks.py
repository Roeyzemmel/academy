"""reword_marks.py (#137): the reword marks of the paper's stale settled statements.

A proved / proved-modulo statement reworded after its review keeps its status colour; the
words changed since the reviewed text are wrapped in ``\\Reworded{...}`` and the removed
ones shown as ``\\Struck{...}``. The marks are generated from the stale list and the
reviewed text recovered exactly from the paper's git history (its hash must be the base
pass's), never typed; they never move the statement hash, and they go when the claim is
no longer stale.
"""

import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fixtures import REPO, SCRIPTS, Sandbox, HAVE_GIT  # noqa: E402
import reword_marks as rm  # noqa: E402

ENGINE = os.path.join(REPO, "academy")

TEX_OLD = ("\\section{A}\n\n"
           "\\begin{prop}[Lifting]\\label{prop:foo} \\label{prop:alias}\n"
           "Let $X$ be a compact surface. Then every \\emph{flat morphism} lifts\n"
           "by \\cref{lem:bar}.\n"
           "\\end{prop}\n\n"
           "\\begin{proof}\nEasy.\n\\end{proof}\n\n"
           "\\begin{lem}\\label{lem:bar}\nBar holds.\n\\end{lem}\n")
TEX_NEW = TEX_OLD.replace("compact surface", "closed surface").replace(
    "\\emph{flat morphism} lifts\nby", "\\emph{flat map} lifts\nas shown by")
PREAMBLE = ("\\documentclass{amsart}\n\\usepackage{xcolor,soul}\n"
            "\\NewDocumentCommand{\\Reworded}{m}{\\textcolor{violet}{#1}}\n"
            "\\NewDocumentCommand{\\Struck}{m}{{\\st{#1}}}\n"
            "\\begin{document}\n\\input{sections/a}\n\\end{document}\n")
REWORDED = {"name": "reworded", "kind": "mark", "command": "\\Reworded",
            "strike": "\\Struck", "colour": "violet", "requires": "stale",
            "generated": True, "statuses": ["proved", "proved-modulo"]}
LEVELS = [{"name": "established", "colour": "black", "kind": "established",
           "statuses": ["proved"]},
          {"name": "sketch", "env": "sketch", "command": "\\Sketch", "colour": "blue",
           "kind": "unestablished", "statuses": ["sketch", "proved-modulo"]}]
RUN = ("---\nsubject: paper:{label}\npass: {pass_}\nrun: {run}\nrun_id: rv-20261101-0000{n}"
       "-{low}\nverdict: CONFIRMED\nmodulo: []\nmodel: claude-opus-5-5\nstatement_hash: "
       "{h}\n{extra}agent: expert:rigor-reviewer\nlanded: 2026-11-01\n---\n\nVerdict.\n")


class Units(unittest.TestCase):
    """The diff on balanced units, and what is never wrapped."""

    def test_changed_words_are_reworded_and_removed_ones_struck(self):
        old = "\\begin{prop}\\label{p}\nA compact surface lifts.\n\\end{prop}"
        new = "\\begin{prop}\\label{p}\nA closed surface lifts.\n\\end{prop}"
        marked, rep = rm.mark(old, new)
        self.assertIn("A \\Struck{compact} \\Reworded{closed} surface", marked)
        self.assertEqual((rep["reworded"], rep["struck"], rep["unmarked"]), (1, 1, []))
        self.assertEqual(rm.hash_of(marked), rm.hash_of(new))
        self.assertEqual(rm.strip_in_place(marked), new)

    def test_a_formula_or_a_group_is_one_unit_and_struck_macros_are_boxed(self):
        old = "\\begin{lem}\\label{l}\nFor $x \\in X$ see \\emph{the old map} \\cite[Thm 3]{K}.\n\\end{lem}"
        new = "\\begin{lem}\\label{l}\nFor $x \\in Y$ see \\emph{the new map} \\cite[Thm 4]{K}.\n\\end{lem}"
        marked, rep = rm.mark(old, new)
        self.assertIn("\\Struck{\\mbox{$x \\in X$}} \\Reworded{$x \\in Y$}", marked)
        self.assertIn("\\Struck{\\mbox{\\emph{the old map}} \\mbox{\\cite[Thm 3]{K}.}} "
                      "\\Reworded{\\emph{the new map} \\cite[Thm 4]{K}.}", marked)
        self.assertEqual(rm.hash_of(marked), rm.hash_of(new))

    def test_structure_is_never_wrapped(self):
        old = ("\\begin{lem}[Old title]\\label{l}\nA.\n\\begin{enumerate}[label=(a)]\n"
               "\\item x\n\\end{enumerate}\n% a comment\n\\end{lem}")
        new = ("\\begin{prop}[New title]\\label{l}\\label{l2}\nA.\n"
               "\\begin{enumerate}[label=(i)]\n\\item x\n\\item y\n\\end{enumerate}\n"
               "% another comment\n\\end{prop}")
        marked, rep = rm.mark(old, new)
        # the title's words are words; the environment, labels, items, list options and
        # comments are not
        self.assertIn("\\begin{prop}[\\Struck{Old }\\Reworded{New} title]", marked)
        self.assertEqual(rm.strip_in_place(marked), new)
        self.assertIn("\\item \\Reworded{y}", marked)
        for tok in ("\\begin{prop}", "\\label{l2}", "\\item", "[label=(i)]",
                    "% another comment", "\\end{prop}"):
            self.assertIn(tok, marked)
            self.assertNotIn("\\Reworded{" + tok, marked)
        self.assertTrue(any("\\label{l2}" in u for u in rep["unmarked"]), rep)
        self.assertEqual(rm.hash_of(marked), rm.hash_of(new))

    def test_display_math_is_coloured_but_never_struck(self):
        old = "\\begin{lem}\\label{l}\nThen\n\\[ a = \\left( b \\right) \\]\nholds.\n\\end{lem}"
        new = "\\begin{lem}\\label{l}\nThen\n\\[ a = \\left( c \\right) \\]\nholds.\n\\end{lem}"
        marked, rep = rm.mark(old, new)
        self.assertNotIn("\\Struck", marked)
        self.assertNotIn("\\Reworded{\\left", marked)       # unpaired \left: left alone
        self.assertIn("\\Reworded{c}", marked)
        self.assertTrue(any(u.startswith("removed") for u in rep["unmarked"]), rep)
        old2 = old.replace("\\left( b \\right)", "b + d")
        new2 = old.replace("\\left( b \\right)", "b + e")
        self.assertIn("\\Reworded{e}", rm.mark(old2, new2)[0])
        aligned = ("\\begin{lem}\\label{l}\n\\begin{align*} a &= %s \\end{align*}\n\\end{lem}")
        m3, _r = rm.mark(aligned % "b", aligned % "c")
        self.assertIn("\\Reworded{c}", m3)
        m4, r4 = rm.mark(aligned % "b &= 1", aligned % "b &= 2")
        self.assertIn("\\Reworded{2}", m4)
        self.assertNotIn("\\Reworded{&", m4)

    def test_strip_in_place_restores_the_text_exactly(self):
        new = TEX_NEW
        marked, _rep = rm.mark(TEX_OLD, new)
        self.assertNotEqual(marked, new)
        self.assertEqual(rm.strip_in_place(marked), new)
        self.assertEqual(rm.strip_in_place(new), new)


@unittest.skipUnless(HAVE_GIT, "git not available")
class RewordMarks(unittest.TestCase):
    """The script on a paper home in git, against a library's review passes."""

    def setUp(self):
        self.sb = Sandbox()
        self.addCleanup(self.sb.cleanup)
        self.home, self.lib = self.sb.home, os.path.join(self.sb.root, "lib")
        self.tex = os.path.join(self.home, "sections", "a.tex")
        self.sb.write(os.path.join(self.lib, ".claude", "academy.json"),
                      json.dumps({"role": "expert", "instance": "expert@t",
                                  "paths": {"reviews": "reviews"}}))
        self.sb.write(os.path.join(self.home, "main.tex"), PREAMBLE)
        self.sb.write(os.path.join(self.home, "claims", "paper", "prop__foo.md"),
                      "---\nid: paper:prop:foo\ntitle: prop:foo\nstatus: proved\n"
                      "where: sections/a.tex\nhistory:\n  - 2026-11-02 | proved | x\n---\n")
        self.sb.write(self.tex, TEX_OLD)
        self.sb.git_init(self.home)
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "reviewed")
        self.h_old = self.hash_now()
        self.blind_pass("2026-11-01-T-0001", self.h_old)
        self.sb.write(self.tex, TEX_NEW)
        self.h_new = self.hash_now()
        self.assertNotEqual(self.h_old, self.h_new)

    def git(self, *args):
        subprocess.run(["git", "-C", self.home] + list(args), check=True,
                       capture_output=True)

    def env(self):
        return dict(self.sb.env, ACADEMY_ROOT=REPO)

    def hash_now(self, label="prop:foo"):
        code = ("import sys; sys.path.insert(0, %r)\nimport registry\n"
                "from registry.core import federation\nregistry.clear_cache()\n"
                "print(federation.store('paper', %r).statement_hash(%r))"
                % (ENGINE, self.home, label))
        res = subprocess.run([sys.executable, "-c", code], capture_output=True,
                             env=self.env())
        self.assertEqual(res.returncode, 0, res.stderr.decode())
        return res.stdout.decode().strip()

    def run_record(self, pass_, run, h, extra=""):
        d = os.path.join(self.lib, "reviews", "paper", "prop-foo", pass_)
        self.sb.write(os.path.join(d, run + ".md"), RUN.format(
            label="prop:foo", pass_=pass_, run=run, n=ord(run) - 64, low=run.lower(), h=h,
            extra=extra))
        return d

    def blind_pass(self, pass_, h):
        for run in "AB":
            d = self.run_record(pass_, run, h)
        self.sb.write(os.path.join(d, "decision.md"), "# decision\n\n- outcome: `confirmed`\n")

    def reword_pass(self, pass_, base, base_hash, h):
        d = self.run_record(pass_, "R", h, extra="mode: reword\nbase_pass: %s\nbase_hash: %s\n"
                            "reword_scope: equivalent\n" % (base, base_hash))
        self.sb.write(os.path.join(d, "decision.md"), "# decision\n\noutcome `confirmed`\n")

    def configure(self, mark=True):
        levels = LEVELS + ([REWORDED] if mark else [])
        cfg = json.loads(self.sb.read(os.path.join(self.home, ".claude", "academy.json")))
        cfg["author"]["statusLevels"] = levels
        self.sb.write(os.path.join(self.home, ".claude", "academy.json"), json.dumps(cfg))

    def script(self, *args):
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "reword_marks.py"),
                              "--home", self.home] + list(args), capture_output=True,
                             env=self.env(), timeout=120)
        return res.returncode, res.stdout.decode("utf-8"), res.stderr.decode("utf-8")

    def test_the_dry_run_prints_the_diff_and_writes_nothing(self):
        code, out, err = self.script()
        self.assertEqual(code, 0, out + err)
        self.assertIn("1 to mark", out)
        self.assertIn("[-compact-] {+closed+}", out)          # reviews.py's word diff
        self.assertIn("\\Struck{compact} \\Reworded{closed}", out)
        self.assertIn("reviewed text: sections/a.tex at", out)
        self.assertIn("--apply refuses", out)                  # no mark level yet
        self.assertEqual(self.sb.read(self.tex), TEX_NEW)
        data = json.loads(self.script("--json")[1])
        (item,) = data["items"]
        self.assertEqual((item["qid"], item["pass_hash"], item["hash"]),
                         ("paper:prop:foo", self.h_old, self.h_new))

    def test_apply_needs_the_mark_level_and_the_macros(self):
        code, _out, err = self.script("--apply")
        self.assertEqual(code, 2)
        self.assertIn("no level of kind mark", err)
        self.configure()
        self.sb.write(os.path.join(self.home, "main.tex"),
                      "\\documentclass{amsart}\n\\begin{document}\n\\end{document}\n")
        code, _out, err = self.script("--apply")
        self.assertEqual(code, 2)
        self.assertIn("preamble defines no", err)
        self.assertEqual(self.sb.read(self.tex), TEX_NEW)

    def test_apply_writes_the_marks_without_moving_the_hash_and_is_idempotent(self):
        self.configure()
        code, out, err = self.script("--apply")
        self.assertEqual(code, 0, out + err)
        text = self.sb.read(self.tex)
        self.assertIn("\\Struck{compact} \\Reworded{closed} surface", text)
        self.assertIn("\\Struck{\\mbox{\\emph{flat morphism}}} \\Reworded{\\emph{flat map}}",
                      text)
        self.assertIn("\\Reworded{as shown}", text)
        self.assertIn("\\begin{proof}\nEasy.\n\\end{proof}", text)   # the proof untouched
        self.assertEqual(self.hash_now(), self.h_new)
        self.assertEqual(self.script("--apply")[0], 0)
        self.assertEqual(self.sb.read(self.tex), text)                 # nothing new

    def test_the_marks_go_when_the_reword_pass_confirms(self):
        self.configure()
        self.script("--apply")
        self.assertIn("\\Reworded", self.sb.read(self.tex))
        self.reword_pass("2026-11-05-T-0002-reword", "2026-11-01-T-0001", self.h_old,
                         self.h_new)
        code, out, err = self.script("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertIn("no longer stale: its marks were removed", out)
        self.assertEqual(self.sb.read(self.tex), TEX_NEW)

    def test_a_statement_whose_reviewed_text_is_not_recovered_is_never_touched(self):
        self.configure()
        # the pass hashed a text no commit holds (a hand-copied extract, T-0464)
        for run in "AB":
            self.run_record("2026-11-01-T-0001", run, "0123456789abcdef")
        code, out, _err = self.script("--apply")
        self.assertEqual(code, 1)
        self.assertIn("cannot be recovered", out)
        self.assertEqual(self.sb.read(self.tex), TEX_NEW)

    def test_the_reviewed_text_is_found_on_any_ref(self):
        # the reviewed wording is reachable only from a side branch
        self.git("branch", "side")
        self.git("checkout", "-q", "--orphan", "fresh")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "fresh")
        self.git("branch", "-qD", "main")
        code, out, err = self.script()
        self.assertEqual(code, 0, out + err)
        self.assertIn("\\Struck{compact} \\Reworded{closed}", out)


    def test_an_environment_with_two_records_is_marked_once_and_kept(self):
        # prop:alias labels the same environment (an old label kept); it is not stale
        self.sb.write(os.path.join(self.home, "claims", "paper", "prop__alias.md"),
                      "---\nid: paper:prop:alias\ntitle: prop:alias\nstatus: sketch\n"
                      "where: sections/a.tex\nhistory:\n  - 2026-11-02 | sketch | x\n---\n")
        self.configure()
        code, out, err = self.script("--apply")
        self.assertEqual(code, 0, out + err)
        once = self.sb.read(self.tex)
        self.assertEqual(once.count("\\Reworded{closed}"), 1)
        self.assertIn("\\begin{proof}\nEasy.\n\\end{proof}", once)
        code, out, err = self.script("--apply")           # the alias's marks are the stale
        self.assertEqual(code, 0, out + err)              # claim's: never removed
        self.assertNotIn("its marks were removed", out)
        self.assertEqual(self.sb.read(self.tex), once)
        _code, cp_out = self.check_paper()
        self.assertNotIn("[R8]", cp_out)
        self.assertNotIn("[W5]", cp_out)

    def test_apply_refuses_a_write_that_would_move_a_hash(self):
        self.configure()
        env = TEX_NEW[TEX_NEW.index("\\begin{prop}"):TEX_NEW.index("\\end{prop}") + 10]
        bad = env.replace("closed", "\\Reworded{closed} extra")
        result = {"items": [{"label": "prop:foo", "marked": bad}], "remove": [], "kept": []}
        problems = rm.apply(self.home, {}, result)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("would move", problems[0])
        self.assertEqual(self.sb.read(self.tex), TEX_NEW)

    def check_paper(self):
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_paper.py"),
                              "--root", self.home, "--no-log", "--no-registry"],
                             capture_output=True, env=self.env(), timeout=300)
        return res.returncode, res.stdout.decode("utf-8") + res.stderr.decode("utf-8")

    def test_check_paper_warns_on_a_stale_claim_without_marks(self):
        self.configure()
        _code, out = self.check_paper()
        self.assertIn("prop:foo: [W5]", out)
        self.assertIn("reword_marks.py --apply", out)
        self.script("--apply")
        _code, out = self.check_paper()
        self.assertNotIn("[W5]", out)
        self.assertNotIn("[R8]", out)

    def test_check_paper_fails_marks_on_a_claim_that_is_not_stale(self):
        self.configure()
        self.script("--apply")
        self.reword_pass("2026-11-05-T-0002-reword", "2026-11-01-T-0001", self.h_old,
                         self.h_new)
        code, out = self.check_paper()
        self.assertEqual(code, 1, out)
        self.assertIn("prop:foo: [R8]", out)
        self.script("--apply")
        code, out = self.check_paper()
        self.assertNotIn("[R8]", out)

    def test_check_paper_ignores_marks_without_the_mark_level(self):
        self.configure(mark=False)
        _code, out = self.check_paper()
        self.assertNotIn("[W5]", out)


if __name__ == "__main__":
    unittest.main()
