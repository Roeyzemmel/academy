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

- The referee report on author@main: this packet.

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
subject: author@main
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

    def test_the_gap_class_is_kept_in_the_record(self):
        text = REPORT.replace("verdict: CONFIRMED", "verdict: GAP").replace(
            "blocking: none", "blocking: step 2\ngap_class: statement")
        fixtures.run_script("land_verdict.py", stop_event("expert:rigor-reviewer", text))
        with open(os.path.join(self.pass_dir(), "A.md"), encoding="utf-8") as fh:
            meta, _ = ac.read_frontmatter(fh.read())
        self.assertEqual(meta["gap_class"], "statement")

    def test_idempotent_by_run(self):
        # 2026-10-08: a second landing of the same run made A-2.md duplicates
        for _ in range(2):
            code, out, err = fixtures.run_script("land_verdict.py",
                                                 stop_event("rigor-reviewer", REPORT))
        self.assertEqual(sorted(os.listdir(self.pass_dir())), ["A.md"])
        self.assertIn("already landed", out["systemMessage"])
        # the same reviewer with a changed report: rewritten in place, same run id
        with open(os.path.join(self.pass_dir(), "A.md"), encoding="utf-8") as fh:
            rid = ac.read_frontmatter(fh.read())[0]["run_id"]
        code, out, err = fixtures.run_script(
            "land_verdict.py", stop_event("rigor-reviewer", "Amended.\n\n" + REPORT))
        self.assertEqual(sorted(os.listdir(self.pass_dir())), ["A.md"])
        with open(os.path.join(self.pass_dir(), "A.md"), encoding="utf-8") as fh:
            meta, body = ac.read_frontmatter(fh.read())
        self.assertEqual(meta["run_id"], rid)
        self.assertIn("Amended.", body)
        self.assertIn("rewritten in place", out["systemMessage"])

    def test_another_reviewer_on_the_same_run_is_said(self):
        fixtures.run_script("land_verdict.py", stop_event("rigor-reviewer", REPORT))
        code, out, err = fixtures.run_script(
            "land_verdict.py", stop_event("rigor-reviewer", REPORT, agent_id="zzz999"))
        self.assertEqual(sorted(os.listdir(self.pass_dir())), ["A-2.md", "A.md"])
        self.assertIn("another reviewer", out["systemMessage"])

    def test_placeholder_pass_is_never_filed_silently(self):
        # 2026-10-07: "pass: not in brief" became reviews/paper/<slug>/not-in-brief/B.md
        bad = REPORT.replace("pass: 2026-09-28-T-0007", "pass: not in brief") \
            .replace("statement_hash: 0123456789abcdef", "statement_hash: not in brief")
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", bad))
        self.assertEqual(out["decision"], "block")
        self.assertIn("pass and statement_hash", out["reason"])
        code, out, err = fixtures.run_script(
            "land_verdict.py", stop_event("expert:rigor-reviewer", bad,
                                          stop_hook_active=True))
        subj = os.path.join(self.sb.lib, "reviews", "paper", "lem-strip-bound")
        self.assertEqual(os.listdir(subj), ["_unfiled"])
        self.assertIn("ERROR: not filed into a pass", out["systemMessage"])

    REWORD = REPORT.replace("pass: 2026-09-28-T-0007", "pass: 2026-10-12-T-0347-reword") \
        .replace("run: A", "run: R\nmode: reword\nbase_pass: 2026-09-28-T-0007\n"
                           "base_hash: 0123456789abcdef\nreword_scope: weaker") \
        .replace("statement_hash: 0123456789abcdef", "statement_hash: fedcba9876543210")

    def test_a_reword_run_lands_as_R_with_its_fields(self):
        """T-0347: the reword run's record keeps mode, base_pass, base_hash, reword_scope."""
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", self.REWORD))
        self.assertEqual(code, 0, err)
        d = os.path.join(self.sb.lib, "reviews", "paper", "lem-strip-bound",
                         "2026-10-12-T-0347-reword")
        self.assertEqual(os.listdir(d), ["R.md"], out)
        with open(os.path.join(d, "R.md"), encoding="utf-8") as fh:
            meta, _ = ac.read_frontmatter(fh.read())
        self.assertEqual((meta["mode"], meta["base_pass"], meta["base_hash"],
                          meta["reword_scope"], meta["run"], meta["statement_hash"]),
                         ("reword", "2026-09-28-T-0007", "0123456789abcdef", "weaker", "R",
                          "fedcba9876543210"))
        # a reword block that says run A still lands as R
        fixtures.run_script("land_verdict.py", stop_event(
            "expert:rigor-reviewer", self.REWORD.replace("run: R", "run: A"),
            agent_id="other9"))
        self.assertEqual(sorted(os.listdir(d)), ["R-2.md", "R.md"])

    def test_a_reword_run_keeps_its_base_subject(self):
        """T-0476: a reword run on a renamed record names the base pass's subject."""
        text = self.REWORD.replace("subject: paper:lem:strip-bound",
                                   "subject: paper:cor:strip-bound") \
            .replace("reword_scope: weaker", "base_subject: paper:lem:strip-bound\n"
                                             "reword_scope: weaker")
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", text))
        self.assertEqual(code, 0, err)
        p = os.path.join(self.sb.lib, "reviews", "paper", "cor-strip-bound",
                         "2026-10-12-T-0347-reword", "R.md")
        with open(p, encoding="utf-8") as fh:
            meta, _ = ac.read_frontmatter(fh.read())
        self.assertEqual((meta["subject"], meta["base_subject"], meta["base_pass"]),
                         ("paper:cor:strip-bound", "paper:lem:strip-bound",
                          "2026-09-28-T-0007"))

    def test_a_reword_run_without_base_subject_records_none(self):
        fixtures.run_script("land_verdict.py",
                            stop_event("expert:rigor-reviewer", self.REWORD))
        p = os.path.join(self.sb.lib, "reviews", "paper", "lem-strip-bound",
                         "2026-10-12-T-0347-reword", "R.md")
        with open(p, encoding="utf-8") as fh:
            meta, _ = ac.read_frontmatter(fh.read())
        self.assertNotIn("base_subject", meta)

    def test_a_bare_base_subject_blocks(self):
        text = self.REWORD.replace("reword_scope: weaker", "base_subject: lem-strip-bound\n"
                                                           "reword_scope: weaker")
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", text))
        self.assertEqual(out["decision"], "block")
        self.assertIn("base_subject", out["reason"])

    def test_a_blind_record_carries_no_reword_fields(self):
        fixtures.run_script("land_verdict.py", stop_event("expert:rigor-reviewer", REPORT))
        with open(os.path.join(self.pass_dir(), "A.md"), encoding="utf-8") as fh:
            meta, _ = ac.read_frontmatter(fh.read())
        for k in ("mode", "base_pass", "base_hash", "reword_scope"):
            self.assertNotIn(k, meta)

    def test_a_suggested_dependency_is_kept_in_the_record(self):
        """2026-11-20: a CONFIRMED with add_dependency keeps the suggestion."""
        text = REPORT.replace("modulo: none", "modulo: none\nadd_dependency: paper:lem:y, "
                                              "bib:LMW16#Thm11")
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", text))
        self.assertEqual(code, 0, err)
        with open(os.path.join(self.pass_dir(), "A.md"), encoding="utf-8") as fh:
            meta, _ = ac.read_frontmatter(fh.read())
        self.assertEqual(meta["add_dependency"], ["paper:lem:y", "bib:LMW16#Thm11"])
        self.assertNotIn("mode", meta)

    def test_a_record_without_a_suggestion_has_no_amend_fields(self):
        fixtures.run_script("land_verdict.py", stop_event("expert:rigor-reviewer", REPORT))
        with open(os.path.join(self.pass_dir(), "A.md"), encoding="utf-8") as fh:
            meta, _ = ac.read_frontmatter(fh.read())
        for k in ("add_dependency", "amended_with", "mode"):
            self.assertNotIn(k, meta)

    def test_an_amend_run_lands_as_B_in_the_same_pass_with_its_fields(self):
        text = REPORT.replace("run: A", "run: B\nmode: amend\nbase_pass: 2026-09-28-T-0007\n"
                                        "base_hash: 0123456789abcdef\n"
                                        "amended_with: paper:lem:y")
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", text))
        self.assertEqual(code, 0, err)
        with open(os.path.join(self.pass_dir(), "B.md"), encoding="utf-8") as fh:
            meta, _ = ac.read_frontmatter(fh.read())
        self.assertEqual((meta["run"], meta["mode"], meta["base_pass"], meta["base_hash"],
                          meta["amended_with"]),
                         ("B", "amend", "2026-09-28-T-0007", "0123456789abcdef",
                          ["paper:lem:y"]))

    def test_an_amend_block_without_its_base_blocks(self):
        text = REPORT.replace("run: A", "run: B\nmode: amend\namended_with: paper:lem:y")
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", text))
        self.assertEqual(out["decision"], "block")
        self.assertIn("base_pass", out["reason"])

    def test_a_reword_block_without_its_base_blocks_once(self):
        bad = self.REWORD.replace("base_hash: 0123456789abcdef", "base_hash: not in brief")
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", bad))
        self.assertEqual(out["decision"], "block")
        self.assertIn("base_hash", out["reason"])

    def test_a_skipped_landing_is_visible(self):
        code, out, err = fixtures.run_script("land_verdict.py",
                                             stop_event("expert:rigor-reviewer", ""))
        self.assertIn("NOT landed", out["systemMessage"])

    def test_hook_landed_pair_is_a_valid_pair(self):
        import decision_table as dt
        fixtures.run_script("land_verdict.py", stop_event("expert:rigor-reviewer", REPORT))
        fixtures.run_script("land_verdict.py", stop_event(
            "expert:rigor-reviewer", REPORT.replace("run: A", "run: B"), agent_id="bbb222"))
        r = dt.decide(dt.read_record(os.path.join(self.pass_dir(), "A.md")),
                      dt.read_record(os.path.join(self.pass_dir(), "B.md")))
        self.assertNotEqual(r["outcome"], "invalid-pair", r)

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

    def handback_transcript(self, report, preamble=None):
        """A reviewer transcript that ends the way T-1193's run A did (T-1194): the
        report is a SubagentHandback call's message, then its tool result and the
        hook attachments; no assistant text after it."""
        blocks = ([{"type": "text", "text": preamble}] if preamble else []) + [
            {"type": "tool_use", "id": "toolu_1", "name": "SubagentHandback",
             "input": {"message": report}}]
        return self.sb.write("tr.jsonl", "\n".join(json.dumps(r) for r in [
            {"type": "user", "message": {"role": "user", "content": "brief"}},
            {"type": "assistant", "message": {"role": "assistant", "content": blocks}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1",
                 "content": [{"type": "text", "text": "Report delivered to your caller."}]}]}},
            {"type": "attachment", "attachment": {"type": "hook_success"}},
        ]) + "\n")

    def test_lands_a_report_handed_back_by_subagent_handback(self):
        # T-1194: the verdict was in the SubagentHandback message; the hook found no
        # text and said "no final message", and no A.md was written
        ev = stop_event("expert:rigor-reviewer", "",
                        agent_transcript_path=self.handback_transcript(REPORT))
        code, out, err = fixtures.run_script("land_verdict.py", ev)
        self.assertEqual(code, 0, err)
        path = os.path.join(self.pass_dir(), "A.md")
        self.assertTrue(os.path.isfile(path), (out, err))
        self.assertIn("verdict landed", out["systemMessage"])
        with open(path, encoding="utf-8") as fh:
            meta, body = ac.read_frontmatter(fh.read())
        self.assertEqual((meta["verdict"], meta["run"]), ("CONFIRMED", "A"))
        self.assertIn("VERDICT", body)

    def test_a_handback_is_read_over_its_preamble(self):
        # a short text written in the hand-off's own turn is not the report
        ev = stop_event("expert:rigor-reviewer", "Handing back.",
                        agent_transcript_path=self.handback_transcript(
                            REPORT, preamble="Handing back."))
        code, out, err = fixtures.run_script("land_verdict.py", ev)
        self.assertNotEqual((out or {}).get("decision"), "block", out)
        self.assertTrue(os.path.isfile(os.path.join(self.pass_dir(), "A.md")), (out, err))


class LandRefereeTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        tpath = os.path.join(self.sb.board, "expert@main", "T-0003-referee-the-paper.md")
        meta = {"id": "T-0003", "title": "Referee the paper", "kind": "referee",
                "from": "author@main", "to": "expert@main", "status": "in-progress",
                "priority": "normal", "ask": "Referee it.", "deliverable": "A packet.",
                "refs": [], "blocks": [], "waiting_on": [],
                "budget": {"runs": 1, "max_model": "fable"}, "packets": [],
                "created": "2026-09-28", "updated": "2026-09-28"}
        ac.atomic_write(tpath, ac.new_ticket(meta))
        self.tpath = tpath

    def tearDown(self):
        self.sb.close()

    def packets(self):
        d = os.path.join(self.sb.board, "packets", "expert@main")
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def test_lands_packet_and_copy(self):
        code, out, err = fixtures.run_script("land_referee.py",
                                             stop_event("expert:referee", REFEREE_REPORT))
        self.assertEqual(code, 0, err)
        pk = self.packets()
        self.assertEqual(len(pk), 1, (out, err))
        with open(os.path.join(self.sb.board, "packets", "expert@main", pk[0]),
                  encoding="utf-8") as fh:
            meta, body = ac.read_frontmatter(fh.read())
        self.assertEqual(ac.validate_packet(meta, body), [])
        self.assertEqual((meta["kind"], meta["by"], meta["ticket"]),
                         ("referee", "expert@main/referee", "T-0003"))
        self.assertIn("## Objective findings", body)
        self.assertNotIn("REFEREE", body)
        copies = os.listdir(os.path.join(self.sb.lib, "reviews", "referee", "author-main"))
        self.assertEqual(len(copies), 1)
        with open(self.tpath, encoding="utf-8") as fh:
            tmeta, _ = ac.read_frontmatter(fh.read())
        self.assertEqual(tmeta["packets"], [meta["packet"]])

    def test_wraps_a_report_not_in_packet_shape(self):
        text = "# My report\n\nThe paper is fine.\n\n## Findings\n\n- one\n\n" \
               "REFEREE\nsubject: author@main\nticket: none\nmodel: claude-sonnet-4-5\n"
        code, out, err = fixtures.run_script("land_referee.py",
                                             stop_event("expert:referee", text))
        pk = self.packets()
        self.assertEqual(len(pk), 1, err)
        with open(os.path.join(self.sb.board, "packets", "expert@main", pk[0]),
                  encoding="utf-8") as fh:
            meta, body = ac.read_frontmatter(fh.read())
        self.assertEqual(ac.validate_packet(meta, body), [])
        self.assertIn("## Report", body)
        self.assertIn("#### Findings", body)
        self.assertIn("reduced-strength", body)
        self.assertIn("reduced strength", meta["title"])
        self.assertIsNone(meta["ticket"])

    def test_opus_55_report_is_full_strength(self):
        text = REFEREE_REPORT.replace("claude-fable-5-1", "claude-opus-5-5")
        code, out, err = fixtures.run_script("land_referee.py",
                                             stop_event("expert:referee", text))
        self.assertEqual(code, 0, err)
        with open(os.path.join(self.sb.board, "packets", "expert@main", self.packets()[0]),
                  encoding="utf-8") as fh:
            meta, body = ac.read_frontmatter(fh.read())
        self.assertNotIn("reduced-strength", body)
        self.assertNotIn("reduced strength", meta["title"])

    def test_sonnet_report_is_reduced_strength(self):
        text = REFEREE_REPORT.replace("claude-fable-5-1", "claude-sonnet-4-5")
        fixtures.run_script("land_referee.py", stop_event("expert:referee", text))
        with open(os.path.join(self.sb.board, "packets", "expert@main", self.packets()[0]),
                  encoding="utf-8") as fh:
            meta, body = ac.read_frontmatter(fh.read())
        self.assertIn("reduced-strength", body)
        self.assertIn("reduced strength", meta["title"])

    def test_unknown_ticket_is_noted(self):
        text = REFEREE_REPORT.replace("T-0003", "T-0999")
        fixtures.run_script("land_referee.py", stop_event("expert:referee", text))
        with open(os.path.join(self.sb.board, "packets", "expert@main", self.packets()[0]),
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

    def test_lands_a_report_handed_back_by_subagent_handback(self):
        # T-1194: the referee's report may arrive only as a SubagentHandback message
        tr = self.sb.write("tr.jsonl", "\n".join(json.dumps(r) for r in [
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "SubagentHandback",
                 "input": {"message": REFEREE_REPORT}}]}},
            {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok"}]}},
        ]) + "\n")
        ev = stop_event("expert:referee", "", agent_transcript_path=tr)
        code, out, err = fixtures.run_script("land_referee.py", ev)
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.packets()), 1, (out, err))


class BlindGuardTests(unittest.TestCase):
    def setUp(self):
        self.sb = fixtures.Sandbox()
        self.reviews = os.path.join(self.sb.lib, "reviews")

    def tearDown(self):
        self.sb.close()

    def ev(self, tool, agent="expert:rigor-reviewer", **ti):
        return {"hook_event_name": "PreToolUse", "tool_name": tool, "agent_type": agent,
                "tool_input": ti, "cwd": self.sb.paperhome}

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

    def _pass(self, closer=None):
        d = os.path.join(self.reviews, "paper", "lem-x", "2026-11-20-T-0001")
        os.makedirs(d, exist_ok=True)
        for f in ("A.md", "B.md", "S-table.json") + ((closer,) if closer else ()):
            with open(os.path.join(d, f), "w", encoding="utf-8") as fh:
                fh.write("x\n")
        return d

    def test_the_settler_reads_the_two_verdicts_and_the_table_of_an_open_pass(self):
        """#121: the dependency-settler reads A.md, B.md and S-table.json of the pass it
        settles, and nothing else under reviews/."""
        d, S = self._pass(), "expert:dependency-settler"
        for f in ("A.md", "B.md", "S-table.json"):
            self.assertIsNone(self.decision(self.ev("Read", agent=S,
                                                    file_path=os.path.join(d, f))), f)
        self.assertEqual(self.decision(self.ev("Read", agent=S, file_path=os.path.join(
            d, "decision.md"))), "deny")
        self.assertEqual(self.decision(self.ev("Read", agent=S, file_path=os.path.join(
            d, "S.md"))), "deny")
        self.assertEqual(self.decision(self.ev("Grep", agent=S, pattern="x", path=d)), "deny")
        self.assertEqual(self.decision(self.ev("Glob", agent=S, pattern="*", path=self.sb.lib)),
                         "deny")
        # a folder that is no pass (no date) stays closed
        self.assertEqual(self.decision(self.ev("Read", agent=S, file_path=os.path.join(
            self.reviews, "paper", "x", "p", "A.md"))), "deny")
        # the rigor-reviewer gets no such opening
        self.assertEqual(self.decision(self.ev("Read", file_path=os.path.join(d, "A.md"))),
                         "deny")

    def test_the_settler_never_reads_a_closed_pass(self):
        S = "expert:dependency-settler"
        for closer in ("decision.md", "abandoned.md"):
            d = self._pass(closer)
            self.assertEqual(self.decision(self.ev("Read", agent=S, file_path=os.path.join(
                d, "A.md"))), "deny", closer)
            os.remove(os.path.join(d, closer))

    def test_the_settler_reads_no_other_subjects_open_pass_and_no_symlink(self):
        """Review of 39de757: an open pass of another subject (no S-table.json: nothing is
        being settled there), a pass folder outside reviews/<ns>/<subject>/, and a symlink
        named like a verdict all stay closed."""
        S = "expert:dependency-settler"
        other = os.path.join(self.reviews, "s1", "b", "2026-11-19-T-0002")
        os.makedirs(other, exist_ok=True)
        with open(os.path.join(other, "A.md"), "w", encoding="utf-8") as fh:
            fh.write("x\n")
        self.assertEqual(self.decision(self.ev("Read", agent=S, file_path=os.path.join(other, "A.md"))), "deny")
        shallow = os.path.join(self.reviews, "2026-11-20")
        os.makedirs(shallow, exist_ok=True)
        for f in ("A.md", "S-table.json"):
            with open(os.path.join(shallow, f), "w", encoding="utf-8") as fh:
                fh.write("x\n")
        self.assertEqual(self.decision(self.ev("Read", agent=S, file_path=os.path.join(shallow, "A.md"))), "deny")
        d = self._pass()
        os.remove(os.path.join(d, "B.md"))
        try:
            os.symlink(os.path.join(other, "A.md"), os.path.join(d, "B.md"))
        except (OSError, NotImplementedError):
            self.skipTest("no symlinks here")
        self.assertEqual(self.decision(self.ev("Read", agent=S, file_path=os.path.join(d, "B.md"))), "deny")

    def test_the_settler_reads_the_library_outside_reviews(self):
        self.assertIsNone(self.decision(self.ev("Read", agent="expert:dependency-settler",
                                                file_path=os.path.join(self.sb.lib,
                                                                       "ABC21.txt"))))


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
        p = self.sb.write("paperhome/cards/ABC21/x.md", "not a card")
        self.assertIsNone(self.ctx(self.edit(p)))

    def test_shell_in_library_reports_fresh_gaps_only(self):
        self.sb.write("papers/NEW22.pdf", "x")
        ev = {"hook_event_name": "PostToolUse", "tool_name": "Bash",
              "tool_input": {"command": "curl -o NEW22.pdf https://x"}, "cwd": self.sb.lib}
        self.assertIn("NEW22", self.ctx(ev))
        old = os.path.join(self.sb.lib, "NEW22.pdf")
        os.utime(old, (1, 1))
        self.assertIsNone(self.ctx(ev))
        ev["cwd"] = self.sb.paperhome
        os.utime(old, None)
        self.assertIsNone(self.ctx(ev))           # not in the library, not named


if __name__ == "__main__":
    unittest.main()
