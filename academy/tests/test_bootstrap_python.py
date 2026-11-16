"""bootstrap.py renders ACADEMY_PYTHON on a machine without the ``py`` launcher (T-0181).

The academy MCP server is started as ``${ACADEMY_PYTHON:-py}`` (``.mcp.json``, spawned
without a shell), so where there is no ``py`` the rendered environment must name the
interpreter. The hooks fall back to python3 themselves; the MCP server cannot. Temp
directories only, and ``which`` is injected: nothing here looks at the real PATH."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import workspace_bootstrap as bootstrap  # noqa: E402


def which_of(table):
    """A fake ``shutil.which``: the path of each command in ``table``, else None."""
    return lambda cmd, *a, **k: table.get(cmd)


class PythonEnvTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="ws-py-home-")
        self.addCleanup(shutil.rmtree, self.home, True)
        patcher = mock.patch.dict(os.environ, {"HOME": self.home, "USERPROFILE": self.home})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("ACADEMY_PYTHON", None)
        self.shim = os.path.join(self.home, ".local", "bin", "py")

    def test_no_py_names_python3(self):
        env = bootstrap.python_env(which_of({"python3": "/usr/bin/python3"}))
        self.assertEqual({"ACADEMY_PYTHON": "/usr/bin/python3"}, env)

    def test_no_py_and_no_python3_falls_back_to_python(self):
        env = bootstrap.python_env(which_of({"python": "/usr/bin/python"}))
        self.assertEqual({"ACADEMY_PYTHON": "/usr/bin/python"}, env)

    def test_a_real_py_launcher_renders_nothing(self):
        env = bootstrap.python_env(which_of({"py": "/usr/bin/py", "python3": "/usr/bin/python3"}))
        self.assertEqual({}, env)

    def test_the_bootstraps_own_py_shim_does_not_count_as_a_launcher(self):
        # the shim is installed after the environment is rendered; a second run, which
        # finds it on PATH, must render the same variable (idempotent), since a shell-less
        # spawn may not have ~/.local/bin on its PATH
        env = bootstrap.python_env(which_of({"py": self.shim, "python3": "/usr/bin/python3"}))
        self.assertEqual({"ACADEMY_PYTHON": "/usr/bin/python3"}, env)

    def test_no_python_at_all_renders_nothing(self):
        self.assertEqual({}, bootstrap.python_env(which_of({})))

    def test_an_existing_working_value_wins(self):
        os.environ["ACADEMY_PYTHON"] = "python3.12"
        env = bootstrap.python_env(which_of({"python3": "/usr/bin/python3",
                                             "python3.12": "/opt/py/bin/python3.12"}))
        self.assertEqual({"ACADEMY_PYTHON": "python3.12"}, env)

    def test_an_existing_broken_value_is_replaced(self):
        os.environ["ACADEMY_PYTHON"] = "/gone/python"
        env = bootstrap.python_env(which_of({"python3": "/usr/bin/python3"}))
        self.assertEqual({"ACADEMY_PYTHON": "/usr/bin/python3"}, env)

    def test_it_is_machine_wide_not_tagged_and_not_legacy(self):
        old, bootstrap.ROOT = bootstrap.ROOT, "/w/My Work"
        self.addCleanup(setattr, bootstrap, "ROOT", old)
        out = bootstrap.tagged({"ACADEMY_PYTHON": "/usr/bin/python3",
                                "ACADEMY_ROOT": "/a"})
        self.assertEqual({"ACADEMY_PYTHON": "/usr/bin/python3",
                          "ACADEMY_WS__MY_WORK__ROOT": "/a"}, out)
        # an earlier bootstrap's unprefixed variables are removed from the machine-wide
        # places; ACADEMY_PYTHON is not one of them (the user may have set it there)
        self.assertFalse(bootstrap.is_legacy("ACADEMY_PYTHON"))
        self.assertTrue(bootstrap.is_legacy("ACADEMY_ROOT"))


class RenderedEnvTests(unittest.TestCase):
    """home_env, the one environment written to every settings.local.json, workspace.env
    and the machine-wide places, carries the variable when py is absent."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="ws-py-")
        self.addCleanup(shutil.rmtree, self.root, True)
        old, bootstrap.ROOT = bootstrap.ROOT, self.root
        self.addCleanup(setattr, bootstrap, "ROOT", old)
        patcher = mock.patch.dict(os.environ, {"HOME": self.root, "USERPROFILE": self.root})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("ACADEMY_PYTHON", None)
        os.makedirs(os.path.join(self.root, "lab"))
        with open(os.path.join(self.root, "workspace.template.json"), "w") as fh:
            json.dump({"instances": {"scientist@x": {"role": "scientist", "home": "lab"}},
                       "board": "board", "human": {"name": "R"}}, fh)
        self.ws_path = bootstrap.workspace()

    def test_rendered_when_py_is_absent(self):
        with mock.patch.object(bootstrap.shutil, "which",
                               which_of({"python3": "/usr/bin/python3"})):
            env, _ws = bootstrap.home_env(self.ws_path)
        self.assertEqual("/usr/bin/python3", env["ACADEMY_PYTHON"])

    def test_not_rendered_when_py_is_there(self):
        with mock.patch.object(bootstrap.shutil, "which",
                               which_of({"py": "/usr/bin/py", "python3": "/usr/bin/python3"})):
            env, _ws = bootstrap.home_env(self.ws_path)
        self.assertNotIn("ACADEMY_PYTHON", env)

    def test_written_to_the_settings_and_workspace_env(self):
        with mock.patch.object(bootstrap.shutil, "which",
                               which_of({"python3": "/usr/bin/python3"})), \
                mock.patch.object(bootstrap, "persist_env"), \
                mock.patch.object(bootstrap, "write_user_env"), \
                mock.patch.object(bootstrap, "check_permissions"), \
                mock.patch.object(bootstrap, "say"):
            bootstrap.settings_local(self.ws_path)
        with open(os.path.join(self.root, ".claude", "settings.local.json")) as fh:
            self.assertEqual("/usr/bin/python3", json.load(fh)["env"]["ACADEMY_PYTHON"])
        with open(os.path.join(self.root, "lab", ".claude", "settings.local.json")) as fh:
            self.assertEqual("/usr/bin/python3", json.load(fh)["env"]["ACADEMY_PYTHON"])
        with open(os.path.join(self.root, "workspace.env")) as fh:
            self.assertIn('ACADEMY_PYTHON="/usr/bin/python3"\n', fh.read())


if __name__ == "__main__":
    unittest.main()
