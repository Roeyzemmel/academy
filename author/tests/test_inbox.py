"""inbox.py: roadmap items become self-tickets, the ordered inbox, idempotent filing, sweep first."""

import json
import os
import subprocess
import sys
import unittest

from fixtures import SCRIPTS, Sandbox

sys.path.insert(0, SCRIPTS)
import agenda_lib as al  # noqa: E402
import inbox as nx  # noqa: E402
import routes  # noqa: E402
import _academy as ac  # noqa: E402

AGENDA = """# Agenda: author@t

## Milestones

- `round-1`: thm:main=proved, prop:a=sketch

## Entries

| # | label | claim | required | depends_on | owner | status |
|---|---|---|---|---|---|---|
| 1 | thm:main | paper:thm:main | proved | lem:b | author@t | sketch |
| 2 | prop:a | paper:prop:a | sketch | - | author@t | sketch |
| 3 | lem:b | paper:lem:b | proved | defn:c | author@t | sketch |
| 4 | defn:c | paper:defn:c | proved | - | author@t | proved |
| 5 | lem:d | paper:lem:d | proved | - | author@t | open |
"""


def item(iid, tag, title, **fields):
    body = fields.pop("body", "Do %s." % title)
    lines = ["## %s [%s] %s" % (iid, tag, title)]
    fields = dict([("status", fields.pop("status", "open"))] + list(fields.items()))
    for k, v in fields.items():
        lines.append("- %s: %s" % (k, v))
    return "\n".join(lines) + "\n\n" + body + "\n"


ROADMAP = "# Roadmap: author@t\n\nPreamble.\n\n" + "\n".join([
    item("R-0001", "apply", "Fix lem:d wording", agenda="paper:lem:d"),
    item("R-0002", "write", "Explain lem:b", agenda="lem:b", priority="low"),
    item("R-0003", "apply", "Main theorem edit", agenda="paper:thm:main", priority="high",
         depends_on="[R-0004]"),
    item("R-0004", "write", "Global prose pass", agenda="global", priority="high"),
    item("R-0005", "verify", "Verify lem:b", agenda="paper:lem:b"),
    item("R-0006", "lead", "Prove lem:d", agenda="paper:lem:d", status="ticketed",
         ticket="T-0002"),
    item("R-0007", "cite", "Cite LMW16", agenda="global", status="ticketed", ticket="T-0003"),
    item("R-0008", "apply", "Already done", agenda="global", status="done"),
    item("R-0009", "write", "Ask Roey", agenda="global", status="needs-human"),
    item("R-0010", "apply", "After a rejected ticket", agenda="prop:a",
         depends_on="[T-0004]"),
    item("R-0011", "verify", "Verify thm:main", agenda="paper:thm:main"),
    item("R-0012", "write", "After prop:a", agenda="global", depends_on="[paper:prop:a]"),
])


def ticket(board, tid, to, status, kind="other", frm="author@t", agenda="", priority="normal",
           result=""):
    text = ("---\nid: %s\ntitle: %s ticket\nkind: %s\nfrom: %s\nto: %s\nstatus: %s\n"
            "priority: %s\nask: x\ndeliverable: y\nagenda: %s\nresult: %s\n---\n\n"
            "## Ask\n\n## Result\n\n## Thread\n" % (tid, kind, kind, frm, to, status,
                                                     priority, agenda, result))
    path = os.path.join(board, to, "%s-%s-ticket.md" % (tid, kind))
    Sandbox.write(path, text)


class InboxPlanTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.agenda = os.path.join(self.sb.home, "Drafts", "agenda.md")
        self.roadmap = os.path.join(self.sb.home, "Drafts", "roadmap.md")
        self.sb.write(self.agenda, AGENDA)
        self.sb.write(self.roadmap, ROADMAP)
        b = self.sb.board
        ticket(b, "T-0001", "author@t", "open", kind="figure", frm="human",
               agenda="paper:thm:main")
        ticket(b, "T-0002", "researcher@t", "delivered", kind="prove",
               agenda="paper:lem:d", result="proved")
        ticket(b, "T-0003", "expert@t", "open", kind="cite")
        ticket(b, "T-0004", "expert@t", "rejected", kind="verify")
        ticket(b, "T-0005", "author@t", "closed", kind="build")
        ticket(b, "T-0006", "author@t", "accepted", kind="question", priority="high")
        os.environ["ACADEMY_WORKSPACE"] = self.sb.workspace

    def tearDown(self):
        os.environ.pop("ACADEMY_WORKSPACE", None)
        self.sb.cleanup()

    def ctx(self, items=3, statuses=None):
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        return nx.Context(self.agenda, self.roadmap, self.sb.board, ws, "author@t", "paper",
                          items, ["dom"], statuses)

    def run_cli(self, *args):
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "inbox.py")]
                             + list(args) + ["--home", self.sb.home],
                             capture_output=True, env=dict(self.sb.env))
        return res.returncode, res.stdout.decode("utf-8"), res.stderr.decode("utf-8")

    def test_ready_items_in_paper_order(self):
        p = nx.plan(self.ctx())
        self.assertEqual([r["id"] for r in p["to_file"]],
                         ["R-0005", "R-0002", "R-0001", "R-0004", "R-0012"])
        self.assertEqual([r["id"] for r in p["land"]], ["R-0006"])

    def test_positions_come_from_what_an_item_unblocks(self):
        p = nx.plan(self.ctx())
        pos = {r["id"]: r["position"] for r in p["to_file"]}
        self.assertEqual(pos["R-0002"], 1)      # lem:b is at 3, but thm:main rests on it
        self.assertEqual(pos["R-0001"], 5)
        self.assertIsNone(pos["R-0004"])        # global sorts last

    def test_actions(self):
        p = {r["id"]: r for r in nx.plan(self.ctx())["to_file"]}
        self.assertEqual((p["R-0001"]["action"], p["R-0001"]["agent"], p["R-0001"]["kind"]),
                         ("self", "math-editor", "apply"))
        self.assertEqual((p["R-0002"]["action"], p["R-0002"]["agent"], p["R-0002"]["kind"]),
                         ("self", "math-writer", "write"))
        self.assertEqual((p["R-0005"]["action"], p["R-0005"]["kind"], p["R-0005"]["to"]),
                         ("ticket", "verify", "expert@t"))
        land = nx.plan(self.ctx())["land"][0]
        self.assertEqual((land["action"], land["ticket"]), ("land", "T-0002"))
        rows = nx.land_rows(self.ctx(), nx.plan(self.ctx()))
        self.assertEqual((rows[0]["id"], rows[0]["route"]["target"], rows[0]["return"]),
                         ("T-0002", "math-writer", True))

    def test_waiting_and_parked(self):
        p = nx.plan(self.ctx())
        waiting = {r["id"]: r["reason"] for r in p["waiting"]}
        parked = {r["id"]: r["reason"] for r in p["parked"]}
        self.assertEqual(set(waiting), {"R-0003", "R-0007", "R-0011"})
        self.assertIn("R-0004", waiting["R-0003"])
        self.assertIn("T-0003", waiting["R-0007"])
        self.assertIn("lem:b", waiting["R-0011"])     # verify waits for its entry's inputs
        self.assertEqual(set(parked), {"R-0009", "R-0010"})
        self.assertIn("rejected", parked["R-0010"])

    def test_statuses_override_unblocks(self):
        p = nx.plan(self.ctx(statuses={"paper:lem:b": "proved"}))
        ready = [r["id"] for r in p["to_file"]]
        self.assertIn("R-0011", ready)
        self.assertLess(ready.index("R-0011"), ready.index("R-0002"))

    def test_done_dependency_unblocks(self):
        rm = al.parse_roadmap(al.read_text(self.roadmap))
        rm.get("R-0004").fields["status"] = "done"
        al.write_text(self.roadmap, al.write_roadmap(rm))
        p = nx.plan(self.ctx())
        self.assertEqual(p["to_file"][0]["id"], "R-0003")   # high priority at position 1

    def test_inbox_takes_land_first_then_by_position_and_caps_at_three(self):
        code, out, err = self.run_cli("--sync", "--json")
        self.assertEqual(code, 0, err)
        d = json.loads(out)
        rows = d["take"]
        self.assertEqual([(r["id"] == "T-0002", r["return"]) for r in rows[:1]], [(True, True)])
        self.assertEqual(rows[1]["id"], "T-0001")           # position 1, normal
        self.assertEqual((rows[2]["kind"], rows[2]["route"]["target"]),
                         ("write", "math-writer"))          # the self-ticket of R-0002
        self.assertIn("R-0002", rows[2]["refs"])
        self.assertEqual((len(rows), d["limit"]), (3, 3))
        self.assertGreater(d["remaining"], 0)

    def test_sweep_comes_first_except_in_all(self):
        code, out, err = self.run_cli("--sync", "--json")
        self.assertEqual(json.loads(out)["sweep"]["target"], "note-sweeper")
        code, out, err = self.run_cli("--sync")
        self.assertTrue(out.startswith("SWEEP FIRST"), out)
        code, out, err = self.run_cli("--all", "--json")
        d = json.loads(out)
        self.assertNotIn("sweep", d)
        self.assertTrue({"R-0003", "R-0007", "R-0011"} <=
                        {r["id"] for r in d["waiting_items"]})
        self.assertEqual({r["id"] for r in d["parked"]}, {"R-0009", "R-0010"})

    def test_unfiled_items_are_reported_without_sync(self):
        code, out, err = self.run_cli("--json")
        self.assertEqual(json.loads(out)["unfiled"], 5)
        code, out, err = self.run_cli()
        self.assertIn("not filed yet", out)

    def test_items_per_run_is_capped_at_three(self):
        self.assertEqual(self.ctx(items=1).items_per_run, 1)
        self.assertEqual(self.ctx(items=9).items_per_run, 3)
        code, out, err = self.run_cli("--sync", "--json", "--n", "1")
        self.assertEqual(len(json.loads(out)["take"]), 1)

    def test_check_reports_an_unfinished_ticket(self):
        code, out, err = self.run_cli("--check", "T-0006")
        self.assertEqual(code, 3, err)
        self.assertIn("unfinished", out)
        code, out, err = self.run_cli("--check", "T-0002")
        self.assertEqual(code, 0)


class RoutesTests(unittest.TestCase):
    def test_route_by_kind(self):
        for kind, target in (("write", "math-writer"), ("apply", "math-editor"),
                             ("copy", "math-editor"), ("figure", "figure-maker"),
                             ("build", "tex-engineer"), ("notation", "notation-auditor"),
                             ("sweep", "note-sweeper"), ("note", "math-writer")):
            r = routes.route({"kind": kind})
            self.assertEqual((r["how"], r["target"]), ("agent", target), kind)

    def test_unknown_kind_is_asked_never_guessed(self):
        for kind in ("question", "decision", "other", "verify", None):
            r = routes.route({"kind": kind})
            self.assertEqual((r["how"], r["target"]), ("human", "human"), kind)

    def test_land_routes(self):
        self.assertEqual(routes.land_route("verify")["target"], "math-editor")
        self.assertEqual(routes.land_route("cite")["target"], "math-editor")
        self.assertEqual(routes.land_route("lead")["target"], "math-writer")
        self.assertEqual(routes.land_route("experiment")["target"], "math-writer")
        self.assertEqual(routes.land_route("referee")["target"], "author:notes")

    def test_every_self_ticket_kind_is_a_ticket_kind_and_routes(self):
        for kind in list(routes.ITEM_KINDS.values()) + list(routes.AGENT_KINDS.values()):
            self.assertIn(kind, ac.TICKET_KINDS)
            self.assertEqual(routes.route({"kind": kind})["how"], "agent")


class InboxWriteTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.agenda = os.path.join(self.sb.home, "Drafts", "agenda.md")
        self.roadmap = os.path.join(self.sb.home, "Drafts", "roadmap.md")
        self.sb.write(self.agenda, AGENDA)
        self.sb.write(self.roadmap, ROADMAP)
        os.environ["ACADEMY_WORKSPACE"] = self.sb.workspace

    def tearDown(self):
        os.environ.pop("ACADEMY_WORKSPACE", None)
        self.sb.cleanup()

    def ctx(self):
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        return nx.Context(self.agenda, self.roadmap, self.sb.board, ws, "author@t", "paper",
                          3, ["dom"])

    def board_tickets(self, folder):
        d = os.path.join(self.sb.board, folder)
        return sorted(f for f in os.listdir(d) if f.startswith("T-"))

    def test_add_and_mark(self):
        it = nx.add(self.ctx(), "apply", "A new  edit", agenda="paper:lem:d",
                    depends_on=["R-0001"], source="notes", body="Body.", date="2026-09-28")
        self.assertEqual(it.id, "R-0013")
        again = al.parse_roadmap(al.read_text(self.roadmap)).get("R-0013")
        self.assertEqual((again.title, again.agenda, again.depends_on),
                         ("A new edit", "paper:lem:d", ["R-0001"]))
        nx.mark(self.ctx(), "R-0013", "done", "how: edited", date="2026-09-29")
        nx.mark(self.ctx(), "R-0013", None, "second note", date="2026-09-30")
        after = al.parse_roadmap(al.read_text(self.roadmap)).get("R-0013")
        self.assertEqual(after.status, "done")
        self.assertTrue(after.body.endswith("- 2026-09-29: status done; how: edited\n"
                                            "- 2026-09-30: second note"))
        with self.assertRaises(nx.InboxError):
            nx.mark(self.ctx(), "R-0013", "finished")

    def test_lead_goes_to_the_expert_for_the_researcher(self):
        c = self.ctx()
        draft = nx.ticket_draft(c, c.roadmap.get("R-0006"))
        self.assertEqual((draft["to"], draft["kind"], draft["final_to"]),
                         ("expert@t", "research", "researcher"))
        self.assertEqual(draft["deliverable"], nx.DELIVERABLES["prove"])

    def test_file_ticket_marks_the_item_ticketed(self):
        draft, dry = nx.file_ticket(self.ctx(), "R-0005", dry_run=True)
        self.assertIsNone(dry)
        self.assertEqual((draft["to"], draft["kind"], draft["refs"], draft["agenda"]),
                         ("expert@t", "verify", ["paper:lem:b"], "paper:lem:b"))
        draft, tid = nx.file_ticket(self.ctx(), "R-0005")
        self.assertRegex(tid, r"^T-\d{4}$")
        path = [f for f in os.listdir(os.path.join(self.sb.board, "expert@t"))
                if f.startswith(tid)][0]
        text = self.sb.read(os.path.join(self.sb.board, "expert@t", path))
        self.assertIn("from: author@t", text)
        self.assertIn("kind: verify", text)
        it = al.parse_roadmap(al.read_text(self.roadmap)).get("R-0005")
        self.assertEqual((it.status, it.ticket), ("ticketed", tid))
        p = nx.plan(self.ctx())
        self.assertIn("R-0005", [r["id"] for r in p["waiting"]])

    def test_a_local_item_becomes_a_self_ticket(self):
        draft, tid = nx.file_ticket(self.ctx(), "R-0001")
        d = os.path.join(self.sb.board, "author@t")
        text = self.sb.read(os.path.join(d, [f for f in os.listdir(d) if f.startswith(tid)][0]))
        meta = ac.read_frontmatter(text)[0]
        self.assertEqual((meta["from"], meta["to"], meta["kind"], meta["status"]),
                         ("author@t", "author@t", "apply", "open"))
        self.assertEqual(meta["refs"], ["R-0001", "paper:lem:d"])
        self.assertEqual(meta["agenda"], "paper:lem:d")
        self.assertEqual(ac.validate_ticket(meta), [])
        it = al.parse_roadmap(al.read_text(self.roadmap)).get("R-0001")
        self.assertEqual((it.status, it.ticket), ("ticketed", tid))
        # it is in the inbox, not in the waiting list
        p = nx.plan(self.ctx())
        self.assertNotIn("R-0001", [r["id"] for r in p["waiting"] + p["to_file"]])

    def test_a_route_field_picks_the_kind(self):
        rm = al.parse_roadmap(al.read_text(self.roadmap))
        rm.get("R-0002").fields["route"] = "figure-maker"
        al.write_text(self.roadmap, al.write_roadmap(rm))
        c = self.ctx()
        self.assertEqual(nx.self_draft(c, c.roadmap.get("R-0002"))["kind"], "figure")

    def test_sync_is_idempotent(self):
        first = nx.sync(self.ctx())
        self.assertEqual([f["item"] for f in first["filed"]],
                         ["R-0005", "R-0002", "R-0001", "R-0004", "R-0012"])
        before = {f: self.board_tickets(f) for f in ("author@t", "expert@t")}
        second = nx.sync(self.ctx())
        self.assertEqual(second, {"filed": [], "settled": []})
        self.assertEqual({f: self.board_tickets(f) for f in ("author@t", "expert@t")}, before)

    def test_a_ticket_already_on_the_board_is_adopted_not_duplicated(self):
        _, tid = nx.file_ticket(self.ctx(), "R-0001")
        rm = al.parse_roadmap(al.read_text(self.roadmap))    # the roadmap write was lost
        rm.get("R-0001").fields["status"] = "open"
        rm.get("R-0001").fields.pop("ticket", None)
        al.write_text(self.roadmap, al.write_roadmap(rm))
        n = len(self.board_tickets("author@t"))
        _, again = nx.file_ticket(self.ctx(), "R-0001")
        self.assertEqual(again, tid)
        self.assertEqual(len(self.board_tickets("author@t")), n)
        it = al.parse_roadmap(al.read_text(self.roadmap)).get("R-0001")
        self.assertEqual((it.status, it.ticket), ("ticketed", tid))

    def test_a_delivered_self_ticket_is_settled_and_the_item_done(self):
        _, tid = nx.file_ticket(self.ctx(), "R-0001")
        import board as bd
        for st in ("accepted", "in-progress"):
            bd.transition_ticket(self.sb.board, tid, st, as_instance="author@t")
        bd.transition_ticket(self.sb.board, tid, "delivered", result="reworded",
                             as_instance="author@t")
        res = nx.sync(self.ctx())
        self.assertEqual(res["settled"], [{"item": "R-0001", "ticket": tid}])
        it = al.parse_roadmap(al.read_text(self.roadmap)).get("R-0001")
        self.assertEqual(it.status, "done")
        self.assertEqual(bd.get_ticket(self.sb.board, tid)[1]["status"], "closed")
        self.assertEqual(nx.sync(self.ctx())["settled"], [])

    def test_mark_done_closes_a_delivered_self_ticket(self):
        _, tid = nx.file_ticket(self.ctx(), "R-0001")
        import board as bd
        for st in ("accepted", "in-progress"):
            bd.transition_ticket(self.sb.board, tid, st, as_instance="author@t")
        bd.transition_ticket(self.sb.board, tid, "delivered", result="ok",
                             as_instance="author@t")
        nx.mark(self.ctx(), "R-0001", "done", "how: edited")
        self.assertEqual(bd.get_ticket(self.sb.board, tid)[1]["status"], "closed")

    def test_mark_done_walks_an_in_progress_self_ticket_to_closed(self):
        _, tid = nx.file_ticket(self.ctx(), "R-0001")
        import board as bd
        for st in ("accepted", "in-progress"):
            bd.transition_ticket(self.sb.board, tid, st, as_instance="author@t")
        nx.mark(self.ctx(), "R-0001", "done", "how: edited")
        meta = bd.get_ticket(self.sb.board, tid)[1]
        self.assertEqual((meta["status"], meta["result"]), ("closed", "how: edited"))

    def test_mark_needs_human_parks_the_self_ticket(self):
        _, tid = nx.file_ticket(self.ctx(), "R-0001")
        import board as bd
        nx.mark(self.ctx(), "R-0001", "needs-human", "asks Roey")
        meta = bd.get_ticket(self.sb.board, tid)[1]
        self.assertEqual((meta["status"], meta["waiting_on"]), ("blocked", ["human"]))
        rows, _ = ac.inbox_core.select(self.sb.board, "author@t", 3, route=routes.route)
        self.assertNotIn(tid, [r["id"] for r in rows])

    def test_file_refuses_a_non_open_item(self):
        with self.assertRaises(nx.InboxError):
            nx.file_ticket(self.ctx(), "R-0008", dry_run=True)

    def test_cli_subcommands(self):
        env = dict(self.sb.env)
        base = [sys.executable, os.path.join(SCRIPTS, "inbox.py")]
        res = subprocess.run(base + ["sync", "--dry-run", "--home", self.sb.home],
                             capture_output=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.board_tickets("author@t"), [])
        res = subprocess.run(base + ["sync", "--home", self.sb.home],
                             capture_output=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)
        res = subprocess.run(base + ["sync", "--home", self.sb.home],
                             capture_output=True, env=env)
        self.assertEqual(res.returncode, 1)                  # nothing new to file
        res = subprocess.run(base + ["mark", "R-0004", "--status", "done", "--home",
                                     self.sb.home], capture_output=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)


class AskLineTests(unittest.TestCase):

    def test_a_leading_list_marker_is_dropped(self):
        it = al.Item("R-0001", "verify", "Verify lem:x", {}, "- `lem:x` -- check it\n")
        self.assertEqual(nx._ask_line(it), "Verify lem:x -- `lem:x` -- check it")

    def test_plain_first_paragraph_is_kept(self):
        it = al.Item("R-0001", "cite", "Cite X", {}, "Pinpoint X.\n\nMore.")
        self.assertEqual(nx._ask_line(it), "Cite X -- Pinpoint X.")


if __name__ == "__main__":
    unittest.main()
