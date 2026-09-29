"""next.py: the ordered ready set from agenda.md + roadmap.md + board tickets (plan 4, 10.4)."""

import json
import os
import subprocess
import sys
import unittest

from fixtures import SCRIPTS, Sandbox

sys.path.insert(0, SCRIPTS)
import agenda_lib as al  # noqa: E402
import next as nx  # noqa: E402

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


class NextPlanTests(unittest.TestCase):
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

    def test_ordered_ready_set(self):
        p = nx.plan(self.ctx())
        self.assertEqual([r["id"] for r in p["ready"]],
                         ["R-0005", "T-0001", "R-0002", "R-0001", "R-0006",
                          "R-0004", "T-0006", "R-0012"])
        self.assertEqual([r["id"] for r in p["selected"]], ["R-0005", "T-0001", "R-0002"])
        self.assertEqual(p["remaining_ready"], 5)

    def test_positions_come_from_what_an_item_unblocks(self):
        p = nx.plan(self.ctx())
        pos = {r["id"]: r["position"] for r in p["ready"]}
        self.assertEqual(pos["R-0002"], 1)      # lem:b is at 3, but thm:main rests on it
        self.assertEqual(pos["R-0001"], 5)
        self.assertIsNone(pos["R-0004"])        # global sorts last

    def test_routes(self):
        p = {r["id"]: r for r in nx.plan(self.ctx())["ready"]}
        self.assertEqual((p["R-0001"]["action"], p["R-0001"]["agent"]), ("agent", "math-editor"))
        self.assertEqual((p["R-0002"]["action"], p["R-0002"]["agent"]), ("agent", "math-writer"))
        self.assertEqual((p["R-0005"]["action"], p["R-0005"]["kind"], p["R-0005"]["to"]),
                         ("ticket", "verify", "expert@t"))
        self.assertEqual((p["R-0006"]["action"], p["R-0006"]["agent"]), ("land", "math-writer"))
        self.assertEqual((p["T-0001"]["action"], p["T-0001"]["agent"]), ("agent", "figure-maker"))
        self.assertEqual(p["T-0006"]["action"], "triage")

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

    def test_items_per_run_is_capped_at_three(self):
        self.assertEqual(len(nx.plan(self.ctx(items=1))["selected"]), 1)
        self.assertEqual(len(nx.plan(self.ctx(items=9))["selected"]), 3)

    def test_statuses_override_unblocks(self):
        p = nx.plan(self.ctx(statuses={"paper:lem:b": "proved"}))
        ready = [r["id"] for r in p["ready"]]
        self.assertIn("R-0011", ready)
        self.assertLess(ready.index("R-0011"), ready.index("R-0002"))

    def test_done_dependency_unblocks(self):
        rm = al.parse_roadmap(al.read_text(self.roadmap))
        rm.get("R-0004").fields["status"] = "done"
        al.write_text(self.roadmap, al.write_roadmap(rm))
        p = nx.plan(self.ctx())
        self.assertEqual(p["ready"][0]["id"], "R-0003")   # high priority at position 1

    def test_cli_plan_from_home_config(self):
        env = dict(self.sb.env)
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "next.py"), "plan",
                              "--json", "--home", self.sb.home], capture_output=True, env=env)
        self.assertEqual(res.returncode, 0, res.stderr)
        p = json.loads(res.stdout.decode("utf-8"))
        self.assertEqual([r["id"] for r in p["selected"]], ["R-0005", "T-0001", "R-0002"])
        text = subprocess.run([sys.executable, os.path.join(SCRIPTS, "next.py"), "plan",
                               "--home", self.sb.home], capture_output=True, env=env)
        self.assertIn("SELECTED", text.stdout.decode("utf-8"))


class NextWriteTests(unittest.TestCase):
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
        with self.assertRaises(nx.NextError):
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

    def test_file_refuses_non_ask_items(self):
        with self.assertRaises(nx.NextError):
            nx.file_ticket(self.ctx(), "R-0001", dry_run=True)


class AskLineTests(unittest.TestCase):

    def test_a_leading_list_marker_is_dropped(self):
        it = al.Item("R-0001", "verify", "Verify lem:x", {}, "- `lem:x` -- check it\n")
        self.assertEqual(nx._ask_line(it), "Verify lem:x -- `lem:x` -- check it")

    def test_plain_first_paragraph_is_kept(self):
        it = al.Item("R-0001", "cite", "Cite X", {}, "Pinpoint X.\n\nMore.")
        self.assertEqual(nx._ask_line(it), "Cite X -- Pinpoint X.")


if __name__ == "__main__":
    unittest.main()
