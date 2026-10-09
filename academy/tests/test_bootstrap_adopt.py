"""adopt_sibling: an attached checkout moves into the submodule path, a symlink stays."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "scripts"))
import workspace_bootstrap as bootstrap  # noqa: E402


class AdoptSiblingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "ws")
        os.makedirs(os.path.join(self.root, "library"))         # the empty submodule dir
        self.near = os.path.join(self.tmp, "Lib")
        os.makedirs(os.path.join(self.near, ".git"))
        with open(os.path.join(self.near, "index.md"), "w") as fh:
            fh.write("x")
        old, bootstrap.ROOT = bootstrap.ROOT, self.root
        self.addCleanup(setattr, bootstrap, "ROOT", old)

    def test_moves_and_leaves_symlink(self):
        self.assertTrue(bootstrap.adopt_sibling("library", self.near))
        self.assertTrue(os.path.isdir(os.path.join(self.root, "library", ".git")))
        self.assertTrue(os.path.islink(self.near))
        self.assertEqual(os.path.realpath(os.path.join(self.near, "index.md")),
                         os.path.realpath(os.path.join(self.root, "library", "index.md")))

    def test_rerun_is_a_noop_on_the_symlink(self):
        bootstrap.adopt_sibling("library", self.near)
        self.assertFalse(bootstrap.adopt_sibling("library", self.near))
        self.assertTrue(os.path.exists(os.path.join(self.root, "library", "index.md")))

    def test_populated_submodule_path_is_refused_and_untouched(self):
        with open(os.path.join(self.root, "library", "mine"), "w") as fh:
            fh.write("y")
        self.assertFalse(bootstrap.adopt_sibling("library", self.near))
        self.assertTrue(os.path.isdir(self.near) and not os.path.islink(self.near))
        self.assertTrue(os.path.exists(os.path.join(self.root, "library", "mine")))


if __name__ == "__main__":
    unittest.main()
