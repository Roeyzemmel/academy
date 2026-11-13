"""session_start.staleness: the session is told when the academy code it runs is behind
(2026-11-13: three weeks of already-fixed errors came from stale checkouts and copies)."""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import session_start as ss  # noqa: E402
from ship_fixture import configure, run  # noqa: E402


def plugin(root, version):
    d = os.path.join(root, "academy", ".claude-plugin")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "plugin.json"), "w", encoding="utf-8") as fh:
        json.dump({"name": "academy", "version": version}, fh)
    return os.path.join(root, "academy")


class Staleness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="stale-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def checkout(self, behind):
        """A clone of a bare remote whose origin/main is ``behind`` commits ahead of HEAD."""
        bare = os.path.join(self.tmp, "remote.git")
        run(self.tmp, "init", "-q", "--bare", "-b", "main", bare)
        repo = os.path.join(self.tmp, "repo")
        run(self.tmp, "clone", "-q", bare, repo)
        configure(repo)
        run(repo, "switch", "-q", "-c", "main")
        root = plugin(repo, "0.2.1")
        run(repo, "add", "-A")
        run(repo, "commit", "-q", "-m", "one")
        run(repo, "push", "-q", "-u", "origin", "main")
        for k in range(behind):
            with open(os.path.join(repo, "f%d" % k), "w") as fh:
                fh.write("x")
            run(repo, "add", "-A")
            run(repo, "commit", "-q", "-m", "more %d" % k)
        if behind:
            run(repo, "push", "-q", "origin", "main")
            run(repo, "reset", "-q", "--hard", "HEAD~%d" % behind)
        return root

    def test_a_checkout_behind_origin_main_says_by_how_much(self):
        self.assertEqual("", ss.staleness(self.checkout(0), workspace={}))
        shutil.rmtree(os.path.join(self.tmp, "repo"))
        shutil.rmtree(os.path.join(self.tmp, "remote.git"))
        line = ss.staleness(self.checkout(3), workspace={})
        self.assertIn("3 commits behind origin/main", line)
        self.assertIn("as last fetched", line)

    def test_an_installed_copy_older_than_the_workspaces_checkout_says_so(self):
        installed = plugin(os.path.join(self.tmp, "cache"), "0.2.0")
        ws_root = os.path.join(self.tmp, "ws")
        plugin(os.path.join(ws_root, "academy"), "0.2.1")
        ws = {"_path": os.path.join(ws_root, "workspace.json")}
        old = os.environ.pop("ACADEMY_ROOT", None)
        self.addCleanup(lambda: old is not None and os.environ.__setitem__("ACADEMY_ROOT", old))
        line = ss.staleness(installed, workspace=ws)
        self.assertIn("installed academy plugins are 0.2.0", line)
        self.assertIn("checkout is 0.2.1", line)
        self.assertIn("scripts/bootstrap.py", line)
        plugin(os.path.join(self.tmp, "cache"), "0.2.1")
        self.assertEqual("", ss.staleness(installed, workspace=ws))
        self.assertEqual("", ss.staleness(installed, workspace={}))        # no workspace: silent


if __name__ == "__main__":
    unittest.main()
