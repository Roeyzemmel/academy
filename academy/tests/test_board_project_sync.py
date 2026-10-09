"""Tests for board_project_sync.py: a ticket issue's Project fields, written through a fake gql."""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_board_github import GithubBoardCase, issue_of  # noqa: E402

import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402
import board_project as bp  # noqa: E402
import board_project_sync as ps  # noqa: E402


def project_of(spec):
    """A live-shaped Project from the spec: every field, every option, with ids."""
    fields = {}
    for f in spec["fields"]:
        live = {"id": "F_" + f["name"], "name": f["name"],
                "dataType": "TEXT" if f["type"] == "text" else "SINGLE_SELECT"}
        if f["type"] != "text":
            live["options"] = [{"id": "O_%s_%s" % (f["name"], o["name"]), "name": o["name"]}
                               for o in f["options"]]
        fields[f["name"]] = live
    return {"id": "PVT_1", "fields": fields}


class FakeGql(object):
    def __init__(self, data=None):
        self.calls = []
        self.data = data or {}

    def __call__(self, query, variables):
        self.calls.append((query, variables))
        if "addProjectV2ItemById" in query:
            return {"addProjectV2ItemById": {"item": {"id": "PVTI_" + variables["c"]}}}
        if "updateProjectV2Field(" in query:
            opts = [dict(o, id=o.get("id") or "O_new_" + o["name"]) for o in variables["o"]]
            return {"updateProjectV2Field": {"projectV2Field": {"options": opts}}}
        return self.data


class TestValues(GithubBoardCase):
    def issues(self):
        self.make()
        out = []
        for _p, m, b in bd.iter_tickets(self.board):
            iss = issue_of(bc.encode(m, b))
            iss["node_id"] = "I_%d" % iss["number"]
            out.append((m, iss))
        return out

    def test_values_are_fields_for_the_decoded_ticket(self):
        for m, iss in self.issues():
            values, problem = ps.values_for(iss)
            self.assertIsNone(problem)
            self.assertEqual(bp.fields_for(bc.decode(iss)[0]), values)

    def test_a_non_ticket_gets_status_from_its_state_only(self):
        for state, want in (("open", "Todo"), ("closed", "Done")):
            values, problem = ps.values_for({"number": 7, "title": "a bug report",
                                             "body": "", "labels": [], "state": state})
            self.assertEqual({"Status": want}, values)
            self.assertTrue(problem)

    def test_sync_adds_the_item_and_sets_every_field(self):
        project = project_of(bp.build())
        m, iss = self.issues()[0]
        project["fields"]["Instance"]["options"].append(
            {"id": "O_Instance_%s" % m["to"], "name": m["to"]})
        gql = FakeGql()
        self.assertEqual(([], True), ps.sync_issue(gql, project, iss))
        (add_q, add_v), (set_q, _v) = gql.calls
        self.assertIn("addProjectV2ItemById", add_q)
        self.assertEqual({"p": "PVT_1", "c": iss["node_id"]}, add_v)
        values, _ = ps.values_for(iss)
        for name, v in values.items():
            fid = 'fieldId:"F_%s"' % name
            self.assertIn(fid, set_q)
            if v is None:
                self.assertRegex(set_q, r"clearProjectV2ItemFieldValue\(input:\{[^}]*%s" % fid)
            elif name == "Agenda":
                self.assertIn("{text:%s}" % json.dumps(v), set_q)
            else:
                self.assertIn('singleSelectOptionId:"O_%s_%s"' % (name, v), set_q)

    def test_a_missing_option_is_added_keeping_the_others(self):
        """A ticket to an instance the Project predates: the option is appended, the existing
        options keep their ids (so no item loses its value), then the value is set."""
        project = project_of(bp.build())
        m, iss = self.issues()[0]
        before = list(project["fields"]["Instance"]["options"])
        gql = FakeGql()
        self.assertEqual(([], True), ps.sync_issue(gql, project, iss))
        upd = [(q, v) for q, v in gql.calls if "updateProjectV2Field(" in q]
        self.assertEqual(1, len(upd))
        sent = upd[0][1]["o"]
        self.assertEqual([o["id"] for o in before], [o.get("id") for o in sent[:-1]])
        self.assertEqual(m["to"], sent[-1]["name"])
        self.assertIn('singleSelectOptionId:"O_new_%s"' % m["to"], gql.calls[-1][0])

    def test_a_missing_field_is_reported_not_written(self):
        project = project_of(bp.build([m["to"] for m, _i in self.issues()]))
        del project["fields"]["Agenda"]
        _m, iss = self.issues()[0]
        gql = FakeGql()
        problems, _w = ps.sync_issue(gql, project, iss)
        self.assertTrue(any("no field 'Agenda'" in p for p in problems))
        self.assertNotIn('"F_Agenda"', gql.calls[-1][0])

    def test_an_item_already_right_is_left_alone(self):
        project = project_of(bp.build([m["to"] for m, _i in self.issues()]))
        _m, iss = self.issues()[0]
        values, _ = ps.values_for(iss)
        gql = FakeGql()
        self.assertEqual(([], False), ps.sync_issue(gql, project, iss, ("PVTI_x", dict(values))))
        self.assertEqual([], gql.calls)
        stale = dict(values, Status="Done" if values["Status"] != "Done" else "Todo")
        self.assertEqual(([], True), ps.sync_issue(gql, project, iss, ("PVTI_x", stale)))
        self.assertNotIn("addProjectV2ItemById", " ".join(q for q, _v in gql.calls))
        self.assertIn('itemId:"PVTI_x"', gql.calls[-1][0])

    def test_sync_never_writes_the_issue(self):
        project = project_of(bp.build([m["to"] for m, _i in self.issues()]))
        gql = FakeGql()
        for _m, iss in self.issues():
            ps.sync_issue(gql, project, iss)
        for q, _v in gql.calls:
            self.assertNotRegex(q, r"updateIssue|addComment|closeIssue|addLabels")


class TestProjectRef(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(("user", "ada", 2), ps.parse_project("users/ada/2"))
        self.assertEqual(("organization", "acme", 5), ps.parse_project("orgs/acme/5"))
        self.assertEqual(("user", "ada", 2),
                         ps.parse_project("https://github.com/users/ada/projects/2"))
        for bad in ("", "ada/2", "users/x/projects"):
            with self.assertRaises(ValueError):
                ps.parse_project(bad)

    def test_load_project_reads_fields(self):
        live = project_of(bp.build())
        data = {"user": {"projectV2": {"id": "PVT_1",
                                       "fields": {"nodes": list(live["fields"].values()) + [{}]}}}}
        got = ps.load_project(FakeGql(data), "users/ada/2")
        self.assertEqual(live, got)
        with self.assertRaises(LookupError):
            ps.load_project(FakeGql({"user": {"projectV2": None}}), "users/ada/9")

    def test_main_without_repo_or_project_is_an_error(self):
        # independent of the machine: ACADEMY_WORKSPACE may name a real, configured workspace
        from unittest import mock
        with mock.patch.object(ps.ac, "load_workspace", side_effect=ps.ac.ConfigError("none")):
            self.assertEqual(2, ps.main([]))
        with mock.patch.object(ps.ac, "load_workspace",
                               return_value={"board_config": {"repo": "o/r"}}):
            self.assertEqual(2, ps.main([]))       # a repo but no project

    def test_project_items_reads_values_by_field_name(self):
        page = {"node": {"items": {"pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {"id": "PVTI_1", "content": {"number": 5, "repository": {
                        "nameWithOwner": "o/r"}}, "fieldValues": {"nodes": [
                        {"name": "Todo", "field": {"name": "Status"}},
                        {"text": "paper:lem:x", "field": {"name": "Agenda"}}, {}]}},
                    {"id": "PVTI_2", "content": {"number": 5, "repository": {
                        "nameWithOwner": "o/other"}}, "fieldValues": {"nodes": []}},
                    {"id": "PVTI_3", "content": None, "fieldValues": {"nodes": []}}]}}}
        got = ps.project_items(FakeGql(page), {"id": "PVT_1"}, "o/r")
        self.assertEqual({5: ("PVTI_1", {"Status": "Todo", "Agenda": "paper:lem:x"})}, got)


if __name__ == "__main__":
    unittest.main()
