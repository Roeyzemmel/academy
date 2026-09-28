"""agenda_lib (the agenda.md / roadmap.md formats) and agenda.py (check, status, gaps,
milestones)."""

import json
import os
import subprocess
import sys
import unittest

from fixtures import SCRIPTS, Sandbox
from test_next import AGENDA, ROADMAP

sys.path.insert(0, SCRIPTS)
import agenda_lib as al  # noqa: E402


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

    def test_roadmap_round_trip(self):
        rm = al.parse_roadmap(ROADMAP)
        self.assertEqual(len(rm.items), 12)
        it = rm.get("R-0003")
        self.assertEqual((it.tag, it.priority, it.depends_on, it.agenda),
                         ("apply", "high", ["R-0004"], "paper:thm:main"))
        self.assertEqual(al.write_roadmap(rm), ROADMAP)
        self.assertEqual(rm.next_id(), "R-0013")

    def test_roadmap_keeps_prose_sections(self):
        text = ("# R\n\nintro\n\n## Notes\n\nfree prose\n\n"
                "## R-0001 [write] T\n- status: open\n\nbody\n")
        rm = al.parse_roadmap(text)
        self.assertEqual(len(rm.items), 1)
        self.assertEqual(al.write_roadmap(rm), text)

    def test_duplicate_item_is_an_error(self):
        with self.assertRaises(al.AgendaError):
            al.parse_roadmap("## R-0001 [write] a\n\n## R-0001 [write] b\n")

    def test_satisfied(self):
        self.assertTrue(al.satisfied("proved", "sketch"))
        self.assertTrue(al.satisfied("supported", "sketch"))
        self.assertFalse(al.satisfied("sketch", "proved-modulo"))
        self.assertFalse(al.satisfied("refuted", "open"))
        self.assertTrue(al.satisfied("refuted", "refuted"))
        self.assertFalse(al.satisfied("missing", "open"))
        self.assertFalse(al.satisfied("", "open"))

    def test_check(self):
        ag, rm = al.parse_agenda(AGENDA), al.parse_roadmap(ROADMAP)
        self.assertEqual(al.check(ag, rm, "paper"), [])
        bad_ag = al.parse_agenda(AGENDA.replace("| 4 | defn:c | paper:defn:c | proved | - |",
                                                "| 4 | defn:c | paper:defn:c | proved | thm:main |"))
        probs = al.check(bad_ag, rm, "paper")
        self.assertTrue(any("cycle" in p for p in probs), probs)
        bad_rm = al.parse_roadmap(ROADMAP.replace("[R-0004]", "[R-0099]")
                                  .replace("## R-0001 [apply]", "## R-0001 [frobnicate]"))
        probs = al.check(ag, bad_rm, "paper")
        self.assertTrue(any("R-0099" in p for p in probs))
        self.assertTrue(any("unknown tag" in p for p in probs))

    def test_new_files(self):
        entries = [al.Entry("thm:a", "paper:thm:a", "proved", [], "author@t", "sketch")]
        text = al.new_agenda_text("author@t", entries, {"sub": {"thm:a": "proved"}})
        ag = al.parse_agenda(text)
        self.assertEqual(ag.entries[0].label, "thm:a")
        self.assertEqual(ag.milestones, {"sub": {"thm:a": "proved"}})
        rm = al.parse_roadmap(al.new_roadmap_text("author@t", [al.Item(
            "R-0001", "write", "T", {"status": "open"}, "b")]))
        self.assertEqual(rm.items[0].title, "T")


class AgendaCliTests(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()
        self.agenda = os.path.join(self.sb.home, "Drafts", "agenda.md")
        self.sb.write(self.agenda, AGENDA)
        self.sb.write(os.path.join(self.sb.home, "Drafts", "roadmap.md"), ROADMAP)

    def tearDown(self):
        self.sb.cleanup()

    def run_cli(self, *args):
        res = subprocess.run([sys.executable, os.path.join(SCRIPTS, "agenda.py")] + list(args)
                             + ["--home", self.sb.home], capture_output=True, env=self.sb.env)
        return res.returncode, res.stdout.decode("utf-8"), res.stderr.decode("utf-8")

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

    def test_gaps(self):
        code, out, _err = self.run_cli("gaps", "--json")
        self.assertEqual(code, 1)                       # nothing uncovered: exit 1
        gaps = {g["label"]: g for g in json.loads(out)}
        # lem:b and lem:d have open items; thm:main has R-0003/R-0011
        self.assertEqual(set(gaps), set())
        rm = os.path.join(self.sb.home, "Drafts", "roadmap.md")
        self.sb.write(rm, "# Roadmap\n")
        code, out, _err = self.run_cli("gaps", "--json")
        gaps = {g["label"]: g for g in json.loads(out)}
        self.assertEqual(set(gaps), {"thm:main", "lem:b", "lem:d"})
        self.assertEqual(gaps["lem:b"]["proposed_tag"], "verify")
        self.assertEqual(gaps["lem:d"]["proposed_tag"], "lead")

    def test_milestones(self):
        code, out, _err = self.run_cli("milestones", "--json")
        m = json.loads(out)
        self.assertEqual((m["round-1"]["met"], m["round-1"]["of"]), (1, 2))


if __name__ == "__main__":
    unittest.main()
