"""The vendored copies <plugin>/scripts/_academy/ must equal the package
academy/lib/academy_common/, file by file; and the package still is one namespace.

Fix a failure with:  py academy/scripts/sync_common.py
"""

import ast
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

sys.path.insert(0, os.path.join(PLUGIN, "lib"))

import sync_common  # noqa: E402
import academy_common as ac  # noqa: E402

LIB = os.path.join(PLUGIN, "lib", "academy_common")


class VendoredTests(unittest.TestCase):
    def test_five_plugins(self):
        self.assertEqual(sync_common.PLUGINS,
                         ("academy", "author", "researcher", "expert", "scientist"))

    def test_no_drift(self):
        lib = sync_common.modules(LIB)
        self.assertIn("__init__.py", lib)
        self.assertGreater(len(lib), 1)
        for target in sync_common.targets(REPO):
            rel = os.path.relpath(target, REPO)
            with self.subTest(copy=rel):
                self.assertTrue(os.path.isdir(target), "%s is missing; run "
                                "py academy/scripts/sync_common.py" % rel)
                self.assertEqual(sync_common.modules(target), lib, "%s drifted from the "
                                 "lib; run py academy/scripts/sync_common.py" % rel)
                # the single file of before the split would be shadowed by the package
                self.assertFalse(os.path.exists(target + ".py"), rel + ".py")

    def test_check_mode_agrees(self):
        self.assertEqual(sync_common.drifted(REPO), [])

    def test_no_stray_debug_output_in_scripts(self):
        # verification Group G: out.txt / out2.txt were committed into expert/scripts/
        import glob
        stray = []
        for plugin in sync_common.PLUGINS:
            for pat in ("out*.txt", "*.out", "debug*.txt"):
                stray += glob.glob(os.path.join(REPO, plugin, "scripts", pat))
        self.assertEqual([os.path.relpath(p, REPO) for p in stray], [])


class OneNamespaceTests(unittest.TestCase):
    """The split library behaves as the one module it was: every name of a part is a
    name of the package, and rebinding one on the package reaches the parts."""

    def test_every_name_of_every_part_is_on_the_package(self):
        for part in ac._PARTS:
            for name in vars(part):
                if not name.startswith("__"):
                    self.assertTrue(hasattr(ac, name), "%s.%s" % (part.__name__, name))
                    self.assertIs(getattr(ac, name), getattr(part, name), name)

    def test_assigning_on_the_package_rebinds_the_name_in_every_part(self):
        seen = []
        real = ac.load_workspace
        ac.load_workspace = lambda path=None: seen.append(path) or {"board": "B"}
        try:
            # open_store (in _store) calls load_workspace (from _workspace) by its bare name
            self.assertEqual(ac.open_store("ws.json").board, "B")
            ac.human_name()                                  # _workspace's own caller
        finally:
            ac.load_workspace = real
        self.assertEqual(seen, ["ws.json", None])
        for part in ac._PARTS:
            if "load_workspace" in vars(part):
                self.assertIs(part.load_workspace, real, part.__name__)

    def test_patch_object_reaches_the_parts_and_is_undone(self):
        real = ac.today
        with mock.patch.object(ac, "today", lambda: "2001-02-03"):
            self.assertEqual(ac._tickets.today(), "2001-02-03")
            self.assertEqual(ac._packets.today(), "2001-02-03")
        self.assertIs(ac._base.today, real)
        self.assertIs(ac._tickets.today, real)
        self.assertIs(ac.today, real)

    def test_a_name_a_part_rebinds_is_read_live(self):
        # every ``global`` statement of the library names a _LIVE name
        rebound = set()
        for name in sync_common.modules(LIB):
            with open(os.path.join(LIB, name), encoding="utf-8") as fh:
                for node in ast.walk(ast.parse(fh.read())):
                    if isinstance(node, ast.Global):
                        rebound.update(node.names)
        self.assertEqual(rebound, set(ac._LIVE))
        saved = ac.WORKSPACE_TAGS
        try:
            env = {"ACADEMY_WS__A__WORKSPACE": "/a/workspace.json",
                   "ACADEMY_WS__B__WORKSPACE": "/b/workspace.json"}
            self.assertIsNone(ac.resolve_workspace_env(env, etc=os.devnull, cwd="/nowhere"))
            self.assertEqual(ac.WORKSPACE_TAGS, ["A", "B"])
            ac.WORKSPACE_TAGS = ["C"]
            self.assertEqual(ac._workspace.WORKSPACE_TAGS, ["C"])
        finally:
            ac.WORKSPACE_TAGS = saved

    def test_the_parts_import_only_earlier_parts(self):
        order = [p.__name__.rsplit(".", 1)[1] for p in ac._PARTS]
        self.assertEqual(sorted(order + ["__init__"]),
                         sorted(n[:-3] for n in sync_common.modules(LIB)))
        for i, name in enumerate(order):
            with open(os.path.join(LIB, name + ".py"), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level:
                    self.assertEqual(node.level, 1, name)
                    self.assertIn(node.module, order[:i], "%s imports %s" % (name, node.module))


if __name__ == "__main__":
    unittest.main()
