"""routes.py: a decided edit or a delivered argument is landed, never sent to research.

#92 (2026-11-20 board audit): T-1441 (an `apply` ticket carrying the human's decided
hypothesis) and T-1385 (a `write` ticket whose repair T-1618 had delivered) went to
research a fourth time, because the ask's wording matched ``RE_NEEDS_ARGUMENT`` and
``proved_source`` skipped the paper's own namespace and ignored delivered tickets. The
metas below are the live tickets' fields of that morning.
"""

import json
import os
import subprocess
import sys
import unittest
import unittest.mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fixtures import SCRIPTS, Sandbox  # noqa: E402
import routes  # noqa: E402
import _academy as ac  # noqa: E402

T1441 = {
    "id": "T-1441", "kind": "apply", "from": "author@t", "to": "author@t",
    "status": "accepted",
    "title": "thm:arithmetic-billiard-goal: add the hypothesis that Q has no marked "
             "regular points and no semi-corners (the human, 2026-11-15)",
    "ask": "Add to paper:thm:arithmetic-billiard-goal (sections/introduction.tex, "
           "conjectural) the hypothesis that Q carries no marked regular points and no "
           "semi-corners (Sigma_Q = V(Q)), per the human's word of 2026-11-15.",
    "refs": ["paper:thm:arithmetic-billiard-goal"],
}
T1385 = {
    "id": "T-1385", "kind": "write", "from": "author@t", "to": "author@t",
    "status": "accepted",
    "title": "Repair the proof of lem:periodic-one-point: \"It is injective\" (l.950) is "
             "false for the unlabelled Sigma_Y (T-1236 run B, F2)",
    "ask": "A missing step in the proof of lem:periodic-one-point: the sentence \"It is "
           "injective\" at markings.tex:950 fails for the unlabelled Sigma_Y (square "
           "torus, Sigma_X={0}, p=(1/2,0): the map is 2-to-1); the conclusion survives "
           "by countability.",
    "refs": ["paper:lem:periodic-one-point", "P-0358", "T-1236", "T-1379", "T-1618"],
}
#: the tickets T-1385 names, as the board had them (T-1618 delivered the repair)
BOARD = {
    "T-1236": {"id": "T-1236", "kind": "verify", "status": "closed", "final_to": None},
    "T-1379": {"id": "T-1379", "kind": "verify", "status": "blocked", "final_to": None},
    "T-1618": {"id": "T-1618", "kind": "research", "status": "closed",
               "final_to": "researcher"},
}


def _never(*_a, **_k):
    raise AssertionError("no lookup is needed for this route")


class LiveTicketTests(unittest.TestCase):
    def route(self, meta, registry=None, board=None):
        reg = registry or {}
        brd = BOARD if board is None else board
        with unittest.mock.patch.object(routes, "_registry_status",
                                        side_effect=lambda q: reg.get(q)), \
                unittest.mock.patch.object(routes, "_workspace_tickets",
                                           return_value=brd.get):
            return routes.route(meta)

    def test_t1441_an_apply_ticket_is_never_sent_to_research(self):
        self.assertTrue(routes.needs_argument(T1441))        # the wording still matches
        with unittest.mock.patch.object(routes, "_registry_status", side_effect=_never), \
                unittest.mock.patch.object(routes, "_workspace_tickets", side_effect=_never):
            r = routes.route(T1441)
        self.assertEqual(("agent", "math-editor"), (r["how"], r["target"]))
        self.assertIn("already decided", r["why"])

    def test_t1385_a_write_ticket_naming_a_delivered_research_ticket_lands_it(self):
        self.assertTrue(routes.needs_argument(T1385))
        r = self.route(T1385)
        self.assertEqual(("agent", "math-writer"), (r["how"], r["target"]))
        self.assertIn("T-1618", r["why"])

    def test_a_repair_of_a_proved_paper_claim_without_a_delivered_argument_goes_to_research(self):
        """The paper's own namespace does not count for proved_source: a repair asked of a
        paper claim proved on the human's word or with a GAP review needs an argument
        (T-1387, T-1626); only a delivered argument ticket lands it (T-1385)."""
        with unittest.mock.patch.object(routes, "_own_ns", return_value="paper"):
            r = self.route(T1385, registry={"paper:lem:periodic-one-point": "proved-modulo"},
                           board={})
        self.assertEqual(("research", "expert"), (r["how"], r["target"]))

    def test_t1385_without_a_delivered_argument_still_goes_to_research(self):
        open_ = dict(BOARD, **{"T-1618": dict(BOARD["T-1618"], status="in-progress")})
        r = self.route(T1385, registry={"paper:lem:periodic-one-point": "sketch"},
                       board=open_)
        self.assertEqual(("research", "expert"), (r["how"], r["target"]))


class DeliveredArgumentTests(unittest.TestCase):
    def test_a_parked_ticket_finds_its_research_ticket_in_waiting_on(self):
        """The writer parks the self-ticket on the research ticket it filed (waiting_on),
        often without listing it in refs (review of e68e18a)."""
        meta = {"kind": "write", "refs": ["paper:lem:x"], "waiting_on": ["T-0009"]}
        board = {"T-0009": {"id": "T-0009", "kind": "research", "status": "delivered",
                            "final_to": "researcher"}}
        self.assertEqual("T-0009", routes.delivered_argument(meta, board.get))

    def test_scalar_or_odd_refs_do_not_crash(self):
        for refs in (5, None, "T-0001", [None, 5, ["T-1"]]):
            r = routes.route({"kind": "write", "ask": "a new argument", "refs": refs},
                             ticket_of=lambda _t: None)
            self.assertEqual("research", r["how"], refs)

    def test_only_a_delivered_or_closed_argument_ticket_counts(self):
        meta = {"kind": "write", "refs": ["paper:lem:x", "T-0001"]}
        for kind, status, final_to, want in (
                ("research", "delivered", "researcher", "T-0001"),
                ("research", "closed", "researcher", "T-0001"),
                ("prove", "delivered", None, "T-0001"),
                ("research", "in-progress", "researcher", ""),
                ("research", "rejected", "researcher", ""),
                ("research", "cancelled", "researcher", ""),
                ("verify", "delivered", None, ""),
                ("cite", "closed", None, ""),
                ("research", "delivered", "scientist", "")):     # an experiment, not an argument
            board = {"T-0001": {"id": "T-0001", "kind": kind, "status": status,
                                "final_to": final_to}}
            self.assertEqual(want, routes.delivered_argument(meta, board.get),
                             (kind, status, final_to))

    def test_refs_that_are_not_tickets_are_skipped_and_an_unreadable_board_is_none(self):
        meta = {"kind": "write", "refs": ["paper:lem:x", "P-0001", "file:a.md"]}
        self.assertEqual("", routes.delivered_argument(meta, _never))
        boom = unittest.mock.Mock(side_effect=OSError("no board"))
        self.assertEqual("", routes.delivered_argument({"refs": ["T-0002"]}, boom))
        with unittest.mock.patch.object(routes, "_workspace_tickets", return_value=boom), \
                unittest.mock.patch.object(routes, "_registry_status", return_value=None):
            r = routes.route({"kind": "write", "ask": "fill the gap in step 2",
                              "refs": ["paper:lem:x", "T-0002"]})
        self.assertEqual("research", r["how"])

    def test_proved_source_skips_the_own_namespace_but_counts_another(self):
        """The ticket's own namespace (``paper``) is skipped; another namespace's proved
        claim (a notebook) still lands (T-0426)."""
        ws = {"instances": {"author@t": {"ns": "paper"}}}
        status = {"paper:lem:x": "proved", "flat:FND-14": "proved-modulo"}.get
        with unittest.mock.patch.object(ac, "load_workspace", return_value=ws), \
                unittest.mock.patch.object(routes, "_registry_status", side_effect=status):
            self.assertEqual("", routes.proved_source(
                {"kind": "write", "to": "author@t", "refs": ["paper:lem:x"]}))
            self.assertEqual("flat:FND-14", routes.proved_source(
                {"kind": "write", "to": "author@t", "refs": ["flat:FND-14"]}))


#: #92 remainder (2026-11-20 audit): the Author's kinds without a route went to the human
#: even after the human had accepted the ticket. The metas are the live tickets' fields.
T0085 = {
    "id": "T-0085", "kind": "question", "from": "human", "to": "author@t",
    "status": "accepted",
    "title": "fact:forgetful-props: replace item 2's openness with LMW16 Lemma 6 as stated "
             "(Ada's decision)",
    "ask": "Edit fact:forgetful-props (markings.tex:106-135) per Ada's decision on T-0081: "
           "replace the subspace-topology openness claim in item 2 and the Moreover clause "
           "with LMW16 Lemma 6 quoted as stated. Keep item 1 (ordering-independence) as "
           "written.",
    "refs": ["paper:fact:forgetful-props", "bib:LMW16#Lemma 6"],
}
T0068 = {
    "id": "T-0068", "kind": "other", "from": "researcher@flat", "to": "author@t",
    "status": "accepted",
    "title": "thm:main-resolvable-4k is false as stated under the draft's inclusive "
             "convention: add K_M = C_4k",
    "ask": "Ada's decision 2026-09-28. thm:main-resolvable-4k is refuted as written. THE "
           "REPAIR: add the hypothesis K_M = C_{4k} to the theorem.",
    "refs": ["paper:thm:main-resolvable-4k", "flat:resolvable-4k-blocking"],
}
T0351 = {
    "id": "T-0351", "kind": "question", "from": "expert@t", "to": "author@t",
    "status": "accepted",
    "title": "Wording items for landing FND-20's \"Paper text to land\" in "
             "rmk:unfolding-quotient (review T-0337)",
    "ask": "When landing flat:FND-20's \"Paper text to land\" as the proof of "
           "paper:rmk:unfolding-quotient, apply these wording items from the two CONFIRMED "
           "reviews. None changes the mathematics.",
    "refs": ["flat:FND-20", "paper:rmk:unfolding-quotient", "T-0337", "T-0348"],
}
T0086 = {
    "id": "T-0086", "kind": "question", "from": "expert@t", "to": "author@t",
    "status": "accepted",
    "title": "Repair proof of lem:marking-full-preimage (GAP, markings.tex:300)",
    "ask": "Repair the proof of lem:marking-full-preimage (sections/markings.tex) after run "
           "A's GAP; the statement itself was not faulted.",
    "refs": ["paper:lem:marking-full-preimage", "paper:lem:covering-moduli-proper"],
}
T0051 = {
    "id": "T-0051", "kind": "write", "from": "human", "to": "author@t", "status": "accepted",
    "title": "Agenda pass: lower required for sketch-kept results, add first milestone "
             "(P-0006 D2)",
    "ask": "Run an /author:agenda pass that lowers required to sketch for results the paper "
           "keeps as sketches and adds a first milestone.",
    "refs": ["P-0006", "file:author@t/Drafts/agenda.md"],
}
#: T-1494: the parent of research ticket T-1664 (by its parent field only: the refs name
#: the verify T-1368, and waiting_on was emptied when it was released)
T1494 = {
    "id": "T-1494", "kind": "write", "from": "author@t", "to": "author@t",
    "status": "accepted",
    "title": "Add the missing clause and convention found in the review of "
             "cor:full-preimage-locus (T-1368)",
    "ask": "Add the hypothesis/convention: H^{*0}=H for E empty (Notation), and Y marked at "
           "Sigma containing the zeros of omega_Y at t_0.",
    "refs": ["T-1368", "P-0369"], "waiting_on": [],
}
BOARD_1494 = [
    {"id": "T-1368", "kind": "verify", "status": "closed", "parent": "T-0628"},
    {"id": "T-1664", "kind": "research", "status": "closed", "final_to": "researcher",
     "parent": "T-1494"},
]


class UnroutedKindTests(unittest.TestCase):
    """question and other have Author routes; decision stays the human's."""

    def route(self, meta, board=()):
        look = routes.TicketLookup(lambda: list(board))
        with unittest.mock.patch.object(routes, "_registry_status", return_value=None), \
                unittest.mock.patch.object(routes, "_human", return_value="Ada"):
            return routes.route(meta, ticket_of=look)

    def test_a_question_is_answered_by_the_writer(self):
        r = self.route(T0351)
        self.assertEqual(("agent", "math-writer"), (r["how"], r["target"]))
        self.assertIn("answer", r["why"])

    def test_a_question_or_other_naming_a_decided_edit_goes_to_the_editor(self):
        r = self.route(T0085)
        self.assertEqual(("agent", "math-editor"), (r["how"], r["target"]))
        # T-0068 is decided too, but adds a hypothesis: the writer (and its research ticket)
        r = self.route(T0068)
        self.assertEqual(("agent", "math-writer"), (r["how"], r["target"]))
        self.assertTrue(routes.decided_edit(T0068, human="Ada"))
        # the human's word, unnamed, counts too (T-1441's phrase)
        r = self.route(dict(T0351, ask="Reword item 2 per the human's word of 2026-11-15."))
        self.assertEqual("math-editor", r["target"])

    def test_the_human_s_chosen_alternative_is_a_decided_edit(self):
        """#86: an accepted question/other is not bounced back as a gate. The alternative the
        human chose on /academy:decide (decision_choice) makes it a decided edit; a plain
        acceptance keeps the writer, told not to block on the human for it again."""
        ask = "Decide: drop the note, or a literature lookup and a one-line remark."
        meta = dict(T0351, ask=ask, decision_choice="(a) drop the note")
        self.assertTrue(routes.decided_edit(meta, human="Ada"))
        self.assertEqual("math-editor", self.route(meta)["target"])
        r = self.route(dict(T0351, decision_choice="proceed"))
        self.assertEqual("math-writer", r["target"])
        self.assertIn("accepted it", r["why"])
        self.assertIn("never block on the human", r["why"])
        for choice in ("not now (2026-11-27)", None):
            m = dict(T0351, ask=ask, decision_choice=choice)
            self.assertFalse(routes.decided_edit(m, human="Ada"))
            self.assertNotIn("accepted it", self.route(m)["why"])

    def test_a_choice_still_open_is_not_a_decided_edit(self):
        for ask in ("Decide the repair: restrict the hypothesis, or recolour.",
                    "The wording is to be decided; see the reviewer's decision table.",
                    "Which reading is undecided.",
                    # review of badbc50: a decision still wanted, or another's decision
                    "This needs Ada's decision between A and B.",
                    "Awaiting the human's decision on K_P.",
                    "Pending Ada's ruling on the convention.",
                    "Wait for the human's choice of reading.",
                    "The reviewer decided on T-12 that it is a GAP; what is the fix?"):
            self.assertFalse(routes.decided_edit({"ask": ask}, human="Ada"), ask)
            self.assertEqual("math-writer", self.route(dict(T0351, ask=ask))["target"], ask)

    def test_a_decided_edit_that_needs_an_argument_goes_to_the_writer(self):
        """T-0368 (review of badbc50): the human's decision removes an exception, i.e. it
        strengthens a statement; math-writer makes the change and files the research
        ticket for the argument, math-editor would only edit."""
        meta = dict(T0351, title="Unite plugs and semi-corners",
                    ask="Ada's decision: drop the semi-corner exception; add the hypothesis "
                        "that P has no plugs to thm:x.")
        self.assertTrue(routes.decided_edit(meta, human="Ada"))
        self.assertTrue(routes.needs_argument(meta))
        r = self.route(meta)
        self.assertEqual(("agent", "math-writer"), (r["how"], r["target"]))
        self.assertIn("research", r["why"])
        # the live T-0368 wording: the exception goes, so the statement is stronger
        t0368 = dict(T0351, title="Unite plugs and semi-corners so pathologies are inherited "
                                  "without exception",
                     ask="Ada's decision while preparing the talk: plugs and semi-corners "
                         "form one pathology. Then prop:pathologies-inherited holds without "
                         "its semi-corner exception.")
        self.assertTrue(routes.needs_argument(t0368))
        self.assertEqual("math-writer", self.route(t0368)["target"])
        for ask in ("Remove the exception in item 2 of lem:x.",
                    "Drop the semi-corner exception from prop:y."):
            self.assertTrue(routes.needs_argument({"ask": ask}), ask)
        self.assertFalse(routes.needs_argument({"ask": "Typeset the exception list as a "
                                                       "table."}))

    def test_a_question_needing_an_argument_goes_to_research(self):
        r = self.route(T0086)
        self.assertEqual(("research", "expert"), (r["how"], r["target"]))

    def test_other_and_a_missing_kind_take_the_defined_fallback(self):
        for kind in ("other", None):
            r = self.route(dict(T0351, kind=kind))
            self.assertEqual(("agent", "math-writer"), (r["how"], r["target"]), kind)

    def test_a_decision_ticket_is_the_humans(self):
        r = self.route({"kind": "decision", "title": "Status of paper:thm:x -> proved-modulo"})
        self.assertEqual(("human", "human"), (r["how"], r["target"]))

    def test_an_agenda_pass_routes_to_the_agenda_skill(self):
        for kind in ("write", "question", "other", "apply"):
            r = self.route(dict(T0051, kind=kind))
            self.assertEqual(("skill", "author:agenda"), (r["how"], r["target"]), kind)
        r = self.route({"kind": "question", "title": "Run /author:agenda gaps before the round"})
        self.assertEqual("author:agenda", r["target"])
        # a ticket that only mentions the agenda, or an entry of it, is not a pass
        for title in ("Write up lem:x", "Update the agenda entry for lem:x",
                      "Refresh the agenda entry of prop:y and its proof"):
            r = self.route({"kind": "write", "title": title,
                            "ask": "its agenda entry is paper:lem:x"})
            self.assertEqual("math-writer", r["target"], title)
        # another role's kind is still rejected
        self.assertEqual("reject", self.route(dict(T0051, kind="prove"))["how"])


class ReturnLegTests(unittest.TestCase):
    """A parent whose research child came back lands it, found by the child's parent field
    (T-1494 / T-1664: the router sent it down the research route again)."""

    def route(self, meta, board):
        with unittest.mock.patch.object(routes, "_registry_status", return_value=None):
            return routes.route(meta, ticket_of=routes.TicketLookup(lambda: list(board)))

    def test_t1494_lands_the_delivered_child(self):
        self.assertTrue(routes.needs_argument(T1494))
        r = self.route(T1494, BOARD_1494)
        self.assertEqual(("agent", "math-writer"), (r["how"], r["target"]))
        self.assertIn("T-1664", r["why"])

    def test_a_child_not_back_or_an_experiment_child_does_not_count(self):
        for status, final_to in (("cancelled", "researcher"), ("delivered", "scientist")):
            board = [BOARD_1494[0], dict(BOARD_1494[1], status=status, final_to=final_to)]
            r = self.route(T1494, board)
            self.assertEqual(("research", "expert"), (r["how"], r["target"]),
                             (status, final_to))

    def test_a_child_still_out_is_never_filed_again(self):
        # #128: a research child still out that the parent does not wait on is the
        # argument asked separately; the parent goes to its writer, never to research
        board = [BOARD_1494[0], dict(BOARD_1494[1], status="in-progress")]
        r = self.route(T1494, board)
        self.assertEqual(("wait", "T-1664"), (r["how"], r["target"]))
        self.assertIn("block this ticket waiting on it", r["why"])
        # a parent that waits on it (or blocks it) is parked on it: not separate
        for field in ("waiting_on", "blocks"):
            meta = dict(T1494, **{field: ["T-1664"]})
            self.assertEqual("", routes.separate_argument(
                meta, routes.TicketLookup(lambda: list(board))), field)


#: T-1948 as filed (2026-11-23): editorial, its research child T-1949 separate
T1948 = {
    "id": "T-1948", "kind": "write", "from": "author@t", "to": "author@t",
    "status": "accepted",
    "title": "defn:flat-structure: drop the discreteness clause; state \"Sigma_S discrete\" "
             "only where used (the human 2026-11-23, P-0500 D1)",
    "ask": "Remove \", which is required to be discrete in $S$\" from the completion clause "
           "of defn:flat-structure (l.112) and add the hypothesis \"$\\Sigma_S$ discrete\" "
           "only to the statements whose proofs use it (the human's option 1, 2026-11-23)",
    "refs": ["paper:defn:flat-structure", "P-0500"], "waiting_on": [], "blocks": ["T-1950"],
}


class EditorialTests(unittest.TestCase):
    """#128: T-1948, an editorial write ticket, was routed to research twice."""

    def route(self, meta, board=()):
        with unittest.mock.patch.object(routes, "_registry_status", return_value=None):
            return routes.route(meta, ticket_of=routes.TicketLookup(lambda: list(board)))

    def test_the_first_run_files_research_without_a_marker(self):
        r = self.route(T1948)                    # "add the hypothesis": as before
        self.assertEqual("research", r["how"])

    def test_an_editorial_marker_routes_to_the_writer(self):
        for line in ("EDITORIAL ONLY: it needs no new argument.",
                     "Editorial: drop the clause.", "This needs no argument.",
                     "Adding a hypothesis is not a new argument.",
                     "No new argument is needed."):
            meta = dict(T1948, ask=T1948["ask"] + ". " + line)
            self.assertFalse(routes.needs_argument(meta), line)
            r = self.route(meta)
            self.assertEqual(("agent", "math-writer"), (r["how"], r["target"]), line)

    def test_a_marker_does_not_hide_a_real_ask(self):
        for line in ("Fill the gap with a new argument.", "the editorial board asks"):
            self.assertTrue(routes.needs_argument(dict(T1948, ask=line + " Prove that X.")),
                            line)

    def test_a_ticket_needing_the_argument_t1949_asks_waits_on_it(self):
        board = [{"id": "T-1949", "kind": "research", "status": "open", "to": "expert@t",
                  "final_to": "researcher", "parent": "T-1948"}]
        r = self.route(dict(T1948, ask="Prove that the marked set is discrete."), board)
        self.assertEqual(("wait", "T-1949"), (r["how"], r["target"]))

    def test_a_child_still_out_holds_an_older_delivered_one(self):
        """T-0876 (review of badbc50): an older closed child (another gap) does not land
        the ticket while the child for its current gap is still blocked."""
        meta = dict(T1494, id="T-0876")
        board = [{"id": "T-0880", "kind": "research", "status": "blocked",
                  "final_to": "researcher", "parent": "T-0876"},
                 {"id": "T-0881", "kind": "research", "status": "closed",
                  "final_to": "researcher", "parent": "T-0876", "result": "a proof"}]
        self.assertEqual("", routes.delivered_argument(meta, routes.TicketLookup(lambda: board)))
        # not landed, and not filed again either (#128): the writer, told to wait on T-0880
        r = self.route(meta, board)
        self.assertEqual(("wait", "T-0880"), (r["how"], r["target"]))
        self.assertNotIn("delivered", r["why"])

    def test_only_the_newest_child_counts(self):
        older = {"id": "T-0010", "kind": "research", "status": "closed",
                 "final_to": "researcher", "parent": "T-1494", "result": "proved"}
        newer = dict(older, id="T-0020", status="cancelled")
        look = routes.TicketLookup(lambda: [older, newer])
        self.assertEqual("T-0010", routes.delivered_argument(T1494, look))   # cancelled: skipped
        newest = dict(older, id="T-0030", kind="prove", result="the lemma is unproved")
        look = routes.TicketLookup(lambda: [older, newest])
        self.assertEqual("", routes.delivered_argument(T1494, look))

    def test_a_child_returned_unproved_gap_or_refuted_does_not_count(self):
        """T-1341 (review of badbc50): closed with 'returned unproved: no lead'."""
        for result in ("child T-1392 closed (returned unproved: no lead)",
                       "GAP at step 3; no repair found", "the statement is refuted",
                       "Not proved: the gap remains open"):
            board = [dict(BOARD_1494[1], result=result)]
            self.assertEqual("", routes.delivered_argument(
                T1494, routes.TicketLookup(lambda b=board: b)), result)
        # a result that fills a gap is a delivered argument
        board = [dict(BOARD_1494[1], result="the repair fills the gap in step 2 (attempt-2)")]
        self.assertEqual("T-1664", routes.delivered_argument(
            T1494, routes.TicketLookup(lambda: board)))

    def test_a_question_parent_lands_its_child_too(self):
        board = [{"id": "T-0090", "kind": "research", "status": "delivered",
                  "final_to": "researcher", "parent": "T-0086"}]
        r = self.route(T0086, board)
        self.assertEqual(("agent", "math-writer"), (r["how"], r["target"]))
        self.assertIn("T-0090", r["why"])

    def test_the_lookup_reads_one_listing_and_a_plain_callable_has_no_children(self):
        calls = []

        def metas():
            calls.append(1)
            return BOARD_1494
        look = routes.TicketLookup(metas)
        self.assertEqual(["T-1664"], [m["id"] for m in look.children("T-1494")])
        self.assertEqual([], look.children("T-01368"))
        self.assertEqual("verify", look("T-1368")["kind"])
        self.assertEqual(1, len(calls))
        # a plain id -> meta callable (the older ticket_of) still works, without children
        self.assertEqual("", routes.delivered_argument(T1494, {}.get))


class DecisionTicketTests(unittest.TestCase):
    """A choice only the human can make is filed as a `decision` ticket to the human whose
    ask carries the options (review of badbc50: decisions.py builds a ticket's item from
    its ask, with fixed Proceed/Decline options, so options left in a block reason are
    lost)."""

    def test_the_decision_ask_carries_the_options(self):
        meta = routes.decision_ticket(
            dict(T0351, id="T-0364", to="author@t", agenda="paper:conj:x",
                 refs=["paper:conj:x"]),
            "Which repair of conj:x", ["restrict the hypothesis to primitive origamis",
                                       "change the conclusion", "recolour it conjectural"])
        self.assertEqual(("decision", "human", "author@t"),
                         (meta["kind"], meta["to"], meta["from"]))
        self.assertEqual("T-0364", meta["parent"])
        self.assertEqual(["paper:conj:x", "T-0364"], meta["refs"])
        self.assertEqual("Which repair of conj:x? (a) restrict the hypothesis to primitive "
                         "origamis; (b) change the conclusion; (c) recolour it conjectural",
                         meta["ask"])
        self.assertNotIn("\n", meta["ask"])
        with self.assertRaises(ValueError):
            routes.decision_ticket(T0351, "Which?", ["only one"])

    def test_decisions_list_shows_the_options(self):
        sb = Sandbox()
        try:
            meta = routes.decision_ticket(dict(T0351, id="T-0002", to="author@t"),
                                          "Which reading", ["H^{*0}=H", "H^{*0} empty"])
            write_ticket(sb.board, "T-0001", "human", "open", "decision", ask=meta["ask"])
            res = subprocess.run(
                [sys.executable, os.path.join(SCRIPTS, "..", "..", "academy", "scripts",
                                              "decisions.py"),
                 "--board", sb.board, "list", "--json"],
                capture_output=True, env=dict(sb.env))
            self.assertEqual(0, res.returncode, res.stderr)
            items = json.loads(res.stdout.decode("utf-8"))
            q = [i for i in items if i["id"] == "T-0001"][0]["question"]
            self.assertIn("(a) H^{*0}=H", q)
            self.assertIn("(b) H^{*0} empty", q)
        finally:
            sb.cleanup()


def write_ticket(board, tid, to, status, kind, frm="author@t", refs=(), ask="x",
                 final_to=None, parent=None):
    text = ("---\nid: %s\ntitle: %s ticket\nkind: %s\nfrom: %s\nto: %s\nstatus: %s\n"
            "priority: normal\nask: %s\ndeliverable: y\nrefs: [%s]\n%s---\n\n"
            "## Ask\n\n## Result\n\n## Thread\n"
            % (tid, kind, kind, frm, to, status, ask, ", ".join(refs),
               (("final_to: %s\n" % final_to) if final_to else "")
               + (("parent: %s\n" % parent) if parent else "")))
    Sandbox.write(os.path.join(board, to, "%s-%s-ticket.md" % (tid, kind)), text)


class BoardLookupTests(unittest.TestCase):
    """The inbox reads the refs' tickets on its own board (one listing), not another."""

    def setUp(self):
        self.sb = Sandbox()
        b = self.sb.board
        write_ticket(b, "T-0001", "expert@t", "closed", "research", final_to="researcher")
        write_ticket(b, "T-0002", "author@t", "accepted", "write",
                     refs=["paper:lem:x", "T-0001"],
                     ask="Repair the proof of lem:x: a missing step")
        write_ticket(b, "T-0003", "author@t", "accepted", "apply",
                     ask="add the hypothesis that Q is compact, per the human's word")
        write_ticket(b, "T-0004", "author@t", "accepted", "write", refs=["paper:lem:y"],
                     ask="Repair the proof of lem:y: a missing step")
        write_ticket(b, "T-0005", "expert@t", "delivered", "research",
                     final_to="researcher", parent="T-0004")
        write_ticket(b, "T-0006", "author@t", "accepted", "question",
                     ask="where does the paper state the convention for E empty")

    def tearDown(self):
        self.sb.cleanup()

    def test_ticket_lookup_reads_one_listing_by_number(self):
        store = ac.FileBoardStore(self.sb.board)
        with unittest.mock.patch.object(store, "iter_meta", wraps=store.iter_meta) as it:
            look = routes.ticket_lookup(store)
            self.assertEqual("closed", look("T-0001")["status"])
            self.assertEqual("closed", look("T-00001")["status"])
            self.assertIsNone(look("T-0099"))
        self.assertEqual(1, it.call_count)

    def test_the_inbox_routes_on_the_board_it_reads(self):
        other = os.path.join(self.sb.root, "elsewhere")       # the workspace's board: empty
        os.makedirs(other)
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        ws["board"] = other
        Sandbox.write(self.sb.workspace, json.dumps(ws))
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "inbox.py"), "--json",
                              "--all", "--home", self.sb.home, "--board", self.sb.board],
                             capture_output=True, env=dict(self.sb.env))
        rows = {r["id"]: r["route"] for r in json.loads(res.stdout.decode("utf-8"))["take"]}
        self.assertEqual("math-writer", rows["T-0002"]["target"], rows["T-0002"])
        self.assertIn("T-0001", rows["T-0002"]["why"])
        self.assertEqual("math-editor", rows["T-0003"]["target"])
        self.assertEqual("math-writer", rows["T-0004"]["target"], rows["T-0004"])
        self.assertIn("T-0005", rows["T-0004"]["why"])
        self.assertEqual("math-writer", rows["T-0006"]["target"], rows["T-0006"])


if __name__ == "__main__":
    unittest.main()
