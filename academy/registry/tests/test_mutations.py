"""The mutation path: set-status and evidence (fsl-claims), line-preserving; new."""
import unittest

from _util import Homes, write, LAB_GOOD

from registry.core import federation
from registry.profiles import fsl, s1kb

OPEN = LAB_GOOD.replace("status: supported", "status: open").replace(
    "  - 2026-09-24 | supported | ran\n", "")

COMP = {"basis": "computation", "commit": "c0", "validation_passed": True,
        "outcome": "supports", "producer_role": "experimenter",
        "verdicts": [{"verdict": "SOUND", "run_id": "A", "grader_role": "experiment-reviewer",
                      "ref": "audits/foo/2026-09-28-A.md"},
                     {"verdict": "SOUND", "run_id": "B", "grader_role": "experiment-reviewer",
                      "ref": "audits/foo/2026-09-28-B.md"}]}


def landed(subject, verdict, run_id, by="landed_by: researcher/land_review"):
    """A review record as the SubagentStop hooks land it (the fields the grounds read)."""
    return ("---\nsubject: %s\nrun: A\nrun_id: %s\nverdict: %s\n%s\n---\nreport\n"
            % (subject, run_id, verdict, by))


class TestSetStatus(Homes):
    def setUp(self):
        super().setUp()
        self.p = write(self.lab / "claims" / "lab" / "foo.md", OPEN, newline="\r\n")
        for run in ("A", "B"):
            write(self.lab / "audits" / "foo" / ("2026-09-28-%s.md" % run),
                  landed("lab:foo", "SOUND", run))

    def test_only_the_intended_lines_change_and_crlf_is_kept(self):
        before = self.p.read_bytes()
        fsl.set_status(self.lab, "lab:foo", "supported", COMP, note="two audits", date="2026-09-28")
        after = self.p.read_bytes()
        self.assertNotIn(b"\n", after.replace(b"\r\n", b""))        # every line still CRLF
        b, a = before.decode().split("\r\n"), after.decode().split("\r\n")
        removed = [x for x in b if x not in a]
        added = [x for x in a if x not in b]
        self.assertEqual(removed, ["status: open"])
        # the review records the change rests on are written as evidence rows
        self.assertEqual(added, ["status: supported",
                                 "  - audit | audits/foo/2026-09-28-A.md | SOUND | run A; "
                                 "grader experiment-reviewer",
                                 "  - audit | audits/foo/2026-09-28-B.md | SOUND | run B; "
                                 "grader experiment-reviewer",
                                 "  - 2026-09-28 | supported | two audits; computation review "
                                 "(SOUND A, SOUND B)"])
        self.assertLess(a.index(added[3]), a.index("  - 2026-09-20 | open | created"))

    def test_verdicts_must_match_their_review_records(self):
        before = self.p.read_bytes()

        def refs(**kw):
            g = {k: v for k, v in COMP.items() if k != "verdicts"}
            g["verdicts"] = [dict(v, **kw) for v in COMP["verdicts"]]
            return g
        write(self.lab / "audits" / "other" / "x.md", landed("lab:other", "SOUND", "A"))
        write(self.lab / "audits" / "bad" / "gap.md", landed("lab:foo", "GAP", "A"))
        write(self.lab / "audits" / "bad" / "prover.md",
              landed("lab:foo", "SOUND", "A", by="agent: expert:rigor-reviewer"))
        cases = (
            (refs(ref="audits/none.md"), "not found"),                       # made-up ref
            ({**COMP, "verdicts": [{k: v for k, v in r.items() if k != "ref"}
                                   for r in COMP["verdicts"]]}, "ref of its review record"),
            (refs(ref="audits/other/x.md"), "is about lab:other"),
            (refs(ref="audits/bad/gap.md"), "says GAP"),
            (refs(ref="audits/bad/prover.md"), "written by rigor-reviewer"),
            (refs(grader_role="prover"), "graded by experiment-reviewer"),  # wrong reviewer
            (dict(COMP, producer_role="experiment-reviewer",
                  verdicts=[dict(r, grader_role="experimenter") for r in COMP["verdicts"]]),
             "graded by experiment-reviewer"),                               # swapped roles
        )
        for g, why in cases:
            with self.subTest(why=why):
                with self.assertRaises(fsl.Refused) as cm:
                    fsl.set_status(self.lab, "lab:foo", "supported", g)
                self.assertIn(why, str(cm.exception))
                self.assertEqual(self.p.read_bytes(), before)

    def test_refusals_leave_the_file_untouched(self):
        before = self.p.read_bytes()
        for status, g in (("supported", None),                       # no grounds
                          ("proved", COMP),                          # computation never proves
                          ("supported", dict(COMP, producer_role="experiment-reviewer"))):
            with self.subTest(status=status):
                with self.assertRaises(fsl.Refused):
                    fsl.set_status(self.lab, "lab:foo", status, g)
                self.assertEqual(self.p.read_bytes(), before)

    def test_refused_when_the_result_fails_the_check(self):
        write(self.p, OPEN.replace("  - experiment | results/x.json | not audited | "
                                   "0 counterexamples below 10\n", "").replace(
                                       "evidence:\n", "evidence: []\n"))
        before = self.p.read_bytes()
        word = {"basis": "human", "quote": "it is supported"}
        with self.assertRaises(fsl.Refused) as cm:
            fsl.set_status(self.lab, "lab:foo", "supported", word, human=True)
        self.assertIn("no evidence", str(cm.exception))
        self.assertEqual(self.p.read_bytes(), before)
        fsl.set_status(self.lab, "lab:foo", "supported", word, human=True,
                       evidence=["audit | results/x.json | SOUND | runs A, B"])
        c = fsl.parse_text(self.p.read_text(encoding="utf-8"))
        self.assertEqual(c.status, "supported")
        self.assertEqual(c.evidence, ["audit | results/x.json | SOUND | runs A, B"])

    def test_human_quote(self):
        fsl.set_status(self.lab, "lab:foo", "dropped",
                       {"basis": "human", "quote": "stop: out of scope"}, human=True)
        c = fsl.parse_text(self.p.read_text(encoding="utf-8"), fallback=False)
        self.assertEqual(c.status, "dropped")
        self.assertIn('Roey\'s word "stop: out of scope"', c.history[0])

    def test_human_quote_from_an_agent_names_its_ticket(self):
        before = self.p.read_bytes()
        with self.assertRaises(fsl.Refused) as cm:
            fsl.set_status(self.lab, "lab:foo", "dropped", {"basis": "human", "quote": "stop"})
        self.assertIn("ticket or packet", str(cm.exception))
        self.assertEqual(self.p.read_bytes(), before)
        fsl.set_status(self.lab, "lab:foo", "dropped",
                       {"basis": "human", "quote": "stop", "where": "T-0007"})
        self.assertIn("(T-0007)", fsl.parse_text(self.p.read_text(encoding="utf-8")).history[0])

    def test_attach_evidence(self):
        fsl.attach_evidence(self.lab, "lab:foo", "audit | results/x.json | SOUND | run A")
        c = fsl.parse_text(self.p.read_text(encoding="utf-8"), fallback=False)
        self.assertEqual(c.evidence[-1], "audit | results/x.json | SOUND | run A")
        with self.assertRaises(fsl.Refused):
            fsl.attach_evidence(self.lab, "lab:foo", "audit | results/x.json | SOUND | run A")
        with self.assertRaises(fsl.Refused):
            fsl.attach_evidence(self.lab, "lab:foo", "rumour | x | - | y")

    def test_new_writes_the_dialect(self):
        p = fsl.new_claim(self.lab, "lab:bar", "a: title, with [brackets]")
        text = p.read_text(encoding="utf-8")
        self.assertIn("evidence: []", text)
        self.assertIn('title: "a: title, with [brackets]"', text)
        c = fsl.parse_text(text, fallback=False)
        self.assertEqual(c.title, "a: title, with [brackets]")
        cs, _ = fsl.load(fsl.registry_root(self.lab))
        errs, _ = fsl.check(cs, repo=self.lab)
        self.assertEqual([e for e in errs if "bar" in e], [])


class TestModuloWrite(unittest.TestCase):
    """proved-modulo writes the grounds' inputs as the record's `modulo`; proved drops it."""

    def doc(self, text):
        import tempfile, pathlib
        from registry.core.edit import Doc
        d = pathlib.Path(tempfile.mkdtemp()) / "x.md"
        d.write_bytes(text.encode())
        return Doc(d)

    def test_set_list_replaces_and_remove_drops(self):
        doc = self.doc("---\nid: a\nstatus: sketch\ndepends_on: [b]\nevidence:\n  - x\n---\nbody\n")
        after = ("id", "kind", "form", "title", "status", "statement")
        doc.set_list("modulo", ["paper:lem:p", "paper:lem:q"], after=after)
        self.assertEqual(doc.list_items("modulo"), ["paper:lem:p", "paper:lem:q"])
        self.assertLess(doc.find("status"), doc.find("modulo"))
        self.assertLess(doc.find("modulo"), doc.find("depends_on"))
        doc.set_list("modulo", ["paper:lem:r"], after=after)
        self.assertEqual(doc.list_items("modulo"), ["paper:lem:r"])
        doc.remove("modulo")
        self.assertIsNone(doc.find("modulo"))
        self.assertEqual(doc.list_items("depends_on"), ["b"])
        self.assertEqual(doc.list_items("evidence"), ["x"])


class TestS1(Homes):
    def test_sql_is_in_memory_and_writes_nothing(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = s1kb.main(["sql", "SELECT id FROM entities ORDER BY id", "--root", str(self.s1)])
        self.assertEqual(rc, 0)
        self.assertIn("CEX-1", out.getvalue())
        self.assertFalse((self.s1 / "kb").exists())
        self.assertFalse((self.s1 / "STATUS.md").exists())

    def test_check_files_reports_only_those(self):
        write(self.s1 / "claims" / "CEX-1.md", "---\nid: CEX-1\nstatus: Proven\n---\n")
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = s1kb.main(["check", str(self.s1 / "assumptions" / "GA-2T′.md"),
                            "--root", str(self.s1)])
        self.assertEqual(rc, 0, out.getvalue())
        with contextlib.redirect_stdout(out):
            rc = s1kb.main(["check", str(self.s1 / "claims" / "CEX-1.md"), "--root", str(self.s1)])
        self.assertEqual(rc, 1)
        self.assertIn("status 'Proven'", out.getvalue())

    def test_attach_verdict(self):
        eid, vrel = s1kb.attach_verdict(self.s1, "N8", "computation/verdicts/2026-09-24_G8.md")
        self.assertEqual((eid, vrel), ("CEX-1", "computation/verdicts/2026-09-24_G8.md"))
        text = (self.s1 / "claims" / "CEX-1.md").read_text(encoding="utf-8")
        self.assertIn("cleared_by: [computation/verdicts/2026-09-24_G8.md]", text)
        federation.CACHE.clear()
        with self.assertRaises(ValueError):
            s1kb.attach_verdict(self.s1, "CEX-1", "notes/x.md")


if __name__ == "__main__":
    unittest.main()
