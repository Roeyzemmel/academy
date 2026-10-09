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


if __name__ == "__main__":
    unittest.main()
