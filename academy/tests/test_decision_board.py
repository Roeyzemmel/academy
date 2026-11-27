"""Tests for the decision board v2 (#86): decisions.py's routine policy, real options,
multi-select batches, pinned releases, folded rulings, leads and the session files.

Run from the repo root:  py -m unittest discover academy/tests
"""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import decisions as dc  # noqa: E402
import rulings as rl  # noqa: E402
from test_decisions import DATE, DecisionsCase  # noqa: E402

LATER = "2026-09-29"


def texts(board, tid):
    _m, body = bd.read_ticket(ac.find_ticket(board, tid))
    return [t for _d, _w, t in ac.thread_lines(body)]


def meta_of(board, tid):
    return bd.read_ticket(ac.find_ticket(board, tid))[0]


class BoardCase(DecisionsCase):
    def policy(self, *cats):
        self.ws["decisions"] = {"routine": list(cats)}

    def blocked(self, **kw):
        kw.setdefault("to", "expert@main")
        kw.setdefault("as_instance", "human")
        path = self.ticket(**kw)
        tid = bd.read_ticket(path)[0]["id"]
        bd.transition_ticket(self.board, tid, "blocked", waiting_on=["human"],
                             as_instance=kw["to"], date=DATE)
        return tid


# ----------------------------------------------------------------------------
# (1) the routine policy, its digest and the undo window
# ----------------------------------------------------------------------------

class RoutinePolicyTests(BoardCase):
    def test_no_policy_accepts_nothing(self):
        self.blocked(kind="verify")
        self.assertEqual(dc.routine_policy(self.ws), [])
        self.assertEqual(dc.apply_policy(self.board, self.ws, date=DATE), [])
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "blocked")

    def test_policy_kinds_are_accepted_and_the_rest_stay_asked(self):
        self.policy("verify", "cite")
        self.blocked(kind="verify", title="Verify lem:a")
        self.blocked(kind="cite", title="Cite X")
        self.blocked(kind="review-experiment", title="Review lab:x", to="researcher@r1")
        self.blocked(kind="prove", title="Prove lem:b", to="researcher@r1")
        done = dc.apply_policy(self.board, self.ws, date=DATE)
        self.assertEqual([d["id"] for d in done], ["T-0001", "T-0002"])
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "accepted")
        self.assertEqual(meta_of(self.board, "T-0003")["status"], "blocked")
        left = [i["id"] for i in dc.pending_decisions(self.board, workspace=self.ws)]
        self.assertEqual(left, ["T-0003", "T-0004"])
        self.assertTrue(any(t.startswith(dc.POLICY_MARK) for t in texts(self.board, "T-0001")))

    def test_dry_run_writes_nothing(self):
        self.policy("verify")
        self.blocked(kind="verify")
        done = dc.apply_policy(self.board, self.ws, date=DATE, dry_run=True)
        self.assertEqual([d["id"] for d in done], ["T-0001"])
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "blocked")

    def test_review_experiment_is_never_routine(self):
        with self.assertRaises(ac.AcademyError):
            dc.routine_policy({"decisions": {"routine": ["review-experiment"]}})
        with self.assertRaises(ac.AcademyError):
            dc.routine_policy({"decisions": {"routine": ["no-such-kind"]}})

    def test_claim_status_and_repair_categories(self):
        self.policy("claim-status", "repair")
        self.blocked(kind="decision", title="Status of s1:GEO-3 -> sketch", to="researcher@r1")
        self.blocked(kind="prove", title="Repair the proof of s1:GEO-4", to="researcher@r1")
        self.blocked(kind="prove", title="Prove s1:GEO-5", to="researcher@r1")
        self.blocked(kind="decision", title="Which modulo list?", to="researcher@r1")
        done = dc.apply_policy(self.board, self.ws, date=DATE)
        self.assertEqual([(d["id"], d["category"]) for d in done],
                         [("T-0001", "claim-status"), ("T-0002", "repair")])

    def test_a_ticket_to_the_human_is_accepted_from_open(self):
        self.policy("cite")
        self.ticket(to="human", kind="cite", as_instance="expert@main")
        done = dc.apply_policy(self.board, self.ws, date=DATE)
        self.assertEqual(done[0]["was"], "open")
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "accepted")

    def test_digest_one_line_per_kind_with_ids(self):
        done = [{"id": "T-0001", "category": "verify"}, {"id": "T-0002", "category": "cite"},
                {"id": "T-0003", "category": "verify"}]
        self.assertEqual(dc.digest(done),
                         "accepted under the policy: 2 verify (T-0001, T-0003), "
                         "1 cite (T-0002)")
        self.assertEqual(dc.digest([]), "")


class UndoTests(BoardCase):
    def test_undo_restores_a_blocked_ticket(self):
        self.policy("verify")
        self.blocked(kind="verify")
        dc.apply_policy(self.board, self.ws, date=DATE)
        out = dc.undo(self.board, "T-0001", date=LATER)
        self.assertEqual(out["status"], "blocked")
        m = meta_of(self.board, "T-0001")
        self.assertEqual((m["status"], m["waiting_on"]), ("blocked", ["human"]))
        self.assertEqual([i["id"] for i in dc.pending_decisions(self.board,
                                                                 workspace=self.ws)],
                         ["T-0001"])

    def test_undo_restores_an_open_ticket_to_the_human(self):
        self.policy("cite")
        self.ticket(to="human", kind="cite", as_instance="expert@main")
        dc.apply_policy(self.board, self.ws, date=DATE)
        self.assertEqual(dc.undo(self.board, "T-0001", date=LATER)["status"], "open")

    def test_undo_refused_once_an_inbox_run_touched_it(self):
        self.policy("verify")
        self.blocked(kind="verify")
        dc.apply_policy(self.board, self.ws, date=DATE)
        bd.transition_ticket(self.board, "T-0001", "in-progress", as_instance="expert@main",
                             date=LATER)
        with self.assertRaises(ac.AcademyError):
            dc.undo(self.board, "T-0001", date=LATER)

    def test_undo_refused_after_a_line_by_an_instance(self):
        self.policy("verify")
        self.blocked(kind="verify")
        dc.apply_policy(self.board, self.ws, date=DATE)
        bd.append_to_ticket(self.board, "T-0001", "picked up", as_instance="expert@main")
        with self.assertRaises(ac.AcademyError):
            dc.undo(self.board, "T-0001", date=LATER)

    def test_undo_refused_for_an_answer_the_human_gave(self):
        self.blocked(kind="verify")
        dc.record(self.board, "T-0001", "proceed", date=DATE)
        with self.assertRaises(ac.AcademyError):
            dc.undo(self.board, "T-0001", date=LATER)

    def test_undo_twice_refused(self):
        self.policy("verify")
        self.blocked(kind="verify")
        dc.apply_policy(self.board, self.ws, date=DATE)
        dc.undo(self.board, "T-0001", date=LATER)
        with self.assertRaises(ac.AcademyError):
            dc.undo(self.board, "T-0001", date=LATER)


class PolicyCLITests(BoardCase):
    def test_policy_cli_prints_the_digest(self):
        self.policy("verify")
        with open(self.ws_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        raw["decisions"] = {"routine": ["verify"]}
        with open(self.ws_path, "w", encoding="utf-8") as fh:
            json.dump(raw, fh)
        self.blocked(kind="verify")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = dc.main(["--board", self.board, "--workspace", self.ws_path, "policy"])
        self.assertEqual(rc, 0)
        self.assertIn("accepted under the policy: 1 verify (T-0001)", out.getvalue())


# ----------------------------------------------------------------------------
# (2) real options: alternatives without letters, no bare proceed, the stored choice
# ----------------------------------------------------------------------------

ALT_ASK = ("rmk:x cites no source for the bound. Decide: drop the note, or a literature "
           "lookup and a one-line remark.")


class AlternativesParseTests(unittest.TestCase):
    def test_comma_or_after_a_cue(self):
        self.assertEqual(rl.alternatives(ALT_ASK),
                         {"a": "drop the note",
                          "b": "a literature lookup and a one-line remark"})

    def test_either_or(self):
        self.assertEqual(rl.alternatives("Either keep the hypothesis or weaken it to PA-5w?"),
                         {"a": "keep the hypothesis", "b": "weaken it to PA-5w"})

    def test_three_alternatives(self):
        self.assertEqual(sorted(rl.alternatives(
            "Choose: cite LMW16, or reprove it here, or drop the remark.").values()),
            ["cite LMW16", "drop the remark", "reprove it here"])

    def test_no_cue_no_alternatives(self):
        # a plain "or" inside a statement is not a choice put to the human
        self.assertEqual(rl.alternatives("Verify that the set is finite, or empty."), {})
        self.assertEqual(rl.alternatives("Check lem:x is proved or refuted."), {})
        self.assertEqual(rl.alternatives(""), {})

    def test_slight_parts_are_no_alternatives(self):
        self.assertEqual(rl.alternatives("Decide: yes, or no."), {})


class RealOptionsTests(BoardCase):
    def test_alternatives_are_the_options_with_a_decline(self):
        self.blocked(kind="note", ask=ALT_ASK)
        it = dc.pending_decisions(self.board, workspace=self.ws)[0]
        labels = [o["label"] for o in it["options"]]
        self.assertTrue(labels[0].startswith("(a) drop the note"), labels)
        self.assertTrue(labels[1].startswith("(b) a literature lookup"), labels)
        self.assertEqual(labels[-1], "(decline) Decline")
        self.assertTrue(it["own_options"])

    def test_a_bare_proceed_is_refused_when_alternatives_exist(self):
        self.blocked(kind="note", ask=ALT_ASK)
        for word in ("proceed", "yes", "accept"):
            with self.assertRaises(ac.AcademyError) as cm:
                dc.record(self.board, "T-0001", word, date=DATE)
            self.assertIn("drop the note", str(cm.exception))
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "blocked")

    def test_the_chosen_alternative_is_stored_on_the_ticket(self):
        self.blocked(kind="note", ask=ALT_ASK)
        out = dc.record(self.board, "T-0001", "b", date=DATE)
        m = meta_of(self.board, "T-0001")
        self.assertEqual(out["status"], "accepted")
        self.assertEqual(m["status"], "accepted")
        self.assertEqual(m["decision_choice"], "(b) a literature lookup and a one-line remark")
        self.assertTrue(any("(b) a literature lookup" in t for t in texts(self.board, "T-0001")))
        path, meta, body = bd.get_ticket(self.board, "T-0001")
        self.assertEqual(ac.validate_ticket(meta, body), [])

    def test_a_drop_alternative_proceeds_it_does_not_reject(self):
        self.blocked(kind="note", ask=ALT_ASK)
        dc.record(self.board, "T-0001", "a", date=DATE)
        m = meta_of(self.board, "T-0001")
        self.assertEqual((m["status"], m["decision_choice"]), ("accepted", "(a) drop the note"))

    def test_decline_still_declines(self):
        self.blocked(kind="note", ask=ALT_ASK)
        self.assertEqual(dc.record(self.board, "T-0001", "decline", date=DATE)["status"],
                         "cancelled")

    def test_lettered_options_refuse_a_bare_proceed_and_store_the_letter(self):
        self.ticket(to="human", kind="question", as_instance="expert@main",
                    ask="Which? Options: (a) keep the remark as it is; (b) cut the remark "
                        "entirely.")
        with self.assertRaises(ac.AcademyError):
            dc.record(self.board, "T-0001", "proceed", date=DATE)
        dc.record(self.board, "T-0001", "a", date=DATE)
        self.assertEqual(meta_of(self.board, "T-0001")["decision_choice"],
                         "(a) keep the remark as it is")

    def test_a_plain_proceed_stores_proceed(self):
        self.blocked(kind="verify")
        dc.record(self.board, "T-0001", "proceed", date=DATE)
        self.assertEqual(meta_of(self.board, "T-0001")["decision_choice"], "proceed")

    def test_the_choice_is_a_human_only_field(self):
        self.assertIn("decision_choice", ac.TICKET_FIELDS["human_only"])
        perms = ac.load_permissions(os.path.join(PLUGIN, "permissions.json"))
        self.assertIn("decision_choice", perms["tickets"]["fields"]["human_only"])

    def test_a_policy_acceptance_stores_its_choice_and_undo_clears_it(self):
        self.policy("verify")
        self.blocked(kind="verify")
        dc.apply_policy(self.board, self.ws, date=DATE)
        self.assertEqual(meta_of(self.board, "T-0001")["decision_choice"],
                         "proceed (routine policy)")
        dc.undo(self.board, "T-0001", date=LATER)
        self.assertNotIn("decision_choice", meta_of(self.board, "T-0001"))

    def test_a_ticket_naming_alternatives_is_asked_not_accepted(self):
        self.policy("note")
        self.blocked(kind="note", ask=ALT_ASK)
        self.assertEqual(dc.apply_policy(self.board, self.ws, date=DATE), [])


# ----------------------------------------------------------------------------
# (3) experiments and proofs: multi-select batches, grouped by claim
# ----------------------------------------------------------------------------

class MultiSelectTests(BoardCase):
    def make(self):
        self.blocked(kind="prove", title="Prove A1", to="researcher@r1", refs=["s1:A"])
        self.blocked(kind="experiment", title="Search B", to="researcher@r1", refs=["s1:B"])
        self.blocked(kind="test", title="Test A2", to="researcher@r1", refs=["s1:A"])
        self.blocked(kind="verify", title="Verify C")
        self.blocked(kind="prove", title="Prove A3", to="researcher@r1", refs=["s1:A"])

    def test_selectable_items_are_batched_by_claim_after_the_others(self):
        self.make()
        bs = dc.batches(dc.pending_decisions(self.board, workspace=self.ws))
        self.assertEqual([[i["id"] for i in b] for b in bs],
                         [["T-0004"], ["T-0001", "T-0003", "T-0005", "T-0002"]])
        self.assertTrue(all(i["multiselect"] for i in bs[1]))
        self.assertNotIn("multiselect", bs[0][0])
        self.assertEqual([i["select"] for i in bs[1]], ["s1:A", "s1:A", "s1:A", "s1:B"])

    def test_a_claim_group_is_kept_whole_when_it_fits(self):
        for n in range(3):
            self.blocked(kind="prove", title="Prove A%d" % n, to="researcher@r1", refs=["s1:A"])
        for n in range(2):
            self.blocked(kind="prove", title="Prove B%d" % n, to="researcher@r1", refs=["s1:B"])
        bs = dc.batches(dc.pending_decisions(self.board, workspace=self.ws))
        self.assertEqual([[i["select"] for i in b] for b in bs],
                         [["s1:A"] * 3, ["s1:B"] * 2])

    def test_ticked_proceed_and_unticked_stay_with_not_now(self):
        self.make()
        out = dc.select(self.board, ticked=["T-0001", "T-0003"], unticked=["T-0005", "T-0002"],
                        date=DATE)
        self.assertEqual([o["status"] for o in out], ["accepted", "accepted", "blocked",
                                                      "blocked"])
        self.assertEqual(meta_of(self.board, "T-0001")["decision_choice"], "proceed")
        m = meta_of(self.board, "T-0005")
        self.assertEqual((m["status"], m["waiting_on"]), ("blocked", ["human"]))
        self.assertTrue(any(t.startswith(dc.NOT_NOW) for t in texts(self.board, "T-0005")))
        # not asked again the same day; asked again on a later one
        same = [i["id"] for i in dc.pending_decisions(self.board, workspace=self.ws,
                                                      date=DATE)]
        self.assertEqual(same, ["T-0004"])
        later = [i["id"] for i in dc.pending_decisions(self.board, workspace=self.ws,
                                                       date=LATER)]
        self.assertEqual(later, ["T-0002", "T-0004", "T-0005"])

    def test_select_refuses_a_ticket_that_is_not_selectable(self):
        self.make()
        with self.assertRaises(ac.AcademyError):
            dc.select(self.board, ticked=["T-0004"], unticked=[], date=DATE)

    def test_select_cli(self):
        self.make()
        out = io.StringIO()
        with redirect_stdout(out):
            rc = dc.main(["--board", self.board, "--workspace", self.ws_path, "select",
                          "--ticked", "T-0001", "--unticked", "T-0003,T-0005"])
        self.assertEqual(rc, 0)
        self.assertEqual(len(json.loads(out.getvalue())), 3)


if __name__ == "__main__":
    unittest.main()
