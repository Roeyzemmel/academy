"""The permission rules for the scripts/ship.py shim: safe verbs allowlisted, merge/publish never."""
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "scripts"))
import workspace_bootstrap as bootstrap  # noqa: E402

REAL_ROOT = bootstrap.ROOT
SAFE = ["status", "start", "commit", "push", "ship", "checkpoint"]
# accept-baseline rewrites what the gate accepts, so it prompts like merge and publish
DANGEROUS = ["merge", "publish", "accept-baseline"]


def matches(rule, command):
    """Does a Claude Code prefix rule ``Tool(prefix:*)`` / ``Tool(prefix*)`` / exact match ``command``?"""
    m = re.match(r"^(?:Bash|PowerShell)\((.*)\)$", rule)
    if not m:
        return False
    pat = m.group(1)
    if pat.endswith(":*"):
        return command == pat[:-2] or command.startswith(pat[:-2] + " ")
    if pat.endswith("*"):
        return command.startswith(pat[:-1])
    return command == pat


class ShipPermissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "ws").replace("\\", "/")
        os.makedirs(os.path.join(self.root, "scripts"))
        # the rules come from this academy's templates/workspace/permissions.json (the temp
        # workspace has no academy submodule, so the running checkout's is used)
        bootstrap.ROOT = self.root
        self.addCleanup(setattr, bootstrap, "ROOT", REAL_ROOT)
        acad = self.tmp.replace("\\", "/") + "/academy"
        self.env = {"ACADEMY_ROOT": acad, "ACADEMY_BOARD": self.root + "/board",
                    "ACADEMY_LIBRARY": self.root + "/library"}
        self.ws = {"instances": {"expert": {"role": "expert", "home": self.root + "/library"}}}
        self.rules = bootstrap.permission_rules("workspace", self.env, self.ws)
        self.ps_root = self.root.replace("/", "\\")

    def cmd(self, verb, shell, relative=False, forward=False):
        if relative:
            if shell == "Bash" or forward:
                return "py scripts/ship.py %s" % verb
            return "py scripts\\ship.py %s" % verb
        if shell == "Bash":
            return "py %s/scripts/ship.py %s" % (self.root, verb)
        return "py %s\\scripts\\ship.py %s" % (self.ps_root, verb)

    def allowed(self, verb, shell, relative=False, forward=False):
        cmd = self.cmd(verb, shell, relative, forward)
        return any(r.startswith(shell + "(") and matches(r, cmd + " x") for r in self.rules)

    FORMS = [("Bash", False, False), ("Bash", True, False), ("PowerShell", False, False),
             ("PowerShell", True, False), ("PowerShell", True, True)]

    def test_safe_verbs_allowed_in_both_shells(self):
        for verb in SAFE:
            for shell, relative, forward in self.FORMS:
                self.assertTrue(self.allowed(verb, shell, relative, forward), (verb, shell, relative, forward))

    def test_powershell_forward_slash_relative_twin(self):
        # M1: a PowerShell session types the relative path with forward slashes too
        for verb in SAFE:
            self.assertIn("PowerShell(py scripts/ship.py %s:*)" % verb, self.rules)
            self.assertIn("PowerShell(py scripts\\ship.py %s:*)" % verb, self.rules)

    def test_merge_publish_and_accept_baseline_never_allowed(self):
        for verb in DANGEROUS:
            for shell, relative, forward in self.FORMS:
                self.assertFalse(self.allowed(verb, shell, relative, forward), (verb, shell, relative, forward))
        self.assertFalse([r for r in self.rules if "accept-baseline" in r])
        for r in self.rules:
            if "ship.py" in r:
                self.assertNotRegex(r, r"ship\.py(:\*|\*|\s\*)")

    def test_workspace_placeholder_expands_with_forward_slashes(self):
        bash = [r for r in self.rules if r.startswith("Bash(py %s/" % self.root)]
        self.assertEqual(len(bash), len(SAFE))
        self.assertFalse(any("{WORKSPACE}" in r for r in self.rules))

    def test_root_rules_are_only_ship_rules(self):
        self.assertTrue(self.rules)
        for r in self.rules:
            self.assertIn("ship.py", r)
            self.assertFalse(r.startswith(("Read(", "Edit(")), r)
        # absolute Bash + PowerShell, relative Bash + PowerShell (backslash and forward slash)
        self.assertEqual(len(self.rules), 5 * len(SAFE))

    def test_homes_do_not_get_ship_rules(self):
        for role in ("expert", "researcher", "scientist", "author"):
            rules = bootstrap.permission_rules(role, self.env, self.ws)
            self.assertFalse([r for r in rules if "ship.py" in r], role)

    def _settings(self):
        with open(os.path.join(self.root, ".claude", "settings.local.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_workspace_root_settings_get_the_rules(self):
        bootstrap.write_root_settings(self.env, self.ws)
        allow = self._settings()["permissions"]["allow"]
        self.assertIn("Bash(py %s/scripts/ship.py status:*)" % self.root, allow)
        self.assertIn("Bash(py scripts/ship.py status:*)", allow)

    def test_write_root_settings_idempotent(self):
        bootstrap.write_root_settings(self.env, self.ws)
        first = self._settings()
        bootstrap.write_root_settings(self.env, self.ws)
        self.assertEqual(self._settings(), first)

    def test_write_root_settings_preserves_existing_keys(self):
        os.makedirs(os.path.join(self.root, ".claude"))
        with open(os.path.join(self.root, ".claude", "settings.local.json"), "w", encoding="utf-8") as fh:
            json.dump({"model": "x", "env": {"KEEP": "1"},
                       "permissions": {"allow": ["Bash(ls:*)"], "deny": ["Bash(rm:*)"]}}, fh)
        bootstrap.write_root_settings(self.env, self.ws)
        cur = self._settings()
        self.assertEqual(cur["model"], "x")
        self.assertEqual(cur["env"]["KEEP"], "1")
        self.assertEqual(cur["permissions"]["deny"], ["Bash(rm:*)"])
        self.assertEqual(cur["permissions"]["allow"][0], "Bash(ls:*)")
        self.assertIn("Bash(py scripts/ship.py ship:*)", cur["permissions"]["allow"])

    def test_write_root_settings_retires_accept_baseline_rules(self):
        # an earlier bootstrap allowlisted accept-baseline; the rules are append-only, so a
        # re-run must drop the retired ones explicitly or the verb never prompts
        os.makedirs(os.path.join(self.root, ".claude"))
        old = ["Bash(ls:*)", "Bash(py scripts/ship.py accept-baseline:*)",
               "PowerShell(py scripts\\ship.py accept-baseline:*)",
               "Bash(py %s/scripts/ship.py accept-baseline:*)" % self.root]
        with open(os.path.join(self.root, ".claude", "settings.local.json"), "w", encoding="utf-8") as fh:
            json.dump({"permissions": {"allow": old}}, fh)
        bootstrap.write_root_settings(self.env, self.ws)
        allow = self._settings()["permissions"]["allow"]
        self.assertEqual([r for r in allow if "accept-baseline" in r], [])
        self.assertEqual(allow[0], "Bash(ls:*)")
        self.assertIn("Bash(py scripts/ship.py checkpoint:*)", allow)


if __name__ == "__main__":
    unittest.main()
