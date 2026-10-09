"""domain_get in the cloud layout (workflow fix 5, 2026-10-09).

A cloud session runs the plugins from ``~/.claude/plugins/cache/<marketplace>/
<plugin>/<version>`` and its ``workspace.json`` sits in the workspace, not in the
marketplace, so ``<academy root>/domains`` is empty there: 165 refusals "no domain
pack 'translation-surfaces' (have: none)" on 2026-10-08. The pack is now also found
through the marketplace's source directory and through an installed pack plugin, and a
miss lists the places searched and says not to retry.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
for p in (os.path.join(PLUGIN, "lib"), os.path.join(PLUGIN, "mcp")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tools import Context, ToolError  # noqa: E402
from tools import domain  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class TestCloudLayout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acad-dom-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        t = self.tmp
        self.ws = {"instances": {}, "board": os.path.join(t, "ws", "board"),
                   "_path": os.path.join(t, "ws", "workspace.json")}
        self.plugins = os.path.join(t, "dotclaude", "plugins")
        self.plugin = os.path.join(self.plugins, "cache", "mkt", "academy", "0.1.0")
        os.makedirs(self.plugin)
        env = {k: v for k, v in os.environ.items() if k != "ACADEMY_ROOT"}
        env["CLAUDE_PLUGIN_ROOT"] = self.plugin
        p = mock.patch.dict(os.environ, env, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def ctx(self):
        return Context(cwd=self.tmp, workspace=self.ws)

    def test_found_through_the_known_marketplace(self):
        src = os.path.join(self.tmp, "src", "academy")
        write(os.path.join(src, "domains", "test-pack", "notation.md"), "# N\n")
        write(os.path.join(self.plugins, "known_marketplaces.json"), json.dumps(
            {"mkt": {"source": {"source": "directory", "path": src},
                     "installLocation": src}}))
        res = domain._get(self.ctx(), {"name": "test-pack", "file": "notation.md"})
        self.assertEqual(res["text"], "# N\n")

    def test_found_as_an_installed_pack_plugin(self):
        pack = os.path.join(self.plugins, "cache", "mkt", "ts-domain", "0.1.0")
        write(os.path.join(pack, "pack.json"), json.dumps({"name": "test-pack"}))
        write(os.path.join(pack, "notation.md"), "# I\n")
        res = domain._get(self.ctx(), {"name": "test-pack"})
        self.assertIn("notation.md", res["files"])

    def test_found_beside_the_plugin_in_the_repo_layout(self):
        repo = os.path.join(self.tmp, "repo")
        write(os.path.join(repo, "domains", "test-pack", "notation.md"), "# R\n")
        os.makedirs(os.path.join(repo, "academy"))
        with mock.patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT":
                                          os.path.join(repo, "academy")}):
            res = domain._get(self.ctx(), {"name": "test-pack", "file": "notation.md"})
        self.assertEqual(res["text"], "# R\n")

    def test_a_miss_names_the_places_and_says_do_not_retry(self):
        with self.assertRaises(ToolError) as cm:
            domain._get(self.ctx(), {"name": "test-pack"})
        msg = str(cm.exception)
        self.assertIn("Do not retry", msg)
        self.assertIn(os.path.join(self.tmp, "ws", "domains").replace("\\", "/"), msg)
        self.assertIn("installed plugins under", msg)


if __name__ == "__main__":
    unittest.main()
