"""settle_deps.py: a dependency-settler record checked against the human's cases and their
fixed order (#121, 2026-11-20), and applied."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
sys.path.insert(0, SCRIPTS)
import settle_deps as sd  # noqa: E402


def fact(inp, run="A", shape="id", result=None, exists=True, open_check=False, cycle=False):
    return {"input": inp, "run": run, "shape": shape,
            "result": inp if result is None else result, "pointer": False,
            "open_check": open_check, "exists": exists, "cycle": cycle}


def table(*facts, modulo=()):
    return {"outcome": "settle-dependencies", "modulo": list(modulo),
            "differing_inputs": list(facts)}


def entry(inp, case, **kw):
    e = {"input": inp, "case": case, "chosen": "", "sources": [], "line": "",
         "remark": "", "evidence": "q"}
    e.update(kw)
    return e


def rec(*entries, differ=False, evidence=""):
    return {"readings": {"differ": differ, "evidence": evidence}, "inputs": list(entries)}


class CaseTests(unittest.TestCase):
    def ok(self, r, t):
        self.assertEqual([], sd.check(r, t))
        return sd.apply(r, t)

    def bad(self, r, t, word):
        probs = sd.check(r, t)
        self.assertTrue(probs, "expected a problem")
        self.assertTrue(any(word in p for p in probs), probs)

    def test_case_12_stops_the_pass_and_needs_evidence(self):
        t = table(fact("paper:lem:x"))
        out = self.ok(rec(differ=True, evidence="A reads labelled, B unlabelled"), t)
        self.assertEqual("disagreement", out["outcome"])
        self.assertEqual(12, out["stops"][0]["case"])
        self.bad(rec(differ=True), t, "case 12")

    def test_case_11_is_forced_by_a_cycle_and_needs_one(self):
        t = table(fact("paper:lem:y", cycle=True, shape="cycle"))
        out = self.ok(rec(entry("paper:lem:y", 11)), t)
        self.assertEqual("disagreement", out["outcome"])
        self.bad(rec(entry("paper:lem:y", 1, chosen="paper:lem:y")), t, "case 11")
        t2 = table(fact("paper:lem:y"))
        self.bad(rec(entry("paper:lem:y", 11)), t2, "needs the registry cycle")

    def test_case_9_is_forced_by_an_open_check(self):
        t = table(fact("bib:AW21#2 [CHECK T-1144]", shape="check", result="",
                       exists=False, open_check=True))
        out = self.ok(rec(entry("bib:AW21#2 [CHECK T-1144]", 9)), t)
        self.assertEqual("disagreement", out["outcome"])
        # an open CHECK is never settled as a duplicate source (T-1463)
        self.bad(rec(entry("bib:AW21#2 [CHECK T-1144]", 2, chosen="x", sources=["x", "y"])),
                 t, "case 9")

    def test_case_9_by_judgement_needs_evidence(self):
        t = table(fact("paper:lem:x"))
        self.ok(rec(entry("paper:lem:x", 9, evidence="hypothesis (H2) of lem:x unchecked")), t)
        self.bad(rec(entry("paper:lem:x", 9, evidence="")), t, "case 9")

    def test_case_10_free_text_is_pending_with_a_cite_ticket(self):
        t = table(fact("(T0) Hausdorff topology (uncited)", shape="text", result="",
                       exists=False), modulo=["paper:lem:z"])
        out = self.ok(rec(entry("(T0) Hausdorff topology (uncited)", 10)), t)
        self.assertEqual("confirmed-settled", out["outcome"])
        self.assertEqual("proved-modulo", out["proposed_status"])
        self.assertIn("(T0) Hausdorff topology (uncited)", out["modulo"])
        self.assertEqual(1, len(out["cite"]))
        self.bad(rec(entry("(T0) Hausdorff topology (uncited)", 10, chosen="x")), t, "case 10")

    def test_no_shown_result_cannot_take_a_later_keeping_case(self):
        t = table(fact("check:T-1033#Fix", shape="unshown", exists=False))
        self.bad(rec(entry("check:T-1033#Fix", 1, chosen="check:T-1033#Fix")), t,
                 "case 10 (missing source) applies before")
        # dropping it as formal or spurious is still possible
        self.ok(rec(entry("check:T-1033#Fix", 14, line="l.12: by definition")), t)

    def test_case_14_formal_input_is_dropped_and_can_leave_proved(self):
        t = table(fact("s1:GEO-55"))
        out = self.ok(rec(entry("s1:GEO-55", 14, line="l.4: the identification is "
                                                       "notational")), t)
        self.assertEqual("confirmed-settled", out["outcome"])
        self.assertEqual("proved", out["proposed_status"])
        self.assertEqual([], out["modulo"])
        self.bad(rec(entry("s1:GEO-55", 14)), t, "proof line")
        self.bad(rec(entry("s1:GEO-55", 14, line="l.4", chosen="s1:GEO-55")), t,
                 "chosen must be empty")

    def test_case_6_spurious_is_dropped(self):
        t = table(fact("paper:defn:x"), modulo=["paper:lem:a"])
        out = self.ok(rec(entry("paper:defn:x", 6, line="not used in steps 1-3")), t)
        self.assertEqual(["paper:lem:a"], out["modulo"])

    def test_case_5_keeps_or_drops_the_route(self):
        t = table(fact("paper:lem:a"), fact("paper:lem:b", run="B"))
        out = self.ok(rec(entry("paper:lem:a", 5, chosen="paper:lem:a", line="step 2"),
                          entry("paper:lem:b", 5, line="B's own route")), t)
        self.assertEqual(["paper:lem:a"], out["modulo"])
        self.assertEqual("paper:lem:b", out["dropped"][0]["input"])

    def test_case_7_declares_or_is_a_gap(self):
        t = table(fact("paper:lem:hidden", run="B"))
        out = self.ok(rec(entry("paper:lem:hidden", 7, chosen="paper:lem:hidden")), t)
        self.assertEqual("paper:lem:hidden", out["declarations"][0]["dependency"])
        gap = self.ok(rec(entry("paper:lem:hidden", 7)), t)
        self.assertEqual("disagreement", gap["outcome"])

    def test_case_1_folklore_takes_a_named_dependency(self):
        t = table(fact("bib:KS00#Thm1", shape="card", exists=None, run="B"))
        out = self.ok(rec(entry("bib:KS00#Thm1", 1, chosen="bib:KS00#Thm1")), t)
        self.assertIn("bib:KS00#Thm1", out["modulo"])
        self.assertEqual("bib:KS00#Thm1", out["declarations"][0]["dependency"])
        self.bad(rec(entry("bib:KS00#Thm1", 1, chosen="bib:OTHER")), t, "case 1")
        self.bad(rec(entry("bib:KS00#Thm1", 1)), t, "case 1")

    def test_case_2_routine_names_all_sources_and_keeps_one(self):
        t = table(fact("bib:A#1", shape="card", exists=None),
                  fact("bib:B#2", run="B", shape="card", exists=None))
        srcs = ["bib:A#1", "bib:B#2"]
        out = self.ok(rec(entry("bib:A#1", 2, chosen="bib:A#1", sources=srcs),
                          entry("bib:B#2", 2, chosen="bib:A#1", sources=srcs)), t)
        self.assertEqual(["bib:A#1"], out["modulo"])
        self.assertEqual("routine", out["notes"][0]["kind"])
        self.bad(rec(entry("bib:A#1", 2, chosen="bib:A#1", sources=["bib:A#1"]),
                     entry("bib:B#2", 2, chosen="bib:A#1", sources=srcs)), t, "at least two")
        self.bad(rec(entry("bib:A#1", 2, chosen="bib:A#1", sources=srcs),
                     entry("bib:B#2", 2, chosen="bib:B#2", sources=srcs)), t,
                 "keep one")

    def test_case_3_needs_a_remark(self):
        t = table(fact("bib:A#1", shape="card", exists=None),
                  fact("bib:B#2", run="B", shape="card", exists=None))
        srcs = ["bib:A#1", "bib:B#2"]
        out = self.ok(rec(entry("bib:A#1", 3, chosen="bib:A#1", sources=srcs,
                                remark="also [B, Thm 2] in the compact setting"),
                          entry("bib:B#2", 3, chosen="bib:A#1", sources=srcs,
                                remark="also [B, Thm 2] in the compact setting")), t)
        self.assertEqual("remark", out["notes"][0]["kind"])
        self.bad(rec(entry("bib:A#1", 3, chosen="bib:A#1", sources=srcs),
                     entry("bib:B#2", 3, chosen="bib:A#1", sources=srcs)), t, "remark")

    def test_case_8_chooses_a_weaker_result(self):
        t = table(fact("bib:BIG#Thm", shape="card", exists=None),
                  fact("paper:lem:small", run="B"))
        out = self.ok(rec(entry("bib:BIG#Thm", 8, chosen="paper:lem:small"),
                          entry("paper:lem:small", 5, chosen="paper:lem:small",
                                line="step 3")), t)
        self.assertEqual(["paper:lem:small"], out["modulo"])
        self.bad(rec(entry("bib:BIG#Thm", 8, chosen="bib:BIG#Thm"),
                     entry("paper:lem:small", 5, chosen="paper:lem:small", line="s")),
                 t, "case 8")


class ReviewOf09eda00Tests(unittest.TestCase):
    """The review of 09eda00: what the checker accepted and should not."""
    A = fact("paper:lem:a")
    B = fact("paper:lem:b", run="B")

    def probs(self, *entries, t=None):
        return sd.check(rec(*entries), t or table(self.A, self.B))

    def test_sources_and_chosen_must_be_listed(self):
        p = self.probs(entry("paper:lem:a", 2, chosen="paper:lem:ghost",
                             sources=["paper:lem:ghost", "paper:lem:ghost2"]),
                       entry("paper:lem:b", 6, line="l"))
        self.assertTrue(any("no run lists" in x for x in p), p)
        self.assertTrue(any("include the input itself" in x for x in p), p)
        p = self.probs(entry("paper:lem:a", 8, chosen="made up free text"),
                       entry("paper:lem:b", 6, line="l"))
        self.assertTrue(any("case 8" in x for x in p), p)

    def test_one_step_keeps_one_source_across_cases(self):
        srcs = ["paper:lem:a", "paper:lem:b"]
        for b in (entry("paper:lem:b", 5, chosen="paper:lem:b", line="l"),
                  entry("paper:lem:b", 3, chosen="paper:lem:b", sources=srcs, remark="r")):
            p = self.probs(entry("paper:lem:a", 2, chosen="paper:lem:a", sources=srcs), b)
            self.assertTrue(any("keep one" in x for x in p), (b, p))

    def test_nothing_kept_is_dropped_elsewhere(self):
        p = self.probs(entry("paper:lem:a", 8, chosen="paper:lem:b"),
                       entry("paper:lem:b", 6, line="l"))
        self.assertTrue(any("another entry drops" in x for x in p), p)

    def test_case_5_keeps_one_route(self):
        p = self.probs(entry("paper:lem:a", 5, line="l"), entry("paper:lem:b", 5, line="l"))
        self.assertTrue(any("keeps the route" in x for x in p), p)

    def test_case_10_on_a_shown_result_is_refused(self):
        p = sd.check(rec(entry("paper:lem:a", 10)), table(self.A))
        self.assertTrue(any("not a missing source" in x for x in p), p)

    def test_malformed_fields_are_problems_not_crashes(self):
        for bad in ({"sources": 5}, {"sources": "ab"}, {"line": ["x"]}, {"chosen": 0}):
            e = dict(entry("paper:lem:a", 6, line="l"), **bad)
            p = sd.check(rec(e), table(self.A))
            self.assertTrue(p, bad)
        for t in ([1, 2], {"outcome": "settle-dependencies", "differing_inputs": [5, "x"]},
                  {"outcome": "settle-dependencies", "modulo": 5, "differing_inputs": []}):
            sd.check(rec(), t)                    # no exception

    def test_only_cases_7_1_8_declare(self):
        srcs = ["paper:lem:a", "paper:lem:b"]
        out = sd.apply(rec(entry("paper:lem:a", 2, chosen="paper:lem:a", sources=srcs),
                           entry("paper:lem:b", 2, chosen="paper:lem:a", sources=srcs)),
                       table(self.A, self.B))
        self.assertEqual([], out["declarations"])


class RecordShapeTests(unittest.TestCase):
    def test_one_entry_per_differing_input_no_extras_no_duplicates(self):
        t = table(fact("paper:lem:a"), fact("paper:lem:b", run="B"))
        probs = sd.check(rec(entry("paper:lem:a", 6, line="l")), t)
        self.assertTrue(any("not classified" in p for p in probs))
        probs = sd.check(rec(entry("paper:lem:a", 6, line="l"), entry("paper:lem:a", 6, line="l"),
                             entry("paper:lem:b", 6, line="l")), t)
        self.assertTrue(any("twice" in p for p in probs))
        probs = sd.check(rec(entry("paper:lem:zz", 6, line="l")), table(fact("paper:lem:a")))
        self.assertTrue(any("not a differing input" in p for p in probs))

    def test_mechanical_and_unknown_cases_are_refused(self):
        t = table(fact("paper:lem:a"))
        for case, word in ((13, "mechanical"), (4, "mechanical"), (12, "pass-level"),
                           (15, "not one of"), ("2", "not a case"), (True, "not a case")):
            probs = sd.check(rec(entry("paper:lem:a", case)), t)
            self.assertTrue(any(word in p for p in probs), (case, probs))

    def test_only_a_settle_dependencies_table_is_settled(self):
        self.assertIn("nothing to settle", sd.check(rec(), {"outcome": "confirmed"})[0])

    def test_a_stop_wins_over_settled_inputs(self):
        t = table(fact("paper:lem:a"), fact("bib:X#1 [CHECK T-1]", run="B", shape="check",
                                            result="", exists=False, open_check=True))
        out = sd.apply(rec(entry("paper:lem:a", 14, line="l"),
                           entry("bib:X#1 [CHECK T-1]", 9)), t)
        self.assertEqual("disagreement", out["outcome"])
        self.assertIsNone(out["proposed_status"])


class StageOrderTests(unittest.TestCase):
    def test_every_record_case_has_a_stage_and_the_stages_follow_the_ruling(self):
        self.assertEqual(sorted(sd.RECORD_CASES + sd.MECHANICAL + (12,)), list(range(1, 15)))
        order = [12, 11, 9, 10, 14, 6, 5, 7, 1, 2, 3, 8]
        stages = [sd.STAGE[c] for c in order]
        self.assertEqual(stages, sorted(stages))


class CliTests(unittest.TestCase):
    def run_cli(self, action, r, t):
        with tempfile.TemporaryDirectory() as d:
            rp, tp = os.path.join(d, "S.json"), os.path.join(d, "t.json")
            for path, data in ((rp, r), (tp, t)):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            p = subprocess.run([sys.executable, os.path.join(SCRIPTS, "settle_deps.py"),
                                action, rp, "--table", tp], capture_output=True, text=True)
        return p.returncode, json.loads(p.stdout)

    def test_check_and_apply(self):
        t = table(fact("s1:GEO-55"))
        good = rec(entry("s1:GEO-55", 14, line="l.4"))
        self.assertEqual((0, True), (lambda c, o: (c, o["ok"]))(*self.run_cli("check", good, t)))
        code, out = self.run_cli("apply", good, t)
        self.assertEqual((0, "proved"), (code, out["proposed_status"]))
        code, out = self.run_cli("apply", rec(entry("s1:GEO-55", 14)), t)
        self.assertEqual(1, code)
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()
