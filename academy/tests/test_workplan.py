"""academy/lib/workplan.py, cowork.py and the cowork tag, on a fixture board.

The shared mechanics of a campaign and a cowork: the tag, the state computed from the
tagged tickets (ACTIVE / WAITING / PAUSE / DONE), the caps, the plan file, and the tag
accepted end to end (board.py new --cowork, the inbox core's --cowork, validation).
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import academy_common as ac  # noqa: E402
import workplan as wp  # noqa: E402
import board as bd  # noqa: E402
import cowork  # noqa: E402


def meta(tid, to, status="open", **extra):
    m = {"id": tid, "title": "t " + tid, "kind": "verify", "from": "researcher@t",
         "to": to, "status": status, "priority": "normal", "ask": "a", "deliverable": "d",
         "refs": [], "blocks": [], "waiting_on": [], "budget": {"runs": 1},
         "packets": [], "created": "2026-10-09", "updated": "2026-10-09"}
    m.update(extra)
    return m


class Board(unittest.TestCase):
    def setUp(self):
        self.board = tempfile.mkdtemp(prefix="workplan-")
        self.addCleanup(shutil.rmtree, self.board, ignore_errors=True)

    def put(self, m):
        ac.atomic_write(os.path.join(self.board, m["to"], ac.ticket_filename(m["id"], "t")),
                        ac.new_ticket(m))

    def metas(self):
        return [m for _p, m in ac.FileBoardStore(self.board).iter_meta()]


class TicketClassTests(unittest.TestCase):
    def test_classes(self):
        self.assertEqual("done", wp.ticket_class(meta("T-1", "expert@t", "delivered")))
        self.assertEqual("decision", wp.ticket_class(meta("T-1", "human")))
        self.assertEqual("decision", wp.ticket_class(
            meta("T-1", "expert@t", "blocked", waiting_on=["human"])))
        self.assertEqual("dead", wp.ticket_class(
            meta("T-1", "expert@t", "blocked", blocked_by="s1:X", reopen_if="new idea")))
        self.assertEqual("out", wp.ticket_class(
            meta("T-1", "expert@t", "blocked", waiting_on=["T-0002"])))
        self.assertEqual("own", wp.ticket_class(meta("T-1", "researcher@t"),
                                                lead="researcher@t"))
        self.assertEqual("out", wp.ticket_class(meta("T-1", "researcher@t")))   # no lead


class StateFromFixtureBoard(Board):
    def test_waiting_pause_done_from_the_tagged_tickets(self):
        self.put(meta("T-0001", "expert@t", cowork="c"))
        self.put(meta("T-0002", "scientist@t", "accepted", cowork="c"))
        self.put(meta("T-0003", "expert@t", cowork="other"))
        self.put(meta("T-0004", "expert@t"))
        st = wp.state(self.metas(), "cowork", "c")
        self.assertEqual("WAITING", st["state"])
        self.assertEqual(["T-0001", "T-0002"], st["out"])
        # a decision with nothing else movable pauses
        self.put(meta("T-0001", "expert@t", "delivered", cowork="c"))
        self.put(meta("T-0002", "scientist@t", "blocked", waiting_on=["human"], cowork="c"))
        self.assertEqual("PAUSE", wp.state(self.metas(), "cowork", "c")["state"])
        # every ticket done: DONE
        self.put(meta("T-0002", "scientist@t", "closed", cowork="c"))
        st = wp.state(self.metas(), "cowork", "c")
        self.assertEqual(("DONE", ["T-0001", "T-0002"]), (st["state"], st["done"]))

    def test_a_campaign_lead_with_own_work_is_active(self):
        self.put(meta("T-0001", "expert@t", campaign="s1:X"))
        self.put(meta("T-0002", "researcher@t", campaign="s1:X"))
        self.assertEqual("ACTIVE", wp.state(self.metas(), "campaign", "s1:X",
                                            lead="researcher@t")["state"])
        self.assertEqual("WAITING", wp.state(self.metas(), "campaign", "s1:X")["state"])

    def test_combine_and_active(self):
        self.assertEqual("PAUSE", wp.combine(["PAUSE", "PAUSE", "DONE"]))
        self.assertEqual("WAITING", wp.combine(["PAUSE", "WAITING"]))
        self.assertEqual("ACTIVE", wp.combine(["ACTIVE", "WAITING"]))
        self.assertEqual("DONE", wp.combine(["DONE"]))
        self.put(meta("T-0001", "expert@t", cowork="c"))
        self.put(meta("T-0002", "expert@t", "closed", cowork="d"))
        self.put(meta("T-0003", "expert@t", campaign="s1:X"))
        self.assertEqual({"c": ["T-0001"]}, wp.active(self.metas(), "cowork"))
        self.assertEqual({"s1:X": ["T-0003"]}, wp.active(self.metas(), "campaign"))


class TagAndCapsTests(unittest.TestCase):
    def test_tags(self):
        self.assertEqual("", wp.check_tag("cowork", "flat-section"))
        self.assertIn("slug", wp.check_tag("cowork", "Flat section"))
        self.assertEqual("", wp.check_tag("campaign", "paper:lem:x"))
        self.assertIn("one line", wp.check_tag("campaign", "a\nb"))
        self.assertEqual(("cowork", "c"), wp.tag_of({"cowork": "c"}))
        self.assertEqual((None, None), wp.tag_of({}))

    def test_caps(self):
        with self.assertRaises(wp.WorkplanError):
            wp.caps("campaign", agents=4)                       # rounds required
        c = wp.caps("campaign", 3, 4, 2, "lingo", cloud=True)
        self.assertEqual((0, True), (c["runs"], c["runs_forced_to_zero"]))
        c = wp.caps("cowork")
        self.assertEqual((1, ["agents"]), (c["agents"], c["binding"]))
        with self.assertRaises(wp.WorkplanError):
            wp.caps("cowork", agents=0)

    def test_the_lib_knows_the_same_fields(self):
        for k in wp.KINDS:
            self.assertIn(k, ac.TICKET_FIELDS["sender"])
            self.assertIn(k, ac.TICKET_KEY_ORDER)
        perms = ac.load_permissions(os.path.join(PLUGIN, "permissions.json"))
        self.assertIn("cowork", perms["tickets"]["fields"]["sender"])


class CoworkEndToEnd(Board):
    """board.py new --cowork -> validation -> inbox --cowork -> cowork.py status/list."""

    def setUp(self):
        super().setUp()
        for inst in ("author@t", "expert@t", "researcher@t", "human"):
            os.makedirs(os.path.join(self.board, inst), exist_ok=True)
        self.ws = {"instances": {
            "author@t": {"role": "author", "home": self.board, "domains": ["d"]},
            "expert@t": {"role": "expert", "home": self.board, "domains": ["d"]}},
            "board": self.board}

    def run_cli(self, mod, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = mod.main(list(argv))
            except SystemExit as exc:
                rc = exc.code
        return rc, out.getvalue(), err.getvalue()

    def test_the_tag_is_accepted_end_to_end(self):
        path = bd.create_ticket(self.board, "expert@t", "Verify lem:x", "Verify it.", "A packet.",
                                kind="verify", as_instance="human", workspace=self.ws,
                                cowork="flat-section", perms=ac.load_permissions(
                                    os.path.join(PLUGIN, "permissions.json")))
        with open(path, encoding="utf-8") as fh:
            fm, body = ac.read_frontmatter(fh.read())
        self.assertEqual("flat-section", fm["cowork"])
        self.assertEqual([], ac.validate_ticket(fm, body))
        self.assertIn("slug", " ".join(ac.validate_ticket(dict(fm, cowork="Bad Slug"))))
        # the inbox core: --cowork parses, selects only the tag, lifts the cap
        core = ac.inbox_core
        args = core.parser("t").parse_args(["--cowork", "flat-section", "--json"])
        self.assertEqual("flat-section", args.cowork)
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            core.parser("t").parse_args(["--cowork", "a", "--campaign", "b"])
        out = io.StringIO()
        rc = core.run(args, "expert@t", self.board, 3,
                      lambda m: {"how": "skill", "target": "x", "why": "y"}, out=out)
        self.assertEqual(0, rc)
        doc = json.loads(out.getvalue())
        self.assertEqual(["flat-section"], [r["cowork"] for r in doc["take"]])
        self.assertIsNone(doc["limit"])                     # no cut of three
        # the plan file and the state
        rc, out, err = self.run_cli(cowork, "--board", self.board, "new", "flat-section",
                                    "--goal", "Land the flat section")
        self.assertEqual(0, rc, err)
        plan = os.path.join(self.board, "cowork", "flat-section.md")
        with open(plan, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("status: active", text)
        self.assertIn("Land the flat section", text)
        self.assertNotIn("{{", text)
        self.assertEqual(2, self.run_cli(cowork, "--board", self.board, "new",
                                         "flat-section")[0])          # exists: resume
        rc, out, _ = self.run_cli(cowork, "--board", self.board, "status", "flat-section",
                                  "--json")
        st = json.loads(out)
        self.assertEqual("WAITING", st["state"])
        rc, out, _ = self.run_cli(cowork, "--board", self.board, "list")
        self.assertIn("flat-section", out)
        self.assertIn("WAITING", out)

    def test_board_cli_has_the_flag(self):
        buf = io.StringIO()
        with self.assertRaises(SystemExit), redirect_stdout(buf):
            bd.main(["new", "--help"])
        self.assertIn("--cowork", buf.getvalue())


class CoworkDocs(unittest.TestCase):
    def read(self, *rel):
        with open(os.path.join(REPO, *rel), encoding="utf-8") as fh:
            return fh.read()

    def test_the_skill_and_the_charter(self):
        skill = self.read("academy", "skills", "cowork", "SKILL.md")
        charter = self.read("academy", "references", "orchestrator.md")
        self.assertIn("orchestrator.md", skill)
        self.assertIn("AskUserQuestion", skill)
        self.assertIn("--cowork <slug>", skill)
        self.assertIn("board/cowork/<slug>.md".replace("board", "<board>"), skill)
        for never in ("Write mathematics, tex or code", "Grade", "Set a status"):
            self.assertIn(never, charter)
        budget = self.read("academy", "references", "budget.md")
        self.assertIn("## Cowork", budget)
        self.assertRegex(budget, r"`--agents A` \(default 1\) \*\*binds\*\*")
        self.assertIn("cowork.py list", self.read("academy", "skills", "desk", "SKILL.md"))
        self.assertIn("--cowork <slug>", self.read("academy", "skills", "inbox", "SKILL.md"))


if __name__ == "__main__":
    unittest.main()
