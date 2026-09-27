---
name: audit-notation
description: Compare the domain skill's notation sheet with the notation the draft actually uses, report every clash (one object with two symbols, one symbol with two meanings, a symbol used before it is introduced), and update the notation sheet to match the draft — the draft wins. Read-only on the tex. Use after a tier that introduced notation, before a coauthor round, or when a symbol feels overloaded.
---

# Audit the notation contract against the draft

The notation sheet of the domain skill is the contract every agent writes against. Its
own header says where the drafts differ, the drafts win, and the sheet is updated to
match them rather than the paper being silently rewritten. This command enforces that
in the one direction it goes.

Dispatch `notation-auditor` (`subagent_type: notation-auditor`). It reads all of
`sections/`, edits **only** the notation sheet, and reports everything else.

## The brief

> Audit the notation. <The notation introduced or changed since the last audit, and by
> which tier.> The project's rules record the decisions already settled; check each one
> explicitly.

## Two things the main session must handle

- **The sheet is user-global.** It is shared with every other project and with the
  desktop app, so an edit is not confined to this repo. Say so when relaying, and if the
  audit wants to change a decision rather than record one, stop and put it to the author.
- **Clashes inside the draft are not fixed here.** They come back as recommendations
  with occurrence counts; file them as `[apply]` roadmap items, which is where a
  notation change gets made.

Relay the four parts of the agent's report as it wrote them. Never ask questions.
