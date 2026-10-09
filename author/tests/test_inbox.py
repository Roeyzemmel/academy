"""inbox.py: the board is the only queue; tickets are routed, returned ones landed,
released ones offered again, the sweep comes first. Nothing reads or writes a roadmap."""

import hashlib
import json
import os
import subprocess
import sys
import unittest

from fixtures import REPO, SCRIPTS, Sandbox

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
           result="", waiting_on=None, final_to=None, body="", campaign=None, extra=""):
    wo = ("waiting_on: [%s]\n" % ", ".join(waiting_on)) if waiting_on else ""
    ft = ("final_to: %s\n" % final_to) if final_to else ""
    ft += ("campaign: %s\n" % campaign) if campaign else ""
    ft += extra
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

    def test_check_of_a_finished_ticket_runs_the_ship_checkpoint_as_author(self):
        # the workspace's scripts/ship.py (a stub logging its arguments); T-0002 is a
        # landing (to researcher@t, filed by this Author): the work is the Author's
        # (the sandbox root is the workspace: the home 'paper' and 'board' are submodules,
        # and the session runs inside it)
        log = os.path.join(self.sb.root, "scripts", "calls.log")
        self.sb.write(os.path.join(self.sb.root, "scripts", "ship.py"),
                      "import sys\nopen(%r, 'a').write(' '.join(sys.argv[1:]) + '\\n')\n"
                      % log)
        self.sb.write(os.path.join(self.sb.root, ".gitmodules"),
                      "".join('[submodule "%s"]\n\tpath = %s\n\turl = x\n' % (s, s)
                              for s in ("paper", "board", "lab")))
        self.sb.env["CLAUDE_PROJECT_DIR"] = self.sb.root
        code, out, err = self.run_cli("--check", "T-0002")
        self.assertEqual(code, 0, err)
        with open(log) as fh:
            self.assertEqual(fh.read().splitlines(),
                             ["checkpoint --ticket T-0002 --role author --only paper board"])

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

    def test_another_roles_kind_is_rejected_with_the_route_to_ask(self):
        for kind, role in (("prove", "researcher"), ("experiment", "scientist")):
            r = routes.route({"kind": kind})
            self.assertEqual("reject", r["how"], kind)
            self.assertIn("final_to %s" % role, r["why"])

    def test_a_write_ticket_needing_an_argument_goes_to_research(self):
        r = routes.route({"kind": "write", "title": "Lemma 3",
                          "ask": "fill the gap in step 2 with a new argument"})
        self.assertEqual(("research", "expert"), (r["how"], r["target"]))
        r = routes.route({"kind": "write", "ask": "write up the delivered proof of lem:x"})
        self.assertEqual(("agent", "math-writer"), (r["how"], r["target"]))

    def test_writers_file_research_tickets_for_missing_arguments(self):
        good = {"kind": "research", "to": "expert@t", "final_to": "researcher",
                "title": "Prove lem:x", "ask": "a missing argument in step 2"}
        self.assertEqual([], routes.check_filed(good))
        for bad in (dict(good, kind="write", to="author@t", final_to=None),
                    dict(good, kind="prove"),
                    dict(good, final_to=None),
                    dict(good, to="researcher@t")):
            self.assertTrue(routes.check_filed(bad), bad)
        # asks that need no argument pass untouched
        self.assertEqual([], routes.check_filed({"kind": "verify", "to": "expert@t",
                                                 "title": "Verify lem:x", "ask": "verify"}))
        self.assertEqual([], routes.check_filed({"kind": "research", "to": "expert@t",
                                                 "final_to": "scientist", "ask": "run"}))
        # every ask the gap filer drafts passes the check
        for tag, (role, kind, ft, _d) in routes.OUT_ROUTES.items():
            meta = {"kind": kind, "to": role + "@t", "final_to": ft,
                    "title": "Prove x" if tag == "lead" else tag, "ask": tag}
            self.assertEqual([], routes.check_filed(meta), tag)

    def test_land_routes_by_ticket_kind(self):
        self.assertEqual(routes.land_route("verify")["target"], "math-editor")
        self.assertEqual(routes.land_route("cite")["target"], "math-editor")
        self.assertEqual(routes.land_route("research")["target"], "math-writer")
        self.assertEqual(routes.land_route("prove")["target"], "math-writer")
        self.assertEqual(routes.land_route("experiment")["target"], "math-writer")
        self.assertEqual(routes.land_route("something-new")["target"], "math-editor")
        with self.assertRaises(TypeError):                   # no ignored relay argument
            routes.land_route("research", "researcher")
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

    def test_no_tool_opens_a_roadmap_file_in_a_home_that_has_one(self):
        import builtins
        import contextlib
        import io
        import agenda as ag
        rm = os.path.join(self.sb.home, "Drafts", "roadmap.md")
        self.sb.write(rm, self.JUNK)
        before = sha(rm)
        ticket(self.sb.board, "T-0001", "author@t", "open", kind="write",
               agenda="paper:lem:b")
        statuses = os.path.join(self.sb.root, "st.json")
        self.sb.write(statuses, "{}")
        home = ["--home", self.sb.home]
        runs = [(nx.main, ["--json"] + home), (nx.main, ["--all"] + home),
                (nx.main, ["--check", "T-0001"] + home),
                (ag.main, ["check"] + home), (ag.main, ["gaps"] + home),
                (ag.main, ["gaps", "--file"] + home), (ag.main, ["milestones"] + home),
                (ag.main, ["show"] + home), (ag.main, ["status", "--statuses", statuses] + home)]
        real, opened = builtins.open, []

        def spy(file, *a, **k):
            if "roadmap" in os.path.basename(str(file)).lower():
                opened.append(str(file))
            return real(file, *a, **k)

        builtins.open = spy
        try:
            for fn, argv in runs:
                with contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    fn(argv)
        finally:
            builtins.open = real
        self.assertEqual(opened, [])                          # never even read
        self.assertEqual(sha(rm), before)

    def test_the_hook_config_does_not_mention_a_roadmap(self):
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


class CampaignTests(InboxBase):
    """--campaign lists only the campaign's tickets: landings and released rows included."""

    def setUp(self):
        InboxBase.setUp(self)
        b = self.sb.board
        ticket(b, "T-0001", "author@t", "open", kind="write", agenda="paper:lem:b",
               campaign="paper:thm:main")
        ticket(b, "T-0002", "author@t", "open", kind="write", agenda="paper:lem:b")
        ticket(b, "T-0003", "researcher@t", "delivered", kind="prove", result="proved",
               campaign="paper:thm:main")
        ticket(b, "T-0004", "expert@t", "delivered", kind="verify", result="CONFIRMED")
        ticket(b, "T-0005", "author@t", "blocked", kind="write", waiting_on=["T-0003"],
               campaign="paper:thm:main")
        ticket(b, "T-0006", "author@t", "blocked", kind="write", waiting_on=["T-0004"])

    def ids(self, *args):
        code, out, err = self.run_cli("--json", *args)
        self.assertIn(code, (0, 1), err)
        return json.loads(out)

    def test_without_a_campaign_everything_is_listed(self):
        d = self.ids("--all")
        self.assertEqual({r["id"] for r in d["take"]},
                         {"T-0001", "T-0002", "T-0003", "T-0004", "T-0005", "T-0006"})

    def test_a_campaign_filters_landing_and_released_rows_too(self):
        d = self.ids("--campaign", "paper:thm:main")
        self.assertEqual({r["id"] for r in d["take"]}, {"T-0001", "T-0003", "T-0005"})
        rows = {r["id"]: r for r in d["take"]}
        self.assertTrue(rows["T-0003"]["return"])
        self.assertTrue(rows["T-0005"]["released"])
        self.assertEqual({r["campaign"] for r in d["take"]}, {"paper:thm:main"})
        self.assertEqual((d["land"], d["released"]), (1, 1))   # the header counts the same
        d = self.ids("--campaign", "paper:other")
        self.assertEqual(d["take"], [])
        self.assertEqual((d["land"], d["released"]), (0, 0))

    def test_the_campaign_text_listing_has_no_foreign_row(self):
        code, out, err = self.run_cli("--campaign", "paper:thm:main")
        for tid in ("T-0002", "T-0004", "T-0006"):
            self.assertNotIn(tid, out)


class ReleasedTests(InboxBase):
    def setUp(self):
        InboxBase.setUp(self)
        b = self.sb.board
        ticket(b, "T-0001", "expert@t", "delivered", kind="verify", frm="author@t",
               result="CONFIRMED")
        ticket(b, "T-0002", "expert@t", "rejected", kind="verify")
        ticket(b, "T-0003", "expert@t", "cancelled", kind="cite")
        ticket(b, "T-0004", "author@t", "blocked", kind="write", waiting_on=["T-0001"])
        ticket(b, "T-0005", "author@t", "blocked", kind="write", waiting_on=["T-0001", "T-0002"])
        ticket(b, "T-0006", "author@t", "blocked", kind="write", waiting_on=["T-0003"])
        ticket(b, "T-0007", "author@t", "blocked", kind="write", waiting_on=["T-0099"])
        ticket(b, "T-0008", "author@t", "blocked", kind="write", waiting_on=["T-0001"],
               extra="blocked_by: T-0001\nreopen_if: a proof appears\n")   # a dead route
        ticket(b, "T-0009", "author@t", "blocked", kind="write", waiting_on=["human"])

    def test_only_a_ticket_whose_waits_are_all_back_is_released(self):
        p = nx.plan(self.ctx())
        self.assertEqual([r["ticket"] for r in p["release"]], ["T-0004"])

    def test_a_wait_on_a_rejected_or_cancelled_ticket_is_a_note_not_a_release(self):
        p = nx.plan(self.ctx())
        notes = "\n".join(p["notes"])
        self.assertIn("T-0005 waits on T-0002, which was rejected", notes)
        self.assertIn("T-0006 waits on T-0003, which was cancelled", notes)
        self.assertNotIn("T-0004", notes)

    def test_a_wait_on_a_ticket_that_is_not_on_the_board_is_a_note(self):
        p = nx.plan(self.ctx())
        self.assertIn("T-0007 waits on T-0099, which is not on the board", p["notes"])

    def test_a_dead_route_and_a_human_wait_are_neither_released_nor_noted(self):
        p = nx.plan(self.ctx())
        self.assertNotIn("T-0008", [r["ticket"] for r in p["release"]])
        self.assertNotIn("T-0009", [r["ticket"] for r in p["release"]])
        self.assertFalse([n for n in p["notes"] if n.startswith(("T-0008", "T-0009"))])

    def test_notes_are_printed_in_the_text_output_with_and_without_all(self):
        for args in ([], ["--all"]):
            code, out, err = self.run_cli(*args)
            self.assertIn("NOTES", out)
            self.assertIn("T-0005 waits on T-0002, which was rejected", out)
        code, out, err = self.run_cli("--all", "--json")
        self.assertIn("T-0007 waits on T-0099, which is not on the board",
                      json.loads(out)["notes"])

    def test_the_released_rows_use_the_shared_rule(self):
        self.assertIs(nx.ac.released_waits, ac.released_waits)
        self.assertEqual(nx.core.MAX, 3)
        for gone in ("_released", "_num", "MAX_ITEMS", "TICKET_DEAD"):
            self.assertFalse(hasattr(nx, gone), gone)


class EmptyAndNotesTests(InboxBase):
    def test_an_empty_board(self):
        code, out, err = self.run_cli()
        self.assertEqual(code, 1, err)
        self.assertIn("(inbox of author@t is empty)", out)
        code, out, err = self.run_cli("--json")
        d = json.loads(out)
        self.assertEqual((code, d["take"], d["land"], d["released"]), (1, [], 0, 0))

    def test_a_ticket_on_an_unknown_entry_is_a_note_and_sorts_last(self):
        ticket(self.sb.board, "T-0001", "expert@t", "delivered", kind="verify", result="ok",
               agenda="paper:nonexistent")
        code, out, err = self.run_cli("--all")
        self.assertIn("T-0001: agenda entry paper:nonexistent not found", out)


class GithubParityTests(InboxBase):
    """The Author inbox gives identical rows on a file board and on a github one."""

    def setUp(self):
        InboxBase.setUp(self)
        b = self.sb.board
        ticket(b, "T-0001", "author@t", "open", kind="figure", frm="human",
               agenda="paper:thm:main")
        ticket(b, "T-0002", "researcher@t", "delivered", kind="prove", agenda="paper:lem:d",
               result="proved", campaign="paper:lem:d")
        ticket(b, "T-0003", "expert@t", "delivered", kind="verify", agenda="paper:lem:b",
               result="CONFIRMED", priority="high")
        ticket(b, "T-0004", "author@t", "blocked", kind="write", waiting_on=["T-0002"],
               agenda="paper:prop:a")
        ticket(b, "T-0005", "author@t", "blocked", kind="write", waiting_on=["T-0006"])
        ticket(b, "T-0006", "expert@t", "rejected", kind="cite")
        ticket(b, "T-0007", "author@t", "accepted", kind="question", priority="high")
        ticket(b, "T-0008", "author@t", "in-progress", kind="apply", agenda="paper:lem:d")
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        ws["board"] = {"path": self.sb.board, "backend": "github", "repo": "o/r",
                       "transport": "_gh_seed:factory"}
        self.gh_ws = os.path.join(self.sb.root, "ws-github.json")
        self.sb.write(self.gh_ws, json.dumps(ws))

    def run_on(self, workspace, *args):
        tests = os.path.join(REPO, "academy", "tests")
        env = dict(self.sb.env, ACADEMY_TEST_SEED=self.sb.board,
                   PYTHONPATH=os.pathsep.join([tests] + ([os.environ["PYTHONPATH"]]
                                                         if os.environ.get("PYTHONPATH")
                                                         else [])))
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "inbox.py"), "--home",
                              self.sb.home, "--workspace", workspace] + list(args),
                             capture_output=True, env=env)
        return res.returncode, res.stdout.decode("utf-8"), res.stderr.decode("utf-8")

    @staticmethod
    def rows(doc):
        for r in doc["take"]:
            r.pop("path", None)
        return doc

    def test_rows_notes_and_headers_are_identical(self):
        for args in (["--json", "--n", "9"], ["--json", "--all"],
                     ["--json", "--campaign", "paper:lem:d"]):
            with self.subTest(args=args):
                a = self.run_on(self.sb.workspace, *args)
                b = self.run_on(self.gh_ws, *args)
                self.assertIn(a[0], (0, 1), a[2])
                self.assertEqual(a[0], b[0], b[2])
                da, db = self.rows(json.loads(a[1])), self.rows(json.loads(b[1]))
                self.assertTrue(da["take"])                   # not the silent empty inbox
                self.assertEqual(da, db)

    def test_landing_and_released_rows_appear_on_github(self):
        code, out, err = self.run_on(self.gh_ws, "--json", "--n", "9")
        d = json.loads(out)
        rows = {r["id"]: r for r in d["take"]}
        self.assertTrue(rows["T-0003"]["return"] and rows["T-0002"]["return"])
        self.assertTrue(any(n.startswith("T-0005 waits on T-0006, which was rejected")
                            for n in d["notes"]), d["notes"])
        self.assertEqual(d["unfinished"], ["T-0008"])
        self.assertEqual(d["released"], 1)                   # T-0004, cut by the limit of 3
        code, out, err = self.run_on(self.gh_ws, "--json", "--n", "9", "--campaign",
                                     "paper:lem:d")
        self.assertEqual([r["id"] for r in json.loads(out)["take"]], ["T-0002"])

    def test_check_reads_the_github_board(self):
        self.assertEqual(self.run_on(self.gh_ws, "--check", "T-0007")[0], 3)
        self.assertEqual(self.run_on(self.gh_ws, "--check", "T-0002")[0], 0)

    def test_an_unopenable_github_board_is_an_error_never_a_file_board(self):
        with open(self.gh_ws, encoding="utf-8") as fh:
            ws = json.load(fh)
        del ws["board"]["transport"]
        bad = os.path.join(self.sb.root, "ws-bad.json")
        self.sb.write(bad, json.dumps(ws))
        code, out, err = self.run_on(bad, "--json")
        self.assertEqual(code, 2)
        self.assertIn("transport", err)


if __name__ == "__main__":
    unittest.main()
