"""The campaign dispatch step, as documented, against the CLI and the inbox core.

Real subagent dispatch cannot run here, so this keeps the *documents* honest: what the
campaign skill and its dispatch reference tell the driver to type must parse and behave as
the inbox core (academy_common.inbox_core) and the ticket tools do -- serial dispatch through
``/academy:inbox --campaign <target>``, tickets tagged ``campaign: <target>``, the cap of
three lifted, dead routes never listed, the checkpoint's exit codes.
"""

import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))
sys.path.insert(0, os.path.join(PLUGIN, "mcp"))

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
from tools import tickets as mcp_tickets  # noqa: E402

core = ac.inbox_core


def text(*rel):
    with open(os.path.join(REPO, *rel), encoding="utf-8") as fh:
        return fh.read()


SKILL = ("researcher", "skills", "campaign", "SKILL.md")
REF = ("researcher", "references", "campaign-dispatch.md")
INBOX = ("academy", "skills", "inbox", "SKILL.md")


def route(meta):
    return {"how": "skill", "target": "do:" + str(meta.get("kind")), "why": "by kind"}


class DocumentedCommands(unittest.TestCase):
    def test_the_dispatch_step_names_the_inbox_command_with_the_campaign_flag(self):
        skill, ref, inbox = text(*SKILL), text(*REF), text(*INBOX)
        self.assertRegex(skill, r"/academy:inbox --campaign <target>")
        self.assertRegex(ref, r"/academy:inbox --campaign <target>`? lists")
        self.assertRegex(ref, r"never dispatch from it")
        # serial: one ticket, one subagent of the Researcher, checkpoint, next
        self.assertRegex(skill, r"(?i)serial")
        self.assertRegex(ref, r"one ticket, one subagent of this role, then the\s+\*\*Checkpoint\*\*")
        # other roles' tickets wait for their next actor; the campaign does not run them
        self.assertRegex(skill, r"waits for the next\s+actor")
        self.assertRegex(ref, r"Wait for the next actor")
        # the serial rule is stated once, in budget.md "Campaigns"; the skill points there
        budget = text("academy", "references", "budget.md")
        self.assertRegex(budget, r"(?i)one subagent at a time")
        self.assertRegex(budget, r"\*\*Rule 2 is never suspended")
        self.assertRegex(skill, r"budget\.md")
        self.assertRegex(ref, r"(?i)\*\*Checkpoint\*\*")
        # the inbox skill accepts the same flag and says what it does to the cap
        self.assertIn("--campaign <target-id>", inbox)
        self.assertRegex(inbox, r"(?i)with `--campaign` each instance's\s+listing is not cut at three")

    def test_every_documented_flag_parses_with_the_inbox_parser(self):
        ref, inbox = text(*REF), text(*INBOX)
        parser = core.parser("t")
        flags = set()
        for doc in (ref, inbox):
            flags |= set(re.findall(r"(?<![\w-])(--[a-z]+)\b", doc)) & {
                "--campaign", "--all", "--json", "--check", "--instance", "--n"}
        self.assertTrue({"--campaign", "--all", "--json", "--check", "--instance"} <= flags)
        args = parser.parse_args(["--campaign", "paper:thm:x", "--all", "--json",
                                  "--instance", "researcher@t", "--n", "9"])
        self.assertEqual("paper:thm:x", args.campaign)
        self.assertTrue(args.all)
        self.assertEqual("T-0007", parser.parse_args(["--check", "T-0007"]).check)

    def test_role_inbox_scripts_document_the_flag_in_their_usage(self):
        for role in ("author", "expert", "researcher", "scientist"):
            with open(os.path.join(REPO, role, "scripts", "inbox.py"), encoding="utf-8") as fh:
                src = fh.read()
            with self.subTest(role=role):
                self.assertIn("inbox_core", src)          # a wrapper over the shared core
                self.assertTrue("core.parser(" in src or "core.main(" in src)  # --campaign free

    def test_the_documented_ticket_tagging_matches_the_tools(self):
        skill = text(*SKILL)
        self.assertRegex(skill, r"tagged `campaign: <target>`")
        self.assertIn("`tickets_create` field `campaign`", skill)
        self.assertIn("`board.py new --campaign`", skill)
        # the MCP tool has the field, the CLI has the flag, the field is the sender's
        tool = next(t for t in mcp_tickets.TOOLS if t.name == "tickets_create")
        self.assertIn("campaign", json.dumps(getattr(tool, "schema", None)
                                             or getattr(tool, "input_schema", None)
                                             or tool.__dict__))
        self.assertIn("campaign", ac.TICKET_FIELDS["sender"])
        self.assertIn("campaign", ac.TICKET_KEY_ORDER)
        buf = io.StringIO()
        with self.assertRaises(SystemExit) as cm, redirect_stdout(buf):
            bd.main(["new", "--help"])                     # --campaign is a known option
        self.assertEqual(0, cm.exception.code)
        self.assertIn("--campaign", buf.getvalue())

    def test_the_docs_use_the_field_name_the_core_filters_on(self):
        for rel in (SKILL, REF, INBOX):
            self.assertRegex(text(*rel), r"campaign")
        src = text("academy", "lib", "academy_common.py")
        self.assertIn('m.get("campaign") != campaign', src)


class DispatchLoop(unittest.TestCase):
    """The documented loop on a fixture board: list, take the first, checkpoint, next."""

    def setUp(self):
        self.board = tempfile.mkdtemp(prefix="campaign-docs-")
        self.addCleanup(shutil.rmtree, self.board, ignore_errors=True)
        self.inst = "researcher@t"
        for n, (status, extra) in enumerate([
                ("in-progress", {"campaign": "T"}), ("open", {"campaign": "T"}),
                ("open", {"campaign": "T"}), ("open", {"campaign": "T"}),
                ("open", {"campaign": "T"}), ("open", {"campaign": "U"}),
                ("blocked", {"campaign": "T", "blocked_by": "paper:lem:y",
                             "reopen_if": "a new invariant"}),
                ("open", {})], 1):
            self.put(n, status, **extra)

    def put(self, n, status, **extra):
        tid = "T-%04d" % n
        meta = {"id": tid, "title": "t " + tid, "kind": "prove", "from": "author@t",
                "to": self.inst, "status": status, "priority": "normal", "ask": "a",
                "deliverable": "d", "refs": [], "blocks": [], "waiting_on": [],
                "budget": {"runs": 1, "max_model": "sonnet"}, "packets": [],
                "created": "2026-09-30", "updated": "2026-09-30"}
        meta.update(extra)
        text_ = ac.new_ticket(meta)
        if status == "blocked" and extra.get("blocked_by"):
            fm, body = ac.read_frontmatter(text_)
            text_ = ac.write_frontmatter(fm, ac.append_thread(
                body, self.inst, "tried: the induction", "2026-09-30"))
        ac.atomic_write(os.path.join(self.board, self.inst, ac.ticket_filename(tid, "t")), text_)

    def inbox(self, *argv):
        args = core.parser("t").parse_args(list(argv))
        out = io.StringIO()
        rc = core.run(args, self.inst, self.board, 3, route, out=out)
        return rc, out.getvalue()

    def test_the_campaign_listing_is_in_inbox_order_without_blocked_tickets(self):
        """What the dispatch step reads (no --all): in-progress first, no dead routes."""
        rc, out = self.inbox("--campaign", "T", "--all", "--json")
        rows = json.loads(out)["take"]
        self.assertEqual({"T"}, {r["campaign"] for r in rows})
        # --all only looks: it adds the blocked ticket, marked (the doc says never dispatch from it)
        self.assertEqual(["T-0007"], [r["id"] for r in rows if r["blocked"] == "dead-route"])
        rc, out = self.inbox("--campaign", "T", "--json", "--n", "9")
        taken = [r["id"] for r in json.loads(out)["take"]]
        self.assertEqual(["T-0001", "T-0002", "T-0003", "T-0004", "T-0005"], taken)  # > 3, no dead

    def test_without_the_flag_the_cap_of_three_holds_and_other_campaigns_are_mixed_in(self):
        rc, out = self.inbox("--json", "--n", "9")
        self.assertEqual(3, len(json.loads(out)["take"]))

    def test_checkpoint_exit_codes_as_the_reference_describes(self):
        ref, inbox = text(*REF), text(*INBOX)        # the checkpoint is the inbox skill's
        self.assertRegex(inbox, r"exit 0 means delivered,\s+blocked with its reason or rejected")
        self.assertRegex(inbox, r"Exit 3 means unfinished")
        self.assertRegex(ref, r"exit 3 means unfinished")
        self.assertEqual(3, self.inbox("--check", "T-0002")[0])       # open: unfinished
        self.assertEqual(3, self.inbox("--check", "T-0001")[0])       # in progress
        self.assertEqual(0, self.inbox("--check", "T-0007")[0])       # blocked with its reason
        bd.transition_ticket(self.board, "T-0001", "delivered", result="done",
                             as_instance=self.inst, date="2026-09-30")
        rc, out = self.inbox("--check", "T-0001")
        self.assertEqual(0, rc)
        self.assertIn("delivered", out)
        # unfinished work is first in line next time (resume before anything new)
        bd.transition_ticket(self.board, "T-0002", "accepted", as_instance=self.inst)
        bd.transition_ticket(self.board, "T-0002", "in-progress", as_instance=self.inst)
        rows = json.loads(self.inbox("--campaign", "T", "--json")[1])["take"]
        self.assertEqual("T-0002", rows[0]["id"])


class CampaignReachesOtherRolesOnlyByTickets(unittest.TestCase):
    """Roey: campaign tooling acts on other roles only by issuing tickets and waiting for
    the next actor. The campaign skill and its dispatch reference never name another
    role's agent, and never tell the driver to dispatch one."""

    def test_no_other_roles_agent_is_named_for_dispatch(self):
        perms = ac.load_permissions(os.path.join(PLUGIN, "permissions.json"))
        others = [a for role, agents in perms["roster"].items()
                  if role not in ("researcher", "academy") for a in agents]
        self.assertIn("review-chair", others)
        for rel in (SKILL, REF):
            body = text(*rel)
            for agent in others:
                with self.subTest(doc=rel[-1], agent=agent):
                    self.assertNotRegex(body, r"(?<![\w-])%s(?![\w-])" % re.escape(agent))
            self.assertNotRegex(body, r"(?i)dispatch one subagent for the receiving role")
            self.assertNotRegex(body, r"(?i)subagent_type:\s*(author|expert|scientist):")

    def test_the_states_are_documented_and_computed_by_the_shared_module(self):
        skill, ref = text(*SKILL), text(*REF)
        for word in ("WAITING", "PAUSE"):
            self.assertIn(word, skill)
            self.assertIn(word, ref)
        self.assertIn("academy/lib/workplan.py", ref)
        self.assertRegex(skill, r"never\s+runs another role's agents")


if __name__ == "__main__":
    unittest.main()
