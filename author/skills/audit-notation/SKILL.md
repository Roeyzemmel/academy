---
name: audit-notation
description: 'Audit the paper''s notation against the home''s notation decisions and the domain pack, report clashes, sync notation-decisions.md to the draft, ticket domain changes to the Expert. Read-only on tex. Use after new notation or before a coauthor round.'
---

# /author:audit-notation

Launch `notation-auditor` (`subagent_type: author:notation-auditor`). It reads the
tex, edits **only** the home's `.claude/rules/notation-decisions.md`, and files one
`notation` ticket to the Expert for rows that belong in the domain pack. Precedence
(the academy `notation-discipline` skill): domain pack < project decisions < the draft.

## The brief

> Audit the notation. <The notation introduced or changed since the last audit, by
> ticket id, if known.> Check each of the home's settled decisions explicitly.

## What the main session does with the report

- **Clashes inside the draft** are not fixed here. For each recommendation the agent
  gives, file a ticket to this Author: `py ${CLAUDE_PLUGIN_ROOT}/../academy/scripts/board.py
  new --as <this instance> --to <this instance> --kind apply --title "Notation:
  <symbol>" --ask "<the clash, one line>" --deliverable "the recommended symbol applied"
  --agenda <ns>:<label> --detail "audit-notation <date>: <the clash, the counts, the
  recommended symbol>"` (no `--agenda` for a global one). If a recommendation changes a
  decision rather than recording one, park the ticket on `human` instead (`board.py
  transition T-NNNN blocked --waiting-on human --reason "<the decision>" --as <this
  instance>`).
- **The domain ticket** (if any) is the Expert's to act on; relay its id.
- **The decisions file** is this paper's only; say which rows changed.

Relay the report's parts as the agent wrote them. Never ask questions.
