---
name: status
description: One screen on the Expert instance — whether its home is switched over, the library (cached keys, index rows, keys with no row), the cards (errors, warnings, quotes verified against the cached text), review passes awaiting run B or a decision record, the age of hot.md, and the tickets and open packets on the board. Read-only. Use for "expert status", "how is the library", "what's pending in reviews", and before /expert:inbox or /expert:library-index.
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
