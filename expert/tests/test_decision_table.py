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

    def test_modulo_different_inputs_go_to_the_settler(self):
        # #121 (the human's decision, 2026-11-20): two CONFIRMED runs that still differ in
        # the inputs they list are neither a union nor a ruling: the dependency-settler
        # classifies each differing input, and no status is proposed yet
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:b"))
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertIsNone(r["proposed_status"])
        self.assertEqual([(d["input"], d["run"], d["shape"]) for d in r["differing_inputs"]],
                         [("paper:lem:a", "A", "id"), ("paper:lem:b", "B", "id")])
        # the grounds settle_deps.py completes once the settler's record is applied (part 3):
        # both verdict rows, no modulo yet, and no grounds of the table's own
        self.assertIsNone(r["grounds"])
        g = r["grounds_template"]
        self.assertEqual((g["basis"], len(g["verdicts"]), g.get("modulo")), ("proof", 2, None))
        self.assertEqual({v["verdict"] for v in g["verdicts"]}, {"CONFIRMED"})

    # The definition rule (the human's ruling of 2026-11-20 on #103, replacing T-0148): a
    # definition in a CONFIRMED run's modulo list stays an input, of both runs, giving
    # proved-modulo, unless its registry record is tagged ``notation-only``; a reviewer's
    # ``(notation only)`` on the entry is not trusted
    def test_an_unmarked_definition_stays_an_input(self):
        # updated for the ruling: it was settle-dependencies (the settler could drop the
        # definition); now it is an input of both runs, mechanically, and never the settler's
        kinds = {"paper:defn:affine-in-charts": "definition", "paper:lem:a": "claim"}
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a, paper:defn:affine-in-charts"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:a"),
                      kind_of=kinds.get, tags_of=lambda q: None)
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["proposed_status"], "proved-modulo")
        self.assertEqual(r["modulo"], ["paper:defn:affine-in-charts", "paper:lem:a"])
        self.assertEqual(r["dropped_definitions"], [])
        self.assertEqual(r["kept_definitions"], ["paper:defn:affine-in-charts"])
        # against a clean run: proved-modulo the definition, never proved
        r = dt.decide(rec("CONFIRMED", modulo="paper:defn:affine-in-charts"),
                      rec("CONFIRMED", run="B"), kind_of=lambda q: None, tags_of=lambda q: None)
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["proposed_status"], "proved-modulo")
        self.assertEqual(r["grounds"]["modulo"], ["paper:defn:affine-in-charts"])

    def test_t1475_shape_is_proved_modulo_the_definition(self):
        """T-1475 (lem:illumination-open): A CONFIRMED with no inputs, B "CONFIRMED modulo
        paper:defn:illuminated-pair". T-0148's drop proposed proved (T-1703) and the
        claim-keeper refused; the ruling gives proved-modulo the definition."""
        defn = "paper:defn:illuminated-pair"
        kinds = {defn: "definition"}.get
        r = dt.decide(rec("CONFIRMED", subject="paper:lem:illumination-open"),
                      rec("CONFIRMED", run="B", modulo=defn,
                          subject="paper:lem:illumination-open"),
                      kind_of=kinds, tags_of=lambda q: None)
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["proposed_status"], "proved-modulo")
        self.assertEqual(r["modulo"], [defn])
        self.assertEqual(r["grounds"]["modulo"], [defn])
        self.assertEqual(r["dropped_definitions"], [])
        self.assertEqual(r["kept_definitions"], [defn])
        self.assertFalse(r["recolour"])
        # the same pair with the definition's record tagged notation-only: proved
        r = dt.decide(rec("CONFIRMED", subject="paper:lem:illumination-open"),
                      rec("CONFIRMED", run="B", modulo=defn,
                          subject="paper:lem:illumination-open"),
                      kind_of=kinds, tags_of={defn: ["notation-only"]}.get)
        self.assertEqual(r["outcome"], "confirmed")
        self.assertEqual(r["proposed_status"], "proved")
        self.assertEqual(r["dropped_definitions"], [defn])
        self.assertEqual(r["kept_definitions"], [])
        # a definition kept, a lemma only one run lists: the lemma alone is the settler's
        r = dt.decide(rec("CONFIRMED", modulo="%s, paper:lem:b" % defn),
                      rec("CONFIRMED", run="B"), kind_of=kinds, tags_of=lambda q: None)
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertEqual(r["modulo"], [defn])
        self.assertEqual([d["input"] for d in r["differing_inputs"]], ["paper:lem:b"])

    def test_the_reviewers_own_mark_is_not_trusted(self):
        """Review of e9a0272: a run could mark a definition the argument relies on; only
        the registry record's notation-only tag drops it."""
        kinds = {"paper:defn:affine-in-charts": "definition", "paper:lem:a": "claim"}
        # updated for the ruling (#103): the untagged definition is an input of both runs,
        # spelled without the reviewer's mark
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a, paper:defn:affine-in-charts "
                                              "(Notation-Only)"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:a"),
                      kind_of=kinds.get, tags_of=lambda q: None)
        self.assertEqual((r["outcome"], r["modulo"]),
                         ("confirmed-modulo", ["paper:defn:affine-in-charts", "paper:lem:a"]))
        r = dt.decide(rec("CONFIRMED", modulo="paper:defn:affine-in-charts (notation only)"),
                      rec("CONFIRMED", run="B"), kind_of=lambda q: None, tags_of=lambda q: None)
        self.assertEqual((r["proposed_status"], r["modulo"]),
                         ("proved-modulo", ["paper:defn:affine-in-charts"]))
        # with the registry tag the marked entry is dropped
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a, paper:defn:affine-in-charts "
                                              "(notation only)"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:a"), kind_of=kinds.get,
                      tags_of={"paper:defn:affine-in-charts": ["notation-only"]}.get)
        self.assertEqual((r["outcome"], r["dropped_definitions"]),
                         ("confirmed-modulo", ["paper:defn:affine-in-charts"]))

    def test_no_drop_through_a_via_that_is_circular_through_the_subject(self):
        links = {"paper:lem:y": {"depends_on": ["paper:lem:S"]},
                 "paper:lem:S": {"depends_on": ["paper:lem:x"]}}.get
        got = dt.reduce_differing(["paper:lem:y", "paper:lem:x"], ["paper:lem:y"], links,
                                  subject="paper:lem:S")
        self.assertEqual([], got["dropped"])
        self.assertEqual(["paper:lem:x"], got["differing"])

    def test_a_definition_tagged_notation_only_in_the_registry_is_dropped(self):
        tags = {"paper:defn:d": ["notation-only"], "paper:defn:e": ["setup"]}.get
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a, paper:defn:d"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:a"),
                      kind_of=lambda q: None, tags_of=tags)
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["dropped_definitions"], ["paper:defn:d"])
        # another tag marks nothing: the definition stays an input (updated for #103)
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a, paper:defn:e"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:a"),
                      kind_of=lambda q: None, tags_of=tags)
        self.assertEqual((r["outcome"], r["modulo"]),
                         ("confirmed-modulo", ["paper:defn:e", "paper:lem:a"]))
        # a notation-only definition both runs list is no input either
        r = dt.decide(rec("CONFIRMED", modulo="paper:defn:d"),
                      rec("CONFIRMED", run="B", modulo="paper:defn:d"),
                      kind_of=lambda q: None, tags_of=tags)
        self.assertEqual((r["outcome"], r["dropped_definitions"]), ("confirmed", ["paper:defn:d"]))

    def test_the_mark_on_a_non_definition_marks_nothing(self):
        self.assertIsNone(dt.notation_only("paper:lem:b (notation only)", lambda q: None,
                                           lambda q: None))
        self.assertIsNone(dt.notation_only("s1:DEF-1 (notation only)",
                                           {"s1:DEF-1": "lemma"}.get, lambda q: None))
        self.assertIsNone(dt.notation_only("bib:Ha02#Def1 (notation only)", lambda q: None,
                                           lambda q: ["notation-only"]))
        self.assertEqual(dt.notation_only("paper:defn:d ( notation  only )", lambda q: None,
                                          lambda q: ["notation-only"]), "paper:defn:d")
        self.assertIsNone(dt.notation_only("paper:defn:d ( notation  only )", lambda q: None,
                                           lambda q: None))
        self.assertEqual(dt.notation_only("s1:DEF-1", lambda q: None,
                                          {"s1:DEF-1": ["Notation-Only"]}.get), "s1:DEF-1")
        # pointer text other than the mark: the tag is read on the head (updated for the
        # re-review of e800543, R1; it pinned None here); an open [CHECK] is never dropped
        self.assertEqual(dt.notation_only("paper:defn:d (item 2)", lambda q: None,
                                          lambda q: ["notation-only"]), "paper:defn:d")
        self.assertIsNone(dt.notation_only("paper:defn:d [CHECK]", lambda q: None,
                                           lambda q: ["notation-only"]))
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:b (notation only)"),
                      rec("CONFIRMED", run="B"), kind_of=lambda q: None, tags_of=lambda q: None)
        self.assertEqual(r["outcome"], "settle-dependencies")

    def test_lemma_difference_goes_to_the_settler_without_the_definition(self):
        # the notation-only definition one run lists is dropped mechanically, the lemma one
        # run lists is the settler's
        kinds = {"paper:defn:d": "definition", "paper:lem:b": "claim"}
        r = dt.decide(rec("CONFIRMED", modulo="paper:defn:d (notation only), paper:lem:b"),
                      rec("CONFIRMED", run="B"), kind_of=kinds.get,
                      tags_of={"paper:defn:d": ["notation-only"]}.get)
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertIsNone(r["proposed_status"])
        self.assertEqual([d["input"] for d in r["differing_inputs"]], ["paper:lem:b"])
        self.assertEqual(r["dropped_definitions"], ["paper:defn:d"])
        self.assertIn("paper:lem:b", r["summary"])

    def test_citation_difference_goes_to_the_settler(self):
        r = dt.decide(rec("CONFIRMED", modulo="bib:Ha02#1.3"),
                      rec("CONFIRMED", run="B"), kind_of=lambda q: None)
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertEqual([(d["input"], d["run"], d["shape"]) for d in r["differing_inputs"]],
                         [("bib:Ha02#1.3", "A", "card")])

    def test_registry_kind_beats_the_label(self):
        # an id that looks like a definition but is a lemma in the registry is an input,
        # marked or not
        r = dt.decide(rec("CONFIRMED", modulo="s1:DEF-1 (notation only)"),
                      rec("CONFIRMED", run="B"), kind_of={"s1:DEF-1": "lemma"}.get,
                      tags_of=lambda q: None)
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertEqual([d["input"] for d in r["differing_inputs"]],
                         ["s1:DEF-1 (notation only)"])
        self.assertTrue(dt.is_definition("s1:DEF-2", {"s1:DEF-2": "def"}.get))
        self.assertTrue(dt.is_definition("s1:DEF-9", lambda q: None))
        self.assertTrue(dt.is_definition("paper:defn:x", lambda q: None))
        self.assertFalse(dt.is_definition("paper:lem:x", lambda q: None))
        self.assertFalse(dt.is_definition("bib:defn:x", {"bib:defn:x": "definition"}.get))

    def test_default_lookup_falls_back_to_the_label(self):
        # the module's workspace names a home that does not exist: no registry, label rule
        self.assertIsNone(dt.registry_kind("paper:defn:x"))
        self.assertIsNone(dt.registry_tags("paper:defn:x"))
        # without a registry no record carries the tag: a marked definition stays an input
        # (updated for #103: an input of both runs, proved-modulo, not the settler's)
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a, paper:defn:x (notation only)"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:a"))
        self.assertEqual((r["outcome"], r["modulo"]),
                         ("confirmed-modulo", ["paper:defn:x", "paper:lem:a"]))
        r = dt.decide(rec("CONFIRMED", modulo="paper:lem:a, paper:defn:x"),
                      rec("CONFIRMED", run="B", modulo="paper:lem:a"))
        self.assertEqual((r["outcome"], r["modulo"]),
                         ("confirmed-modulo", ["paper:defn:x", "paper:lem:a"]))

    def test_one_modulo_one_clean_goes_to_the_settler(self):
        r = dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B", modulo="paper:lem:b"))
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertEqual(r["modulo"], [])

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
        # T-0350: minTier none, else the tier floor (large -> Opus 5.5) adds Opus 5.5
        ws["grading"] = {"primaryModels": ["fable"], "minTier": "none"}
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


def rwrec(verdict="CONFIRMED", scope="equivalent", base_pass="2026-09-28-T-0007",
          base_hash="abc123", h="def456", modulo="none", model="claude-opus-5-5",
          run_id="rv-R", blocking="none", subject="paper:lem:x"):
    """A reword run's record (T-0347): mode reword, base pass and base hash."""
    text = ("Report.\n\nVERDICT\nsubject: %s\npass: 2026-10-12-T-0347-reword\nrun: R\n"
            "mode: reword\nbase_pass: %s\nbase_hash: %s\nverdict: %s\nreword_scope: %s\n"
            "modulo: %s\nmodel: %s\nstatement_hash: %s\nblocking: %s\nticket: T-0347\n"
            % (subject, base_pass, base_hash, verdict, scope, modulo, model, h, blocking))
    r = dt.parse_record(text)
    r["run_id"] = run_id
    r.setdefault("file", "reviews/paper/lem-x/2026-10-12-T-0347-reword/R.md")
    return r


class RewordTableTests(unittest.TestCase):
    """T-0347 (the human's decision, 2026-10-12): one informed reword run on top of a CONFIRMED x2 base."""

    def base(self, modulo="none", b="CONFIRMED"):
        return rec("CONFIRMED", modulo=modulo), rec(b, run="B", modulo=modulo)

    def test_parse_reword_fields(self):
        r = rwrec(scope="Covered")
        self.assertTrue(dt.is_reword(r))
        self.assertEqual((r["mode"], r["base_pass"], r["base_hash"], r["reword_scope"]),
                         ("reword", "2026-09-28-T-0007", "abc123", "covered"))
        self.assertFalse(dt.is_reword(rec("CONFIRMED")))
        self.assertEqual(rec("CONFIRMED")["mode"], "")

    def test_confirmed_on_a_confirmed_base_proposes_proved(self):
        a, b = self.base()
        r = dt.decide_reword(rwrec(), a, b)
        self.assertEqual(r["outcome"], "confirmed")
        self.assertEqual(r["proposed_status"], "proved")
        self.assertTrue(r["recolour"])
        self.assertFalse(r["launch_full_pass"])
        g = r["grounds"]
        self.assertEqual((g["mode"], g["base_hash"], g["statement_hash"], g["base_pass"]),
                         ("reword", "abc123", "def456", "2026-09-28-T-0007"))
        self.assertEqual([v["run_id"] for v in g["verdicts"]], ["rv-R", "rv-A", "rv-B"])
        self.assertEqual(g["verdicts"][0]["mode"], "reword")
        self.assertEqual(g["verdicts"][0]["reword_scope"], "equivalent")
        self.assertEqual([v["statement_hash"] for v in g["verdicts"]],
                         ["def456", "abc123", "abc123"])
        self.assertTrue(all(v["ref"] for v in g["verdicts"]))
        claims = ex.mcp_module("claims")
        ok, why = claims.check_grounds("proved", g, "def456")
        self.assertTrue(ok, why)
        self.assertFalse(claims.check_grounds("proved", g, "abc123")[0])
        self.assertIn("reword", dt._text(r))

    def test_decide_dispatches_on_a_reword_record(self):
        a, b = self.base()
        self.assertEqual(dt.decide(rwrec(), base=(a, b))["outcome"], "confirmed")
        # no base given: nothing to stand on
        r = dt.decide(rwrec())
        self.assertEqual(r["outcome"], "invalid-base")
        self.assertIsNone(r["proposed_status"])

    def test_weaker_and_covered_count_too(self):
        for scope in ("weaker", "covered"):
            a, b = self.base()
            self.assertEqual(dt.decide_reword(rwrec(scope=scope), a, b)["outcome"],
                             "confirmed", scope)

    def test_base_modulo_is_carried_and_the_reword_adds_its_own(self):
        a, b = self.base(modulo="paper:lem:a")
        r = dt.decide_reword(rwrec(), a, b)
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["modulo"], ["paper:lem:a"])
        self.assertFalse(r["recolour"])
        a, b = self.base(modulo="paper:lem:a")
        r = dt.decide_reword(rwrec(modulo="paper:lem:b"), a, b)
        self.assertEqual(r["modulo"], ["paper:lem:a", "paper:lem:b"])
        self.assertEqual(r["proposed_status"], "proved-modulo")
        self.assertEqual([i["kind"] for i in r["file_items"]], ["verify-input"] * 2)
        ok, why = ex.mcp_module("claims").check_grounds("proved-modulo", r["grounds"],
                                                         "def456")
        self.assertTrue(ok, why)
        a, b = self.base(modulo="paper:lem:a")
        r = dt.decide_reword(rwrec(), a, b, established=["paper:lem:a"])
        self.assertTrue(r["recolour"])

    def test_exceeds_without_a_gap_falls_back_to_a_full_blind_pass(self):
        # #147: the ruling names gaps only; CONFIRMED with scope exceeds keeps the blind pass
        a, b = self.base()
        r = dt.decide_reword(rwrec(scope="exceeds"), a, b)
        self.assertEqual(r["outcome"], "full-pass-needed")
        self.assertTrue(r["launch_full_pass"])
        self.assertIsNone(r["proposed_status"])
        self.assertFalse(r["recolour"])
        self.assertEqual(r["file_items"], [])
        self.assertIn("fresh blind", r["summary"])
        self.assertIn("next: open a fresh blind pass", dt._text(r))

    def test_a_reword_gap_is_repaired_then_reworded_against_the_same_base(self):
        """#147 (the human's ruling, 2026-11-28): a GAP in a reword review counts as a
        reword too, against the last verified statement: the blocking step goes to the
        producer as a repair (routed as a blind GAP's), and the next pass is a reword on
        the same base pass, never a fresh blind pass."""
        for kw in ({"verdict": "GAP", "scope": "exceeds",
                    "blocking": "the new wording drops compactness, which step 3 uses"},
                   {"verdict": "GAP", "scope": "none", "blocking": "step 3 needs x > 0"},
                   {"verdict": "GAP", "scope": "equivalent", "blocking": "step 3"}):
            with self.subTest(**kw):
                a, b = self.base()
                r = dt.decide_reword(rwrec(**kw), a, b)
                self.assertEqual(r["outcome"], "reword-gap")
                self.assertFalse(r["launch_full_pass"])
                self.assertFalse(r["launch_b"])
                self.assertIsNone(r["proposed_status"])
                self.assertFalse(r["recolour"])
                self.assertEqual(r["base_pass"], "2026-09-28-T-0007")
                self.assertEqual(r["reword_finding"], kw["blocking"])
                self.assertEqual([(i["kind"], i["run"], i["text"]) for i in r["file_items"]],
                                 [("repair", "R", kw["blocking"])])
                # routed exactly as the blind GAP's repair of the same finding
                blind = dt.decide(rec("GAP", blocking=kw["blocking"]))
                self.assertEqual(blind["outcome"], "single-negative")
                self.assertEqual(r["file_items"][0]["route"], blind["file_items"][0]["route"])
                self.assertEqual(r["file_items"][0]["gap_class"],
                                 blind["file_items"][0]["gap_class"])
                self.assertIn("2026-09-28-T-0007", r["summary"])
                self.assertIn("reword", r["summary"])
                self.assertNotIn("open a fresh blind", r["summary"])
                txt = dt._text(r)
                self.assertIn("next: after the repair, a reword pass against "
                              "2026-09-28-T-0007", txt)
                self.assertNotIn("next: open a fresh blind", txt)
        self.assertIn("compactness", dt.decide_reword(
            rwrec(verdict="GAP", blocking="drops compactness"), *self.base())["summary"])

    def test_a_reword_gap_repair_goes_to_the_producer(self):
        # the producer from producer_role_for (an override wins, as for a blind GAP); a lab
        # claim's repair goes through the Researcher to the Scientist
        a, b = self.base()
        r = dt.decide_reword(rwrec(verdict="GAP", blocking="rephrase: say 'of M'"), a, b,
                             producer_role="author")
        r2 = dt.decide(rec("GAP", blocking="rephrase: say 'of M'"), producer_role="author")
        self.assertEqual(r["file_items"][0]["route"], r2["file_items"][0]["route"])
        r = dt.decide_reword(rwrec(verdict="GAP", blocking="step 3"), a, b,
                             producer_role="scientist")
        self.assertEqual((r["file_items"][0]["route"]["to_role"],
                          r["file_items"][0]["route"]["final_to"]),
                         ("researcher", "scientist"))
        # with no blocking step the repair says where to look
        r = dt.decide_reword(rwrec(verdict="GAP"), a, b)
        self.assertEqual(r["outcome"], "reword-gap")
        self.assertEqual(len(r["file_items"]), 1)
        self.assertIn("report", r["file_items"][0]["text"])

    def test_a_reword_gap_through_the_cli(self):
        # decide() dispatches a reword record to the reword table: the same outcome
        a, b = self.base()
        r = dt.decide(rwrec(verdict="GAP", blocking="step 3"), None, base=(a, b))
        self.assertEqual((r["outcome"], r["launch_full_pass"]), ("reword-gap", False))
        self.assertEqual([i["kind"] for i in r["file_items"]], ["repair"])

    def test_disproved_goes_to_the_human(self):
        r = dt.decide_reword(rwrec(verdict="DISPROVED", blocking="the square torus"),
                             *self.base())
        self.assertEqual(r["outcome"], "disproved")
        self.assertTrue(r["needs_human"])
        self.assertIsNone(r["proposed_status"])
        self.assertEqual(r["file_items"][0]["route"]["to_role"], "human")

    def test_fallback_model_is_degraded(self):
        r = dt.decide_reword(rwrec(model="claude-sonnet-4-5"), *self.base())
        self.assertEqual(r["outcome"], "degraded")
        self.assertIsNone(r["proposed_status"])

    def test_confirmed_without_a_scope_is_incomplete(self):
        r = dt.decide_reword(rwrec(scope="none"), *self.base())
        self.assertEqual(r["outcome"], "incomplete")
        self.assertTrue(any("reword_scope" in x for x in r["anomalies"]))

    def test_base_anomalies(self):
        cases = {
            "missing": (rwrec(), None, None),
            "not confirmed": (rwrec(), *self.base(b="GAP")),
            "base_hash": (rwrec(base_hash="zzz999"), *self.base()),
            "did not change": (rwrec(h="abc123"), *self.base()),
            "subject": (rwrec(subject="paper:lem:y"), *self.base()),
            "run id": (rwrec(run_id="rv-A"), *self.base()),
        }
        for why, (r, a, b) in cases.items():
            with self.subTest(why=why):
                res = dt.decide_reword(r, a, b)
                self.assertEqual(res["outcome"], "invalid-base")
                self.assertIsNone(res["proposed_status"])
                self.assertTrue(any(why in x for x in res["anomalies"]), res["anomalies"])

    def test_a_reword_run_is_never_half_of_a_blind_pair(self):
        r = dt.decide(rec("CONFIRMED"), rwrec(h="abc123"))
        self.assertEqual(r["outcome"], "invalid-pair")
        self.assertTrue(any("reword" in x for x in r["anomalies"]))

    def test_every_new_outcome_is_known(self):
        for o in ("full-pass-needed", "invalid-base", "reword-gap"):
            self.assertIn(o, dt.OUTCOMES)

    def test_cli_finds_the_base_pass_beside_the_reword_pass(self):
        import shutil
        d = tempfile.mkdtemp()
        try:
            subj = os.path.join(d, "reviews", "paper", "lem-x")
            base = os.path.join(subj, "2026-09-28-T-0007")
            rw = os.path.join(subj, "2026-10-12-T-0347-reword")
            os.makedirs(base)
            os.makedirs(rw)
            for run in ("A", "B"):
                with open(os.path.join(base, run + ".md"), "w", encoding="utf-8") as fh:
                    fh.write("---\nsubject: paper:lem:x\npass: 2026-09-28-T-0007\nrun: %s\n"
                             "run_id: rv-%s\nverdict: CONFIRMED\nmodulo: []\n"
                             "model: claude-opus-5-5\nstatement_hash: abc123\n---\n\nr\n"
                             % (run, run))
            with open(os.path.join(base, "decision.md"), "w", encoding="utf-8") as fh:
                fh.write("# decided\n")
            rpath = os.path.join(rw, "R.md")
            with open(rpath, "w", encoding="utf-8") as fh:
                fh.write("---\nsubject: paper:lem:x\npass: 2026-10-12-T-0347-reword\n"
                         "run: R\nrun_id: rv-R\nverdict: CONFIRMED\nmodulo: []\n"
                         "model: claude-opus-5-5\nstatement_hash: def456\nmode: reword\n"
                         "base_pass: 2026-09-28-T-0007\nbase_hash: abc123\n"
                         "reword_scope: weaker\n---\n\nr\n")
            code, out, err = fixtures.run_script("decision_table.py", None, [rpath, "--json"])
            self.assertEqual(code, 0, err)
            self.assertEqual(out["outcome"], "confirmed", out)
            self.assertTrue(out["grounds"]["verdicts"][1]["ref"].endswith("A.md"))
            # an abandoned base pass is no base
            with open(os.path.join(base, "abandoned.md"), "w", encoding="utf-8") as fh:
                fh.write("dead\n")
            code, out, err = fixtures.run_script("decision_table.py", None, [rpath, "--json"])
            self.assertEqual(out["outcome"], "invalid-base", out)
            # --base-dir overrides the lookup
            code, out, err = fixtures.run_script("decision_table.py", None,
                                                 [rpath, "--base-dir", rw, "--json"])
            self.assertEqual(out["outcome"], "invalid-base", out)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class RewordChainTests(unittest.TestCase):
    """#127 (the human's ruling, 2026-11-27: "rewording in general should have the
    previous confirmed statement as reference"): a reword on a confirmed reword pass."""

    P1, P2, P3 = "2026-10-12-T-0347-reword", "2026-10-20-T-0400-reword", \
        "2026-10-25-T-0500-reword"

    def link(self, rec_r, pass_, base):
        """``rec_r`` as the base reword pass ``pass_``'s run R, standing on ``base``."""
        r = dict(rec_r)
        r["pass"] = pass_
        r["file"] = "reviews/paper/lem-x/%s/R.md" % pass_
        r["_base"] = base
        return r

    def chain2(self, r1_kw=None, modulo="none"):
        a, b = rec("CONFIRMED", modulo=modulo), rec("CONFIRMED", run="B", modulo=modulo)
        return self.link(rwrec(**(r1_kw or {})), self.P1, (a, b, []))

    def test_a_reword_on_a_confirmed_reword_pass(self):
        r1 = self.chain2()
        r2 = rwrec(base_pass=self.P1, base_hash="def456", h="ghi789", run_id="rv-R2")
        r = dt.decide(r2, base=(r1, None))
        self.assertEqual((r["outcome"], r["proposed_status"]), ("confirmed", "proved"))
        self.assertEqual(r["chain"], ["2026-09-28-T-0007", self.P1])
        self.assertEqual((r["root_pass"], r["root_hash"]), ("2026-09-28-T-0007", "abc123"))
        g = r["grounds"]
        self.assertEqual([v["run_id"] for v in g["verdicts"]], ["rv-R2", "rv-R", "rv-A", "rv-B"])
        self.assertEqual([(v.get("mode"), v.get("base_hash"), v.get("base_pass"))
                          for v in g["verdicts"][:2]],
                         [("reword", "def456", self.P1),
                          ("reword", "abc123", "2026-09-28-T-0007")])
        self.assertEqual((g["base_hash"], g["root_hash"], g["chain"]),
                         ("def456", "abc123", ["2026-09-28-T-0007", self.P1]))
        claims = ex.mcp_module("claims")
        ok, why = claims.check_grounds("proved", g, "ghi789")
        self.assertTrue(ok, why)
        self.assertFalse(claims.check_grounds("proved", g, "def456")[0])
        self.assertIn("chain", dt._text(r))

    def test_a_three_link_chain_carries_every_modulo(self):
        r1 = self.chain2(r1_kw={"modulo": "paper:lem:b"}, modulo="paper:lem:a")
        r2 = self.link(rwrec(base_pass=self.P1, base_hash="def456", h="ghi789",
                             run_id="rv-R2"), self.P2, (r1, None, []))
        r3 = rwrec(base_pass=self.P2, base_hash="ghi789", h="jkl012", run_id="rv-R3",
                   modulo="paper:lem:c")
        r = dt.decide(r3, base=(r2, None))
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["modulo"], ["paper:lem:a", "paper:lem:b", "paper:lem:c"])
        self.assertEqual(r["chain"], ["2026-09-28-T-0007", self.P1, self.P2])
        self.assertEqual([v["run_id"] for v in r["grounds"]["verdicts"]],
                         ["rv-R3", "rv-R2", "rv-R", "rv-A", "rv-B"])
        ok, why = ex.mcp_module("claims").check_grounds("proved-modulo", r["grounds"],
                                                         "jkl012")
        self.assertTrue(ok, why)

    def test_a_broken_link_carries_nothing(self):
        ok_r2 = dict(base_pass=self.P1, base_hash="def456", h="ghi789", run_id="rv-R2")
        cases = {
            # compared against the root's wording, not the one the link confirmed
            "base_hash abc123 is not": (rwrec(**dict(ok_r2, base_hash="abc123")),
                                        self.chain2()),
            "not confirmed": (rwrec(**ok_r2), self.chain2({"verdict": "GAP",
                                                           "blocking": "step 2"})),
            "exceeds": (rwrec(**ok_r2), self.chain2({"scope": "exceeds"})),
            "own base": (rwrec(**ok_r2), self.link(rwrec(), self.P1, None)),
            "root base": (rwrec(**ok_r2),
                          self.link(rwrec(), self.P1, (rec("CONFIRMED"),
                                                       rec("GAP", run="B"), []))),
            "run id": (rwrec(**dict(ok_r2, run_id="rv-A")), self.chain2()),
            "belongs to pass": (rwrec(**dict(ok_r2, base_pass=self.P2)), self.chain2()),
        }
        for why, (r2, r1) in cases.items():
            with self.subTest(why=why):
                res = dt.decide(r2, base=(r1, None))
                self.assertIn(res["outcome"], ("invalid-base",), res["anomalies"])
                self.assertIsNone(res["proposed_status"])
                self.assertIsNone(res["grounds"])

    def test_a_named_root_must_be_the_chains(self):
        r2 = rwrec(base_pass=self.P1, base_hash="def456", h="ghi789", run_id="rv-R2")
        r2["root_pass"] = "2026-09-01-T-0001"
        res = dt.decide(r2, base=(self.chain2(), None))
        self.assertEqual(res["outcome"], "invalid-base")
        self.assertTrue(any("root_pass" in x for x in res["anomalies"]), res["anomalies"])
        r2["root_pass"], r2["root_hash"] = "2026-09-28-T-0007", "abc123"
        self.assertEqual(dt.decide(r2, base=(self.chain2(), None))["outcome"], "confirmed")

    def test_a_reword_record_beside_a_blind_run_is_still_no_base(self):
        # a misfiled reword record as the base pass's A, with a blind B: not a link
        res = dt.decide(rwrec(run_id="rv-R2", base_hash="def456", h="ghi789"),
                        base=(rwrec(), rec("CONFIRMED", run="B")))
        self.assertEqual(res["outcome"], "invalid-base")

    def test_base_records_follow_the_chain_on_disk(self):
        import shutil
        d = tempfile.mkdtemp()
        try:
            subj = os.path.join(d, "reviews", "paper", "lem-x")

            def put(pass_, name, text):
                os.makedirs(os.path.join(subj, pass_), exist_ok=True)
                p = os.path.join(subj, pass_, name)
                with open(p, "w", encoding="utf-8") as fh:
                    fh.write(text)
                return p
            for run in ("A", "B"):
                put("2026-09-28-T-0007", run + ".md",
                    "---\nsubject: paper:lem:x\npass: 2026-09-28-T-0007\nrun: %s\n"
                    "run_id: rv-%s\nverdict: CONFIRMED\nmodulo: []\nmodel: claude-opus-5-5\n"
                    "statement_hash: abc123\n---\n\nr\n" % (run, run))
            rw = ("---\nsubject: paper:lem:x\npass: {p}\nrun: R\nrun_id: {rid}\n"
                  "verdict: CONFIRMED\nmodulo: []\nmodel: claude-opus-5-5\n"
                  "statement_hash: {h}\nmode: reword\nbase_pass: {bp}\nbase_hash: {bh}\n"
                  "reword_scope: weaker\n---\n\nr\n")
            put(self.P1, "R.md", rw.format(p=self.P1, rid="rv-R1", h="def456",
                                           bp="2026-09-28-T-0007", bh="abc123"))
            put(self.P2, "R.md", rw.format(p=self.P2, rid="rv-R2", h="ghi789",
                                           bp=self.P1, bh="def456"))
            r3 = put(self.P3, "R.md", rw.format(p=self.P3, rid="rv-R3", h="jkl012",
                                                bp=self.P2, bh="ghi789"))
            code, out, err = fixtures.run_script("decision_table.py", None, [r3, "--json"])
            self.assertEqual(code, 0, err)
            self.assertEqual(out["outcome"], "confirmed", out)
            self.assertEqual(out["chain"], ["2026-09-28-T-0007", self.P1, self.P2])
            # a loop: the first link names the last as its base
            put(self.P1, "R.md", rw.format(p=self.P1, rid="rv-R1", h="def456",
                                           bp=self.P2, bh="ghi789"))
            code, out, err = fixtures.run_script("decision_table.py", None, [r3, "--json"])
            self.assertEqual(out["outcome"], "invalid-base", out)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class EstablishedAtConcludeTests(unittest.TestCase):
    """#133: a reword pass carried the base pass's modulo over, so a proposal named an
    input that the registry already showed proved (four proposals on one day, three of
    them lowering a proved claim). The table now reads the registry at conclude time
    (``established_of``; the CLI's ``registry_established``) and drops what is
    established now; R proposes proved when nothing remains."""

    P1 = RewordChainTests.P1

    def base(self, modulo):
        return rec("CONFIRMED", modulo=modulo), rec("CONFIRMED", run="B", modulo=modulo)

    def est(self, *proved):
        seen = []

        def of(items, subject):
            seen.append((list(items), subject))
            return {i: {"id": i, "status": "proved", "why": ""} for i in items if i in proved}
        of.seen = seen
        return of

    def check_proved(self, r):
        self.assertEqual((r["outcome"], r["proposed_status"], r["modulo"]),
                         ("confirmed", "proved", []))
        self.assertTrue(r["recolour"])
        self.assertNotIn("modulo", r["grounds"])
        ok, why = ex.mcp_module("claims").check_grounds("proved", r["grounds"], r["grounds"]
                                                         ["statement_hash"])
        self.assertTrue(ok, why)

    def test_carried_base_input_proved_now_proposes_proved(self):
        # shape 1: the blind base pass said modulo X; X has been proved since
        of = self.est("paper:prop:compact-conical-finite")
        r = dt.decide(rwrec(), base=self.base("paper:prop:compact-conical-finite"),
                      established_of=of)
        self.check_proved(r)
        self.assertEqual(r["established_dropped"], ["paper:prop:compact-conical-finite"])
        self.assertEqual([i["input"] for i in r["established_inputs"]],
                         ["paper:prop:compact-conical-finite"])
        self.assertIn("paper:prop:compact-conical-finite", of.seen[0][0])
        self.assertEqual(of.seen[0][1], "paper:lem:x")
        self.assertIn("dropped from the carried modulo", dt._text(r))

    def test_unqualified_input_is_read_canonically(self):
        # shape 2: the base runs wrote the label without its namespace
        of = self.est("paper:fact:unfolding-properties")
        r = dt.decide(rwrec(), base=self.base("fact:unfolding-properties"),
                      established_of=of)
        self.check_proved(r)

    def test_input_carried_down_a_reword_chain(self):
        # shape 3: the input sits in the blind root's modulo under a confirmed reword link
        a, b = self.base("paper:lem:dihedral-structure-group")
        r1 = dict(rwrec(), **{"pass": self.P1,
                              "file": "reviews/paper/lem-x/%s/R.md" % self.P1,
                              "_base": (a, b, [])})
        r2 = rwrec(base_pass=self.P1, base_hash="def456", h="ghi789", run_id="rv-R2")
        r = dt.decide(r2, base=(r1, None),
                      established_of=self.est("paper:lem:dihedral-structure-group"))
        self.check_proved(r)
        self.assertEqual(len(r["chain"]), 2)

    def test_input_named_by_the_reword_run_itself(self):
        # shape 4: R lists the input (proved on the human's word); the base had none
        r = dt.decide(rwrec(modulo="paper:lem:polar-decomposition"), base=self.base("none"),
                      established_of=self.est("paper:lem:polar-decomposition"))
        self.check_proved(r)

    def test_only_the_open_inputs_stay(self):
        r = dt.decide(rwrec(), base=self.base("paper:lem:a, paper:lem:b"),
                      established_of=self.est("paper:lem:a"))
        self.assertEqual((r["outcome"], r["proposed_status"], r["modulo"]),
                         ("confirmed-modulo", "proved-modulo", ["paper:lem:b"]))
        self.assertEqual(r["grounds"]["modulo"], ["paper:lem:b"])
        self.assertEqual(r["established_dropped"], ["paper:lem:a"])
        self.assertEqual(r["pending_inputs"], ["paper:lem:b"])

    def test_nothing_established_keeps_the_carried_modulo(self):
        r = dt.decide(rwrec(), base=self.base("paper:lem:a"), established_of=self.est())
        self.assertEqual((r["outcome"], r["modulo"]), ("confirmed-modulo", ["paper:lem:a"]))
        # an unreadable registry (the hook raising) is the same as nothing established
        def boom(items, subject):
            raise OSError("no registry")
        r = dt.decide(rwrec(), base=self.base("paper:lem:a"), established_of=boom)
        self.assertEqual(r["modulo"], ["paper:lem:a"])

    def test_the_established_option_drops_too(self):
        r = dt.decide(rwrec(), base=self.base("paper:lem:a"), established=["lem:a"])
        self.check_proved(r)

    def test_amend_reads_the_registry_too(self):
        a = rec("CONFIRMED", modulo="paper:lem:a")
        a["add_dependency"] = ["paper:lem:d"]
        b = rec("CONFIRMED", run="B", modulo="paper:lem:a")
        b.update(mode="amend", base_pass=a.get("pass"), base_hash="abc123",
                 amended_with=["paper:lem:d"], add_dependency=[])
        r = dt.decide(a, b, established_of=self.est("paper:lem:a", "paper:lem:d"))
        self.assertEqual((r["mode"], r["outcome"], r["proposed_status"]),
                         ("amend", "confirmed", "proved"))
        r = dt.decide(a, b, established_of=self.est("paper:lem:a"))
        self.assertEqual((r["outcome"], r["pending_inputs"]),
                         ("confirmed-modulo", ["paper:lem:d"]))


class RegistryEstablishedTests(unittest.TestCase):
    """#133: ``registry_established`` reads the discharge's rule from a real registry."""

    LAB = ("---\nid: lab:{id}\nkind: claim\ntitle: t {id}\nstatus: {status}\n"
           "lifecycle: active\nevidence:\n  - verdict | reviews/{id}/A.md | CONFIRMED | "
           "rv-a-{id} | grader rigor-reviewer\n  - verdict | reviews/{id}/B.md | CONFIRMED"
           " | rv-b-{id} | grader rigor-reviewer\nhistory:\n  - 2026-11-20 | {status} | "
           "proof review\n---\nBody {id}.\n")

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        lab = os.path.join(self.tmp, "LabHome")
        os.makedirs(os.path.join(lab, "claims", "lab"))
        for cid, st in (("in-a", "proved"), ("in-b", "sketch"), ("in-c", "proved-modulo")):
            with open(os.path.join(lab, "claims", "lab", cid + ".md"), "w",
                      encoding="utf-8") as fh:
                fh.write(self.LAB.format(id=cid, status=st))
        ws = os.path.join(self.tmp, "workspace.json")
        with open(ws, "w", encoding="utf-8") as fh:
            json.dump({"board": os.path.join(self.tmp, "board"), "instances": {
                "scientist@t": {"role": "scientist", "home": lab, "ns": "lab"}}}, fh)
        from unittest import mock
        p = mock.patch.dict(os.environ, {"ACADEMY_WORKSPACE": ws})
        p.start()
        self.addCleanup(p.stop)
        self._clear()
        self.addCleanup(self._clear)

    def _clear(self):
        try:
            import registry
            registry.clear_cache()
        except Exception:  # noqa: BLE001
            pass

    def test_only_proved_inputs_are_established(self):
        got = dt.registry_established(["lab:in-a", "lab:in-b", "lab:in-c", "free text"],
                                      "lab:x")
        self.assertEqual(sorted(got), ["lab:in-a"])
        self.assertEqual(got["lab:in-a"]["status"], "proved")

    def test_unknown_namespace_reads_nothing(self):
        self.assertEqual(dt.registry_established(["zz:a"], "zz:x"), {})


class RewordBaseSubjectTests(unittest.TestCase):
    """T-0476: a reword run on a renamed record names the base pass's subject
    (``base_subject``, the superseded id) and the table reads the base there."""

    OLD_ID, NEW_ID = "paper:lem:x", "paper:cor:x"

    def rw(self, **kw):
        kw.setdefault("subject", self.NEW_ID)
        r = rwrec(**kw)
        r["base_subject"] = self.OLD_ID
        return r

    def base(self, subject=None):
        return (rec("CONFIRMED", subject=subject or self.OLD_ID),
                rec("CONFIRMED", run="B", subject=subject or self.OLD_ID))

    def test_parse_keeps_base_subject(self):
        text = ("VERDICT\nsubject: paper:cor:x\npass: 2026-10-17-T-0476-reword\nrun: R\n"
                "mode: reword\nbase_pass: 2026-09-28-T-0007\nbase_hash: abc123\n"
                "base_subject: paper:lem:x\nverdict: CONFIRMED\nreword_scope: equivalent\n"
                "model: claude-opus-5-5\nstatement_hash: def456\n")
        self.assertEqual(dt.parse_record(text)["base_subject"], "paper:lem:x")
        self.assertIn("base_subject", dt.REWORD_FIELDS)

    def test_confirmed_and_grounds_carry_base_subject(self):
        r = dt.decide_reword(self.rw(), *self.base())
        self.assertEqual(r["outcome"], "confirmed", r["anomalies"])
        self.assertEqual(r["base_subject"], self.OLD_ID)
        g = r["grounds"]
        self.assertEqual(g["base_subject"], self.OLD_ID)
        self.assertEqual([v.get("base_subject") for v in g["verdicts"]], [self.OLD_ID] * 3)
        ok, why = ex.mcp_module("claims").check_grounds("proved", g, "def456")
        self.assertTrue(ok, why)
        self.assertIn("base_subject %s" % self.OLD_ID, dt._text(r))

    def test_base_of_another_subject_without_base_subject_is_invalid(self):
        r = rwrec(subject=self.NEW_ID)
        res = dt.decide_reword(r, *self.base())
        self.assertEqual(res["outcome"], "invalid-base")
        self.assertTrue(any("subject" in a for a in res["anomalies"]), res["anomalies"])

    def test_base_records_must_be_about_base_subject(self):
        res = dt.decide_reword(self.rw(), *self.base(subject="paper:lem:other"))
        self.assertEqual(res["outcome"], "invalid-base")
        self.assertTrue(any("base_subject" in a for a in res["anomalies"]),
                        res["anomalies"])
        # nor about the new id: base_subject says where the base was reviewed
        res = dt.decide_reword(self.rw(), *self.base(subject=self.NEW_ID))
        self.assertEqual(res["outcome"], "invalid-base")

    def test_hash_and_run_id_checks_still_apply(self):
        for kw in ({"base_hash": "zzz999"}, {"h": "abc123"}, {"run_id": "rv-A"}):
            with self.subTest(**kw):
                res = dt.decide_reword(self.rw(**kw), *self.base())
                self.assertEqual(res["outcome"], "invalid-base")

    def test_base_records_resolves_under_base_subject(self):
        import shutil
        d = tempfile.mkdtemp()
        try:
            root = os.path.join(d, "reviews", "paper")
            base = os.path.join(root, "lem-x", "2026-09-28-T-0007")
            rw = os.path.join(root, "cor-x", "2026-10-17-T-0476-reword")
            os.makedirs(base)
            os.makedirs(rw)
            for run in ("A", "B"):
                with open(os.path.join(base, run + ".md"), "w", encoding="utf-8") as fh:
                    fh.write("---\nsubject: paper:lem:x\npass: 2026-09-28-T-0007\nrun: %s\n"
                             "run_id: rv-%s\nverdict: CONFIRMED\nmodulo: []\n"
                             "model: claude-opus-5-5\nstatement_hash: abc123\n---\n\nr\n"
                             % (run, run))
            with open(os.path.join(base, "decision.md"), "w", encoding="utf-8") as fh:
                fh.write("# decided\n")
            rpath = os.path.join(rw, "R.md")
            with open(rpath, "w", encoding="utf-8") as fh:
                fh.write("---\nsubject: paper:cor:x\npass: 2026-10-17-T-0476-reword\n"
                         "run: R\nrun_id: rv-R\nverdict: CONFIRMED\nmodulo: []\n"
                         "model: claude-opus-5-5\nstatement_hash: def456\nmode: reword\n"
                         "base_pass: 2026-09-28-T-0007\nbase_hash: abc123\n"
                         "base_subject: paper:lem:x\nreword_scope: equivalent\n---\n\nr\n")
            a, b, notes = dt.base_records(rpath, "2026-09-28-T-0007",
                                          base_subject="paper:lem:x")
            self.assertEqual((a["run"], b["run"], notes), ("A", "B", []))
            code, out, err = fixtures.run_script("decision_table.py", None, [rpath, "--json"])
            self.assertEqual(code, 0, err)
            self.assertEqual(out["outcome"], "confirmed", out)
            self.assertEqual(out["base_subject"], "paper:lem:x")
            self.assertEqual(out["grounds"]["base_subject"], "paper:lem:x")
            self.assertIn("lem-x", out["grounds"]["verdicts"][1]["ref"].replace("\\", "/"))
            # without base_subject the sibling folder under cor-x is looked up: missing
            with open(rpath, encoding="utf-8") as fh:
                t = fh.read()
            with open(rpath, "w", encoding="utf-8") as fh:
                fh.write(t.replace("base_subject: paper:lem:x\n", ""))
            code, out, err = fixtures.run_script("decision_table.py", None, [rpath, "--json"])
            self.assertEqual(out["outcome"], "invalid-base", out)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    # --- test-engineer review of T-0476 ---------------------------------------------

    def _tree(self, d, base_subject_line):
        """reviews/paper/{lem-x,cor-x}/..., and a look-alike base pass OUTSIDE reviews/
        (``d/x/<pass>/``) that a namespace of ``..`` would reach."""
        bp = "2026-09-28-T-0007"
        rec = ("---\nsubject: paper:lem:x\npass: %s\nrun: %s\nrun_id: rv-%s\n"
               "verdict: CONFIRMED\nmodulo: []\nmodel: claude-opus-5-5\n"
               "statement_hash: abc123\n---\n\nr\n")
        for sub in (("reviews", "paper", "lem-x", bp), ("x", bp)):
            os.makedirs(os.path.join(d, *sub))
            for run in ("A", "B"):
                with open(os.path.join(d, *sub, run + ".md"), "w", encoding="utf-8") as fh:
                    fh.write(rec % (bp, run, run))
        rw = os.path.join(d, "reviews", "paper", "cor-x", "2026-10-17-T-0476-reword")
        os.makedirs(rw)
        rpath = os.path.join(rw, "R.md")
        with open(rpath, "w", encoding="utf-8") as fh:
            fh.write("---\nsubject: paper:cor:x\nrun: R\nrun_id: rv-R\n"
                     "verdict: CONFIRMED\nstatement_hash: def456\nmode: reword\n"
                     "base_pass: %s\nbase_hash: abc123\n%sreword_scope: equivalent\n"
                     "---\n\nr\n" % (bp, base_subject_line))
        return rpath, bp

    def test_base_records_follow_only_a_well_formed_namespace(self):
        import shutil
        d = tempfile.mkdtemp()
        try:
            rpath, bp = self._tree(d, "")
            for bad in ("lem-x", ":x", "paper:"):
                with self.subTest(base_subject=bad):
                    a, b, notes = dt.base_records(rpath, bp, base_subject=bad)
                    self.assertEqual((a, b), (None, None))
                    self.assertIn("namespaced", " ".join(notes))
            a, b, notes = dt.base_records(rpath, bp, base_subject="paper:lem:x")
            self.assertEqual((a["run"], b["run"]), ("A", "B"), notes)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_base_records_do_not_leave_the_reviews_root(self):
        import shutil
        d = tempfile.mkdtemp()
        try:
            rpath, bp = self._tree(d, "")
            a, b, notes = dt.base_records(rpath, bp, base_subject="..:x")
            self.assertIsNone(a, "read a base pass from outside reviews/")
        finally:
            shutil.rmtree(d, ignore_errors=True)


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


class MissingVerdictTests(unittest.TestCase):
    """A verdict that is not there says what to check (the ledger: five bare
    '[Errno 2] No such file' in five weeks)."""

    def run_cli(self, *argv):
        import contextlib
        import io
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = dt.main(list(argv))
        return rc, err.getvalue()

    def test_a_missing_folder_and_a_run_not_landed(self):
        with tempfile.TemporaryDirectory() as d:
            rc, err = self.run_cli(os.path.join(d, "no-pass", "A.md"))
            self.assertEqual(2, rc)
            self.assertIn("run A's verdict is not at", err)
            self.assertIn("does not exist", err)
            self.assertIn("reviews.py dir", err)
            self.assertNotIn("Errno", err)
            os.makedirs(os.path.join(d, "pass"))
            with open(os.path.join(d, "pass", "brief.md"), "w", encoding="utf-8") as fh:
                fh.write("x")
            rc, err = self.run_cli(os.path.join(d, "pass", "A.md"))
            self.assertEqual(2, rc)
            self.assertIn("the pass folder holds brief.md", err)
            self.assertIn("land_verdict", err)
            self.assertIn("Nothing to decide yet.", err)


class ModuloNormalisationTests(unittest.TestCase):
    """#103: two CONFIRMED runs that name one input two ways agree."""

    ALIASES = {"paper:lem:lifting": "paper:lem:lift-covers",
               "paper:lem:lift-covers": "paper:lem:lift-covers"}

    def canon(self, qid):
        return self.ALIASES.get(qid)

    def decide(self, ma, mb):
        return dt.decide(rec("CONFIRMED", "A", modulo=ma), rec("CONFIRMED", "B", modulo=mb),
                         kind_of=lambda q: None, canon=self.canon)

    def test_namespace_prefix_is_not_a_difference(self):
        res = self.decide("paper:lem:y", "lem:y")
        self.assertEqual(res["outcome"], "confirmed-modulo")
        self.assertEqual(res["modulo"], ["paper:lem:y"])

    def test_an_alias_resolves_to_its_record(self):
        res = self.decide("paper:lem:lifting", "lem:lift-covers")
        self.assertEqual(res["outcome"], "confirmed-modulo")
        self.assertEqual(res["modulo"], ["paper:lem:lift-covers"])

    def test_a_pointer_text_with_commas_is_one_input_and_is_kept(self):
        r = rec("CONFIRMED", "A", modulo="lem:y (the lifting lemma, for covers), bib:LMW16")
        self.assertEqual(r["modulo"], ["lem:y (the lifting lemma, for covers)", "bib:LMW16"])
        res = self.decide("lem:y (first clause only), bib:LMW16", "bib:LMW16; paper:lem:y")
        # the pointer may restrict it: two inputs, for the settler (#121), never merged here
        self.assertEqual(res["outcome"], "settle-dependencies")
        self.assertEqual([d["input"] for d in res["differing_inputs"]],
                         ["lem:y (first clause only)", "paper:lem:y"])

    def test_review_of_96a9cab_false_agreements(self):
        # pointer text and bracketed pinpoints are not dropped
        res = self.decide("bib:LMW16 [Thm 11]", "bib:LMW16 [Thm 12]")
        self.assertEqual(res["outcome"], "settle-dependencies")
        self.assertEqual([d["input"] for d in res["differing_inputs"]],
                         ["bib:LMW16 [Thm 11]", "bib:LMW16 [Thm 12]"])
        # (#121: two inputs differently pinpointed stay two, for the settler, never one)
        res = self.decide("flat:MOD-1#(I0) charts", "flat:MOD-1#(I1) charts")
        self.assertEqual(res["outcome"], "settle-dependencies")
        self.assertEqual([d["input"] for d in res["differing_inputs"]],
                         ["flat:MOD-1#(I0) charts", "flat:MOD-1#(I1) charts"])
        self.assertEqual(dt.canon_input("check:T-1033#Fix(j_Y)", "paper:lem:x", lambda q: None),
                         "check:T-1033#Fix(j_Y)")
        # an unclosed bracket does not swallow the inputs after it
        self.assertEqual(dt._split_list("paper:lem:x2 [1, paper:lem:p, paper:lem:q"),
                         ["paper:lem:x2 [1", "paper:lem:p", "paper:lem:q"])
        self.assertEqual(dt._split_list(["paper:lem:a (see", "paper:lem:b"]),
                         ["paper:lem:a (see", "paper:lem:b"])
        # free text after a pinpoint keeps its ticket numbers
        self.assertEqual(dt._norm_pinpoint("Thm 2.6 (T-1144)"), "Thm2.6 (T-1144)")
        self.assertEqual(dt._norm_pinpoint("§ 2.2, p. 8"), "§2.2, p8")

    def test_a_label_is_qualified_only_for_an_author_subject_or_a_known_record(self):
        none = lambda q: None  # noqa: E731
        self.assertEqual(dt.canon_input("lem:y", "s1:GEO-1", none), "lem:y")
        self.assertEqual(dt.canon_input("lem:y", "s1:GEO-1", {"s1:lem:y": "s1:lem:y"}.get),
                         "s1:lem:y")

    def test_registry_canonical_takes_exact_ids_and_registered_aliases_only(self):
        class Store:
            records = {"CRIT-3": object()}
            def lookup(self, name):
                return ("CRIT-3", name == "CRIT-3") if name.upper().startswith("CRIT-3") \
                    or name in ("R2-4.7",) else (None, False)
            def aliases(self, rid):
                return ["R2-4.7"]
        import unittest.mock as um
        from registry.core import federation, workspace as rws
        with um.patch.object(rws, "namespaces", return_value={"s1": {"home": os.getcwd()}}), \
                um.patch.object(federation, "store", return_value=Store()):
            self.assertEqual(dt.registry_canonical("s1:CRIT-3"), "s1:CRIT-3")
            self.assertEqual(dt.registry_canonical("s1:R2-4.7"), "s1:CRIT-3")
            self.assertIsNone(dt.registry_canonical("s1:CRIT-3a"))
            self.assertIsNone(dt.registry_canonical("s1:crit-3"))

    def test_other_namespaces_and_free_text_are_kept(self):
        none = lambda q: None  # noqa: E731
        self.assertEqual(dt.canon_input("s1:OBS-3", "paper:lem:x", none), "s1:OBS-3")
        self.assertEqual(dt.canon_input("check:T-1033#a", "paper:lem:x", none),
                         "check:T-1033#a")
        self.assertEqual(dt.canon_input("the  standard setting", "paper:lem:x", none),
                         "the standard setting")
        self.assertEqual(dt.canon_input("`bib:LMW16`", "paper:lem:x", none), "bib:LMW16")

    def test_a_bare_notebook_id_is_qualified_only_when_the_registry_knows_it(self):
        known = {"s1:OBS-3": "s1:OBS-3"}.get
        self.assertEqual(dt.canon_input("OBS-3", "s1:GEO-1", known), "s1:OBS-3")
        self.assertEqual(dt.canon_input("LMW16", "s1:GEO-1", known), "LMW16")

    def test_a_real_difference_offers_union_and_intersection(self):
        # only a disagreement that remains (a CONFIRMED run naming a blocking step) asks
        res = dt.decide(rec("CONFIRMED", "A", modulo="lem:y, lem:z", blocking="step 4 is thin"),
                        rec("CONFIRMED", "B", modulo="paper:lem:y"),
                        kind_of=lambda q: None, canon=self.canon)
        self.assertEqual(res["outcome"], "disagreement")
        opts = {o["label"]: o["modulo"] for o in res["modulo_options"]}
        self.assertEqual(opts["union"], ["paper:lem:y", "paper:lem:z"])
        self.assertEqual(opts["intersection"], ["paper:lem:y"])
        self.assertIn("option union", dt._text(res))

    def test_a_list_landed_split_inside_brackets_is_rejoined(self):
        self.assertEqual(dt._split_list(["lem:y (uncited", "T-0508)", "bib:X"]),
                         ["lem:y (uncited, T-0508)", "bib:X"])

    def test_pinpoint_punctuation_is_not_a_difference(self):
        res = self.decide("bib:Mo06#Thm2.6, lem:z#item4", "bib:Mo06#Thm 2.6; paper:lem:z#item-4")
        self.assertEqual(res["outcome"], "confirmed-modulo")
        self.assertEqual(res["modulo"], ["bib:Mo06#Thm2.6", "paper:lem:z#item4"])

    def test_established_is_normalised_too(self):
        res = dt.decide(rec("CONFIRMED", "A", modulo="lem:y"),
                        rec("CONFIRMED", "B", modulo="paper:lem:y"),
                        established=["lem:y"], kind_of=lambda q: None, canon=self.canon)
        self.assertEqual(res["pending_inputs"], [])
        self.assertTrue(res["recolour"])



class DifferingInputsTests(unittest.TestCase):
    """#121 (the human's decision of 2026-11-20): two CONFIRMED runs with no blocking step
    whose modulo lists differ are not a union and not a ruling. The script reduces what is
    mechanical (stage 1 of the fixed order: #103 spelling, notation-only definitions, an
    input a shared or declared input reaches through the registry, a carried modulo of a
    shared input); a difference that remains is ``settle-dependencies``, each differing
    input with the admissibility facts the dependency-settler needs."""

    # the subject paper:lem:x declares paper:lem:a, paper:lem:b, paper:lem:y (depends_on),
    # paper:lem:m (modulo) and cites Mo06; paper:lem:y rests on paper:lem:x2, which rests
    # on paper:lem:w and cites SW08; flat:PER-2 cites AW21 and is proved-modulo flat:PER-9;
    # paper:lem:c1 and c2 rest on each other; paper:lem:z rests on the subject, and
    # paper:lem:z2 is proved-modulo paper:lem:z
    LINKS = {"paper:lem:x": {"depends_on": ["paper:lem:a", "paper:lem:b", "paper:lem:y"],
                             "modulo": ["paper:lem:m"], "cites": ["Mo06"]},
             "paper:lem:y": {"depends_on": ["paper:lem:x2"], "cites": []},
             "paper:lem:x2": {"depends_on": ["paper:lem:w"], "cites": ["SW08"]},
             "paper:lem:w": {"depends_on": [], "cites": []},
             "flat:PER-2": {"depends_on": [], "modulo": ["flat:PER-9"], "cites": ["AW21"]},
             "flat:PER-9": {"depends_on": ["flat:PER-10"], "cites": []},
             "paper:lem:c1": {"depends_on": ["paper:lem:c2"], "cites": []},
             "paper:lem:c2": {"depends_on": ["paper:lem:c1"], "cites": []},
             "paper:lem:z": {"depends_on": ["paper:lem:x"], "cites": []},
             "paper:lem:z2": {"depends_on": [], "modulo": ["paper:lem:z"], "cites": []}}

    def decide(self, ma, mb, links=True, established=(), ba="none", bb="none", vb="CONFIRMED",
               exists=None):
        return dt.decide(rec("CONFIRMED", "A", modulo=ma, blocking=ba),
                         rec(vb, "B", modulo=mb, blocking=bb), established=established,
                         kind_of=lambda q: None, canon=lambda q: None, exists=exists,
                         tags_of=lambda q: None,
                         links_of=self.LINKS.get if links else None)

    def facts(self, r):
        return {d["input"]: d for d in r["differing_inputs"]}

    def test_a_remaining_difference_is_settle_dependencies(self):
        r = self.decide("paper:lem:a, bib:LMW16#Thm11", "paper:lem:a, paper:lem:b")
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertIn(r["outcome"], dt.OUTCOMES)
        self.assertNotIn("confirmed-union", dt.OUTCOMES)
        # no status yet, no ticket, nothing for the human: the settler comes first
        self.assertIsNone(r["proposed_status"])
        self.assertIsNone(r["grounds"])
        self.assertFalse(r["needs_human"])
        self.assertFalse(r["recolour"])
        self.assertEqual(r["file_items"], [])
        self.assertEqual(r["modulo_options"], [])
        self.assertEqual(r["pending_inputs"], [])
        # what both runs list is the settlement's base; each differing input once, with its run
        self.assertEqual(r["modulo"], ["paper:lem:a"])
        self.assertEqual(r["differing_inputs"], [
            {"input": "bib:LMW16#Thm11", "run": "A", "shape": "card",
             "result": "bib:LMW16#Thm11", "pointer": False, "open_check": False,
             "exists": None, "cycle": False, "definition": False},
            {"input": "paper:lem:b", "run": "B", "shape": "id", "result": "paper:lem:b",
             "pointer": False, "open_check": False, "exists": None, "cycle": False,
             "definition": False}])
        # both runs' lists kept, as the table compared them
        self.assertEqual(r["modulo_lists"], {"A": ["paper:lem:a", "bib:LMW16#Thm11"],
                                             "B": ["paper:lem:a", "paper:lem:b"]})
        self.assertEqual(r["dropped_inputs"], [])
        self.assertNotIn("declare_dependencies", r)
        txt = dt._text(r)
        self.assertIn("outcome: settle-dependencies", txt)
        self.assertIn("differing input (run A, card): bib:LMW16#Thm11", txt)
        self.assertIn("run B listed: paper:lem:a, paper:lem:b", txt)
        self.assertIn("dependency-settler", r["summary"])

    def test_an_open_check_is_a_fact_and_never_reduced(self):
        # an open [CHECK] can never be a dependency (case 9 only); free text is no result
        r = self.decide("paper:lem:a", "paper:lem:a, flat:PER-7 ([CHECK] T-1144), "
                        "bib:AW21#§1 p2 [CHECK T-1144] invariance, uncited Hausdorffness of T")
        f = self.facts(r)
        self.assertEqual({k: v["shape"] for k, v in f.items()},
                         {"flat:PER-7 ([CHECK] T-1144)": "check",
                          "bib:AW21#§1 p2 [CHECK T-1144] invariance": "check",
                          "uncited Hausdorffness of T": "text"})
        self.assertTrue(f["flat:PER-7 ([CHECK] T-1144)"]["open_check"])
        self.assertEqual(f["flat:PER-7 ([CHECK] T-1144)"]["result"], "flat:PER-7")
        self.assertFalse(f["uncited Hausdorffness of T"]["open_check"])
        self.assertEqual(f["uncited Hausdorffness of T"]["result"], "")
        self.assertIs(f["uncited Hausdorffness of T"]["exists"], False)
        # T-1463's shape: a [CHECK] input the shared lemma reaches stays for the settler
        # (listed first: _split_list strips a ']' that ends the whole line, a separate issue)
        r = self.decide("paper:lem:w [CHECK T-9], paper:lem:y", "paper:lem:y")
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertEqual(r["dropped_inputs"], [])
        self.assertEqual(self.facts(r)["paper:lem:w [CHECK T-9]"]["shape"], "check")

    def test_existence_is_shown_or_not_never_maybe(self):
        known = {"paper:lem:b", "paper:lem:y"}
        ex_ = lambda q: True if q in known else (None if q == "paper:lem:dark" else False)
        r = self.decide("paper:lem:a", "paper:lem:a, paper:lem:b, paper:lem:nowhere, "
                        "paper:lem:dark, check:T-1033#Fix(j_Y), lem:y (first clause)",
                        exists=ex_)
        f = self.facts(r)
        self.assertEqual((f["paper:lem:b"]["shape"], f["paper:lem:b"]["exists"]), ("id", True))
        self.assertEqual((f["paper:lem:nowhere"]["shape"], f["paper:lem:nowhere"]["exists"]),
                         ("unshown", False))
        # an unreadable registry (None) does not show it either
        self.assertEqual((f["paper:lem:dark"]["shape"], f["paper:lem:dark"]["exists"]),
                         ("unshown", False))
        # an unknown namespace with pointer text after it
        c = f["check:T-1033#Fix(j_Y)"]
        self.assertEqual((c["shape"], c["exists"], c["pointer"]), ("unshown", False, True))
        # a pointer-restricted id is normalised before the existence check
        p = f["lem:y (first clause)"]
        self.assertEqual((p["shape"], p["result"], p["pointer"], p["exists"]),
                         ("id", "paper:lem:y", True, True))
        # without a registry check nothing is shown and nothing refused: exists None
        r = self.decide("paper:lem:a", "paper:lem:b")
        self.assertIsNone(self.facts(r)["paper:lem:b"]["exists"])

    def test_registry_exists_reads_an_unknown_namespace_as_absent(self):
        import unittest.mock as um
        from registry.core import workspace as rws
        with um.patch.object(rws, "namespaces", return_value={"paper": {"home": "/nowhere"}}):
            for q in ("check:T-1033", "tex:eq-3", "uncited:Hausdorff"):
                with self.subTest(q=q):
                    self.assertIs(dt.registry_exists(q), False)
                    self.assertFalse(dt.dependency_ok(q, exists=dt.registry_exists))
            # a namespace of the workspace whose home cannot be read: not readable (None)
            self.assertIsNone(dt.registry_exists("paper:lem:y"))

    def test_a_cycle_back_to_the_subject_is_a_fact(self):
        r = self.decide("paper:lem:a", "paper:lem:a, paper:lem:z, paper:lem:z2, paper:lem:w")
        f = self.facts(r)
        self.assertEqual((f["paper:lem:z"]["shape"], f["paper:lem:z"]["cycle"]), ("cycle", True))
        # through a modulo link too
        self.assertEqual(f["paper:lem:z2"]["shape"], "cycle")
        self.assertEqual((f["paper:lem:w"]["shape"], f["paper:lem:w"]["cycle"]), ("id", False))
        # the subject itself listed as an input
        r = self.decide("paper:lem:a", "paper:lem:a, paper:lem:x")
        self.assertEqual(self.facts(r)["paper:lem:x"]["shape"], "cycle")
        # no registry: no cycle shown
        r = self.decide("paper:lem:a", "paper:lem:a, paper:lem:z", links=False)
        self.assertEqual(self.facts(r)["paper:lem:z"]["shape"], "id")

    def test_two_wordings_of_one_input_stay_two(self):
        # the 93e5325 report: the same thing in different words is the settler's
        r = self.decide("bib:Wr14#Theorem1.1 extended to strata with marked points",
                        "bib:Wr14#Theorem1.1 (extended to strata with marked points)")
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertEqual(len(r["differing_inputs"]), 2)
        self.assertEqual({d["shape"] for d in r["differing_inputs"]}, {"card"})
        self.assertEqual({d["pointer"] for d in r["differing_inputs"]}, {True})

    def test_an_input_a_shared_input_reaches_is_dropped_mechanically(self):
        # T-1428's shape: both name paper:lem:y, A also names paper:lem:w it rests on (case 4)
        r = self.decide("paper:lem:y, paper:lem:w", "paper:lem:y")
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["proposed_status"], "proved-modulo")
        self.assertEqual(r["modulo"], ["paper:lem:y"])
        self.assertEqual(r["dropped_inputs"], [{"input": "paper:lem:w", "via": "paper:lem:y",
                                                "how": "depends_on", "case": 4}])
        self.assertEqual(r["modulo_lists"]["A"], ["paper:lem:y", "paper:lem:w"])
        self.assertIn("paper:lem:w", r["grounds"]["note"])
        self.assertEqual(r["grounds"]["modulo"], ["paper:lem:y"])
        self.assertIn("dropped: paper:lem:w (reached through paper:lem:y", dt._text(r))
        claims = ex.mcp_module("claims")
        ok, why = claims.check_grounds("proved-modulo", r["grounds"], "abc123")
        self.assertTrue(ok, why)

    def test_a_card_a_shared_lemma_cites_is_dropped_mechanically(self):
        # T-1427's shape: A cites the card section, both the lemma that cites it (case 4)
        r = self.decide("flat:PER-2, bib:AW21#Theorem3.6", "flat:PER-2")
        self.assertEqual((r["outcome"], r["modulo"]), ("confirmed-modulo", ["flat:PER-2"]))
        self.assertEqual(r["dropped_inputs"], [{"input": "bib:AW21#Theorem3.6",
                                                "via": "flat:PER-2", "how": "cites",
                                                "case": 4}])
        # through the depends_on chain too: paper:lem:y -> paper:lem:x2 cites SW08
        r = self.decide("paper:lem:y", "paper:lem:y, bib:SW08#Sect2")
        self.assertEqual((r["outcome"], r["modulo"]), ("confirmed-modulo", ["paper:lem:y"]))

    def test_a_carried_modulo_of_a_shared_input_is_no_difference(self):
        # case 13: flat:PER-2 is itself only proved-modulo flat:PER-9; a run that lists PER-9
        # too names what PER-2 carries (and what PER-9 rests on)
        r = self.decide("flat:PER-2, flat:PER-9", "flat:PER-2")
        self.assertEqual((r["outcome"], r["modulo"]), ("confirmed-modulo", ["flat:PER-2"]))
        self.assertEqual(r["dropped_inputs"], [{"input": "flat:PER-9", "via": "flat:PER-2",
                                                "how": "modulo", "case": 13}])
        r = self.decide("flat:PER-2", "flat:PER-2, flat:PER-10")
        self.assertEqual(r["modulo"], ["flat:PER-2"])
        self.assertEqual((r["dropped_inputs"][0]["how"], r["dropped_inputs"][0]["case"]),
                         ("modulo", 13))
        # both runs CONFIRMED with no difference left: no proved without the carried input
        r = self.decide("flat:PER-2, flat:PER-9", "flat:PER-2", established=["flat:PER-2"])
        self.assertEqual((r["outcome"], r["proposed_status"]), ("confirmed-modulo",
                                                                "proved-modulo"))

    def test_a_declared_input_of_one_run_covers_what_it_rests_on_in_the_other(self):
        # case 4 where the registry shows it: the proof declares paper:lem:y (the more direct);
        # B names paper:lem:x2, which paper:lem:y rests on
        r = self.decide("paper:lem:y", "paper:lem:x2")
        self.assertEqual((r["outcome"], r["modulo"]), ("confirmed-modulo", ["paper:lem:y"]))
        self.assertEqual(r["dropped_inputs"], [{"input": "paper:lem:x2", "via": "paper:lem:y",
                                                "how": "depends_on", "case": 4}])
        # an undeclared reaching input decides nothing: both go to the settler
        r = self.decide("paper:lem:x2", "paper:lem:w")
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertEqual([d["input"] for d in r["differing_inputs"]],
                         ["paper:lem:w", "paper:lem:x2"])
        self.assertEqual(r["dropped_inputs"], [])

    def test_only_the_mechanical_cases_are_normalised(self):
        # no shared record cites the key: the settler's
        self.assertEqual(self.decide("flat:PER-2", "flat:PER-2, bib:LMW16#S2.2")["outcome"],
                         "settle-dependencies")
        # the reaching input is pinpointed or restricted by pointer text: no reach
        self.assertEqual(self.decide("paper:lem:y#item2, paper:lem:w", "paper:lem:y#item2")
                         ["outcome"], "settle-dependencies")
        self.assertEqual(self.decide("paper:lem:y (first clause), paper:lem:w",
                                     "paper:lem:y (first clause)")["outcome"],
                         "settle-dependencies")
        # an input both runs list is never dropped
        r = self.decide("paper:lem:y, paper:lem:w", "paper:lem:y, paper:lem:w")
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["modulo"], ["paper:lem:w", "paper:lem:y"])
        self.assertNotIn("dropped_inputs", r)
        # a cycle in depends_on drops neither
        r = self.decide("paper:lem:c1, paper:lem:c2", "paper:lem:c1")
        self.assertEqual(r["outcome"], "settle-dependencies")
        # without the registry nothing is dropped
        r = self.decide("paper:lem:y, paper:lem:w", "paper:lem:y", links=False)
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertEqual(r["dropped_inputs"], [])

    def test_reduce_differing_alone(self):
        got = dt.reduce_differing(["paper:lem:y", "paper:lem:w"], ["paper:lem:y"],
                                  self.LINKS.get)
        self.assertEqual(got["differing"], [])
        self.assertEqual(got["agreed"], ["paper:lem:y"])
        got = dt.reduce_differing(["paper:lem:a"], ["paper:lem:b"], self.LINKS.get)
        self.assertEqual(got, {"dropped": [], "differing": ["paper:lem:a", "paper:lem:b"],
                               "agreed": []})

    def test_a_blocking_step_or_differing_verdicts_stay_a_disagreement(self):
        r = self.decide("paper:lem:a", "paper:lem:b", bb="step 3 is unclear")
        self.assertEqual(r["outcome"], "disagreement")
        self.assertIsNone(r["proposed_status"])
        self.assertEqual([i["kind"] for i in r["file_items"]], ["inputs"])
        self.assertEqual(len(r["modulo_options"]), 2)
        r = self.decide("paper:lem:a", "paper:lem:b", vb="GAP", bb="step 3")
        self.assertEqual(r["outcome"], "disagreement")
        self.assertIsNone(r["proposed_status"])

    def test_the_amend_route_is_unchanged(self):
        a = rec("CONFIRMED", "A", modulo="paper:lem:a")
        a["add_dependency"] = ["paper:lem:x2"]
        r = dt.decide(a, None, kind_of=lambda q: None, canon=lambda q: None,
                      links_of=self.LINKS.get)
        self.assertEqual(r["outcome"], "awaiting-amendment")

    def test_registry_links_reads_depends_on_modulo_and_cites(self):
        class Rec:
            links = [("depends_on", "paper:lem:x2"), ("depends_on", "lem:w"),
                     ("bears_on", "flat:FND-1"), ("modulo", "paper:lem:m")]
            fields = {"cites": ["SW08", "bib:AW21"]}

        class Store:
            def lookup(self, name):
                return (name, True) if name == "lem:y" else (None, False)

            def get(self, name):
                return Rec() if name == "lem:y" else None
        import unittest.mock as um
        from registry.core import federation, workspace as rws
        with um.patch.object(rws, "namespaces", return_value={"paper": {"home": os.getcwd()}}), \
                um.patch.object(federation, "store", return_value=Store()), \
                um.patch.object(dt, "registry_canonical", side_effect=lambda q: None):
            got = dt.registry_links("paper:lem:y")
            self.assertEqual(got, {"depends_on": ["paper:lem:x2", "paper:lem:w"],
                                   "modulo": ["paper:lem:m"], "cites": ["SW08", "AW21"]})
            self.assertIsNone(dt.registry_links("paper:lem:nowhere"))
        self.assertIsNone(dt.registry_links("bib:AW21"))


def arec(verdict="CONFIRMED", add="paper:lem:x2", modulo="none", run_id="rv-A",
         model="claude-fable-5-1", h="abc123", subject="paper:lem:x"):
    """Run A of a pass, CONFIRMED with a suggested dependency (2026-11-20)."""
    text = ("Report.\n\nVERDICT\nsubject: %s\npass: 2026-09-28-T-0007\nrun: A\n"
            "verdict: %s\nmodulo: %s\nadd_dependency: %s\nmodel: %s\nstatement_hash: %s\n"
            "blocking: none\nticket: T-0007\n" % (subject, verdict, modulo, add, model, h))
    r = dt.parse_record(text)
    r["run_id"] = run_id
    r.setdefault("file", "reviews/paper/lem-x/2026-09-28-T-0007/A.md")
    return r


def amrec(verdict="CONFIRMED", amended="paper:lem:x2", modulo="none", base_pass="2026-09-28-T-0007",
          base_hash="abc123", h="abc123", run_id="rv-B", model="claude-opus-5-5",
          blocking="none", subject="paper:lem:x", add="none"):
    """Run B in amend mode: the informed review of the amended proof."""
    text = ("Report.\n\nVERDICT\nsubject: %s\npass: 2026-09-28-T-0007\nrun: B\n"
            "mode: amend\nbase_pass: %s\nbase_hash: %s\namended_with: %s\nverdict: %s\n"
            "modulo: %s\nadd_dependency: %s\nmodel: %s\nstatement_hash: %s\nblocking: %s\n"
            "ticket: T-0007\n" % (subject, base_pass, base_hash, amended, verdict, modulo,
                                   add, model, h, blocking))
    r = dt.parse_record(text)
    r["run_id"] = run_id
    r.setdefault("file", "reviews/paper/lem-x/2026-09-28-T-0007/B.md")
    return r


class AmendTableTests(unittest.TestCase):
    """The human's design (2026-11-20): a reviewer may suggest a dependency the proof
    relies on but does not list; once the producer adds it, B reviews the amended proof
    informed of the suggestion, and A + B are the two agreeing verdicts."""

    def test_parse_add_dependency_and_amend_fields(self):
        a = arec(add="paper:lem:y, bib:LMW16#Thm-11")
        self.assertEqual(a["add_dependency"], ["paper:lem:y", "bib:LMW16#Thm-11"])
        self.assertFalse(dt.is_amend(a))
        b = amrec()
        self.assertTrue(dt.is_amend(b))
        self.assertEqual((b["mode"], b["base_pass"], b["base_hash"], b["amended_with"]),
                         ("amend", "2026-09-28-T-0007", "abc123", ["paper:lem:x2"]))
        self.assertEqual(rec("CONFIRMED")["add_dependency"], [])

    def test_a_confirmed_with_a_suggestion_awaits_the_amendment(self):
        r = dt.decide(arec())
        self.assertEqual(r["outcome"], "awaiting-amendment")
        self.assertFalse(r["launch_b"])
        self.assertIsNone(r["proposed_status"])
        self.assertEqual(r["add_dependency"], ["paper:lem:x2"])
        it = r["file_items"][0]
        self.assertEqual((it["kind"], it["text"]), ("add-dependency", "paper:lem:x2"))
        self.assertEqual((it["route"]["kind"], it["route"]["to_role"], it["route"]["mode"]),
                         ("prove", "researcher", "repair"))
        self.assertIn("awaiting-amendment", dt.OUTCOMES)

    def test_a_without_a_suggestion_is_unchanged(self):
        r = dt.decide(rec("CONFIRMED"))
        self.assertEqual((r["outcome"], r["launch_b"]), ("awaiting-b", True))
        r = dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B"))
        self.assertEqual(r["outcome"], "confirmed")

    def test_amend_b_confirmed_gives_confirmed_modulo_the_added_dependency(self):
        r = dt.decide(arec(), amrec())
        self.assertEqual(r["outcome"], "confirmed-modulo", r)
        self.assertEqual(r["mode"], "amend")
        self.assertEqual(r["modulo"], ["paper:lem:x2"])
        self.assertEqual(r["added_dependencies"], ["paper:lem:x2"])
        self.assertEqual(r["proposed_status"], "proved-modulo")
        self.assertFalse(r["recolour"])
        self.assertEqual(r["pending_inputs"], ["paper:lem:x2"])
        g = r["grounds"]
        self.assertEqual(g["modulo"], ["paper:lem:x2"])
        self.assertEqual([v["run_id"] for v in g["verdicts"]], ["rv-A", "rv-B"])
        self.assertEqual(g["mode"], "amend")
        self.assertEqual(g["verdicts"][1]["mode"], "amend")
        self.assertIn("rv-A", g["note"])
        self.assertIn("rv-B", g["note"])
        self.assertIn("amend", dt._text(r))

    def test_established_added_dependency_gives_confirmed(self):
        r = dt.decide(arec(), amrec(), established=["paper:lem:x2"])
        self.assertEqual((r["outcome"], r["proposed_status"], r["recolour"]),
                         ("confirmed", "proved", True))
        self.assertNotIn("modulo", r["grounds"])      # proved needs none (registry grounds)
        self.assertEqual(r["grounds"]["added_dependencies"], ["paper:lem:x2"])
        self.assertEqual(r["pending_inputs"], [])

    def test_union_with_the_modulo_lists_and_b_may_add_to_modulo(self):
        r = dt.decide(arec(modulo="paper:lem:a"), amrec(modulo="paper:lem:b"),
                      established=["paper:lem:a"])
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["modulo"], ["paper:lem:a", "paper:lem:b", "paper:lem:x2"])
        self.assertEqual(r["pending_inputs"], ["paper:lem:b", "paper:lem:x2"])

    def test_spellings_are_normalised_in_the_dependency_lists(self):
        """#103: the added dependencies are compared in canonical spelling."""
        r = dt.decide(arec(add="lem:x2, bib:LMW16#Thm-11"),
                      amrec(amended="paper:lem:x2; bib:LMW16#Thm11"))
        self.assertEqual(r["outcome"], "confirmed-modulo", r["anomalies"])
        self.assertEqual(sorted(r["added_dependencies"]), ["bib:LMW16#Thm11", "paper:lem:x2"])

    def test_a_gap_amend_run_changes_nothing(self):
        r = dt.decide(arec(), amrec(verdict="GAP", blocking="the added lemma needs compactness"))
        self.assertEqual(r["outcome"], "disagreement")
        self.assertIsNone(r["proposed_status"])
        self.assertIsNone(r["grounds"])
        self.assertEqual(r["file_items"][0]["kind"], "repair")

    def test_invalid_amend_runs(self):
        cases = [
            ("suggested nothing", rec("CONFIRMED"), amrec()),
            ("other dependencies", arec(), amrec(amended="paper:lem:z")),
            ("other dependencies", arec(add="paper:lem:x2, paper:lem:y"), amrec()),
            ("base_pass", arec(), amrec(base_pass="2026-01-01-T-0001")),
            ("base_hash", arec(), amrec(base_hash="ffff00")),
            ("statement", arec(), amrec(h="def456", base_hash="abc123")),
            ("run id", arec(), amrec(run_id="rv-A")),
            ("further dependencies", arec(), amrec(add="paper:lem:w")),
        ]
        for why, a, b in cases:
            with self.subTest(why=why):
                r = dt.decide(a, b)
                self.assertEqual(r["outcome"], "invalid-amend", r)
                self.assertIsNone(r["proposed_status"])
                self.assertTrue(any(why in x for x in r["anomalies"]), r["anomalies"])
        self.assertIn("invalid-amend", dt.OUTCOMES)

    def test_a_blind_b_after_a_suggestion_is_not_two_agreeing_verdicts(self):
        r = dt.decide(arec(), rec("CONFIRMED", run="B"))
        self.assertEqual(r["outcome"], "invalid-amend")
        self.assertIsNone(r["proposed_status"])

    def test_a_non_primary_amend_run_is_degraded(self):
        r = dt.decide(arec(), amrec(model="claude-sonnet-4-5"))
        self.assertEqual(r["outcome"], "degraded")
        self.assertIsNone(r["proposed_status"])

    def test_cli_reads_the_amend_pair_from_landed_records(self):
        import shutil
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "2026-09-28-T-0007")
            os.makedirs(p)
            with open(os.path.join(p, "A.md"), "w", encoding="utf-8") as fh:
                fh.write("---\nsubject: paper:lem:x\npass: 2026-09-28-T-0007\nrun: A\n"
                         "run_id: rv-A\nverdict: CONFIRMED\nmodulo: []\n"
                         "model: claude-opus-5-5\nstatement_hash: abc123\n"
                         "add_dependency: [paper:lem:x2]\n---\n\nr\n")
            with open(os.path.join(p, "B.md"), "w", encoding="utf-8") as fh:
                fh.write("---\nsubject: paper:lem:x\npass: 2026-09-28-T-0007\nrun: B\n"
                         "run_id: rv-B\nverdict: CONFIRMED\nmodulo: []\n"
                         "model: claude-opus-5-5\nstatement_hash: abc123\nmode: amend\n"
                         "base_pass: 2026-09-28-T-0007\nbase_hash: abc123\n"
                         "amended_with: [paper:lem:x2]\n---\n\nr\n")
            code, out, err = fixtures.run_script(
                "decision_table.py", None, [os.path.join(p, "A.md"), "--json"])
            self.assertEqual(out["outcome"], "awaiting-amendment", out)
            code, out, err = fixtures.run_script(
                "decision_table.py", None, [os.path.join(p, "A.md"), os.path.join(p, "B.md"),
                                            "--established", "paper:lem:x2", "--json"])
            self.assertEqual(code, 0, err)
            self.assertEqual(out["outcome"], "confirmed", out)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class AmendReviewFixTests(unittest.TestCase):
    """Review fixes of the amend route (2026-11-20): a blind B's suggestion is an honest
    outcome, and a suggestion must name an existing result."""

    def bsug(self, add="paper:lem:x2"):
        text = ("Report.\n\nVERDICT\nsubject: paper:lem:x\npass: 2026-09-28-T-0007\nrun: B\n"
                "verdict: CONFIRMED\nmodulo: none\nadd_dependency: %s\nmodel: claude-opus-5-5\n"
                "statement_hash: abc123\nblocking: none\nticket: T-0007\n" % add)
        r = dt.parse_record(text)
        r["run_id"] = "rv-B"
        r["file"] = "reviews/paper/lem-x/2026-09-28-T-0007/B.md"
        return r

    def test_a_blind_b_suggestion_is_an_honest_outcome_routed_to_the_producer(self):
        r = dt.decide(rec("CONFIRMED"), self.bsug())
        self.assertEqual(r["outcome"], "new-pass-after-amendment", r)
        self.assertIn("new-pass-after-amendment", dt.OUTCOMES)
        self.assertIsNone(r["proposed_status"])
        self.assertIsNone(r["grounds"])
        self.assertEqual(r["anomalies"], [])
        it = r["file_items"][0]
        self.assertEqual((it["run"], it["kind"], it["text"]), ("B", "add-dependency", "paper:lem:x2"))
        self.assertEqual((it["route"]["kind"], it["route"]["to_role"], it["route"]["mode"]),
                         ("prove", "researcher", "repair"))
        self.assertIn("run B", r["summary"])
        self.assertIn("not run A", r["summary"])
        self.assertIn("new pass", r["summary"])

    def test_dependency_forms(self):
        ok = ["paper:lem:x2", "s1:CEX-3", "bib:LMW16", "bib:LMW16#Thm11", "paper:lem:x2#item2"]
        bad = ["a lemma that compact sets are closed", "lem x2", "OBS-3", "bib:", "bib:LMW 16",
               "paper:lem:y (first clause)", ""]
        for d in ok:
            with self.subTest(d=d):
                self.assertTrue(dt.dependency_ok(d), d)
        for d in bad:
            with self.subTest(d=d):
                self.assertFalse(dt.dependency_ok(d), d)
        # a registry that can be read must know the id; an unreadable one (None) does not refuse
        self.assertFalse(dt.dependency_ok("paper:lem:x2", exists=lambda q: False))
        self.assertTrue(dt.dependency_ok("paper:lem:x2", exists=lambda q: None))
        self.assertTrue(dt.dependency_ok("bib:LMW16#Thm11", exists=lambda q: False))

    def test_a_pinpoint_is_a_pinpoint_and_an_open_check_never_passes(self):
        # the 93e5325 report: bib:KEY# followed by free text, '[CHECK ...]' included, passed
        ok = ["bib:AW21#Assumption 3.2", "bib:LMW16#§2.3 Example", "bib:Ha02#§1.3-Ex23",
              "paper:lem:covering-moduli-proper#items 2-3", "bib:MS91#Lem4.2-interior-reading",
              "paper:defn:covering-moduli#labelled-points", "bib:EMM15#Theorem2.1",
              "bib:AW21#p. 8"]
        bad = ["bib:EMM15#Thm2.1 and Thm2.6 for strata with marked points incl. genus 1 "
               "(bridged only by bib:LMW16#S2.2)",
               "bib:AW21#§1 p2 [CHECK] T-1144 (GL2+(R)-invariance of the M-periodic point N)",
               "bib:AW21#§1 p2 [CHECK T-1144] GL2+(R)-invariance",
               "bib:Wr14#Theorem1.1 extended to strata with marked points",
               "bib:Wr14#Theorem1.1 (extended to strata with marked points)",
               "flat:PER-7 ([CHECK] T-1144)", "paper:lem:x2#item2 [CHECK]",
               "paper:lem:x2#item2 [check: T-9]", "bib:SW08#Lemmas 14-16 and Corollary17",
               "flat:MOD-1#(I0) period coordinates"]
        for d in ok:
            with self.subTest(d=d):
                self.assertTrue(dt.dependency_ok(d), d)
        for d in bad:
            with self.subTest(d=d):
                self.assertFalse(dt.dependency_ok(d), d)
        self.assertTrue(dt.has_open_check("x [CHECK] y"))
        self.assertTrue(dt.has_open_check("x [ check T-1144 ]"))
        self.assertFalse(dt.has_open_check("bib:AW21#Theorem3.6"))

    def test_a_suggestion_that_is_not_a_result_is_a_gap_for_the_amend_route(self):
        r = dt.decide(arec(add="the lemma that the lift is continuous"))
        self.assertEqual(r["outcome"], "single-negative", r)
        self.assertFalse(r["launch_b"])
        self.assertIsNone(r["proposed_status"])
        self.assertNotIn("add-dependency", [i["kind"] for i in r["file_items"]])
        self.assertEqual(r["file_items"][0]["kind"], "repair")
        self.assertTrue(any("not an existing result" in x for x in r["anomalies"]), r["anomalies"])

    def test_an_unknown_registry_id_is_not_a_dependency(self):
        r = dt.decide(arec(add="paper:lem:nowhere"), exists=lambda q: False)
        self.assertEqual(r["outcome"], "single-negative", r)
        self.assertTrue(any("paper:lem:nowhere" in x for x in r["anomalies"]))
        r = dt.decide(arec(add="paper:lem:x2"), exists=lambda q: q == "paper:lem:x2")
        self.assertEqual(r["outcome"], "awaiting-amendment")

    def test_an_amend_b_suggesting_a_non_result_is_gap_equivalent(self):
        r = dt.decide(arec(), amrec(add="some missing step"))
        self.assertEqual(r["outcome"], "disagreement", r)
        self.assertIsNone(r["proposed_status"])

    def test_the_canon_command_prints_the_canonical_spelling(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = dt.main(["canon", "--subject", "paper:lem:x", "bib:LMW16#Thm-11",
                            " paper:lem:y "])
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue().split(), ["bib:LMW16#Thm11", "paper:lem:y"])

    def test_the_cli_checks_the_registry(self):
        d = tempfile.mkdtemp()
        try:
            p = os.path.join(d, "A.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("---\nsubject: paper:lem:x\npass: 2026-09-28-T-0007\nrun: A\n"
                         "run_id: rv-A\nverdict: CONFIRMED\nmodulo: []\n"
                         "model: claude-opus-5-5\nstatement_hash: abc123\n"
                         "add_dependency: [paper:lem:nowhere]\n---\n\nr\n")
            seen = []
            old = dt.registry_exists
            dt.registry_exists = lambda q: seen.append(q) or False
            try:
                import contextlib
                import io
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    dt.main([p, "--json"])
            finally:
                dt.registry_exists = old
            out = json.loads(buf.getvalue())
            self.assertEqual(out["outcome"], "single-negative", out)
            self.assertIn("paper:lem:nowhere", seen)
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)


class ResearcherForTests(unittest.TestCase):
    """Review V1 #5: the Researcher a claim's falsifier request goes to, computed, not
    guessed: the Researcher owning the claim's namespace; else the one Researcher the
    claim's bears_on names; else the one Researcher in the ticket's parent chain; else
    (none, or more than one at a step) the human decides."""
    WS = {"instances": {
        "researcher@a": {"role": "researcher", "ns": "a"},
        "researcher@b": {"role": "researcher", "ns": "b"},
        "author@main": {"role": "author", "ns": "paper"},
        "scientist@main": {"role": "scientist", "ns": "lab"},
        "expert@main": {"role": "expert"}}}

    def who(self, subject, **kw):
        return dt.researcher_for(subject, self.WS, **kw)[0]

    def test_several_owners_of_one_namespace_stop_at_the_human(self):
        ws = {"instances": dict(self.WS["instances"], **{"researcher@a2": {"role": "researcher", "ns": "a"}})}
        who, why = dt.researcher_for("a:GEO-1", ws, bears_on=["b:X"])
        self.assertEqual(who, "human")
        self.assertIn("several Researchers", why)

    def test_the_namespace_owner_wins(self):
        self.assertEqual(self.who("a:GEO-1", bears_on=["b:X"], parties=["researcher@b"]),
                         "researcher@a")

    def test_bears_on_then_the_parent_chain(self):
        self.assertEqual(self.who("paper:lem:x", bears_on=["b:GEO-9", "paper:lem:y"]), "researcher@b")
        self.assertEqual(self.who("lab:x-search", bears_on=["a:CLASS-1"],
                                  parties=["researcher@b"]), "researcher@a")
        self.assertEqual(self.who("paper:lem:x", parties=["author@main", "expert@main",
                                                          "researcher@a", "researcher@a"]),
                         "researcher@a")

    def test_none_or_several_is_the_humans_call(self):
        self.assertEqual(self.who("paper:lem:x"), "human")
        inst, why = dt.researcher_for("paper:lem:x", self.WS, bears_on=["a:X", "b:Y"],
                                      parties=["researcher@a"])
        self.assertEqual(inst, "human")
        self.assertIn("researcher@a, researcher@b", why)
        self.assertEqual(self.who("lab:x", parties=["researcher@a", "researcher@b"]), "human")
        self.assertEqual(self.who("zz:unknown"), "human")

    def test_the_cli_answers_in_json(self):
        sb = fixtures.Sandbox()
        self.addCleanup(sb.close)
        with open(sb.ws_path, encoding="utf-8") as fh:
            ws = json.load(fh)
        ws["instances"]["researcher@a"] = {"role": "researcher", "ns": "a", "home": sb.root.replace("\\", "/"),
                                          "domains": ["translation-surfaces"]}
        with open(sb.ws_path, "w", encoding="utf-8") as fh:
            json.dump(ws, fh)
        code, out, err = fixtures.run_script("reviews.py", args=[
            "researcher-for", "paper:lem:x", "--party", "author@main", "--party", "researcher@a"])
        self.assertEqual(code, 0, err)
        self.assertEqual(out["instance"], "researcher@a")
        self.assertTrue(out["why"])


if __name__ == "__main__":
    unittest.main()


class DefinitionRuleReviewTests(unittest.TestCase):
    """The review of 47ab60e (#103): the definition rule's findings, from the reviewer's
    scenario script."""
    D, E = "paper:defn:d", "paper:defn:e"
    KINDS = {"paper:defn:d": "definition", "paper:defn:e": "definition",
             "paper:lem:a": "claim", "paper:lem:b": "claim", "paper:lem:x": "claim"}

    def run_(self, a, b, tags=None, links=None, kinds=None):
        return dt.decide(rec("CONFIRMED", modulo=a), rec("CONFIRMED", run="B", modulo=b),
                         kind_of=(kinds or self.KINDS).get, tags_of=(tags or {}).get,
                         links_of=links)

    # finding 1: the kind is read on the head token, and the settler gets a definition fact
    def test_a_definition_with_pointer_text_and_any_label_is_kept(self):
        kinds = {"s1:GEO-9": "definition"}
        r = self.run_("s1:GEO-9 (clause 2)", "none", kinds=kinds)
        self.assertEqual((r["outcome"], r["proposed_status"]),
                         ("confirmed-modulo", "proved-modulo"))
        self.assertEqual(r["kept_definitions"], ["s1:GEO-9 (clause 2)"])
        self.assertTrue(dt.is_definition("s1:GEO-9 (clause 2)", kinds.get))
        self.assertTrue(dt.is_definition("paper:defn:c#labelled-points", lambda q: None))
        self.assertFalse(dt.is_definition("paper:lem:a (item 2)", self.KINDS.get))

    def test_input_facts_say_whether_the_input_is_a_definition(self):
        kinds = {"s1:GEO-9": "definition", "paper:lem:a": "claim"}.get
        self.assertTrue(dt.input_facts("s1:GEO-9 (clause 2)", "A", kind_of=kinds)["definition"])
        self.assertFalse(dt.input_facts("paper:lem:a", "A", kind_of=kinds)["definition"])
        self.assertFalse(dt.input_facts("bib:Ha02#1.3", "A", kind_of=kinds)["definition"])

    # finding 2: a kept definition is no route for a case-4 drop
    def test_a_kept_definition_does_not_drop_a_lemma_by_granularity(self):
        links = {"paper:lem:x": {"depends_on": [], "modulo": [], "cites": []},
                 self.D: {"depends_on": ["paper:lem:a"], "modulo": [], "cites": []},
                 "paper:lem:a": {"depends_on": [], "modulo": [], "cites": []}}.get
        r = self.run_("paper:lem:a", self.D, links=links)
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertEqual(r["modulo"], [self.D])
        self.assertEqual([d["input"] for d in r["differing_inputs"]], ["paper:lem:a"])
        self.assertEqual(r["dropped_inputs"], [])

    # finding 3: a kept definition is a once-per-definition decision, never a verify ticket
    def test_a_kept_definition_is_a_definition_input_decision_not_a_verify(self):
        r = self.run_("paper:lem:a, " + self.D, "paper:lem:a")
        items = {i["text"]: i for i in r["file_items"]}
        self.assertEqual(items["paper:lem:a"]["kind"], "verify-input")
        it = items[self.D]
        self.assertEqual(it["kind"], "definition-input")
        self.assertEqual(it["definition"], self.D)
        route = it["route"]
        self.assertEqual((route["kind"], route["to_role"]), ("decision", "human"))
        self.assertTrue(route["once"])
        self.assertEqual(route["title"], "Definition input: %s" % self.D)
        self.assertIn("notation-only", route["ask"])
        self.assertIn("paper:lem:x", route["ask"])
        self.assertFalse(r["recolour"])
        # the pointer variant: the decision is about the definition's id
        r = self.run_(self.D + " (item 2)", "none")
        self.assertEqual([(i["kind"], i["definition"]) for i in r["file_items"]],
                         [("definition-input", self.D)])

    # nit (a): one kept input per definition, the pointer variant when there is one
    def test_one_kept_input_per_definition(self):
        r = self.run_(self.D + " (item 2)", self.D)
        self.assertEqual(r["kept_definitions"], [self.D + " (item 2)"])
        self.assertEqual(r["modulo"], [self.D + " (item 2)"])
        r = self.run_(self.D + " (notation only)", self.D)
        self.assertEqual(r["kept_definitions"], [self.D])

    # nit (b): the reword run's modulo follows the same rule
    def test_the_reword_run_applies_the_definition_rule(self):
        a, b = rec("CONFIRMED"), rec("CONFIRMED", run="B")
        tags = {self.D: ["notation-only"]}.get
        r = dt.decide_reword(rwrec(modulo=self.D + " (notation only)"), a, b,
                             kind_of=self.KINDS.get, tags_of=tags)
        self.assertEqual((r["outcome"], r["proposed_status"]), ("confirmed", "proved"))
        self.assertEqual(r["dropped_definitions"], [self.D])
        r = dt.decide_reword(rwrec(modulo=self.D + " (notation only)"), a, b,
                             kind_of=self.KINDS.get, tags_of=lambda q: None)
        self.assertEqual((r["outcome"], r["modulo"]), ("confirmed-modulo", [self.D]))
        self.assertEqual(r["kept_definitions"], [self.D])
        self.assertEqual([i["kind"] for i in r["file_items"]], ["definition-input"])

    def test_the_amend_pass_applies_the_definition_rule(self):
        tags = {self.D: ["notation-only"]}.get
        r = dt.decide(arec(add="paper:lem:x2", modulo=self.D),
                      amrec(amended="paper:lem:x2"), kind_of=self.KINDS.get, tags_of=tags,
                      established=["paper:lem:x2"])
        self.assertEqual((r["outcome"], r["proposed_status"]), ("confirmed", "proved"))
        self.assertEqual(r["dropped_definitions"], [self.D])
        r = dt.decide(arec(add="paper:lem:x2", modulo=self.D),
                      amrec(amended="paper:lem:x2"), kind_of=self.KINDS.get,
                      tags_of=lambda q: None, established=["paper:lem:x2"])
        self.assertEqual((r["outcome"], r["modulo"]),
                         ("confirmed-modulo", [self.D, "paper:lem:x2"]))
        self.assertEqual([i["kind"] for i in r["file_items"]], ["definition-input"])

    # nit (d): an open [CHECK] on a definition is not kept past the settler's case-9 stop
    def test_a_definition_with_an_open_check_goes_to_the_settler(self):
        r = self.run_(self.D + " [CHECK]", "none")
        self.assertEqual(r["outcome"], "settle-dependencies")
        self.assertEqual(r["kept_definitions"], [])
        (f,) = r["differing_inputs"]
        self.assertEqual((f["input"], f["open_check"], f["definition"]),
                         (self.D + " [CHECK]", True, True))

    # residual R1 (re-review of e800543): the tag is read on the definition's head
    def test_a_tagged_definition_with_pointer_text_is_dropped(self):
        tags = {self.D: ["notation-only"]}
        r = self.run_(self.D + " (item 2)", "none", tags=tags)
        self.assertEqual((r["outcome"], r["proposed_status"]), ("confirmed", "proved"))
        self.assertEqual((r["dropped_definitions"], r["kept_definitions"]), ([self.D], []))
        self.assertEqual(r["file_items"], [])

    # residual R2: a shared definition with an open [CHECK] is no verify ticket
    def test_a_shared_definition_with_an_open_check_is_a_decision_not_a_verify(self):
        r = self.run_(self.D + " [CHECK T-9]", self.D + " [CHECK T-9]")
        self.assertEqual((r["outcome"], r["proposed_status"]),
                         ("confirmed-modulo", "proved-modulo"))
        (it,) = r["file_items"]
        self.assertEqual((it["kind"], it["definition"]), ("definition-check", self.D))
        route = it["route"]
        self.assertEqual((route["kind"], route["to_role"], route["once"]),
                         ("decision", "human", True))
        self.assertEqual(route["title"], "Definition check: %s [CHECK T-9]" % self.D)
        self.assertIn("[CHECK", route["ask"])
        self.assertFalse(r["recolour"])
        # a lemma with the same mark is still a verify-input
        r = self.run_("paper:lem:a [CHECK]", "paper:lem:a [CHECK]")
        self.assertEqual([i["kind"] for i in r["file_items"]], ["verify-input"])


class BasePassOnAnotherBranchTests(unittest.TestCase):
    """#130: a base pass committed on a forked ticket branch was reported as "has no
    decision.md"; the note now names the branch that holds it."""

    def git(self, *args):
        import subprocess
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        subprocess.run(["git", "-C", self.repo] + list(args), check=True, env=env,
                       capture_output=True)

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = self._tmp.name
        self.git("init", "-q", "-b", "main")
        self.d = os.path.join(self.repo, "reviews", "paper", "lem-x", "2026-11-23-T-1957")
        os.makedirs(self.d)
        for f in ("A.md", "B.md"):
            with open(os.path.join(self.d, f), "w") as fh:
                fh.write("run\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "runs")
        self.git("switch", "-q", "-c", "2026-11-23/t-1957/expert")
        with open(os.path.join(self.d, "decision.md"), "w") as fh:
            fh.write("decision\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "decision")
        self.git("switch", "-q", "main")

    def test_the_note_names_the_branch_holding_the_decision(self):
        self.assertEqual(dt.branches_holding(self.d), ["2026-11-23/t-1957/expert"])
        _a, _b, notes = dt.base_records(None, "x", self.d)
        self.assertIn("has no decision.md", notes[0])
        self.assertIn("complete on 2026-11-23/t-1957/expert", notes[0])

    def test_a_missing_folder_names_it_too(self):
        self.git("switch", "-q", "--orphan", "empty")
        import shutil
        shutil.rmtree(os.path.join(self.repo, "reviews"), ignore_errors=True)
        _a, _b, notes = dt.base_records(None, "x", self.d)
        self.assertIn("folder", notes[0])
        self.assertIn("2026-11-23/t-1957/expert", notes[0])

    def test_a_reword_base_on_another_branch_is_named(self):
        # #127 with #130: a chain's reword link holds R.md and decision.md, no A or B
        r = os.path.join(self.repo, "reviews", "paper", "lem-x", "2026-11-24-T-1960")
        os.makedirs(r)
        with open(os.path.join(r, "R.md"), "w") as fh:
            fh.write("run\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "reword run")
        self.git("switch", "-q", "-c", "2026-11-24/t-1960/expert")
        with open(os.path.join(r, "decision.md"), "w") as fh:
            fh.write("decision\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "reword decision")
        self.git("switch", "-q", "main")
        self.assertIn("complete on 2026-11-24/t-1960/expert", dt.elsewhere(r))

    def test_no_note_when_the_checkout_has_it_or_no_branch_does(self):
        self.git("switch", "-q", "2026-11-23/t-1957/expert")
        self.assertEqual(dt.branches_holding(self.d), [])
        self.git("switch", "-q", "main")
        self.git("branch", "-q", "-D", "2026-11-23/t-1957/expert")
        self.assertEqual(dt.branches_holding(self.d), [])
        self.assertEqual(dt.elsewhere(self.d), "")


def irec(verdict, items, run="A", hyps="H1, H2", **kw):
    """A run with an ``items:`` line (#127) and ``hypotheses_used``."""
    r = rec(verdict, run=run, **kw)
    r["items"], r["item_problems"] = dt.parse_items(items)
    r["hypotheses_used"] = [h.strip() for h in hyps.split(",") if h.strip()]
    return r


REG = {"hash": "abc123", "items": {"C1": {"hash": "h1" * 8, "status": "sketch"},
                                   "C2": {"hash": "h2" * 8, "status": "sketch"},
                                   "C3": {"hash": "h3" * 8, "status": "sketch"}}}


def items_of(_qid):
    return REG


class ItemTests(unittest.TestCase):
    """#127: the table per item, the whole outcome derived from the items'."""

    def test_parse_items_line(self):
        r = dt.parse_record(
            "VERDICT\nsubject: paper:prop:x\nverdict: GAP\nitems: C1 CONFIRMED; it:c2 "
            "CONFIRMED modulo paper:lem:x, bib:AW21#Thm1.3; C3: GAP\n"
            "hypotheses_used: H1, H3\n")
        self.assertEqual(r["items"], {
            "C1": {"verdict": "CONFIRMED", "modulo": []},
            "c2": {"verdict": "CONFIRMED", "modulo": ["paper:lem:x", "bib:AW21#Thm1.3"]},
            "C3": {"verdict": "GAP", "modulo": []}})
        self.assertEqual(r["hypotheses_used"], ["H1", "H3"])
        self.assertEqual(r["item_problems"], [])
        bad = dt.parse_record("VERDICT\nverdict: GAP\nitems: C1 maybe; C2 GAP extra\n")
        self.assertEqual(len(bad["item_problems"]), 2)
        self.assertFalse(bad["problems"])      # the whole verdict still reads

    def test_every_item_confirmed_is_confirmed(self):
        it = "C1 CONFIRMED; C2 CONFIRMED; C3 CONFIRMED"
        r = dt.decide(irec("CONFIRMED", it), irec("CONFIRMED", it, run="B"),
                      items_of=items_of)
        self.assertEqual(r["outcome"], "confirmed")
        self.assertEqual(r["proposed_items"],
                         {"C1": ["proved"], "C2": ["proved"], "C3": ["proved"]})
        self.assertEqual(r["items"]["C2"]["grounds"]["item"], "C2")
        self.assertEqual(r["items"]["C2"]["grounds"]["item_hash"], "h2" * 8)

    def test_one_item_modulo_keeps_the_others_proved(self):
        it = "C1 CONFIRMED; C2 CONFIRMED modulo paper:lem:y; C3 CONFIRMED"
        r = dt.decide(irec("CONFIRMED", it, modulo="paper:lem:y"),
                      irec("CONFIRMED", it, run="B", modulo="paper:lem:y"),
                      items_of=items_of)
        self.assertEqual(r["outcome"], "confirmed-modulo")
        self.assertEqual(r["modulo"], ["paper:lem:y"])
        self.assertEqual(r["proposed_items"], {"C1": ["proved"],
                                               "C2": ["proved-modulo", "paper:lem:y"],
                                               "C3": ["proved"]})
        self.assertEqual(r["grounds"]["modulo"], ["paper:lem:y"])

    def test_a_gap_on_one_item_holds_only_that_item(self):
        # A: GAP overall (C3), CONFIRMED on C1 and C2: B is launched for the items
        ra = irec("GAP", "C1 CONFIRMED; C2 CONFIRMED; C3 GAP", blocking="step 4")
        self.assertTrue(dt.should_launch_b(ra))
        r = dt.decide(ra, items_of=items_of)
        self.assertEqual(r["outcome"], "awaiting-b")
        self.assertTrue(r["launch_b"])
        rb = irec("CONFIRMED", "C1 CONFIRMED; C2 CONFIRMED; C3 CONFIRMED", run="B")
        r = dt.decide(ra, rb, items_of=items_of)
        self.assertEqual(r["outcome"], "per-item")
        self.assertIsNone(r["proposed_status"])
        self.assertEqual(r["items"]["C3"]["outcome"], "single-negative")
        self.assertEqual(r["proposed_items"], {"C1": ["proved"], "C2": ["proved"]})
        self.assertEqual([i["item"] for i in r["file_items"]], ["C3"])
        self.assertIn("step 4", r["file_items"][0]["text"])

    def test_a_run_without_items_falls_back_to_the_whole_statement(self):
        r = dt.decide(rec("CONFIRMED"), rec("CONFIRMED", run="B"), items_of=items_of)
        self.assertEqual(r["outcome"], "confirmed")
        self.assertNotIn("items", r)
        self.assertIn("decided on the whole statement", r["items_note"])
        # one run with items, one without: the same fallback
        it = "C1 CONFIRMED; C2 CONFIRMED; C3 CONFIRMED"
        r = dt.decide(irec("CONFIRMED", it), rec("CONFIRMED", run="B"), items_of=items_of)
        self.assertEqual(r["outcome"], "confirmed")
        self.assertIn("gave no `items:` entry", r["items_note"])

    def test_a_moved_statement_gives_item_grounds_without_item_hash(self):
        it = "C1 CONFIRMED; C2 CONFIRMED; C3 CONFIRMED"
        r = dt.decide(irec("CONFIRMED", it, h="old999"),
                      irec("CONFIRMED", it, run="B", h="old999"), items_of=items_of)
        self.assertNotIn("item_hash", r["items"]["C1"]["grounds"])
        self.assertTrue(any("statement changed since the runs" in a for a in r["anomalies"]))

    def test_unrecorded_items_without_registry(self):
        it = "C1 CONFIRMED; C2 GAP"
        r = dt.decide(irec("GAP", it, blocking="x"), irec("CONFIRMED", it, run="B"))
        self.assertEqual(r["outcome"], "per-item")
        self.assertNotIn("item_hash", r["items"]["C1"]["grounds"])
