"""R5: the academy object schema (core/schema.py) and both profiles reading and mutating
schema-v2 records, on temp homes laid out like the migration worktrees (their v2 records
are ``_v2_homes.V2_FILES``, what the one-time R5 migration made of them)."""
import io
import unittest
from contextlib import redirect_stdout, redirect_stderr

from _util import Homes, write
from _v2_homes import V2_FILES

from registry.core import projection, schema
from registry.profiles import fsl, s1kb

def quiet(fn, *a, **k):
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        return fn(*a, **k)


class TestSchemaRules(unittest.TestCase):
    def rec(self, **kw):
        base = {"id": "x", "kind": "claim", "title": "t", "status": "open",
                "lifecycle": "active", "evidence": [],
                "history": ["2026-09-28 | open | created"]}
        base.update(kw)
        return {k: v for k, v in base.items() if v is not None}

    def errors(self, f, **kw):
        return [m for lv, m in schema.check_record(f, **kw) if lv == "error"]

    def test_a_good_record_is_clean(self):
        self.assertEqual(self.errors(self.rec()), [])
        self.assertTrue(schema.is_v2(self.rec()))
        self.assertFalse(schema.is_v2({"id": "x", "status": "open"}))

    def test_generic_rules(self):
        cases = [(self.rec(lifecycle=None), "missing field 'lifecycle'"),
                 (self.rec(open=["a"]), "unknown field(s): open"),
                 (self.rec(kind="definition"), "a definition carries no status"),
                 (self.rec(status="proved", modulo=["X"],
                           history=["2026-09-28 | proved | x"]), "is proved-modulo"),
                 (self.rec(status="proved-modulo",
                           history=["2026-09-28 | proved-modulo | x"]), "needs `modulo`"),
                 (self.rec(status="Proved"), "is not one of"),
                 (self.rec(history=["2026-09-28 | sketch | x"]), "latest history status"),
                 (self.rec(history=["2026-09-20 | open | a", "2026-09-28 | | b"]),
                  "not newest first"),
                 (self.rec(evidence=["hand | x | - | note"]), "is not `type | ref"),
                 (self.rec(status=None, history=["2026-09-28 | | x"]), "needs a status")]
        for f, want in cases:
            with self.subTest(want):
                self.assertTrue(any(want in m for m in self.errors(f)), self.errors(f))

    def test_a_remark_and_a_profile_status_kind(self):
        self.assertEqual(self.errors(self.rec(status=None, form="remark",
                                              history=["2026-09-28 | | x"])), [])
        self.assertEqual(self.errors(self.rec(kind="definition"),
                                     status_kinds=schema.KINDS), [])

    def test_lifecycle_projects_to_na(self):
        self.assertEqual(schema.project(self.rec(status="proved")), projection.TRUE)
        self.assertEqual(schema.project(self.rec(status="proved", lifecycle="dropped")),
                         projection.NA)
        self.assertEqual(schema.state(self.rec(lifecycle="superseded")), "superseded")


class Migrated(Homes):
    """The temp homes with their records in schema v2 (``V2_FILES``)."""
    suffix = "-academy"

    def setUp(self):
        super().setUp()
        homes = {"FlatSurfLab": self.lab, "Slope1illuminationResearch": self.s1}
        for (home, rel), text in V2_FILES.items():
            write(homes[home] / rel, text)
        from registry.core import federation
        federation.CACHE.clear()


class TestV2Homes(Migrated):
    def test_every_check_is_clean(self):
        claims, perrs = fsl.load(fsl.registry_root(self.lab))
        errs, warns = fsl.check(claims, repo=self.lab)
        self.assertEqual((perrs, errs), ([], []))
        self.assertTrue(all(c.v2 for c in claims))
        kb = s1kb.load_kb(self.s1)
        s1kb.run_check(kb)
        self.assertEqual(kb.errors, [])
        self.assertTrue(all(e.v2 is not None for e in kb.entities.values()
                            if e.etype in ("claim", "assumption")))

    def test_statuses_lifecycles_and_modulo(self):
        c = {c.id: c for c in fsl.load(fsl.registry_root(self.lab))[0]}
        old = c["lab:old"]
        self.assertEqual((old.status, old.fields["lifecycle"], old.state),
                         ("supported", "dropped", "dropped"))
        kb = s1kb.load_kb(self.s1)
        v = lambda i: kb.entities[i].v2  # noqa: E731
        self.assertEqual((v("CRIT-1")["status"], v("CRIT-1")["modulo"]),
                         ("proved-modulo", ["OPEN-2"]))
        self.assertEqual(schema.evidence_cells(v("CEX-1")["evidence"][0])[:2],
                         ("verdict", "computation/verdicts/2026-09-24_G8.md"))


class TestV2Mutations(Migrated):
    def test_fsl_lifecycle_move_and_evidence_row(self):
        p = self.lab / "claims" / "lab" / "foo.md"
        fsl.set_status(self.lab, "lab:foo", "dropped",
                       {"basis": "human", "quote": "drop it"}, date="2026-09-29", human=True)
        c = fsl.parse_text(p.read_text(encoding="utf-8"), p)
        self.assertEqual((c.status, c.fields["lifecycle"]), ("supported", "dropped"))
        self.assertTrue(c.history[0].startswith("2026-09-29 | dropped |"))
        fsl.attach_evidence(self.lab, "lab:foo", "hand | chat | Roey | a note")
        c = fsl.parse_text(p.read_text(encoding="utf-8"), p)
        self.assertIn("hand | chat | Roey | - | a note", c.evidence)
        claims, _ = fsl.load(fsl.registry_root(self.lab))
        self.assertEqual(fsl.check(claims, repo=self.lab)[0], [])

    def test_fsl_supersession_writes_the_one_way_link(self):
        fsl.new_claim(self.lab, "lab:bar", "the restated claim")
        p, q = (self.lab / "claims" / "lab" / n for n in ("foo.md", "bar.md"))
        before = p.read_bytes(), q.read_bytes()
        with self.assertRaises(fsl.Refused):              # no replacing record named
            fsl.set_status(self.lab, "lab:foo", "superseded",
                           {"basis": "proof", "note": "restated"})
        self.assertEqual((p.read_bytes(), q.read_bytes()), before)
        fsl.set_status(self.lab, "lab:foo", "superseded",
                       {"basis": "proof", "note": "restated", "superseded_by": "lab:bar"})
        foo = fsl.parse_text(p.read_text(encoding="utf-8"), p)
        bar = fsl.parse_text(q.read_text(encoding="utf-8"), q)
        self.assertEqual(foo.fields["lifecycle"], "superseded")
        self.assertEqual(bar.fields["supersedes"], ["lab:foo"])
        claims, _ = fsl.load(fsl.registry_root(self.lab))
        self.assertEqual(fsl.check(claims, repo=self.lab)[0], [])

    def test_fsl_new_writes_v2(self):
        p = fsl.new_claim(self.lab, "lab:bar", "a new one")
        c = fsl.parse_text(p.read_text(encoding="utf-8"), p)
        self.assertTrue(c.v2)
        self.assertEqual((c.fields["kind"], c.status), ("claim", "open"))
        claims, _ = fsl.load(fsl.registry_root(self.lab))
        self.assertEqual(fsl.check(claims, repo=self.lab)[0], [])

    def s1_verdict(self, name, clears, runs, subjects=None):
        body = "".join("Run %s: %s — a reason\n" % (r, w) for r, w in zip("AB", runs))
        write(self.s1 / "computation" / "verdicts" / name,
              "---\nid: %s\nsubjects: [%s]\nclears: [%s]\ndecision: cleared\n---\n%s"
              % (name[:-3], ", ".join(subjects if subjects is not None else clears),
                 ", ".join(clears), body))
        return "computation/verdicts/" + name

    def s1_set(self, *argv):
        return quiet(s1kb.main, ["set-status", *argv, "--root", str(self.s1)])

    def test_s1_set_status_needs_a_verdict_file_on_the_claim(self):
        p = self.s1 / "claims" / "OPEN-2.md"
        before = p.read_bytes()
        refusals = (
            # the review finding: a file about nothing, whose runs say GAP
            ("refuted", self.s1_verdict("2026-09-28_a.md", [], ["GAP", "GAP"])),
            # it names the claim but clears only another one
            ("refuted", "computation/verdicts/2026-09-24_G8.md"),
            ("refuted", self.s1_verdict("2026-09-28_b.md", ["OPEN-2"], ["DISPROVED"])),
            ("refuted", self.s1_verdict("2026-09-28_c.md", ["OPEN-2"],
                                        ["DISPROVED", "GAP"])),
            ("proved", self.s1_verdict("2026-09-28_d.md", ["OPEN-2"],
                                       ["REFUTATION CONFIRMED", "DISPROVED"])),
            ("open", self.s1_verdict("2026-09-28_e.md", [], [], subjects=["CRIT-1"])),
        )
        for label, vfile in refusals:
            with self.subTest(vfile=vfile):
                self.assertEqual(self.s1_set("OPEN-2", label, "--verdict", vfile), 1)
                self.assertEqual(p.read_bytes(), before)
        # the human's word stands in for the runs, not for the file's subject
        self.assertEqual(self.s1_set("OPEN-2", "refuted", "--verdict",
                                     self.s1_verdict("2026-09-28_f.md", ["OPEN-2"], []),
                                     "--human", "OPEN-2 is false"), 0)
        self.assertIn('the human\'s word "OPEN-2 is false"',
                      s1kb.load_kb(self.s1).entities["OPEN-2"].v2["history"][0])

    def test_s1_set_status_puts_the_file_back_when_the_build_fails(self):
        p = self.s1 / "claims" / "OPEN-2.md"
        before = p.read_bytes()
        write(self.s1 / "claims" / "BAD-1.md", "---\nid: BAD-1\nstatus: Proven\n---\n")
        vfile = self.s1_verdict("2026-09-28_g.md", ["OPEN-2"], ["DISPROVED", "DISPROVED"])
        self.assertNotEqual(self.s1_set("OPEN-2", "refuted", "--verdict", vfile), 0)
        self.assertEqual(p.read_bytes(), before)

    def test_s1_show_prints_the_statement_of_a_v2_record(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = s1kb.main(["show", "OPEN-2", "--root", str(self.s1)])
        self.assertEqual(rc, 0)
        self.assertIn("lifecycle: active", out.getvalue())
        self.assertTrue(out.getvalue().rstrip().endswith("Is it?"), out.getvalue())

    def test_s1_lifecycle_move_needs_only_a_note(self):
        self.assertEqual(self.s1_set("OPEN-2", "dropped"), 1)
        self.assertEqual(self.s1_set("OPEN-2", "dropped", "--note", "out of scope"), 0)
        e = s1kb.load_kb(self.s1).entities["OPEN-2"]
        self.assertEqual(e.v2["lifecycle"], "dropped")
        self.assertIn("out of scope", e.v2["history"][0])
        self.assertEqual(self.s1_set("OPEN-2", "proved", "--note", "x"), 1)

    def test_s1_supersession_writes_the_one_way_link(self):
        self.assertEqual(self.s1_set("OPEN-2", "superseded", "--note", "restated"), 1)
        self.assertEqual(self.s1_set("OPEN-2", "superseded", "--note", "restated",
                                     "--superseded-by", "OBS-1"), 0)
        kb = s1kb.load_kb(self.s1)
        self.assertEqual(kb.entities["OPEN-2"].v2["lifecycle"], "superseded")
        self.assertEqual(kb.entities["OBS-1"].v2["supersedes"], ["OPEN-2"])
        s1kb.run_check(kb)
        self.assertEqual(kb.errors, [])

    def test_s1_set_status_attach_and_new(self):
        vfile = self.s1_verdict("2026-09-28_OPEN-2.md", ["OPEN-2"],
                                ["REFUTATION CONFIRMED", "DISPROVED"])
        rc = quiet(s1kb.main, ["set-status", "OPEN-2", "refuted", "--verdict", vfile,
                               "--root", str(self.s1)])
        self.assertEqual(rc, 0)
        e = s1kb.load_kb(self.s1).entities["OPEN-2"]
        self.assertEqual(e.v2["status"], "refuted")
        self.assertEqual(e.meta["cleared_by"], [vfile])
        self.assertTrue(e.v2["history"][0].split(" | ")[1] == "refuted")
        s1kb.attach_row(self.s1, "OPEN-2", "note | somewhere | - | - | a remark")
        self.assertIn("note | somewhere | - | - | a remark",
                      s1kb.load_kb(self.s1).entities["OPEN-2"].v2["evidence"])
        rc = quiet(s1kb.main, ["new", "GEO", "--title", "fresh", "--root", str(self.s1)])
        self.assertEqual(rc, 0)
        kb = s1kb.load_kb(self.s1)
        new = kb.entities["GEO-1"]
        self.assertIsNotNone(new.v2)
        self.assertEqual((new.v2["kind"], new.v2["form"], new.v2["status"]),
                         ("claim", "draft", "open"))
        s1kb.run_check(kb)
        self.assertEqual([m for m in kb.errors if "GEO-1" in m], [])

    def test_s1_store_classes(self):
        from registry.core import federation
        st = federation.store("s1", self.s1)
        self.assertEqual(st.records["CRIT-1"].cls, projection.TRUE_MODULO)
        self.assertEqual(st.records["CEX-1"].cls, projection.FALSE)
        self.assertEqual(st.records["GA-2T′"].cls, projection.NA)


if __name__ == "__main__":
    unittest.main()
