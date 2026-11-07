"""bootstrap's plugin step: missing plugins are installed, installed ones are updated.

Claude Code caches a plugin per version, so an installed plugin is never refreshed unless
something asks (2026-11-07: a session kept 0.1.0 skills without the workflow calls). A fake
``claude`` on PATH logs its argv; ``plugin list`` answers from a file. Skipped on Windows.
"""
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "scripts"))
import workspace_bootstrap as bootstrap  # noqa: E402

FAKE = """#!/bin/sh
echo "$*" >> "{log}"
if [ "$1 $2" = "plugin list" ]; then cat "{listing}"; exit 0; fi
if [ "$1 $2" = "plugin update" ]; then
  case "$3" in
    {fail}@academy) echo "update failed: boom" >&2; exit 1 ;;
    {same}@academy) echo "$3 is already at the latest version"; exit 0 ;;
  esac
  echo "Updated $3 to 0.2.0"; exit 0
fi
if [ "$1 $2" = "plugin install" ]; then echo "  > $3" >> "{listing}"; fi
exit 0
"""


@unittest.skipIf(os.name == "nt", "a sh fake of the claude CLI")
class PluginStepTests(unittest.TestCase):
    NAMES = ["academy", "author", "expert"]

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="acad-bp-")
        self.addCleanup(shutil.rmtree, self.root, True)
        with open(os.path.join(self.root, bootstrap.TEMPLATE), "w", encoding="utf-8") as fh:
            json.dump({"plugins": self.NAMES}, fh)
        old, bootstrap.ROOT = bootstrap.ROOT, self.root
        self.addCleanup(setattr, bootstrap, "ROOT", old)
        self.bin = os.path.join(self.root, "bin")
        os.mkdir(self.bin)
        self.log = os.path.join(self.root, "calls.log")
        self.listing = os.path.join(self.root, "listing.txt")
        old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = self.bin + os.pathsep + old_path
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)

    def fake(self, installed, fail="none", same="none"):
        with open(self.listing, "w", encoding="utf-8") as fh:
            fh.write("Installed plugins:\n\n" + "".join("  > %s@academy\n" % n for n in installed))
        p = os.path.join(self.bin, "claude")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(FAKE.format(log=self.log, listing=self.listing, fail=fail, same=same))
        os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)

    def run_step(self, **kw):
        buf = StringIO()
        with redirect_stdout(buf):
            bootstrap.plugins(**kw)
        with open(self.log, encoding="utf-8") as fh:
            calls = [c.strip() for c in fh if not c.startswith("plugin list")]
        return calls, buf.getvalue()

    def test_installed_plugins_are_updated_after_the_marketplace(self):
        self.fake(self.NAMES)
        calls, out = self.run_step()
        self.assertEqual(calls, ["plugin marketplace update academy"]
                         + ["plugin update %s@academy --scope project" % n for n in self.NAMES])
        self.assertNotIn("-y", " ".join(calls))           # a declared command is a person's to accept
        self.assertIn("plugin academy     available (updated)", out)
        self.assertIn("restart Claude Code", out)

    def test_missing_ones_are_installed_and_the_rest_updated(self):
        self.fake(["academy"])
        calls, out = self.run_step()
        self.assertIn("plugin update academy@academy --scope project", calls)
        self.assertNotIn("plugin update author@academy --scope project", calls)
        self.assertIn("plugin install author@academy --scope project", calls)
        self.assertIn("plugin install expert@academy --scope project", calls)
        self.assertIn("plugin author      available", out)

    def test_no_plugin_update_skips_the_step(self):
        self.fake(self.NAMES)
        calls, out = self.run_step(update=False)
        self.assertEqual(calls, [])
        self.assertNotIn("restart", out)

    def test_a_failed_update_is_reported_and_up_to_date_is_told_apart(self):
        self.fake(self.NAMES, fail="author", same="expert")
        calls, out = self.run_step()
        self.assertIn("plugin author      available (update failed)", out)
        self.assertIn("plugin expert      available (up to date)", out)
        self.assertIn("claude plugin update author@academy failed", out)


class VersionPinTests(unittest.TestCase):
    """Every plugin of the marketplace carries one version, the MCP server's: a bump that
    misses a plugin would leave its cache stale."""

    def test_one_version_for_every_plugin(self):
        top = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
        with open(os.path.join(top, ".claude-plugin", "marketplace.json"), encoding="utf-8") as fh:
            entries = json.load(fh)["plugins"]
        versions = {}
        for e in entries:
            with open(os.path.join(top, e["source"], ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
                versions[e["name"]] = json.load(fh).get("version")
        sys.path.insert(0, os.path.join(top, "academy", "mcp"))
        import server  # noqa: E402
        self.assertEqual(set(versions.values()), {server.SERVER_VERSION}, versions)


if __name__ == "__main__":
    unittest.main()
