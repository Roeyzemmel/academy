---
name: lookup
description: 'Answer a quick question about the library or registry via the Expert''s clerk (hot.md, cards, MCP read tools, no web); a miss escalates to the librarian. Use for "what does LMW16 Theorem 11 assume", "what''s the status of paper:lem:x", "do we have Z cached".'
---

# Look it up

## Scope notes

- The clerk answers from `hot.md`, the cards and the MCP read tools only, with no web access.

`$ARGUMENTS` is the question in plain words (a key, a pinpoint, a claim id or a
phrase). Budget: one clerk run (`academy/references/budget.md`).

1. Dispatch **one** `clerk` (`subagent_type: expert:clerk`) with the question as
   given. Add nothing: the clerk reads `hot.md` and the cards itself.
2. Relay its answer as it is, with its source line (the card path or the claim id and
   status).
3. **A miss** ends in an `ESCALATE` block (`to: librarian`, `kind: cite|lookup`,
   `ask: ...`). Do not search further yourself. Offer the human the next step in one line:
   `/expert:cite <ask>` for a `cite`, or a `lookup` ticket to the Expert instance for
   the librarian (`tickets_create`, kind `lookup`, the clerk's `ask` as the ask). File
   the ticket only when the human says so, or when the caller is an agent whose own brief
   allows filing it.

If the clerk fails on a limit, say so and stop; never relaunch (`budget.md` rule 4).
The accesses the clerk made are logged by the MCP server and feed `hot.md`
(`py ${CLAUDE_PLUGIN_ROOT}/scripts/hot.py` rebuilds it; `/expert:status` shows its age).
