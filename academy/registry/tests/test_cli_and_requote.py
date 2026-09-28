"""``py -m registry`` dispatch and the R2 requote."""
import contextlib
import io
import os
import subprocess
import sys
import unittest

from _util import ENGINE, Homes, write

from registry import cli, requote
from registry.profiles import fsl

LEGACY = """---
id: lab:old
title: Search: a pair (x,y) with {braces}
status: open
where:
evidence:
history:
  - 2026-09-24 | open | created: by hand
open:
  - |v| <= 2 only
tags: [a, b]
---
Body kept.

## More
"""


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = cli.main(argv)
        except SystemExit as exc:
            rc = exc.code
    return rc, out.getvalue(), err.getvalue()


class TestCli(Homes):
    def test_dispatch_by_profile(self):
        rc, out, _ = run(["--repo", str(self.lab), "check"])
        self.assertEqual(rc, 0, out)
        self.assertIn("1 claims: 0 error(s), 0 warning(s)", out)
        rc, out, _ = run(["check", "--root", str(self.s1)])
        self.assertEqual(rc, 0, out)
        self.assertIn("check: 3 entities, 0 errors, 0 warnings", out)
        rc, out, _ = run(["--repo", str(self.s1), "show", "N8"])
        self.assertIn("(resolved from alias 'N8')", out)
        rc, out, _ = run(["--repo", str(self.lab), "show", "lab:foo"])
        self.assertIn("experiment experiments/x.py", out)

    def test_engine_commands(self):
        rc, out, _ = run(["--repo", str(self.lab), "federation"])
        self.assertIn("lab\t(this repo)", out)
        self.assertIn("s1-kb", out)
        rc, out, _ = run(["--repo", str(self.lab), "classes", "--ns", "s1"])
        self.assertIn("s1:CEX-1\tclaim\tDisproved\tfalse", out)
        rc, out, _ = run(["--repo", str(self.lab), "graph", "deps", "lab:foo"])
        self.assertIn("paper:prop:foo (bears_on)", out)

    def test_python_dash_m(self):
        env = dict(os.environ, PYTHONPATH=str(ENGINE), PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-m", "registry", "--repo", str(self.lab), "list"],
                           capture_output=True, env=env, cwd=str(self.tmp))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn(b"lab:foo", p.stdout)


class TestRequote(Homes):
    def test_equal_as_data_and_written_lf(self):
        p = write(self.lab / "claims" / "lab" / "old.md", LEGACY, newline="\r\n")
        c = fsl.parse_text(p.read_text(encoding="utf-8"))
        self.assertTrue(c.dialect_error)
        rows = requote.run(self.lab, write=True)
        row = [r for r in rows if r["file"].endswith("old.md")][0]
        self.assertEqual(row["status"], "equal", row)
        self.assertTrue(row["written"])
        raw = p.read_bytes()
        self.assertNotIn(b"\r", raw)
        text = raw.decode("utf-8")
        self.assertIn('title: "Search: a pair (x,y) with {braces}"', text)
        self.assertIn('where: ""', text)
        self.assertIn("evidence: []", text)
        self.assertIn("tags:\n  - a\n  - b", text)
        self.assertTrue(text.endswith("---\nBody kept.\n\n## More\n"))
        new = fsl.parse_text(text, fallback=False)
        self.assertIsNone(new.dialect_error)
        self.assertEqual((new.fields, new.body), (c.fields, c.body))
        # idempotent
        self.assertFalse([r for r in requote.run(self.lab) if r["changed_text"]])
        md = requote.report([("lab", str(self.lab), rows)])
        self.assertIn("| 2 | 2 | 0 | 0 |", md)


if __name__ == "__main__":
    unittest.main()
