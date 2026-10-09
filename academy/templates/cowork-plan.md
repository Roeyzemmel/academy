# Cowork: {{slug}}

status: active
started: {{date}}
led by: the human; orchestrator: the main session (`academy/references/orchestrator.md`)
caps: --agents {{agents}} (binding); everything else advisory (`academy/references/budget.md`, "Cowork")

## Goal

{{goal}}

## Seeding

- Registry records for every new label: (none yet; `claims_new` through the owning role)
- Pinned statements (`author/scripts/pinned.py`): (not listed yet)
- Cited but unreadable sources (one Expert ticket): (none yet)
- Cost estimate (tasks x runs x average tokens, `usage_report.py`), shown to the human before any dispatch: (not made yet)
- Standing reviewer brief: (the home's `.claude/rules/`, pointed to in every verify ticket)

## Tasks

One row per focused task. The owner is decided by the role cut
(`academy/references/roster-rules.md`); the ticket carries `cowork: {{slug}}`.

| # | task | owner | deliverable | depends on | done when | ticket | state |
|---|---|---|---|---|---|---|---|

## Decisions

Every decision is the human's, asked with AskUserQuestion and recorded here verbatim.

| date | question | answer |
|---|---|---|

## Log

- {{date}}: plan opened.
