"""The workspace tooling that moved into the academy plugin: workspace_bootstrap.py (the
workspace's scripts/bootstrap.py shim runs it), ship.py's workspace discovery, and the
shims in templates/workspace/scripts. Temp directories and temp git repos only; nothing
here writes outside them (the bootstrap's machine-wide steps are not run)."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
REPO = os.path.dirname(os.path.dirname(HERE))
TEMPLATES = os.path.join(os.path.dirname(HERE), "templates", "workspace")
sys.path.insert(0, HERE)
sys.path.insert(0, SCRIPTS)
import ship  # noqa: E402
import workspace_bootstrap as bootstrap  # noqa: E402
from ship_fixture import configure, run  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="ws-boot-")
        self.addCleanup(shutil.rmtree, self.root, True)
        old, bootstrap.ROOT = bootstrap.ROOT, self.root
        self.addCleanup(setattr, bootstrap, "ROOT", old)
        self.said = []
        old_say, bootstrap.say = bootstrap.say, self.said.append
        self.addCleanup(setattr, bootstrap, "say", old_say)
        os.makedirs(os.path.join(self.root, "lab"))

    def template(self, **extra):
        doc = {"_about": "x",
               "instances": {"scientist@x": {"role": "scientist", "home": "lab",
                                             "domains": ["dom"]}},
               "board": {"path": "board", "backend": "github", "repo": "o/r"},
               "human": {"name": "Ada", "login": "ada"}}
        doc.update(extra)
        write(os.path.join(self.root, "workspace.template.json"), json.dumps(doc))
        return doc

    def test_a_plain_board_directory_counts_as_present(self):
        self.template()
        self.assertFalse(bootstrap.board_present())
        os.makedirs(os.path.join(self.root, "board"))         # a plain directory, no .git
        self.assertTrue(bootstrap.board_present())

    def test_unknown_top_level_keys_pass_through(self):
        compute = {"workers": {"w": {"transport": "ssh", "host": "h", "gateway": "g"}},
                   "gateways": {"g": {"kind": "vpn", "onDown": "ask the human"}}}
        self.template(compute=compute, grading={"primaryModels": ["a", "b"]},
                      plugins=["academy", "scientist"])
        with open(bootstrap.workspace(), encoding="utf-8") as fh:
            ws = json.load(fh)
        self.assertEqual(ws["compute"], compute)
        self.assertEqual(ws["grading"], {"primaryModels": ["a", "b"]})
        self.assertEqual(ws["human"], {"name": "Ada", "login": "ada"})
        self.assertEqual(ws["plugins"], ["academy", "scientist"])
        self.assertNotIn("_about", ws)
        self.assertEqual(ws["board"]["path"], bootstrap.posix(os.path.join(self.root, "board")))

    def fake_academy(self):
        acad = os.path.join(self.root, "acad")
        write(os.path.join(acad, ".claude-plugin", "marketplace.json"), json.dumps(
            {"plugins": [{"name": "academy", "source": "./academy"},
                         {"name": "dom-pack", "source": "./domains/dom"}]}))
        write(os.path.join(acad, "domains", "other", ".claude-plugin", "plugin.json"),
              json.dumps({"name": "other-pack"}))
        return acad

    def test_plugins_derive_from_roles_and_domains(self):
        acad = self.fake_academy()
        ws = {"instances": {"a": {"role": "author", "domains": ["dom"]},
                            "s": {"role": "scientist", "domains": ["dom", "other"]},
                            "x": {"role": "researcher", "domains": ["nope"]}}}
        self.assertEqual(bootstrap.plugin_names(ws, acad),
                         ["academy", "researcher", "scientist", "author", "dom-pack",
                          "other-pack"])
        self.assertTrue(any("nope" in s for s in self.said))
        self.assertEqual(bootstrap.plugin_names(dict(ws, plugins=["academy"]), acad), ["academy"])

    def test_the_real_marketplace_names_every_domain_pack(self):
        for d in os.listdir(os.path.join(REPO, "domains")):
            if os.path.isdir(os.path.join(REPO, "domains", d)):
                self.assertTrue(bootstrap.domain_plugin(d, REPO), d)

    def test_permissions_template_merged_with_the_workspace_override(self):
        write(os.path.join(self.root, "workspace.permissions.json"), json.dumps(
            {"_about": "x", "researcher": ["Bash(py {SCIENTIST}/tests/run.py)"],
             "newkey": ["Bash(true)"]}))
        table = bootstrap.permission_table()
        with open(os.path.join(TEMPLATES, "permissions.json"), encoding="utf-8") as fh:
            tpl = json.load(fh)
        self.assertEqual(table["researcher"], tpl["researcher"] + ["Bash(py {SCIENTIST}/tests/run.py)"])
        self.assertEqual(table["newkey"], ["Bash(true)"])
        self.assertEqual(table["workspace"], tpl["workspace"])

    def test_the_template_names_no_project(self):
        with open(os.path.join(TEMPLATES, "permissions.json"), encoding="utf-8") as fh:
            text = fh.read()
        for word in ("fslab", "run_all.py", "R" "oey"):
            self.assertNotIn(word, text)

    def test_find_workspace(self):
        self.template()
        deep = os.path.join(self.root, "lab", "x")
        os.makedirs(deep)
        self.assertEqual(bootstrap.find_workspace(cwd=deep), self.root)
        self.assertEqual(bootstrap.find_workspace(self.root), self.root)
        other = tempfile.mkdtemp(prefix="ws-none-")
        self.addCleanup(shutil.rmtree, other, True)
        with mock.patch.dict(os.environ, {"ACADEMY_WORKSPACE": os.path.join(self.root, "workspace.json")}):
            self.assertEqual(bootstrap.find_workspace(cwd=other), self.root)

    def test_main_without_a_workspace_says_so(self):
        other = tempfile.mkdtemp(prefix="ws-none-")
        self.addCleanup(shutil.rmtree, other, True)
        bootstrap.ROOT = None
        env = {k: v for k, v in os.environ.items() if k != "ACADEMY_WORKSPACE"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(bootstrap, "ACADEMY_REPO", other), \
                mock.patch("os.getcwd", return_value=other):
            self.assertEqual(bootstrap.main([]), 1)
        self.assertIn("no workspace found", self.said[-1])


class ShipWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ws-ship-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_find_workspace_order(self):
        ws = os.path.join(self.tmp, "ws")
        deep = os.path.join(ws, "home", "sub")
        os.makedirs(deep)
        write(os.path.join(ws, "workspace.json"), "{}")
        self.assertEqual(ship.find_workspace(cwd=deep), ws)
        self.assertEqual(ship.find_workspace(os.path.join(ws, "workspace.json")), ws)
        with self.assertRaises(ship.Refuse):
            ship.find_workspace(os.path.join(self.tmp, "nope"))
        elsewhere = os.path.join(self.tmp, "elsewhere")
        os.makedirs(elsewhere)
        with mock.patch.dict(os.environ, {"ACADEMY_WORKSPACE": os.path.join(ws, "workspace.json")}):
            self.assertEqual(ship.find_workspace(cwd=elsewhere), ws)
        env = {k: v for k, v in os.environ.items() if k != "ACADEMY_WORKSPACE"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(ship, "ACADEMY_REPO", os.path.join(self.tmp, "x", "academy")):
            with self.assertRaises(ship.Refuse):
                ship.find_workspace(cwd=elsewhere)
            write(os.path.join(self.tmp, "gm", ".gitmodules"), "")
            os.makedirs(os.path.join(self.tmp, "gm", "a"))
            self.assertEqual(ship.find_workspace(cwd=os.path.join(self.tmp, "gm", "a")),
                             os.path.join(self.tmp, "gm"))


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class ShimTests(unittest.TestCase):
    """The workspace's scripts/ship.py and scripts/bootstrap.py shims (copies of
    templates/workspace/scripts) run this academy's scripts with --workspace <root>."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ws-shim-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "ws")
        os.makedirs(os.path.join(self.root, "scripts"))
        for name in ("ship.py", "bootstrap.py", "cloud-setup.sh"):
            shutil.copy(os.path.join(TEMPLATES, "scripts", name),
                        os.path.join(self.root, "scripts", name))
        run(self.tmp, "init", "-q", "-b", "main", self.root)
        configure(self.root)
        write(os.path.join(self.root, "board", "README.md"), "b\n")
        write(os.path.join(self.root, "workspace.json"), json.dumps({"board": {"path": "board"}}))
        run(self.root, "add", "board")
        run(self.root, "commit", "-q", "-m", "init")
        self.env = dict(os.environ, ACADEMY_ROOT=REPO)
        self.env.pop("ACADEMY_WORKSPACE", None)

    def shim(self, name, *argv, cwd=None):
        return subprocess.run([sys.executable, os.path.join(self.root, "scripts", name), *argv],
                              cwd=cwd or self.tmp, env=self.env, capture_output=True, text=True,
                              timeout=120)

    def test_ship_shim_runs_the_plugin_for_its_workspace(self):
        write(os.path.join(self.root, "board", "p.md"), "p\n")
        res = self.shim("ship.py", "status")              # cwd outside the workspace
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertRegex(res.stdout, r"(?m)^board +main .*\[PROTECTED\] \(superproject, board/ only\)")
        res = self.shim("ship.py", "checkpoint", "--ticket", "T-1", "--only", "board")
        self.assertEqual(res.returncode, 1)               # dirty on main: refused, exit kept
        self.assertIn("REFUSED: dirty on main", res.stdout)

    def test_ship_shim_without_an_academy_refuses(self):
        self.env["ACADEMY_ROOT"] = os.path.join(self.tmp, "none")
        res = self.shim("ship.py", "status")
        self.assertEqual(res.returncode, 1)
        self.assertIn("no academy checkout", res.stderr)

    def test_bootstrap_shim_reaches_the_plugin(self):
        res = self.shim("bootstrap.py", "--help-not-a-flag", "--no-submodules", "--no-plugins",
                        cwd=self.tmp)
        # no workspace.template.json in this workspace: the plugin says so and exits 1
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("no workspace found", res.stdout)


if __name__ == "__main__":
    unittest.main()
