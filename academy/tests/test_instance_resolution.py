"""Per-call instance resolution in the MCP server (workflow fixes 1 and 2, 2026-10-09).

In a cloud session the server runs outside every home (or in the library), so its
cwd says nothing about the calling agent. The acting instance is resolved per call:
the ``instance`` argument, else the call's ticket, else the server's home, else the
only instance of the agent's role. A role agent never acts as ``human``, and
``claims_new`` reaches another instance's namespace only on a live ticket addressed
to it.

Run from the repo root:  py -m unittest discover academy/tests
"""

import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_mcp import McpTestBase, write  # noqa: E402

import server as srv  # noqa: E402  (academy/mcp, put on sys.path by test_mcp)
from tools import claims as claims_mod  # noqa: E402


class TwoResearchers(McpTestBase):
    """The shared temp workspace plus a second researcher (namespace s2)."""

    @classmethod
    def setUpClass(cls):
        super(TwoResearchers, cls).setUpClass()
        t = cls.tmp.replace("\\", "/")
        cls.homes["researcher@u"] = t + "/notebook2"
        os.makedirs(cls.homes["researcher@u"])
        with open(cls.ws_path, encoding="utf-8") as fh:
            ws = json.load(fh)
        ws["instances"]["researcher@u"] = {"role": "researcher",
                                           "home": cls.homes["researcher@u"],
                                           "domains": ["test-pack"], "ns": "s2"}
        write(cls.ws_path, json.dumps(ws, indent=2))

    def ticket(self, to, frm_home="author@t", **kw):
        """File a ticket as the main session of ``frm_home`` (or the human)."""
        args = dict(title="t", kind="question", to=to, ask="a", deliverable="d")
        args.update(kw)
        err, t = self.server(frm_home).call("tickets_create", **args)
        self.assertFalse(err, t)
        return t["id"]


class TestAgentAtTheWorkspaceRoot(TwoResearchers):
    def test_agent_updates_its_own_ticket_from_the_root(self):
        # the cloud case: the server's cwd is the workspace root, in no home
        tid = self.ticket("expert@t")
        root = self.server()
        err, res = root.call("tickets_update", caller="expert:review-chair", id=tid,
                             status="accepted", note="taking it")
        self.assertFalse(err, res)
        err, g = root.call("tickets_get", id=tid)
        self.assertIn("expert@t/review-chair: status open -> accepted", g["body"])

    def test_researcher_resolved_by_the_ticket_among_two(self):
        tid = self.ticket("researcher@u", frm_home="researcher@t")
        err, res = self.server().call("tickets_update", caller="researcher:claim-keeper",
                                      id=tid, status="accepted")
        self.assertFalse(err, res)
        err, g = self.server().call("tickets_get", id=tid)
        self.assertIn("researcher@u/claim-keeper: status open -> accepted", g["body"])

    def test_explicit_instance_files_as_it(self):
        err, t = self.server().call("tickets_create", caller="researcher:prover",
                                    instance="researcher@u", title="t", kind="question",
                                    to="researcher@t", ask="a", deliverable="d")
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "researcher@u")

    def test_ambiguous_role_without_hint_is_refused(self):
        err, msg = self.server().call("tickets_create", caller="researcher:prover",
                                      title="t", kind="question", to="expert@t",
                                      ask="a", deliverable="d")
        self.assertTrue(err)
        self.assertIn("pass instance", msg)

    def test_unique_role_resolves_from_another_roles_home(self):
        # the server ran in the library (expert home); a math-writer still is author@t
        err, t = self.server("expert@t").call("tickets_create", caller="author:math-writer",
                                              title="t", kind="question", to="expert@t",
                                              ask="a", deliverable="d")
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "author@t")

    def test_explicit_instance_of_another_role_refused(self):
        err, msg = self.server().call("tickets_create", caller="author:math-writer",
                                      instance="expert@t", title="t", kind="question",
                                      to="expert@t", ask="a", deliverable="d")
        self.assertTrue(err)
        self.assertIn("belongs to the author role", msg)

    def test_unknown_instance_refused(self):
        err, msg = self.server().call("tickets_create", caller="author:math-writer",
                                      instance="author@nowhere", title="t",
                                      kind="question", to="expert@t", ask="a",
                                      deliverable="d")
        self.assertTrue(err)
        self.assertIn("workspace instance", msg)

    def test_agent_never_files_as_human(self):
        err, msg = self.server().call("tickets_create", caller="author:math-writer",
                                      instance="human", title="t", kind="question",
                                      to="expert@t", ask="a", deliverable="d")
        self.assertTrue(err)
        self.assertIn("never as 'human'", msg)

    def test_main_session_may_name_its_instance(self):
        err, t = self.server().call("tickets_create", instance="author@t", title="t",
                                    kind="question", to="expert@t", ask="a",
                                    deliverable="d")
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "author@t")

    def test_child_ticket_files_as_the_party_on_the_parent(self):
        parent = self.ticket("researcher@u", frm_home="researcher@t")
        err, t = self.server().call("tickets_create", caller="researcher:prover",
                                    parent=parent, title="t", kind="question",
                                    to="expert@t", ask="a", deliverable="d")
        self.assertFalse(err, t)
        self.assertEqual(t["from"], "researcher@u")

    def test_config_get_for_an_agent_outside_every_home(self):
        err, res = self.server().call("config_get", caller="author:math-writer")
        self.assertFalse(err, res)
        self.assertEqual(res["instance"], "author@t")
        err, msg = self.server().call("config_get")
        self.assertTrue(err)
        self.assertIn("name an instance", msg)


class FakeBackend(object):
    created = []

    def __init__(self, ctx):
        self.ctx = ctx

    def new(self, cid, title, status="open", where=None, kind=None):
        FakeBackend.created.append(cid)
        return {"command": "new %s" % cid, "exit": 0, "stdout": "", "stderr": ""}


class TestClaimsNewAcrossInstances(TwoResearchers):
    """claims_new in another instance's namespace only on a ticket addressed to it."""

    def call(self, home, caller, **args):
        os.environ["ACADEMY_WORKSPACE"] = self.ws_path
        self.addCleanup(os.environ.pop, "ACADEMY_WORKSPACE", None)
        with mock.patch.object(claims_mod, "BACKEND_FACTORY", FakeBackend):
            res = srv.call_tool("claims_new", args, cwd=self.homes[home] if home else
                                self.tmp, caller=caller)
        text = res["content"][0]["text"]
        try:
            return res["isError"], json.loads(text)
        except ValueError:
            return res["isError"], text

    def test_own_namespace(self):
        err, res = self.call("researcher@t", "researcher:prover", id="s1:GEO", title="x")
        self.assertFalse(err, res)

    def test_other_namespace_needs_a_ticket(self):
        err, msg = self.call("researcher@t", "researcher:prover", id="s2:GEO", title="x")
        self.assertTrue(err)
        self.assertIn("pass ticket=", msg)

    def test_other_namespace_on_a_ticket_addressed_to_it(self):
        tid = self.ticket("researcher@u", frm_home="researcher@t")
        err, res = self.call("researcher@t", "researcher:prover", id="s2:GEO",
                             title="x", ticket=tid)
        self.assertFalse(err, res)
        self.assertEqual(res["for_instance"], "researcher@u")
        self.assertEqual(res["target_role"], "researcher")
        self.assertIn("s2:GEO", FakeBackend.created)
        err, g = self.server().call("tickets_get", id=tid)
        self.assertIn("researcher@u/prover: created s2:GEO (open) for researcher@u",
                      g["body"])

    def test_ticket_to_someone_else_refused(self):
        tid = self.ticket("expert@t", frm_home="researcher@t")
        err, msg = self.call("researcher@t", "researcher:prover", id="s2:GEO",
                             title="x", ticket=tid)
        self.assertTrue(err)
        self.assertIn("addressed to researcher@u", msg)

    def test_author_agent_cannot_create_in_a_researcher_namespace(self):
        tid = self.ticket("researcher@u", frm_home="researcher@t")
        err, msg = self.call("author@t", "author:math-writer", id="s2:GEO", title="x",
                             ticket=tid)
        self.assertTrue(err)
        self.assertIn("belongs to the author role", msg)

    def test_math_writer_in_its_namespace_from_the_library(self):
        # 2026-10-08: "math-writer may create claims only in its own instance's
        # namespace, not 'paper'" -- the server's cwd was another home
        err, res = self.call("expert@t", "author:math-writer", id="paper:lem:z",
                             title="x")
        self.assertFalse(err, res)


if __name__ == "__main__":
    unittest.main()
