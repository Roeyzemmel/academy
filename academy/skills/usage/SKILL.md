---
name: usage
description: 'Report Claude Code usage by instance, role and agent (turns, cache, models, limit failures) for a session or window; --weekly files a usage packet. Use for "usage this week", "how much did that run cost", "did we hit the limit".'
---

# Usage

`$ARGUMENTS` is one of: empty (the last 7 days), `--days N`, `--since YYYY-MM-DD`, a
session id, or `--weekly`. Scripts: `$S` as in
`${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Budget rules: `references/budget.md`.

| Argument | Run | Then |
|---|---|---|
| empty, `--days N`, `--since D` | `py $S/usage_report.py [--days N \| --since D]` | Show the Markdown as it is. Add at most three lines on the flags (limit, fan-out, context-bloat, heavier-than-declared). |
| a session id | `py $S/session_usage.py <id>` | Show it; compare with the budget rules if a pass overran. |
| `--weekly` | the `academy-weekly` workflow (below) | Give the packet id, its one-line summary and whether the ledger was settled. |

**`--weekly`** may run unattended (`claude -p "/academy:usage --weekly"` from a
scheduler), so nothing in it may ask a question. Call the **Workflow** tool with
`scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/weekly.js` and `args: {instance: "<the cwd's
instance>", days: 7}`. The script holds the cycle (docs/workflows.md): the
`usage-analyst` gathers and proposes; the script drops a grader's downgrade, a downgrade
that is not a lower tier, and anything past three decisions (regressions first); the
analyst writes and files one `usage` packet with exactly those; `error_ledger.py settle`
runs only after the packet is shown to exist. Report `reason` when `filed` or `settled`
is false; do not relaunch.

**Errors.** A `PostToolUseFailure` hook (`scripts/error_ledger.py hook`) appends every
failed tool call, redacted and without the command line, to
`<board>/.errors/<instance>.jsonl` as it happens. The weekly packet lists the week's
error classes and carries the unresolved ones forward; `settle`, run after the packet is
filed, closes the classes that were reported and stayed quiet for seven days. From the
main session: `py $S/error_ledger.py report [--days N]` shows the picture, and
`py $S/error_ledger.py resolve "<class>" --note "<why>"` closes a class by hand.

**Cloud sessions.** `ship.py checkpoint` writes content-free session summaries to
`<board>/.usage/<instance>.<host>.jsonl`; the report adds those whose transcript is not on this
machine (a note line says how many; `--no-board` skips them).

Reading the numbers: cache reads track cost; output tokens are undercounted in the
transcripts and not shown. The report counts; it does not show that the budget rules
held.

The packet's instance is the home the job runs in (a packet always belongs to an
instance, `docs/packet-template.md`); schedule the job with a home as its working
directory. From outside any home, print the report and file no packet.
