---
name: referee
description: 'Whole-paper referee report for one Author instance: the read-only referee agent reads the built PDF cold, and its report lands as a referee packet for the human. Use for a referee ticket (from presync), before a coauthor round or submission.'
---

# Referee the whole paper

`$ARGUMENTS` is an Author instance (default: the only one in `workspace.json`), or a
`referee` ticket id. Budget: one referee run (`academy/references/budget.md`). Run it from
the library home, so the landed packet and the ticket belong to the Expert instance.

Not a proof check: `/expert:verify` does that, one statement at a time. This is the other
failure mode, where every proof is fine and the document does not hold together.

**Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/referee.js` and
`args: {instance: "author@<x>", ticket: "T-NNNN", focus: "<only what the human asked to be looked at hardest>"}`.
The inbox runs it for a `referee` ticket. The order is code (2026-10-31; docs/workflows.md):
1. the ticket is taken;
2. the clerk checks the PDF (`<build.dir>/<main stem>.pdf`). It rebuilds a missing or
   stale PDF with `author.build.cmd`, waits at most two minutes while `author.build.lock`
   exists (LaTeX Workshop is building), and edits nothing in the Author home. The referee
   has no shell;
3. one cold `referee` run, whose brief is built from facts only: the PDF and its date,
   what changed since the last report, the vision file, and the human's own focus.
   Nothing else is added, because telling a referee where the weak parts are destroys the
   pass. A hand launch is refused by `review_launch_guard`;
4. the `land_referee` hook keeps the report at `reviews/referee/<instance>/<date>.md` and
   files the `referee` packet; the script finds it and delivers the ticket
   (`referee packet P-NNNN; <n> blocking`).

The Author's `notes` skill files the packet's objective points into its agenda; the
judgement points go to the author untouched.

## Report

The overall assessment paragraph in full, the counts per class and severity, the five
findings the referee would fix first, the packet id and the copy's path. `outcome:
unlanded` means the hook filed nothing: say so. Never ask questions.
