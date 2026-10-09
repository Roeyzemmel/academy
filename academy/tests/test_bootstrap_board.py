"""bootstrap.py keeps a GitHub board config ({"path", "backend", ...}) in workspace.json."""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import workspace_bootstrap as bootstrap  # noqa: E402


class BoardConfigTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        old, bootstrap.ROOT = bootstrap.ROOT, self.root
        self.addCleanup(setattr, bootstrap, "ROOT", old)
        os.makedirs(os.path.join(self.root, "lab"))

    def write_template(self, board):
        with open(os.path.join(self.root, "workspace.template.json"), "w") as fh:
            json.dump({"instances": {"scientist@x": {"role": "scientist", "home": "lab"}},
                       "board": board, "human": {"name": "R"}}, fh)

    def written(self):
        path = bootstrap.workspace()
        with open(path) as fh:
            return path, json.load(fh)

    def test_a_plain_board_path_is_made_absolute(self):
        self.write_template("board")
        _p, ws = self.written()
        self.assertEqual(bootstrap.posix(os.path.join(self.root, "board")), ws["board"])

    def test_a_github_board_keeps_its_config_and_an_absolute_path(self):
        cfg = {"path": "board", "backend": "github", "repo": "o/r",
               "transport": "board_gh:transport"}
        self.write_template(cfg)
        path, ws = self.written()
        self.assertEqual(dict(cfg, path=bootstrap.posix(os.path.join(self.root, "board"))),
                         ws["board"])
        self.assertEqual(ws["board"]["path"], bootstrap.home_env(path)[0]["ACADEMY_BOARD"])


if __name__ == "__main__":
    unittest.main()


class BoardCheckTests(unittest.TestCase):
    """board_check: on a GitHub board, gh must be there and able to read the repo."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.said = []
        old, bootstrap.say = bootstrap.say, self.said.append
        self.addCleanup(setattr, bootstrap, "say", old)

    def ws(self, board):
        path = os.path.join(self.tmp, "workspace.json")
        with open(path, "w") as fh:
            json.dump({"instances": {}, "board": board}, fh)
        return path

    @staticmethod
    def run_as(code, out="", err=""):
        class Res(object):
            returncode, stdout, stderr = code, out, err
        calls = []

        def run(args, **kw):
            calls.append(args)
            return Res()
        run.calls = calls
        return run

    def test_a_file_board_is_not_checked(self):
        run = self.run_as(1)
        self.assertTrue(bootstrap.board_check(self.ws("/b"), which=lambda n: None, run=run))
        self.assertEqual([], run.calls)
        self.assertEqual([], self.said)

    def test_github_board_readable(self):
        run = self.run_as(0, "o/r\n")
        ws = self.ws({"path": "/b", "backend": "github", "repo": "o/r"})
        self.assertTrue(bootstrap.board_check(ws, which=lambda n: "/usr/bin/gh", run=run))
        self.assertEqual([["gh", "api", "repos/o/r", "--jq", ".full_name"]], run.calls)
        self.assertIn("gh can read it", self.said[-1])

    def test_github_board_without_gh_warns(self):
        ws = self.ws({"path": "/b", "backend": "github", "repo": "o/r"})
        self.assertFalse(bootstrap.board_check(ws, which=lambda n: None, run=self.run_as(0)))
        self.assertIn("gh is not installed", self.said[-1])

    def test_github_board_gh_refused_warns_with_the_reason(self):
        run = self.run_as(1, err="gh: HTTP 404: Not Found\nmore")
        ws = self.ws({"path": "/b", "backend": "github", "repo": "o/r"})
        self.assertFalse(bootstrap.board_check(ws, which=lambda n: "/usr/bin/gh", run=run))
        self.assertIn("gh cannot read it: gh: HTTP 404: Not Found.", self.said[-1])
