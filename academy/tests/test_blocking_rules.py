"""The blocking rules, once: board.py and the MCP tickets_update apply ``ac.apply_blocking``,
so the same move gives the same thread and the same error on both transports (and on both
backends); the human may leave a dead route; blocked_by and tried: are validated.

Run from the repo root:  py -m unittest discover academy/tests
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board_store import StoreCase, INST  # noqa: E402

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
from tools import Context, ToolError, tickets as mcp_tickets  # noqa: E402


def core(msg):
    """An error message without its transport's prefix ('T-0005: ', 'refused: ')."""
    return re.sub(r"^(?:T-\d+: |refused: )", "", str(msg))


class Parity(StoreCase):
    """board.py on the file board, the MCP tool on the github board, same seed."""

    def receiver(self, store):
        return Context(cwd=os.path.join(self.tmp, "r1"), workspace=self.ws, store=store,
                       agent="prover", agent_ns="researcher")

    def human(self, store):
        return Context(cwd=self.tmp, workspace=self.ws, store=store)

    def via_board(self, tid, status, who=INST, **kw):
        try:
            bd.transition_ticket(self.files, tid, status, as_instance=who,
                                 agent="prover" if who != "human" else "", **kw)
        except ac.AcademyError as exc:
            return "error", core(exc)
        return "ok", None

    def via_mcp(self, tid, status, human=False, **kw):
        a = {"id": tid, "status": status}
        a["reason"] = kw.pop("reason", "")
        if kw.get("reopen") is not None:
            a["reopen"] = kw.pop("reopen")
        fields = {k: v for k, v in (("waiting_on", kw.get("waiting_on")),
                                    ("blocked_by", kw.get("blocked_by")),
                                    ("reopen_if", kw.get("reopen_if"))) if v}
        if fields:
            a["fields"] = fields
        if kw.get("result"):
            a.setdefault("fields", {})["result"] = kw["result"]
        ctx = self.human(self.gh) if human else self.receiver(self.gh)
        try:
            mcp_tickets.update_ticket(ctx, a)
        except ToolError as exc:
            return "error", core(exc)
        return "ok", None

    def thread(self, store, tid):
        return [(w.split("/")[0], t) for _d, w, t in ac.thread_lines(store.get(tid)[2])]

    def both(self, tid, status, human=False, **kw):
        who = "human" if human else INST
        a = self.via_board(tid, status, who, **dict(kw))
        b = self.via_mcp(tid, status, human, **dict(kw))
        self.assertEqual(a, b, (tid, status, kw))
        self.assertEqual(self.snapshot(self.files), self.snapshot(self.gh), (tid, status))
        self.assertEqual(self.thread(self.files, tid), self.thread(self.gh, tid))
        return a


class TestBlockingParity(Parity):
    # (ticket, status, kwargs, the error that must occur, or None for success)
    CASES = [
        ("T-0003", "blocked", dict(waiting_on=["T-0001"]), None),
        ("T-0003", "blocked", {}, "a blocked ticket needs waiting_on, or both blocked_by "
                                  "and reopen_if"),
        ("T-0002", "blocked", dict(blocked_by="GEO-31", reopen_if="a new invariant",
                                   reason="the induction fails"), None),
        ("T-0002", "blocked", dict(blocked_by="GEO-31"),
         "a dead-route block needs both blocked_by and reopen_if"),
        ("T-0002", "blocked", dict(blocked_by="GEO-31", reopen_if="x", waiting_on=["T-0001"]),
         "blocked is pending (waiting_on) or a dead route (blocked_by and reopen_if), "
         "not both"),
        ("T-0002", "blocked", dict(blocked_by="GEO-31", reopen_if="x"),
         "a dead-route block needs a reason naming what was tried"),
        ("T-0002", "blocked", dict(blocked_by="lol", reopen_if="x", reason="r"),
         "blocked_by must be a ticket or registry id (T-0007, GEO-31, paper:lem:x), "
         "not 'lol'"),
        ("T-0004", "accepted", dict(reopen="a new lemma"), ac.REOPEN_ONLY),   # pending block
        ("T-0001", "accepted", dict(reopen="a new lemma"), ac.REOPEN_ONLY),   # not blocked
        ("T-0005", "in-progress", {},
         "a dead-route ticket reopens only by blocked -> accepted with reopen (the new "
         "mechanism); the sender may cancel, with a reason"),
        ("T-0005", "accepted", {},
         "a dead-route ticket reopens by blocked -> accepted with reopen (the new mechanism)"),
        ("T-0005", "accepted", dict(reopen="a new construction"), None),
        ("T-0002", "rejected", {}, "accepted -> rejected needs a reason"),
        ("T-0001", "accepted", dict(blocked_by="GEO-31"),
         "blocked_by, reopen_if and waiting_on belong to a move to blocked"),
    ]

    def test_same_outcome_error_thread_and_ticket_on_both_transports(self):
        for tid, status, kw, err in self.CASES:
            with self.subTest(tid=tid, status=status, kw=kw):
                self.tearDown()
                self.setUp()                      # every case on a fresh pair of boards
                kind, msg = self.both(tid, status, **kw)
                if err is None:
                    self.assertEqual("ok", kind, msg)
                else:
                    self.assertEqual(("error", err), (kind, msg))

    def test_the_thread_order_is_tried_then_the_fields_then_the_status(self):
        self.both("T-0002", "blocked", blocked_by="GEO-31", reopen_if="a new invariant",
                  reason="the induction fails")
        texts = [t for _w, t in self.thread(self.gh, "T-0002")]
        self.assertEqual(["opened", "tried: the induction fails",
                          "set blocked_by: GEO-31; reopen_if: a new invariant",
                          "status accepted -> blocked"], texts[-4:])

    def test_reopen_leaves_the_reopened_line_before_the_status_line(self):
        self.both("T-0005", "accepted", reopen="a new construction")
        texts = [t for _w, t in self.thread(self.gh, "T-0005")]
        self.assertEqual(["reopened: a new construction", "status blocked -> accepted"],
                         texts[-2:])
        m = self.gh.get("T-0005")[1]
        self.assertNotIn("blocked_by", m)
        self.assertNotIn("reopen_if", m)

    def test_reopen_without_a_status_change_is_refused_by_both(self):
        for tid in ("T-0005", "T-0004", "T-0001"):
            a = self.via_board(tid, self.files.get(tid)[1]["status"], reopen="x")
            b = self.via_mcp(tid, None, reopen="x")
            self.assertEqual(("error", ac.REOPEN_ONLY), a, tid)
            self.assertEqual(a, b, tid)

    def test_a_pending_block_mirrors_blocks_into_the_awaited_ticket_on_both(self):
        self.both("T-0003", "blocked", waiting_on=["T-0006"])
        for s in (self.files, self.gh):
            self.assertIn("T-0003", s.get("T-0006")[1]["blocks"])


class TestHumanLeavesADeadRoute(Parity):
    """docs/protocol.md: the human may make any transition, so a dead route is no trap."""

    def test_the_human_leaves_by_any_transition_with_a_reason(self):
        for status in ("in-progress", "accepted", "open", "cancelled"):
            with self.subTest(status=status):
                self.tearDown()
                self.setUp()
                kind, msg = self.both("T-0005", status, human=True,
                                      reason="the new lemma makes it reachable")
                self.assertEqual(("ok", None), (kind, msg))
                meta, body = self.gh.get("T-0005")[1:]
                self.assertEqual(status, meta["status"])
                self.assertNotIn("blocked_by", meta)
                self.assertNotIn("reopen_if", meta)
                self.assertEqual([], ac.validate_ticket(meta, body))
                texts = [t for _w, t in self.thread(self.gh, "T-0005")]
                self.assertEqual(status == "accepted",
                                 "reopened: the new lemma makes it reachable" in texts)

    def test_the_human_must_still_give_a_reason(self):
        for status in ("in-progress", "accepted"):
            kind, msg = self.both("T-0005", status, human=True)
            self.assertEqual("error", kind)
            self.assertEqual("blocked", self.files.status_of("T-0005"))

    def test_the_receiver_still_has_only_the_reopen_route(self):
        kind, msg = self.both("T-0005", "in-progress", reason="because")
        self.assertEqual("error", kind)
        self.assertIn("reopens only by blocked -> accepted", msg)

    def test_reopen_counts_as_the_human_reason(self):
        self.assertEqual(("ok", None), self.both("T-0005", "accepted", human=True,
                                                 reopen="a new mechanism"))


class TestValidation(unittest.TestCase):
    def meta(self, **kw):
        m = {"id": "T-0001", "title": "t", "kind": "prove", "from": "author@main",
             "to": "researcher@r1", "status": "blocked", "priority": "normal", "ask": "a",
             "deliverable": "d", "budget": {"runs": 1, "max_model": "sonnet"},
             "created": "2026-09-30", "updated": "2026-09-30",
             "blocked_by": "GEO-31", "reopen_if": "a new invariant"}
        m.update(kw)
        return m

    def body(self, *lines):
        b = "\n## Ask\n\na\n\n## Result\n\n\n## Thread\n\n"
        return b + "".join("- 2026-09-30 researcher@r1: %s\n" % t for t in lines)

    def test_blocked_by_accepts_ticket_and_registry_ids(self):
        for ok in ("T-0007", "GEO-31", "Q1", "EX-L3", "PA-5w", "DIR-1", "paper:lem:x",
                   "paper:thm:a", "lab:some-claim", "s1:GEO-31"):
            with self.subTest(ok=ok):
                self.assertEqual([], ac.validate_ticket(self.meta(blocked_by=ok),
                                                        self.body("tried: x")))

    def test_blocked_by_rejects_junk(self):
        for bad in ("lol", "see the thread", "a b", "paper:", ":x", "geo-31", "-"):
            with self.subTest(bad=bad):
                probs = ac.validate_ticket(self.meta(blocked_by=bad), self.body("tried: x"))
                self.assertTrue(any("blocked_by must be a ticket or registry id" in p
                                    for p in probs), probs)

    def test_a_second_dead_route_needs_its_own_tried_line(self):
        first = self.body("tried: induction", "reopened: Prym forms")
        probs = ac.validate_ticket(self.meta(), first)
        self.assertTrue(any("needs a thread line 'tried:" in p for p in probs), probs)
        second = self.body("tried: induction", "reopened: Prym forms", "tried: Prym forms")
        self.assertEqual([], ac.validate_ticket(self.meta(), second))

    def test_one_dead_route_predicate_everywhere(self):
        for m in ({}, {"blocked_by": "x"}, {"reopen_if": "y"},
                  {"blocked_by": "x", "reopen_if": "y"}):
            self.assertEqual(ac.is_dead_route(m), ac.inbox_core.is_dead_route(m))
        import board_codec as bc
        self.assertEqual(["route:dead"], bc.route_labels(self.meta()))


if __name__ == "__main__":
    unittest.main()
