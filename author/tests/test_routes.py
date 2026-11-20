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
    "id": "T-1441", "kind": "apply", "from": "author@bi", "to": "author@bi",
    "status": "accepted",
    "title": "thm:arithmetic-billiard-goal: add the hypothesis that Q has no marked "
             "regular points and no semi-corners (Roey 2026-11-15)",
    "ask": "Add to paper:thm:arithmetic-billiard-goal (sections/introduction.tex, "
           "conjectural) the hypothesis that Q carries no marked regular points and no "
           "semi-corners (Sigma_Q = V(Q)), per Roey's word of 2026-11-15.",
    "refs": ["paper:thm:arithmetic-billiard-goal"],
}
T1385 = {
    "id": "T-1385", "kind": "write", "from": "author@bi", "to": "author@bi",
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


def write_ticket(board, tid, to, status, kind, frm="author@t", refs=(), ask="x",
                 final_to=None):
    text = ("---\nid: %s\ntitle: %s ticket\nkind: %s\nfrom: %s\nto: %s\nstatus: %s\n"
            "priority: normal\nask: %s\ndeliverable: y\nrefs: [%s]\n%s---\n\n"
            "## Ask\n\n## Result\n\n## Thread\n"
            % (tid, kind, kind, frm, to, status, ask, ", ".join(refs),
               ("final_to: %s\n" % final_to) if final_to else ""))
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
                              "--home", self.sb.home, "--board", self.sb.board],
                             capture_output=True, env=dict(self.sb.env))
        rows = {r["id"]: r["route"] for r in json.loads(res.stdout.decode("utf-8"))["take"]}
        self.assertEqual("math-writer", rows["T-0002"]["target"], rows["T-0002"])
        self.assertIn("T-0001", rows["T-0002"]["why"])
        self.assertEqual("math-editor", rows["T-0003"]["target"])


if __name__ == "__main__":
    unittest.main()
