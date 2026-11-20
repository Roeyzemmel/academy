"""A ruling the human answers files its follow-up by code (#121 item 4).

A ruling ticket is a ``decision`` ticket from an Expert to the human about the inputs of
a review pass whose two runs are both CONFIRMED (verify's ``disagreement`` on the modulo
lists). Recording the human's answer with ``decisions.py record`` files the keeper's
``decision`` ticket (the claim, the chosen modulo, the pass's verdict files as grounds)
in the same step, names it on the ruling, and files nothing on a second record.

Run from the repo root:  py -m unittest discover -s academy/tests -t academy/tests -p test_rulings.py
"""

import importlib.util
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import decisions as dc  # noqa: E402
import rulings as rl  # noqa: E402
_spec = importlib.util.spec_from_file_location(   # scripts/registry.py shadows the package
    "_grounds_under_test", os.path.join(PLUGIN, "registry", "core", "grounds.py"))
_grounds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_grounds)
check_grounds = _grounds.check_grounds
from test_decisions import DecisionsCase, DATE  # noqa: E402

SUBJECT = "paper:lem:x"
HASH = "8f853138ca7af4f3"
PASS = "2026-11-15-T-0001"


def record_text(run, verdict="CONFIRMED", modulo="", run_id=None, subject=SUBJECT,
                hash_=HASH, pass_=PASS):
    return ("---\nsubject: %s\npass: %s\nrun: %s\nrun_id: %s\nverdict: %s\nmodulo: %s\n"
            "model: claude-opus-5-5\nstatement_hash: %s\nblocking:\ngap_class:\nticket: T-0001\n"
            "agent: expert:rigor-reviewer\nlanded: 2026-11-15\n---\n\n**Verdict.**\n"
            % (subject, pass_, run, run_id or "rv-%s-%s" % (pass_, run), verdict, modulo,
               hash_))


class RulingCase(DecisionsCase):
    """A verify ticket T-0001, its pass with A and B, and the ruling ticket T-0002."""

    A_MODULO = "[paper:lem:rigid, paper:cor:locus, Notation identifications (l.1306, uncited)]"
    B_MODULO = "paper:lem:rigid, lem:locus2, paper:cor:locus"

    def setUp(self):
        super().setUp()
        self.ticket(to="expert@main", title="verify lem:x", refs=[SUBJECT])   # T-0001
        self.write_pass()

    def write_pass(self, a=None, b=None, pass_=PASS, slug="lem-x"):
        d = os.path.join(self.ws["instances"]["expert@main"]["home"], "reviews", "paper",
                         slug, pass_)
        os.makedirs(d, exist_ok=True)
        for name, text in (("A.md", a or record_text("A", modulo=self.A_MODULO, pass_=pass_)),
                           ("B.md", b or record_text("B", modulo=self.B_MODULO, pass_=pass_))):
            with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        return d

    def ruling(self, body_path=True, parent="T-0001", **kw):
        detail = ("decision_table.py gives disagreement on the inputs. Record: "
                  "library/reviews/paper/lem-x/%s/decision.md." % PASS) if body_path else (
                  "decision_table.py gives disagreement on the modulo inputs.")
        args = dict(to="human", as_instance="expert@main", kind="decision",
                    title="Ruling: modulo inputs of lem:x", parent=parent,
                    ask="Rule on the runs' differing modulo lists on lem:x?",
                    deliverable="A ruling: union, intersection or re-run.",
                    refs=[SUBJECT, "T-0001", "P-0007"], detail=detail)
        args.update(kw)
        path = self.ticket(**args)
        return bd.read_ticket(path)[0]["id"]

    def record(self, tid, choice, comment="", **kw):
        return dc.record(self.board, tid, choice, comment, workspace=self.ws, date=DATE, **kw)

    def tickets(self):
        return {m["id"]: m for m in bd.list_tickets(self.board, include_terminal=True)}

    def thread(self, tid):
        return [t for _d, _w, t in ac.thread_lines(bd.get_ticket(self.board, tid)[2])]


class TestFindRuling(RulingCase):
    def test_a_ruling_on_two_confirmed_runs_is_read_with_its_options(self):
        tid = self.ruling()
        r = rl.find_ruling(self.board, tid, self.ws)
        self.assertEqual(SUBJECT, r["subject"])
        self.assertEqual(PASS, r["pass"])
        self.assertEqual(HASH, r["statement_hash"])
        self.assertEqual(["paper:lem:rigid", "paper:cor:locus",
                          "Notation identifications (l.1306, uncited)", "paper:lem:locus2"],
                         r["union"])
        self.assertEqual(["paper:lem:rigid", "paper:cor:locus"], r["intersection"])
        self.assertEqual(["file:expert@main/reviews/paper/lem-x/%s/A.md" % PASS,
                          "file:expert@main/reviews/paper/lem-x/%s/B.md" % PASS],
                         [v["ref"] for v in r["verdicts"]])

    def test_the_pass_is_found_through_the_parent_when_the_text_names_none(self):
        tid = self.ruling(body_path=False)
        self.assertEqual(PASS, rl.find_ruling(self.board, tid, self.ws)["pass"])

    def test_the_pass_is_found_through_a_file_ref(self):
        tid = self.ruling(body_path=False, parent=None,
                          refs=[SUBJECT, "file:expert@main/reviews/paper/lem-x/%s/decision.md" % PASS])
        self.assertEqual(PASS, rl.find_ruling(self.board, tid, self.ws)["pass"])

    def test_a_pass_with_a_run_not_confirmed_is_no_ruling(self):
        self.write_pass(b=record_text("B", verdict="GAP", modulo=self.B_MODULO))
        tid = self.ruling()
        self.assertIsNone(rl.find_ruling(self.board, tid, self.ws))

    def test_runs_on_different_hashes_or_one_run_id_are_no_ruling(self):
        self.write_pass(b=record_text("B", modulo=self.B_MODULO, hash_="0000000000000000"))
        self.assertIsNone(rl.find_ruling(self.board, self.ruling(), self.ws))
        self.write_pass(b=record_text("B", modulo=self.B_MODULO, run_id="rv-%s-A" % PASS))
        self.assertIsNone(rl.find_ruling(self.board, "T-0002", self.ws))

    def test_identical_lists_are_no_ruling(self):
        """Point 1 of the review: nothing to rule on when the lists agree."""
        self.write_pass(a=record_text("A", modulo="paper:lem:rigid, lem:locus2"),
                        b=record_text("B", modulo="paper:lem:locus2, paper:lem:rigid"))
        self.assertIsNone(rl.find_ruling(self.board, self.ruling(), self.ws))

    def test_the_table_s_reduced_lists_are_used_when_present(self):
        d = self.write_pass()
        with open(os.path.join(d, "S-table.json"), "w", encoding="utf-8") as fh:
            json.dump({"outcome": "settle-dependencies", "modulo": ["paper:lem:rigid"],
                       "differing_inputs": [{"input": "paper:lem:locus2", "run": "B"}],
                       "dropped_inputs": [{"input": "paper:cor:locus", "via": "paper:lem:rigid",
                                           "case": 4}]}, fh)
        tid = self.ruling()
        r = rl.find_ruling(self.board, tid, self.ws)
        self.assertEqual((["paper:lem:rigid", "paper:lem:locus2"], ["paper:lem:rigid"]),
                         (r["union"], r["intersection"]))
        out = self.record(tid, "a")
        body = bd.get_ticket(self.board, out["follow_up"])[2]
        self.assertEqual(["paper:lem:rigid", "paper:lem:locus2"], rl.grounds_in(body)["modulo"])
        self.assertIn("dropped mechanically [paper:cor:locus]", body)

    def write_settler(self, record):
        d = self.write_pass()
        with open(os.path.join(d, "S.json"), "w", encoding="utf-8") as fh:
            json.dump(record, fh)

    def test_a_settler_stop_with_no_status_offers_only_rerun_and_decline(self):
        """Point 5: case 12 (and 11, and 7 with no result) leave no status to give."""
        for rec in ({"readings": {"differ": True, "evidence": "A reads X open, B closed"}},
                    {"readings": {"differ": False}, "inputs": [
                        {"input": "paper:lem:locus2", "case": 11, "evidence": "cycle"}]},
                    {"readings": {"differ": False}, "inputs": [
                        {"input": "paper:lem:locus2", "case": 7, "chosen": "",
                         "evidence": "no result"}]}):
            self.write_settler(rec)
            tid = self.ruling()
            r = rl.find_ruling(self.board, tid, self.ws)
            self.assertTrue(r["no_status"])
            self.assertEqual(["(c) Re-run", "(d) Decline"], [o["label"] for o in rl.options(r)])
            with self.assertRaises(ac.AcademyError):
                self.record(tid, "a")
        out = self.record(tid, "c")
        k = bd.get_ticket(self.board, out["follow_up"])
        self.assertEqual("verify", k[1]["kind"])
        self.assertIn("no result", k[2])

    def test_a_case_9_stop_keeps_the_four_options_and_is_quoted(self):
        self.write_settler({"readings": {"differ": False}, "inputs": [
            {"input": "paper:lem:locus2", "case": 9, "evidence": "open [CHECK] T-1144"}]})
        tid = self.ruling()
        r = rl.find_ruling(self.board, tid, self.ws)
        self.assertEqual(4, len(rl.options(r)))
        out = self.record(tid, "a")
        self.assertIn("open [CHECK] T-1144", bd.get_ticket(self.board, out["follow_up"])[2])

    def test_a_plain_decision_ticket_to_the_human_is_no_ruling(self):
        self.ticket(to="human", as_instance="expert@main", kind="decision", title="Redeploy?",
                    ask="Redeploy fsq.sh?", refs=[])
        self.assertIsNone(rl.find_ruling(self.board, "T-0002", self.ws))

    def test_a_ruling_from_a_role_other_than_the_expert_is_no_ruling(self):
        tid = self.ruling(as_instance="author@main")
        self.assertIsNone(rl.find_ruling(self.board, tid, self.ws))

    def test_pending_decisions_offer_the_ruling_options(self):
        tid = self.ruling()
        item = [i for i in dc.pending_decisions(self.board, workspace=self.ws)
                if i["id"] == tid][0]
        labels = [o["label"] for o in item["options"]]
        self.assertEqual(["(a) Union", "(b) Intersection", "(c) Re-run", "(d) Decline"], labels)
        self.assertIn("paper:lem:locus2", item["options"][0]["description"])
        self.assertNotIn("paper:lem:locus2", item["options"][1]["description"])
        self.assertEqual(SUBJECT, item["ruling"]["subject"])


class TestRecordRuling(RulingCase):
    def test_union_files_the_keeper_ticket_in_the_same_step_and_the_ruling_names_it(self):
        tid = self.ruling()
        before = set(self.tickets())
        out = self.record(tid, "a", comment="union of inputs")
        new = sorted(set(self.tickets()) - before)
        self.assertEqual(1, len(new))
        k = self.tickets()[new[0]]
        self.assertEqual((new[0], True), (out["follow_up"], out["filed"]))
        self.assertEqual(("decision", "human", "researcher@r1", tid),
                         (k["kind"], k["from"], k["to"], k["parent"]))
        for ref in (SUBJECT, tid, "P-0007",
                    "file:expert@main/reviews/paper/lem-x/%s/A.md" % PASS):
            self.assertIn(ref, k["refs"])
        self.assertIn("proved-modulo", k["ask"])
        _p, _m, body = bd.get_ticket(self.board, new[0])
        grounds = rl.grounds_in(body)
        self.assertEqual(["paper:lem:rigid", "paper:cor:locus",
                          "Notation identifications (l.1306, uncited)", "paper:lem:locus2"],
                         grounds["modulo"])
        ok, why = check_grounds("proved-modulo", grounds, HASH)
        self.assertTrue(ok, why)
        self.assertIn("union of inputs", body)                     # the human's words, quoted
        meta = bd.get_ticket(self.board, tid)[1]
        self.assertEqual("delivered", meta["status"])
        self.assertIn(new[0], meta["result"])
        self.assertTrue(any(new[0] in t and "keeper follow-up" in t for t in self.thread(tid)))
        self.assertEqual([], ac.validate_ticket(meta, bd.get_ticket(self.board, tid)[2]))

    def test_a_second_record_files_nothing_new(self):
        tid = self.ruling()
        first = self.record(tid, "a")
        n, thread = len(self.tickets()), self.thread(tid)
        again = self.record(tid, "a")
        self.assertEqual((first["follow_up"], False), (again["follow_up"], again["filed"]))
        self.assertEqual(n, len(self.tickets()))
        self.assertEqual(thread, self.thread(tid))

    def test_a_follow_up_filed_before_an_interruption_is_found_not_filed_again(self):
        """Point 3 of the review: the follow-up was filed, then the line and the delivery
        were lost; the next record completes them and files nothing new."""
        tid = self.ruling()
        bd.append_to_ticket(self.board, tid, "human decision: (a) union", date=DATE)
        self.ticket(to="researcher@r1", as_instance="human", kind="decision", parent=tid,
                    title="Status of paper:lem:x -> proved-modulo (ruling %s)" % tid,
                    ask="Set it.")
        self.assertEqual([tid], [x["id"] for x in rl.stalled(self.board, self.ws)])
        n = len(self.tickets())
        out = self.record(tid, "a")
        self.assertEqual((False, n, "T-0003"), (out["filed"], len(self.tickets()),
                                                out["follow_up"]))
        self.assertEqual("delivered", bd.get_ticket(self.board, tid)[1]["status"])
        th = self.thread(tid)
        self.assertEqual(1, len([t for t in th if t.startswith("human decision: (a)")]))
        self.assertTrue(any(t.startswith("keeper follow-up: T-0003") for t in th))
        self.assertEqual([], rl.stalled(self.board, self.ws))

    def test_a_ruling_the_keeper_already_acted_on_files_nothing(self):
        """T-0979: the claim-keeper set the status from the packet and said so on the ruling."""
        tid = self.ruling()
        bd.append_to_ticket(self.board, tid, "claim-keeper (researcher@r1): set proved-modulo",
                            as_instance="researcher@r1", agent="claim-keeper", date=DATE)
        n = len(self.tickets())
        out = self.record(tid, "a", comment="union")
        self.assertEqual((False, n), (out["filed"], len(self.tickets())))
        meta = bd.get_ticket(self.board, tid)[1]
        self.assertEqual("delivered", meta["status"])                  # the answer is kept
        self.assertIn("claim-keeper", meta["result"])
        self.assertTrue(any(t.startswith("human decision: (a) union -- union")
                            for t in self.thread(tid)))

    def test_another_letter_over_an_interrupted_record_is_refused(self):
        """Second review: (a) was answered and its follow-up filed, then interrupted; (b)
        must not reuse the union follow-up. The same letter still completes it."""
        tid = self.ruling()
        bd.append_to_ticket(self.board, tid, "human decision: (a) union", date=DATE)
        self.ticket(to="researcher@r1", as_instance="human", kind="decision", parent=tid,
                    title="Status of paper:lem:x -> proved-modulo (ruling %s)" % tid,
                    ask="Set it.")
        thread = self.thread(tid)
        with self.assertRaises(ac.AcademyError) as cm:
            self.record(tid, "b")
        self.assertIn("(a)", str(cm.exception))
        self.assertIn("T-0003", str(cm.exception))
        self.assertEqual(thread, self.thread(tid))                     # nothing written
        self.assertEqual("open", bd.get_ticket(self.board, tid)[1]["status"])
        out = self.record(tid, "a")
        self.assertEqual(("T-0003", False), (out["follow_up"], out["filed"]))
        self.assertEqual("delivered", bd.get_ticket(self.board, tid)[1]["status"])

    def test_another_letter_over_a_keeper_who_acted_is_refused(self):
        """A non-rerun answer over an earlier, different one the keeper acted on (#125)."""
        tid = self.ruling()
        bd.append_to_ticket(self.board, tid, "human decision: (a) union", date=DATE)
        bd.append_to_ticket(self.board, tid, "claim-keeper (researcher@r1): set proved-modulo",
                            as_instance="researcher@r1", agent="claim-keeper", date=DATE)
        thread = self.thread(tid)
        with self.assertRaises(ac.AcademyError) as cm:
            self.record(tid, "b")
        self.assertIn("claim-keeper", str(cm.exception))
        self.assertIn("--force", str(cm.exception))
        self.assertEqual(thread, self.thread(tid))                     # nothing written
        self.assertEqual("delivered", self.record(tid, "a")["status"])

    def test_a_forced_other_letter_over_a_keeper_who_acted_files_and_notes(self):
        tid = self.ruling()
        bd.append_to_ticket(self.board, tid, "human decision: (a) union", date=DATE)
        bd.append_to_ticket(self.board, tid, "claim-keeper (researcher@r1): set proved-modulo",
                            as_instance="researcher@r1", agent="claim-keeper", date=DATE)
        out = self.record(tid, "b", force=True)
        self.assertTrue(out["filed"])
        self.assertEqual("decision", self.tickets()[out["follow_up"]]["kind"])
        self.assertTrue(any("earlier ruling" in t and "(a) union" in t for t in self.thread(tid)))

    def test_a_rerun_over_a_keeper_who_acted_files_the_rerun(self):
        """#125 item 2: the keeper acted on an earlier ruling; a new re-run is filed, not
        swallowed by the earlier action."""
        tid = self.ruling()
        bd.append_to_ticket(self.board, tid, "human decision: (a) union", date=DATE)
        bd.append_to_ticket(self.board, tid, "claim-keeper (researcher@r1): set proved-modulo",
                            as_instance="researcher@r1", agent="claim-keeper", date=DATE)
        out = self.record(tid, "c")
        self.assertTrue(out["filed"])
        k = self.tickets()[out["follow_up"]]
        self.assertEqual(("verify", "expert@main"), (k["kind"], k["to"]))
        meta = bd.get_ticket(self.board, tid)[1]
        self.assertIn(out["follow_up"], meta["result"])
        self.assertIn("rerun", meta["result"])
        self.assertNotIn("acted on it", meta["result"])

    def test_a_ticket_naming_the_ruling_only_in_its_refs_is_not_its_follow_up(self):
        """Point 2 of the review: an unrelated verify ticket listing the ruling in its refs
        must not swallow the human's answer."""
        tid = self.ruling()
        self.ticket(to="expert@main", as_instance="human", kind="verify",
                    title="verify lem:y", ask="Verify it.", refs=[SUBJECT, tid])
        self.assertIsNone(rl.follow_up_of(self.board, tid))
        out = self.record(tid, "a")
        self.assertTrue(out["filed"])
        self.assertEqual("delivered", bd.get_ticket(self.board, tid)[1]["status"])

    def test_a_ticket_whose_ask_names_the_ruling_is_its_follow_up(self):
        tid = self.ruling()
        self.ticket(to="researcher@r1", as_instance="human", kind="decision",
                    title="Keeper: six statements", ask="Set them, on %s." % tid)
        self.assertEqual(("T-0003", "ticket"), rl.follow_up_of(self.board, tid))

    def test_decline_rejects_even_when_a_follow_up_exists(self):
        tid = self.ruling()
        self.ticket(to="researcher@r1", as_instance="human", kind="decision",
                    title="Status (ruling %s)" % tid, ask="Set it.")
        out = self.record(tid, "d", comment="no")
        self.assertEqual("rejected", out["status"])
        self.assertEqual("rejected", bd.get_ticket(self.board, tid)[1]["status"])

    def test_intersection_and_an_empty_intersection_proposes_proved(self):
        self.write_pass(a=record_text("A", modulo="paper:lem:rigid"),
                        b=record_text("B", modulo="none"))
        tid = self.ruling()
        out = self.record(tid, "intersection")
        k = self.tickets()[out["follow_up"]]
        self.assertIn("-> proved", k["title"])
        self.assertNotIn("proved-modulo", k["title"])
        grounds = rl.grounds_in(bd.get_ticket(self.board, out["follow_up"])[2])
        self.assertNotIn("modulo", grounds)
        self.assertTrue(check_grounds("proved", grounds, HASH)[0])

    def test_rerun_files_a_verify_ticket_to_the_expert(self):
        tid = self.ruling()
        out = self.record(tid, "c")
        k = self.tickets()[out["follow_up"]]
        self.assertEqual(("verify", "expert@main", tid), (k["kind"], k["to"], k["parent"]))
        self.assertIn(SUBJECT, k["refs"])
        self.assertEqual("delivered", bd.get_ticket(self.board, tid)[1]["status"])

    def test_decline_rejects_and_files_nothing(self):
        tid = self.ruling()
        n = len(self.tickets())
        out = self.record(tid, "d", comment="not now")
        self.assertEqual(("rejected", None), (out["status"], out.get("follow_up")))
        self.assertEqual(n, len(self.tickets()))

    def test_a_bare_proceed_names_no_modulo_and_is_refused(self):
        tid = self.ruling()
        with self.assertRaises(ac.AcademyError) as cm:
            self.record(tid, "proceed")
        self.assertIn("union", str(cm.exception))
        self.assertEqual("open", bd.get_ticket(self.board, tid)[1]["status"])

    def test_an_accepted_ruling_without_follow_up_is_filed_on_record(self):
        """The stalled case: answered 'proceed' before this change, accepted, no keeper."""
        tid = self.ruling()
        bd.append_to_ticket(self.board, tid, "human decision: proceed -- union", date=DATE)
        bd.transition_ticket(self.board, tid, "accepted", as_instance="human", date=DATE)
        out = self.record(tid, "a")
        self.assertTrue(out["filed"])
        self.assertEqual("delivered", bd.get_ticket(self.board, tid)[1]["status"])

    def test_a_finished_ruling_is_not_reopened(self):
        tid = self.ruling()
        self.record(tid, "d")
        with self.assertRaises(ac.AcademyError):
            self.record(tid, "a")

    def test_a_plain_ticket_still_takes_proceed_and_files_nothing(self):
        self.ticket(to="human", as_instance="expert@main", kind="decision", title="Redeploy?",
                    ask="Redeploy fsq.sh?", refs=[])
        n = len(self.tickets())
        out = self.record("T-0002", "proceed")
        self.assertEqual("accepted", out["status"])
        self.assertEqual(n, len(self.tickets()))


#: a T-0979-shaped ask: the ticket's own letters, where (c) is "wait", not a re-run
OWN_ASK = ("Run A (CONFIRMED) lists modulo paper:lem:rigid, paper:cor:locus and a notation "
           "entry; run B (CONFIRMED) lists paper:lem:rigid, lem:locus2, paper:cor:locus. The "
           "table returns 'disagreement' on the inputs. Please rule: (a) accept that A's "
           "notation entry is superseded by the card, so the keeper may take proved-modulo "
           "[paper:lem:rigid, paper:cor:locus]; (b) re-run A (and B) against the current "
           "library; (c) wait until paper:lem:rigid is proved. Recommendation: (a). See "
           "packet P-0007.")


class TestOwnOptions(RulingCase):
    """#125 item 1: a ticket's own lettered options win over the tool's generic ones."""

    def own(self, **kw):
        return self.ruling(ask=OWN_ASK, **kw)

    def acted_on_earlier(self, tid):
        """T-0979's history: the human ruled (a) on 2026-11-13 as a bare proceed, the keeper set
        the status, the ruling stayed accepted."""
        bd.append_to_ticket(self.board, tid, "claim-keeper (researcher@r1): on the human's "
                            "ruling (a), set proved-modulo", as_instance="researcher@r1",
                            agent="claim-keeper", date="2026-11-01")
        bd.append_to_ticket(self.board, tid, "human decision: proceed -- ruling (a): the "
                            "keeper takes proved-modulo", date="2026-11-13")
        bd.transition_ticket(self.board, tid, "accepted", as_instance="human", date="2026-11-13")

    def test_the_own_options_are_parsed_and_classified(self):
        tid = self.own()
        _p, meta, body = bd.get_ticket(self.board, tid)
        own = rl.own_options(meta, body)
        self.assertEqual(["a", "b", "c"], list(own))           # "Recommendation: (a)." is none
        self.assertTrue(own["b"].startswith("re-run A (and B)"))
        self.assertEqual("wait until paper:lem:rigid is proved", own["c"])
        self.assertEqual(["accept", "rerun", "wait"], [rl.classify(own[k]) for k in own])
        self.assertEqual({}, rl.own_options({"ask": "Rule on the modulo inputs?"}, ""))

    def test_own_c_is_wait_and_files_nothing(self):
        tid = self.own()
        n = len(self.tickets())
        out = self.record(tid, "c", comment="wait")
        self.assertEqual((False, None), (out["filed"], out["follow_up"]))
        self.assertEqual(n, len(self.tickets()))
        self.assertTrue(any(t.startswith("human decision: (c) wait") for t in self.thread(tid)))
        self.assertFalse(any("rerun" in t for t in self.thread(tid)))
        meta = bd.get_ticket(self.board, tid)[1]
        self.assertEqual("delivered", meta["status"])
        self.assertIn("wait", meta["result"])
        self.assertNotIn("rerun", meta["result"])

    def test_a_letter_and_an_action_that_disagree_are_refused_naming_the_own_options(self):
        tid = self.own()
        thread = self.thread(tid)
        with self.assertRaises(ac.AcademyError) as cm:
            self.record(tid, "c", action="rerun")
        msg = str(cm.exception)
        self.assertIn("(b) re-run A (and B)", msg)
        self.assertIn("(c) wait until", msg)
        self.assertEqual(thread, self.thread(tid))
        self.assertEqual("open", bd.get_ticket(self.board, tid)[1]["status"])

    def test_own_b_is_the_rerun_and_files_it(self):
        tid = self.own()
        out = self.record(tid, "b")
        k = self.tickets()[out["follow_up"]]
        self.assertEqual(("verify", "expert@main", tid), (k["kind"], k["to"], k["parent"]))
        self.assertEqual("Re-run the blind pass on %s (ruling %s)" % (SUBJECT, tid), k["title"])
        self.assertTrue(any(t.startswith("human decision: (b) rerun") for t in self.thread(tid)))

    def test_an_action_alone_picks_the_own_option(self):
        tid = self.own()
        out = self.record(tid, None, action="rerun")
        self.assertEqual("b", out["choice"])
        self.assertEqual("verify", self.tickets()[out["follow_up"]]["kind"])

    def test_own_accept_takes_the_list_its_text_names(self):
        tid = self.own()
        out = self.record(tid, "a")
        body = bd.get_ticket(self.board, out["follow_up"])[2]
        self.assertEqual(["paper:lem:rigid", "paper:cor:locus"], rl.grounds_in(body)["modulo"])

    def test_pending_decisions_show_the_own_options(self):
        tid = self.own()
        item = [i for i in dc.pending_decisions(self.board, workspace=self.ws)
                if i["id"] == tid][0]
        self.assertEqual(["(a) Accept", "(b) Re-run", "(c) Wait"],
                         [o["label"] for o in item["options"]])
        self.assertIn("wait until paper:lem:rigid", item["options"][2]["description"])

    def test_a_rerun_after_an_acted_on_earlier_ruling_files_and_notes(self):
        """#125 item 2, T-0979 exactly: the keeper acted on (a); the new (b) re-run is filed,
        the result names it, and a note says the earlier status stands."""
        tid = self.own()
        self.acted_on_earlier(tid)
        before = set(self.tickets())
        out = self.record(tid, "b", comment="2026-11-20: re-run")
        self.assertTrue(out["filed"])
        self.assertEqual([out["follow_up"]], sorted(set(self.tickets()) - before))
        meta = bd.get_ticket(self.board, tid)[1]
        self.assertEqual("delivered", meta["status"])
        self.assertIn("(b) rerun", meta["result"])
        self.assertIn(out["follow_up"], meta["result"])
        self.assertNotIn("acted on it", meta["result"])
        notes = [t for t in self.thread(tid) if t.startswith("earlier ruling")]
        self.assertEqual(1, len(notes))
        self.assertIn("proceed -- ruling (a)", notes[0])
        self.assertIn("stands until", notes[0])
        again = self.record(tid, "b")                               # idempotent
        self.assertEqual((out["follow_up"], False), (again["follow_up"], again["filed"]))
        self.assertEqual(len(before) + 1, len(self.tickets()))

    def test_a_wait_after_an_acted_on_earlier_ruling_needs_force(self):
        tid = self.own()
        self.acted_on_earlier(tid)
        thread = self.thread(tid)
        with self.assertRaises(ac.AcademyError) as cm:
            self.record(tid, "c")
        self.assertIn("--force", str(cm.exception))
        self.assertIn("claim-keeper", str(cm.exception))
        self.assertEqual(thread, self.thread(tid))
        out = self.record(tid, "c", force=True)
        self.assertEqual(("delivered", False), (out["status"], out["filed"]))
        self.assertTrue(any("earlier ruling" in t for t in self.thread(tid)))

    def test_a_plain_ticket_s_own_letter_is_its_own_option(self):
        """Not a ruling: (b) is a re-run of the checks, not a decline."""
        self.ticket(to="human", as_instance="expert@main", kind="decision", title="Redeploy?",
                    ask="Redeploy fsq.sh? (a) redeploy now; (b) re-run the checks first; "
                        "(c) drop it.", refs=[])
        out = self.record("T-0002", "b")
        self.assertEqual("accepted", out["status"])
        self.assertTrue(any(t.startswith("human decision: (b) rerun")
                            for t in self.thread("T-0002")))
        item = [i for i in dc.pending_decisions(self.board, workspace=self.ws)
                if i["id"] == "T-0002"]
        self.assertEqual([], item)                                     # answered
        self.ticket(to="human", as_instance="expert@main", kind="decision", title="Redeploy?",
                    ask="Redeploy fsq.sh? (a) redeploy now; (b) re-run the checks first; "
                        "(c) drop it.", refs=[])
        self.assertEqual("rejected", self.record("T-0003", "c")["status"])

    T0981_ASK = ("Run A lists modulo paper:lem:rigid and run B none, so the table proposes "
                 "nothing on the inputs. Choose: (a) take proved (modulo formal); (b) take "
                 "proved-modulo [paper:lem:other] by inheritance; (c) split lem:rigid items "
                 "1-3 / item 4(a) first, then proved. Recommendation: (a).")

    def t0981(self):
        self.write_pass(a=record_text("A", modulo="paper:lem:rigid"),
                        b=record_text("B", modulo="none"))
        return self.ruling(ask=self.T0981_ASK)

    def test_a_rerun_the_own_options_lack_is_still_filed(self):
        """T-0981: no own option is a re-run; --action rerun files the generic re-run and
        the answer line carries no letter that could be misread."""
        tid = self.t0981()
        self.assertEqual(["accept", "accept", "split"],
                         [rl.classify(v) for v in rl.own_options(
                             bd.get_ticket(self.board, tid)[1]).values()])
        out = self.record(tid, None, action="rerun")
        self.assertEqual("verify", self.tickets()[out["follow_up"]]["kind"])
        self.assertTrue(any(t.startswith("human decision: (-) rerun") for t in self.thread(tid)))
        with self.assertRaises(ac.AcademyError):
            self.record(self.t0981(), "c", action="rerun")

    def test_own_split_files_nothing_and_bare_proved_is_the_empty_intersection(self):
        tid = self.t0981()
        out = self.record(tid, "c")
        self.assertEqual((False, None), (out["filed"], out["follow_up"]))
        self.assertIn("split", bd.get_ticket(self.board, tid)[1]["result"])
        tid = self.t0981()
        out = self.record(tid, "a")
        self.assertIn("-> proved ", self.tickets()[out["follow_up"]]["title"])
        with self.assertRaises(ac.AcademyError) as cm:            # a third list: not guessed
            self.record(self.t0981(), "b")
        self.assertIn("--action union", str(cm.exception))

    def test_cli_takes_an_action_and_refuses_a_disagreement(self):
        tid = self.own()
        base = ["--board", self.board, "--workspace", self.ws_path]
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            self.assertEqual(1, dc.main(base + ["record", tid, "--choice", "c",
                                                "--action", "rerun"]))
        self.assertIn("(b) re-run", err.getvalue())
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(0, dc.main(base + ["record", tid, "--action", "rerun"]))
        self.assertEqual("b", json.loads(out.getvalue())["choice"])


class TestGithubBackend(RulingCase):
    def test_record_on_the_github_store_finds_the_new_ticket_and_is_idempotent(self):
        import board_store as bs
        tid = self.ruling()
        store = bs.GithubBoardStore(bs.from_file_board(self.board), repo="o/r")
        out = dc.record(store, tid, "a", workspace=self.ws, date=DATE)
        self.assertTrue(out["filed"])
        k = store.get(out["follow_up"])[1]
        self.assertEqual(("researcher@r1", tid), (k["to"], k["parent"]))
        self.assertIn("keeper follow-up: %s" % out["follow_up"],
                      "\n".join(t for _d, _w, t in ac.thread_lines(store.get(tid)[2])))
        self.assertFalse(dc.record(store, tid, "a", workspace=self.ws, date=DATE)["filed"])


class TestStalled(RulingCase):
    def test_stalled_lists_answered_rulings_without_a_follow_up(self):
        tid = self.ruling()
        bd.append_to_ticket(self.board, tid, "human decision: proceed -- union", date=DATE)
        bd.transition_ticket(self.board, tid, "accepted", as_instance="human", date=DATE)
        self.assertEqual([tid], [r["id"] for r in rl.stalled(self.board, self.ws)])
        self.record(tid, "a")
        self.assertEqual([], rl.stalled(self.board, self.ws))

    def test_cli_record_and_stalled(self):
        tid = self.ruling()
        base = ["--board", self.board, "--workspace", self.ws_path]
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(0, dc.main(base + ["record", tid, "--choice", "a"]))
        self.assertTrue(json.loads(out.getvalue())["filed"])
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, dc.main(base + ["stalled-rulings", "--json"]))
        self.assertEqual([], json.loads(out.getvalue()))


if __name__ == "__main__":
    unittest.main()
