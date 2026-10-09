"""R6, the notebook layout of the s1-kb profile: objects/<kind>/, audits/, views/."""
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from _util import Homes, notebook_config, write

from registry.profiles import fsl, s1kb

CEX = """---
id: CEX-1
kind: claim
form: prop
title: t
status: refuted
lifecycle: active
summary: s
depends_on: [Q1]
evidence: []
history:
  - 2026-09-24 | refuted | created
---
## Statement
It fails.
"""

Q1 = """---
id: Q1
kind: question
form: question
title: q
status: open
lifecycle: active
summary: the question
evidence: []
history:
  - 2026-09-24 | open | created
---
## Statement
Does it?
"""

GA = """---
id: GA-2T
kind: assumption
title: a
lifecycle: active
implies: []
incomparable_with: []
evidence: []
history:
  - 2026-09-24 | | created
---
## Definition
x
"""

DIR = """---
id: DIR-1
kind: direction
title: d
lifecycle: active
evidence: []
history:
  - 2026-09-28 | | created
---
## Program

p

## Questions

<!-- - s1:NOPE-1 — a commented example is not an item -->
- s1:Q1 — the question

## Candidate claims

- s1:CEX-1 — the claim
- s1:GEO-99 — not written yet
"""

VERDICT = """---
id: 2026-09-23_E1-x
date: 2026-09-23
kind: result
subjects: [E1]
decision: cleared
---
ok
"""

REVIEW_RUN = """---
run: A
subject: lab:x
verdict: SOUND
---
a landed review run
"""


def run_kb(root, *argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = s1kb.main(list(argv) + ["--root", str(root)])
    return rc, out.getvalue() + err.getvalue()


class TestObjectsLayout(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="registry-r6-"))
        self.addCleanup(shutil.rmtree, str(self.root), True)
        notebook_config(self.root)
        o = self.root / "objects"
        write(o / "claim" / "CEX-1.md", CEX)
        write(o / "question" / "Q1.md", Q1)
        write(o / "assumption" / "GA-2T.md", GA)
        write(o / "direction" / "DIR-1.md", DIR)
        write(self.root / "audits" / "E1" / "2026-09-23_E1-x.md", VERDICT)
        write(self.root / "audits" / "lab-x" / "2026-09-28-A.md", REVIEW_RUN)
        write(self.root / "audits" / "_unparsed" / "2026-09-28-run.md", "no frontmatter\n")
        write(self.root / "computation" / "runs" / "E1.md", "---\nid: E1\n---\nrun\n")

    def test_loads_every_kind_folder_and_the_audits(self):
        kb = s1kb.load_kb(self.root)
        self.assertEqual(kb.layout, "objects")
        self.assertEqual({e.id: (e.etype, e.folder) for e in kb.entities.values()
                          if e.etype not in s1kb.LEDGER_TYPES},
                         {"CEX-1": ("claim", "claim"), "Q1": ("claim", "question"),
                          "GA-2T": ("assumption", "assumption"),
                          "DIR-1": ("direction", "direction")})
        self.assertIn("2026-09-23_E1-x", kb.entities)      # the ledger verdict
        self.assertNotIn("2026-09-28-A", kb.entities)      # a landed review run: reviews.py's
        self.assertNotIn("2026-09-28-run", kb.entities)    # _unparsed
        errors, warnings = s1kb.run_check(kb)
        self.assertEqual((errors, warnings), ([], []))

    def test_a_direction_may_name_an_approach_and_the_approach_folder_is_ignored(self):
        write(self.root / "objects" / "direction" / "DIR-1.md",
              DIR.replace("lifecycle: active\n", "lifecycle: active\napproach: AP-1\n", 1))
        write(self.root / "objects" / "approach" / "AP-1.md",
              "---\nid: AP-1\nkind: approach\ntitle: a\nlifecycle: active\n---\nx\n")
        kb = s1kb.load_kb(self.root)
        self.assertNotIn("AP-1", kb.entities)
        self.assertEqual(s1kb.run_check(kb), ([], []))

    def test_a_record_in_the_wrong_folder_is_an_error(self):
        shutil.move(str(self.root / "objects" / "question" / "Q1.md"),
                    str(self.root / "objects" / "claim" / "Q1.md"))
        kb = s1kb.load_kb(self.root)
        errors, _ = s1kb.run_check(kb)
        self.assertEqual(errors, ["objects/claim/Q1.md: kind 'question' belongs in "
                                  "objects/question/, not objects/claim/"])

    def test_new_writes_into_the_folder_of_the_kind(self):
        for argv, want in ((["new", "GEO"], "objects/claim/GEO-1.md"),
                           (["new", "OPEN", "--kind", "open"], "objects/question/OPEN-1.md"),
                           (["new", "DEF", "--kind", "def"], "objects/definition/DEF-1.md"),
                           (["new", "PA"], "objects/assumption/PA-1.md")):
            rc, out = run_kb(self.root, *argv)
            self.assertEqual((rc, out.strip()), (0, want))
        rc, out = run_kb(self.root, "new", "DIR")
        self.assertEqual(rc, 1)
        self.assertIn("notebook.py new direction", out)
        rc, out = run_kb(self.root, "check")
        self.assertEqual(rc, 0, out)

    def test_set_status_takes_a_verdict_under_audits(self):
        rc, out = run_kb(self.root, "set-status", "Q1", "conjectured",
                         "--verdict", "audits/E1/2026-09-23_E1-x.md")
        self.assertEqual(rc, 1, out)                       # the file is not about Q1
        self.assertIn("does not name Q1", out)
        write(self.root / "audits" / "E1" / "2026-09-24_E1-q.md",
              VERDICT.replace("subjects: [E1]", "subjects: [E1, Q1]").replace("E1-x", "E1-q"))
        rc, out = run_kb(self.root, "set-status", "Q1", "conjectured",
                         "--verdict", "audits/E1/2026-09-24_E1-q.md")
        self.assertEqual(rc, 0, out)
        text = (self.root / "objects" / "question" / "Q1.md").read_text(encoding="utf-8")
        self.assertIn("status: conjectured", text)
        self.assertIn("verdict | audits/E1/2026-09-24_E1-q.md | cleared", text)

    def test_set_status_on_landed_review_runs(self):
        run = ("---\nsubject: s1:Q1\nrun: {r}\nrun_id: {r}1\nverdict: {v}\n"
               "landed_by: researcher/land_review\n---\nreport\n")
        write(self.root / "audits" / "q1" / "2026-09-28-A.md", run.format(r="A", v="SOUND"))
        rc, out = run_kb(self.root, "set-status", "Q1", "supported",
                         "--verdict", "audits/q1/2026-09-28-A.md")
        self.assertEqual(rc, 1, out)                       # one run is not a pair
        self.assertIn("two landed runs", out)
        write(self.root / "audits" / "q1" / "2026-09-28-B.md", run.format(r="B", v="SOUND"))
        rc, out = run_kb(self.root, "set-status", "Q1", "supported",
                         "--verdict", "audits/q1/2026-09-28-A.md")
        self.assertEqual(rc, 0, out)
        rc, out = run_kb(self.root, "set-status", "Q1", "open", "--verdict",
                         "audits/lab-x/nope.md")
        self.assertEqual(rc, 1)
        self.assertIn("computation/verdicts/ or audits/", out)

    def test_build_writes_the_notebook_views(self):
        (self.root / "papers").mkdir()
        rc, out = run_kb(self.root, "build")
        self.assertEqual(rc, 0, out)
        v = self.root / "views"
        self.assertFalse((self.root / "assumptions").exists())
        for name in ("assumptions.md", "INDEX.md", "directions.md", "graph.md", "rests-on.md"):
            self.assertTrue((v / name).read_text(encoding="utf-8").startswith(s1kb.GENERATED),
                            name)
        d = (v / "directions.md").read_text(encoding="utf-8")
        self.assertIn("| [Q1](../objects/question/Q1.md) | open | the question |", d)
        self.assertIn("| GEO-99 | (no object here) | |", d)
        self.assertNotIn("NOPE-1", d)
        self.assertIn("[CEX-1](../objects/claim/CEX-1.md)", (v / "rests-on.md")
                      .read_text(encoding="utf-8"))
        g = (v / "graph.md").read_text(encoding="utf-8")
        self.assertIn("2 objects, 1 edges.", g)
        a = (v / "assumptions.md").read_text(encoding="utf-8")
        self.assertIn("[GA-2T](../objects/assumption/GA-2T.md)", a)
        ledger = (self.root / "computation" / "verdicts.md").read_text(encoding="utf-8")
        self.assertIn("`audits/<subject>/`", ledger)
        self.assertIn("[2026-09-23_E1-x](../audits/E1/2026-09-23_E1-x.md)", ledger)


class TestLegacyLayoutUnchanged(Homes):
    def test_audits_are_not_verdict_files_without_objects(self):
        write(self.s1 / "audits" / "E1" / "v.md", VERDICT)
        self.assertIsNone(s1kb._verdict_relpath(self.s1, "audits/E1/v.md"))
        self.assertEqual(s1kb.load_kb(self.s1).layout, "legacy")


class TestForeignRefsPreferTheWorktree(Homes):
    suffix = "-wt"

    def test_repo_path_ref_resolves_in_the_sibling_worktree_first(self):
        write(self.s1 / "audits" / "E1" / "v.md", VERDICT)
        p = fsl.resolve_ref("Slope1illuminationResearch:audits/E1/v.md", self.lab)
        self.assertEqual(p, self.s1 / "audits" / "E1" / "v.md")
        self.assertTrue(p.exists())


CEX2 = """---
id: CEX-2
kind: claim
form: prop
title: t2
status: sketch
lifecycle: active
summary: s
evidence: []
history:
  - 2026-09-24 | sketch | created
---
## Statement
It fails too.
"""

OLD_VERDICT = """---
id: 2026-09-23_N8
date: 2026-09-23
kind: claim
subjects: [CEX-2]
clears: [CEX-2]
decision: "Proved / Proved"
---
Run A: CONFIRMED
Run B: CONFIRMED
"""


class TestExpertReviewRefs(Homes):
    """Phase 7 (P-0004 D9, P-0005 D8): s1 set-status anchored on a review in the Expert's
    library, written as the protocol ref ``file:expert@<name>/reviews/s1/<id>/<file>``."""

    def setUp(self):
        super().setUp()
        import json
        from registry.core import workspace as ws_mod
        ws = json.loads(self.ws.read_text(encoding="utf-8"))
        self.papers = self.tmp / "papers"
        ws["instances"]["expert@t"] = {"role": "expert", "home": str(self.papers),
                                       "domains": ["d"]}
        write(self.ws, json.dumps(ws))
        ws_mod._ws_cache.clear()
        # the notebook layout: the legacy fixture's records and its ledger verdict go
        shutil.rmtree(str(self.s1 / "claims"))
        shutil.rmtree(str(self.s1 / "assumptions"))
        (self.s1 / "computation" / "verdicts" / "2026-09-24_G8.md").unlink()
        write(self.s1 / "objects" / "claim" / "CEX-2.md", CEX2)
        self.review = self.papers / "reviews" / "s1" / "CEX-2" / "2026-09-23_N8.md"
        write(self.review, OLD_VERDICT)
        self.ref = "file:expert@t/reviews/s1/CEX-2/2026-09-23_N8.md"

    def test_the_ref_resolves_in_the_library(self):
        self.assertEqual(s1kb.review_ref_path(self.s1, self.ref), self.review)
        self.assertEqual(fsl.resolve_ref(self.ref, self.s1), self.review)
        self.assertEqual(s1kb._verdict_relpath(self.s1, self.ref), self.ref)
        # an absolute path into the library's reviews/ is recorded as the ref
        self.assertEqual(s1kb._verdict_relpath(self.s1, str(self.review)), self.ref)
        self.assertIsNone(s1kb._verdict_relpath(self.s1, self.ref.replace("N8", "N9")))
        self.assertIsNone(s1kb.review_ref_path(self.s1, "computation/verdicts/x.md"))

    def test_set_status_takes_an_expert_review_ref(self):
        rc, out = run_kb(self.s1, "set-status", "CEX-2", "proved", "--verdict", self.ref)
        self.assertEqual(rc, 0, out)
        text = (self.s1 / "objects" / "claim" / "CEX-2.md").read_text(encoding="utf-8")
        self.assertIn("status: proved", text)
        self.assertIn("verdict | %s | Proved / Proved | 2026-09-23_N8 | cleared_by" % self.ref,
                      text)
        rc, out = run_kb(self.s1, "check")
        self.assertEqual(rc, 0, out)

    def test_the_review_must_clear_the_claim(self):
        write(self.review, OLD_VERDICT.replace("clears: [CEX-2]", "clears: []"))
        rc, out = run_kb(self.s1, "set-status", "CEX-2", "proved", "--verdict", self.ref)
        self.assertEqual(rc, 1, out)
        self.assertIn("does not clear CEX-2", out)

    def test_landed_review_runs_in_the_library_count_as_a_pair(self):
        run = ("---\nsubject: s1:CEX-2\nrun: {r}\nrun_id: rv-{r}\nverdict: CONFIRMED\n"
               "landed_by: expert/land_verdict\n---\nreport\n")
        d = self.papers / "reviews" / "s1" / "CEX-2" / "p1"
        write(d / "A.md", run.format(r="A"))
        ref_a = "file:expert@t/reviews/s1/CEX-2/p1/A.md"
        rc, out = run_kb(self.s1, "set-status", "CEX-2", "proved", "--verdict", ref_a)
        self.assertEqual(rc, 1, out)
        self.assertIn("two landed runs", out)
        write(d / "B.md", run.format(r="B"))
        rc, out = run_kb(self.s1, "set-status", "CEX-2", "proved", "--verdict", ref_a)
        self.assertEqual(rc, 0, out)

    def test_check_reports_a_missing_review(self):
        text = CEX2.replace("evidence: []", "evidence:\n  - verdict | %s | x | y | z"
                            % self.ref.replace("N8", "N9"))
        write(self.s1 / "objects" / "claim" / "CEX-2.md", text)
        errors, _ = s1kb.run_check(s1kb.load_kb(self.s1))
        self.assertTrue(any("evidence ref 'file:expert@t/reviews/s1/CEX-2/2026-09-23_N9.md' "
                            "is not a file" in e for e in errors), errors)

    def test_a_cleared_by_ref_keeps_its_ledger_edge(self):
        write(self.s1 / "computation" / "verdicts" / "2026-09-23_N8.md", OLD_VERDICT)
        text = CEX2.replace("evidence: []", "evidence:\n  - verdict | %s | d | 2026-09-23_N8"
                            " | cleared_by" % self.ref)
        write(self.s1 / "objects" / "claim" / "CEX-2.md", text)
        kb = s1kb.load_kb(self.s1)
        self.assertEqual(kb.entities["CEX-2"].meta["cleared_by"], [self.ref])
        self.assertIn(("CEX-2", "2026-09-23_N8", "cleared_by"), list(s1kb.iter_edges(kb)))


if __name__ == "__main__":
    unittest.main()
