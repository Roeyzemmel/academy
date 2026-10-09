"""The ``s1-kb`` profile (a notebook registry: aliases, assumptions, views, mutations).
Moved from Slope1illuminationResearch's ``tools/test_kb.py`` on 2026-10-09; the fixture
is self-contained."""
from __future__ import annotations

import contextlib
import difflib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _util import ENGINE as _ENGINE_PATH  # noqa: E402

ENGINE = str(_ENGINE_PATH)
from registry.profiles import s1kb as kb  # noqa: E402

VERDICT = "computation/verdicts/2026-09-24_G8-N22.md"

# the home's id rules (registry.prefixes / assumptionGroups, docs/config.md): topic order
# and assumption groups come from academy.json, not from the engine
RULES = {"ns": "s1", "registry": {"profile": "s1", "root": ".", "prefixes": [
    "Q", "OA", "PA", "GA", "DEF", "GEO", "STR", "CRIT", "OBS", "CEX", "BOUND", "COMP",
    "OPEN", "EX", "DIR"], "assumptionGroups": {"OA": "Origami", "PA": "Parking garage",
                                                "GA": "Group-theoretic tags"}}}

FIXTURE = {
    ".claude/academy.json": json.dumps(RULES),
    "assumptions/OA-2.md": """---
id: OA-2
title: Involution with derivative -I
kind: assumption
old: "(A2)"
implies: []
incomparable_with: []
---
## Statement
Old (A2).
""",
    "assumptions/OA-3.md": """---
id: OA-3
title: "(A3) condition"
kind: assumption
old: "(A3)"
implies: [OA-2]
incomparable_with: []
---
## Statement
Old (A3).
""",
    "assumptions/PA-4.md": """---
id: PA-4
title: Unfolding of a parking garage
kind: assumption
old: "(A4)"
implies: [OA-3]
incomparable_with: []
---
## Statement
Old (A4).
""",
    "assumptions/PA-5.md": """---
id: PA-5
title: Parking garage with more structure
kind: assumption
old: "(A5)"
implies: [PA-4]
incomparable_with: [PA-SC]
---
## Statement
Old (A5).
""",
    "assumptions/PA-SC.md": """---
id: PA-SC
title: Simply connected, transverse
kind: assumption
old: "(SC)"
implies: [OA-3]
incomparable_with: [PA-5]
---
## Statement
Old (SC).
""",
    "claims/Q2.md": """---
id: Q2
aliases: []
title: "Question (Q2)"
summary: Does every slope-1 trajectory family illuminate?
kind: question
status: Not settled
status_by_level:
  OA-0..OA-3: Disproved
  PA-4..PA-7: Not settled
topics: [q2]
added: 2026-09-10
---
## Statement
Q2 statement.
""",
    "claims/GEO-1.md": """---
id: GEO-1
aliases: [R Prop 1.6]
title: Corners and commutator cycles
summary: "Corners of P correspond to cycles of [σ,τ]"
kind: prop
status: Proved
level: OA-3
topics: [geometry]
added: 2026-09-10
---
## Statement
**Proposition 1.6** (Proved). Corners of $P$ are cycles.

## Proof
Easy.
""",
    "claims/CEX-3.md": """---
id: CEX-3
aliases: [N22, G8]
title: "O_16^a fails (Q2) at (A3)"
summary: "(Q2) fails on a 16-square Cayley origami at level OA-3"
kind: prop
status: Proved
status_note: ""
level: OA-3
topics: [q2, counterexample]
examples: [EX-O16a]
depends_on: [GEO-1]
supersedes: []
superseded_by: []
cleared_by: [computation/verdicts/2026-09-24_G8-N22.md]
source: "writing/n8-generalization.md §4.1"
added: 2026-09-24
---
## Statement
**Proposition N22** (Proved). The origami $O_{16}^a$ fails (Q2); compare R Prop 1.6.

## Proof
SECRET-PROOF-TEXT uses N22 and (A3).

## Notes
Nothing.

## History
- 2026-09-24: created
""",
    "claims/OPEN-1.md": """---
id: OPEN-1
aliases: [CEX-11]
title: (Q2) at level (A4)
summary: Does (Q2) hold for parking-garage unfoldings?
kind: open
status: Not settled
level: PA-4
topics: [q2]
added: 2026-09-11
---
## Statement
Open.
""",
    "examples/EX-O16a.md": """---
id: EX-O16a
aliases: [O16a]
title: The Cayley origami of Z/4 ⋊ Z/4
level: OA-3
q2: fails
n: "16"
runs: [E2a]
---
Key facts.
""",
    VERDICT: """---
date: 2026-09-24
kind: claim-verification
subjects: [CEX-3]
clears: [CEX-3]
decision: cleared
models: [Opus 5.5, Fable 5.1]
---
Both runs agree.
""",
    "computation/runs/E2a.md": """---
status: done
family: EW
script: fslab/christoffel/e2a.py
jobs: ["42"]
class_short: "EW covers, n ≤ 64"
---
Run notes.
""",
    "notes/03-q2/topic.md": "# Topic page\n\nProse before.  \n\n"
                            "<!-- kb:list topic=q2 -->\nstale content\n<!-- /kb:list -->\n\n"
                            "Prose after, verbatim.\n",
    "kb/retired.txt": "# ids that were retired\nretired_ids: [CEX-9]\n",
}


def run(root, *argv):
    """Run kb.main in-process; return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = kb.main([*argv, "--root", str(root)])
    return rc, out.getvalue(), err.getvalue()


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kbtest_"))
        for rel, text in FIXTURE.items():
            p = self.tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def edit(self, rel, old, new):
        p = self.tmp / rel
        text = p.read_text(encoding="utf-8")
        self.assertIn(old, text)
        p.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


class TestFrontmatter(unittest.TestCase):
    def test_round_trip(self):
        d = {"id": "GA-CT′", "aliases": ["(CT′)", "R2 Thm 4.7", "a, b", ""],
             "title": 'He said "hi": #1 [x]', "summary": "- leading dash",
             "kind": "prop", "status": "Proved modulo stated inputs", "status_note": "",
             "level": "DEF-Λ", "topics": [], "added": "2026-09-24",
             "status_by_level": {"OA-0..OA-3": "Disproved", "PA-6∖PA-7": "Reduced",
                                 "key: colon": ["x", "y"]},
             "empty_map": {}, "zeta": "back\\slash\nnewline", "alpha": "it's"}
        text = kb.serialize_frontmatter(d)
        self.assertEqual(kb.parse_frontmatter(text.split("\n")), d)
        self.assertTrue(text.startswith("id: GA-CT′\naliases:"))
        keys = [line.split(":")[0] for line in text.split("\n") if line and line[0] != " "]
        self.assertEqual(keys, ["id", "aliases", "title", "summary", "kind", "status",
                                "status_note", "level", "topics", "added", "alpha",
                                "empty_map", "status_by_level", "zeta"])

    def test_parse_forms(self):
        lines = ["id: DEF-Λ  # comment", "q: 'it''s'", "blk:", "  - a", "  - \"b, c\"",
                 "blk2:", "- x", "", "# full-line comment", "m:", "  A..B: Proved",
                 "  C: [1, 2]", "l: [a, 'b', \"c, d\"]", "date: 2026-09-24"]
        d = kb.parse_frontmatter(lines, "f.md")
        self.assertEqual(d, {"id": "DEF-Λ", "q": "it's", "blk": ["a", "b, c"],
                             "blk2": ["x"], "m": {"A..B": "Proved", "C": ["1", "2"]},
                             "l": ["a", "b", "c, d"], "date": "2026-09-24"})

    def test_rejects(self):
        bad = {
            "flow map": ["a: {x: 1}"],
            "tab indent": ["m:", "\tk: v"],
            "no space": ["a:b"],
            "nested list": ["a: [[b]]"],
            "unterminated": ['a: "abc'],
            "duplicate": ["a: 1", "a: 2"],
            "colon in bare": ["a: b: c"],
            "anchor": ["a: &x b"],
            "empty value": ["a:", "b: c"],
            "two-level map": ["m:", "  k: {}"],
            "trailing comma": ["a: [b, ]"],
            "not a key": ["just text"],
            "bad escape": ['a: "\\q"'],
            "mixed nested indent": ["m:", "  a: 1", "    b: 2"],
        }
        for name, lines in bad.items():
            with self.subTest(name), self.assertRaises(kb.FrontmatterError) as cm:
                kb.parse_frontmatter(["id: X"] + lines, "claims/X.md", 2)
            self.assertRegex(str(cm.exception), r"^claims/X\.md:\d+: ")

    def test_error_names_line(self):
        with self.assertRaises(kb.FrontmatterError) as cm:
            kb.split_document("---\nid: A\ntitle: ok\nbad: {x}\n---\n", "claims/A.md")
        self.assertTrue(str(cm.exception).startswith("claims/A.md:4:"))

    def test_normalize(self):
        forms = ["R2 Thm 4.7", "R2 Thm. 4.7", "r2-thm4.7", "R2 Theorem 4.7"]
        self.assertEqual({kb.normalize(f) for f in forms}, {"r2thm4.7"})
        self.assertNotEqual(kb.normalize("(2T)"), kb.normalize("(2T′)"))
        self.assertEqual(kb.normalize("(CT′)"), kb.normalize("(CT')"))


class TestAliases(FixtureCase):
    def test_lookup(self):
        k = kb.load_kb(self.tmp)
        for text in ("N22", "n22", "G8", " g8 ", "CEX-3", "cex3"):
            with self.subTest(text):
                self.assertEqual(kb.lookup(k, text)[0], "CEX-3")
        self.assertEqual(kb.lookup(k, "N22"), ("CEX-3", True))
        self.assertEqual(kb.lookup(k, "CEX-3"), ("CEX-3", False))
        self.assertEqual(kb.lookup(k, "(A3)")[0], "OA-3")
        self.assertEqual(kb.lookup(k, "R Prop. 1.6")[0], "GEO-1")
        self.assertEqual(kb.lookup(k, "R Proposition 1.6")[0], "GEO-1")
        self.assertIsNone(kb.lookup(k, "N99")[0])

    def test_reverse_edges(self):
        k = kb.load_kb(self.tmp)
        self.assertEqual(k.entities["GEO-1"].usedby, ["CEX-3"])
        self.assertEqual(k.entities["EX-O16a"].example_claims, ["CEX-3"])
        self.assertEqual(k.entities["OA-3"].implied_by, ["PA-4", "PA-SC"])

    def test_resolve_command(self):
        rc, out, _ = run(self.tmp, "resolve", "see N22, R2 Thm 4.7 and (A3), (SC); G8")
        self.assertEqual(rc, 0)
        self.assertIn("N22 → CEX-3 · Proved", out)
        self.assertIn("G8 → CEX-3", out)
        self.assertIn("(A3) → OA-3", out)
        self.assertIn("(SC) → PA-SC", out)
        self.assertIn("R2 Thm 4.7 → (unresolved)", out)


class TestCheck(FixtureCase):
    def check(self):
        return run(self.tmp, "check")

    def test_clean(self):
        rc, out, _ = self.check()
        self.assertEqual(rc, 0, out)
        self.assertIn("0 errors", out)

    def test_dangling_depends_on(self):
        self.edit("claims/CEX-3.md", "depends_on: [GEO-1]", "depends_on: [GEO-1, GEO-77]")
        rc, out, _ = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("depends_on: 'GEO-77' does not resolve", out)

    def test_asymmetric_supersession(self):
        self.edit("claims/CEX-3.md", "supersedes: []", "supersedes: [GEO-1]")
        rc, out, _ = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("CEX-3 supersedes GEO-1, but GEO-1 has no superseded_by", out)

    def test_bad_status(self):
        self.edit("claims/GEO-1.md", "status: Proved", "status: Proven")
        rc, out, _ = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("status 'Proven' is not one of", out)

    def test_duplicate_alias(self):
        self.edit("claims/OPEN-1.md", "aliases: [CEX-11]", "aliases: [CEX-11, n22]")
        rc, out, _ = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("duplicate alias 'n22'", out)

    def test_alias_collides_with_id(self):
        self.edit("claims/OPEN-1.md", "aliases: [CEX-11]", "aliases: [GEO-1]")
        rc, out, _ = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("collides with the id 'GEO-1'", out)

    def test_incomparable_path(self):
        self.edit("assumptions/PA-SC.md", "implies: [OA-3]", "implies: [PA-5]")
        rc, out, _ = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("an implies-path joins them", out)

    def test_warnings(self):
        self.edit("claims/GEO-1.md", "status: Proved", "status: Partial")
        rc, out, _ = self.check()
        self.assertEqual(rc, 0, out)
        self.assertIn("WARNING claims/CEX-3.md: Proved, but depends_on GEO-1", out)
        self.assertIn("body's first status phrase is 'Proved' but frontmatter says 'Partial'", out)

    def test_parse_error_reported(self):
        self.edit("claims/GEO-1.md", "kind: prop", "kind: {prop}")
        rc, out, _ = self.check()
        self.assertEqual(rc, 1)
        self.assertIn("ERROR claims/GEO-1.md:6:", out)

    def test_cli_subprocess(self):
        code = ("import sys; sys.path.insert(0, %r); from registry.profiles import s1kb; "
                "sys.exit(s1kb.main())" % ENGINE)
        proc = subprocess.run([sys.executable, "-c", code, "check", "--root",
                               str(self.tmp)], capture_output=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class TestBuild(FixtureCase):
    VIEWS = ["STATUS.md", "INDEX.md", "OPEN.md", "assumptions/README.md",
             "computation/verdicts.md", "computation/runs.md", "site/index.html"]

    def test_build_writes_views(self):
        rc, out, _ = run(self.tmp, "build")
        self.assertEqual(rc, 0, out)
        for rel in self.VIEWS:
            with self.subTest(rel):
                first = (self.tmp / rel).read_text(encoding="utf-8").split("\n")[0]
                self.assertEqual(first, kb.GENERATED)
        data = json.loads((self.tmp / "kb/claims.json").read_text(encoding="utf-8"))
        self.assertEqual(data["alias_patterns"], kb.ALIAS_PATTERNS)
        self.assertIn("SECRET-PROOF-TEXT", next(e["body"] for e in data["entities"]
                                                if e["id"] == "CEX-3"))
        con = sqlite3.connect(self.tmp / "kb/kb.sqlite")
        edges = con.execute("SELECT src, dst, kind FROM edges WHERE kind='depends_on'").fetchall()
        con.close()
        self.assertEqual(edges, [("CEX-3", "GEO-1", "depends_on")])

    def test_view_contents(self):
        run(self.tmp, "build")
        status = (self.tmp / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn("| [Q2](claims/Q2.md) | OA-0..OA-3 | Disproved |", status)
        self.assertIn("| [CEX-3](claims/CEX-3.md) | N22, G8 | Proved |", status)
        index = (self.tmp / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("| N22 | [CEX-3](claims/CEX-3.md) | claims/CEX-3.md |", index)
        opened = (self.tmp / "OPEN.md").read_text(encoding="utf-8")
        self.assertIn("OPEN-1", opened)
        self.assertNotIn("CEX-3", opened)
        readme = (self.tmp / "assumptions/README.md").read_text(encoding="utf-8")
        self.assertIn("graph TD", readme)
        self.assertIn(" -.- ", readme)
        site = (self.tmp / "site/index.html").read_text(encoding="utf-8")
        self.assertNotIn("</script>\n</body>", site.split('id="kb-data"')[1][:200])
        self.assertLess(len(site.encode("utf-8")), 2_000_000)

    def test_marker_fill_preserves_surroundings(self):
        rel = "notes/03-q2/topic.md"
        before = (self.tmp / rel).read_bytes()
        rc, out, _ = run(self.tmp, "build")
        self.assertEqual(rc, 0, out)
        after = (self.tmp / rel).read_bytes()
        start, end = b"<!-- kb:list topic=q2 -->", b"<!-- /kb:list -->"
        self.assertEqual(before.split(start)[0], after.split(start)[0])
        self.assertEqual(before.split(end)[1], after.split(end)[1])
        inner = after.split(start)[1].split(end)[0].decode("utf-8")
        self.assertNotIn("stale content", inner)
        self.assertIn("- [CEX-3](../../claims/CEX-3.md) — Proved — ", inner)
        self.assertIn("[Q2](../../claims/Q2.md)", inner)
        self.assertNotIn("GEO-1", inner)
        run(self.tmp, "build")                      # idempotent
        self.assertEqual(after, (self.tmp / rel).read_bytes())

    def test_build_aborts_on_error(self):
        self.edit("claims/GEO-1.md", "status: Proved", "status: Proven")
        rc, _, _ = run(self.tmp, "build")
        self.assertEqual(rc, 1)
        self.assertFalse((self.tmp / "STATUS.md").exists())

    def test_sql_builds_first(self):
        rc, out, _ = run(self.tmp, "sql", "SELECT id FROM entities WHERE status='Not settled' "
                                          "ORDER BY id")
        self.assertEqual(rc, 0)
        self.assertEqual(out.split("\n")[:3], ["id", "OPEN-1", "Q2"])


class TestQueries(FixtureCase):
    def test_show_brief(self):
        rc, out, _ = run(self.tmp, "show", "N22")
        self.assertEqual(rc, 0)
        self.assertIn("(resolved from alias 'N22')", out)
        self.assertIn("## Statement", out)
        self.assertIn("**Proposition N22**", out)
        self.assertNotIn("SECRET-PROOF-TEXT", out)
        self.assertNotIn("## Proof", out)

    def test_show_full_and_deps(self):
        rc, out, _ = run(self.tmp, "show", "G8", "--full", "--deps")
        self.assertIn("SECRET-PROOF-TEXT", out)
        self.assertIn("depends_on: GEO-1 · Proved · Corners of P", out)
        rc, out, _ = run(self.tmp, "show", "GEO-1", "--deps")
        self.assertIn("usedby: CEX-3 · Proved", out)

    def test_show_example(self):
        rc, out, _ = run(self.tmp, "show", "EX-O16a")
        self.assertIn("claims: CEX-3", out)

    def test_find(self):
        _, out, _ = run(self.tmp, "find", "--level-at-least", "OA-3")
        ids = [line.split(" · ")[0] for line in out.strip().split("\n")]
        self.assertEqual(ids, ["GEO-1", "CEX-3", "OPEN-1", "EX-O16a"])
        _, out, _ = run(self.tmp, "find", "--level-at-least", "PA-4")
        self.assertEqual(out.strip(), "OPEN-1 · Not settled · Does (Q2) hold for "
                                      "parking-garage unfoldings?")
        _, out, _ = run(self.tmp, "find", "--level-at-least", "(A2)", "--prefix", "cex")
        self.assertEqual(out.split(" · ")[0], "CEX-3")
        _, out, _ = run(self.tmp, "find", "--status", "not settled", "--topic", "q2")
        self.assertEqual([l.split(" · ")[0] for l in out.strip().split("\n")], ["Q2", "OPEN-1"])
        _, out, _ = run(self.tmp, "find", "secret-proof")
        self.assertTrue(out.startswith("CEX-3 · "))

    def test_deps_usedby_transitive(self):
        self.edit("claims/OPEN-1.md", "level: PA-4", "level: PA-4\ndepends_on: [CEX-3]")
        _, out, _ = run(self.tmp, "usedby", "GEO-1", "--transitive")
        self.assertEqual([l.strip().split(" · ")[0] for l in out.strip().split("\n")],
                         ["CEX-3", "OPEN-1"])
        _, out, _ = run(self.tmp, "deps", "OPEN-1")
        self.assertEqual(out.strip().split(" · ")[0], "CEX-3")


class TestMutations(FixtureCase):
    def test_new_skips_retired_and_aliases(self):
        rc, out, _ = run(self.tmp, "new", "CEX", "--kind", "prop", "--title", "A new one")
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.strip(), "claims/CEX-12.md")     # CEX-11 alias, CEX-9 retired
        text = (self.tmp / "claims/CEX-12.md").read_text(encoding="utf-8")
        meta, body = kb.split_document(text)
        self.assertEqual((meta["id"], meta["kind"], meta["title"], meta["status"]),
                         ("CEX-12", "prop", "A new one", "Not settled"))
        for head in ("## Statement", "## Proof", "## Notes", "## History"):
            self.assertIn(head, body)
        self.assertIn(f"- {kb.today()}: created", body)
        rc, out, _ = run(self.tmp, "new", "CEX")
        self.assertEqual(out.strip(), "claims/CEX-13.md")
        rc, out, _ = run(self.tmp, "new", "BOUND")
        self.assertEqual(out.strip(), "claims/BOUND-1.md")
        self.assertEqual(run(self.tmp, "check")[0], 0)

    def test_set_status_edits_only_intended_lines(self):
        v2 = "computation/verdicts/2026-09-25_N22-repair.md"
        (self.tmp / v2).write_text("---\ndate: 2026-09-25\nsubjects: [CEX-3]\n---\nok\n",
                                   encoding="utf-8", newline="\n")
        path = self.tmp / "claims/CEX-3.md"
        before = path.read_text(encoding="utf-8").split("\n")
        rc, out, _ = run(self.tmp, "set-status", "N22", "Proved modulo stated inputs",
                         "--verdict", v2, "--note", "one input")
        self.assertEqual(rc, 0, out)
        after = path.read_text(encoding="utf-8").split("\n")
        diff = [l for l in difflib.ndiff(before, after) if l[:2] in ("- ", "+ ")]
        self.assertEqual(sorted(l for l in diff if l.startswith("- ")), sorted([
            "- status: Proved", '- status_note: ""',
            f"- cleared_by: [{VERDICT}]"]))
        self.assertEqual(sorted(l for l in diff if l.startswith("+ ")), sorted([
            "+ status: Proved modulo stated inputs", "+ status_note: one input",
            f"+ cleared_by: [{VERDICT}, {v2}]",
            f"+ - {kb.today()}: status Proved → Proved modulo stated inputs (verdict {v2})"]))
        hist = after[after.index("## History"):]
        self.assertEqual(hist[1:3], ["- 2026-09-24: created",
                                     f"- {kb.today()}: status Proved → Proved modulo "
                                     f"stated inputs (verdict {v2})"])
        self.assertTrue((self.tmp / "STATUS.md").exists())    # build ran

    def test_set_status_block_list_and_missing_history(self):
        self.edit("claims/GEO-1.md", "added: 2026-09-10", "added: 2026-09-10\ncleared_by:\n  - x.md")
        (self.tmp / "x.md").write_text("x", encoding="utf-8")
        rc, out, _ = run(self.tmp, "set-status", "GEO-1", "Partial", "--verdict", VERDICT)
        self.assertEqual(rc, 0, out)
        text = (self.tmp / "claims/GEO-1.md").read_text(encoding="utf-8")
        self.assertIn(f"cleared_by:\n  - x.md\n  - {VERDICT}\n", text)
        self.assertTrue(text.rstrip("\n").endswith(
            f"## History\n- {kb.today()}: status Proved → Partial (verdict {VERDICT})"))

    def test_set_status_rejects(self):
        self.assertEqual(run(self.tmp, "set-status", "CEX-3", "Proven", "--verdict", VERDICT)[0], 1)
        self.assertEqual(run(self.tmp, "set-status", "CEX-3", "Partial", "--verdict",
                             "computation/runs/E2a.md")[0], 1)
        self.assertEqual(run(self.tmp, "set-status", "CEX-3", "Partial", "--verdict",
                             "computation/verdicts/nope.md")[0], 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
