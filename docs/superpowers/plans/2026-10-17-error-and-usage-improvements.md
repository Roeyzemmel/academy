# Error ledger and usage statistics: improvement plan

Date: 2026-10-17. Author: Roey with Claude. Branch: `2026-10-17/error-usage-plan/human`
(stacked on `usage-attribution`, which holds the families table and the `workspace` bucket).

## Why

The 30-day ledger (695 errors, 112 classes) and one usage window showed three things:
most errors are agents misusing the board's rules, the same error is counted many times
(retry bursts), and the weekly usage view cannot see cloud sessions at all. Findings and
numbers: the 2026-10-17 error analysis in the session that produced this plan.

Already shipped before this plan: no-match `grep` exits are not errors; refusals name their
route and first reason; the ledger keeps the reason line after a trailing colon; a
"Top families" table; `workspace` bucket for workspace-root sessions.

## Rules for every task

- Test first; one agent per task, run **one at a time** (tasks share `error_ledger.py` and
  `usage_report.py`); the agent edits, the human-side session reviews and ships.
- Do not change `signature()` or the class keys (existing `resolve` records use them).
- `academy/lib/academy_common.py` is vendored byte-identically into five plugins'
  `scripts/_academy.py`: edit once, `cp` to all five, verify the md5sums.
- Done means: new tests fail before and pass after; `python3 -m pytest -q academy/tests
  academy/registry/tests` is green; no unrelated file changed.
- Additive only: existing behaviour, output shapes and `--json` fields stay valid.

## Tasks (in execution order)

### Errors

**E1. Fold the remaining families; split `Bash: exit code`.** Add `family()` rules for
`domain_get: no domain pack`, `delivered needs result`, `does not contain the quote ...
verbatim`; family `Bash: exit code` splits by the first word of the recorded `cmd`
(`git`, `py`, `python3`, other). Files: `error_ledger.py`, its test.

**E2. Count retry bursts once.** In `report`, records of one class in one session within
60 s count as one occurrence for ranking (`bursts`), while the raw count stays shown.
Files: `error_ledger.py`, its test.

**E3. Resolve with the fix.** `resolve --commit SHA` stores the commit (and date) in the
resolve record; a class that recurs after a resolve-with-commit is reported as
`regression`, not `recurring`. Files: `error_ledger.py`, its test.

**E4. Infer the instance.** `config_get`, `claims_*`, `tickets_update` currently refuse
"agent X could act for A or B; pass instance=". Infer it from the ticket's `to` (or the
only candidate) and keep the refusal when still ambiguous. Files: the MCP tool helpers
under `academy/mcp/`, tests in `test_mcp.py`.

**E5. One call to deliver.** `tickets_update` gains an optional `deliver: true` for the
receiver: it walks `open/accepted -> in-progress -> delivered` writing the usual thread
lines, and requires `fields.result`. Existing single-step transitions and the transition
table are unchanged. Files: `mcp/tools/tickets.py`, `docs/protocol.md` section 4, tests.

### Usage

**U1. Context-bloat flag.** `usage_report.py` flags sessions averaging over 100k cache read
per turn (threshold `--max-read-per-turn`, default 100000) next to the existing flags.

**U2. Errors per agent.** Join the error ledger to the usage tally by session id: add
"errors per 100 turns" by agent and role to the report. Ledger records carry `session`.

**U3. Cost per ticket.** Attribute sessions to tickets (the `Ticket: OWNER/NAME#N` lines of
checkpoint commits, or a ticket id in the first user message) and report cache read per
delivered ticket by ticket kind.

**U4. Wasted retries.** Count turns between an error and the next success in the same
session, per error family; add to the weekly packet's family table.

**U5. Cloud usage reaches the board.** `ship.py checkpoint` also writes a content-free
usage summary (session id, instance bucket, turns, cache read/write, models, subagent
counts; no prompts or paths beyond the instance) to `board/.usage/<instance>.jsonl`, and
`usage_report.py` reads it when local transcripts are absent. Riskiest task: last, and
reviewed by hand before merge.

## Out of scope

Rewriting writer-agent prompts; bulk resolving old ledger classes (a decision of the
human); the superproject submodule-pointer bump (human-run `merge --bump`).

## Status

| task | state |
|---|---|
| E1 | done |
| E2 | done |
| E3 | done |
| E4 | done |
| E5 | done |
| U1 | done |
| U2 | done |
| U3 | done |
| U4 | done |
| U5 | done |
