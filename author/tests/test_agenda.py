"""agenda_lib (the agenda.md format) and agenda.py (check, status, gaps, gap filing,
milestones). The board is the only queue: gaps become tickets."""

import json
import os
import subprocess
import sys
import unittest

from fixtures import SCRIPTS, Sandbox
from test_inbox import AGENDA, ticket

sys.path.insert(0, SCRIPTS)
import agenda as ag  # noqa: E402
import agenda_lib as al  # noqa: E402
import gaps as gp  # noqa: E402
import inbox as nx  # noqa: E402
import _academy as ac  # noqa: E402


class FormatTests(unittest.TestCase):
    def test_agenda_round_trip(self):
        ag = al.parse_agenda(AGENDA)
        self.assertEqual([e.label for e in ag.entries],
                         ["thm:main", "prop:a", "lem:b", "defn:c", "lem:d"])
        self.assertEqual(ag.entries[0].depends_on, ["lem:b"])
        self.assertEqual(ag.milestones, {"round-1": {"thm:main": "proved", "prop:a": "sketch"}})
        self.assertEqual(al.write_agenda(ag), AGENDA)
        self.assertEqual(al.write_agenda(al.parse_agenda(al.write_agenda(ag))), AGENDA)

    def test_agenda_lookup_and_unblock(self):
        ag = al.parse_agenda(AGENDA)
        self.assertIs(ag.lookup("paper:lem:b", "paper"), ag.lookup("lem:b", "paper"))
        self.assertEqual(ag.unblock_position("lem:b"), 1)
        self.assertEqual(ag.unblock_position("defn:c"), 1)    # via lem:b -> thm:main
        self.assertEqual(ag.unblock_position("lem:d"), 5)
        self.assertIsNone(ag.unblock_position("nope"))

    def test_satisfied(self):
        self.assertTrue(al.satisfied("proved", "sketch"))
        self.assertTrue(al.satisfied("supported", "sketch"))
        self.assertFalse(al.satisfied("sketch", "proved-modulo"))
        self.assertFalse(al.satisfied("refuted", "open"))
        self.assertTrue(al.satisfied("refuted", "refuted"))
        self.assertFalse(al.satisfied("missing", "open"))
        self.assertFalse(al.satisfied("", "open"))

    def test_check(self):
        ag = al.parse_agenda(AGENDA)
        self.assertEqual(al.check(ag, "paper"), [])
        bad_ag = al.parse_agenda(AGENDA.replace("| 4 | defn:c | paper:defn:c | proved | - |",
                                                "| 4 | defn:c | paper:defn:c | proved | thm:main |"))
        probs = al.check(bad_ag, "paper")
        self.assertTrue(any("cycle" in p for p in probs), probs)

    def test_new_files(self):
        entries = [al.Entry("thm:a", "paper:thm:a", "proved", [], "author@t", "sketch")]
        text = al.new_agenda_text("author@t", entries, {"sub": {"thm:a": "proved"}})
        ag = al.parse_agenda(text)
        self.assertEqual(ag.entries[0].label, "thm:a")
        self.assertEqual(ag.milestones, {"sub": {"thm:a": "proved"}})

    def test_the_library_has_no_roadmap_format(self):
        for name in ("Item", "Roadmap", "parse_roadmap", "write_roadmap", "new_roadmap_text",
                     "TAGS", "ITEM_STATUSES", "RE_ITEM_ID"):
            self.assertFalse(hasattr(al, name), name)


class AgendaCliTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.agenda = os.path.join(self.sb.home, "Drafts", "agenda.md")
        self.sb.write(self.agenda, AGENDA)

    def tearDown(self):
        self.sb.cleanup()

    def run_cli(self, *args):
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "agenda.py")] + list(args)
                             + ["--home", self.sb.home], capture_output=True, env=self.sb.env)
        return res.returncode, res.stdout.decode("utf-8"), res.stderr.decode("utf-8")

    def board_files(self, folder):
        d = os.path.join(self.sb.board, folder)
        return sorted(f for f in os.listdir(d) if f.startswith("T-"))

    def meta(self, folder, name):
        return ac.read_frontmatter(self.sb.read(os.path.join(self.sb.board, folder, name)))

    def test_check_clean(self):
        code, out, err = self.run_cli("check")
        self.assertEqual(code, 0, out + err)

    def test_status_refresh_from_file(self):
        st = os.path.join(self.sb.root, "st.json")
        self.sb.write(st, json.dumps({"paper:thm:main": "proved", "paper:lem:b": "proved"}))
        code, out, err = self.run_cli("status", "--statuses", st)
        self.assertEqual(code, 0, err)
        ag = al.parse_agenda(self.sb.read(self.agenda))
        got = {e.label: e.status for e in ag.entries}
        self.assertEqual(got["thm:main"], "proved")
        self.assertEqual(got["prop:a"], "missing")      # the registry does not know it
        self.assertIn("thm:main: sketch -> proved", out)

    def test_status_without_registry_is_an_error(self):
        code, _out, err = self.run_cli("status")
        self.assertEqual(code, 2)
        self.assertIn("claims_list", err)

    def test_gaps_are_the_entries_with_no_ticket(self):
        code, out, _err = self.run_cli("gaps", "--json")
        self.assertEqual(code, 0)
        gaps = {g["label"]: g for g in json.loads(out)}
        self.assertEqual(set(gaps), {"thm:main", "lem:b", "lem:d"})
        self.assertEqual(gaps["lem:b"]["proposed_tag"], "verify")
        self.assertEqual(gaps["lem:d"]["proposed_tag"], "lead")
        self.assertEqual(gaps["thm:main"]["waits_for"], ["lem:b"])   # its input is unproved
        self.assertEqual(gaps["lem:b"]["waits_for"], [])
        # a ticket on lem:d (any non-terminal one, to or from this Author) covers it
        ticket(self.sb.board, "T-0001", "author@t", "open", kind="write",
               agenda="paper:lem:d")
        ticket(self.sb.board, "T-0002", "expert@t", "closed", kind="verify",
               agenda="paper:lem:b")                     # closed: no longer covers lem:b
        code, out, _err = self.run_cli("gaps", "--json")
        self.assertEqual({g["label"] for g in json.loads(out)}, {"thm:main", "lem:b"})

    def test_gaps_file_files_one_ticket_per_gap_and_holds_a_verify_on_unproved_inputs(self):
        code, out, err = self.run_cli("gaps", "--file", "--json")
        self.assertEqual(code, 0, err)
        res = json.loads(out)
        self.assertEqual([(r["label"], r["to"], r["kind"]) for r in res["filed"]],
                         [("lem:b", "expert@t", "verify"),
                          ("lem:d", "expert@t", "research")])
        self.assertEqual([h["label"] for h in res["held"]], ["thm:main"])
        self.assertIn("lem:b", res["held"][0]["why"])
        files = self.board_files("expert@t")
        self.assertEqual(len(files), 2)
        for f in files:
            meta, body = self.meta("expert@t", f)
            self.assertEqual(meta["from"], "author@t")
            self.assertEqual(ac.validate_ticket(meta), [])
            if meta["kind"] == "verify":
                self.assertEqual((meta["agenda"], meta["refs"]),
                                 ("paper:lem:b", ["paper:lem:b"]))
            else:
                self.assertEqual((meta["agenda"], meta["refs"], meta["final_to"]),
                                 ("paper:lem:d", ["paper:lem:d"], "researcher"))

    def test_the_same_gap_twice_is_one_ticket(self):
        self.assertEqual(self.run_cli("gaps", "--file")[0], 0)
        before = {f: self.board_files(f) for f in ("author@t", "expert@t")}
        code, out, _err = self.run_cli("gaps", "--file")
        self.assertEqual(code, 1, out)                   # nothing new to file
        self.assertEqual({f: self.board_files(f) for f in ("author@t", "expert@t")}, before)
        # and in one process, through the library
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        os.environ["ACADEMY_WORKSPACE"] = self.sb.workspace
        try:
            ctx = nx.Context(self.agenda, self.sb.board, ws, "author@t", "paper", 3, ["dom"])
            self.assertEqual(gp.file_gaps(ctx)["filed"], [])
            self.assertEqual(gp.file_gaps(ctx)["filed"], [])
        finally:
            os.environ.pop("ACADEMY_WORKSPACE", None)
        self.assertEqual({f: self.board_files(f) for f in ("author@t", "expert@t")}, before)

    def test_dry_run_files_nothing(self):
        code, out, _err = self.run_cli("gaps", "--file", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("2 ticket(s) to file", out)
        self.assertEqual(self.board_files("expert@t"), [])
        self.assertEqual(self.board_files("author@t"), [])

    def test_a_missing_record_is_held_for_roey_not_ticketed(self):
        # claim records are made by claims_new / the claim-keeper, not by the math-editor
        self.sb.write(self.agenda, AGENDA.replace("| proved | - | author@t | open |",
                                                  "| proved | - | author@t | missing |"))
        code, out, err = self.run_cli("gaps", "--file", "--json")
        res = json.loads(out)
        self.assertEqual([r["label"] for r in res["filed"]], ["lem:b"])   # not lem:d
        held = {h["label"]: h["why"] for h in res["held"]}
        self.assertIn("claims_new", held["lem:d"])
        self.assertEqual(self.board_files("author@t"), [])                # no self-ticket
        code, out, _err = self.run_cli("gaps", "--json")
        self.assertEqual({g["label"]: g["proposed_tag"] for g in json.loads(out)}["lem:d"],
                         "hold")

    def test_a_refuted_claim_gets_no_ticket_but_is_reported(self):
        for st in ("refuted", "refuted-as-stated"):
            with self.subTest(status=st):
                self.sb.write(self.agenda, AGENDA.replace(
                    "| proved | - | author@t | open |", "| proved | - | author@t | %s |" % st))
                code, out, err = self.run_cli("gaps", "--file", "--dry-run", "--json")
                res = json.loads(out)
                self.assertNotIn("lem:d", [r["label"] for r in res["filed"]])
                held = {h["label"]: h["why"] for h in res["held"]}
                self.assertIn("refuted", held["lem:d"])

    def test_proved_modulo_needs_a_lead_and_a_sketch_a_verify(self):
        ctx = self.ctx_of(AGENDA.replace("| proved | - | author@t | open |",
                                         "| proved | - | author@t | proved-modulo |"))
        g = {x["label"]: x for x in gp.gaps(ctx)}
        self.assertEqual(g["lem:d"]["proposed_tag"], "lead")
        self.assertEqual(g["lem:b"]["proposed_tag"], "verify")

    def ctx_of(self, agenda_text, instance="author@t", domains=("dom",), ws=None):
        self.sb.write(self.agenda, agenda_text)
        with open(self.sb.workspace, encoding="utf-8") as fh:
            w = ws or json.load(fh)
        return nx.Context(self.agenda, self.sb.board, w, instance, "paper", 3, list(domains))

    def test_a_receiver_choice_with_several_or_no_candidate_instances(self):
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        ws["instances"]["expert@u"] = dict(ws["instances"]["expert@t"])
        ctx = self.ctx_of(AGENDA, ws=ws)
        to, note = gp.target_instance(ctx, "expert")
        self.assertEqual(to, "expert@t")                    # the first by name, said aloud
        self.assertIn("several expert instances", note)
        ws["instances"]["expert@t"]["domains"] = ["other"]
        ws["instances"]["expert@u"]["domains"] = ["other"]
        ctx = self.ctx_of(AGENDA, ws=ws)
        self.assertEqual(gp.target_instance(ctx, "expert")[0], None)
        res = gp.file_gaps(ctx, dry_run=True)
        self.assertEqual(res["filed"], [])
        held = {h["label"]: h["why"] for h in res["held"]}
        self.assertIn("no expert instance", held["lem:b"])
        self.assertIn("no expert instance", held["lem:d"])

    def test_gaps_file_exits_1_when_nothing_was_filed(self):
        self.assertEqual(self.run_cli("gaps", "--file")[0], 0)
        self.assertEqual(self.run_cli("gaps", "--file")[0], 1)

    def test_gaps_file_carries_a_campaign(self):
        code, out, err = self.run_cli("gaps", "--file", "--campaign", "paper:thm:main")
        self.assertEqual(code, 0, err)
        metas = [self.meta("expert@t", f)[0] for f in self.board_files("expert@t")]
        self.assertEqual(len(metas), 2)
        self.assertTrue(all(m.get("campaign") == "paper:thm:main" for m in metas), metas)
        code, out, err = self.run_cli("gaps", "--file", "--campaign", "x:y")
        self.assertEqual(code, 1)                           # nothing new; the flag is accepted

    def test_two_entries_sharing_a_claim_are_each_ticketed_once(self):
        two = AGENDA.replace(
            "| 5 | lem:d | paper:lem:d | proved | - | author@t | open |",
            "| 5 | lem:d | paper:lem:d | proved | - | author@t | open |\n"
            "| 6 | lem:d2 | paper:lem:d | proved | - | author@t | open |")
        self.sb.write(self.agenda, two)
        self.assertEqual(al.check(al.parse_agenda(two), "paper").count(
            "agenda: lem:d and lem:d2 share the claim paper:lem:d (one entry per claim: a "
            "ticket's agenda names one entry)"), 1)
        code, out, err = self.run_cli("gaps", "--file", "--json")
        first = json.loads(out)
        filed = {r["label"]: r for r in first["filed"]}
        self.assertEqual(set(filed), {"lem:b", "lem:d", "lem:d2"})
        self.assertEqual(filed["lem:d"]["agenda"], "paper:lem:d")
        self.assertEqual(filed["lem:d2"]["agenda"], "paper:lem:d2")      # the label, exact
        before = self.board_files("expert@t")
        self.assertEqual(len(before), 3)
        for _ in range(2):                                  # stable across reruns
            code, out, err = self.run_cli("gaps", "--file", "--json")
            self.assertEqual((code, json.loads(out)["filed"]), (1, []), out)
        self.assertEqual(self.board_files("expert@t"), before)
        code, out, _err = self.run_cli("show", "--json")
        rows = {r["label"]: r["tickets"] for r in json.loads(out)}
        self.assertEqual(len(rows["lem:d"]), 1)
        self.assertEqual(len(rows["lem:d2"]), 1)
        self.assertNotEqual(rows["lem:d"], rows["lem:d2"])

    def test_a_verify_is_filed_once_its_inputs_reach_their_status(self):
        self.sb.write(self.agenda, AGENDA.replace(
            "| 3 | lem:b | paper:lem:b | proved | defn:c | author@t | sketch |",
            "| 3 | lem:b | paper:lem:b | proved | defn:c | author@t | proved |"))
        code, out, err = self.run_cli("gaps", "--file", "--json")
        self.assertEqual(code, 0, err)
        labels = [r["label"] for r in json.loads(out)["filed"]]
        self.assertEqual(labels, ["thm:main", "lem:d"])

    def test_milestones_and_show_carry_the_entry_tickets(self):
        ticket(self.sb.board, "T-0001", "expert@t", "open", kind="verify",
               agenda="paper:thm:main")
        code, out, _err = self.run_cli("milestones", "--json")
        m = json.loads(out)
        self.assertEqual((m["round-1"]["met"], m["round-1"]["of"]), (1, 2))
        rows = {r["label"]: r for r in m["round-1"]["entries"]}
        self.assertEqual(rows["thm:main"]["tickets"], ["T-0001"])
        code, out, _err = self.run_cli("show", "--json")
        self.assertEqual({r["label"]: r["tickets"] for r in json.loads(out)}["thm:main"],
                         ["T-0001"])


class MissingAgendaTests(unittest.TestCase):
    """A configured agenda path that is not a file is an error, never an empty agenda."""

    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.cleanup()

    def run_cli(self, *args):
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "agenda.py")] + list(args)
                             + ["--home", self.sb.home], capture_output=True, env=self.sb.env)
        return res.returncode, res.stdout.decode("utf-8"), res.stderr.decode("utf-8")

    def test_every_agenda_command_fails_loudly(self):
        agenda = os.path.join(self.sb.home, "Drafts", "agenda.md")
        st = os.path.join(self.sb.root, "st.json")
        self.sb.write(st, "{}")
        for cmd in (["check"], ["gaps"], ["gaps", "--file"], ["milestones"], ["show"],
                    ["status", "--statuses", st]):
            with self.subTest(cmd=cmd):
                code, out, err = self.run_cli(*cmd)
                self.assertEqual(code, 2, out)
                self.assertIn("does not exist", err)
                self.assertIn("agenda.md", err)
                self.assertFalse(os.path.exists(agenda), "a bare agenda was created")

    def test_the_inbox_lists_tickets_and_says_the_agenda_is_missing(self):
        ticket(self.sb.board, "T-0001", "author@t", "open", kind="write")
        env = dict(self.sb.env)
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "inbox.py"), "--home",
                              self.sb.home, "--json"], capture_output=True, env=env)
        d = json.loads(res.stdout.decode("utf-8"))
        self.assertEqual([r["id"] for r in d["take"]], ["T-0001"])
        self.assertIsNone(d["gaps"])                        # unknown, not "0 gaps"
        self.assertIn("agenda.md", d["agenda_missing"])
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "inbox.py"), "--home",
                              self.sb.home], capture_output=True, env=env)
        self.assertIn("does not exist", res.stdout.decode("utf-8"))

    def test_a_malformed_agenda_is_an_error_not_zero_gaps(self):
        self.sb.write(os.path.join(self.sb.home, "Drafts", "agenda.md"),
                      "# A\n\n| label | claim |\n|---|---|\n| x | y |\n")
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "inbox.py"), "--home",
                              self.sb.home, "--json"], capture_output=True, env=self.sb.env)
        self.assertEqual(res.returncode, 2)
        self.assertIn("required", res.stderr.decode("utf-8"))


class ModuleShapeTests(unittest.TestCase):
    def run_py(self, code):
        return subprocess.run([sys.executable, "-c", code], capture_output=True, cwd=SCRIPTS,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))

    def test_inbox_does_not_import_agenda_so_there_is_no_cycle(self):
        r = self.run_py("import sys, inbox; assert 'agenda' not in sys.modules; "
                        "import agenda; "
                        "assert agenda.nx is inbox")
        self.assertEqual(r.returncode, 0, r.stderr.decode())

    def test_an_import_failure_is_not_swallowed_as_zero_gaps(self):
        # inbox no longer wraps an import in `except ImportError`: a broken module is loud
        with open(os.path.join(SCRIPTS, "inbox.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("except (al.AgendaError, ImportError)", src)
        self.assertNotIn("import agenda as ag", src)


REGISTRY_SCRIPT = """import sys
assert sys.argv[-2:] == ["sql", "select id, status from claims"], sys.argv
print("id | status")
print("paper:thm:main | proved")
print("paper:lem:b | sketch")
"""


class RegistryCommandTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.script = os.path.join(self.sb.root, "fake registry", "claims.py")
        self.sb.write(self.script, REGISTRY_SCRIPT)

    def tearDown(self):
        self.sb.cleanup()

    def cfg(self, cmd):
        return {"registry": {"legacy": {"claims": cmd}}}

    def test_argv_strips_quotes_and_maps_every_python_launcher(self):
        for cmd, tail in (('py ../lab/claims.py --repo .', ["../lab/claims.py", "--repo", "."]),
                          ('py.exe "C:\\x\\claims.py"', ["C:\\x\\claims.py"]),
                          ('"C:\\Windows\\py.exe" claims.py', ["claims.py"]),
                          ("PYTHON3.EXE claims.py", ["claims.py"]),
                          ("python claims.py", ["claims.py"])):
            with self.subTest(cmd=cmd):
                self.assertEqual(ag.registry_argv(cmd), [sys.executable] + tail)
        self.assertEqual(ag.registry_argv("sage -python claims.py")[0], "sage")
        self.assertEqual(ag.registry_argv("'/opt/x/claims'"), ["/opt/x/claims"])

    def test_success_path_runs_the_command_and_parses_the_rows(self):
        for cmd in ('python3 "%s"' % self.script, 'py.exe "%s"' % self.script,
                    '"%s" "%s"' % (sys.executable, self.script)):
            with self.subTest(cmd=cmd):
                got = ag.registry_statuses(self.sb.home, self.cfg(cmd))
                self.assertEqual(got, {"paper:thm:main": "proved", "paper:lem:b": "sketch"})

    def test_a_failing_command_is_an_error_with_its_message(self):
        bad = os.path.join(self.sb.root, "bad.py")
        self.sb.write(bad, "import sys; sys.stderr.write('boom'); sys.exit(3)")
        with self.assertRaises(nx.InboxError) as cm:
            ag.registry_statuses(self.sb.home, self.cfg('python3 "%s"' % bad))
        self.assertIn("exited 3", str(cm.exception))
        self.assertIn("boom", str(cm.exception))

    def test_status_command_refreshes_from_the_registry_command(self):
        self.sb.write(os.path.join(self.sb.home, "Drafts", "agenda.md"), AGENDA)
        self.sb.write_config(registry={"profile": "paper", "root": "claims", "legacy": {
            "claims": 'python3 "%s"' % self.script}})
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "agenda.py"), "status",
                              "--home", self.sb.home], capture_output=True, env=self.sb.env)
        self.assertEqual(res.returncode, 0, res.stderr.decode())
        got = {e.label: e.status for e in al.parse_agenda(
            self.sb.read(os.path.join(self.sb.home, "Drafts", "agenda.md"))).entries}
        self.assertEqual((got["thm:main"], got["lem:b"], got["prop:a"]),
                         ("proved", "sketch", "missing"))


class SharedFilingTests(unittest.TestCase):
    """The gap filer and the converter create tickets through one helper."""

    def setUp(self):
        self.sb = Sandbox()
        self.agenda = os.path.join(self.sb.home, "Drafts", "agenda.md")
        self.sb.write(self.agenda, AGENDA)
        os.environ["ACADEMY_WORKSPACE"] = self.sb.workspace

    def tearDown(self):
        os.environ.pop("ACADEMY_WORKSPACE", None)
        self.sb.cleanup()

    def ctx(self, board=None):
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        return nx.Context(self.agenda, board or self.sb.board, ws, "author@t", "paper", 3,
                          ["dom"])

    def test_filing_goes_through_file_ticket(self):
        calls = []
        real = gp.file_ticket

        def spy(ctx, draft, detail="", campaign=None):
            calls.append((draft["title"], detail, campaign))
            return real(ctx, draft, detail, campaign)

        gp.file_ticket = spy
        try:
            ctx = self.ctx()
            gp.file_gaps(ctx, campaign="c1")
        finally:
            gp.file_ticket = real
        self.assertEqual([c[0] for c in calls], ["Verify lem:b", "Prove lem:d"])
        self.assertEqual([c[2] for c in calls], ["c1", "c1"])

    def test_ticket_ids_of_a_file_and_of_a_github_ref(self):
        self.assertEqual(gp.ticket_id_of("/b/expert@t/T-0012-verify-x.md"), "T-0012")
        self.assertEqual(gp.ticket_id_of("github#12"), "T-0012")
        with self.assertRaises(al.AgendaError):
            gp.ticket_id_of("nonsense")

    def test_filing_works_on_a_github_store(self):
        import board_store as bs
        with open(self.sb.workspace, encoding="utf-8") as fh:
            ws = json.load(fh)
        ws["board"] = {"path": self.sb.board, "backend": "github", "repo": "o/r"}
        wsf = os.path.join(self.sb.root, "ws-gh.json")
        self.sb.write(wsf, json.dumps(ws))
        store = ac.open_store(ac.load_workspace(wsf),
                              transport=bs.from_file_board(self.sb.board))
        self.assertNotIsInstance(store, ac.FileBoardStore)
        ctx = self.ctx(board=store)
        self.assertIs(ctx.board, store)
        res = gp.file_gaps(ctx)
        self.assertEqual([r["label"] for r in res["filed"]], ["lem:b", "lem:d"])
        self.assertTrue(all(r["ticket"].startswith("T-") for r in res["filed"]), res)
        self.assertEqual(len(store.read_all("expert@t")), 2)
        self.assertEqual(gp.file_gaps(ctx)["filed"], [])       # idempotent on github too


if __name__ == "__main__":
    unittest.main()
