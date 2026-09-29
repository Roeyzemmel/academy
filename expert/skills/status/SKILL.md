---
name: status
description: 'One screen on the Expert instance: switch-over state, library (cached keys, index rows, cards), reviews awaiting run B, hot.md age, tickets and packets. Read-only. Use for "expert status", "how is the library", before /expert:inbox.'
---

# Expert status

`$ARGUMENTS` is empty or an Expert instance. Read-only.

1. `py ${CLAUDE_PLUGIN_ROOT}/scripts/expert_status.py [--instance X]`
   (`--no-quotes` skips the quote check when the library is large and the answer is
   wanted fast).
2. Relay its output as it is. Then, in at most three lines, what needs doing next and
   by which skill: keys with no row → `/expert:library-index fill`; passes awaiting B
   or a record → `/expert:verify <id>`; tickets waiting → `/expert:inbox`; `hot.md`
   older than a week → `py ${CLAUDE_PLUGIN_ROOT}/scripts/hot.py`.

For the whole academy use `/academy:status`; for the board, `/academy:board`.
