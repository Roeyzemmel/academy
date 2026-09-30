"""inbox.py: the board is the only queue; tickets are routed, returned ones landed,
released ones offered again, the sweep comes first. Nothing reads or writes a roadmap."""

import hashlib
import json
import os
import re
import subprocess
import sys
import unittest

from fixtures import SCRIPTS, Sandbox

sys.path.insert(0, SCRIPTS)
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


def ticket(board, tid, to, status, kind="other", frm="author@t", agenda="", priority="normal",
           result="", waiting_on=None, final_to=None, body=""):
    wo = ("waiting_on: [%s]\n" % ", ".join(waiting_on)) if waiting_on else ""
    ft = ("final_to: %s\n" % final_to) if final_to else ""
    text = ("---\nid: %s\ntitle: %s ticket\nkind: %s\nfrom: %s\nto: %s\nstatus: %s\n"
            "priority: %s\nask: x\ndeliverable: y\nagenda: %s\nresult: %s\n%s%s---\n\n"
            "## Ask\n\n%s\n\n## Result\n\n## Thread\n" % (tid, kind, kind, frm, to, status,
                                                         priority, agenda, result, wo, ft,
                                                         body))
    path = os.path.join(board, to, "%s-%s-ticket.md" % (tid, kind))
    Sandbox.write(path, text)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class InboxBase(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.agenda = os.path.join(self.sb.home, "Drafts", "agenda.md")
        self.sb.write(self.agenda, AGENDA)
        os.environ["ACADEMY_WORKSPACE"] = self.sb.workspace

    def tearDown(self):
        os.environ.pop("ACADEMY_WORKSPACE", None)
        self.sb.cleanup()

    def ctx(self, items=3):
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        return nx.Context(self.agenda, self.sb.board, ws, "author@t", "paper", items, ["dom"])

    def run_cli(self, *args):
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "inbox.py")]
                             + list(args) + ["--home", self.sb.home],
                             capture_output=True, env=dict(self.sb.env))
        return res.returncode, res.stdout.decode("utf-8"), res.stderr.decode("utf-8")


class InboxPlanTests(InboxBase):
    def setUp(self):
        InboxBase.setUp(self)
        b = self.sb.board
        ticket(b, "T-0001", "author@t", "open", kind="figure", frm="human",
               agenda="paper:thm:main")
        ticket(b, "T-0002", "researcher@t", "delivered", kind="prove",
               agenda="paper:lem:d", result="proved")
        ticket(b, "T-0003", "expert@t", "open", kind="cite")
        ticket(b, "T-0004", "expert@t", "rejected", kind="verify")
        ticket(b, "T-0005", "author@t", "closed", kind="build")
        ticket(b, "T-0006", "author@t", "accepted", kind="question", priority="high")
        ticket(b, "T-0007", "author@t", "open", kind="write", agenda="paper:lem:b")
        ticket(b, "T-0008", "author@t", "open", kind="apply", agenda="paper:lem:d")
        ticket(b, "T-0009", "author@t", "blocked", kind="write", waiting_on=["T-0002"],
               agenda="paper:prop:a")
        ticket(b, "T-0010", "author@t", "blocked", kind="write", waiting_on=["T-0003"])
        ticket(b, "T-0011", "author@t", "blocked", kind="apply", waiting_on=["human"])
        ticket(b, "T-0012", "expert@t", "delivered", kind="verify", agenda="paper:lem:b",
               result="CONFIRMED", priority="high")
        ticket(b, "T-0013", "author@t", "delivered", kind="write", frm="author@t",
               result="done")      # a delivered self-ticket: not a landing

    def test_returned_tickets_are_the_delivered_ones_this_author_filed_elsewhere(self):
        p = nx.plan(self.ctx())
        # T-0012 unblocks position 1 (lem:b under thm:main), T-0002 position 5
        self.assertEqual([r["ticket"] for r in p["land"]], ["T-0012", "T-0002"])

    def test_released_are_blocked_on_tickets_that_are_all_back(self):
        p = nx.plan(self.ctx())
        self.assertEqual([r["ticket"] for r in p["release"]], ["T-0009"])   # not T-0010/11

    def test_land_routes_by_kind(self):
        rows = {r["id"]: r for r in nx.land_rows(self.ctx(), nx.plan(self.ctx()))}
        self.assertEqual((rows["T-0002"]["route"]["target"], rows["T-0002"]["return"]),
                         ("math-writer", True))
        self.assertEqual(rows["T-0012"]["route"]["target"], "math-editor")

    def test_inbox_takes_in_progress_then_landings_then_position_and_caps_at_three(self):
        code, out, err = self.run_cli("--json", "--n", "9")
        self.assertEqual(code, 0, err)
        d = json.loads(out)
        ids = [r["id"] for r in d["take"]]
        self.assertEqual(len(ids), 3)
        self.assertEqual(ids, ["T-0012", "T-0002", "T-0009"])   # landings, then the release
        self.assertEqual(d["limit"], 3)
        self.assertGreater(d["remaining"], 0)
        self.assertEqual((d["land"], d["released"]), (2, 1))
        rows = {r["id"]: r for r in d["take"]}
        self.assertTrue(rows["T-0012"]["return"] and rows["T-0009"]["released"])
        self.assertIn("blocked -> accepted", rows["T-0009"]["route"]["why"])

    def test_open_tickets_follow_by_agenda_position_then_priority(self):
        b = self.sb.board
        for t in ("T-0002", "T-0012", "T-0009"):         # settle the landings and the release
            os.remove([os.path.join(b, d, f) for d in os.listdir(b)
                       for f in os.listdir(os.path.join(b, d)) if f.startswith(t)][0])
        code, out, err = self.run_cli("--json")
        ids = [r["id"] for r in json.loads(out)["take"]]
        # T-0001 (thm:main, pos 1), T-0007 (lem:b unblocks thm:main, pos 1), T-0008 (pos 5);
        # T-0006 has no agenda entry and sorts last
        self.assertEqual(ids, ["T-0001", "T-0007", "T-0008"])
        code, out, err = self.run_cli("--all", "--json")
        all_ids = [r["id"] for r in json.loads(out)["take"]]
        self.assertLess(all_ids.index("T-0008"), all_ids.index("T-0006"))

    def test_sweep_comes_first_except_in_all(self):
        code, out, err = self.run_cli("--json")
        self.assertEqual(json.loads(out)["sweep"]["target"], "note-sweeper")
        code, out, err = self.run_cli()
        self.assertTrue(out.startswith("SWEEP FIRST"), out)
        code, out, err = self.run_cli("--all", "--json")
        d = json.loads(out)
        self.assertNotIn("sweep", d)
        ids = [r["id"] for r in d["take"]]
        self.assertEqual(ids.count("T-0009"), 1)            # the blocked pool, not twice
        self.assertIn("T-0010", ids)                        # blocked pending: listed by --all

    def test_every_entry_has_a_ticket_so_no_gap_is_reported(self):
        code, out, err = self.run_cli("--json")
        self.assertEqual(json.loads(out)["gaps"], 0)

    def test_items_per_run_is_capped_at_three(self):
        self.assertEqual(self.ctx(items=1).items_per_run, 1)
        self.assertEqual(self.ctx(items=9).items_per_run, 3)
        code, out, err = self.run_cli("--json", "--n", "1")
        self.assertEqual(len(json.loads(out)["take"]), 1)

    def test_check_reports_an_unfinished_ticket(self):
        code, out, err = self.run_cli("--check", "T-0006")
        self.assertEqual(code, 3, err)
        self.assertIn("unfinished", out)
        code, out, err = self.run_cli("--check", "T-0002")
        self.assertEqual(code, 0)

    def test_the_old_filing_and_item_commands_are_gone(self):
        for cmd in ("sync", "file", "mark", "add"):
            code, out, err = self.run_cli(cmd)
            self.assertEqual(code, 2, cmd)                  # not a subcommand any more
        code, out, err = self.run_cli("--sync")
        self.assertEqual(code, 2)


class GapHeaderTests(InboxBase):
    def test_the_header_counts_agenda_gaps_without_a_ticket(self):
        code, out, err = self.run_cli("--json")
        self.assertEqual(code, 1)                           # an empty inbox
        self.assertEqual(json.loads(out)["gaps"], 3)        # thm:main, lem:b, lem:d
        code, out, err = self.run_cli()
        self.assertIn("3 agenda gap(s) have no ticket", out)


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

    def test_land_routes_by_ticket_kind(self):
        self.assertEqual(routes.land_route("verify")["target"], "math-editor")
        self.assertEqual(routes.land_route("cite")["target"], "math-editor")
        self.assertEqual(routes.land_route("research", "researcher")["target"], "math-writer")
        self.assertEqual(routes.land_route("research", "scientist")["target"], "math-writer")
        self.assertEqual(routes.land_route("referee")["target"], "author:notes")

    def test_every_self_kind_is_a_ticket_kind_and_routes(self):
        for kind in routes.SELF_KINDS:
            self.assertIn(kind, ac.TICKET_KINDS)
            self.assertEqual(routes.route({"kind": kind})["how"], "agent")

    def test_every_out_route_is_a_ticket_kind_with_a_deliverable(self):
        for tag, (role, kind, final_to, dkey) in routes.OUT_ROUTES.items():
            self.assertIn(kind, ac.TICKET_KINDS)
            self.assertIn(dkey, routes.DELIVERABLES)


class NoRoadmapTests(InboxBase):
    """No code path reads or writes a roadmap; an old file and an old config are inert."""

    JUNK = "# Roadmap\n\n## R-0001 [apply] old\n- status: open\n- agenda: lem:d\n\nbody\n"

    def test_no_script_but_the_converter_knows_the_roadmap(self):
        pat = re.compile(r"roadmap\.md|parse_roadmap|write_roadmap|\bRoadmap\b|R-\\d|R-NNNN")
        for name in sorted(os.listdir(SCRIPTS)):
            if not name.endswith(".py") or name in ("agenda_migrate.py", "_academy.py"):
                continue
            with open(os.path.join(SCRIPTS, name), encoding="utf-8") as fh:
                self.assertIsNone(pat.search(fh.read()), name)
        hooks = os.path.join(os.path.dirname(SCRIPTS), "hooks", "hooks.json")
        with open(hooks, encoding="utf-8") as fh:
            self.assertNotIn("roadmap", fh.read().lower())

    def test_running_the_tools_never_touches_or_reads_a_roadmap_file(self):
        rm = os.path.join(self.sb.home, "Drafts", "roadmap.md")
        self.sb.write(rm, self.JUNK)
        before = sha(rm)
        ticket(self.sb.board, "T-0001", "author@t", "open", kind="write",
               agenda="paper:lem:b")
        with_file = self.run_cli("--json")[1]
        os.remove(rm)
        self.assertEqual(self.run_cli("--json")[1], with_file)         # same without it
        self.sb.write(rm, self.JUNK)
        agenda_cli = [sys.executable, os.path.join(SCRIPTS, "agenda.py")]
        for cmd in (["check"], ["status", "--statuses", os.devnull], ["gaps"],
                    ["gaps", "--file"], ["milestones"], ["show"]):
            subprocess.run(agenda_cli + cmd + ["--home", self.sb.home], capture_output=True,
                           env=self.sb.env)
        self.assertEqual(sha(rm), before)
        self.assertEqual(self.run_cli("--json", "--roadmap", rm)[0], 2)  # no such option

    def test_an_old_config_with_a_roadmap_path_still_validates_and_runs(self):
        cfg = json.loads(self.sb.read(os.path.join(self.sb.home, ".claude", "academy.json")))
        self.assertNotIn("roadmap", cfg["paths"])
        cfg["paths"]["roadmap"] = "Drafts/roadmap.md"
        self.sb.write(os.path.join(self.sb.home, ".claude", "academy.json"),
                      json.dumps(cfg, indent=2))
        self.assertEqual(ac.validate_config(ac.load_config(self.sb.home)), [])
        code, out, err = self.run_cli("--json")
        self.assertIn(code, (0, 1), err)
        self.assertIn("sweep", json.loads(out))


if __name__ == "__main__":
    unittest.main()
