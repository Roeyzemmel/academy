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


if __name__ == "__main__":
    unittest.main()
