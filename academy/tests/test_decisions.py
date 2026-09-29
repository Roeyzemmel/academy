"""Tests for academy/scripts/decisions.py (behind /academy:decide).

Run from the repo root:  py -m unittest discover academy/tests
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import packets as pk  # noqa: E402
import decisions as dc  # noqa: E402

DATE = "2026-09-28"

ONE_DECISION_BODY = """
## Summary

One run confirms.

## Produced

- Verdict: `file:expert@main/reviews/paper/x/`.

## Established vs assumed

- **Established:** paper:lem:x.

## Evidence

- Run A.

## Decisions needed

### D1. Recolour paper:lem:x now?

- (a) Yes, recolour now.
- (b) Wait until Theorem 1.3 is checked.
- Recommendation: (a), both runs agree.

## Machine notes

None.

## Decision
"""

TWO_DECISION_BODY = """
## Summary

Two decisions.

## Produced

- Nothing.

## Established vs assumed

- **Established:** none.

## Evidence

- n/a

## Decisions needed

### D1. Rename the pack file?

- (a) Yes.
- (b) No.
- Recommendation: (a), it is a typo fix.

### D2. Recolour paper:lem:y?

- (a) Yes.
- (b) No.
- Recommendation: (b), the dependence is unchecked.

## Machine notes

None.

## Decision
"""


def make_workspace(root):
    ws = {"instances": {
        "expert@main": {"role": "expert", "home": os.path.join(root, "papers"),
                      "domains": ["dom-a"]},
        "author@main": {"role": "author", "home": os.path.join(root, "paperhome"),
                      "domains": ["dom-a"], "ns": "paper"},
        "researcher@r1": {"role": "researcher", "home": os.path.join(root, "r1"),
                          "domains": ["dom-b"], "ns": "s1"}},
        "board": os.path.join(root, "board").replace("\\", "/")}
    path = os.path.join(root, "workspace.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(ws, fh)
    return ac.load_workspace(path), path


class DecisionsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-decisions-")
        self.ws, self.ws_path = make_workspace(self.tmp)
        self.board = self.ws["board"]
        os.makedirs(self.board)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ticket(self, **kw):
        args = dict(to="expert@main", title="Check something", ask="Check it",
                    deliverable="an answer", kind="verify", as_instance="author@main",
                    workspace=self.ws, date=DATE, budget={"runs": 1, "max_model": "sonnet"})
        args.update(kw)
        return bd.create_ticket(self.board, **args)

    def packet(self, body=ONE_DECISION_BODY, instance="expert@main", ticket=None, **kw):
        kw.setdefault("title", "Verify lem x")
        kw.setdefault("kind", "verification")
        kw.setdefault("subject", ["paper:lem:x"])
        kw.setdefault("status_before", "sketch")
        kw.setdefault("status_proposed", "proved")
        title = kw.pop("title")
        return pk.create_packet(self.board, instance, title,
                                by=instance + "/review-chair", ticket=ticket,
                                body=body, workspace=self.ws, date=DATE, **kw)


class TestSelectOptions(unittest.TestCase):
    def test_few_options_kept_as_is_recommended_first(self):
        kept, note = dc.select_options({"a": "Yes", "b": "No"}, "b")
        self.assertIsNone(note)
        self.assertEqual([k for k, _ in kept], ["b", "a"])

    def test_more_than_four_keeps_recommended_and_notes_the_rest(self):
        options = {
            "a": "Yes, recolour now",
            "b": "Wait for Theorem 1.3",
            "c": "Wait for the referee",
            "d": "Ask Barak first",
            "e": "Ask Victoria first",
            "f": "Drop the lemma entirely",
        }
        kept, note = dc.select_options(options, "f", max_options=4)
        self.assertEqual(len(kept), 4)
        self.assertEqual(kept[0][0], "f")                # recommended always kept, first
        self.assertIsNotNone(note)
        omitted = set(options) - {k for k, _ in kept}
        self.assertEqual(len(omitted), 2)
        self.assertIn(", ".join(sorted(omitted)) if len(omitted) else "", note)

    def test_no_recommendation_still_caps_at_four(self):
        options = {chr(97 + i): "option %d text here" % i for i in range(6)}
        kept, note = dc.select_options(options, None, max_options=4)
        self.assertEqual(len(kept), 4)
        self.assertIsNotNone(note)


class TestPendingDecisions(DecisionsCase):
    def test_packet_decision_listed_with_capped_options(self):
        self.packet()
        items = dc.pending_decisions(self.board)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["id"], "P-0001/D1")
        self.assertEqual(it["instance"], "expert@main")
        self.assertEqual(it["source"], "packet")
        self.assertEqual(it["kind"], "substantive")          # status_proposed: proved
        self.assertTrue(it["question"].endswith("?"))
        self.assertLessEqual(len(it["options"]), 4)
        self.assertEqual(it["recommendation"], "(a), both runs agree.")

    def test_already_decided_decision_is_excluded(self):
        self.packet(body=TWO_DECISION_BODY, kind="notation")
        pk.decide_packet(self.board, "P-0001", "a", 1, date=DATE)
        items = dc.pending_decisions(self.board)
        self.assertEqual([i["id"] for i in items], ["P-0001/D2"])

    def test_fully_decided_packet_contributes_nothing(self):
        self.packet(body=TWO_DECISION_BODY, kind="notation")
        pk.decide_packet(self.board, "P-0001", "a", 1, date=DATE)
        pk.decide_packet(self.board, "P-0001", "b", 2, date=DATE)
        self.assertEqual(dc.pending_decisions(self.board), [])

    def test_notation_packet_is_mechanical(self):
        self.packet(body=TWO_DECISION_BODY, kind="notation", status_before=None,
                    status_proposed=None)
        items = dc.pending_decisions(self.board)
        self.assertTrue(all(i["kind"] == "mechanical" for i in items))

    def test_human_open_ticket_is_pending(self):
        self.ticket(to="human", kind="decision", ask="Spend a second run on this?",
                   as_instance="expert@main")
        items = dc.pending_decisions(self.board)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["id"], "T-0001")
        self.assertEqual(it["source"], "ticket-human")
        self.assertEqual(it["instance"], "expert@main")        # the sender, waiting on human
        self.assertEqual(it["kind"], "substantive")          # kind: decision
        self.assertIsNone(it["recommendation"])

    def test_human_ticket_not_yet_open_is_excluded(self):
        self.ticket(to="human", as_instance="expert@main")
        bd.transition_ticket(self.board, "T-0001", "cancelled", reason="moot",
                             as_instance="expert@main", date=DATE)
        self.assertEqual(dc.pending_decisions(self.board), [])

    def test_blocked_waiting_on_human_ticket_is_pending_regardless_of_folder(self):
        self.ticket(to="expert@main", kind="other")            # any receiver folder
        bd.transition_ticket(self.board, "T-0001", "blocked", waiting_on=["human"],
                             as_instance="expert@main", date=DATE)
        items = dc.pending_decisions(self.board)
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["source"], "ticket-blocked")
        self.assertEqual(it["instance"], "expert@main")        # the stuck receiver
        self.assertEqual(it["kind"], "mechanical")           # kind: other

    def test_blocked_waiting_on_a_ticket_not_human_is_excluded(self):
        self.ticket(title="first")
        self.ticket(title="second", to="researcher@r1", as_instance="human")
        bd.transition_ticket(self.board, "T-0001", "blocked", waiting_on=["T-0002"],
                             as_instance="expert@main", date=DATE)
        self.assertEqual(dc.pending_decisions(self.board), [])

    def test_instance_filter(self):
        self.packet(instance="expert@main")
        self.ticket(to="human", as_instance="author@main", title="other")
        self.assertEqual(len(dc.pending_decisions(self.board, instance="expert@main")), 1)
        self.assertEqual(len(dc.pending_decisions(self.board, instance="author@main")), 1)
        self.assertEqual(dc.pending_decisions(self.board, instance="researcher@r1"), [])

    def test_unblocks_names_the_linked_ticket_and_what_it_blocks(self):
        self.ticket(title="verify", to="expert@main")               # T-0001
        self.ticket(title="downstream", to="researcher@r1", as_instance="human")       # T-0002
        bd.transition_ticket(self.board, "T-0002", "blocked", waiting_on=["T-0001"],
                             as_instance="researcher@r1", date=DATE)
        self.packet(ticket="T-0001")
        items = dc.pending_decisions(self.board)
        it = [i for i in items if i["id"] == "P-0001/D1"][0]
        self.assertIn("T-0001", it["unblocks"])
        self.assertIn("T-0002", it["unblocks"])

    def test_staleness_hint_on_shared_subject_decided_later(self):
        self.packet(subject=["paper:lem:x"], title="early")
        self.packet(subject=["paper:lem:x"], title="later")
        pk.decide_packet(self.board, "P-0002", "b", 1, date="2026-09-29")
        items = dc.pending_decisions(self.board)
        early = [i for i in items if i["id"] == "P-0001/D1"][0]
        self.assertIsNotNone(early["stale"])
        self.assertIn("P-0002", early["stale"])


class TestBatches(DecisionsCase):
    def test_order_and_size(self):
        self.packet(kind="notation", subject=[], status_before=None, status_proposed=None,
                   title="mech")
        self.ticket(to="human", kind="decision", as_instance="expert@main", title="subst")
        items = dc.pending_decisions(self.board)
        bs = dc.batches(items, size=1)
        self.assertEqual(len(bs), 2)
        self.assertEqual(len(bs[0]), 1)
        # substantive (the human ticket) sorts before mechanical (the notation packet)
        self.assertEqual(bs[0][0]["kind"], "substantive")
        self.assertEqual(bs[1][0]["kind"], "mechanical")

    def test_batch_size_default_four(self):
        for i in range(6):
            self.ticket(to="human", as_instance="expert@main", title="t%d" % i)
        bs = dc.batches(dc.pending_decisions(self.board))
        self.assertEqual([len(b) for b in bs], [4, 2])


class TestRecord(DecisionsCase):
    def test_record_packet_decision_by_letter(self):
        self.packet(body=TWO_DECISION_BODY, kind="notation")
        out = dc.record(self.board, "P-0001/D1", "a", date=DATE)
        self.assertEqual(out["decision"], 1)
        _m, body = pk.read_packet(pk.get_packet(self.board, "P-0001")[0])
        self.assertEqual(ac.packet_answers(body)[1][0], "(a)")

    def test_record_bare_packet_id_needs_exactly_one_pending(self):
        self.packet(body=TWO_DECISION_BODY, kind="notation")
        with self.assertRaises(ac.AcademyError):
            dc.record(self.board, "P-0001", "a", date=DATE)     # two pending: ambiguous
        dc.record(self.board, "P-0001/D1", "a", date=DATE)
        out = dc.record(self.board, "P-0001", "b", date=DATE)   # now exactly one left
        self.assertEqual(out["decision"], 2)

    def test_record_human_ticket_proceed_transitions_to_accepted(self):
        self.ticket(to="human", as_instance="expert@main")
        out = dc.record(self.board, "T-0001", "a", comment="go ahead", date=DATE)
        self.assertEqual(out["status"], "accepted")
        meta, body = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        self.assertEqual(meta["status"], "accepted")
        texts = [t for _d, _w, t in ac.thread_lines(body)]
        self.assertTrue(any("go ahead" in t for t in texts))

    def test_record_human_ticket_decline_transitions_to_rejected(self):
        self.ticket(to="human", as_instance="expert@main")
        out = dc.record(self.board, "T-0001", "decline", date=DATE)
        self.assertEqual(out["status"], "rejected")
        meta, _b = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        self.assertEqual(meta["status"], "rejected")

    def test_record_blocked_ticket_proceed_clears_waiting_on(self):
        self.ticket(to="expert@main")
        bd.transition_ticket(self.board, "T-0001", "blocked", waiting_on=["human"],
                             as_instance="expert@main", date=DATE)
        dc.record(self.board, "T-0001", "proceed", date=DATE)
        meta, body = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        self.assertEqual(meta["status"], "accepted")
        self.assertEqual(meta["waiting_on"], [])
        self.assertEqual(ac.validate_ticket(meta, body), [])

    def test_record_rejects_bad_id(self):
        with self.assertRaises(ac.AcademyError):
            dc.record(self.board, "not-an-id", "a")

    def test_record_ticket_rejects_bad_choice(self):
        self.ticket(to="human", as_instance="expert@main")
        with self.assertRaises(ac.AcademyError):
            dc.record(self.board, "T-0001", "maybe")

    def test_record_never_touches_other_tickets(self):
        """Recording a decision starts no work (budget.md rule 3): only its own file changes."""
        self.ticket(to="human", as_instance="expert@main", title="first")
        p2 = self.ticket(to="researcher@r1", title="second", as_instance="human")
        dc.record(self.board, "T-0001", "a", date=DATE)
        meta2, _b2 = bd.read_ticket(p2)
        self.assertEqual(meta2["status"], "open")


class TestAcceptRecommended(DecisionsCase):
    def test_dry_run_writes_nothing(self):
        self.packet(kind="notation")
        out = dc.accept_recommended(self.board, dry_run=True, date=DATE)
        self.assertEqual(out, [{"id": "P-0001/D1", "choice": "a"}])
        _m, body = pk.read_packet(pk.get_packet(self.board, "P-0001")[0])
        self.assertEqual(ac.packet_answers(body), {})

    def test_mechanical_only_skips_substantive(self):
        self.packet(kind="citation", title="cite")           # substantive kind
        self.packet(kind="notation", title="notation", subject=[], status_before=None,
                   status_proposed=None)
        out = dc.accept_recommended(self.board, mechanical_only=True, date=DATE)
        self.assertEqual([o["id"] for o in out], ["P-0002/D1"])
        _m, body1 = pk.read_packet(pk.get_packet(self.board, "P-0001")[0])
        self.assertEqual(ac.packet_answers(body1), {})

    def test_never_accepts_a_ticket_decision(self):
        self.ticket(to="human", kind="decision", as_instance="expert@main")
        out = dc.accept_recommended(self.board, date=DATE)
        self.assertEqual(out, [])
        meta, _b = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        self.assertEqual(meta["status"], "open")

    def test_applies_and_decides_a_single_decision_packet(self):
        self.packet(kind="notation")
        out = dc.accept_recommended(self.board, date=DATE)
        self.assertEqual(out, [{"id": "P-0001/D1", "choice": "a"}])
        meta, body = pk.read_packet(pk.get_packet(self.board, "P-0001")[0])
        self.assertEqual(meta["state"], "decided")
        self.assertEqual(ac.packet_answers(body)[1][0], "(a)")


class TestCLI(DecisionsCase):
    def _base(self):
        return ["--board", self.board, "--workspace", self.ws_path]

    def test_list_json_and_record_roundtrip(self):
        self.packet(kind="notation")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(dc.main(self._base() + ["list", "--json"]), 0)
        rows = json.loads(out.getvalue())
        self.assertEqual(rows[0]["id"], "P-0001/D1")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(dc.main(self._base() + ["record", "P-0001/D1",
                                                      "--choice", "a"]), 0)
        self.assertEqual(json.loads(out.getvalue())["decided"], True)

    def test_batches_cli(self):
        self.ticket(to="human", as_instance="expert@main")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(dc.main(self._base() + ["batches", "--json", "--size", "1"]), 0)
        self.assertEqual(len(json.loads(out.getvalue())), 1)

    def test_accept_recommended_cli_dry_run(self):
        self.packet(kind="notation")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(dc.main(self._base() + ["accept-recommended", "--dry-run",
                                                      "--json"]), 0)
        self.assertEqual(json.loads(out.getvalue()), [{"id": "P-0001/D1", "choice": "a"}])

    def test_bad_id_exits_nonzero(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            rc = dc.main(self._base() + ["record", "X-0001", "--choice", "a"])
        self.assertEqual(rc, 1)
        self.assertIn("error:", err.getvalue())


if __name__ == "__main__":
    unittest.main()
