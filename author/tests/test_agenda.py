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
            import inbox as nx
            ctx = nx.Context(self.agenda, self.sb.board, ws, "author@t", "paper", 3, ["dom"])
            self.assertEqual(ag.file_gaps(ctx)["filed"], [])
            self.assertEqual(ag.file_gaps(ctx)["filed"], [])
        finally:
            os.environ.pop("ACADEMY_WORKSPACE", None)
        self.assertEqual({f: self.board_files(f) for f in ("author@t", "expert@t")}, before)

    def test_dry_run_files_nothing(self):
        code, out, _err = self.run_cli("gaps", "--file", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("2 ticket(s) to file", out)
        self.assertEqual(self.board_files("expert@t"), [])
        self.assertEqual(self.board_files("author@t"), [])

    def test_a_missing_record_becomes_a_self_ticket(self):
        self.sb.write(self.agenda, AGENDA.replace("| proved | - | author@t | open |",
                                                  "| proved | - | author@t | missing |"))
        self.assertEqual(self.run_cli("gaps", "--file")[0], 0)
        files = self.board_files("author@t")
        self.assertEqual(len(files), 1)
        meta, _body = self.meta("author@t", files[0])
        self.assertEqual((meta["from"], meta["to"], meta["kind"], meta["agenda"]),
                         ("author@t", "author@t", "apply", "paper:lem:d"))
        self.assertEqual(ac.validate_ticket(meta), [])

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


if __name__ == "__main__":
    unittest.main()
