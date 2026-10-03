"""BoardStore parity: the same tickets on a file board and on a GitHub board (in-memory
transport, encoded by the codec) behave identically under inbox_core.select, the dead-route
and --campaign filters, the transition rules, board.py and the MCP tickets_* tools.

Run from the repo root:  py -m unittest discover academy/tests
"""

import io
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PLUGIN, "mcp"))

from test_board import BoardCase  # noqa: E402

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402
import board_store as bs  # noqa: E402
from tools import Context, ToolError, tickets as mcp_tickets  # noqa: E402

core = ac.inbox_core
INST = "researcher@r1"
DATE = "2026-09-30"


def route(meta):
    if meta.get("kind") == "verify":
        return {"how": "reject", "target": None, "why": "not ours"}
    return {"how": "skill", "target": "do:" + str(meta.get("kind")), "why": "by kind"}


def make_transport(cfg=None):               # for board.transport = "test_board_store:make_transport"
    return bs.MemoryTransport()


class StoreCase(BoardCase):
    """A file board with a spread of tickets, and a GitHub board built from it."""

    def put(self, n, status="open", kind="prove", priority="normal", to=INST,
            frm="author@main", thread=(), **extra):
        tid = "T-%04d" % n
        meta = {"id": tid, "title": "t " + tid, "kind": kind, "from": frm, "to": to,
                "status": status, "priority": priority, "ask": "a", "deliverable": "d",
                "refs": [], "blocks": [], "waiting_on": [],
                "budget": {"runs": 1, "max_model": "sonnet"}, "packets": [],
                "created": "2026-09-29", "updated": "2026-09-29"}
        meta.update(extra)
        if status in ("delivered", "closed"):
            meta["result"] = "done"
        fm, body = ac.read_frontmatter(ac.new_ticket(meta, "Ask %s" % tid))
        for who, text in thread:
            body = ac.append_thread(body, who, text, "2026-09-29")
        if not thread:
            body = ac.append_thread(body, frm, "opened", "2026-09-29")
        bd.write_ticket(os.path.join(self.board, to, ac.ticket_filename(tid, meta["title"])),
                        fm, body)

    def fill(self):
        self.put(1)
        self.put(2, status="accepted", priority="high", agenda="paper:thm:a")
        self.put(3, status="in-progress", priority="low")
        self.put(4, status="blocked", waiting_on=["T-0001"])
        self.put(5, status="blocked", campaign="c", blocked_by="paper:lem:y",
                 reopen_if="a new invariant",
                 thread=[("author@main", "opened"), (INST, "tried: the induction")])
        self.put(6, campaign="c")
        self.put(7, campaign="c", priority="high", kind="write")
        self.put(8, status="delivered")
        self.put(9, status="closed")
        self.put(10, status="blocked", final_to="expert", waiting_on=["T-0011"])
        self.put(11, status="delivered", to="expert@main", frm=INST)
        self.put(12, to="expert@main", kind="verify")
        self.put(13, to="human", kind="decision")
        self.put(14, campaign="other")
        self.put(16, kind="sweep", campaign="c", to="author@main", frm="author@main")
        # T-0015 is a gap: a closed placeholder on GitHub

    def setUp(self):
        super().setUp()
        self.fill()
        self.files = ac.FileBoardStore(self.board)
        self.transport = bs.from_file_board(self.board)
        self.gh = bs.GithubBoardStore(self.transport, "o/r")

    def snapshot(self, store):
        """Every ticket as (id, rendered file text), refs dropped."""
        return sorted((m["id"], bc.render(m, b)) for _r, m, b in store.iter_tickets()
                      if m is not None)

    def rows(self, store, **kw):
        kw.setdefault("route", route)
        rows, total = core.select(store, kw.pop("instance", INST), kw.pop("limit", 3), **kw)
        return [{k: v for k, v in r.items() if k != "path"} for r in rows], total


class TestSeed(StoreCase):
    def test_every_issue_is_consistent_and_the_gap_is_a_placeholder(self):
        for n, i in self.transport.issues.items():
            if n == 15:
                self.assertEqual(["placeholder"], i["labels"])
                continue
            self.assertEqual([], bc.validate_issue(i, self.transport.comments[n]), n)
        self.assertIn("route:dead", self.transport.issues[5]["labels"])
        self.assertNotIn("route:dead", self.transport.issues[4]["labels"])

    def test_both_stores_hold_the_same_tickets(self):
        self.assertEqual(self.snapshot(self.files), self.snapshot(self.gh))
        self.assertEqual(15, len(self.snapshot(self.gh)))

    def test_find_get_status_of_and_missing(self):
        self.assertEqual("github#3", self.gh.find("T-0003"))
        self.assertIsNone(self.gh.find("T-0015"))                # placeholder
        self.assertIsNone(self.gh.find("T-0099"))
        self.assertEqual("blocked", self.gh.status_of("T-0005"))
        self.assertIsNone(self.gh.status_of("T-0099"))
        with self.assertRaises(ac.AcademyError):
            self.gh.get("T-0099")
        with self.assertRaises(ac.AcademyError):
            self.files.get("T-0099")


class TestSelectParity(StoreCase):
    def same(self, **kw):
        a, b = self.rows(self.files, **kw), self.rows(self.gh, **kw)
        self.assertEqual(a, b, kw)
        return a[0]

    def test_default_selection(self):
        rows = self.same()
        self.assertEqual(["T-0003", "T-0010", "T-0002"], [r["id"] for r in rows])   # cap 3
        self.assertTrue(rows[1]["return"])

    def test_all(self):
        rows = self.same(all=True)
        blocked = {r["id"]: r["blocked"] for r in rows if r["blocked"]}
        self.assertEqual({"T-0004": "pending", "T-0005": "dead-route",
                          "T-0010": "pending"}, blocked)

    def test_dead_route_is_never_taken_and_pending_is_not_either(self):
        for store in (self.files, self.gh):
            ids = [r["id"] for r in self.rows(store, limit=9)[0]]
            self.assertNotIn("T-0005", ids)
            self.assertNotIn("T-0004", ids)

    def test_campaign_filter_lifts_the_cap_and_skips_dead_routes(self):
        rows = self.same(campaign="c", limit=9)
        self.assertEqual(["T-0007", "T-0006"], [r["id"] for r in rows])
        self.same(campaign="c", all=True)
        self.same(campaign="other")
        self.same(campaign="c", instance="author@main")

    def test_return_leg_and_position_options(self):
        rows = self.same(limit=9)                  # the cap of three holds outside a campaign
        self.assertEqual(3, len(rows))
        self.assertTrue(rows[1]["return"])
        no_ret = self.same(limit=9, return_legs=False)
        self.assertNotIn("T-0010", [r["id"] for r in no_ret])
        self.same(all=True)
        self.same(limit=9, position_first=True)
        self.same(limit=9, position=lambda m: 0 if m.get("agenda") else 5)

    def test_other_instances_and_human(self):
        self.same(instance="expert@main")
        self.same(instance="human")
        self.same(instance="scientist@nowhere")

    def test_serial_checkpoint_parity(self):
        for tid in ("T-0001", "T-0003", "T-0005", "T-0008", "T-0004"):
            self.assertEqual(core.check(self.files, tid), core.check(self.gh, tid))
        with self.assertRaises(ac.AcademyError):
            core.check(self.gh, "T-0099")

    def run_cli(self, store, *argv):
        args = core.parser("t").parse_args(list(argv))
        out = io.StringIO()
        rc = core.run(args, INST, store, 3, route, out=out)
        return rc, out.getvalue()

    def test_run_output_is_identical_in_text_json_and_check(self):
        for argv in ([], ["--all"], ["--campaign", "c"], ["--check", "T-0003"],
                     ["--check", "T-0001"], ["--n", "9", "--campaign", "c"]):
            a, b = self.run_cli(self.files, *argv), self.run_cli(self.gh, *argv)
            self.assertEqual(a, b, argv)
        for argv in (["--json"], ["--json", "--campaign", "c"], ["--json", "--all"]):
            docs = []
            for store in (self.files, self.gh):
                rc, text = self.run_cli(store, *argv)
                doc = json.loads(text)
                for r in doc["take"]:
                    r.pop("path")
                docs.append((rc, doc))
            self.assertEqual(docs[0], docs[1], argv)

    def test_select_reads_no_comments_from_github(self):
        self.transport.calls.clear()
        self.rows(self.gh, limit=9)
        kinds = {c[0] for c in self.transport.calls}
        self.assertNotIn("list_comments", kinds)
        self.assertIn(("list_issues", ("to:" + INST,), "all", 1), self.transport.calls)

    def test_a_path_still_means_the_file_board(self):
        a, _ = core.select(self.board, INST, 3, route=route)
        b, _ = core.select(self.files, INST, 3, route=route)
        self.assertEqual(a, b)
        self.assertTrue(a[0]["path"].endswith(".md"))
        self.assertTrue(core.select(self.gh, INST, 3, route=route)[0][0]["path"]
                        .startswith("github#"))


class TestTransitionParity(StoreCase):
    def attempt(self, board, fn, *a, **kw):
        try:
            fn(board, *a, **kw)
            return "ok"
        except ac.AcademyError as e:
            return "error: %s" % e

    OPS = [
        ("T-0001", "accepted", dict(as_instance=INST)),
        ("T-0001", "delivered", dict(as_instance=INST, result="r")),         # not legal yet
        ("T-0001", "in-progress", dict(as_instance=INST)),
        ("T-0001", "blocked", dict(as_instance=INST, waiting_on=["T-0006"])),  # mirrors blocks
        ("T-0005", "accepted", dict(as_instance=INST)),                        # no reopen
        ("T-0005", "in-progress", dict(as_instance=INST, reopen="x")),         # wrong target
        ("T-0005", "accepted", dict(as_instance=INST, reopen="a new lemma")),
        ("T-0006", "rejected", dict(as_instance=INST)),                        # needs a reason
        ("T-0006", "rejected", dict(as_instance=INST, reason="out of scope")),
        ("T-0002", "delivered", dict(as_instance="author@main", result="r")),  # wrong party
        ("T-0008", "in-progress", dict(as_instance="author@main")),           # needs a reason
        ("T-0008", "in-progress", dict(as_instance="author@main", reason="redo")),
        ("T-0003", "blocked", dict(as_instance=INST, blocked_by="paper:lem:z",
                                   reopen_if="new idea", reason="tried A and B")),
        ("T-0003", "in-progress", dict(as_instance=INST)),                     # dead: no reopen
        ("T-0003", "cancelled", dict(as_instance="author@main", reason="moot")),
        ("T-0009", "open", dict()),                                            # human reopens
        ("T-0014", "blocked", dict(as_instance=INST)),                         # nothing to wait on
        ("T-0007", "closed", dict(as_instance="author@main")),                 # not delivered
    ]

    #: which OPS must fail (True) -- parity of two silent successes would prove nothing
    ERRORS = [False, True, False, False, True, True, False, True, False, True, True, False,
              False, True, False, False, True, True]

    def test_same_outcome_for_every_move_and_same_tickets_after(self):
        self.assertEqual(len(self.OPS), len(self.ERRORS))
        for (tid, new, kw), must_fail in zip(self.OPS, self.ERRORS):
            kw = dict(kw, date=DATE)
            a = self.attempt(self.files, bd.transition_ticket, tid, new, **kw)
            b = self.attempt(self.gh, bd.transition_ticket, tid, new, **kw)
            self.assertEqual(a, b, (tid, new))
            self.assertEqual(must_fail, a.startswith("error"), (tid, new, a))
            self.assertEqual(self.snapshot(self.files), self.snapshot(self.gh), (tid, new))
        # the legal moves did happen, the illegal ones did not
        self.assertEqual("accepted", self.gh.status_of("T-0005"))
        self.assertEqual("cancelled", self.gh.status_of("T-0003"))
        self.assertEqual("open", self.gh.status_of("T-0009"))
        self.assertEqual("blocked", self.gh.status_of("T-0001"))
        self.assertIn("T-0001", self.gh.get("T-0006")[1]["blocks"])

    def test_the_github_board_stays_consistent_and_labels_follow(self):
        for tid, new, kw in self.OPS:
            self.attempt(self.gh, bd.transition_ticket, tid, new, date=DATE, **kw)
        for n, i in self.transport.issues.items():
            if n != 15:
                self.assertEqual([], bc.validate_issue(i, self.transport.comments[n]), n)
        self.assertEqual("closed", self.transport.issues[6]["state"])           # rejected
        self.assertEqual("not_planned", self.transport.issues[6]["state_reason"])
        self.assertNotIn("route:dead", self.transport.issues[5]["labels"])      # reopened
        self.assertIn("status:accepted", self.transport.issues[5]["labels"])
        self.assertTrue(any(c.split("\n\n", 1)[1].startswith("reopened: a new lemma")
                            for c in self.transport.comments[5]))

    def test_a_dead_route_move_to_github_carries_the_label(self):
        bd.transition_ticket(self.gh, "T-0003", "blocked", blocked_by="paper:lem:z",
                             reopen_if="new idea", reason="tried A", as_instance=INST,
                             date=DATE)
        self.assertIn("route:dead", self.transport.issues[3]["labels"])
        self.assertIn("status:blocked", self.transport.issues[3]["labels"])
        rows, _ = core.select(self.gh, INST, 3, all=True, route=route)
        self.assertEqual("dead-route", [r for r in rows if r["id"] == "T-0003"][0]["blocked"])

    def test_append_and_the_thread_is_append_only_on_github(self):
        for store in (self.files, self.gh):
            bd.append_to_ticket(store, "T-0001", "a note\nsecond line", as_instance=INST,
                                date=DATE)
        self.assertEqual(self.snapshot(self.files), self.snapshot(self.gh))
        ref, meta, body = self.gh.get("T-0001")
        body = body.replace("a note", "edited note")
        with self.assertRaises(ac.AcademyError) as cm:
            self.gh.save(meta, body, ref)
        self.assertIn("append-only", str(cm.exception))

    def test_saving_an_unchanged_ticket_writes_nothing(self):
        ref, meta, body = self.gh.get("T-0001")
        self.transport.calls.clear()
        self.gh.save(meta, body, ref)
        self.assertFalse([c for c in self.transport.calls
                          if c[0] in ("update_issue", "add_comment", "create_issue")])


class FootedTransport(bs.MemoryTransport):
    """GitHub as a session's posts reach it: every body and comment gets the footer."""
    FOOT = bc.ATTRIBUTION_FOOTERS[0]

    def _add_comment(self, number, body):
        return bs.MemoryTransport._add_comment(self, number, body + self.FOOT)

    def add_encoded(self, e):
        return bs.MemoryTransport.add_encoded(self, dict(e, body=e["body"] + self.FOOT))

    def create_issue(self, title, body, labels, assignees=None):
        return bs.MemoryTransport.create_issue(self, title, body + self.FOOT, labels, assignees)

    def update_issue(self, number, title=None, body=None, **kw):
        return bs.MemoryTransport.update_issue(
            self, number, title=title, body=None if body is None else body + self.FOOT, **kw)


class TestTransitionParityFooted(TestTransitionParity):
    """The same moves on a board whose posts all carry the footer (the live cutover
    rehearsal: the second write to a ticket was refused as a Thread edit)."""

    def setUp(self):
        super().setUp()
        self.transport = bs.from_file_board(self.board, FootedTransport())
        self.gh = bs.GithubBoardStore(self.transport, "o/r")


class TestStoreAssignment(StoreCase):
    def test_saves_assign_the_human_while_the_ticket_needs_them(self):
        st = bs.GithubBoardStore(self.transport, "o/r", assignee="roey")
        bd.transition_ticket(st, "T-0001", "accepted", as_instance=INST, date=DATE)
        self.assertEqual([], self.transport.issues[1].get("assignees", []))
        bd.transition_ticket(st, "T-0001", "blocked", waiting_on=["human"],
                             reason="needs Roey's reading", as_instance=INST, date=DATE)
        self.assertEqual(["roey"], self.transport.issues[1]["assignees"])
        bd.transition_ticket(st, "T-0001", "accepted", reason="Roey answered",
                             as_instance=INST, date=DATE)
        self.assertEqual([], self.transport.issues[1]["assignees"])

    def test_without_a_login_assignees_are_left_alone(self):
        self.transport.issues[1]["assignees"] = ["carlos"]
        bd.transition_ticket(self.gh, "T-0001", "accepted", as_instance=INST, date=DATE)
        self.assertEqual(["carlos"], self.transport.issues[1]["assignees"])


class TestStoreRelationsFollowTheTicket(StoreCase):
    """Native links follow the ticket both ways: a moved parent is replaced, a cleared one
    removed, and an unblocked ticket loses its dependency (not only gains them)."""

    def test_parent_is_replaced_and_removed(self):
        ref, meta, body = self.gh.get("T-0002")
        self.gh.save(dict(meta, parent="T-0001"), body, ref)
        self.assertEqual(1, self.transport.parents[2])
        ref, meta, body = self.gh.get("T-0002")
        self.gh.save(dict(meta, parent="T-0004"), body, ref)
        self.assertEqual(4, self.transport.parents[2])
        ref, meta, body = self.gh.get("T-0002")
        self.gh.save(dict(meta, parent=None), body, ref)
        self.assertNotIn(2, self.transport.parents)

    def test_unblocking_removes_the_dependency(self):
        bd.transition_ticket(self.gh, "T-0001", "accepted", as_instance=INST, date=DATE)
        bd.transition_ticket(self.gh, "T-0001", "blocked", waiting_on=["T-0006"],
                             reason="needs T-0006", as_instance=INST, date=DATE)
        self.assertEqual([(1, 6)], self.transport.dependencies)
        bd.transition_ticket(self.gh, "T-0001", "accepted", reason="T-0006 is in",
                             as_instance=INST, date=DATE)
        self.assertEqual([], self.transport.dependencies)


class TestCreateParity(StoreCase):
    def test_new_ticket_is_identical_with_campaign_and_the_next_id(self):
        kw = dict(to="expert@main", title="Check lemma", ask="Verify it", deliverable="A packet",
                  kind="verify", as_instance="author@main", agent="math-writer",
                  workspace=self.ws, date=DATE, campaign="paper:thm:x",
                  budget={"runs": 2, "max_model": "opus"}, detail="More.\n\n## x\n")
        pa = bd.create_ticket(self.files, **kw)
        pb = bd.create_ticket(self.gh, **kw)
        self.assertTrue(pa.endswith("T-0017-check-lemma.md"))    # max id 16 -> 17
        self.assertEqual("github#17", pb)
        self.assertEqual(self.snapshot(self.files), self.snapshot(self.gh))
        meta = self.gh.get("T-0017")[1]
        self.assertEqual("paper:thm:x", meta["campaign"])
        self.assertEqual("open", meta["status"])
        i = self.transport.issues[17]
        self.assertEqual([], bc.validate_issue(i, self.transport.comments[17]))
        self.assertEqual(("closed", "not_planned"), (self.transport.issues[15]["state"],
                                                     self.transport.issues[15]["state_reason"]))

    def test_the_chain_gate_and_validation_apply_on_github_too(self):
        for store in (self.files, self.gh):
            with self.assertRaises(ac.AcademyError) as cm:
                bd.create_ticket(store, "researcher@r1", "T", "a", "d",
                                 as_instance="author@main", workspace=self.ws)
            self.assertIn("final_to researcher", str(cm.exception))
        self.assertEqual(self.snapshot(self.files), self.snapshot(self.gh))

    def test_relay_depth_reads_through_the_store(self):
        self.assertEqual(ac.relay_depth(self.files, "T-0010"), ac.relay_depth(self.gh, "T-0010"))
        self.assertEqual(1, ac.relay_depth(self.gh, "T-0010"))
        self.assertEqual(0, ac.relay_depth(self.gh, "T-0001"))


class TestCliOnStore(StoreCase):
    def test_show_and_list_read_a_github_ticket(self):
        rows_f = bd.list_tickets(self.files, to=INST)
        rows_g = bd.list_tickets(self.gh, to=INST)
        strip = lambda rs: [{k: v for k, v in r.items() if k != "_path"} for r in rs]  # noqa
        self.assertEqual(strip(rows_f), strip(rows_g))
        _r, meta, body = bd.get_ticket(self.gh, "T-0003")
        self.assertEqual("in-progress", meta["status"])


class TestMcpParity(StoreCase):
    def ctx(self, store):
        return Context(cwd=self.tmp, workspace=self.ws, store=store)

    def norm(self, d):
        d = json.loads(json.dumps(d))
        for k in ("path", "board"):
            d.pop(k, None)
        for t in d.get("tickets", []):
            t.pop("path", None)
        return d

    def test_list_and_get(self):
        for a in ({}, {"to": INST}, {"status": ["blocked"]}, {"instance": "expert@main"},
                  {"include_terminal": False}):
            r = [self.norm(mcp_tickets._list(self.ctx(s), a)) for s in (self.files, self.gh)]
            self.assertEqual(r[0], r[1], a)
        g = [self.norm(mcp_tickets._get(self.ctx(s), {"id": "T-0005"})) for s in
             (self.files, self.gh)]
        self.assertEqual(g[0], g[1])
        with self.assertRaises(ToolError):
            mcp_tickets._get(self.ctx(self.gh), {"id": "T-0099"})

    def test_create_and_update_including_the_dead_route_reopen(self):
        args = dict(title="Chk", kind="verify", to="expert@main", ask="a", deliverable="d",
                    campaign="c", as_human=True)
        made = [mcp_tickets.create_ticket(self.ctx(s), dict(args)) for s in (self.files, self.gh)]
        self.assertEqual("T-0017", made[0]["id"])
        self.assertEqual(made[0]["id"], made[1]["id"])
        steps = [
            {"id": "T-0005", "status": "accepted"},                        # no reopen
            {"id": "T-0005", "status": "accepted", "reopen": "a new lemma"},
            {"id": "T-0001", "status": "accepted", "note": "starting"},
            {"id": "T-0001", "fields": {"waiting_on": ["T-0006"]}},          # not blocked
            {"id": "T-0006", "status": "rejected"},                          # needs a reason
            {"id": "T-0006", "status": "rejected", "reason": "no"},
        ]
        results = []
        for a in steps:
            out = []
            for s in (self.files, self.gh):
                try:
                    r = mcp_tickets.update_ticket(self.ctx(s), dict(a))
                    out.append(self.norm(r))
                except ToolError as e:
                    out.append(str(e))
            self.assertEqual(out[0], out[1], a)
            results.append(out[0])
        self.assertEqual([True, False, False, True, True, False],
                         [isinstance(r, str) for r in results])      # the errors did occur
        self.assertEqual(self.snapshot(self.files), self.snapshot(self.gh))
        self.assertEqual("accepted", self.gh.status_of("T-0005"))

    def test_a_reroute_moves_the_ticket_and_the_label(self):
        a = {"id": "T-0006", "fields": {"to": "expert@main"}}
        for s in (self.files, self.gh):
            mcp_tickets.update_ticket(self.ctx(s), dict(a))
        self.assertTrue(self.files.find("T-0006").split(os.sep)[-2] == "expert@main")
        self.assertIn("to:expert@main", self.transport.issues[6]["labels"])
        self.assertIn("role:expert", self.transport.issues[6]["labels"])
        self.assertEqual(self.snapshot(self.files), self.snapshot(self.gh))


class NoLinks(object):
    """A transport without the optional native-link methods."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        if name in ("set_parent", "add_dependency"):
            raise AttributeError(name)
        return getattr(self._inner, name)


class TestSkippedRelations(StoreCase):
    def test_a_transport_without_links_reports_what_it_could_not_write(self):
        import io
        from contextlib import redirect_stderr
        st = bs.GithubBoardStore(NoLinks(self.transport), "o/r")
        _r, m4, b4 = st.get("T-0004")
        m4 = dict(m4, waiting_on=["T-0001", "T-0002"])
        _r, m6, b6 = st.get("T-0006")
        m6 = dict(m6, parent="T-0001")
        err = io.StringIO()
        with redirect_stderr(err):
            st.save(m4, b4)
            st.save(m6, b6)
        self.assertEqual([{"type": "dependency", "issue": 4, "blocker": 2},
                          {"type": "sub_issue", "parent": 1, "child": 6}],
                         st.skipped_relations)
        self.assertIn("not written", err.getvalue())

    def test_a_transport_with_links_skips_nothing(self):
        _r, m4, b4 = self.gh.get("T-0004")
        self.gh.save(dict(m4, waiting_on=["T-0001", "T-0002"]), b4)
        self.assertEqual([], self.gh.skipped_relations)


class TestOpenStore(BoardCase):
    def write_ws(self, board):
        with open(self.ws_path, encoding="utf-8") as fh:
            ws = json.load(fh)
        ws["board"] = board
        with open(self.ws_path, "w", encoding="utf-8") as fh:
            json.dump(ws, fh)
        return ac.load_workspace(self.ws_path)

    def test_default_is_the_file_board(self):
        st = ac.open_store(self.ws)
        self.assertIsInstance(st, ac.FileBoardStore)
        self.assertEqual(self.board, st.board)
        self.assertEqual({}, self.ws["board_config"])

    def test_board_object_with_backend_files_keeps_the_path(self):
        ws = self.write_ws({"path": self.board, "backend": "files"})
        self.assertEqual(self.board, ws["board"])
        self.assertIsInstance(ac.open_store(ws), ac.FileBoardStore)

    def test_unknown_backend_is_a_config_error(self):
        with self.assertRaises(ac.ConfigError):
            self.write_ws({"path": self.board, "backend": "svn"})

    def test_github_needs_a_transport(self):
        ws = self.write_ws({"path": self.board, "backend": "github", "repo": "o/r"})
        with self.assertRaises(ac.ConfigError) as cm:
            ac.open_store(ws)
        self.assertIn("transport", str(cm.exception))
        st = ac.open_store(ws, transport=bs.MemoryTransport())
        self.assertIsInstance(st, bs.GithubBoardStore)
        self.assertEqual("o/r", st.repo)

    def test_github_transport_by_name(self):
        ws = self.write_ws({"path": self.board, "backend": "github",
                            "transport": "test_board_store:make_transport"})
        self.assertIsInstance(ac.open_store(ws).t, bs.MemoryTransport)

    def test_the_rest_transport_by_name(self):
        # the cutover switch: workspace.json names board_gh's factory
        import board_gh
        ws = self.write_ws({"path": self.board, "backend": "github", "repo": "o/r",
                            "transport": "board_gh:transport"})
        st = ac.open_store(ws)
        self.assertIsInstance(st.t, board_gh.GhTransport)
        self.assertEqual("o/r", st.t.repo)
        ws = self.write_ws({"path": self.board, "backend": "github",
                            "transport": "board_gh:transport"})
        with self.assertRaises(ac.ConfigError):
            ac.open_store(ws)                      # no repo: refused, never a guess

    def test_an_explicit_board_path_always_means_files(self):
        ws = self.write_ws({"path": self.board, "backend": "github"})
        self.assertIsInstance(ac.open_store(ws, board=self.board), ac.FileBoardStore)
        self.assertIsInstance(bd.resolve_store(self.board), ac.FileBoardStore)

    def test_resolve_store_uses_the_workspace_backend(self):
        self.write_ws({"path": self.board, "backend": "files"})
        st = bd.resolve_store(None, self.ws_path)
        self.assertIsInstance(st, ac.FileBoardStore)
        self.write_ws({"path": self.board, "backend": "github"})
        with self.assertRaises(ac.ConfigError):
            bd.resolve_store(None, self.ws_path)


if __name__ == "__main__":
    unittest.main()

