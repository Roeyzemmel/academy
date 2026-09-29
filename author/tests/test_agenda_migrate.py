"""agenda_migrate.py: legacy comment_roadmap.md -> agenda.md + roadmap.md.

A synthetic legacy roadmap pins the rules; the real PaperHome roadmap is
migrated from a copy in a temp dir (read-only on the home; skipped if absent).
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from fixtures import SCRIPTS

sys.path.insert(0, SCRIPTS)
import agenda_lib as al  # noqa: E402
import agenda_migrate as am  # noqa: E402


def _real_home(**want):
    """The home of the first workspace.json instance matching ``want`` (role=..., ns=...), or ''
    when there is no workspace: these tests run against real homes only where they exist."""
    try:
        with open(os.environ["ACADEMY_WORKSPACE"], encoding="utf-8-sig") as fh:
            ws = json.load(fh)
    except (KeyError, OSError, ValueError):
        return ""
    for inst in ws.get("instances", {}).values():
        if all(inst.get(k) == v for k, v in want.items()):
            return inst["home"]
    return ""


PAPER_HOME = _real_home(role="author")

LEGACY = """# Roadmap for the open margin notes

Tags: ...

---

## Tier 5 — something **[issues 1-2 of 3 done 2026-09-24]**

Header paragraph.

1. **[write]** Redefine `defn:corners` as above.
   **[done 2026-09-24]** (issue 1) — done it.
2. **[apply]** Define $\\Aff$ at `defn:corners` and in the notation list.
   **[done 2026-09-24 at `defn:corners`; notation list blocked]** — half.
3. **[lead]** (`top-researcher`) Prove `thm:main` with the
   route below.
   - step one
4. **[dropped 2026-09-24]** Not needed.

**Issues:** 1 = items 1-2.

5. **[needs Roey / notation]** *Use `Q_{g,b}`* instead.

## Carried over from the archive

- **[apply]** `lem:x` (`a.tex:90`): typo.
- **[verify]** Source pinpoints for `ex:y`: for `source-checker`.
- **[write, optional]** The cleaner route.
- **[done 2026-09-25, Roey in chat]** settled thing.
- a plain bullet that is not an item

## Verification queue

Arguments awaiting verification.

- `lem:x` — `sections/a.tex` — new sketch — queued by Tier 5, issue 1
- `thm:main` — `sections/b.tex` (moved from c) — restated — queued by Tier 5
"""


class MigrateRulesTests(unittest.TestCase):
    def run_migrate(self):
        return am.migrate(LEGACY, "author@t", "paper", None, {"paper:thm:main": "sketch"},
                          "2026-09-28")

    def test_live_items_and_tags(self):
        _a, roadmap, items, _e, counts, rows = self.run_migrate()
        got = [(it.tag, it.status, it.fields["source"].split(", ", 1)[1]) for it in items]
        self.assertEqual(got, [
            ("apply", "open", "Tier 5 item 2"),
            ("lead", "open", "Tier 5 item 3"),
            ("notation", "needs-human", "Tier 5 item 5"),
            ("apply", "open", "Carried over from the archive"),
            ("cite", "open", "Carried over from the archive"),
            ("write", "open", "Carried over from the archive"),
            ("verify", "open", "Verification queue: lem:x"),
            ("verify", "open", "Verification queue: thm:main"),
        ])
        self.assertEqual((counts["done"], counts["dropped"], counts["queue"]), (2, 1, 2))
        calls = {r[0]: r[5] for r in rows}
        self.assertTrue(any("qualified" in c for c in calls["R-0001"]))
        self.assertTrue(any("optional" in c for c in calls["R-0006"]))
        self.assertEqual(items[5].fields["priority"], "low")

    def test_bodies_are_verbatim_and_attached(self):
        _a, roadmap, items, entries, _c, _r = self.run_migrate()
        self.assertIn("   route below." .strip(), items[1].body)
        self.assertIn("- step one", items[1].body)
        self.assertEqual(items[1].fields["agenda"], "paper:thm:main")
        self.assertEqual(items[7].title, "Verify thm:main")
        self.assertEqual(items[7].fields["agenda"], "paper:thm:main")
        self.assertEqual(items[5].fields["agenda"], "global")
        # no paper root: the agenda is the labels the live items mention
        self.assertEqual([e.label for e in entries],
                         ["defn:corners", "thm:main", "lem:x", "ex:y"])
        self.assertEqual(entries[1].status, "sketch")
        rm = al.parse_roadmap(roadmap)
        self.assertEqual(al.write_roadmap(rm), roadmap)

    def test_output_passes_check(self):
        agenda, roadmap, *_ = self.run_migrate()
        self.assertEqual(al.check(al.parse_agenda(agenda), al.parse_roadmap(roadmap), "paper"),
                         [])


def _digest(path):
    h = hashlib.sha256()
    for dp, dn, fn in os.walk(path):
        dn[:] = [d for d in dn if d not in (".git", ".build")]
        for f in sorted(fn):
            p = os.path.join(dp, f)
            h.update(p.encode("utf-8"))
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


@unittest.skipUnless(os.path.isfile(os.path.join(PAPER_HOME, "Drafts", "comment_roadmap.md")),
                     "PaperHome not present")
class MigrateBiCopyTests(unittest.TestCase):
    """The real roadmap, from a copy; the paper is read in place (read-only)."""

    def test_paper_copy(self):
        tmp = tempfile.mkdtemp(prefix="paper-migrate-")
        try:
            src = os.path.join(tmp, "comment_roadmap.md")
            shutil.copyfile(os.path.join(PAPER_HOME, "Drafts", "comment_roadmap.md"), src)
            before = _digest(os.path.join(PAPER_HOME, "sections")), _digest(os.path.join(PAPER_HOME, "Drafts"))
            out = os.path.join(tmp, "out")
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
            res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "agenda_migrate.py"),
                                  "--roadmap", src, "--paper-root", PAPER_HOME, "--out", out],
                                 capture_output=True, env=env, timeout=300)
            self.assertEqual(res.returncode, 0, res.stderr.decode("utf-8", "replace"))
            after = _digest(os.path.join(PAPER_HOME, "sections")), _digest(os.path.join(PAPER_HOME, "Drafts"))
            self.assertEqual(before, after, "the migration wrote into the home")
            ag = al.parse_agenda(al.read_text(os.path.join(out, "agenda.md")))
            rm = al.parse_roadmap(al.read_text(os.path.join(out, "roadmap.md")))
            self.assertGreater(len(ag.entries), 50)
            self.assertGreater(len(rm.items), 30)
            self.assertEqual(al.check(ag, rm, "paper"), [])
            queue = [it for it in rm.items if it.fields.get("source", "").startswith(
                "comment_roadmap.md, Verification queue")]
            self.assertGreater(len(queue), 10)
            self.assertTrue(all(it.tag == "verify" for it in queue))
            self.assertTrue(os.path.isfile(os.path.join(out, "migration-report.md")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
