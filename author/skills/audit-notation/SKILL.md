---
name: audit-notation
description: Audit the notation the paper actually uses against the home's notation decisions and the domain pack's notation sheet — report every clash (one object with two symbols, one symbol with two meanings, a symbol used before it is introduced), bring the home's .claude/rules/notation-decisions.md in line with the draft (the draft wins), and send domain-notation changes to the Expert as a ticket. Read-only on the tex. Use after work that introduced notation, before a coauthor round, or when a symbol feels overloaded.
---

# /author:audit-notation

Launch `notation-auditor` (`subagent_type: author:notation-auditor`). It reads the
tex, edits **only** the home's `.claude/rules/notation-decisions.md`, and files one
`notation` ticket to the Expert for rows that belong in the domain pack. Precedence
(the academy `notation-discipline` skill): domain pack < project decisions < the draft.

## The brief

> Audit the notation. <The notation introduced or changed since the last audit, by
> item or ticket id, if known.> Check each of the home's settled decisions explicitly.

## What the main session does with the report

- **Clashes inside the draft** are not fixed here. For each recommendation the agent
  gives, file an item: `py ${CLAUDE_PLUGIN_ROOT}/scripts/next.py add --tag apply
  --title "Notation: <symbol>" --attach <label or global> --source "audit-notation
  <date>" --body "<the clash, the counts, the recommended symbol>"`. If a
  recommendation changes a decision rather than recording one, file it as
  `needs-human` instead (`next.py mark R-NNNN --status needs-human`).
- **The domain ticket** (if any) is the Expert's to act on; relay its id.
- **The decisions file** is this paper's only; say which rows changed.

Relay the report's parts as the agent wrote them. Never ask questions.
