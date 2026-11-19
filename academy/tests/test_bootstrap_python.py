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

    def _settings(self, path, env):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump({"env": env}, fh)

    def test_a_working_value_in_the_user_settings_wins(self):
        # finding 1: a value set only in ~/.claude/settings.json (not in this process's
        # environment) is what write_user_env would otherwise overwrite
        self._settings(os.path.join(self.home, ".claude", "settings.json"),
                       {"ACADEMY_PYTHON": "/opt/py311/bin/python"})
        env = bootstrap.python_env(which_of({"python3": "/usr/bin/python3",
                                             "/opt/py311/bin/python": "/opt/py311/bin/python"}))
        self.assertEqual({"ACADEMY_PYTHON": "/opt/py311/bin/python"}, env)

    def test_a_working_value_in_the_workspace_settings_local_wins(self):
        root = tempfile.mkdtemp(prefix="ws-py-root-")
        self.addCleanup(shutil.rmtree, root, True)
        old, bootstrap.ROOT = bootstrap.ROOT, root
        self.addCleanup(setattr, bootstrap, "ROOT", old)
        self._settings(os.path.join(root, ".claude", "settings.local.json"),
                       {"ACADEMY_PYTHON": "python3.12"})
        env = bootstrap.python_env(which_of({"python3": "/usr/bin/python3",
                                             "python3.12": "/opt/py/bin/python3.12"}))
        self.assertEqual({"ACADEMY_PYTHON": "python3.12"}, env)

    def test_the_environment_beats_the_settings_files(self):
        os.environ["ACADEMY_PYTHON"] = "python3.12"
        self._settings(os.path.join(self.home, ".claude", "settings.json"),
                       {"ACADEMY_PYTHON": "/opt/py311/bin/python"})
        env = bootstrap.python_env(which_of({"python3.12": "/opt/py/bin/python3.12",
                                             "/opt/py311/bin/python": "/opt/py311/bin/python"}))
        self.assertEqual({"ACADEMY_PYTHON": "python3.12"}, env)

    def test_a_broken_value_in_the_user_settings_is_replaced(self):
        self._settings(os.path.join(self.home, ".claude", "settings.json"),
                       {"ACADEMY_PYTHON": "/gone/python"})
        env = bootstrap.python_env(which_of({"python3": "/usr/bin/python3"}))
        self.assertEqual({"ACADEMY_PYTHON": "/usr/bin/python3"}, env)

    def test_an_unreadable_user_settings_is_ignored(self):
        path = os.path.join(self.home, ".claude", "settings.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w") as fh:
            fh.write("{not json")
        env = bootstrap.python_env(which_of({"python3": "/usr/bin/python3"}))
        self.assertEqual({"ACADEMY_PYTHON": "/usr/bin/python3"}, env)

    def test_the_windows_store_stub_is_not_rendered(self):
        # finding 3: without py, python3 on Windows is usually the Store alias, which
        # runs nothing (academy/references/windows.md)
        stub = "C:\\Users\\u\\AppData\\Local\\Microsoft\\WindowsApps\\python3.exe"
        with mock.patch.object(bootstrap, "say"):
            env = bootstrap.python_env(which_of({"python3": stub, "python": stub}))
        self.assertEqual({}, env)

    def test_a_real_python_behind_a_store_python3_is_rendered(self):
        # review 2, finding 1: python3 is the Store alias but python is a real install
        stub = "C:\\Users\\u\\AppData\\Local\\Microsoft\\WindowsApps\\python3.exe"
        with mock.patch.object(bootstrap.os.path, "abspath", lambda p: p), \
                mock.patch.object(bootstrap, "say"):
            env = bootstrap.python_env(which_of({"python3": stub,
                                                 "python": "C:\\Python312\\python.exe"}))
        self.assertEqual({"ACADEMY_PYTHON": "C:/Python312/python.exe"}, env)

    def test_python_target_skips_the_store_alias(self):
        stub = "C:\\Users\\u\\AppData\\Local\\Microsoft\\WindowsApps\\python3.exe"
        self.assertEqual("C:\\Python312\\python.exe",
                         bootstrap.python_target(which_of({"python3": stub,
                                                           "python": "C:\\Python312\\python.exe"})))
        self.assertIsNone(bootstrap.python_target(which_of({"python3": stub, "python": stub})))

    def test_only_store_aliases_warn(self):
        stub = "C:\\Users\\u\\AppData\\Local\\Microsoft\\WindowsApps\\python3.exe"
        with mock.patch.object(bootstrap, "say") as say:
            bootstrap.python_env(which_of({"python3": stub, "python": stub}))
        self.assertTrue(any("Store alias" in c.args[0] for c in say.call_args_list))

    def test_the_py_shim_never_links_the_store_alias(self):
        stub = "C:\\Users\\u\\AppData\\Local\\Microsoft\\WindowsApps\\python3.exe"
        with mock.patch.object(bootstrap.shutil, "which",
                               which_of({"python3": stub, "python": stub})), \
                mock.patch.object(bootstrap, "say") as say:
            bootstrap.py_shim()
        self.assertFalse(os.path.lexists(self.shim))
        self.assertIn("Store alias", say.call_args_list[0].args[0])

    def test_the_rendered_path_has_forward_slashes(self):
        # finding 3: like every other rendered path (posix)
        with mock.patch.object(bootstrap.os.path, "abspath", lambda p: p):
            env = bootstrap.python_env(which_of({"python3": "C:\\Python312\\python3.exe"}))
        self.assertEqual({"ACADEMY_PYTHON": "C:/Python312/python3.exe"}, env)

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


class MachineWideTests(unittest.TestCase):
    """finding 2: the machine-wide writers, unmocked, with HOME, the workspace and
    /etc/environment in temp directories."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="ws-py-mw-")
        self.addCleanup(shutil.rmtree, self.root, True)
        old, bootstrap.ROOT = bootstrap.ROOT, os.path.join(self.root, "My Work")
        os.makedirs(bootstrap.ROOT)
        self.addCleanup(setattr, bootstrap, "ROOT", old)
        self.home = os.path.join(self.root, "home")
        os.makedirs(self.home)
        patcher = mock.patch.dict(os.environ, {"HOME": self.home, "USERPROFILE": self.home})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.etc = os.path.join(self.root, "environment")
        for p in (mock.patch.object(bootstrap, "ETC_ENVIRONMENT", self.etc),
                  mock.patch.object(bootstrap, "say")):
            p.start()
            self.addCleanup(p.stop)
        self.user = os.path.join(self.home, ".claude", "settings.json")

    def user_env(self):
        with open(self.user) as fh:
            return json.load(fh)["env"]

    def test_user_settings_get_it_unprefixed(self):
        bootstrap.write_user_env({"ACADEMY_PYTHON": "/usr/bin/python3", "ACADEMY_ROOT": "/a"})
        self.assertEqual({"ACADEMY_PYTHON": "/usr/bin/python3",
                          "ACADEMY_WS__MY_WORK__ROOT": "/a"}, self.user_env())

    def test_a_users_value_survives_the_legacy_purge(self):
        os.makedirs(os.path.dirname(self.user))
        with open(self.user, "w") as fh:
            json.dump({"env": {"ACADEMY_PYTHON": "/opt/py311/bin/python",
                               "ACADEMY_ROOT": "/old"}, "model": "x"}, fh)
        bootstrap.write_user_env({"ACADEMY_ROOT": "/a"})      # py present: no ACADEMY_PYTHON
        with open(self.user) as fh:
            cur = json.load(fh)
        self.assertEqual({"ACADEMY_PYTHON": "/opt/py311/bin/python",
                          "ACADEMY_WS__MY_WORK__ROOT": "/a"}, cur["env"])
        self.assertEqual("x", cur["model"])

    def test_the_whole_render_keeps_a_users_value_in_the_user_settings(self):
        # finding 1 end to end: py absent, the value only in ~/.claude/settings.json
        os.makedirs(os.path.dirname(self.user))
        with open(self.user, "w") as fh:
            json.dump({"env": {"ACADEMY_PYTHON": "/opt/py311/bin/python"}}, fh)
        table = {"python3": "/usr/bin/python3", "/opt/py311/bin/python": "/opt/py311/bin/python"}
        with mock.patch.object(bootstrap.shutil, "which", which_of(table)):
            env = bootstrap.python_env()
        bootstrap.write_user_env(env)
        self.assertEqual("/opt/py311/bin/python", self.user_env()["ACADEMY_PYTHON"])

    @unittest.skipIf(os.name == "nt", "persist_env writes the registry on Windows")
    def test_etc_environment_and_global_env_get_it_unprefixed(self):
        with open(self.etc, "w") as fh:
            fh.write('PATH="/usr/bin"\nACADEMY_ROOT="/old"\nACADEMY_PYTHON="/old/python"\n')
        with mock.patch.object(bootstrap.os, "geteuid", lambda: 0):
            bootstrap.persist_env({"ACADEMY_PYTHON": "/usr/bin/python3", "ACADEMY_ROOT": "/a"})
        with open(self.etc) as fh:
            lines = fh.read().splitlines()
        self.assertEqual(['PATH="/usr/bin"', 'ACADEMY_PYTHON="/usr/bin/python3"',
                          'ACADEMY_WS__MY_WORK__ROOT="/a"'], lines)
        with open(os.path.join(bootstrap.ROOT, "workspace.global.env")) as fh:
            self.assertIn('ACADEMY_PYTHON="/usr/bin/python3"\n', fh.read())

    @unittest.skipIf(os.name == "nt", "persist_env writes the registry on Windows")
    def test_a_users_value_in_etc_environment_survives_when_py_is_there(self):
        with open(self.etc, "w") as fh:
            fh.write('ACADEMY_PYTHON="/opt/py311/bin/python"\n')
        with mock.patch.object(bootstrap.os, "geteuid", lambda: 0):
            bootstrap.persist_env({"ACADEMY_ROOT": "/a"})
        with open(self.etc) as fh:
            self.assertEqual(['ACADEMY_PYTHON="/opt/py311/bin/python"',
                              'ACADEMY_WS__MY_WORK__ROOT="/a"'], fh.read().splitlines())


if __name__ == "__main__":
    unittest.main()
