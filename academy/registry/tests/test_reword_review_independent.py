"""T-0347, the reword pass, tested by test-engineer from the ticket's rule (not from the
code's output).

The human's rule (2026-10-12, T-0347): a statement reworded after a CONFIRMED x2 pass gets
one informed reword run; reword CONFIRMED + the base pass CONFIRMED x2 on ``base_hash``
=> proved; wording beyond the proof => a full blind pass. So:

* a reword row counts only together with two base rows on ``base_hash``;
* a reword run is never one of a blind pair (never counts as a blind verdict);
* a reword never stacks on a reword (exactly one reword row; the base rows are blind).

Tests named ``test_finding_*`` demonstrated review findings on T-0347's thread
(expectedFailure until the developer's fix 723f3d3).
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _util import notebook_config, write  # noqa: F401  (puts the engine on sys.path)

from registry.core import grounds
from registry.profiles import s1kb

OLD, NEW = "1111111111111111", "2222222222222222"

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


def row(run_id, h, **kw):
    r = {"verdict": "CONFIRMED", "run_id": run_id, "grader_role": "rigor-reviewer",
         "statement_hash": h, "ref": "%s.md" % run_id}
    r.update(kw)
    return r


def rw_row(run_id="r", h=NEW, base_hash=OLD, scope="equivalent", **kw):
    return row(run_id, h, mode="reword", base_hash=base_hash, reword_scope=scope, **kw)


def rw_grounds(rows, **kw):
    g = {"basis": "proof", "mode": "reword", "base_pass": "2026-10-01-T-0001",
         "base_hash": OLD, "statement_hash": NEW, "producer_role": "researcher",
         "verdicts": rows}
    g.update(kw)
    return g


class RewordGroundsFromTheRule(unittest.TestCase):
    def ok(self, g, status="proved", current=NEW):
        return grounds.check_grounds(status, g, current)[0]

    def test_the_rule_itself_is_accepted(self):
        """R CONFIRMED on NEW + A, B CONFIRMED on OLD = base_hash -> proved."""
        self.assertTrue(self.ok(rw_grounds([rw_row(), row("a", OLD), row("b", OLD)])))

    def test_a_reword_row_without_base_rows_is_refused(self):
        self.assertFalse(self.ok(rw_grounds([rw_row()])))
        self.assertFalse(self.ok(rw_grounds([rw_row(), row("a", OLD)])))

    def test_a_reword_row_never_completes_a_blind_pair(self):
        """One blind CONFIRMED + one reword CONFIRMED, without mode: reword, on one hash."""
        g = {"basis": "proof", "producer_role": "researcher", "statement_hash": NEW,
             "verdicts": [row("a", NEW), rw_row(h=NEW)]}
        self.assertFalse(self.ok(g))

    def test_base_hash_mismatch_is_refused(self):
        # the base runs were given on another statement than the one R compared against
        self.assertFalse(self.ok(rw_grounds([rw_row(), row("a", "3" * 16),
                                             row("b", "3" * 16)])))
        # one base run on another statement
        self.assertFalse(self.ok(rw_grounds([rw_row(), row("a", OLD), row("b", "3" * 16)])))
        # the reword row names another base_hash than the grounds
        self.assertFalse(self.ok(rw_grounds([rw_row(base_hash="3" * 16), row("a", OLD),
                                             row("b", OLD)])))

    def test_the_claims_current_hash_is_the_new_one(self):
        g = rw_grounds([rw_row(), row("a", OLD), row("b", OLD)])
        self.assertFalse(self.ok(g, current=OLD))

    def test_reword_on_reword_is_refused(self):
        """R2 on top of R1 (itself a reword of A/B): two reword rows."""
        third = "4444444444444444"
        g = rw_grounds([rw_row("r2", h=third, base_hash=NEW), rw_row("r1"), row("a", OLD)],
                       base_hash=NEW, statement_hash=third)
        self.assertFalse(self.ok(g, current=third))

    def test_scope_exceeds_and_non_confirmed_are_refused(self):
        self.assertFalse(self.ok(rw_grounds([rw_row(scope="exceeds"), row("a", OLD),
                                             row("b", OLD)])))
        self.assertFalse(self.ok(rw_grounds([rw_row(verdict="GAP"), row("a", OLD),
                                             row("b", OLD)])))
        self.assertFalse(self.ok(rw_grounds([rw_row(verdict="DISPROVED"), row("a", OLD),
                                             row("b", OLD)]), "refuted"))

    def test_proved_modulo_needs_the_modulo(self):
        g = rw_grounds([rw_row(), row("a", OLD), row("b", OLD)])
        self.assertFalse(self.ok(g, "proved-modulo"))
        g["modulo"] = ["paper:lem:a"]
        self.assertTrue(self.ok(g, "proved-modulo"))
        self.assertFalse(self.ok(g, "proved"))


class RewordVerdictRefs(unittest.TestCase):
    """check_verdict_refs ties each row to its landed record."""

    BLIND = ("---\nsubject: flat:Q1\nrun: {run}\nrun_id: {rid}\nverdict: CONFIRMED\n"
             "statement_hash: {h}\nagent: expert:rigor-reviewer\n---\nreport\n")
    REWORD = ("---\nsubject: flat:Q1\nrun: R\nrun_id: r\nverdict: CONFIRMED\n"
              "statement_hash: " + NEW + "\n{extra}agent: expert:rigor-reviewer\n---\n"
              "report\n")

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="reword-refs-"))
        self.addCleanup(shutil.rmtree, str(self.d), True)
        write(self.d / "a.md", self.BLIND.format(run="A", rid="a", h=OLD))
        write(self.d / "b.md", self.BLIND.format(run="B", rid="b", h=OLD))

    def refs(self, extra, g=None):
        write(self.d / "r.md", self.REWORD.format(extra=extra))
        g = g or rw_grounds([rw_row(), row("a", OLD), row("b", OLD)])
        return grounds.check_verdict_refs(g, lambda ref: str(self.d / ref), "flat:Q1")

    FULL = ("mode: reword\nbase_pass: 2026-10-01-T-0001\nbase_hash: " + OLD +
            "\nreword_scope: equivalent\n")

    def test_a_full_reword_record_matches(self):
        self.assertEqual(self.refs(self.FULL), [])

    def test_a_record_with_another_scope_or_base_hash_is_refused(self):
        self.assertTrue(self.refs(self.FULL.replace("equivalent", "exceeds")))
        self.assertTrue(self.refs(self.FULL.replace(OLD, "3" * 16)))

    def test_a_reword_record_given_as_a_base_row_is_refused(self):
        g = rw_grounds([rw_row("a"), row("r", NEW), row("b", OLD)])
        # rows' run ids follow the records: a.md is blind, r.md is the reword record
        g["verdicts"][0]["ref"] = "a.md"
        g["verdicts"][1]["ref"] = "r.md"
        self.assertTrue(self.refs(self.FULL, g))

    def test_finding_record_without_reword_scope_backs_a_claimed_scope(self):
        """Finding: a reword record that records no reword_scope is accepted for a row
        that claims 'equivalent' (the scope is the reword run's own judgement, so the
        record must carry it)."""
        self.assertTrue(self.refs(self.FULL.replace("reword_scope: equivalent\n", "")))

    def test_finding_record_of_another_base_pass(self):
        """Finding: grounds.base_pass is never compared with the record's base_pass."""
        self.assertTrue(self.refs(self.FULL.replace("2026-10-01-T-0001",
                                                    "2026-08-01-T-0999")))


class RewordRecordsInANotebook(unittest.TestCase):
    """s1kb.verdict_file_problems on landed records (the CLI's --verdict path)."""

    RUN = ("---\nsubject: flat:Q1\nrun: {r}\nrun_id: rv-{r}\nverdict: {v}\n"
           "statement_hash: {h}\nlanded_by: expert/land_verdict\n---\nreport\n")
    RW = ("---\nsubject: flat:Q1\nrun: R\nrun_id: rv-R\nverdict: CONFIRMED\n"
          "statement_hash: {h}\nmode: reword\nbase_pass: {bp}\nbase_hash: {bh}\n"
          "reword_scope: equivalent\nlanded_by: expert/land_verdict\n---\nreport\n")
    BASE = "2026-10-01-T-0001"
    RWP = "2026-10-12-T-0347-reword"

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="reword-nb-"))
        self.addCleanup(shutil.rmtree, str(self.root), True)
        notebook_config(self.root, ns="flat")
        write(self.root / "objects" / "question" / "Q1.md", Q1)
        self.subj = self.root / "audits" / "Q1"

    def land(self, pass_, name, text):
        write(self.subj / pass_ / name, text)

    def problems(self, pass_, name, label="proved"):
        kb = s1kb.load_kb(self.root)
        return s1kb.verdict_file_problems(kb, "audits/Q1/%s/%s" % (pass_, name), "Q1", label)

    def base(self, h=OLD):
        for r in ("A", "B"):
            self.land(self.BASE, r + ".md", self.RUN.format(r=r, v="CONFIRMED", h=h))

    def test_the_rule_carries_proved(self):
        self.base()
        self.land(self.RWP, "R.md", self.RW.format(h=NEW, bp=self.BASE, bh=OLD))
        self.assertEqual(self.problems(self.RWP, "R.md"), [])

    def test_base_hash_mismatch_is_refused(self):
        self.base(h="3" * 16)
        self.land(self.RWP, "R.md", self.RW.format(h=NEW, bp=self.BASE, bh=OLD))
        self.assertTrue(self.problems(self.RWP, "R.md"))

    def test_reword_on_a_reword_pass_is_refused(self):
        self.base()
        self.land(self.RWP, "R.md", self.RW.format(h=NEW, bp=self.BASE, bh=OLD))
        p2 = "2026-10-20-T-0400-reword"
        self.land(p2, "R.md", self.RW.format(h="4" * 16, bp=self.RWP, bh=NEW)
                  .replace("rv-R", "rv-R2"))
        self.assertTrue(self.problems(p2, "R.md"))

    def test_finding_a_reword_run_beside_one_blind_run_is_not_a_pair(self):
        """Finding: a reword R.md landed in a blind pass folder (land_verdict files it
        under whatever ``pass`` the block names) is counted by the blind path as the
        second run: one blind CONFIRMED + one reword CONFIRMED (on another hash) clears
        proved. A reword run is never one of a blind pair (roster-rules rule 4)."""
        self.land(self.BASE, "A.md", self.RUN.format(r="A", v="CONFIRMED", h=OLD))
        self.land(self.BASE, "R.md", self.RW.format(h=NEW, bp="2026-09-01-T-0000", bh=OLD))
        self.assertTrue(self.problems(self.BASE, "A.md"))

    def test_finding_an_unchanged_statement_is_no_reword(self):
        """Finding: R.md with statement_hash == base_hash is accepted (the engine's
        reword_problems and decide_reword both refuse it)."""
        self.base()
        self.land(self.RWP, "R.md", self.RW.format(h=OLD, bp=self.BASE, bh=OLD))
        self.assertTrue(self.problems(self.RWP, "R.md"))

    def test_finding_a_landed_reword_run_is_not_a_ledger_entity(self):
        """Finding: _audit_files skips landed runs only by ``run: A|B``, so a landed
        ``run: R`` record under audits/ is loaded as a ledger entity named ``R``."""
        self.base()
        self.land(self.RWP, "R.md", self.RW.format(h=NEW, bp=self.BASE, bh=OLD))
        self.assertNotIn("R", s1kb.load_kb(self.root).entities)


if __name__ == "__main__":
    unittest.main()
