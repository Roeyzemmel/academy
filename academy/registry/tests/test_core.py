"""The core: the dialect, the projection, homes and federation, the graph, grounds."""
import unittest
from pathlib import Path

from _util import Homes, write, LAB_GOOD  # noqa: F401

from registry.core import fm, projection, workspace, federation, graph, grounds
from registry.profiles import fsl


class TestDialect(unittest.TestCase):
    TRICKY = ["plain", "a: b", "ends:", " lead", "trail ", "#hash", "a #b", "a, b", "[x]",
              "x [y] {z}", "'q'", '"dq"', "\\cite{Mo06}", "{\\cite[Thm 2]{X}} (lab)",
              "|abs|", "- dash", "tab\there", "new\nline", "it's", "π′ unicode", "a|b|c",
              "-", "?", "@x", "`code`", "%", "50% off", "x:y", "http://a.b/c#d"]

    def test_round_trip_every_style(self):
        for fmt in (fm.format_scalar, fm.format_scalar_single):
            for s in self.TRICKY:
                with self.subTest(fmt=fmt.__name__, s=s):
                    d = {"k": s, "l": [s, "x"]}
                    text = fm.serialize_frontmatter(d, (), ("l",), fmt)
                    self.assertEqual(fm.parse_frontmatter(text.split("\n")), d)
                    inline = fm.serialize_frontmatter(d, (), (), fmt)
                    self.assertEqual(fm.parse_frontmatter(inline.split("\n")), d)

    def test_single_style_keeps_latex_readable(self):
        self.assertEqual(fm.format_scalar_single("{\\cite{A}} x"), "'{\\cite{A}} x'")
        self.assertEqual(fm.format_scalar_single("a, b [c]"), "a, b [c]")
        self.assertEqual(fm.format_scalar("a, b [c]"), '"a, b [c]"')   # kb.py's style

    def test_empty_block_is_an_error_unless_the_profile_opts_in(self):
        lines = ["a: x", "evidence:", "b: y"]
        with self.assertRaises(fm.FrontmatterError) as cm:
            fm.parse_frontmatter(lines, "f.md", 2)
        self.assertEqual(cm.exception.lineno, 3)
        d = fm.parse_frontmatter(lines, "f.md", 2, empty=lambda k: [])
        self.assertEqual(d["evidence"], [])

    def test_fsl_parse_errors_keep_claims_py_words(self):
        with self.assertRaises(ValueError) as cm:
            fsl.parse_strict("id: x\n")
        self.assertIn("no frontmatter", str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            fsl.parse_strict("---\nid: lab:x\ntitle: a: b\n---\n")
        self.assertIn("line 3:", str(cm.exception))

    def test_legacy_fallback_is_reported(self):
        c = fsl.parse_text("---\nid: lab:x\ntitle: a: b\n---\n")
        self.assertEqual(c.title, "a: b")
        self.assertIn("line 3", c.dialect_error)
        with self.assertRaises(ValueError):
            fsl.parse_text("---\nid: lab:x\ntitle: a: b\n---\n", fallback=False)


class TestProjection(unittest.TestCase):
    def test_classes(self):
        P = projection
        self.assertEqual(P.project("supported", P.FSL), P.UNSETTLED)   # never true
        self.assertEqual(P.project("refuted-as-stated", P.FSL), P.FALSE)
        self.assertEqual(P.project("Disproved", P.S1), P.FALSE)
        self.assertEqual(P.project("Reduced", P.S1), P.TRUE_MODULO)
        self.assertEqual(P.project("Partial", P.S1), P.UNSETTLED)
        self.assertEqual(P.project("", P.S1), P.NA)
        self.assertEqual(P.project("Proven", P.S1), P.UNSETTLED)       # unknown: not true


class TestHomes(Homes):
    def test_namespaces_come_from_the_workspace(self):
        self.assertEqual(sorted(workspace.namespaces()), ["lab", "paper", "s1"])
        self.assertEqual(workspace.repo_ns(self.lab), "lab")
        self.assertEqual(workspace.home_of("paper", self.lab), self.bi)
        self.assertEqual(workspace.engine_profile("s1"), "s1-kb")
        self.assertEqual(workspace.engine_profile("paper"), "fsl-claims")

    def test_federation_loads_s1_through_its_profile(self):
        R = lambda q: federation.resolve(q, self.lab)[:1] + (  # noqa: E731
            federation.resolve(q, self.lab)[2],)
        self.assertEqual(R("s1:CEX-1"), ("ok", "s1:CEX-1"))
        self.assertEqual(R("s1:N8"), ("alias", "s1:CEX-1"))
        self.assertEqual(R("s1:GA-2T′"), ("ok", "s1:GA-2T′"))        # unicode id
        self.assertEqual(R("s1:2026-09-24_G8"), ("ok", "s1:2026-09-24_G8"))   # a verdict
        self.assertEqual(R("s1:Q99")[0], "missing")
        st = federation.store_from("s1", self.lab)
        self.assertEqual(st.records["CEX-1"].cls, projection.FALSE)

    def test_fsl_check_uses_the_projection_across_namespaces(self):
        write(self.lab / "claims" / "lab" / "foo.md",
              LAB_GOOD.replace("bears_on:", "depends_on:\n  - s1:CEX-1\n  - s1:GA-2T′\nbears_on:"))
        cs, perrs = fsl.load(fsl.registry_root(self.lab))
        errs, warns = fsl.check(cs, repo=self.lab)
        self.assertEqual(perrs + errs, [])
        self.assertTrue(any("depends on `s1:CEX-1`, which is refuted" in w for w in warns), warns)
        write(self.lab / "claims" / "lab" / "foo.md",
              LAB_GOOD.replace("bears_on:", "depends_on:\n  - s1:(2T′)\nbears_on:"))
        federation.CACHE.clear()
        cs, _ = fsl.load(fsl.registry_root(self.lab))
        errs, _ = fsl.check(cs, repo=self.lab)
        self.assertTrue(any("the id is `s1:GA-2T′`" in e for e in errs), errs)

    def test_graph_crosses_namespaces(self):
        write(self.lab / "claims" / "lab" / "foo.md",
              LAB_GOOD.replace("bears_on:", "depends_on:\n  - s1:N8\nbears_on:"))
        fwd = graph.walk("lab:foo", self.lab)
        self.assertEqual(sorted((e["rel"], e["to"]) for e in fwd),
                         [("bears_on", "paper:prop:foo"), ("depends_on", "s1:CEX-1")])
        back = graph.walk("s1:CEX-1", self.s1, reverse=True, transitive=True)
        self.assertEqual([(e["from"], e["class"]) for e in back], [("lab:foo", "unsettled")])

    def test_paper_statement_hash_is_the_tex_environment(self):
        write(self.bi / "claims" / "paper" / "prop__foo.md",
              "---\nid: paper:prop:foo\ntitle: t\nstatus: open\nevidence: []\n"
              "history:\n  - 2026-09-25 | open | seeded\n---\n")
        st = federation.store("paper", self.bi)
        h = st.statement_hash("prop:foo")
        write(self.bi / "sections" / "a.tex",
              "\\begin{prop}\\label{prop:foo}Every  $x$\nis fine.\\end{prop}\n\\label{lem:bar}\n")
        federation.CACHE.clear()
        self.assertEqual(federation.store("paper", self.bi).statement_hash("prop:foo"), h)
        write(self.bi / "sections" / "a.tex",
              "\\begin{prop}\\label{prop:foo}Every $y$ is fine.\\end{prop}\n")
        federation.CACHE.clear()
        self.assertNotEqual(federation.store("paper", self.bi).statement_hash("prop:foo"), h)


class TestWorktreeSiblings(Homes):
    """Homes named LabHome-wt etc. (worktrees) find each other, not the plain names."""
    suffix = "-wt"

    def test_suffix_siblings_first(self):
        write(self.tmp / "PaperHome" / "sections" / "a.tex", "\\label{other}\n")
        self.assertEqual(workspace.repo_ns(self.lab), "lab")
        self.assertEqual(workspace.home_of("paper", self.lab), self.bi)
        self.assertEqual(workspace.home_of("s1", self.bi), self.s1)


class TestGrounds(unittest.TestCase):
    def test_roles_and_human_quote(self):
        rows = [{"verdict": "CONFIRMED", "run_id": "a", "grader_role": "rigor-reviewer",
                 "statement_hash": "H", "ref": "r/a.md"},
                {"verdict": "CONFIRMED", "run_id": "b", "grader_role": "expert:rigor-reviewer",
                 "statement_hash": "H", "ref": "r/b.md"}]
        ok, why = grounds.check_grounds("proved", {"basis": "proof", "verdicts": rows,
                                                   "producer_role": "prover"}, "H")
        self.assertTrue(ok, why)
        ok, why = grounds.check_grounds("proved", {"basis": "proof", "verdicts": rows,
                                                   "producer_role": "rigor-reviewer"}, "H")
        self.assertFalse(ok)
        # the graders must be the basis' reviewers, and the producer no reviewer at all
        for grader, producer in (("experimenter", "claim-keeper"), ("prover", "author"),
                                 ("experiment-reviewer", "prover")):
            bad = [dict(r, grader_role=grader) for r in rows]
            ok, why = grounds.check_grounds("proved", {"basis": "proof", "verdicts": bad,
                                                       "producer_role": producer}, "H")
            self.assertFalse(ok, (grader, producer))
        ok, why = grounds.check_grounds("proved", {"basis": "proof", "verdicts": rows,
                                                   "producer_role": "experiment-reviewer"}, "H")
        self.assertIn("reviewer role", " ".join(why))
        self.assertTrue(grounds.check_grounds("proved", {"basis": "human", "quote": "yes"},
                                              human=True)[0])
        self.assertFalse(grounds.check_grounds("proved", {"basis": "human", "quote": "yes"})[0])
        self.assertTrue(grounds.check_grounds("proved", {"basis": "human", "quote": "yes",
                                                         "where": "packet P-0004 D3"})[0])
        self.assertFalse(grounds.check_grounds("proved", {"basis": "human"}, human=True)[0])

    def test_lifecycle_moves(self):
        self.assertFalse(grounds.check_grounds("dropped", {"basis": "proof"})[0])
        self.assertTrue(grounds.check_grounds("dropped", {"basis": "proof", "note": "moot"})[0])
        self.assertFalse(grounds.check_grounds("superseded", {"basis": "proof",
                                                              "note": "restated"})[0])
        self.assertTrue(grounds.check_grounds("superseded", {"basis": "proof", "note": "x",
                                                             "superseded_by": "lab:new"})[0])

    def test_verdict_refs(self):
        import shutil
        import tempfile
        d = Path(tempfile.mkdtemp())
        try:
            write(d / "a.md", "---\nsubject: paper:lem:x\nrun_id: a\nverdict: CONFIRMED\n"
                              "statement_hash: H\nagent: expert:rigor-reviewer\n---\n")
            write(d / "b.md", "---\nsubject: lem:x\nrun_id: b\nverdict: CONFIRMED\n---\n")
            rows = [{"verdict": "CONFIRMED", "run_id": "a", "ref": "a.md"},
                    {"verdict": "confirmed", "run_id": "b", "ref": "b.md"}]
            g = {"basis": "proof", "verdicts": rows, "statement_hash": "H"}
            res = lambda ref: d / ref  # noqa: E731
            self.assertEqual(grounds.check_verdict_refs(g, res, "paper:lem:x"), [])
            self.assertTrue(grounds.check_verdict_refs(g, res, "paper:lem:y"))
            self.assertTrue(grounds.check_verdict_refs(dict(g, statement_hash="H2"), res))
            bad = dict(g, verdicts=[dict(rows[0], run_id="z"), rows[1]])
            self.assertIn("is run a", " ".join(grounds.check_verdict_refs(bad, res)))
            self.assertIn("written by rigor-reviewer", " ".join(grounds.check_verdict_refs(
                dict(g, basis="computation"), res)))
            self.assertIn("not found", " ".join(grounds.check_verdict_refs(
                dict(g, verdicts=[dict(rows[0], ref="none.md")]), res)))
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestRewordGrounds(unittest.TestCase):
    """T-0347 (Roey, 2026-10-12): a statement reworded after a CONFIRMED x2 pass is
    carried to proved by the base pass's two CONFIRMED verdicts on the old hash plus one
    informed reword run CONFIRMED on the new hash, linking the old one."""

    def grounds(self, **kw):
        rows = [{"verdict": "CONFIRMED", "run_id": "r", "grader_role": "expert",
                 "statement_hash": "NEW", "mode": "reword", "base_hash": "OLD",
                 "reword_scope": "equivalent", "ref": "p2/R.md"},
                {"verdict": "CONFIRMED", "run_id": "a", "grader_role": "expert",
                 "statement_hash": "OLD", "ref": "p1/A.md"},
                {"verdict": "CONFIRMED", "run_id": "b", "grader_role": "expert",
                 "statement_hash": "OLD", "ref": "p1/B.md"}]
        g = {"basis": "proof", "mode": "reword", "base_pass": "2026-10-01-T-0001",
             "base_hash": "OLD", "statement_hash": "NEW", "verdicts": rows,
             "producer_role": "author"}
        g.update(kw)
        return g

    def check(self, g, status="proved", h="NEW"):
        return grounds.check_grounds(status, g, h)

    def test_accepted_on_the_new_hash(self):
        ok, why = self.check(self.grounds())
        self.assertTrue(ok, why)
        self.assertTrue(self.check(self.grounds(), h=None)[0])
        for scope in ("weaker", "covered"):
            g = self.grounds()
            g["verdicts"][0]["reword_scope"] = scope
            self.assertTrue(self.check(g)[0], scope)
        ok, why = self.check(self.grounds(modulo=["paper:lem:a"]), "proved-modulo")
        self.assertTrue(ok, why)

    def test_the_claims_current_hash_must_be_the_reworded_one(self):
        for h in ("OLD", "OTHER"):
            ok, why = self.check(self.grounds(), h=h)
            self.assertFalse(ok, h)
            self.assertIn("current", " ".join(why))

    def test_the_mixed_hashes_without_mode_are_still_refused(self):
        g = self.grounds()
        del g["mode"]
        ok, why = self.check(g)
        self.assertFalse(ok)

    def test_a_reword_run_never_counts_as_a_blind_verdict(self):
        g = self.grounds()
        del g["mode"]
        g["verdicts"] = [g["verdicts"][0], dict(g["verdicts"][0], run_id="r2",
                                                 ref="p2/R2.md")]
        ok, why = self.check(g)
        self.assertFalse(ok)
        self.assertIn("reword", " ".join(why))

    def test_the_base_pass_needs_two_confirmed_on_base_hash(self):
        g = self.grounds()
        g["verdicts"] = g["verdicts"][:2]
        ok, why = self.check(g)
        self.assertFalse(ok)
        self.assertIn("two", " ".join(why))
        g = self.grounds()
        g["verdicts"][2]["statement_hash"] = "OTHER"
        ok, why = self.check(g)
        self.assertFalse(ok)
        self.assertIn("base_hash", " ".join(why))
        g = self.grounds()
        g["verdicts"][2]["verdict"] = "GAP"
        self.assertFalse(self.check(g)[0])

    def test_the_reword_row_links_the_base_hash(self):
        g = self.grounds()
        g["verdicts"][0]["base_hash"] = "OTHER"
        self.assertFalse(self.check(g)[0])
        g = self.grounds()
        del g["verdicts"][0]["base_hash"]
        self.assertFalse(self.check(g)[0])
        self.assertFalse(self.check(self.grounds(base_hash=""))[0])

    def test_exceeds_or_no_scope_is_refused(self):
        for scope in ("exceeds", "", None):
            g = self.grounds()
            g["verdicts"][0]["reword_scope"] = scope
            ok, why = self.check(g)
            self.assertFalse(ok, scope)
            self.assertIn("reword_scope", " ".join(why))

    def test_exactly_one_reword_row(self):
        g = self.grounds()
        g["verdicts"][1]["mode"] = "reword"
        self.assertFalse(self.check(g)[0])
        g = self.grounds()
        del g["verdicts"][0]["mode"]
        self.assertFalse(self.check(g)[0])

    def test_an_unchanged_statement_is_no_reword(self):
        g = self.grounds(base_hash="NEW")
        for r in g["verdicts"]:
            r["statement_hash"] = "NEW"
            r["base_hash"] = "NEW" if r.get("mode") else r.get("base_hash")
        ok, why = self.check(g)
        self.assertFalse(ok)
        self.assertIn("did not change", " ".join(why))

    def test_reword_carries_only_proved(self):
        g = self.grounds()
        for r in g["verdicts"]:
            r["verdict"] = "DISPROVED"
        self.assertFalse(self.check(g, "refuted")[0])

    def test_distinct_runs_and_roles_still_apply(self):
        g = self.grounds()
        g["verdicts"][0]["run_id"] = "a"
        self.assertFalse(self.check(g)[0])
        self.assertFalse(self.check(self.grounds(producer_role="rigor-reviewer"))[0])

    def test_verdict_refs_of_a_reword_record(self):
        import shutil
        import tempfile
        d = Path(tempfile.mkdtemp())
        try:
            base = ("---\nsubject: paper:lem:x\nrun_id: {r}\nverdict: CONFIRMED\n"
                    "statement_hash: OLD\nagent: expert:rigor-reviewer\n---\n")
            write(d / "p1" / "A.md", base.format(r="a"))
            write(d / "p1" / "B.md", base.format(r="b"))
            rw = ("---\nsubject: paper:lem:x\nrun_id: r\nverdict: CONFIRMED\n"
                  "statement_hash: NEW\nmode: reword\nbase_pass: 2026-10-01-T-0001\n"
                  "base_hash: OLD\nreword_scope: equivalent\n"
                  "agent: expert:rigor-reviewer\n---\n")
            write(d / "p2" / "R.md", rw)
            res = lambda ref: d / ref  # noqa: E731
            g = self.grounds()
            self.assertEqual(grounds.check_verdict_refs(g, res, "paper:lem:x"), [])
            # the record must itself be a reword record with the same base hash
            write(d / "p2" / "R.md", rw.replace("base_hash: OLD", "base_hash: ZZZ"))
            self.assertIn("base_hash", " ".join(grounds.check_verdict_refs(g, res)))
            write(d / "p2" / "R.md", rw.replace("mode: reword\n", ""))
            self.assertIn("reword", " ".join(grounds.check_verdict_refs(g, res)))
            # a reword record passed off as a blind verdict
            write(d / "p2" / "R.md", rw)
            g2 = self.grounds()
            del g2["verdicts"][0]["mode"]
            self.assertIn("reword", " ".join(grounds.check_verdict_refs(g2, res)))
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
