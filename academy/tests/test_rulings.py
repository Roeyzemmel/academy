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

    def test_a_pass_with_a_run_not_confirmed_is_no_ruling(self):
        self.write_pass(b=record_text("B", verdict="GAP", modulo=self.B_MODULO))
        tid = self.ruling()
        self.assertIsNone(rl.find_ruling(self.board, tid, self.ws))

    def test_runs_on_different_hashes_or_one_run_id_are_no_ruling(self):
        self.write_pass(b=record_text("B", modulo=self.B_MODULO, hash_="0000000000000000"))
        self.assertIsNone(rl.find_ruling(self.board, self.ruling(), self.ws))
        self.write_pass(b=record_text("B", modulo=self.B_MODULO, run_id="rv-%s-A" % PASS))
        self.assertIsNone(rl.find_ruling(self.board, "T-0002", self.ws))

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
        tid = self.ruling()
        bd.transition_ticket(self.board, tid, "accepted", as_instance="human", date=DATE)
        self.ticket(to="researcher@r1", as_instance="human", kind="decision", parent=tid,
                    title="Status of paper:lem:x -> proved-modulo", ask="Set it.")
        n = len(self.tickets())
        out = self.record(tid, "a")
        self.assertEqual((False, n), (out["filed"], len(self.tickets())))

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
