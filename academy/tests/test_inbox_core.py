"""The shared inbox core (academy_common.inbox_core), against fixture boards.

Ordering, resume-first, return legs, the blocked filter (pending and dead route), the
limit, the serial checkpoint and the campaign filter. The per-role wrappers are tested
in their own plugins.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))

import academy_common as ac  # noqa: E402

core = ac.inbox_core
INST = "researcher@t"


def route(meta):
    kind = meta.get("kind")
    if kind == "code":
        return {"how": "agent", "target": "developer", "why": "code", "over_budget": "opus"}
    if kind == "verify":
        return {"how": "reject", "target": None, "why": "not ours"}
    return {"how": "skill", "target": "do:" + str(kind), "why": "by kind"}


class Board(unittest.TestCase):
    def setUp(self):
        self.board = tempfile.mkdtemp(prefix="inbox-core-")

    def tearDown(self):
        shutil.rmtree(self.board, ignore_errors=True)

    def put(self, tid, status="open", kind="prove", priority="normal", to=INST,
            frm="author@t", **extra):
        meta = {"id": tid, "title": "t " + tid, "kind": kind, "from": frm, "to": to,
                "status": status, "priority": priority, "ask": "a", "deliverable": "d",
                "refs": [], "blocks": [], "waiting_on": [],
                "budget": {"runs": 1, "max_model": "sonnet"}, "packets": [],
                "created": "2026-09-29", "updated": "2026-09-29"}
        meta.update(extra)
        if status in ("delivered", "closed"):
            meta["result"] = "done"
        folder = os.path.join(self.board, to)
        os.makedirs(folder, exist_ok=True)
        ac.atomic_write(os.path.join(folder, ac.ticket_filename(tid, meta["title"])),
                        ac.new_ticket(meta))

    def ids(self, **kw):
        kw.setdefault("route", route)
        rows, total = core.select(self.board, INST, kw.pop("limit", 3), **kw)
        return [r["id"] for r in rows]


class OrderingTests(Board):
    def test_priority_then_agenda_then_id(self):
        self.put("T-0001", kind="other")
        self.put("T-0002", priority="high")
        self.put("T-0003", agenda="paper:thm:main")
        self.put("T-0004", priority="low", agenda="paper:thm:main")
        self.put("T-0005", status="accepted", priority="low")
        self.assertEqual(self.ids(all=True), ["T-0002", "T-0003", "T-0001", "T-0004", "T-0005"])

    def test_terminal_delivered_and_foreign_tickets_are_not_taken(self):
        self.put("T-0001", status="closed")
        self.put("T-0002", status="delivered")
        self.put("T-0003", status="cancelled")
        self.put("T-0004", to="expert@t")
        self.put("T-0005")
        self.assertEqual(self.ids(), ["T-0005"])

    def test_agenda_position_function_overrides_presence(self):
        self.put("T-0001", agenda="a")
        self.put("T-0002", agenda="b")
        rows, _ = core.select(self.board, INST, 3, route=route,
                              position=lambda m: {"a": 9, "b": 1}[m["agenda"]])
        self.assertEqual([r["id"] for r in rows], ["T-0002", "T-0001"])

    def test_empty_board_and_missing_folder(self):
        self.assertEqual(core.select(self.board, INST, 3, route=route), ([], 0))
        self.assertEqual(core.select(os.path.join(self.board, "nope"), INST, 3), ([], 0))

    def test_unreadable_files_are_skipped(self):
        self.put("T-0001")
        with open(os.path.join(self.board, INST, "T-0002-bad.md"), "w") as fh:
            fh.write("no frontmatter at all")
        self.assertEqual(self.ids(), ["T-0001"])


class PositionFirstAndExtraTests(Board):
    def test_position_first_orders_by_agenda_before_priority(self):
        self.put("T-0001", priority="high", agenda="late")
        self.put("T-0002", priority="low", agenda="early")
        pos = lambda m: {"early": 1, "late": 9}[m["agenda"]]  # noqa: E731
        rows, _ = core.select(self.board, INST, 3, route=route, position=pos)
        self.assertEqual([r["id"] for r in rows], ["T-0001", "T-0002"])
        rows, _ = core.select(self.board, INST, 3, route=route, position=pos,
                              position_first=True)
        self.assertEqual([r["id"] for r in rows], ["T-0002", "T-0001"])

    def test_extra_rows_follow_in_progress_and_count_against_the_cut(self):
        self.put("T-0001")
        self.put("T-0002", status="in-progress")
        land = {"id": "T-0900", "status": "delivered", "route": {"how": "agent"}}
        rows, total = core.select(self.board, INST, 3, route=route, extra=[land])
        self.assertEqual([r["id"] for r in rows], ["T-0002", "T-0900", "T-0001"])
        self.assertEqual(total, 3)
        rows, _ = core.select(self.board, INST, 2, route=route, extra=[land])
        self.assertEqual([r["id"] for r in rows], ["T-0002", "T-0900"])

    def test_run_prints_the_header_first(self):
        self.put("T-0001")
        out = io.StringIO()
        a = core.parser("d").parse_args([])
        core.run(a, INST, self.board, 3, route, out=out, header={"text": ["SWEEP FIRST"]})
        self.assertTrue(out.getvalue().startswith("SWEEP FIRST\n"))
        out = io.StringIO()
        a = core.parser("d").parse_args(["--json"])
        core.run(a, INST, self.board, 3, route, out=out, header={"json": {"sweep": {"x": 1}}})
        self.assertEqual(json.loads(out.getvalue())["sweep"], {"x": 1})


class ResumeFirstTests(Board):
    def test_in_progress_comes_before_higher_priority_open(self):
        self.put("T-0001", priority="high")
        self.put("T-0002", status="in-progress", priority="low")
        self.put("T-0003", status="in-progress", priority="high")
        self.assertEqual(self.ids(), ["T-0003", "T-0002", "T-0001"])

    def test_unfinished_ids_are_reported(self):
        self.put("T-0001")
        self.put("T-0002", status="in-progress")
        rows, _ = core.select(self.board, INST, 3, route=route)
        self.assertEqual(core.unfinished(rows), ["T-0002"])
        self.assertEqual(core.unfinished(rows[1:]), [])


class ReturnLegTests(Board):
    def relay_parent(self, child_status, waiting=None, final_to="scientist"):
        self.put("T-0002", status=child_status, frm=INST, to="scientist@t",
                 kind="research", parent="T-0001", final_to=final_to)
        self.put("T-0001", status="blocked", kind="research", frm="expert@t",
                 waiting_on=waiting or ["T-0002"], final_to=final_to)

    def test_ready_parent_is_taken_with_return_mark_after_resume_before_open(self):
        self.relay_parent("delivered")
        self.put("T-0003", priority="high")
        self.put("T-0004", status="in-progress", priority="low")
        rows, _ = core.select(self.board, INST, 3, route=route)
        self.assertEqual([(r["id"], r["return"]) for r in rows],
                         [("T-0004", False), ("T-0001", True), ("T-0003", False)])
        self.assertIn("return leg", rows[1]["route"]["why"])
        self.assertEqual(rows[1]["route"]["target"], "do:research")

    def test_terminal_child_counts(self):
        self.relay_parent("closed")
        self.assertEqual(self.ids(), ["T-0001"])

    def test_open_child_or_human_wait_is_not_taken(self):
        self.relay_parent("in-progress")
        self.assertEqual(self.ids(), [])

    def test_waiting_on_human_is_not_taken(self):
        self.relay_parent("delivered", waiting=["T-0002", "human"])
        self.assertEqual(self.ids(), [])

    def test_return_legs_can_be_switched_off(self):
        self.relay_parent("delivered")
        self.assertEqual(self.ids(return_legs=False), [])

    def test_ordinary_rows_carry_return_false(self):
        self.put("T-0001")
        rows, _ = core.select(self.board, INST, 3, route=route)
        self.assertIs(rows[0]["return"], False)


class BlockedFilterTests(Board):
    def test_pending_blocked_is_skipped(self):
        self.put("T-0001", status="blocked", waiting_on=["human"])
        self.put("T-0002", status="blocked", waiting_on=["expert@t"])
        self.put("T-0003")
        self.assertEqual(self.ids(), ["T-0003"])

    def test_dead_route_is_skipped_whatever_its_status(self):
        self.put("T-0001", status="blocked", blocked_by="paper:lem:x", reopen_if="a new invariant")
        self.put("T-0002", status="accepted", blocked_by="T-0009", reopen_if="a new mechanism")
        self.put("T-0003")
        self.assertEqual(self.ids(), ["T-0003"])

    def test_one_of_the_two_fields_alone_is_not_a_dead_route(self):
        self.put("T-0001", blocked_by="paper:lem:x")
        self.put("T-0002", reopen_if="something")
        self.assertEqual(self.ids(), ["T-0001", "T-0002"])

    def test_all_lists_blocked_tickets_marked(self):
        self.put("T-0001", status="blocked", waiting_on=["human"])
        self.put("T-0002", status="blocked", blocked_by="T-0009", reopen_if="new")
        self.put("T-0003")
        rows, total = core.select(self.board, INST, 3, all=True, route=route)
        self.assertEqual({r["id"]: r["blocked"] for r in rows},
                         {"T-0001": "pending", "T-0002": "dead-route", "T-0003": None})
        self.assertEqual(total, 3)

    def test_is_dead_route(self):
        self.assertTrue(core.is_dead_route({"blocked_by": "T-1", "reopen_if": "x"}))
        self.assertFalse(core.is_dead_route({"blocked_by": "T-1"}))
        self.assertFalse(core.is_dead_route({"waiting_on": ["human"]}))


class LimitTests(Board):
    def setUp(self):
        super().setUp()
        for i in range(1, 6):
            self.put("T-000%d" % i)

    def test_cap_is_three(self):
        rows, total = core.select(self.board, INST, 9, route=route)
        self.assertEqual((len(rows), total), (3, 5))

    def test_smaller_limit_and_floor_of_one(self):
        self.assertEqual(len(self.ids(limit=2)), 2)
        self.assertEqual(len(self.ids(limit=0)), 1)

    def test_all_does_not_cut(self):
        self.assertEqual(len(self.ids(all=True, limit=1)), 5)

    def test_campaign_lifts_the_cap_of_three(self):
        for i in range(1, 6):
            self.put("T-001%d" % i, campaign="paper:thm:main")
        rows, total = core.select(self.board, INST, 9, route=route, campaign="paper:thm:main")
        self.assertEqual((len(rows), total), (5, 5))


class CampaignFilterTests(Board):
    def test_only_tickets_carrying_the_campaign_tag(self):
        self.put("T-0001")
        self.put("T-0002", campaign="paper:thm:main")
        self.put("T-0003", campaign="paper:other")
        self.put("T-0004", status="in-progress", campaign="paper:thm:main")
        self.assertEqual(self.ids(campaign="paper:thm:main"), ["T-0004", "T-0002"])
        self.assertEqual(self.ids(), ["T-0004", "T-0001", "T-0002"])

    def test_campaign_still_skips_dead_routes(self):
        self.put("T-0001", campaign="c", blocked_by="T-0009", reopen_if="new")
        self.put("T-0002", campaign="c")
        self.assertEqual(self.ids(campaign="c"), ["T-0002"])

    def test_campaign_is_an_allowed_ticket_field(self):
        meta = {"id": "T-0001", "title": "t", "kind": "prove", "from": "author@t",
                "to": INST, "status": "open", "priority": "normal", "ask": "a",
                "deliverable": "d", "budget": {"runs": 1, "max_model": "sonnet"},
                "created": "2026-09-29", "updated": "2026-09-29", "campaign": "paper:x"}
        self.assertEqual(ac.validate_ticket(meta), [])
        self.assertIn("campaign", ac.TICKET_FIELDS["sender"])


class RowShapeTests(Board):
    def test_row_shape_and_over_budget(self):
        self.put("T-0001", kind="code")
        self.put("T-0002", kind="verify")
        rows, _ = core.select(self.board, INST, 3, route=route)
        r = rows[0]
        for key in ("id", "kind", "priority", "return", "route", "over_budget"):
            self.assertIn(key, r)
        self.assertEqual(set(r["route"]) & {"how", "target", "why"}, {"how", "target", "why"})
        self.assertEqual((r["route"]["how"], r["route"]["target"]), ("agent", "developer"))
        self.assertEqual(r["over_budget"], "opus")
        self.assertNotIn("over_budget", r["route"])
        self.assertIsNone(rows[1]["over_budget"])
        self.assertEqual(rows[1]["route"]["how"], "reject")
        self.assertTrue(r["path"].endswith(".md"))

    def test_json_serialisable(self):
        self.put("T-0001")
        rows, _ = core.select(self.board, INST, 3, route=route)
        json.dumps(rows)


class CheckpointTests(Board):
    def state(self, **kw):
        meta = {"id": "T-0001", "status": "open"}
        meta.update(kw)
        return core.serial_checkpoint(meta)

    def test_delivered_rejected_and_blocked_are_settled(self):
        for kw, want in (({"status": "delivered", "result": "r"}, "delivered"),
                         ({"status": "closed", "result": "r"}, "delivered"),
                         ({"status": "rejected"}, "rejected"),
                         ({"status": "cancelled"}, "rejected"),
                         ({"status": "blocked", "waiting_on": ["human"]}, "blocked"),
                         ({"status": "blocked", "blocked_by": "T-9",
                           "reopen_if": "new"}, "blocked")):
            r = self.state(**kw)
            self.assertEqual((r["state"], r["unfinished"], r["problem"]), (want, False, None), kw)

    def test_open_accepted_in_progress_are_unfinished(self):
        for st in ("open", "accepted", "in-progress"):
            r = self.state(status=st)
            self.assertEqual((r["state"], r["unfinished"]), ("unfinished", True), st)

    def test_delivered_without_result_and_blocked_without_reason_are_problems(self):
        r = self.state(status="delivered")
        self.assertIn("result", r["problem"])
        self.assertTrue(r["unfinished"])
        r = self.state(status="blocked")
        self.assertIn("reason", r["problem"])
        self.assertTrue(r["unfinished"])

    def test_check_reads_the_board(self):
        self.put("T-0001", status="in-progress")
        r = core.check(self.board, "T-0001")
        self.assertEqual((r["id"], r["state"]), ("T-0001", "unfinished"))
        with self.assertRaises(ac.AcademyError):
            core.check(self.board, "T-0099")


class CliTests(Board):
    """``inbox_core.run``: the shared printing, exit codes and the --n / --limit alias."""

    def parse(self, *argv):
        return core.parser("d").parse_args(list(argv))

    def run_it(self, *argv, budget_limit=3):
        out = io.StringIO()
        code = core.run(self.parse(*argv), INST, self.board, budget_limit, route, out=out)
        return code, out.getvalue()

    def test_json_shape_and_remaining(self):
        for i in range(1, 6):
            self.put("T-000%d" % i)
        code, out = self.run_it("--json")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual((data["instance"], len(data["take"]), data["remaining"],
                          data["waiting"], data["limit"]), (INST, 3, 2, 5, 3))

    def test_limit_is_an_alias_of_n_and_capped(self):
        for i in range(1, 6):
            self.put("T-000%d" % i)
        self.assertEqual(len(json.loads(self.run_it("--json", "--limit", "2")[1])["take"]), 2)
        self.assertEqual(len(json.loads(self.run_it("--json", "--n", "2")[1])["take"]), 2)
        self.assertEqual(len(json.loads(self.run_it("--json", "--n", "9")[1])["take"]), 3)

    def test_budget_limit_bounds_n(self):
        for i in range(1, 6):
            self.put("T-000%d" % i)
        data = json.loads(self.run_it("--json", "--n", "3", budget_limit=1)[1])
        self.assertEqual((len(data["take"]), data["limit"]), (1, 1))

    def test_campaign_option(self):
        for i in range(1, 6):
            self.put("T-000%d" % i, campaign="c")
        self.put("T-0009")
        data = json.loads(self.run_it("--json", "--campaign", "c", "--n", "9")[1])
        self.assertEqual([r["id"] for r in data["take"]], ["T-000%d" % i for i in range(1, 6)])

    def test_all_option_lists_everything(self):
        for i in range(1, 6):
            self.put("T-000%d" % i)
        data = json.loads(self.run_it("--json", "--all")[1])
        self.assertEqual((len(data["take"]), data["remaining"]), (5, 0))

    def test_text_output_marks_return_and_over_budget(self):
        self.put("T-0002", status="delivered", frm=INST, to="scientist@t", kind="research",
                 parent="T-0001", final_to="scientist")
        self.put("T-0001", status="blocked", kind="research", waiting_on=["T-0002"],
                 final_to="scientist")
        self.put("T-0003", kind="code")
        code, out = self.run_it()
        self.assertEqual(code, 0)
        self.assertIn("(return)", out)
        self.assertIn("[over budget: opus]", out)

    def test_empty_inbox_exit_1(self):
        code, out = self.run_it()
        self.assertEqual(code, 1)
        self.assertIn("empty", out)
        self.assertIn("0 taken", out)

    def test_check_option(self):
        self.put("T-0001", status="in-progress")
        code, out = self.run_it("--check", "T-0001")
        self.assertEqual(code, 3)
        self.assertIn("unfinished", out)
        self.put("T-0002", status="delivered")
        code, out = self.run_it("--check", "T-0002")
        self.assertEqual(code, 0)
        self.assertIn("delivered", out)

    def test_unfinished_ticket_is_flagged(self):
        self.put("T-0001", status="in-progress")
        self.put("T-0002")
        data = json.loads(self.run_it("--json")[1])
        self.assertEqual(data["unfinished"], ["T-0001"])
        self.assertEqual(data["take"][0]["id"], "T-0001")


STUB = r'''import json, os, sys, time
mode = %r
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "calls.log"), "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}) + "\n")
if mode == "sleep":
    time.sleep(30)
print("checkpoint stub: pushed")
sys.exit(1 if mode == "fail" else 0)
'''


class ShipCheckpointHookTests(Board):
    """``--check`` on a ticket settled as finished runs the academy's
    ``ship.py --workspace <root> checkpoint --ticket <id> --role <role>`` (non-fatal, never
    for an unfinished or blocked ticket, a board that is not the workspace's, an absent
    ship.py, or ``"shipCheckpoint": false``). The script is a stub (``SHIP_SCRIPT``)."""

    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="inbox-ws-")
        self.board = os.path.join(self.ws, "board")
        os.makedirs(self.board)
        os.makedirs(os.path.join(self.ws, "scripts"))
        with open(os.path.join(self.ws, ".gitmodules"), "w") as f:
            for sub in ("home", "board", "library", "a"):
                f.write('[submodule "%s"]\n\tpath = %s\n\turl = x\n' % (sub, sub))
        self.write_ws()
        self.stub("ok")
        from unittest import mock
        p = mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": self.ws})
        p.start()
        self.addCleanup(p.stop)
        q = mock.patch.object(core, "SHIP_SCRIPT", os.path.join(self.ws, "scripts", "ship.py"))
        q.start()
        self.addCleanup(q.stop)

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)

    def write_ws(self, **extra):
        doc = {"board": self.board.replace("\\", "/"),
               "instances": {INST: {"role": "researcher", "home": self.ws + "/home",
                                    "domains": ["d"]},
                             "expert@t": {"role": "expert", "home": self.ws + "/library",
                                          "domains": ["d"]},
                             "author@t": {"role": "author", "home": self.ws + "/a",
                                          "domains": ["d"]}}}
        doc.update(extra)
        with open(os.path.join(self.ws, "workspace.json"), "w") as f:
            json.dump(doc, f)

    def stub(self, mode):
        with open(os.path.join(self.ws, "scripts", "ship.py"), "w") as f:
            f.write(STUB % mode)

    def calls(self):
        log = os.path.join(self.ws, "scripts", "calls.log")
        if not os.path.isfile(log):
            return []
        with open(log) as f:
            return [json.loads(line) for line in f if line.strip()]

    def check(self, tid, board=None, instance=INST, **kw):
        args = core.parser("d").parse_args(["--check", tid, "--workspace",
                                            os.path.join(self.ws, "workspace.json")])
        out, err = io.StringIO(), io.StringIO()
        from unittest import mock
        with mock.patch("sys.stderr", err):
            code = core.run(args, instance, board or self.board, 3, route, out=out, **kw)
        return code, out.getvalue(), err.getvalue()

    def test_delivered_ticket_runs_checkpoint_once(self):
        self.put("T-0001", status="delivered")
        code, out, err = self.check("T-0001")
        self.assertEqual(code, 0)
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["argv"],
                         ["--workspace", os.path.realpath(self.ws), "checkpoint", "--ticket",
                          "T-0001", "--role", "researcher", "--only", "home", "board"])
        self.assertEqual(os.path.normcase(os.path.realpath(calls[0]["cwd"])),
                         os.path.normcase(os.path.realpath(self.ws)))
        self.assertEqual(err, "")

    def test_closed_rejected_cancelled_run_checkpoint(self):
        for i, st in enumerate(("closed", "rejected", "cancelled"), 1):
            self.put("T-000%d" % i, status=st)
            self.assertEqual(self.check("T-000%d" % i)[0], 0)
        self.assertEqual([c["argv"][4] for c in self.calls()], ["T-0001", "T-0002", "T-0003"])

    def test_unfinished_blocked_and_problem_tickets_do_not_run_it(self):
        self.put("T-0001", status="in-progress")
        self.put("T-0002", status="blocked", waiting_on=["human"])
        self.put("T-0003", status="delivered")
        self.write_ticket_without_result("T-0003")
        self.assertEqual(self.check("T-0001")[0], 3)
        self.assertEqual(self.check("T-0002")[0], 0)
        self.assertEqual(self.check("T-0003")[0], 3)
        self.assertEqual(self.calls(), [])

    def write_ticket_without_result(self, tid):
        store = ac.as_store(self.board)
        ref, meta, body = store.get(tid)
        meta.pop("result", None)
        store.save(meta, body, ref=ref)

    def test_opt_out_key_disables_it(self):
        self.write_ws(shipCheckpoint=False)
        self.put("T-0001", status="delivered")
        self.assertEqual(self.check("T-0001")[0], 0)
        self.assertEqual(self.calls(), [])

    def test_absent_ship_py_is_silent(self):
        os.remove(os.path.join(self.ws, "scripts", "ship.py"))
        self.put("T-0001", status="delivered")
        code, out, err = self.check("T-0001")
        self.assertEqual((code, err), (0, ""))

    def test_other_board_than_the_workspace_one_does_not_run_it(self):
        other = tempfile.mkdtemp(prefix="inbox-other-")
        self.addCleanup(shutil.rmtree, other, True)
        saved, self.board = self.board, other
        self.put("T-0001", status="delivered")
        self.board = saved
        self.assertEqual(self.check("T-0001", board=other)[0], 0)
        self.assertEqual(self.calls(), [])

    def test_failure_is_a_warning_and_keeps_the_exit_code(self):
        self.stub("fail")
        self.put("T-0001", status="delivered")
        code, out, err = self.check("T-0001")
        self.assertEqual(code, 0)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("warning", err)
        self.assertIn("T-0001: delivered", out)

    def test_timeout_is_a_warning_and_keeps_the_exit_code(self):
        self.stub("sleep")
        self.put("T-0001", status="delivered")
        from unittest import mock
        with mock.patch.object(core, "SHIP_TIMEOUT", 2):
            code, out, err = self.check("T-0001")
        self.assertEqual(code, 0)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("timed out", err)

    def role_and_only(self):
        argv = self.calls()[0]["argv"]
        return argv[argv.index("--role") + 1], argv[argv.index("--only") + 1:]

    def test_role_without_instance_comes_from_the_addressee(self):
        self.put("T-0001", status="delivered", to="author@t", frm=INST)
        self.assertEqual(self.check("T-0001", instance="")[0], 0)
        self.assertEqual(self.role_and_only(), ("author", ["a", "board"]))

    def test_explicit_role_wins(self):
        # the Author's --check: no instance, role author; a landing addressed elsewhere
        self.put("T-0001", status="delivered")
        self.assertEqual(self.check("T-0001", instance="", role="author")[0], 0)
        self.assertEqual(self.role_and_only(), ("author", ["a", "board"]))

    def test_expert_scope_is_its_home_board_and_library(self):
        self.put("T-0001", status="delivered", to="expert@t")
        self.assertEqual(self.check("T-0001", instance="expert@t")[0], 0)
        self.assertEqual(self.role_and_only(), ("expert", ["library", "board"]))

    def test_expert_with_a_home_elsewhere_still_gets_library(self):
        self.write_ws(instances={
            "expert@t": {"role": "expert", "home": self.ws + "/a", "domains": ["d"]}})
        self.put("T-0001", status="delivered", to="expert@t")
        self.assertEqual(self.check("T-0001", instance="expert@t")[0], 0)
        self.assertEqual(self.role_and_only(), ("expert", ["a", "board", "library"]))

    def test_unmappable_home_scopes_to_board_only_and_says_so(self):
        self.write_ws(instances={INST: {"role": "researcher", "home": self.ws + "/elsewhere",
                                        "domains": ["d"]}})
        self.put("T-0001", status="delivered")
        code, out, err = self.check("T-0001")
        self.assertEqual(code, 0)
        self.assertEqual(self.role_and_only(), ("researcher", ["board"]))
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("board only", err)

    def test_session_outside_the_workspace_does_not_run_it(self):
        outside = tempfile.mkdtemp(prefix="inbox-outside-")
        self.addCleanup(shutil.rmtree, outside, True)
        self.put("T-0001", status="delivered")
        from unittest import mock
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": outside}):
            code, out, err = self.check("T-0001")
        self.assertEqual(code, 0)
        self.assertEqual(self.calls(), [])
        self.assertEqual(err.strip(), "checkpoint not run: session is outside %s; run it by "
                         "hand: py scripts/ship.py checkpoint --ticket T-0001 --role researcher"
                         " --only home board" % os.path.realpath(self.ws))

    def session_at(self, *parts):
        d = os.path.join(self.ws, *parts)
        os.makedirs(d, exist_ok=True)
        from unittest import mock
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": d}):
            return self.check("T-0001")

    def test_a_worktree_session_inside_the_root_does_not_run_it(self):
        self.put("T-0001", status="delivered")
        for parts in ((".claude", "worktrees", "x"),               # a workspace worktree
                      ("home", ".claude", "worktrees", "y"),       # ship.py start --worktree
                      (".claude", "worktrees", "x", "home")):      # deeper inside one
            code, out, err = self.session_at(*parts)
            self.assertEqual(code, 0)
            self.assertIn("checkpoint not run: session is outside", err, parts)
            self.assertIn("--only home board", err)
        self.assertEqual(self.calls(), [])

    def test_a_session_at_the_root_or_in_a_submodule_home_runs_it(self):
        self.put("T-0001", status="delivered")
        self.assertEqual(self.session_at()[0], 0)
        self.assertEqual(self.session_at("home", "sub", "dir")[0], 0)
        self.assertEqual(len(self.calls()), 2)

    def gitmodules(self, *subs):
        with open(os.path.join(self.ws, ".gitmodules"), "w") as f:
            for sub in subs:
                f.write('[submodule "%s"]\n\tpath = %s\n\turl = x\n' % (sub, sub))

    def test_a_plain_board_directory_of_the_workspace_is_in_scope(self):
        # the folded layout: board/ is a directory of the workspace repo, not a submodule
        self.gitmodules("home", "library", "a")
        self.put("T-0001", status="delivered")
        self.assertEqual(self.check("T-0001")[0], 0)
        self.assertEqual(self.role_and_only(), ("researcher", ["home", "board"]))

    def test_a_board_that_is_its_own_repository_is_not_in_scope(self):
        self.gitmodules("home", "library", "a")
        os.makedirs(os.path.join(self.board, ".git"))
        self.put("T-0001", status="delivered")
        self.assertEqual(self.check("T-0001")[0], 0)
        self.assertEqual(self.role_and_only(), ("researcher", ["home"]))

    def test_the_plugin_script_is_used_by_default(self):
        from unittest import mock
        with mock.patch.object(core, "SHIP_SCRIPT", None):
            script = core.ship_script(self.ws)
        self.assertTrue(script.endswith(os.path.join("academy", "scripts", "ship.py")), script)
        self.assertTrue(os.path.isfile(script))
        self.assertNotEqual(os.path.dirname(os.path.dirname(script)),
                            os.path.join(self.ws, "scripts"))

    def test_without_a_scope_the_by_hand_command_still_names_only(self):
        # neither submodules nor a board inside the workspace: nothing to scope to
        os.remove(os.path.join(self.ws, ".gitmodules"))
        other = tempfile.mkdtemp(prefix="inbox-board-")
        self.addCleanup(shutil.rmtree, other, True)
        self.write_ws(board=other.replace("\\", "/"))
        saved, self.board = self.board, other
        self.put("T-0001", status="delivered")
        code, out, err = self.check("T-0001", board=other)
        self.board = saved
        self.assertEqual(code, 0)
        self.assertEqual(self.calls(), [])
        self.assertIn("py scripts/ship.py checkpoint --ticket T-0001 --role researcher "
                      "--only <your home submodule> board", err)

    def test_exit_1_advice_is_scoped_and_names_start(self):
        self.stub("fail")
        self.put("T-0001", status="delivered")
        code, out, err = self.check("T-0001")
        self.assertEqual(code, 0)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("exited 1", err)
        self.assertIn("py scripts/ship.py start <sub> <topic>", err)
        self.assertIn("py scripts/ship.py checkpoint --ticket T-0001 --role researcher "
                      "--only home board", err)

    def test_timeout_advice_is_scoped(self):
        self.stub("sleep")
        self.put("T-0001", status="delivered")
        from unittest import mock
        with mock.patch.object(core, "SHIP_TIMEOUT", 2):
            code, out, err = self.check("T-0001")
        self.assertIn("--only home board", err)

    def test_cwd_is_used_without_claude_project_dir(self):
        self.put("T-0001", status="delivered")
        from unittest import mock
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("os.getcwd", return_value=os.path.join(self.ws, "home")):
            self.assertEqual(self.check("T-0001")[0], 0)
        self.assertEqual(len(self.calls()), 1)

    def test_an_unexpected_error_is_one_warning_never_raised(self):
        self.put("T-0001", status="delivered")

        class Boom(io.StringIO):
            def write(self, s):
                if "stub" in s:
                    raise UnicodeEncodeError("cp1252", s, 0, 1, "boom")
                return super().write(s)
        args = core.parser("d").parse_args(["--check", "T-0001", "--workspace",
                                            os.path.join(self.ws, "workspace.json")])
        err = io.StringIO()
        from unittest import mock
        with mock.patch("sys.stderr", err):
            code = core.run(args, INST, self.board, 3, route, out=Boom())
        self.assertEqual(code, 0)
        self.assertEqual(len(err.getvalue().strip().splitlines()), 1)
        self.assertIn("warning", err.getvalue())

    def test_timeout_is_90_seconds(self):
        self.assertEqual(core.SHIP_TIMEOUT, 90)

    def test_check_help_names_the_side_effect(self):
        helps = {a.dest: a.help for a in core.parser("d")._actions}
        self.assertIn("ship.py checkpoint", helps["check"])


if __name__ == "__main__":
    unittest.main()
