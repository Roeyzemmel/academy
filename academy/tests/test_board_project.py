"""Tests for board_project.py: the Project fields as a spec derived from the constants."""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board_github import GithubBoardCase  # noqa: E402

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402
import board_project as bp  # noqa: E402


def names(spec, field):
    return bp._names(bp._field(spec, field))


class TestSpec(unittest.TestCase):
    def test_kind_options_are_every_ticket_kind_including_campaign_kinds(self):
        got = names(bp.build(), "Kind")
        self.assertEqual(list(ac.TICKET_KINDS), got)
        for k in ("write", "apply", "copy", "sweep"):
            self.assertIn(k, got)

    def test_status_options_carry_the_added_states(self):
        got = names(bp.build(), "Status")
        for o in ("Todo", "In Progress", "Done", "Accepted", "Blocked", "Delivered"):
            self.assertIn(o, got)
        self.assertEqual(len(set(got)), len(got))

    def test_role_priority_block_agenda(self):
        spec = bp.build(["author@a", "expert@b"])
        self.assertEqual(list(bc.ROLES), names(spec, "Role"))
        self.assertEqual(["P0", "P1", "P2"], names(spec, "Priority"))
        self.assertEqual(["pending", "dead-route"], names(spec, "Block"))
        self.assertEqual("text", bp._field(spec, "Agenda")["type"])
        self.assertEqual(["author@a", "expert@b", "human"], names(spec, "Instance"))

    def test_the_spec_covers_every_kind_status_priority_and_role(self):
        self.assertEqual([], bp.check(bp.build()))

    def test_check_reports_a_kind_the_spec_lacks(self):
        spec = bp.build()
        bp._field(spec, "Kind")["options"] = [o for o in bp._field(spec, "Kind")["options"]
                                              if o["name"] != "sweep"]
        self.assertTrue(any("no option 'sweep'" in p for p in bp.check(spec)))

    def test_check_reports_a_status_without_a_mapping(self):
        spec = bp.build()
        del spec["mappings"]["status"]["blocked"]
        self.assertTrue(any("'blocked'" in p for p in bp.check(spec)))
        spec = bp.build()
        spec["mappings"]["status"]["blocked"] = "Stuck"
        self.assertTrue(any("not a Status option" in p for p in bp.check(spec)))

    def test_every_status_and_priority_is_mapped(self):
        self.assertEqual(set(ac.TICKET_STATUSES), set(bp.STATUS_OPTIONS))
        self.assertEqual(set(ac.PRIORITIES), set(bp.PRIORITY_OPTIONS))

    def test_deterministic(self):
        self.assertEqual(json.dumps(bp.build(["a@b"])), json.dumps(bp.build(["a@b"])))


class TestLive(unittest.TestCase):
    def test_missing_field_and_option_are_reported_extras_noted(self):
        spec = bp.build()
        live = {"fields": [{"name": "Kind", "options": [{"name": k} for k in ac.TICKET_KINDS
                                                        if k != "sweep"] + ["legacy"]},
                           {"name": "Status", "options": ["Todo", "In Progress", "Done"]}]}
        probs, notes = bp.compare_live(spec, live)
        self.assertIn("Project field Kind lacks option 'sweep'", probs)
        self.assertIn("Project field Status lacks option 'Blocked'", probs)
        self.assertIn("Project has no field Block", probs)
        self.assertIn("Project field Kind has an extra option 'legacy'", notes)

    def test_a_matching_project_is_clean(self):
        spec = bp.build()
        live = {"fields": [{"name": f["name"], "options": _opts(f)} for f in spec["fields"]]}
        self.assertEqual(([], []), bp.compare_live(spec, live))


def _opts(f):
    return [o["name"] for o in f.get("options", [])]


class TestFieldsFor(GithubBoardCase):
    def test_values_follow_the_ticket(self):
        self.new(title="a", agenda="paper:thm:x", priority="high", kind="write",
                 to="author@main")
        self.new(title="b")
        self.new(title="c")
        bd.transition_ticket(self.board, "T-0002", "blocked", blocked_by="paper:lem:y",
                             reopen_if="new", reason="tried", as_instance="expert@main")
        bd.transition_ticket(self.board, "T-0003", "blocked", waiting_on=["T-0001"],
                             as_instance="expert@main")
        got = {m["id"]: bp.fields_for(m) for _p, m, _b in bd.iter_tickets(self.board)}
        self.assertEqual({"Status": "Todo", "Instance": "author@main", "Role": "author",
                          "Kind": "write", "Priority": "P0", "Agenda": "paper:thm:x",
                          "Block": None}, got["T-0001"])
        self.assertEqual("dead-route", got["T-0002"]["Block"])
        self.assertEqual("Blocked", got["T-0002"]["Status"])
        self.assertEqual("pending", got["T-0003"]["Block"])
        spec = bp.build(sorted(self.ws["instances"]))
        for f, v in got["T-0001"].items():
            if v and bp._field(spec, f)["type"] == "single_select":
                self.assertIn(v, names(spec, f))

    def test_cli_check_and_spec_output(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = bp.main(["--check", "--workspace", self.ws_path])
        self.assertEqual(0, rc)
        self.assertIn("ok", out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, bp.main(["--workspace", self.ws_path]))
        spec = json.loads(out.getvalue())
        self.assertIn("researcher@r1", names(spec, "Instance"))


if __name__ == "__main__":
    unittest.main()
