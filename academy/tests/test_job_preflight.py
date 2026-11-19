"""job_preflight.py: a scheduled or manual job's first step checks that the workspace is
there (checkout, populated submodules, the board repo readable through gh) and, when it is
not, says FAILED on its first line with the manual command to run (T-1673: the nightly
reported SUCCEEDED after 15 s with no repository attached). Temp directories and a fake
``gh`` on PATH only."""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import contextlib
import io

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
SCRIPT = os.path.join(SCRIPTS, "job_preflight.py")
sys.path.insert(0, SCRIPTS)

import job_preflight as jp  # noqa: E402

GITMODULES = """[submodule "academy"]
\tpath = academy
\turl = https://example.invalid/academy.git
[submodule "library"]
\tpath = library
\turl = https://example.invalid/library.git
"""

FAKE_GH = """#!/bin/sh
# answers like gh: ok for the repo named in $FAKE_GH_OK, 403 otherwise
case "$*" in
  *"repos/$FAKE_GH_OK"*) echo "$FAKE_GH_OK"; exit 0 ;;
esac
echo 'gh: GitHub access to this repository is not enabled for this session (HTTP 403)' >&2
exit 1
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="preflight-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ws = os.path.join(self.tmp, "ws")
        self.bin = os.path.join(self.tmp, "bin")
        write(os.path.join(self.ws, ".gitmodules"), GITMODULES)
        write(os.path.join(self.ws, "workspace.json"),
              json.dumps({"board": {"backend": "github", "repo": "owner/ws"}}))
        write(os.path.join(self.bin, "gh"), FAKE_GH)
        os.chmod(os.path.join(self.bin, "gh"), stat.S_IRWXU)
        self.env = dict(os.environ, PATH=self.bin + os.pathsep + os.environ.get("PATH", ""),
                        FAKE_GH_OK="owner/ws")

    def populate(self, *subs):
        for s in subs:
            write(os.path.join(self.ws, s, ".git"), "gitdir: ../.git/modules/%s\n" % s)
            write(os.path.join(self.ws, s, "README.md"), "x\n")

    def run_script(self, *args, env=None):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True,
                              env=env or self.env, cwd=self.tmp)


class CheckTests(Base):
    def test_all_present_is_ok(self):
        self.populate("academy", "library")
        p = self.run_script("--workspace", self.ws, "--job", "nightly-inbox")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(p.stdout.startswith("PREFLIGHT OK: nightly-inbox"), p.stdout)
        self.assertIn("owner/ws", p.stdout)

    def test_missing_workspace_fails_with_manual_command(self):
        p = self.run_script("--workspace", os.path.join(self.tmp, "absent"), "--job", "nightly-inbox")
        self.assertEqual(p.returncode, jp.FAILED_EXIT)
        first = p.stdout.splitlines()[0]
        self.assertTrue(first.startswith("FAILED: nightly-inbox could not start"), first)
        self.assertIn("no workspace checkout", first)
        self.assertIn("/run-nightly-inbox", p.stdout)

    def test_empty_submodule_named(self):
        self.populate("academy")
        os.makedirs(os.path.join(self.ws, "library"))
        p = self.run_script("--workspace", self.ws, "--job", "weekly-usage")
        self.assertEqual(p.returncode, jp.FAILED_EXIT)
        self.assertIn("submodule not populated: library", p.stdout.splitlines()[0])
        self.assertNotIn("academy", p.stdout.splitlines()[0].split("not populated:")[1])

    def test_need_restricts_the_submodules(self):
        self.populate("library")
        p = self.run_script("--workspace", self.ws, "--job", "weekly-usage", "--need", "library")
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_need_unknown_submodule_fails(self):
        self.populate("academy", "library")
        p = self.run_script("--workspace", self.ws, "--job", "x", "--need", "nope")
        self.assertEqual(p.returncode, jp.FAILED_EXIT)
        self.assertIn("nope", p.stdout.splitlines()[0])

    def test_gh_403_fails_with_its_message(self):
        self.populate("academy", "library")
        env = dict(self.env, FAKE_GH_OK="someone/else")
        p = self.run_script("--workspace", self.ws, "--job", "nightly-inbox", env=env)
        self.assertEqual(p.returncode, jp.FAILED_EXIT)
        first = p.stdout.splitlines()[0]
        self.assertIn("cannot read owner/ws", first)
        self.assertIn("not enabled for this session", first)

    def test_gh_absent_fails(self):
        self.populate("academy", "library")
        os.remove(os.path.join(self.bin, "gh"))
        env = dict(self.env, PATH=self.bin)
        p = self.run_script("--workspace", self.ws, "--job", "nightly-inbox", env=env)
        self.assertEqual(p.returncode, jp.FAILED_EXIT)
        self.assertIn("gh", p.stdout.splitlines()[0])

    def test_no_gh_skips_the_repo_check(self):
        self.populate("academy", "library")
        env = dict(self.env, FAKE_GH_OK="someone/else")
        p = self.run_script("--workspace", self.ws, "--job", "nightly-inbox", "--no-gh", env=env)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_repo_flag_overrides_workspace_json(self):
        self.populate("academy", "library")
        env = dict(self.env, FAKE_GH_OK="other/repo")
        p = self.run_script("--workspace", self.ws, "--job", "j", "--repo", "other/repo", env=env)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_file_board_needs_no_gh(self):
        self.populate("academy", "library")
        write(os.path.join(self.ws, "workspace.json"), json.dumps({"board": {"backend": "file"}}))
        env = dict(self.env, FAKE_GH_OK="someone/else")
        p = self.run_script("--workspace", self.ws, "--job", "j", env=env)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("no GitHub board", p.stdout)

    def test_missing_workspace_json_is_not_a_failure(self):
        # the jobs run the bootstrap when workspace.json is missing; gh is then checked
        # against --repo only, else skipped with a note
        self.populate("academy", "library")
        os.remove(os.path.join(self.ws, "workspace.json"))
        p = self.run_script("--workspace", self.ws, "--job", "j")
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("workspace.json", p.stdout)

    def test_manual_and_environment_flags_in_the_hint(self):
        p = self.run_script("--workspace", os.path.join(self.tmp, "absent"), "--job", "friday",
                            "--manual", "/run-friday-prep --dry", "--environment", "Env-X")
        self.assertIn("/run-friday-prep --dry", p.stdout)
        self.assertIn("Env-X", p.stdout)

    def test_all_reasons_on_the_first_line(self):
        os.makedirs(os.path.join(self.ws, "academy"))
        os.makedirs(os.path.join(self.ws, "library"))
        env = dict(self.env, FAKE_GH_OK="someone/else")
        p = self.run_script("--workspace", self.ws, "--job", "j", env=env)
        first = p.stdout.splitlines()[0]
        self.assertIn("academy, library", first)
        self.assertIn("cannot read owner/ws", first)


class FunctionTests(Base):
    def test_check_returns_reasons_and_notes(self):
        self.populate("academy", "library")
        reasons, notes = jp.check(self.ws, need=None, repo=None, use_gh=False)
        self.assertEqual(reasons, [])
        self.assertTrue(any("2 submodules" in n for n in notes), notes)


class ReviewFindingTests(Base):
    """T-1673 review: the false-FAILED and crash paths."""

    def test_only_dot_git_is_not_populated(self):
        write(os.path.join(self.ws, "library", ".git"), "gitdir: x\n")
        self.assertFalse(jp.populated(os.path.join(self.ws, "library")))

    def test_board_as_a_path_string_is_the_file_board(self):
        # "board" is a path (the file board) or a dict; a string must not crash
        self.populate("academy", "library")
        write(os.path.join(self.ws, "workspace.json"), json.dumps({"board": "board"}))
        p = self.run_script("--workspace", self.ws, "--job", "j")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("no GitHub board", p.stdout)

    def test_workspace_json_not_an_object_is_a_note(self):
        self.populate("academy", "library")
        for text in ("[1, 2]", "42", '{"board": 7}'):
            with self.subTest(text=text):
                write(os.path.join(self.ws, "workspace.json"), text)
                p = self.run_script("--workspace", self.ws, "--job", "j")
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertIn("workspace.json", p.stdout)
                self.assertEqual(p.stderr, "")

    def test_any_crash_is_a_failed_first_line(self):
        out = io.StringIO()
        with mock.patch.object(jp, "check", side_effect=RuntimeError("boom")), \
                contextlib.redirect_stdout(out):
            rc = jp.main(["--workspace", self.ws, "--job", "j"])
        self.assertEqual(rc, jp.FAILED_EXIT)
        first = out.getvalue().splitlines()[0]
        self.assertTrue(first.startswith("FAILED: j could not start: the preflight itself failed"), first)
        self.assertIn("RuntimeError: boom", first)

    def test_gh_timeout_is_a_reason(self):
        write(os.path.join(self.bin, "gh"), "#!/bin/sh\nsleep 5\n")
        with mock.patch.object(jp, "GH_TIMEOUT", 0.3), \
                mock.patch.dict(os.environ, {"PATH": self.env["PATH"]}):
            why = jp.gh_reads("owner/ws")
        self.assertIsNotNone(why)
        self.assertIn("owner/ws", why)
        self.assertIn("timed out", why)


class AttachedCheckoutTests(Base):
    """A cloud session whose clone was refused uses the attached checkout in place
    (workspace_bootstrap.submodules: RESOLVED[path] = the sibling); that is not a failure."""

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.ws, "academy"))
        os.makedirs(os.path.join(self.ws, "library"))

    def attach(self, name):
        d = os.path.join(self.tmp, name)
        write(os.path.join(d, ".git", "HEAD"), "ref: refs/heads/main\n")
        write(os.path.join(d, "README.md"), "x\n")
        return d

    def test_sibling_named_by_the_url_counts(self):
        self.attach("academy")
        self.attach("library")
        p = self.run_script("--workspace", self.ws, "--job", "j", "--no-gh")
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("attached checkout", p.stdout)

    def test_home_in_workspace_json_counts(self):
        self.attach("academy")
        lib = self.attach("BilliardLib")
        write(os.path.join(self.ws, "workspace.template.json"),
              json.dumps({"instances": {"expert@x": {"role": "expert", "home": "library"}}}))
        write(os.path.join(self.ws, "workspace.json"),
              json.dumps({"instances": {"expert@x": {"role": "expert", "home": lib}},
                          "board": {"backend": "github", "repo": "owner/ws"}}))
        p = self.run_script("--workspace", self.ws, "--job", "j")
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("library", p.stdout)

    def test_empty_sibling_does_not_count(self):
        self.attach("academy")
        os.makedirs(os.path.join(self.tmp, "library", ".git"))
        p = self.run_script("--workspace", self.ws, "--job", "j", "--no-gh")
        self.assertEqual(p.returncode, jp.FAILED_EXIT, p.stdout)
        self.assertIn("submodule not populated: library", p.stdout.splitlines()[0])


class GitmodulesTests(Base):
    def test_table_pairs_path_and_url(self):
        self.assertEqual(jp.submodule_table(self.ws),
                         [("academy", "https://example.invalid/academy.git"),
                          ("library", "https://example.invalid/library.git")])

    def test_url_with_equals_sign(self):
        write(os.path.join(self.ws, ".gitmodules"),
              '[submodule "a"]\n\tpath = a\n\turl = https://h/x?y=z/a.git\n')
        self.assertEqual(jp.submodule_table(self.ws), [("a", "https://h/x?y=z/a.git")])


if __name__ == "__main__":
    unittest.main()
