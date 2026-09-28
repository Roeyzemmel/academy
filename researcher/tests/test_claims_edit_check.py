"""claims_edit_check: the registry engine's check (and the s1 profile's blocking build) after a record edit."""

import json
import os
import sys
import unittest

from _fixtures import Workspace, write, record, researcher_config
import claims_edit_check  # noqa: E402

FAKE_CHECK = """import sys
path = sys.argv[-1]
text = open(path, encoding="utf-8").read()
if "BAD" in text:
    print("ERROR %s: bad field" % path)
    sys.exit(1)
print("0 errors")
"""


class ClaimsEditCheckTests(Workspace):
    def setUp(self):
        super().setUp()
        checker = write(os.path.join(self.tmp, "fake_check.py"), FAKE_CHECK)
        cfg = researcher_config()
        cfg["registry"]["check"] = "py %s" % checker.replace("\\", "/")
        write(os.path.join(self.R, ".claude", "academy.json"), json.dumps(cfg))

    def ev(self, path):
        return {"hook_event_name": "PostToolUse", "tool_name": "Edit",
                "tool_input": {"file_path": path}}

    def test_error_is_reported(self):
        p = write(os.path.join(self.R, "objects", "claim", "C-1.md"), record(extra="x: BAD\n"))
        rc, out = self.run_hook("claims_edit_check.py", self.ev(p))
        self.assertEqual(rc, 0)
        self.assertEqual(out["decision"], "block")
        self.assertIn("bad field", out["reason"])

    def test_clean_record_is_silent(self):
        p = write(os.path.join(self.R, "objects", "claim", "C-1.md"), record())
        self.assertEqual(self.run_hook("claims_edit_check.py", self.ev(p)), (0, None))

    def test_unswitched_home_owned_by_a_legacy_hook_is_silent(self):
        legacy = write(os.path.join(self.L, "claims", "lab", "x.md"), record(extra="x: BAD\n"))
        write(os.path.join(self.L, ".claude", "flatsurf.json"),
              json.dumps({"registry": {"tool": "claims.py"}}))
        journal = write(os.path.join(self.R, "journal", "d.md"), record(extra="x: BAD\n"))
        for p in (legacy, journal):
            with self.subTest(path=p):
                self.assertIsNone(claims_edit_check.run(self.ev(p)))
        os.remove(os.path.join(self.L, ".claude", "flatsurf.json"))
        write(os.path.join(self.L, ".claude", "settings.json"),
              '{"hooks": {"PostToolUse": [{"command": "py tools/kb_hook.py"}]}}')
        self.assertIsNone(claims_edit_check.run(self.ev(legacy)))

    def test_unswitched_home_without_legacy_hook_runs_the_engine(self):
        p = write(os.path.join(self.L, "claims", "lab", "x.md"), record(extra="x: BAD\n"))
        kind, reason = claims_edit_check.run(self.ev(p))
        self.assertEqual(kind, "block")
        self.assertIn("unknown field(s)", reason)
        self.assertIn("claims/lab/x.md", reason)

    def test_command_resolution(self):
        rec = {"home": "/h", "config": {"registry": {"legacy": {"claims": "py x.py"}}}}
        argv = claims_edit_check.check_command(rec, "/h/objects/c.md")
        self.assertEqual(argv[:6], [sys.executable, "-m", "registry", "--repo", "/h", "check"])
        self.assertEqual(argv[-1], os.path.abspath("/h/objects/c.md").replace("\\", "/"))
        rec = {"config": {"registry": {"check": "py reg.py check {file} --strict"}}}
        argv = claims_edit_check.check_command(rec, "x.md")
        self.assertEqual(argv[0], sys.executable)
        self.assertEqual(argv[-1], "--strict")


S1_CLAIM = """---
id: GEO-1
aliases: []
title: Corners
summary: Corners of P are cycles
kind: prop
status: {status}
---
## Statement
**Proposition** ({status}). Corners of $P$ are cycles.
"""


class S1ProfileHookTests(Workspace):
    """A home on the s1-kb profile: check <file>, then a blocking build (as kb_hook)."""

    def setUp(self):
        super().setUp()
        cfg = researcher_config(instance="researcher@old", ns="s8")
        cfg["registry"] = {"profile": "s1", "root": "claims", "statusKeeper": "claim-keeper"}
        cfg["paths"]["records"] = ["claims", "assumptions", "examples"]
        write(os.path.join(self.O, ".claude", "academy.json"), json.dumps(cfg))

    def ev(self, path):
        return {"hook_event_name": "PostToolUse", "tool_name": "Write",
                "tool_input": {"file_path": path}}

    def test_good_edit_builds_the_views(self):
        p = write(os.path.join(self.O, "claims", "GEO-1.md"), S1_CLAIM.format(status="Proved"))
        rc, out = self.run_hook("claims_edit_check.py", self.ev(p))
        self.assertEqual((rc, out), (0, None))
        self.assertTrue(os.path.isfile(os.path.join(self.O, "STATUS.md")))

    def test_bad_edit_fails_the_build_with_exit_2(self):
        p = write(os.path.join(self.O, "claims", "GEO-1.md"), S1_CLAIM.format(status="Proven"))
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        import subprocess
        res = subprocess.run([sys.executable, os.path.join(os.path.dirname(claims_edit_check.__file__),
                                                           "claims_edit_check.py")],
                             input=json.dumps(self.ev(p)).encode(), capture_output=True, env=env,
                             cwd=self.tmp, timeout=90)
        self.assertEqual(res.returncode, 2, res.stderr)
        err = res.stderr.decode("utf-8")
        self.assertIn("status 'Proven' is not one of", err)
        self.assertIn("build failed", err)
        self.assertFalse(os.path.isfile(os.path.join(self.O, "STATUS.md")))

    def test_objects_layout_edit_builds_the_views(self):
        # R6: records live in objects/<kind>/; an edit there must rebuild the views too
        cfg = researcher_config(instance="researcher@old", ns="s8")
        cfg["registry"] = {"profile": "s1", "root": "objects", "statusKeeper": "claim-keeper"}
        cfg["paths"]["records"] = "objects"
        write(os.path.join(self.O, ".claude", "academy.json"), json.dumps(cfg))
        p = write(os.path.join(self.O, "objects", "claim", "GEO-1.md"),
                  S1_CLAIM.format(status="Proved"))
        rc, out = self.run_hook("claims_edit_check.py", self.ev(p))
        self.assertEqual(rc, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(self.O, "STATUS.md")))

if __name__ == "__main__":
    unittest.main()
