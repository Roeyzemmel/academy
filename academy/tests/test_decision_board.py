"""Tests for the decision board v2 (#86): decisions.py's routine policy, real options,
multi-select batches, pinned releases, folded rulings, leads and the session files.

Run from the repo root:  py -m unittest discover academy/tests
"""

import io
import json
import os
import subprocess
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


# ----------------------------------------------------------------------------
# (4) an edit to a pinned statement: "accept and release <labels>"
# ----------------------------------------------------------------------------

class PinnedReleaseTests(BoardCase):
    def setUp(self):
        super().setUp()
        self.home = self.ws["instances"]["author@main"]["home"]
        os.makedirs(self.home, exist_ok=True)
        self._orig = dc._pinned_labels
        dc._pinned_labels = lambda home: {"lem:x", "thm:y"} if home == self.home else set()

    def tearDown(self):
        dc._pinned_labels = self._orig
        super().tearDown()

    def release_file(self):
        return os.path.join(self.home, ".claude", "pinned-release.txt")

    def test_an_edit_of_a_pinned_statement_offers_accept_and_release(self):
        self.blocked(kind="apply", to="author@main", title="Weaken the hypothesis of lem:x",
                     refs=["paper:lem:x"])
        self.blocked(kind="apply", to="author@main", title="Rename prop:z", refs=["paper:prop:z"])
        items = dc.pending_decisions(self.board, workspace=self.ws)
        self.assertEqual(items[0]["pinned"], ["lem:x"])
        self.assertIn("(release) Accept and release lem:x",
                      [o["label"] for o in items[0]["options"]])
        self.assertFalse(items[1].get("pinned"))

    def test_a_pinned_edit_is_never_accepted_under_the_policy(self):
        self.policy("apply")
        self.blocked(kind="apply", to="author@main", title="Edit lem:x", refs=["paper:lem:x"])
        self.assertEqual(dc.apply_policy(self.board, self.ws, date=DATE), [])

    def test_release_appends_the_lines_with_the_word_and_the_ticket(self):
        self.blocked(kind="apply", to="author@main", title="Edit lem:x and thm:y",
                     refs=["paper:lem:x"])
        out = dc.record(self.board, "T-0001", "release", comment="the new wording is fine",
                        workspace=self.ws, date=DATE)
        self.assertEqual(out["status"], "accepted")
        self.assertEqual(out["released"], ["lem:x", "thm:y"])
        with open(self.release_file(), encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("lem:x"))
        self.assertIn("T-0001", lines[0])
        self.assertIn("the new wording is fine", lines[0])
        self.assertEqual(meta_of(self.board, "T-0001")["decision_choice"],
                         "accept and release lem:x, thm:y")
        # read back by the author's own parser (one label per line, '#' comments), run as
        # a script: its folder is not put on this suite's path (it has a pre_tool_use too)
        code = ("import sys; sys.path.insert(0, sys.argv[1]); import pinned; "
                "print(sorted(pinned.released(sys.argv[2])))")
        p = subprocess.run([sys.executable, "-c", code, os.path.dirname(dc.AUTHOR_PINNED),
                            self.home], capture_output=True, text=True)
        self.assertEqual(p.stdout.strip(), "['lem:x', 'thm:y']", p.stderr)

    def test_release_on_a_ticket_with_no_pinned_label_is_refused(self):
        self.blocked(kind="apply", to="author@main", title="Rename prop:z", refs=["paper:prop:z"])
        with self.assertRaises(ac.AcademyError):
            dc.record(self.board, "T-0001", "release", workspace=self.ws, date=DATE)
        self.assertFalse(os.path.exists(self.release_file()))

    def test_the_real_reader_finds_no_pin_in_a_home_without_reviews(self):
        dc._pinned_labels = self._orig
        dc._PINS.pop(self.home, None)
        self.assertEqual(dc._pinned_labels(self.home), set())
        self.assertEqual(dc._pinned_labels(os.path.join(self.tmp, "nowhere")), set())

    def test_a_plain_proceed_does_not_release(self):
        self.blocked(kind="apply", to="author@main", title="Edit lem:x", refs=["paper:lem:x"])
        dc.record(self.board, "T-0001", "proceed", workspace=self.ws, date=DATE)
        self.assertFalse(os.path.exists(self.release_file()))


class DecideGuardTests(unittest.TestCase):
    def setUp(self):
        import decide_guard
        self.g = decide_guard

    def ev(self, cmd, agent=None):
        e = {"tool_name": "Bash", "tool_input": {"command": cmd}}
        if agent:
            e["agent_type"] = agent
        return e

    def test_an_agent_may_not_record(self):
        for cmd in ("py /a/academy/scripts/decisions.py record T-1 --choice release",
                    "python3 decisions.py --board b select --ticked T-1",
                    "py decisions.py policy", "py decisions.py undo T-1",
                    "py decisions.py record-batch answers.json"):
            v = self.g.decide(self.ev(cmd, "academy:secretary"))
            self.assertEqual(v[0], "deny", cmd)

    def test_reading_and_the_main_session_pass(self):
        self.assertIsNone(self.g.decide(self.ev("py decisions.py batches --json",
                                                "academy:secretary")))
        self.assertIsNone(self.g.decide(self.ev("py decisions.py policy --dry-run",
                                                "academy:secretary")))
        self.assertIsNone(self.g.decide(self.ev("py decisions.py record T-1 --choice a")))
        self.assertIsNone(self.g.decide({"tool_name": "Edit", "agent_type": "x:y",
                                         "tool_input": {}}))


# ----------------------------------------------------------------------------
# (5) the rest: folded rulings, leads, session files, record-batch, ack, permissions
# ----------------------------------------------------------------------------

INFO_BODY = """
## Summary

For the record.

## Produced

- Nothing.

## Established vs assumed

- **Established:** none.

## Evidence

- n/a

## Decisions needed

None.

## Machine notes

None.

## Decision
"""


class FoldTests(BoardCase):
    def test_a_duplicate_ruling_ticket_is_folded_into_its_packet_question(self):
        self.packet(kind="notation")
        self.ticket(to="human", kind="decision", as_instance="expert@main",
                    title="Recolour paper:lem:x now? (P-0001 D1)", ask="Rule on P-0001 D1.")
        self.ticket(to="human", kind="decision", as_instance="expert@main",
                    title="Something else", ask="Spend a run?")
        items = dc.pending_decisions(self.board, workspace=self.ws)
        self.assertEqual([i["id"] for i in items], ["P-0001/D1", "T-0002"])
        self.assertEqual(items[0]["folded"], ["T-0001"])
        out = dc.record(self.board, "P-0001/D1", "a", workspace=self.ws, date=DATE)
        self.assertEqual(out["folded"], ["T-0001"])
        m = meta_of(self.board, "T-0001")
        self.assertEqual(m["status"], "delivered")
        self.assertIn("P-0001 D1", m["result"])
        self.assertEqual(m["decision_choice"], "(a) Yes, recolour now.")
        self.assertEqual(meta_of(self.board, "T-0002")["status"], "open")

    def test_a_bare_packet_id_folds_when_it_has_one_pending_decision(self):
        self.packet(kind="notation")
        self.ticket(to="human", kind="decision", as_instance="expert@main",
                    title="Decide P-0001", ask="Please rule on P-0001.")
        items = dc.pending_decisions(self.board, workspace=self.ws)
        self.assertEqual([i["id"] for i in items], ["P-0001/D1"])

    def test_no_internal_key_reaches_the_listing(self):
        self.ticket(to="human", kind="decision", as_instance="expert@main", title="P-0009 D1")
        self.assertNotIn("_mentions", dc.pending_decisions(self.board, workspace=self.ws)[0])

    def test_a_decided_packet_folds_nothing(self):
        self.packet(kind="notation")
        dc.record(self.board, "P-0001/D1", "a", date=DATE)
        self.ticket(to="human", kind="decision", as_instance="expert@main",
                    title="Rule on P-0001 D1", ask="Rule on P-0001 D1.")
        self.assertEqual([i["id"] for i in dc.pending_decisions(self.board,
                                                                 workspace=self.ws)],
                         ["T-0001"])

    def test_a_work_ticket_naming_a_packet_is_not_folded(self):
        self.packet(kind="notation")
        self.blocked(kind="write", to="author@main", title="Agenda pass (P-0001 D1)")
        ids = [i["id"] for i in dc.pending_decisions(self.board, workspace=self.ws)]
        self.assertEqual(ids, ["P-0001/D1", "T-0001"])


class AckTests(BoardCase):
    def test_a_packet_with_no_decision_takes_a_plain_acknowledgement(self):
        for n, word in enumerate((None, "ok", "proceed", "yes", "ack"), 1):
            self.packet(body=INFO_BODY, kind="usage", subject=[], status_before=None,
                        status_proposed=None, title="usage %d" % n)
            out = dc.record(self.board, "P-%04d" % n, word, date=DATE)
            self.assertTrue(out["decided"], word)

    def test_the_cli_needs_no_choice_for_it(self):
        self.packet(body=INFO_BODY, kind="usage", subject=[], status_before=None,
                    status_proposed=None)
        out = io.StringIO()
        with redirect_stdout(out):
            rc = dc.main(["--board", self.board, "--workspace", self.ws_path, "record",
                          "P-0001"])
        self.assertEqual(rc, 0)
        self.assertTrue(json.loads(out.getvalue())["decided"])

    def test_a_packet_that_asks_still_needs_its_letter(self):
        self.packet(kind="notation")
        with self.assertRaises(ac.AcademyError):
            dc.record(self.board, "P-0001", None, date=DATE)


class LeadTests(BoardCase):
    def test_free_text_is_recorded_as_a_lead_line(self):
        self.blocked(kind="verify")
        dc.lead(self.board, "T-0001", "try the  Veech group\n of the L", date=DATE)
        self.assertIn("lead: try the Veech group of the L", texts(self.board, "T-0001"))
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "blocked")   # not decided

    def test_record_with_a_lead(self):
        self.blocked(kind="verify")
        dc.record(self.board, "T-0001", "proceed", lead="check EX-EW first", date=DATE)
        t = texts(self.board, "T-0001")
        self.assertIn("lead: check EX-EW first", t)

    def test_a_packet_lead_goes_to_its_ticket(self):
        path = self.ticket(to="expert@main", kind="verify")
        tid = bd.read_ticket(path)[0]["id"]
        self.packet(kind="notation", ticket=tid)
        dc.lead(self.board, "P-0001/D1", "prefer (b) next time", date=DATE)
        self.assertIn("lead: prefer (b) next time", texts(self.board, tid))


class SessionFileTests(BoardCase):
    def test_batches_written_and_the_phrasing_read_back(self):
        self.blocked(kind="verify", title="one")
        self.blocked(kind="cite", title="two")
        out_dir = os.path.join(self.tmp, "decide")
        bs = dc.batches(dc.pending_decisions(self.board, workspace=self.ws), size=1)
        paths = dc.write_batches(bs, out_dir)
        self.assertEqual([os.path.basename(p) for p in paths], ["batch-1.json", "batch-2.json"])
        res = dc.read_phrased(out_dir)
        self.assertEqual(res["missing"], [1, 2])
        with open(os.path.join(out_dir, "batch-1.phrased.json"), "w", encoding="utf-8") as fh:
            json.dump([{"id": bs[0][0]["id"], "header": "T-1", "question": "q?",
                        "options": [{"label": "(a) Proceed"}]}], fh)
        with open(os.path.join(out_dir, "batch-2.phrased.json"), "w", encoding="utf-8") as fh:
            fh.write("not json")
        res = dc.read_phrased(out_dir)
        self.assertEqual(res["missing"], [2])
        self.assertEqual(res["batches"][0]["phrased"][0]["header"], "T-1")
        self.assertIn("2", " ".join(res["problems"]))

    def test_phrasing_that_drops_an_id_is_a_problem(self):
        self.blocked(kind="verify", title="one")
        self.blocked(kind="cite", title="two")
        out_dir = os.path.join(self.tmp, "decide")
        dc.write_batches(dc.batches(dc.pending_decisions(self.board, workspace=self.ws)),
                         out_dir)
        with open(os.path.join(out_dir, "batch-1.phrased.json"), "w", encoding="utf-8") as fh:
            json.dump([{"id": "T-0001", "header": "h", "question": "q", "options": []}], fh)
        res = dc.read_phrased(out_dir)
        self.assertTrue(any("T-0002" in p for p in res["problems"]), res)


class RecordBatchTests(BoardCase):
    def test_answers_recorded_in_one_call_with_a_results_file(self):
        self.blocked(kind="verify")
        self.blocked(kind="prove", to="researcher@r1", refs=["s1:A"])
        self.blocked(kind="test", to="researcher@r1", refs=["s1:A"])
        self.blocked(kind="cite")
        answers = os.path.join(self.tmp, "answers-1.json")
        with open(answers, "w", encoding="utf-8") as fh:
            json.dump([{"id": "T-0001", "choice": "proceed", "lead": "fast"},
                       {"ticked": ["T-0002"], "unticked": ["T-0003"]},
                       {"id": "T-0004", "choice": "maybe"},
                       {"id": "T-0099", "choice": "proceed"}], fh)
        res = dc.record_batch(self.board, answers, workspace=self.ws, date=DATE)
        self.assertEqual([r.get("error") is None for r in res["results"]],
                         [True, True, False, False])
        self.assertTrue(os.path.isfile(res["path"]))
        with open(res["path"], encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["results"], res["results"])
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "accepted")
        self.assertEqual(meta_of(self.board, "T-0002")["status"], "accepted")
        self.assertEqual(meta_of(self.board, "T-0004")["status"], "blocked")


class SecretaryWriteTests(unittest.TestCase):
    def test_the_secretary_writes_only_its_phrasing(self):
        import explainer_write_guard as g
        ev = lambda tool, path: {"tool_name": tool, "agent_type": "academy:secretary",  # noqa: E731
                                 "tool_input": {"file_path": path}}
        self.assertIsNone(g.decide(ev("Write", "/s/decide/batch-3.phrased.json"), ws={}))
        for tool, path in (("Write", "/s/decide/batch-3.json"), ("Edit", "/s/batch-1.phrased.json"),
                           ("Write", "/h/.claude/pinned-release.txt")):
            self.assertEqual(g.decide(ev(tool, path), ws={})[0], "deny", (tool, path))
        self.assertIsNone(g.decide({"tool_name": "Write", "agent_type": "author:math-writer",
                                    "tool_input": {"file_path": "/x.tex"}}, ws={}))


class RecordTwiceTests(BoardCase):
    def test_a_second_run_of_the_same_answers_changes_nothing(self):
        self.blocked(kind="verify")
        self.packet(kind="notation")
        answers = os.path.join(self.tmp, "answers-1.json")
        with open(answers, "w", encoding="utf-8") as fh:
            json.dump([{"id": "T-0001", "choice": "proceed"},
                       {"id": "P-0001/D1", "choice": "a"}], fh)
        dc.record_batch(self.board, answers, workspace=self.ws, date=DATE)
        before = texts(self.board, "T-0001")
        _p, _m, pbody = dc.packetlib.get_packet(self.board, "P-0001")
        res = dc.record_batch(self.board, answers, workspace=self.ws, date=DATE)
        self.assertTrue(res["results"][0].get("error"))
        self.assertEqual(texts(self.board, "T-0001"), before)
        self.assertEqual(dc.packetlib.get_packet(self.board, "P-0001")[2], pbody)


class PermissionTemplateTests(unittest.TestCase):
    def test_bulk_record_is_allowlisted_once(self):
        path = os.path.join(PLUGIN, "templates", "workspace", "permissions.json")
        with open(path, encoding="utf-8") as fh:
            table = json.load(fh)
        for key in ("common",):          # the root's own key stays ship.py-only
            rules = table[key]
            for verb in ("record-batch", "record", "select"):
                self.assertIn("Bash(py {ROOT}/academy/scripts/decisions.py %s:*)" % verb,
                              rules, (key, verb))


if __name__ == "__main__":
    unittest.main()


class PartialWithPolicyTests(BoardCase):
    """#100 with #86 (integration, 2026-11-27): a partial ticket the human sent is the
    human's to finish or take; the routine policy and the multi-select batches never
    touch it, whatever its kind."""

    def partial(self, tid, kind):
        m = {"id": tid, "title": "Verify lem:p", "kind": kind, "from": "human",
             "to": "expert@main", "status": "partial", "ask": "a", "deliverable": "d",
             "priority": "normal", "budget": {"runs": 1}, "created": DATE, "updated": DATE,
             "refs": ["paper:lem:p"], "result": "half done"}
        os.makedirs(os.path.join(self.board, "expert@main"), exist_ok=True)
        ac.atomic_write(os.path.join(self.board, "expert@main", ac.ticket_filename(tid, "t")),
                        ac.new_ticket(m))

    def test_a_partial_ticket_is_asked_not_policy_accepted(self):
        self.policy("verify")
        self.partial("T-0001", "verify")
        self.assertEqual(dc.apply_policy(self.board, self.ws, date=DATE), [])
        items = dc.pending_decisions(self.board, workspace=self.ws)
        self.assertEqual([(i["id"], i["source"]) for i in items], [("T-0001", "ticket-partial")])
        self.assertEqual(meta_of(self.board, "T-0001")["status"], "partial")

    def test_a_partial_prove_ticket_is_not_in_a_select_batch(self):
        self.partial("T-0001", "prove")
        items = dc.pending_decisions(self.board, workspace=self.ws)
        self.assertEqual(len(items), 1)
        self.assertFalse(any(dc._selectable(i) for i in items))
