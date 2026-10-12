"""The git part of the lab template's provenance stamp (templates/lab/package/env.py).

A result must be stamped dirty when the code that produced it is not in the commit it
names: a tracked file changed, the running script untracked (or ignored), or an
untracked file under experiments/ or the lab's package. The stamp records which files,
so a reader can tell what the commit is missing. Ported, with its tests, from a lab's
reviewed fix of its own copy of env.py (T-0214) for T-0219. Each test scaffolds a lab
with /academy:init's scaffold_lab into a throwaway git repo and loads the scaffolded
env.py from there.

    py -m unittest tests.test_lab_env_git        (from scientist/)
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "academy" / "scripts"))

import init_instance  # noqa: E402

HAVE_GIT = shutil.which("git") is not None
PACKAGE = "mylab"


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def scaffold(home):
    """Scaffold a lab with package PACKAGE into `home`; returns its env module."""
    cfg = {"schema": 1, "role": "scientist", "instance": "scientist@mylab",
           "domains": ["dom"], "ns": "mylab",
           "paths": {"package": PACKAGE, "experiments": "experiments/*.py",
                     "results": "results", "queue": "queue", "records": "claims",
                     "views": []},
           "registry": {"profile": "lab", "root": "claims"},
           "scientist": {"envs": {"l": {"kind": "local"}},
                         "policy": {"probe": "l", "test": "l", "run": "l"}}}
    init_instance.scaffold_lab(str(home), cfg)
    path = Path(home) / PACKAGE / "env.py"
    spec = importlib.util.spec_from_file_location(
        "_lab_env_%d" % id(home), path)
    mod = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "dont_write_bytecode", True):
        spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAVE_GIT, "git is not on PATH")
class GitState(unittest.TestCase):
    """git_state on a throwaway repo holding a freshly scaffolded lab."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = Path(self._tmp.name).resolve() / "lab"
        self.repo.mkdir()
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.name", "test")
        _git(self.repo, "config", "user.email", "test@example.invalid")
        _git(self.repo, "config", "commit.gpgsign", "false")
        self.env = scaffold(self.repo)
        with open(self.repo / ".gitignore", "a", encoding="utf-8") as fh:
            fh.write("scratch/*\n")
        self.write("experiments/2026-01-01_old.py", "print(1)\n")
        self.write("README.md", "lab\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")

    def write(self, rel, text="x = 1\n"):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def state(self, script=None):
        return self.env.git_state(script=script, root=self.repo)

    # -- the template's own wiring --------------------------------------------------

    def test_code_dirs_are_experiments_and_the_package(self):
        self.assertEqual(self.env.CODE_DIRS, ("experiments", PACKAGE))

    def test_root_defaults_to_the_lab_root(self):
        self.write(f"{PACKAGE}/new_module.py")
        g = self.env.git_state()
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["untracked"], [f"{PACKAGE}/new_module.py"])

    def test_scaffolded_lab_ignores_bytecode_under_code_dirs(self):
        # importing the package writes <package>/__pycache__/: unignored, every run
        # that imports it would be stamped dirty
        for d in self.env.CODE_DIRS:
            self.write(f"{d}/__pycache__/m.cpython-313.pyc", "bytecode")
        self.write(f"{PACKAGE}/stale.pyc", "bytecode")
        g = self.state(self.repo / "experiments/2026-01-01_old.py")
        self.assertIs(g["dirty"], False)
        self.assertEqual(g["untracked"], [])

    # -- clean and tracked changes --------------------------------------------------

    def test_clean_tree(self):
        g = self.state(self.repo / "experiments/2026-01-01_old.py")
        self.assertRegex(g["commit"], r"^[0-9a-f]{4,}$")
        self.assertIs(g["dirty"], False)
        self.assertEqual(g["modified"], [])
        self.assertEqual(g["untracked"], [])

    def test_modified_tracked_file_is_dirty_and_listed(self):
        self.write("README.md", "changed\n")
        g = self.state()
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["modified"], ["README.md"])
        self.assertEqual(g["untracked"], [])

    def test_staged_new_file_is_dirty_and_listed_as_modified(self):
        self.write(f"{PACKAGE}/staged.py")
        _git(self.repo, "add", f"{PACKAGE}/staged.py")
        g = self.state()
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["modified"], [f"{PACKAGE}/staged.py"])

    # -- untracked files (the defect of T-0214 / T-0219) ----------------------------

    def test_untracked_running_script_in_experiments_is_dirty(self):
        s = self.write("experiments/2026-10-10_new.py")
        g = self.state(s)
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["untracked"], ["experiments/2026-10-10_new.py"])
        self.assertEqual(g["modified"], [])

    def test_untracked_file_under_experiments_is_dirty_without_script(self):
        self.write("experiments/helper_data.py")
        g = self.state()
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["untracked"], ["experiments/helper_data.py"])

    def test_untracked_file_deep_under_the_package_is_dirty(self):
        self.write(f"{PACKAGE}/sub/new_module.py")
        g = self.state(self.repo / "experiments/2026-01-01_old.py")
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["untracked"], [f"{PACKAGE}/sub/new_module.py"])

    def test_untracked_running_script_elsewhere_is_dirty(self):
        s = self.write("tools/one_off.py")
        g = self.state(s)
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["untracked"], ["tools/one_off.py"])

    def test_ignored_running_script_is_dirty(self):
        # scratch/ is gitignored: a script there is never in any commit
        s = self.write("scratch/probe.py")
        g = self.state(s)
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["untracked"], ["scratch/probe.py"])

    def test_relative_script_path_is_resolved(self):
        self.write("experiments/2026-10-10_rel.py")
        cwd = os.getcwd()   # contextlib.chdir is 3.11+
        os.chdir(self.repo)
        try:
            g = self.state("experiments/2026-10-10_rel.py")
        finally:
            os.chdir(cwd)
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["untracked"], ["experiments/2026-10-10_rel.py"])

    def test_path_with_space_is_recorded_verbatim(self):
        self.write("experiments/with space.py")
        g = self.state()
        self.assertEqual(g["untracked"], ["experiments/with space.py"])

    def test_untracked_results_and_other_files_are_not_dirty(self):
        # results are written by runs; notes outside the code are not code
        self.write("results/2026-10-10_x.json", "{}")
        self.write("notes.txt", "todo\n")
        g = self.state(self.repo / "experiments/2026-01-01_old.py")
        self.assertIs(g["dirty"], False)
        self.assertEqual(g["untracked"], [])

    def test_ignored_files_under_the_package_are_not_dirty(self):
        self.write(f"{PACKAGE}/__pycache__/env.cpython-313.pyc", "bytecode")
        self.write("scratch/leftover.py")
        g = self.state(self.repo / "experiments/2026-01-01_old.py")
        self.assertIs(g["dirty"], False)
        self.assertEqual(g["untracked"], [])

    def test_lists_are_sorted_and_without_duplicates(self):
        s = self.write("experiments/b.py")
        self.write(f"{PACKAGE}/a.py")
        self.write("experiments/a.py")
        g = self.state(s)
        self.assertEqual(g["untracked"], ["experiments/a.py", "experiments/b.py",
                                          f"{PACKAGE}/a.py"])

    def test_script_outside_the_repo_is_dirty(self):
        # the commit cannot hold a script outside the repo
        outside = Path(self._tmp.name) / "elsewhere.py"
        outside.write_text("x = 1\n", encoding="utf-8")
        g = self.state(outside)
        self.assertIsNotNone(g)
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["untracked"], [outside.resolve().as_posix()])

    def test_root_below_the_top_level_reports_top_level_paths(self):
        # root need not be the git top level. A lab in the subdirectory sub/: its
        # CODE_DIRS are sub/experiments and sub/<package>, and every path is
        # reported relative to the top level.
        self.write("sub/README.md", "lab\n")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "lab subdir")
        self.write("sub/experiments/2026-10-10_new.py")
        self.write("experiments/2026-10-10_outer.py")   # not under the lab's dirs
        self.write("README.md", "changed\n")
        s = self.write("sub/tools/run_me.py")
        g = self.env.git_state(script=s, root=self.repo / "sub")
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["modified"], ["README.md"])
        self.assertEqual(g["untracked"], ["sub/experiments/2026-10-10_new.py",
                                          "sub/tools/run_me.py"])

    def test_outside_git_returns_none(self):
        plain = Path(self._tmp.name) / "plain"
        plain.mkdir()
        # GIT_CEILING_DIRECTORIES stops git from finding a repo above the temp dir
        with mock.patch.dict("os.environ",
                             {"GIT_CEILING_DIRECTORIES": str(Path(self._tmp.name))}):
            self.assertIsNone(self.env.git_state(root=plain))

    def test_modified_running_script_is_modified_not_untracked(self):
        # a tracked script edited after the commit: the commit holds another version
        s = self.write("experiments/2026-01-01_old.py", "print(2)\n")
        g = self.state(s)
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["modified"], ["experiments/2026-01-01_old.py"])
        self.assertEqual(g["untracked"], [])

    def test_touched_but_unchanged_file_is_not_dirty(self):
        # a new mtime with the committed content: the commit still holds this code
        p = self.repo / PACKAGE / "__init__.py"
        st = p.stat()
        os.utime(p, (st.st_atime + 100, st.st_mtime + 100))
        g = self.state(self.repo / "experiments/2026-01-01_old.py")
        self.assertIs(g["dirty"], False)
        self.assertEqual(g["modified"], [])

    def test_non_ascii_path_is_recorded_verbatim(self):
        # without -z git would octal-quote it ("experiments/\303\261.py")
        self.write("experiments/ñ_σ.py")
        g = self.state()
        self.assertEqual(g["untracked"], ["experiments/ñ_σ.py"])

    def test_untracked_script_and_modified_file_are_both_listed(self):
        s = self.write("scratch/probe.py")
        self.write(f"{PACKAGE}/__init__.py", "X = 1\n")
        g = self.state(s)
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["modified"], [f"{PACKAGE}/__init__.py"])
        self.assertEqual(g["untracked"], ["scratch/probe.py"])

    def test_script_in_a_nested_worktree_is_dirty(self):
        # a script under .worktrees/<w>/ (a separate checkout, ignored by the lab)
        # is not in the commit of `root`, yet `ls-files --others` does not descend
        # into the nested repository: git_state asks "is the script tracked here?"
        with open(self.repo / ".gitignore", "a", encoding="utf-8") as fh:
            fh.write(".worktrees/\n")
        _git(self.repo, "commit", "-q", "-am", "ignore worktrees")
        _git(self.repo, "worktree", "add", "-q", "-b", "feat",
             str(self.repo / ".worktrees" / "w"))
        s = self.write(".worktrees/w/experiments/2026-10-10_new.py")
        g = self.state(s)
        self.assertIs(g["dirty"], True)
        self.assertEqual(g["untracked"], [".worktrees/w/experiments/2026-10-10_new.py"])

    # -- through provenance / save_result / banner ----------------------------------

    def test_save_result_stamps_untracked_script_dirty(self):
        s = self.write("experiments/2026-10-10_defn_test.py")
        with contextlib.redirect_stdout(io.StringIO()):
            p = self.env.save_result("r", {"ok": True}, script=s,
                                     base=self.repo / "results")
        prov = json.loads(p.read_text(encoding="utf-8"))["provenance"]
        self.assertEqual(prov["script"], "experiments/2026-10-10_defn_test.py")
        self.assertIs(prov["git"]["dirty"], True)
        self.assertEqual(prov["git"]["untracked"],
                         ["experiments/2026-10-10_defn_test.py"])

    def test_provenance_of_a_script_outside_the_lab_stamps_it_dirty(self):
        outside = Path(self._tmp.name) / "elsewhere.py"
        outside.write_text("x = 1\n", encoding="utf-8")
        p = self.env.provenance(outside)
        self.assertIs(p["git"]["dirty"], True)
        self.assertEqual(p["git"]["untracked"], [outside.resolve().as_posix()])

    def test_banner_names_the_uncommitted_files(self):
        s = self.write("experiments/2026-10-10_new.py")
        self.write("README.md", "changed\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.env.banner(s)
        text = out.getvalue()
        self.assertIn("(dirty)", text)
        self.assertIn("untracked (not in commit", text)
        self.assertIn("experiments/2026-10-10_new.py", text)
        self.assertIn("modified (not in commit", text)
        self.assertIn("README.md", text)

    def test_banner_of_a_clean_tree_names_no_files(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.env.banner(self.repo / "experiments/2026-01-01_old.py")
        text = out.getvalue()
        self.assertNotIn("(dirty)", text)
        self.assertNotIn("not in commit", text)



class ScaffoldGitignore(unittest.TestCase):
    """Added by the test-engineer's review of T-0219: the scaffold writes the
    bytecode .gitignore into a fresh lab, and leaves a lab's own .gitignore alone
    (the developer's claim (2) on the ticket thread; scaffold_tree never overwrites)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name).resolve() / "lab"
        self.home.mkdir()

    def test_fresh_lab_gets_the_gitignore(self):
        with mock.patch.object(sys, "dont_write_bytecode", True):
            scaffold(self.home)
        text = (self.home / ".gitignore").read_text(encoding="utf-8")
        lines = text.splitlines()
        self.assertIn("__pycache__/", lines)
        self.assertIn("*.py[cod]", lines)

    def test_existing_gitignore_is_kept_byte_for_byte(self):
        own = b"# the lab's own\r\nresults/big/\r\n"
        (self.home / ".gitignore").write_bytes(own)
        made = init_instance.scaffold_lab(str(self.home), {
            "instance": "scientist@mylab", "ns": "mylab",
            "paths": {"package": PACKAGE}})
        self.assertEqual((self.home / ".gitignore").read_bytes(), own)
        self.assertNotIn(".gitignore", [Path(m).name for m in made])
        # the package and its env.py are still scaffolded next to it
        self.assertTrue((self.home / PACKAGE / "env.py").is_file())


if __name__ == "__main__":
    unittest.main()
