"""decision_table.py: every row of the old /paper:verify decision table, in the
academy's verdict words, plus the mechanical rules added on top of it."""

import json
import os
import tempfile
import unittest

import fixtures  # noqa: F401  (puts the plugin's scripts on sys.path)
import _expert as ex
import decision_table as dt

_WS = {}


def setUpModule():
    # grounds.producer_role comes from the namespace owner in workspace.json: give the
    # module its own workspace (paper: -> author) instead of whatever the machine has
    _WS["dir"] = tempfile.TemporaryDirectory()
    path = os.path.join(_WS["dir"].name, "workspace.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"board": os.path.join(_WS["dir"].name, "board"),
                   "instances": {"author@x": {"role": "author", "ns": "paper",
                                               "home": os.path.join(_WS["dir"].name, "bi"),
                                               "domains": ["translation-surfaces"]}}}, fh)
    _WS["old"] = os.environ.get("ACADEMY_WORKSPACE")
    os.environ["ACADEMY_WORKSPACE"] = path


def tearDownModule():
    if _WS["old"] is None:
        os.environ.pop("ACADEMY_WORKSPACE", None)
    else:
        os.environ["ACADEMY_WORKSPACE"] = _WS["old"]
    _WS["dir"].cleanup()


def rec(verdict, run="A", run_id=None, modulo="none", model="claude-fable-5-1",
        h="abc123", subject="paper:lem:x", blocking="none"):
    text = ("Report text.\n\nVERDICT\nsubject: %s\npass: 2026-09-28-T-0007\nrun: %s\n"
            "verdict: %s\nmodulo: %s\nmodel: %s\nstatement_hash: %s\nblocking: %s\n"
            "ticket: T-0007\n" % (subject, run, verdict, modulo, model, h, blocking))
    r = dt.parse_record(text)
    r["run_id"] = run_id or ("rv-%s" % run)
    # a landed record's path: the server now requires each verdict's ref (Group D)
    r.setdefault("file", "reviews/paper/lem-x/2026-09-28-T-0007/%s.md" % run)
    return r


class ParseTests(unittest.TestCase):
    def test_block_in_fence(self):
        text = "Findings...\n\n```\nVERDICT\nsubject: s1:GEO-19\nverdict: GAP\n" \
               "modulo: none\nblocking: step 3\n```\n"
        r = dt.parse_record(text)
        self.assertEqual(r["verdict"], "GAP")
        self.assertEqual(r["subject"], "s1:GEO-19")
        self.assertEqual(r["blocking"], "step 3")
        self.assertEqual(r["modulo"], [])

    def test_last_block_wins(self):
        text = "VERDICT\nverdict: GAP\n\nlater\n\nVERDICT\nverdict: CONFIRMED\n"
        self.assertEqual(dt.parse_record(text)["verdict"], "CONFIRMED")

    def test_modulo_list(self):
        r = rec("CONFIRMED", modulo="paper:lem:a, bib:AW21#Thm1.3")
        self.assertEqual(r["modulo"], ["paper:lem:a", "bib:AW21#Thm1.3"])

    def test_old_status_words_are_not_verdicts(self):
        r = dt.parse_record("VERDICT\nverdict: proved\n")
        self.assertEqual(r["verdict"], "")
        self.assertTrue(r["problems"])

    def test_verdict_with_commentary(self):
        self.assertEqual(dt.norm_verdict("confirmed (on fable)"), "CONFIRMED")

    def test_landed_frontmatter_record(self):
        text = ("---\nsubject: paper:lem:x\npass: p\nrun: B\nrun_id: rv-2\n"
                "verdict: CONFIRMED\nmodulo: [paper:lem:a]\nmodel: fable\n"
                "statement_hash: h\nblocking:\nticket:\n---\n\nbody\n")
        r = dt.parse_record(text)
        self.assertEqual((r["run"], r["run_id"], r["verdict"], r["modulo"]),
                         ("B", "rv-2", "CONFIRMED", ["paper:lem:a"]))

    def test_no_block(self):
        self.assertTrue(dt.parse_record("just prose")["problems"])

    def test_statement_hash_ignores_whitespace(self):
        self.assertEqual(dt.statement_hash("Let  $M$\nbe a\tsurface."),
                         dt.statement_hash("Let $M$ be a surface."))
        self.assertNotEqual(dt.statement_hash("a"), dt.statement_hash("b"))
        self.assertEqual(len(dt.statement_hash("x")), 16)


class TableTests(unittest.TestCase):
    # --- the rows of the old table -------------------------------------------------

    def test_proved_proved_is_confirmed(self):
        r = dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B"))
        self.assertEqual(r["outcome"], "confirmed")
        self.assertEqual(r["proposed_status"], "proved")
        self.assertTrue(r["recolour"])

    def test_modulo_same_inputs(self):
        m = "paper:lem:a, bib:AW21#Thm1.3"
        r = dt.decide(rec("CONFIRMED", modulo=m), rec("CONFIRMED", run="B", modulo=m))
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["proposed_status"], "proved-modulo")
        self.assertFalse(r["recolour"])
        self.assertEqual(r["pending_inputs"], ["bib:AW21#Thm1.3", "paper:lem:a"])
        self.assertEqual([i["kind"] for i in r["file_items"]], ["verify-input"] * 2)

    def test_modulo_recolours_when_every_input_established(self):
        m = "paper:lem:a, bib:AW21#Thm1.3"
        r = dt.decide(rec("CONFIRMED", modulo=m), rec("CONFIRMED", run="B", modulo=m),
                      established=["paper:lem:a", "bib:AW21#Thm1.3"])
        self.assertTrue(r["recolour"])
        self.assertEqual(r["pending_inputs"], [])
        self.assertEqual(r["proposed_status"], "proved-modulo")

    def test_modulo_different_inputs_is_disagreement(self):
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:b"))
        self.assertEqual(r["outcome"], "disagreement")
        self.assertIsNone(r["proposed_status"])

    # T-0148 (the human's decision, 2026-10-09): a definition used only as notation is
    # not an input; two CONFIRMED runs differing only in definitions agree
    def test_definition_only_difference_is_agreement_and_flagged(self):
        kinds = {"paper:defn:affine-in-charts": "definition", "paper:lem:a": "claim"}
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a, paper:defn:affine-in-charts"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:a"),
                      kind_of=kinds.get)
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["modulo"], ["paper:lem:a"])
        self.assertEqual(r["proposed_status"], "proved-modulo")
        self.assertEqual(r["dropped_definitions"], ["paper:defn:affine-in-charts"])
        self.assertIn("T-0148", r["grounds"]["note"])
        self.assertEqual(r["grounds"]["modulo"], ["paper:lem:a"])
        self.assertIn("dropped definitions", dt._text(r))

    def test_definition_only_against_none_is_confirmed(self):
        r = dt.decide(rec("CONFIRMED", modulo="paper:defn:affine-in-charts"),
                      rec("CONFIRMED", run="B"), kind_of=lambda q: None)
        self.assertEqual(r["outcome"], "confirmed")
        self.assertEqual(r["proposed_status"], "proved")
        self.assertEqual(r["dropped_definitions"], ["paper:defn:affine-in-charts"])

    def test_lemma_difference_is_still_disagreement(self):
        kinds = {"paper:defn:d": "definition", "paper:lem:b": "claim"}
        r = dt.decide(rec("CONFIRMED", modulo="paper:defn:d, paper:lem:b"),
                      rec("CONFIRMED", run="B"), kind_of=kinds.get)
        self.assertEqual(r["outcome"], "disagreement")
        self.assertIsNone(r["proposed_status"])
        self.assertEqual(r["dropped_definitions"], [])
        self.assertIn("paper:lem:b", r["summary"])
        self.assertNotIn("paper:defn:d", r["summary"])

    def test_citation_difference_is_still_disagreement(self):
        r = dt.decide(rec("CONFIRMED", modulo="paper:defn:d, bib:Ha02#1.3"),
                      rec("CONFIRMED", run="B"), kind_of=lambda q: None)
        self.assertEqual(r["outcome"], "disagreement")

    def test_registry_kind_beats_the_label(self):
        # an id that looks like a definition but is a lemma in the registry is an input
        r = dt.decide(rec("CONFIRMED", modulo="s1:DEF-1"), rec("CONFIRMED", run="B"),
                      kind_of={"s1:DEF-1": "lemma"}.get)
        self.assertEqual(r["outcome"], "disagreement")
        self.assertTrue(dt.is_definition("s1:DEF-2", {"s1:DEF-2": "def"}.get))
        self.assertTrue(dt.is_definition("s1:DEF-9", lambda q: None))
        self.assertTrue(dt.is_definition("paper:defn:x", lambda q: None))
        self.assertFalse(dt.is_definition("paper:lem:x", lambda q: None))
        self.assertFalse(dt.is_definition("bib:defn:x", {"bib:defn:x": "definition"}.get))

    def test_default_lookup_falls_back_to_the_label(self):
        # the module's workspace names a home that does not exist: no registry, label rule
        self.assertIsNone(dt.registry_kind("paper:defn:x"))
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a, paper:defn:x"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:a"))
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["dropped_definitions"], ["paper:defn:x"])

    def test_one_modulo_one_clean_is_disagreement(self):
        r = dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B", modulo="paper:lem:b"))
        self.assertEqual(r["outcome"], "disagreement")

    def test_proved_then_gap_is_disagreement(self):
        r = dt.decide(rec("CONFIRMED"), rec("GAP", run="B", blocking="step 4"))
        self.assertEqual(r["outcome"], "disagreement")
        self.assertFalse(r["recolour"])
        self.assertEqual(r["file_items"][0]["text"], "step 4")

    def test_disproved_in_a(self):
        r = dt.decide(rec("DISPROVED", blocking="the L-shaped table"))
        self.assertEqual(r["outcome"], "disproved")
        self.assertTrue(r["needs_human"])
        self.assertIsNone(r["proposed_status"])
        self.assertEqual(r["file_items"][0]["kind"], "counterexample")
        # the module's workspace names no human: the generic wording
        self.assertIn("goes to the human at once", r["summary"])

    def test_disproved_in_b_whatever_a_said(self):
        r = dt.decide(rec("CONFIRMED"), rec("DISPROVED", run="B"))
        self.assertEqual(r["outcome"], "disproved")
        self.assertFalse(r["recolour"])

    def test_single_negative_run(self):
        r = dt.decide(rec("GAP", blocking="the uniform choice in step 2"))
        self.assertEqual(r["outcome"], "single-negative")
        self.assertFalse(r["launch_b"])
        self.assertEqual(r["file_items"][0]["text"], "the uniform choice in step 2")

    # --- the sequencing rule --------------------------------------------------------

    def test_confirmed_a_launches_b(self):
        a = rec("CONFIRMED")
        self.assertTrue(dt.should_launch_b(a))
        r = dt.decide(a)
        self.assertEqual(r["outcome"], "awaiting-b")
        self.assertTrue(r["launch_b"])

    def test_negative_a_does_not_launch_b(self):
        for v in ("GAP", "DISPROVED", "PLAUSIBLE"):
            self.assertFalse(dt.should_launch_b(rec(v)), v)

    def test_b_after_negative_a_is_an_anomaly(self):
        r = dt.decide(rec("GAP"), rec("CONFIRMED", run="B"))
        self.assertEqual(r["outcome"], "single-negative")
        self.assertTrue(any("non-positive run A" in a for a in r["anomalies"]))

    # --- fallback and degraded verdicts ---------------------------------------------

    def test_confirmed_on_fallback_reads_as_plausible(self):
        a = rec("CONFIRMED", model="claude-sonnet-4-5")
        self.assertFalse(dt.should_launch_b(a))
        r = dt.decide(a)
        self.assertEqual(r["outcome"], "degraded")
        self.assertTrue(r["anomalies"])
        self.assertEqual(r["runs"][0]["model"], "claude-sonnet-4-5")
        self.assertEqual(r["runs"][0]["effective"], "PLAUSIBLE")

    def test_sonnet_confirmed_pair_is_degraded(self):
        r = dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B", model="claude-sonnet-4-5"))
        self.assertEqual(r["outcome"], "degraded")
        self.assertIsNone(r["proposed_status"])
        self.assertEqual([x["effective"] for x in r["runs"]], ["CONFIRMED", "PLAUSIBLE"])

    def test_older_opus_and_haiku_are_fallbacks(self):
        for m in ("claude-opus-4-1", "claude-haiku-4-5", "opus-5-50", ""):
            with self.subTest(model=m):
                self.assertFalse(dt.should_launch_b(rec("CONFIRMED", model=m)))

    # --- Opus 5.5 is an equal primary (the default grading.primaryModels) ----------

    def test_opus_55_confirmed_counts(self):
        for m in ("claude-opus-5-5", "claude-opus-5-5[1m]", "Opus 5.5", "opus-5.5"):
            with self.subTest(model=m):
                a = rec("CONFIRMED", model=m)
                self.assertTrue(dt.should_launch_b(a))
                r = dt.decide(a)
                self.assertEqual(r["outcome"], "awaiting-b")
                self.assertEqual(r["anomalies"], [])

    def test_opus_55_pair_proposes_proved(self):
        r = dt.decide(rec("CONFIRMED", model="claude-opus-5-5"),
                      rec("CONFIRMED", run="B", model="claude-opus-5-5"))
        self.assertEqual(r["outcome"], "confirmed")
        self.assertEqual(r["proposed_status"], "proved")
        self.assertEqual([x["model"] for x in r["runs"]],
                         ["claude-opus-5-5", "claude-opus-5-5"])
        ok, why = ex.mcp_module("claims").check_grounds("proved", r["grounds"], "abc123")
        self.assertTrue(ok, why)

    def test_fable_and_opus_55_mix(self):
        r = dt.decide(rec("CONFIRMED", model="claude-opus-5-5"), rec("CONFIRMED", run="B"))
        self.assertEqual(r["outcome"], "confirmed")

    def test_primary_option_narrows_the_set(self):
        a = rec("CONFIRMED", model="claude-opus-5-5")
        self.assertFalse(dt.should_launch_b(a, primary="fable"))
        self.assertTrue(dt.should_launch_b(a, primary="fable, opus-5.5"))
        self.assertEqual(dt.decide(a, primary="fable")["outcome"], "degraded")

    def test_model_label(self):
        cases = {"claude-fable-5-1": "fable", "claude-opus-5-5": "opus-5.5",
                 "claude-opus-5-5[1m]": "opus-5.5", "Opus 5.5": "opus-5.5",
                 "opus": "opus", "claude-opus-4-1": "opus",
                 "claude-sonnet-4-5": "sonnet", "": ""}
        for name, want in cases.items():
            with self.subTest(name=name):
                self.assertEqual(dt.model_label(name), want)
        self.assertEqual(dt.PRIMARY_MODELS, ("fable", "opus-5.5"))

    def test_primaries_from_workspace_config(self):
        a = rec("CONFIRMED", model="claude-opus-5-5")
        self.assertEqual(dt.configured_primaries(), ("fable", "opus-5.5"))   # the default
        with open(os.environ["ACADEMY_WORKSPACE"], encoding="utf-8") as fh:
            ws = json.load(fh)
        path = os.path.join(_WS["dir"].name, "ws-fable-only.json")
        ws["grading"] = {"primaryModels": ["fable"]}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(ws, fh)
        old = os.environ["ACADEMY_WORKSPACE"]
        os.environ["ACADEMY_WORKSPACE"] = path
        try:
            self.assertEqual(dt.configured_primaries(), ("fable",))
            self.assertFalse(dt.should_launch_b(a))
            self.assertEqual(dt.decide(a)["outcome"], "degraded")
        finally:
            os.environ["ACADEMY_WORKSPACE"] = old
        self.assertTrue(dt.should_launch_b(a))

    def test_plausible_b_never_counts(self):
        r = dt.decide(rec("CONFIRMED"), rec("PLAUSIBLE", run="B"))
        self.assertEqual(r["outcome"], "degraded")
        self.assertIsNone(r["proposed_status"])

    def test_fallback_b(self):
        # a bare "opus" names no version: not provably Opus 5.5, so a fallback
        r = dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B", model="opus"))
        self.assertEqual(r["outcome"], "degraded")

    # --- pair validity --------------------------------------------------------------

    def test_shared_run_id_is_invalid(self):
        r = dt.decide(rec("CONFIRMED", run_id="rv-1"), rec("CONFIRMED", run="B",
                                                             run_id="rv-1"))
        self.assertEqual(r["outcome"], "invalid-pair")

    def test_statement_changed_between_runs(self):
        r = dt.decide(rec("CONFIRMED", h="aaa"), rec("CONFIRMED", run="B", h="bbb"))
        self.assertEqual(r["outcome"], "invalid-pair")
        self.assertTrue(any("statement hashes differ" in a for a in r["anomalies"]))

    def test_different_subjects(self):
        r = dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B", subject="paper:lem:y"))
        self.assertEqual(r["outcome"], "invalid-pair")

    def test_missing_a(self):
        self.assertEqual(dt.decide(None)["outcome"], "incomplete")
        self.assertEqual(dt.decide(dt.parse_record("no verdict"))["outcome"], "incomplete")

    def test_unreadable_b_after_confirmed_a(self):
        r = dt.decide(rec("CONFIRMED"), dt.parse_record("B crashed"))
        self.assertEqual(r["outcome"], "incomplete")

    def test_every_outcome_is_known(self):
        cases = [dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B")),
                 dt.decide(rec("GAP")), dt.decide(rec("DISPROVED")), dt.decide(None)]
        for c in cases:
            self.assertIn(c["outcome"], dt.OUTCOMES)


class GroundsTests(unittest.TestCase):
    """The grounds the table proposes pass the server's own check_grounds."""

    def setUp(self):
        self.claims = ex.mcp_module("claims")

    def test_proved_grounds_accepted(self):
        r = dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B"))
        ok, why = self.claims.check_grounds("proved", r["grounds"], "abc123")
        self.assertTrue(ok, why)

    def test_modulo_grounds_accepted(self):
        m = "paper:lem:a"
        r = dt.decide(rec("CONFIRMED", modulo=m), rec("CONFIRMED", run="B", modulo=m))
        ok, why = self.claims.check_grounds("proved-modulo", r["grounds"], "abc123")
        self.assertTrue(ok, why)
        ok, _ = self.claims.check_grounds("proved", r["grounds"], "abc123")
        self.assertFalse(ok)

    def test_stale_hash_refused_by_server(self):
        r = dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B"))
        ok, _ = self.claims.check_grounds("proved", r["grounds"], "another-hash")
        self.assertFalse(ok)


class CliTests(unittest.TestCase):
    def test_cli_on_files(self):
        d = tempfile.mkdtemp()
        try:
            a = os.path.join(d, "A.md")
            b = os.path.join(d, "B.md")
            with open(a, "w", encoding="utf-8") as fh:
                fh.write("VERDICT\nsubject: paper:lem:x\nrun: A\nverdict: CONFIRMED\n"
                         "model: fable\nstatement_hash: h\nrun_id: rv-a\n")
            with open(b, "w", encoding="utf-8") as fh:
                fh.write("VERDICT\nsubject: paper:lem:x\nrun: B\nverdict: CONFIRMED\n"
                         "model: fable\nstatement_hash: h\nrun_id: rv-b\n")
            code, out, err = fixtures.run_script("decision_table.py", None,
                                                 [a, b, "--json"])
            self.assertEqual(code, 0, err)
            self.assertEqual(out["outcome"], "confirmed")
            code, out, err = fixtures.run_script("decision_table.py", None, [a])
            self.assertIn("outcome: awaiting-b", out)
            with open(b, "w", encoding="utf-8") as fh:
                fh.write("VERDICT\nsubject: paper:lem:x\nrun: B\nverdict: CONFIRMED\n"
                         "model: claude-opus-5-5\nstatement_hash: h\nrun_id: rv-b\n")
            code, out, err = fixtures.run_script("decision_table.py", None,
                                                 [a, b, "--json"])
            self.assertEqual(out["outcome"], "confirmed")
            code, out, err = fixtures.run_script("decision_table.py", None,
                                                 [a, b, "--json", "--primary", "fable"])
            self.assertEqual(out["outcome"], "degraded")
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)


class FollowUpRoutingTests(unittest.TestCase):
    """roster-rules.md "Role cut", rule 3: hypothesis-level findings go to the Researcher."""

    def gap(self, blocking, gap_class=None, subject="paper:lem:x"):
        r = rec("GAP", blocking=blocking, subject=subject)
        if gap_class:
            r["gap_class"] = gap_class
        return dt.decide(r)["file_items"][0]

    def test_a_hypothesis_gap_routes_to_the_researcher_never_the_author(self):
        it = self.gap("S is the completion of S' only if the structure is conical: "
                      "STRENGTHEN_HYPOTHESIS")
        self.assertEqual("hypothesis", it["gap_class"])
        self.assertEqual(("prove", "researcher"), (it["route"]["kind"], it["route"]["to_role"]))
        self.assertNotIn(it["route"]["kind"], ("apply", "write"))

    def test_the_verdict_field_wins_and_is_read_from_a_landed_body(self):
        text = ("---\nsubject: paper:lem:x\nrun: A\nverdict: GAP\nblocking: step 2\n---\n"
                "\nReport.\n\nVERDICT\nsubject: paper:lem:x\nrun: A\nverdict: GAP\n"
                "blocking: step 2\ngap_class: statement\n")
        r = dt.parse_record(text)
        self.assertEqual("statement", r["gap_class"])
        self.assertEqual("researcher", dt.follow_up({"kind": "repair"}, rec=r)["to_role"])

    def test_a_missing_step_is_the_researchers_and_wording_alone_the_owners(self):
        it = self.gap("step 3 does not follow from step 2")
        self.assertEqual(("proof", "researcher"), (it["gap_class"], it["route"]["to_role"]))
        it = self.gap("the second sentence is ambiguous", gap_class="wording")
        self.assertEqual(("question", "author"), (it["route"]["kind"], it["route"]["to_role"]))

    def test_a_disagreement_repair_and_a_counterexample_are_routed_too(self):
        res = dt.decide(rec("CONFIRMED"), rec("GAP", run="B", blocking="needs the "
                                                 "hypothesis that M is compact"))
        it = res["file_items"][0]
        self.assertEqual(("hypothesis", "researcher"), (it["gap_class"], it["route"]["to_role"]))
        res = dt.decide(rec("DISPROVED", blocking="the square torus"))
        self.assertEqual("human", res["file_items"][0]["route"]["to_role"])
        self.assertIn("-> prove ticket to researcher",
                      dt._text(dt.decide(rec("GAP", blocking="step 3"))))


if __name__ == "__main__":
    unittest.main()
