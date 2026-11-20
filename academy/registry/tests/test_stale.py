"""#109 part 1 (the human's ruling of 2026-11-20): statement drift after a review.

A proved / proved-modulo claim whose current statement hash differs from the hash of
its last positive review pass is flagged by ``check``, shown as ``proved (stale)`` in
the generated views, and ``registry.py stale --file-reword`` files one reword verify
ticket per such claim, titled ``Verify <claim> (reword of <pass>)`` (the title the
inbox reads as reword mode), never a second one while one is open.
"""
import contextlib
import io
import json
import re
import sys
import unittest
from pathlib import Path

from _util import Homes, write, ENGINE

import registry
from registry import cli
from registry.core import federation, stale
from registry.profiles import s1kb

sys.path.insert(0, str(ENGINE / "scripts"))
import board as board_mod  # noqa: E402

PAPER = """---
id: paper:{label}
title: {label}
status: {status}
where: sections/{section}
evidence:
  - note | Drafts/statements.md | - | - | two CONFIRMED runs (the passes are the library's)
history:
  - 2026-11-02 | {status} | two CONFIRMED runs
---
"""

RUN = """---
subject: paper:{label}
pass: {pass_}
run: {run}
run_id: {run_id}
verdict: {verdict}
modulo: {modulo}
model: {model}
statement_hash: {hash}
{extra}agent: expert:rigor-reviewer
landed: 2026-11-01
---

Verdict.
"""

#: inbox.js line 712: the title a reword verify ticket must match
INBOX_RE = re.compile(r"\(reword of (\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9][A-Za-z0-9._-]*)?)\)")


class StaleHomes(Homes):
    """The three homes plus an Expert home (the library) and a file board."""

    def setUp(self):
        super().setUp()
        self.lib = self.tmp / "LibHome"
        write(self.lib / ".claude" / "academy.json",
              json.dumps({"role": "expert", "instance": "expert@t",
                          "paths": {"reviews": "reviews"}}))
        ws = json.loads(self.ws.read_text(encoding="utf-8"))
        ws["instances"]["expert@t"] = {"role": "expert", "home": str(self.lib),
                                       "domains": ["d"]}
        write(self.ws, json.dumps(ws))
        (self.tmp / "board").mkdir(exist_ok=True)
        registry.clear_cache()
        self.tex = {"a.tex": "\\begin{prop}\\label{prop:foo}Every $x$ is fine.\\end{prop}\n"
                             "\\begin{lem}\\label{lem:bar}Bar holds.\\end{lem}\n"}
        self._write_tex()

    # -- fixtures ---------------------------------------------------------------
    def _write_tex(self):
        for name, text in self.tex.items():
            write(self.bi / "sections" / name, text)
        registry.clear_cache()

    def claim(self, label, status="proved", section="a.tex"):
        write(self.bi / "claims" / "paper" / (label.replace(":", "__") + ".md"),
              PAPER.format(label=label, status=status, section=section))
        registry.clear_cache()

    def hash_of(self, label):
        registry.clear_cache()
        return federation.store("paper", self.bi).statement_hash(label)

    def run_record(self, label, pass_, run, hash_, verdict="CONFIRMED", extra="",
                   modulo="[]", model="claude-opus-5-5", fname=None, run_id=None):
        d = self.lib / "reviews" / "paper" / label.replace(":", "-") / pass_
        write(d / ((fname or run) + ".md"), RUN.format(
            label=label, pass_=pass_, run=run, verdict=verdict, hash=hash_, extra=extra,
            modulo=modulo, model=model,
            run_id=run_id or "rv-20261101-0000%02d-%s" % (ord(run) - 64, run.lower())))
        return d

    def blind_pass(self, label, pass_, hash_, verdicts=("CONFIRMED", "CONFIRMED"),
                   decided=True):
        d = None
        for run, v in zip("AB", verdicts):
            d = self.run_record(label, pass_, run, hash_, v)
        if decided:
            write(d / "decision.md", "# decision\n\n- outcome: `confirmed`\n")
        return d

    def reword_pass(self, label, pass_, base, base_hash, hash_, scope="equivalent"):
        d = self.run_record(label, pass_, "R", hash_, extra="mode: reword\nbase_pass: %s\n"
                     "base_hash: %s\nreword_scope: %s\n" % (base, base_hash, scope))
        write(d / "decision.md", "# decision\n\noutcome `confirmed`\n")
        return d

    def reword_text(self, label, new):
        self.tex["a.tex"] = self.tex["a.tex"].replace(
            {"prop:foo": "Every $x$ is fine.", "lem:bar": "Bar holds."}[label], new)
        self._write_tex()

    def found(self, ns="paper", kind="stale"):
        registry.clear_cache()
        st = federation.store(ns, {"paper": self.bi, "s1": self.s1}[ns])
        return [i for i in stale.find(st, stale.reviews_root(self.bi)) if i["kind"] == kind]

    def unreviewed(self, ns="paper"):
        return self.found(ns, kind="unreviewed")

    def differing_pair(self, label, pass_, h, decision):
        """Two CONFIRMED runs whose modulo lists differ: the table's
        settle-dependencies (T-1461's shape)."""
        self.run_record(label, pass_, "A", h, modulo="[paper:lem:bar]")
        d = self.run_record(label, pass_, "B", h, modulo="[]")
        if decision is not None:
            write(d / "decision.md", decision)
        return d

    def cli(self, *argv, repo=None):
        out = io.StringIO()
        registry.clear_cache()
        with contextlib.redirect_stdout(out):
            rc = cli.main(["--repo", str(repo or self.bi)] + list(argv))
        return rc, out.getvalue()

    def tickets(self):
        return [m for _p, m in board_mod.ac.as_store(str(self.tmp / "board")).iter_meta()
                if m is not None]


class TestFind(StaleHomes):
    def test_unchanged_statement_is_not_stale(self):
        self.claim("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"))
        self.assertEqual(self.found(), [])

    def test_changed_statement_is_stale_against_its_last_positive_pass(self):
        self.claim("prop:foo")
        h0 = self.hash_of("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", h0)
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        items = self.found()
        self.assertEqual(len(items), 1, items)
        it = items[0]
        self.assertEqual(it["qid"], "paper:prop:foo")
        self.assertEqual(it["pass"], "2026-11-01-T-0001")
        self.assertEqual(it["base_pass"], "2026-11-01-T-0001")
        self.assertEqual(it["pass_hash"], h0)
        self.assertEqual(it["hash"], self.hash_of("prop:foo"))
        self.assertEqual(it["section"], "sections/a.tex")

    def test_only_proved_and_proved_modulo_are_flagged(self):
        self.claim("prop:foo", status="sketch")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"))
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        self.assertEqual(self.found(), [])
        self.claim("prop:foo", status="proved-modulo")
        self.assertEqual([i["status"] for i in self.found()], ["proved-modulo"])

    def test_a_negative_or_undecided_pass_is_not_positive(self):
        self.claim("prop:foo")
        h0 = self.hash_of("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", h0)
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        h1 = self.hash_of("prop:foo")
        # later passes on the new text: one GAP, one undecided -- neither is positive
        self.blind_pass("prop:foo", "2026-11-05-T-0002", h1, ("CONFIRMED", "GAP"))
        self.blind_pass("prop:foo", "2026-11-06-T-0003", h1, decided=False)
        items = self.found()
        self.assertEqual([i["pass"] for i in items], ["2026-11-01-T-0001"])
        # ... and the later closed pass on the current text keeps it from being filed
        self.assertIn("2026-11-05-T-0002", items[0]["hold"])

    def test_abandoned_pass_is_not_positive(self):
        self.claim("prop:foo")
        d = self.blind_pass("prop:foo", "2026-11-01-T-0001", "0123456789abcdef")
        write(d / "abandoned.md", "---\nabandoned: 2026-11-02\n---\nno\n")
        self.assertEqual(self.found(), [])

    def test_a_reword_pass_is_the_last_positive_pass(self):
        self.claim("prop:foo")
        h0 = self.hash_of("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", h0)
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        h1 = self.hash_of("prop:foo")
        self.reword_pass("prop:foo", "2026-11-03-T-0005-reword", "2026-11-01-T-0001", h0, h1)
        self.assertEqual(self.found(), [])          # the reword pass landed: not stale
        self.tex["a.tex"] = self.tex["a.tex"].replace("Every $x$ is very fine.",
                                                      "Every $y$ is very fine.")
        self._write_tex()
        items = self.found()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["pass"], "2026-11-03-T-0005-reword")
        self.assertEqual(items[0]["pass_hash"], h1)
        # a reword's base is always a blind CONFIRMED x2 pass, never a reword pass
        self.assertEqual(items[0]["base_pass"], "2026-11-01-T-0001")

    def test_a_renamed_record_is_held(self):
        # T-0476: the base pass is filed under the superseded id; the title route the
        # inbox reads passes no base_subject, so no ticket is filed for it
        self.claim("prop:foo")
        h0 = self.hash_of("prop:foo")
        self.blind_pass("prop:old", "2026-11-01-T-0001", h0)     # under the old id
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        h1 = self.hash_of("prop:foo")
        d = self.reword_pass("prop:foo", "2026-11-03-T-0005-reword", "2026-11-01-T-0001", h0, h1)
        r = (d / "R.md").read_text(encoding="utf-8")
        (d / "R.md").write_text(r.replace("mode: reword\n",
                                          "mode: reword\nbase_subject: paper:prop:old\n"),
                                encoding="utf-8")
        self.tex["a.tex"] = self.tex["a.tex"].replace("very fine", "quite fine")
        self._write_tex()
        items = self.found()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["base_subject"], "paper:prop:old")
        self.assertIn("renamed record", items[0]["hold"])

    def test_a_reword_run_outside_the_scopes_is_not_positive(self):
        self.claim("prop:foo")
        h0 = self.hash_of("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", h0)
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        h1 = self.hash_of("prop:foo")
        self.reword_pass("prop:foo", "2026-11-03-T-0005-reword", "2026-11-01-T-0001", h0, h1,
                         scope="exceeds")
        self.assertEqual([i["pass"] for i in self.found()], ["2026-11-01-T-0001"])

    def test_an_unregistered_copy_is_never_compared(self):
        # a home outside the workspace map with the paper's ns: the library's passes are
        # about the registered home's records, not this copy's
        import shutil
        copy = self.tmp / "elsewhere"
        shutil.copytree(self.bi, copy)
        self.claim("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", "0123456789abcdef")
        shutil.copytree(self.bi / "claims", copy / "claims", dirs_exist_ok=True)
        registry.clear_cache()
        self.assertEqual(len(self.found()), 1)
        st = federation.store("paper", copy)
        self.assertEqual(stale.find(st, stale.reviews_root(copy)), [])

    # -- review of b773f2f -------------------------------------------------------
    def test_relaunch_records_count(self):
        """Finding 1: a relaunched run lands as A-2.md; the pass stands on the latest
        record of each run (cor-full-preimage-locus T-1680's shape)."""
        self.claim("prop:foo")
        h0 = self.hash_of("prop:foo")
        self.run_record("prop:foo", "2026-11-01-T-0001", "A", "96a9a03a4d33eccc",
                        run_id="rv-20261101-000001-a")
        self.run_record("prop:foo", "2026-11-01-T-0001", "A", h0, fname="A-2",
                        run_id="rv-20261101-000002-a")
        d = self.run_record("prop:foo", "2026-11-01-T-0001", "B", h0,
                            run_id="rv-20261101-000003-b")
        write(d / "decision.md", "- outcome: `confirmed`\n")
        self.assertEqual(self.found(), [])          # positive, on h0: not stale
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        items = self.found()
        self.assertEqual([(i["pass"], i["pass_hash"]) for i in items],
                         [("2026-11-01-T-0001", h0)])
        # ... but the reword route reads A.md and B.md (reviews.base_decision): held
        self.assertIn("reviews.base_decision", items[0]["hold"])
        self.assertIn("invalid-pair", items[0]["hold"])

    def test_positive_is_what_the_decision_table_says(self):
        """Finding 2/3: two CONFIRMED runs whose modulo lists differ are not a confirmed
        pass for the decision table (reviews.base_decision refuses them as a reword
        base), whatever decision.md's wording."""
        self.claim("prop:foo")
        h0 = self.hash_of("prop:foo")
        self.run_record("prop:foo", "2026-11-01-T-0001", "A", h0, modulo="[paper:lem:bar]")
        d = self.run_record("prop:foo", "2026-11-01-T-0001", "B", h0, modulo="[]")
        write(d / "decision.md", "## Outcome\n\n`disagreement`; no status change\n")
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        self.assertEqual(self.found(), [])

    def test_non_primary_model_pair_is_not_positive(self):
        self.claim("prop:foo")
        h0 = self.hash_of("prop:foo")
        for run in "AB":
            d = self.run_record("prop:foo", "2026-11-01-T-0001", run, h0,
                                model="some-small-model")
        write(d / "decision.md", "- outcome: `confirmed`\n")
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        self.assertEqual(self.found(), [])

    def test_an_abandoned_later_pass_does_not_hold(self):
        """Finding 5."""
        self.claim("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"))
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        d = self.blind_pass("prop:foo", "2026-11-05-T-0002", self.hash_of("prop:foo"),
                            ("GAP", "CONFIRMED"), decided=False)
        write(d / "abandoned.md", "---\nabandoned: 2026-11-05\n---\nlost\n")
        items = self.found()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["hold"], "")

    # -- re-review of 5111b1b ----------------------------------------------------
    def test_table_gives_settle_dependencies_for_the_fixture(self):
        d = self.differing_pair("prop:foo", "2026-11-01-T-0001", "0123456789abcdef", None)
        dt = stale.decision_table()
        recs = stale.latest_records(d)
        self.assertEqual(dt.decide(recs["A"][1], recs["B"][1])["outcome"],
                         "settle-dependencies")

    def test_a_settled_pass_is_positive_and_held(self):
        """Finding 6: settle-dependencies settled to confirmed-modulo (decision.md, no
        S.json: T-1461) is positive; the reword route refuses it as a base: held."""
        self.claim("prop:foo")
        self.differing_pair("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"),
                            "## Outcome\n\n- outcome: `confirmed-modulo` (settled)\n")
        self.assertEqual(self.found(), [])
        self.assertEqual(self.unreviewed(), [])
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        items = self.found()
        self.assertEqual([i["pass"] for i in items], ["2026-11-01-T-0001"])
        self.assertIn("settle-dependencies", items[0]["hold"])

    def test_an_unsettled_pass_is_not_positive(self):
        self.claim("prop:foo")
        self.differing_pair("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"),
                            "- outcome: `settle-dependencies`\n")
        self.assertEqual(self.found(), [])

    def test_a_settlement_record_decides(self):
        """An applied S.json (settle_deps check + apply: confirmed-settled) settles the
        pass whatever decision.md says."""
        self.claim("prop:foo")
        d = self.differing_pair("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"),
                                "pass concluded\n")
        write(d / "S.json", json.dumps({"readings": {"differ": False, "evidence": ""},
                                        "inputs": [{"input": "paper:lem:bar", "case": 6,
                                                    "chosen": "", "sources": [],
                                                    "line": "l.3", "remark": "",
                                                    "evidence": "unused at l.3"}]}))
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        self.assertEqual([i["pass"] for i in self.found()], ["2026-11-01-T-0001"])

    def test_a_reword_over_a_settled_base_is_positive(self):
        """cor:covering-systole 0687 over 0670: the table gives invalid-base (its base is
        settle-dependencies); the base was settled, so the reword pass stands."""
        self.claim("prop:foo")
        h0 = self.hash_of("prop:foo")
        self.differing_pair("prop:foo", "2026-11-01-T-0001", h0,
                            "- outcome: `confirmed-modulo` (settled)\n")
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        h1 = self.hash_of("prop:foo")
        self.reword_pass("prop:foo", "2026-11-03-T-0005-reword", "2026-11-01-T-0001", h0, h1)
        self.assertEqual(self.found(), [])
        self.assertEqual(self.unreviewed(), [])

    def test_proved_without_a_positive_pass_is_reported(self):
        self.claim("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"),
                        ("GAP", "CONFIRMED"))
        items = self.unreviewed()
        self.assertEqual([i["qid"] for i in items], ["paper:prop:foo"])
        self.assertIn("without a positive review pass", items[0]["hold"])
        self.assertEqual(self.found(), [])

    def test_no_library_means_nothing_flagged(self):
        self.claim("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", "0123456789abcdef")
        registry.clear_cache()
        st = federation.store("paper", self.bi)
        self.assertEqual(stale.find(st, None), [])


class TestCheckAndViews(StaleHomes):
    def make_stale(self):
        self.claim("prop:foo")
        self.claim("lem:bar")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"))
        self.blind_pass("lem:bar", "2026-11-01-T-0004", self.hash_of("lem:bar"))
        self.reword_text("prop:foo", "Every $x$ is very fine.")

    def test_check_warns_on_the_stale_claim_only(self):
        self.make_stale()
        rc, out = self.cli("check")
        lines = [ln for ln in out.splitlines() if "stale" in ln]
        self.assertEqual(len(lines), 1, out)
        self.assertIn("prop__foo.md: WARN:", lines[0])
        self.assertIn("2026-11-01-T-0001", lines[0])
        self.assertEqual(rc, 0, out)                 # a warning, not an error
        rc, out = self.cli("check", "--strict")
        self.assertEqual(rc, 1)

    def test_check_unchanged_is_quiet(self):
        self.claim("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"))
        _rc, out = self.cli("check")
        self.assertNotIn("stale", out)

    def test_check_warns_on_proved_without_a_positive_pass(self):
        self.claim("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"),
                        ("GAP", "CONFIRMED"))
        _rc, out = self.cli("check")
        self.assertIn("proved without a positive review pass on record", out)
        self.cli("render")
        index = (self.bi / "claims" / "INDEX.md").read_text(encoding="utf-8")
        self.assertNotIn("(stale)", index)

    def test_missing_decision_table_is_said(self):
        """(a): without the Expert's decision table the check says so, naming the path,
        and stale --file-reword fails instead of reporting 0 claims."""
        self.make_stale()
        saved = dict(stale._DT), stale.DT_PATH
        self.addCleanup(lambda: (stale._DT.clear(), stale._DT.update(saved[0]),
                                 setattr(stale, "DT_PATH", saved[1])))
        stale._DT.clear()
        stale.DT_PATH = self.tmp / "nowhere" / "decision_table.py"
        _rc, out = self.cli("check")
        self.assertIn("decision_table.py", out)
        self.assertIn("nowhere", out)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc, out = self.cli("stale", "--ns", "paper", "--file-reword")
        self.assertNotEqual(rc, 0)
        self.assertIn("nowhere", err.getvalue())

    def test_decision_table_is_not_shadowed(self):
        fake = self.tmp / "fake"
        write(fake / "decision_table.py", "def decide(*a, **k):\n    return {}\n")
        sys.path.insert(0, str(fake))
        sys.modules.pop("decision_table", None)
        self.addCleanup(sys.path.remove, str(fake))
        self.addCleanup(sys.modules.pop, "decision_table", None)
        stale._DT.clear()
        dt = stale.decision_table()
        self.assertEqual(Path(dt.__file__).resolve(), stale.DT_PATH.resolve())

    def test_render_shows_proved_stale(self):
        self.make_stale()
        self.cli("render")
        index = (self.bi / "claims" / "INDEX.md").read_text(encoding="utf-8")
        line = [ln for ln in index.splitlines() if "`paper:prop:foo`" in ln][0]
        self.assertIn("proved (stale)", line)
        other = [ln for ln in index.splitlines() if "`paper:lem:bar`" in ln][0]
        self.assertNotIn("stale", other)
        html = (self.bi / "claims" / "index.html").read_text(encoding="utf-8")
        self.assertIn("proved (stale)", html)
        # display only: the stored status is unchanged
        rec = (self.bi / "claims" / "paper" / "prop__foo.md").read_text(encoding="utf-8")
        self.assertIn("status: proved\n", rec)

    def test_notebook_check_and_status_view(self):
        write(self.s1 / "claims" / "CRIT-2.md",
              "---\nid: CRIT-2\nkind: claim\nform: prop\ntitle: two\nstatus: proved\n"
              "depends_on: []\nlifecycle: active\naliases: []\ndomain: translation-surfaces\n"
              "tags: []\nsummary: proved one\nsource: here\nadded: 2026-09-24\nevidence: []\n"
              "history:\n  - 2026-09-28 | proved | reviewed\n---\n\n## Statement\n\nOld.\n")
        registry.clear_cache()
        h0 = federation.store("s1", self.s1).statement_hash("CRIT-2")
        d = self.lib / "reviews" / "s1" / "CRIT-2" / "2026-11-01-T-0009"
        for run in "AB":
            write(d / (run + ".md"), RUN.replace("paper:{label}", "s1:CRIT-2").format(
                label="", pass_="2026-11-01-T-0009", run=run, verdict="CONFIRMED",
                hash=h0, extra="", modulo="[]", model="claude-opus-5-5",
                run_id="rv-20261101-00000%d-x" % " AB".index(run)))
        write(d / "decision.md", "- outcome: `confirmed`\n")
        self.assertEqual(self.found("s1"), [])
        p = self.s1 / "claims" / "CRIT-2.md"
        p.write_text(p.read_text(encoding="utf-8").replace("Old.", "New."), encoding="utf-8")
        self.assertEqual([i["qid"] for i in self.found("s1")], ["s1:CRIT-2"])
        _rc, out = self.cli("check", repo=self.s1)
        self.assertTrue(any("CRIT-2" in ln and "stale" in ln for ln in out.splitlines()), out)
        kb = s1kb.load_kb(self.s1)
        s1kb.run_check(kb)
        self.assertIn("| proved (stale) |", s1kb.view_status(kb))


class TestFileReword(StaleHomes):
    def make_stale(self):
        self.claim("prop:foo", section="a.tex")
        self.claim("lem:bar", section="b.tex")
        self.tex["b.tex"] = ""
        self.blind_pass("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"))
        self.blind_pass("lem:bar", "2026-11-01-T-0004", self.hash_of("lem:bar"))
        self.reword_text("prop:foo", "Every $x$ is very fine.")
        self.reword_text("lem:bar", "Bar holds always.")

    def test_title_is_what_the_inbox_reads(self):
        t = stale.ticket_title("paper:prop:foo", "2026-11-01-T-0001")
        self.assertEqual(t, "Verify paper:prop:foo (reword of 2026-11-01-T-0001)")
        self.assertEqual(INBOX_RE.search(t).group(1), "2026-11-01-T-0001")

    def test_dry_run_lists_by_section_and_files_nothing(self):
        self.make_stale()
        rc, out = self.cli("stale", "--ns", "paper")
        self.assertEqual(rc, 0, out)
        self.assertIn("sections/a.tex", out)
        self.assertIn("Verify paper:prop:foo (reword of 2026-11-01-T-0001)", out)
        self.assertIn("Verify paper:lem:bar (reword of 2026-11-01-T-0004)", out)
        self.assertLess(out.index("sections/a.tex"), out.index("Verify paper:prop:foo"))
        self.assertEqual(self.tickets(), [])

    def test_file_reword_files_one_ticket_per_claim_and_never_twice(self):
        self.make_stale()
        rc, out = self.cli("stale", "--ns", "paper", "--file-reword")
        self.assertEqual(rc, 0, out)
        ts = self.tickets()
        self.assertEqual(sorted(t["title"] for t in ts),
                         ["Verify paper:lem:bar (reword of 2026-11-01-T-0004)",
                          "Verify paper:prop:foo (reword of 2026-11-01-T-0001)"])
        for t in ts:
            self.assertEqual((t["kind"], t["to"], t["from"]), ("verify", "expert@t", "expert@t"))
            self.assertIn(t["title"].split()[1], t["refs"])
            self.assertIn("mode reword", t["ask"])
        rc, out = self.cli("stale", "--ns", "paper", "--file-reword")
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.tickets()), 2)
        self.assertIn("already open", out)

    def test_an_open_ticket_filed_by_hand_is_not_duplicated(self):
        self.make_stale()
        board_mod.create_ticket(str(self.tmp / "board"), "expert@t",
                                "Verify paper:prop:foo (reword of 2026-11-01-T-0001)",
                                "by hand", "a packet", kind="verify",
                                refs=["paper:prop:foo"], as_instance="human")
        self.cli("stale", "--ns", "paper", "--file-reword")
        titles = [t["title"] for t in self.tickets()]
        self.assertEqual(titles.count("Verify paper:prop:foo (reword of 2026-11-01-T-0001)"), 1)
        self.assertIn("Verify paper:lem:bar (reword of 2026-11-01-T-0004)", titles)

    def test_any_open_verify_ticket_on_the_claim_covers_it(self):
        """Finding 4: a blind verify ticket on the claim (title or refs) is already
        open: no reword ticket beside it, and the listing names it."""
        self.make_stale()
        _p, meta = board_mod.create_ticket(
            str(self.tmp / "board"), "expert@t", "Verify the foo proposition", "blind",
            "a packet", kind="verify", refs=["paper:prop:foo"], as_instance="human",
            return_meta=True)
        _p, meta2 = board_mod.create_ticket(
            str(self.tmp / "board"), "expert@t", "Verify paper:lem:bar", "blind",
            "a packet", kind="verify", refs=[], as_instance="human", return_meta=True)
        _rc, out = self.cli("stale", "--ns", "paper", "--file-reword")
        self.assertEqual(len(self.tickets()), 2, out)
        self.assertIn("already open: %s" % meta["id"], out)
        self.assertIn("already open: %s" % meta2["id"], out)

    def test_unreviewed_is_listed_held_not_filed(self):
        self.claim("prop:foo")
        self.blind_pass("prop:foo", "2026-11-01-T-0001", self.hash_of("prop:foo"),
                        ("GAP", "CONFIRMED"))
        _rc, out = self.cli("stale", "--ns", "paper", "--file-reword")
        self.assertIn("paper:prop:foo", out)
        self.assertIn("without a positive review pass", out)
        self.assertEqual(self.tickets(), [])

    def test_section_filter(self):
        self.make_stale()
        self.cli("stale", "--ns", "paper", "--section", "sections/b.tex", "--file-reword")
        self.assertEqual([t["title"] for t in self.tickets()],
                         ["Verify paper:lem:bar (reword of 2026-11-01-T-0004)"])

    def test_held_claim_is_listed_not_filed(self):
        self.make_stale()
        self.blind_pass("prop:foo", "2026-11-05-T-0002", self.hash_of("prop:foo"),
                        ("GAP", "CONFIRMED"))
        _rc, out = self.cli("stale", "--ns", "paper", "--file-reword")
        self.assertIn("2026-11-05-T-0002", out)
        self.assertEqual([t["title"] for t in self.tickets()],
                         ["Verify paper:lem:bar (reword of 2026-11-01-T-0004)"])

    def test_as_human(self):
        self.make_stale()
        self.cli("stale", "--ns", "paper", "--file-reword", "--as", "human")
        self.assertEqual({t["from"] for t in self.tickets()}, {"human"})


if __name__ == "__main__":
    unittest.main()
