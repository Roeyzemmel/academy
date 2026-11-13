"""paper_diff.py: base selection, command construction, no mutation of the home, messages
(none needs TeX), and an end-to-end build skipped unless latexdiff and latexmk are present."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from fixtures import SCRIPTS, HAVE_GIT

sys.path.insert(0, SCRIPTS)
import paper_diff as pd  # noqa: E402

HAVE_TEX = bool(shutil.which("latexdiff") and shutil.which("latexmk"))

MAIN = (r"\documentclass{amsart}" "\n" r"\usepackage{amsthm}" "\n"
        r"\newtheorem{lem}{Lemma}" "\n"
        r"\begin{document}" "\n" r"\input{sections/a}" "\n" r"\end{document}" "\n")
A_OLD = (r"\begin{lem}\label{lem:x} Every $n\ge 2$ is a sum of two primes." "\n"
         r"\end{lem}" "\n" r"\[ \int_0^1 f(x)\,dx = 1 \]" "\n")
A_NEW = (r"\begin{lem}\label{lem:x} Every even $n\ge 4$ is a sum of two primes." "\n"
         r"\end{lem}" "\n" r"\[ \int_0^2 f(x)\,dx = 2 \]" "\n")

GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")


class Repo(object):
    """A temp git repo that is an Author home (main.tex + sections/a.tex)."""

    def __init__(self, config_author=None):
        self.dir = tempfile.mkdtemp(prefix="pdiff-")
        self.home = os.path.join(self.dir, "paper")
        os.makedirs(os.path.join(self.home, "sections"))
        os.makedirs(os.path.join(self.home, ".claude"))
        self.write("main.tex", MAIN)
        self.write("sections/a.tex", A_OLD)
        self.write(".gitignore", ".build/\n")
        cfg = {"schema": 1, "role": "author", "instance": "author@t", "domains": ["d"],
               "ns": "paper",
               "paths": {"tex": ["main.tex", "sections/*.tex"], "bib": "references.bib",
                         "drafts": "Drafts", "agenda": "Drafts/agenda.md",
                         "records": "claims", "views": []},
               "registry": {"profile": "paper", "root": "claims"},
               "author": dict({"main": "main.tex"}, **(config_author or {}))}
        self.write(".claude/academy.json", json.dumps(cfg))
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.commit("v1", "2026-01-01T10:00:00")

    def write(self, rel, text):
        path = os.path.join(self.home, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)

    def git(self, *args, **kw):
        env = dict(GIT_ENV, **kw.pop("env", {}))
        return subprocess.run(["git", "-C", self.home] + list(args), env=env, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE
                              ).stdout.decode().strip()

    def commit(self, msg, date):
        self.git("commit", "-q", "-am", msg, "--allow-empty",
                 env={"GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date})

    def tag(self, name, date):
        self.git("tag", "-a", name, "-m", name, env={"GIT_COMMITTER_DATE": date})

    def snapshot(self):
        """Everything paper_diff must leave alone."""
        files = {}
        for base, dirs, names in os.walk(self.home):
            dirs[:] = [d for d in dirs if d not in (".git", ".build")]
            for n in names:
                p = os.path.join(base, n)
                with open(p, "rb") as fh:
                    files[os.path.relpath(p, self.home)] = (fh.read(), os.stat(p).st_mtime_ns)
        return (files, self.git("status", "--porcelain"), self.git("rev-parse", "HEAD"),
                self.git("stash", "list"), self.git("for-each-ref"))

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def slurp(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = pd.main(argv)
    return code, out.getvalue(), err.getvalue()


@unittest.skipUnless(HAVE_GIT, "git not on PATH")
class BaseSelection(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.cleanup)

    def resolve(self, cli=None, settings=None):
        return pd.resolve_base(self.repo.home, cli, settings or {})

    def test_no_base_is_exit_1_with_a_hint(self):
        with self.assertRaises(pd.DiffError) as cm:
            self.resolve()
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("--base", str(cm.exception))
        self.assertIn("author.diff.base", str(cm.exception))
        self.assertNotIn("\n", str(cm.exception))

    def test_newest_matching_tag_wins(self):
        self.repo.tag("shared-1", "2026-01-02T10:00:00")
        self.repo.write("sections/a.tex", A_NEW)
        self.repo.commit("v2", "2026-02-01T10:00:00")
        self.repo.tag("round-2", "2026-02-02T10:00:00")
        self.repo.tag("other-3", "2026-03-01T10:00:00")  # not a base tag
        ref, sha, how = self.resolve()
        self.assertEqual(ref, "round-2")
        self.assertEqual(sha, self.repo.git("rev-parse", "round-2^{commit}"))
        self.assertEqual(how, "newest tag")

    def test_config_tag_patterns(self):
        self.repo.tag("milestone-1", "2026-01-02T10:00:00")
        self.assertEqual(self.resolve(settings={"diff": {"tags": ["milestone-*"]}})[0],
                         "milestone-1")

    def test_cli_beats_config_beats_tags(self):
        self.repo.tag("shared-1", "2026-01-02T10:00:00")
        self.repo.tag("mine", "2026-01-03T10:00:00")
        cfg = {"diff": {"base": "mine"}}
        self.assertEqual(self.resolve(settings=cfg)[0], "mine")
        self.assertEqual(self.resolve(cli="HEAD", settings=cfg)[0], "HEAD")
        self.assertEqual(self.resolve(cli="HEAD", settings=cfg)[2], "--base")

    def test_unknown_or_option_like_ref_is_exit_1(self):
        for ref in ("nonesuch", "--output=x"):
            with self.assertRaises(pd.DiffError) as cm:
                self.resolve(cli=ref)
            self.assertEqual(cm.exception.code, 1)


class Commands(unittest.TestCase):
    def test_latexdiff_command_flattens_old_then_new(self):
        cmd = pd.latexdiff_cmd("/old/main.tex", "/new/main.tex", ["--math-markup=whole"])
        self.assertEqual(cmd, ["latexdiff", "--flatten", "--math-markup=whole",
                               "/old/main.tex", "/new/main.tex"])

    def test_default_options_are_math_safe_and_overridable(self):
        self.assertIn("--math-markup=whole", pd.latexdiff_args({}))
        cfg = {"diff": {"args": ["--type=CFONT", "--math-markup=coarse"]}}
        self.assertEqual(pd.latexdiff_args(cfg), ["--type=CFONT", "--math-markup=coarse"])
        self.assertEqual(pd.latexdiff_args({"diff": {"args": []}}), [])

    def test_latexmk_command_builds_in_the_given_outdir(self):
        cmd = pd.latexmk_cmd(".build/diff/main-diff.tex", ".build/diff")
        self.assertEqual(cmd[:2], ["latexmk", "-pdf"])
        self.assertIn("-outdir=.build/diff", cmd)
        self.assertIn("-halt-on-error", cmd)
        self.assertEqual(cmd[-1], ".build/diff/main-diff.tex")


@unittest.skipUnless(HAVE_GIT and os.name != "nt", "git and a POSIX shell needed")
class WithFakeLatexdiff(unittest.TestCase):
    """latexdiff replaced by a stub on PATH: the plumbing without TeX."""

    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.cleanup)
        self.bin = tempfile.mkdtemp(prefix="pdiff-bin-")
        self.addCleanup(shutil.rmtree, self.bin, True)
        self.argv_file = os.path.join(self.bin, "argv.txt")
        self.set_stub('import sys\nopen(%r, "w").write("\\n".join(sys.argv[1:]))\n'
                      'print(open(sys.argv[-2]).read().replace("Every", "EVERY"))\n'
                      % self.argv_file)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = self.bin + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)

    def set_stub(self, body):
        path = os.path.join(self.bin, "latexdiff")
        with open(path, "w") as fh:
            fh.write("#!%s\n%s" % (sys.executable, body))
        os.chmod(path, 0o755)

    def test_no_build_writes_tex_and_leaves_the_home_alone(self):
        self.repo.git("tag", "shared-1")
        self.repo.write("sections/a.tex", A_NEW)            # uncommitted edit
        self.repo.write("sections/untracked.tex", "x\n")    # and an untracked file
        before = self.repo.snapshot()
        code, out, err = run_main(["--root", self.repo.home, "--no-build"])
        self.assertEqual(code, 0, err)
        self.assertEqual(self.repo.snapshot(), before)
        tex = out.strip()
        self.assertEqual(tex, os.path.join(self.repo.home, ".build", "diff", "main-diff.tex"))
        self.assertTrue(os.path.isfile(tex))
        argv = slurp(self.argv_file).split("\n")
        self.assertEqual(argv[0], "--flatten")
        old_main, new_main = argv[-2], argv[-1]
        self.assertEqual(new_main, os.path.join(self.repo.home, "main.tex"))
        self.assertNotEqual(os.path.dirname(old_main), self.repo.home)
        self.assertFalse(os.path.exists(old_main), "the temporary base tree is removed")

    def test_base_tree_is_the_committed_one(self):
        self.repo.git("tag", "shared-1")
        self.repo.write("sections/a.tex", A_NEW)
        self.set_stub('import sys\nprint(open(sys.argv[-2].replace("main.tex", '
                      '"sections/a.tex")).read())\n')
        code, out, err = run_main(["--root", self.repo.home, "--no-build", "--json"])
        self.assertEqual(code, 0, err)
        res = json.loads(out)
        self.assertEqual(res["base"], "shared-1")
        self.assertFalse(res["built"])
        text = slurp(res["diff_tex"])
        self.assertIn(r"\int_0^1", text)       # the base version, not the working tree
        self.assertNotIn(r"\int_0^2", text)

    def test_no_base_message_and_exit(self):
        code, out, err = run_main(["--root", self.repo.home, "--no-build"])
        self.assertEqual((code, out), (1, ""))
        self.assertIn("no diff base", err)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_latexdiff_failure_is_exit_1_diff_not_built(self):
        self.set_stub('import sys\nsys.stderr.write("boom\\n")\nsys.exit(3)\n')
        code, out, err = run_main(["--root", self.repo.home, "--base", "HEAD", "--no-build"])
        self.assertEqual(code, 1)
        self.assertIn("diff not built", err)
        self.assertIn("boom", err)

    def test_config_base_and_args_are_used(self):
        repo = Repo({"diff": {"base": "HEAD", "args": ["--type=CFONT"]}})
        self.addCleanup(repo.cleanup)
        code, out, err = run_main(["--root", repo.home, "--no-build"])
        self.assertEqual(code, 0, err)
        argv = slurp(self.argv_file).split("\n")
        self.assertIn("--type=CFONT", argv)
        self.assertNotIn("--math-markup=whole", argv)

    def test_not_a_git_repo_is_exit_2(self):
        plain = tempfile.mkdtemp(prefix="pdiff-plain-")
        self.addCleanup(shutil.rmtree, plain, True)
        with open(os.path.join(plain, "main.tex"), "w") as fh:
            fh.write(MAIN)
        code, _out, err = run_main(["--root", plain, "--base", "HEAD", "--no-build"])
        self.assertEqual(code, 2)
        self.assertIn("git", err)


@unittest.skipUnless(HAVE_GIT and HAVE_TEX, "latexdiff and latexmk needed")
class EndToEnd(unittest.TestCase):
    def test_diff_pdf_builds_for_a_changed_lemma_and_display_math(self):
        repo = Repo()
        self.addCleanup(repo.cleanup)
        repo.tag("shared-1", "2026-01-02T10:00:00")
        repo.write("sections/a.tex", A_NEW)
        repo.git("add", "-A")
        repo.commit("v2", "2026-02-01T10:00:00")
        before = repo.snapshot()
        out_pdf = os.path.join(repo.dir, "elsewhere", "changes.pdf")
        code, out, err = run_main(["--root", repo.home, "--out", out_pdf, "--json"])
        self.assertEqual(code, 0, err)
        self.assertEqual(repo.snapshot(), before)
        res = json.loads(out)
        self.assertTrue(res["built"])
        self.assertEqual(res["pdf"], out_pdf)
        self.assertGreater(os.path.getsize(out_pdf), 1000)
        tex = slurp(res["diff_tex"])
        self.assertNotIn(r"\input{sections/a}", tex)         # flattened
        self.assertIn(r"\DIFdel", tex)
        self.assertIn(r"\DIFadd", tex)
        self.assertTrue(os.path.isfile(os.path.join(repo.home, ".build", "diff",
                                                    "main-diff.pdf")))

    def test_broken_diff_reports_exit_1_with_the_tex_path(self):
        repo = Repo({"diff": {"args": ["--math-markup=whole", "--type=CFONT"]}})
        self.addCleanup(repo.cleanup)
        repo.write("sections/a.tex", A_NEW + r"\undefinedmacro{" "\n")  # breaks the build
        code, out, err = run_main(["--root", repo.home, "--base", "HEAD"])
        self.assertEqual(code, 1)
        self.assertIn("diff not built", err)
        self.assertIn("main-diff.tex", err)
        self.assertTrue(os.path.isfile(os.path.join(repo.home, ".build", "diff",
                                                    "main-diff.tex")))


if __name__ == "__main__":
    unittest.main()
