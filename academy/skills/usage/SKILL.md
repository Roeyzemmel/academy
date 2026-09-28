---
name: usage
description: Report Claude Code usage by instance, role and agent — turns, cache volume, models seen versus declared, limit failures, fan-out — for one session or a window of days, and with --weekly have the usage-analyst turn the week into a usage packet with budget overruns and model-downgrade suggestions. Use for "how much did that run cost", "usage this week", "which agents are expensive", "did we hit the limit", after a heavy pass, and from the weekly scheduled job.
---

# Usage

`$ARGUMENTS` is one of: empty (the last 7 days), `--days N`, `--since YYYY-MM-DD`, a
session id, or `--weekly`. Scripts: `$S` as in
`${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Budget rules: `references/budget.md`.

| Argument | Run | Then |
|---|---|---|
| empty, `--days N`, `--since D` | `py $S/usage_report.py [--days N \| --since D]` | Show the Markdown as it is. Add at most three lines on the flags. |
| a session id | `py $S/session_usage.py <id>` | Show it; compare with the budget rules if a pass overran. |
| `--weekly` | dispatch one `usage-analyst` subagent (below) | Give the packet id and its one-line summary. |

**`--weekly`** runs unattended from the Windows Task Scheduler
(`claude -p "/academy:usage --weekly"`), so nothing in it may ask a question. Dispatch
one `usage-analyst` with only the window (`--days 7`) and the cwd's instance. It runs
`usage_report.py --days 7 --json` itself, writes one packet of kind `usage` for the
human (`packets.py new --instance <the cwd's instance> --kind usage ...`), and returns
its id. If it fails or hits a limit, report that and stop; do not relaunch.

Reading the numbers: cache reads track cost; output tokens are undercounted in the
transcripts and not shown. The report counts; it does not show that the budget rules
held.

The packet's instance is the home the job runs in (a packet always belongs to an
instance, `docs/packet-template.md`); schedule the job with a home as its working
directory. From outside any home, print the report and file no packet.
