"""Tests for academy/scripts/board.py and packets.py (docs/protocol.md, packet-template.md).

Run from the repo root:  py -m unittest discover academy/tests
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
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts"))

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import packets as pk  # noqa: E402

DATE = "2026-09-28"
DECISION_BODY = """
## Summary

Two runs CONFIRMED $|h| \\le 2$.

## Produced

- Verdicts: `file:expert@main/reviews/paper/x/`.

## Established vs assumed

- **Established:** paper:lem:x (proposed proved).

## Evidence

- Run A, run B.

## Decisions needed

### D1. Recolour now?

- (a) Yes, recolour now.
- (b) Wait.
- Recommendation: (a), both runs agree.

### D2. Open a follow-up?

- (a) Yes.
- (b) No.
- (c) Ask the referee.
- Recommendation: (b), nothing depends on it.

## Machine notes

None.

## Decision
"""

INFO_BODY = DECISION_BODY.split("## Decisions needed")[0] + \
    "## Decisions needed\n\nNone.\n\n## Machine notes\n\nNone.\n\n## Decision\n"


def make_workspace(root):
    ws = {"instances": {
        "expert@main": {"role": "expert", "home": os.path.join(root, "papers"),
                      "domains": ["dom-a"]},
        "author@main": {"role": "author", "home": os.path.join(root, "paperhome"),
                      "domains": ["dom-a"], "ns": "paper"},
        "researcher@r1": {"role": "researcher", "home": os.path.join(root, "r1"),
                          "domains": ["dom-b"], "ns": "s1"}},
        "board": os.path.join(root, "board").replace("\\", "/")}
    path = os.path.join(root, "workspace.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(ws, fh)
    return ac.load_workspace(path), path


class BoardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="academy-board-")
        self.ws, self.ws_path = make_workspace(self.tmp)
        self.board = self.ws["board"]
        os.makedirs(self.board)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def new(self, **kw):
        args = dict(to="expert@main", title="Check Lemma 4.2", ask="Verify paper:lem:x",
                    deliverable="A verification packet", kind="verify",
                    as_instance="author@main", agent="math-writer", workspace=self.ws,
                    date=DATE, budget={"runs": 2, "max_model": "opus"})
        args.update(kw)
        return bd.create_ticket(self.board, **args)

    def read(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()


class TestTickets(BoardCase):
    def test_create_writes_valid_ticket_in_receiver_folder(self):
        p = self.new()
        self.assertEqual(os.path.dirname(p), os.path.join(self.board, "expert@main"))
        self.assertEqual(os.path.basename(p), "T-0001-check-lemma-4-2.md")
        text = self.read(p)
        self.assertNotIn("\r", text)
        meta, body = ac.read_frontmatter(text)
        self.assertEqual(ac.validate_ticket(meta, body), [])
        self.assertEqual(list(meta), [k for k in ac.TICKET_KEY_ORDER if k in meta])
        self.assertEqual(meta["from"], "author@main")
        self.assertEqual(meta["status"], "open")
        self.assertEqual(meta["domain"], "dom-a")          # receiver's first domain
        self.assertEqual(meta["budget"], {"runs": 2, "max_model": "opus"})
        self.assertEqual(ac.thread_lines(body),
                         [(DATE, "author@main/math-writer", "opened")])
        self.assertEqual(ac.write_frontmatter(meta, body), text)   # canonical

    def test_new_requires_as(self):
        with self.assertRaises(ac.AcademyError) as cm:
            bd.create_ticket(self.board, "expert@main", "T", "a", "d", workspace=self.ws)
        self.assertIn("--as", str(cm.exception))

    def test_new_applies_the_chain(self):
        with self.assertRaises(ac.AcademyError) as cm:
            bd.create_ticket(self.board, "researcher@r1", "T", "a", "d",
                             as_instance="author@main", workspace=self.ws)
        self.assertIn("final_to researcher", str(cm.exception))
        path = bd.create_ticket(self.board, "expert@main", "T", "a", "d", kind="research",
                                as_instance="author@main", workspace=self.ws,
                                final_to="researcher")
        meta, body = bd.read_ticket(path)
        self.assertEqual(meta["final_to"], "researcher")
        self.assertIn("author@main/main: opened", body)

    def test_namespaced_agent_is_written_bare(self):
        # agents carry plugin-namespaced names; the speaker is the bare one (protocol 1)
        p = self.new(agent="author:math-writer")
        _, body = ac.read_frontmatter(self.read(p))
        self.assertEqual(ac.thread_lines(body), [(DATE, "author@main/math-writer", "opened")])
        tid = bd.read_ticket(p)[0]["id"]
        bd.append_to_ticket(self.board, tid, "a note", as_instance="expert@main",
                            agent="expert:librarian", date=DATE)
        bd.transition_ticket(self.board, tid, "accepted", as_instance="expert@main",
                             agent="expert:librarian", date=DATE)
        _, body = ac.read_frontmatter(self.read(p))
        self.assertEqual([w for _d, w, _t in ac.thread_lines(body)],
                         ["author@main/math-writer", "expert@main/librarian",
                          "expert@main/librarian"])
        self.assertEqual(bd.bare_agent(" scientist:test-engineer "), "test-engineer")
        self.assertEqual(bd.bare_agent(""), "")

    def test_ids_increase_and_default_budget(self):
        self.new()
        p2 = self.new(title="Second", budget=None)
        meta, _ = bd.read_ticket(p2)
        self.assertEqual(meta["id"], "T-0002")
        self.assertEqual(meta["budget"], ac.CONFIG_DEFAULTS["budget"]["ticketDefault"])

    def test_create_rejects_unknown_receiver(self):
        with self.assertRaises(ac.AcademyError):
            self.new(to="scientist@nowhere")
        with self.assertRaises(ac.AcademyError):
            self.new(to="not an instance")
        self.assertFalse(os.path.exists(os.path.join(self.board, ".ids", "next-ticket")))

    def test_human_ticket_goes_to_human_folder(self):
        p = self.new(to="human", as_instance="expert@main", agent="librarian")
        self.assertEqual(os.path.basename(os.path.dirname(p)), "human")

    def test_list_filters_and_order(self):
        self.new(title="A", priority="low")
        self.new(title="B", priority="high")
        self.new(title="C", to="researcher@r1", as_instance="human", agent="")
        rows = bd.list_tickets(self.board, to="expert@main")
        self.assertEqual([r["title"] for r in rows], ["B", "A"])
        self.assertEqual(len(bd.list_tickets(self.board)), 3)
        bd.transition_ticket(self.board, "T-0001", "cancelled", reason="not needed",
                             as_instance="author@main", date=DATE)
        self.assertEqual(len(bd.list_tickets(self.board)), 2)
        self.assertEqual(len(bd.list_tickets(self.board, include_terminal=True)), 3)
        self.assertEqual([r["id"] for r in bd.list_tickets(self.board, status="cancelled")],
                         ["T-0001"])

    def test_non_ticket_files_are_ignored(self):
        self.new()
        os.makedirs(os.path.join(self.board, "human"), exist_ok=True)
        for name in ("RESUME.md", "SUMMARY.md"):
            with open(os.path.join(self.board, "human", name), "w") as fh:
                fh.write("# free markdown\n")
        os.makedirs(os.path.join(self.board, "deep-dives"), exist_ok=True)
        with open(os.path.join(self.board, "deep-dives", "T-0009-x.md"), "w") as fh:
            fh.write("---\nid: T-0009\n---\n")
        self.assertEqual(len(bd.list_tickets(self.board)), 1)

    def test_lifecycle_by_parties(self):
        self.new()
        with self.assertRaises(ac.AcademyError):      # the sender cannot accept
            bd.transition_ticket(self.board, "T-0001", "accepted", as_instance="author@main")
        with self.assertRaises(ac.AcademyError):      # a stranger cannot either
            bd.transition_ticket(self.board, "T-0001", "accepted",
                                 as_instance="researcher@r1")
        bd.transition_ticket(self.board, "T-0001", "accepted", as_instance="expert@main",
                             agent="review-chair", date=DATE)
        bd.transition_ticket(self.board, "T-0001", "in-progress", as_instance="expert@main",
                             date=DATE)
        with self.assertRaises(ac.AcademyError):      # delivered needs a result
            bd.transition_ticket(self.board, "T-0001", "delivered", as_instance="expert@main")
        bd.transition_ticket(self.board, "T-0001", "delivered", result="CONFIRMED x2",
                             as_instance="expert@main", date=DATE)
        with self.assertRaises(ac.AcademyError):      # a return needs a reason
            bd.transition_ticket(self.board, "T-0001", "in-progress",
                                 as_instance="author@main")
        p = bd.transition_ticket(self.board, "T-0001", "closed", as_instance="author@main",
                                 date=DATE)
        meta, body = bd.read_ticket(p)
        self.assertEqual(meta["status"], "closed")
        self.assertEqual(meta["result"], "CONFIRMED x2")
        self.assertEqual(ac.validate_ticket(meta, body), [])
        texts = [t for _d, _w, t in ac.thread_lines(body)]
        self.assertEqual(texts, ["opened", "status open -> accepted",
                                 "status accepted -> in-progress",
                                 "set result: CONFIRMED x2",
                                 "status in-progress -> delivered",
                                 "status delivered -> closed"])
        whos = [w for _d, w, _t in ac.thread_lines(body)]
        self.assertEqual(whos[1], "expert@main/review-chair")

    def test_reason_required_for_reject_and_cancel(self):
        self.new()
        with self.assertRaises(ac.AcademyError):
            bd.transition_ticket(self.board, "T-0001", "rejected", as_instance="expert@main")
        bd.transition_ticket(self.board, "T-0001", "rejected", reason="out of scope",
                             as_instance="expert@main", date=DATE)
        meta, body = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        self.assertEqual(ac.thread_lines(body)[-1][2], "status open -> rejected: out of scope")

    def test_human_may_reopen_terminal(self):
        self.new()
        bd.transition_ticket(self.board, "T-0001", "cancelled", reason="x",
                             as_instance="author@main")
        bd.transition_ticket(self.board, "T-0001", "open")      # human, no party
        meta, _ = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        self.assertEqual(meta["status"], "open")

    def test_blocked_mirrors_blocks_and_clears_waiting_on(self):
        self.new(title="first")
        self.new(title="second", to="researcher@r1", as_instance="human", agent="")
        with self.assertRaises(ac.AcademyError):      # blocked needs waiting_on
            bd.transition_ticket(self.board, "T-0001", "blocked", as_instance="expert@main")
        bd.transition_ticket(self.board, "T-0001", "blocked", waiting_on=["T-0002"],
                             as_instance="expert@main", date=DATE)
        m1, b1 = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        m2, _ = bd.read_ticket(ac.find_ticket(self.board, "T-0002"))
        self.assertEqual(m1["waiting_on"], ["T-0002"])
        self.assertEqual(m2["blocks"], ["T-0001"])
        self.assertEqual(ac.validate_ticket(m1, b1), [])
        bd.transition_ticket(self.board, "T-0001", "accepted", as_instance="expert@main")
        m1, b1 = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        self.assertEqual(m1["waiting_on"], [])
        self.assertEqual(ac.validate_ticket(m1, b1), [])

    # -- blocking: pending versus dead route (campaign design section 9) --------------

    def block_dead(self, tid="T-0001", **kw):
        args = dict(blocked_by="paper:lem:x", reopen_if="a new invariant",
                    reason="tried the sum formula and the induction; both circular",
                    as_instance="expert@main", date=DATE)
        args.update(kw)
        return bd.transition_ticket(self.board, tid, "blocked", **args)

    def test_blocked_with_neither_kind_fails(self):
        self.new()
        with self.assertRaises(ac.AcademyError):
            bd.transition_ticket(self.board, "T-0001", "blocked", as_instance="expert@main")
        with self.assertRaises(ac.AcademyError):      # blocked_by alone is not a dead route
            bd.transition_ticket(self.board, "T-0001", "blocked", blocked_by="T-0009",
                                 reason="tried x", as_instance="expert@main")

    def test_both_kinds_at_once_fails(self):
        self.new()
        with self.assertRaises(ac.AcademyError):
            self.block_dead(waiting_on=["human"])

    def test_dead_route_without_reopen_if_fails(self):
        self.new()
        with self.assertRaises(ac.AcademyError):
            self.block_dead(reopen_if=None)

    def test_dead_route_needs_a_thread_line_of_what_was_tried(self):
        self.new()
        with self.assertRaises(ac.AcademyError):
            self.block_dead(reason="")

    def test_dead_route_block_records_fields_and_thread(self):
        self.new()
        p = self.block_dead()
        meta, body = bd.read_ticket(p)
        self.assertEqual(meta["blocked_by"], "paper:lem:x")
        self.assertEqual(meta["reopen_if"], "a new invariant")
        self.assertEqual(ac.validate_ticket(meta, body), [])
        self.assertTrue(any(t.startswith("tried: ") for _d, _w, t in ac.thread_lines(body)))
        # validate_ticket alone rejects the same ticket with the line removed
        bare = body.split("- ")[0] + "- %s author@main: opened\n" % DATE
        self.assertTrue(any("tried" in x for x in ac.validate_ticket(meta, bare)))
        self.assertTrue(any("both" in x or "waiting_on" in x for x in
                            ac.validate_ticket(dict(meta, waiting_on=["human"]))))

    def test_reopen_needs_reopen_text_and_only_blocked_to_accepted(self):
        self.new()
        self.block_dead()
        with self.assertRaises(ac.AcademyError):      # reopen without --reopen
            bd.transition_ticket(self.board, "T-0001", "accepted", as_instance="expert@main")
        with self.assertRaises(ac.AcademyError):      # nothing else reopens one
            bd.transition_ticket(self.board, "T-0001", "in-progress",
                                 reopen="a new construction", as_instance="expert@main")
        with self.assertRaises(ac.AcademyError):      # the sender cannot reopen
            bd.transition_ticket(self.board, "T-0001", "accepted",
                                 reopen="a new construction", as_instance="author@main")
        p = bd.transition_ticket(self.board, "T-0001", "accepted",
                                 reopen="a new construction via Prym forms",
                                 as_instance="expert@main", date=DATE)
        meta, body = bd.read_ticket(p)
        self.assertEqual(meta["status"], "accepted")
        self.assertNotIn("blocked_by", meta)
        self.assertNotIn("reopen_if", meta)
        self.assertEqual(ac.validate_ticket(meta, body), [])
        texts = [t for _d, _w, t in ac.thread_lines(body)]
        self.assertIn("reopened: a new construction via Prym forms", texts)

    def test_sender_may_cancel_a_dead_route_with_a_reason(self):
        self.new()
        self.block_dead()
        with self.assertRaises(ac.AcademyError):
            bd.transition_ticket(self.board, "T-0001", "cancelled", as_instance="author@main")
        p = bd.transition_ticket(self.board, "T-0001", "cancelled", reason="dropped",
                                 as_instance="author@main", date=DATE)
        meta, body = bd.read_ticket(p)
        self.assertEqual(ac.validate_ticket(meta, body), [])

    def test_pending_block_reopens_without_reopen_text(self):
        self.new()
        bd.transition_ticket(self.board, "T-0001", "blocked", waiting_on=["human"],
                             as_instance="expert@main", date=DATE)
        bd.transition_ticket(self.board, "T-0001", "accepted", as_instance="expert@main")

    def test_the_core_skips_a_ticket_blocked_through_the_cli_path(self):
        self.new()
        self.block_dead()
        rows, _t = ac.inbox_core.select(self.board, "expert@main", 3,
                                        route=lambda m: {"how": "skill", "target": "x",
                                                         "why": "y"})
        self.assertEqual(rows, [])

    def test_cli_blocked_by_and_reopen_flags(self):
        self.new()
        rc = bd.main(["--board", self.board, "transition", "T-0001", "blocked",
                      "--blocked-by", "paper:lem:x", "--reopen-if", "a new invariant",
                      "--reason", "tried the sum formula", "--as", "expert@main"])
        self.assertEqual(rc, 0)
        rc = bd.main(["--board", self.board, "transition", "T-0001", "accepted",
                      "--reopen", "a new mechanism", "--as", "expert@main"])
        self.assertEqual(rc, 0)
        meta, _ = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        self.assertEqual(meta["status"], "accepted")

    def test_cli_new_campaign_tags_the_ticket_and_inbox_selects_it(self):
        buf = io.StringIO()
        base = ["--board", self.board, "--workspace", self.ws_path, "new", "--to", "expert@main",
                "--title", "Tagged", "--ask", "a", "--deliverable", "d", "--kind", "lookup",
                "--as", "author@main"]
        with redirect_stdout(buf):
            self.assertEqual(0, bd.main(base + ["--campaign", "paper:thm:x"]))
            self.assertEqual(0, bd.main([*base[:-2], "--title", "Untagged", "--as",
                                         "author@main"]))
        meta, _ = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        self.assertEqual("paper:thm:x", meta["campaign"])
        self.assertEqual([], ac.validate_ticket(meta))
        meta2, _ = bd.read_ticket(ac.find_ticket(self.board, "T-0002"))
        self.assertNotIn("campaign", meta2)                  # omitted, not written empty
        route = lambda m: {"how": "skill", "target": "x", "why": "y"}  # noqa: E731
        rows, _t = ac.inbox_core.select(self.board, "expert@main", 3, route=route,
                                        campaign="paper:thm:x")
        self.assertEqual(["T-0001"], [r["id"] for r in rows])
        self.assertEqual("paper:thm:x", rows[0]["campaign"])

    def test_create_ticket_campaign_argument(self):
        p = self.new(campaign="paper:thm:x")
        self.assertEqual("paper:thm:x", bd.read_ticket(p)[0]["campaign"])
        self.assertNotIn("campaign", bd.read_ticket(self.new())[0])
        with self.assertRaises(ac.AcademyError):
            self.new(campaign="two\nlines")

    def test_append_is_append_only(self):
        p = self.new()
        old = bd.read_ticket(p)[1]
        bd.append_to_ticket(self.board, "T-0001", "first line\nsecond line",
                            as_instance="expert@main", agent="clerk", date=DATE)
        new = bd.read_ticket(p)[1]
        self.assertTrue(ac.thread_is_append_only(old, new))
        self.assertEqual(ac.thread_lines(new)[-1],
                         (DATE, "expert@main/clerk", "first line\nsecond line"))

    def test_cli_roundtrip(self):
        base = ["--board", self.board, "--workspace", self.ws_path]
        out = io.StringIO()
        with redirect_stdout(out):
            rc = bd.main(base + ["new", "--to", "expert@main", "--title", "CLI ticket",
                                 "--ask", "ask", "--deliverable", "done",
                                 "--as", "human", "--refs", "paper:lem:x, bib:LMW16",
                                 "--runs", "2"])
        self.assertEqual(rc, 0)
        meta, _ = bd.read_ticket(out.getvalue().strip())
        self.assertEqual(meta["from"], "human")
        self.assertEqual(meta["refs"], ["paper:lem:x", "bib:LMW16"])
        self.assertEqual(meta["budget"]["runs"], 2)
        out = io.StringIO()
        with redirect_stdout(out):
            bd.main(base + ["list", "--json"])
        self.assertEqual(json.loads(out.getvalue())[0]["id"], "T-0001")
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            rc = bd.main(base + ["transition", "T-0001", "accepted", "--as", "author@main"])
        self.assertEqual(rc, 1)
        self.assertIn("receiver", err.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bd.main(base + ["append", "T-0001", "--text", "hello"]), 0)
            self.assertEqual(bd.main(base + ["show", "T-0001"]), 0)


class TestPackets(BoardCase):
    def packet(self, body=DECISION_BODY, ticket=None, **kw):
        return pk.create_packet(self.board, "expert@main", kw.pop("title", "Verify lem x"),
                                kind="verification", by="expert@main/review-chair",
                                ticket=ticket, subject=["paper:lem:x"],
                                status_before="sketch", status_proposed="proved",
                                body=body, workspace=self.ws, date=DATE, **kw)

    def test_new_from_template_is_valid(self):
        p = pk.create_packet(self.board, "author@main", "From the template", date=DATE,
                             workspace=self.ws)
        self.assertEqual(p, os.path.join(self.board, "packets", "author@main",
                                         "P-0001-from-the-template.md"))
        meta, body = pk.read_packet(p)
        self.assertEqual(ac.validate_packet(meta, body), [])
        self.assertEqual(meta["state"], "open")
        self.assertEqual(meta["by"], "author@main")
        self.assertEqual(list(meta), list(ac.PACKET_KEY_ORDER))
        self.assertNotIn("\r", self.read(p))

    def test_new_rejects_bad_input(self):
        with self.assertRaises(ac.AcademyError):
            pk.create_packet(self.board, "author@nowhere", "x", workspace=self.ws)
        with self.assertRaises(ac.AcademyError):
            self.packet(body="## Summary\n\nno other sections\n")
        with self.assertRaises(ac.AcademyError):
            self.packet(body=DECISION_BODY + "\n- D1: (a) | 2026-09-28 | human\n")
        with self.assertRaises(ac.AcademyError):    # the linked ticket must exist
            self.packet(ticket="T-0042")

    def test_new_links_ticket(self):
        bd.create_ticket(self.board, "expert@main", "Check", "ask", "done", "verify",
                         as_instance="author@main", workspace=self.ws, date=DATE)
        self.packet(ticket="T-0001")
        meta, body = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        self.assertEqual(meta["packets"], ["P-0001"])
        self.assertEqual(ac.thread_lines(body)[-1],
                         (DATE, "expert@main/review-chair", "packet P-0001 filed: Verify lem x"))
        self.assertEqual(ac.validate_ticket(meta, body), [])

    def test_ticket_and_packet_ids_are_independent(self):
        bd.create_ticket(self.board, "expert@main", "Check", "ask", "done",
                         as_instance="author@main", workspace=self.ws)
        p = self.packet()
        self.assertTrue(os.path.basename(p).startswith("P-0001-"))

    def test_list_open(self):
        self.packet(title="one")
        self.packet(title="two")
        pk.decide_packet(self.board, "P-0002", "a", 1, date=DATE)
        pk.decide_packet(self.board, "P-0002", "b", 2, date=DATE)
        rows = pk.list_packets(self.board, only_open=True)
        self.assertEqual([r["packet"] for r in rows], ["P-0001"])
        self.assertEqual(rows[0]["_pending"], [1, 2])
        self.assertEqual(len(pk.list_packets(self.board)), 2)
        self.assertEqual(pk.list_packets(self.board, instance="author@main"), [])

    def test_decide_writes_back_and_echoes(self):
        bd.create_ticket(self.board, "expert@main", "Check", "ask", "done", "verify",
                         as_instance="author@main", workspace=self.ws, date=DATE)
        self.packet(ticket="T-0001")
        path, k, decided = pk.decide_packet(self.board, "P-0001", "1", comment="go ahead",
                                            date=DATE)
        self.assertEqual((k, decided), (1, False))
        meta, body = pk.read_packet(path)
        self.assertEqual(meta["state"], "open")
        self.assertEqual(ac.packet_answers(body)[1], ("(a)", DATE, "human", "go ahead"))
        # the next call answers the first pending decision (D2) by default
        path, k, decided = pk.decide_packet(self.board, "P-0001", "other",
                                            comment="ask Barak first", date=DATE)
        self.assertEqual((k, decided), (2, True))
        meta, body = pk.read_packet(path)
        self.assertEqual(meta["state"], "decided")
        self.assertEqual(meta["decided"], DATE)
        self.assertEqual(ac.validate_packet(meta, body), [])
        _tm, tb = bd.read_ticket(ac.find_ticket(self.board, "T-0001"))
        lines = ac.thread_lines(tb)
        self.assertEqual(lines[-2], (DATE, "human",
                                     "decision on P-0001 D1: (a) Yes, recolour now.\n"
                                     "go ahead"))
        self.assertEqual(lines[-1], (DATE, "human", "decision on P-0001 D2: ask Barak first"))
        # the first line of each echo has the exact protocol form
        raw = ac.thread_lines(tb, raw=True)
        self.assertIn("- %s human: decision on P-0001 D1: (a) Yes, recolour now." % DATE, raw)

    def test_decide_last_line_wins(self):
        self.packet()
        pk.decide_packet(self.board, "P-0001", "a", 1, date=DATE)
        path, _k, _d = pk.decide_packet(self.board, "P-0001", "b", 1, date=DATE)
        _m, body = pk.read_packet(path)
        self.assertEqual(ac.packet_answers(body)[1][0], "(b)")
        self.assertEqual(body.count("- D1:"), 2)                # never deleted

    def test_decide_validation(self):
        self.packet()
        with self.assertRaises(ac.AcademyError):
            pk.decide_packet(self.board, "P-0001", "d", 1)       # D1 has no (d)
        with self.assertRaises(ac.AcademyError):
            pk.decide_packet(self.board, "P-0001", "a", 7)       # no D7
        with self.assertRaises(ac.AcademyError):
            pk.decide_packet(self.board, "P-0001", "other", 1)   # other needs text
        with self.assertRaises(ac.AcademyError):
            pk.decide_packet(self.board, "P-0001", "ack")        # not informational
        with self.assertRaises(ac.AcademyError):
            pk.decide_packet(self.board, "P-0001", "z")
        with self.assertRaises(ac.AcademyError):
            pk.decide_packet(self.board, "P-0099", "a")
        self.assertEqual(pk._choice_letter("3"), "c")
        self.assertEqual(pk._choice_letter("(b)"), "b")

    def test_informational_ack(self):
        self.packet(body=INFO_BODY)
        with self.assertRaises(ac.AcademyError):
            pk.decide_packet(self.board, "P-0001", "a")
        path, k, decided = pk.decide_packet(self.board, "P-0001", "ack", date=DATE)
        self.assertEqual((k, decided), (0, True))
        meta, body = pk.read_packet(path)
        self.assertIn("- D0: ack | %s | human" % DATE, body)
        self.assertEqual(meta["state"], "decided")

    def test_withdrawn_cannot_be_decided(self):
        p = self.packet()
        meta, body = pk.read_packet(p)
        meta["state"] = "withdrawn"
        pk.write_packet(p, meta, body)
        with self.assertRaises(ac.AcademyError):
            pk.decide_packet(self.board, "P-0001", "a")

    def test_cli(self):
        base = ["--board", self.board, "--workspace", self.ws_path]
        bodyfile = os.path.join(self.tmp, "body.md")
        with open(bodyfile, "w", encoding="utf-8") as fh:
            fh.write(DECISION_BODY)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(pk.main(base + ["new", "--instance", "expert@main", "--title",
                                             "CLI", "--kind", "verification",
                                             "--subject", "paper:lem:x",
                                             "--body", bodyfile]), 0)
            self.assertEqual(pk.main(base + ["decide", "P-0001", "--choice", "2",
                                             "--decision", "1"]), 0)
        out = io.StringIO()
        with redirect_stdout(out):
            pk.main(base + ["list", "--open", "--json"])
        rows = json.loads(out.getvalue())
        self.assertEqual(rows[0]["_pending"], [2])
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            self.assertEqual(pk.main(base + ["decide", "P-0001", "--choice", "q"]), 1)


if __name__ == "__main__":
    unittest.main()
