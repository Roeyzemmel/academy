"""The Expert plugin's hooks, fed JSON fixture events on stdin in a sandbox academy."""

import json
import os
import unittest

import fixtures
import _academy as ac

REPORT = """Run A. CONFIRMED: every step of the obligation ledger is met.

1. Obligation ledger ...

VERDICT
subject: paper:lem:strip-bound
pass: 2026-09-28-T-0007
run: A
verdict: CONFIRMED
modulo: none
model: claude-fable-5-1
statement_hash: 0123456789abcdef
blocking: none
ticket: T-0007
"""

REFEREE_REPORT = """## Summary

A long paper on illumination; not yet ready for the coauthors.
Two blocking findings.

## Produced

- The referee report on author@bi: this packet.

## Established vs assumed

- **Not established:** no proof was checked line by line.

## Evidence

- The PDF `.build/main.pdf`, built 2026-09-28.

## Assessment

The paper ...

## Objective findings

### Terms used before definition

- **[blocking]** §2 — "unfolding" used before its definition.

## Decisions needed

None.

## Machine notes

None.

## Decision

REFEREE
subject: author@bi
ticket: T-0003
model: claude-fable-5-1
strength: full
"""


def stop_event(agent, text, **extra):
    ev = {"hook_event_name": "SubagentStop", "agent_type": agent, "agent_id": "abc123def",
          "last_assistant_message": text, "stop_hook_active": False}
    ev.update(extra)
    return ev


class LandVerdictTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()

    def tearDown(self):
        self.sb.close()

    def pass_dir(self):
        return os.path.join(self.sb.lib, "reviews", "paper", "lem-strip-bound",
                            "2026-09-28-T-0007")

    def test_lands_the_record(self):
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", REPORT))
        self.assertEqual(code, 0, err)
        path = os.path.join(self.pass_dir(), "A.md")
        self.assertTrue(os.path.isfile(path), out)
        with open(path, encoding="utf-8") as fh:
            meta, body = ac.read_frontmatter(fh.read())
        self.assertEqual(meta["verdict"], "CONFIRMED")
        self.assertEqual(meta["statement_hash"], "0123456789abcdef")
        self.assertTrue(meta["run_id"].startswith("rv-"))
        self.assertTrue(meta["run_id"].endswith("-abc123"))
        self.assertEqual(meta["agent"], "expert:rigor-reviewer")
        self.assertEqual(meta["modulo"], [])
        self.assertIn("Obligation ledger", body)

    def test_never_overwrites(self):
        for _ in range(2):
            fixtures.run_script("land_verdict.py", stop_event("rigor-reviewer", REPORT))
        self.assertEqual(sorted(os.listdir(self.pass_dir())), ["A-2.md", "A.md"])

    def test_decision_table_reads_the_landed_file(self):
        import decision_table as dt
        fixtures.run_script("land_verdict.py", stop_event("expert:rigor-reviewer", REPORT))
        r = dt.decide(dt.read_record(os.path.join(self.pass_dir(), "A.md")))
        self.assertEqual(r["outcome"], "awaiting-b")

    def test_other_agents_are_ignored(self):
        for agent in ("expert:referee", "author:math-writer", "rigor-reviewer-x", ""):
            code, out, err = fixtures.run_script("land_verdict.py", stop_event(agent, REPORT))
            self.assertEqual((code, out), (0, None), agent)
        self.assertFalse(os.path.isdir(os.path.join(self.sb.lib, "reviews")))

    def test_other_plugin_namespace_is_ignored(self):
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("paper:rigor-reviewer", REPORT))
        self.assertIsNone(out)

    def test_missing_block_blocks_once_then_lands(self):
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", "No block."))
        self.assertEqual(out["decision"], "block")
        code, out, err = fixtures.run_script(
            "land_verdict.py", stop_event("expert:rigor-reviewer", "No block.",
                                          stop_hook_active=True))
        folder = os.path.join(self.sb.lib, "reviews", "_unsorted")
        found = [f for dp, dn, fn in os.walk(folder) for f in fn]
        self.assertEqual(found, ["X-noverdict.md"])

    def test_reads_the_agent_transcript(self):
        tr = self.sb.write("tr.jsonl", "\n".join(json.dumps(r) for r in [
            {"type": "user", "message": {"role": "user", "content": "brief"}},
            {"type": "assistant", "message": {"role": "assistant",
                                              "content": [{"type": "text", "text": REPORT}]}},
        ]) + "\n")
        ev = stop_event("expert:rigor-reviewer", "")
        del ev["last_assistant_message"]
        ev["agent_transcript_path"] = tr
        fixtures.run_script("land_verdict.py", ev)
        self.assertTrue(os.path.isfile(os.path.join(self.pass_dir(), "A.md")))


class LandRefereeTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        tpath = os.path.join(self.sb.board, "expert@ts", "T-0003-referee-the-paper.md")
        meta = {"id": "T-0003", "title": "Referee the paper", "kind": "referee",
                "from": "author@bi", "to": "expert@ts", "status": "in-progress",
                "priority": "normal", "ask": "Referee it.", "deliverable": "A packet.",
                "refs": [], "blocks": [], "waiting_on": [],
                "budget": {"runs": 1, "max_model": "fable"}, "packets": [],
                "created": "2026-09-28", "updated": "2026-09-28"}
        ac.atomic_write(tpath, ac.new_ticket(meta))
        self.tpath = tpath

    def tearDown(self):
        self.sb.close()

    def packets(self):
        d = os.path.join(self.sb.board, "packets", "expert@ts")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def test_lands_packet_and_copy(self):
        code, out, err = fixtures.run_script("land_referee.py",
                                             stop_event("expert:referee", REFEREE_REPORT))
        self.assertEqual(code, 0, err)
        pk = self.packets()
        self.assertEqual(len(pk), 1, (out, err))
        with open(os.path.join(self.sb.board, "packets", "expert@ts", pk[0]),
                  encoding="utf-8") as fh:
            meta, body = ac.read_frontmatter(fh.read())
        self.assertEqual(ac.validate_packet(meta, body), [])
        self.assertEqual((meta["kind"], meta["by"], meta["ticket"]),
                         ("referee", "expert@ts/referee", "T-0003"))
        self.assertIn("## Objective findings", body)
        self.assertNotIn("REFEREE", body)
        copies = os.listdir(os.path.join(self.sb.lib, "reviews", "referee", "author-bi"))
        self.assertEqual(len(copies), 1)
        with open(self.tpath, encoding="utf-8") as fh:
            tmeta, _ = ac.read_frontmatter(fh.read())
        self.assertEqual(tmeta["packets"], [meta["packet"]])

    def test_wraps_a_report_not_in_packet_shape(self):
        text = "# My report\n\nThe paper is fine.\n\n## Findings\n\n- one\n\n" \
               "REFEREE\nsubject: author@bi\nticket: none\nmodel: claude-opus-5-5\n"
        code, out, err = fixtures.run_script("land_referee.py",
                                             stop_event("expert:referee", text))
        pk = self.packets()
        self.assertEqual(len(pk), 1, err)
        with open(os.path.join(self.sb.board, "packets", "expert@ts", pk[0]),
                  encoding="utf-8") as fh:
            meta, body = ac.read_frontmatter(fh.read())
        self.assertEqual(ac.validate_packet(meta, body), [])
        self.assertIn("## Report", body)
        self.assertIn("#### Findings", body)
        self.assertIn("reduced-strength", body)
        self.assertIn("reduced strength", meta["title"])
        self.assertIsNone(meta["ticket"])

    def test_unknown_ticket_is_noted(self):
        text = REFEREE_REPORT.replace("T-0003", "T-0999")
        fixtures.run_script("land_referee.py", stop_event("expert:referee", text))
        with open(os.path.join(self.sb.board, "packets", "expert@ts", self.packets()[0]),
                  encoding="utf-8") as fh:
            meta, body = ac.read_frontmatter(fh.read())
        self.assertIn("T-0999", body)
        self.assertIsNone(meta["ticket"])

    def test_other_agents_ignored_and_block_once(self):
        code, out, err = fixtures.run_script("land_referee.py",
                                             stop_event("expert:clerk", REFEREE_REPORT))
        self.assertIsNone(out)
        code, out, err = fixtures.run_script("land_referee.py",
                                             stop_event("expert:referee", "no block"))
        self.assertEqual(out["decision"], "block")
        self.assertEqual(self.packets(), [])


class BlindGuardTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        self.reviews = os.path.join(self.sb.lib, "reviews")

    def tearDown(self):
        self.sb.close()

    def ev(self, tool, agent="expert:rigor-reviewer", **ti):
        return {"hook_event_name": "PreToolUse", "tool_name": tool, "agent_type": agent,
                "tool_input": ti, "cwd": self.sb.bi}

    def decision(self, ev):
        code, out, err = fixtures.run_script("review_blind_guard.py", ev)
        self.assertEqual(code, 0, err)
        return (out or {}).get("hookSpecificOutput", {}).get("permissionDecision")

    def test_read_of_a_record_denied(self):
        p = os.path.join(self.reviews, "paper", "x", "p", "A.md")
        self.assertEqual(self.decision(self.ev("Read", file_path=p)), "deny")

    def test_search_containing_reviews_denied(self):
        self.assertEqual(self.decision(self.ev("Grep", pattern="x", path=self.sb.lib)),
                         "deny")
        self.assertEqual(self.decision(self.ev("Glob", pattern="**/*.md",
                                               path=self.reviews)), "deny")

    def test_allowed_reads(self):
        self.assertIsNone(self.decision(self.ev("Read", file_path=os.path.join(
            self.sb.lib, "ABC21.txt"))))
        self.assertIsNone(self.decision(self.ev("Grep", pattern="x", path=os.path.join(
            self.sb.lib, "ABC21.src"))))
        self.assertIsNone(self.decision(self.ev("Grep", pattern="x")))   # cwd = BI home

    def test_other_agents_pass(self):
        p = os.path.join(self.reviews, "paper", "x", "p", "A.md")
        for agent in ("expert:review-chair", "", "author:math-writer"):
            self.assertIsNone(self.decision(self.ev("Read", agent=agent, file_path=p)))


class LibraryEditCheckTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()

    def tearDown(self):
        self.sb.close()

    def ctx(self, ev):
        code, out, err = fixtures.run_script("library_edit_check.py", ev)
        self.assertEqual(code, 0, err)
        return (out or {}).get("hookSpecificOutput", {}).get("additionalContext")

    def edit(self, path):
        return {"hook_event_name": "PostToolUse", "tool_name": "Write",
                "tool_input": {"file_path": path}, "cwd": self.sb.root}

    def test_good_card_is_silent(self):
        p = self.sb.write("papers/cards/ABC21/lemma-2-1.md", fixtures.card_text())
        self.assertIsNone(self.ctx(self.edit(p)))

    def test_card_quote_mismatch_warns(self):
        p = self.sb.write("papers/cards/ABC21/lemma-2-1.md",
                          fixtures.card_text(quote="Something the paper never says at all."))
        self.assertIn("quote not found", self.ctx(self.edit(p)))

    def test_cached_file_without_row_warns(self):
        p = self.sb.write("papers/NEW22.meta", "key: NEW22\n")
        self.assertIn("NEW22", self.ctx(self.edit(p)))

    def test_outside_the_library_silent(self):
        p = self.sb.write("bi/cards/ABC21/x.md", "not a card")
        self.assertIsNone(self.ctx(self.edit(p)))

    def test_shell_in_library_reports_fresh_gaps_only(self):
        self.sb.write("papers/NEW22.pdf", "x")
        ev = {"hook_event_name": "PostToolUse", "tool_name": "Bash",
              "tool_input": {"command": "curl -o NEW22.pdf https://x"}, "cwd": self.sb.lib}
        self.assertIn("NEW22", self.ctx(ev))
        old = os.path.join(self.sb.lib, "NEW22.pdf")
        os.utime(old, (1, 1))
        self.assertIsNone(self.ctx(ev))
        ev["cwd"] = self.sb.bi
        os.utime(old, None)
        self.assertIsNone(self.ctx(ev))           # not in the library, not named


if __name__ == "__main__":
    unittest.main()
