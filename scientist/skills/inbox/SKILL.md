---
name: inbox
description: 'Work the lab''s board inbox: take at most three open or accepted tickets and route each by kind (experiment/test, code, Upstream, question). Use for "work the inbox", "handle T-NNNN", or when SessionStart reports tickets.'
---

# The lab's inbox

## Scope notes

- Routes by kind: `experiment`, `test` and `question` tickets to the experimenter (a `question` is answered from the lab's records, no new compute); `code` tickets to the developer with test-engineer review; a `code` ticket titled "Upstream: ..." to upstream-contributor.

`$ARGUMENTS`: nothing (take the next ones), `--n N`, `--all` (list only), or ticket ids to take in that order.

## 1. Select (script, not judgement)

```
py "${CLAUDE_PLUGIN_ROOT}/scripts/inbox.py" --json
```

It is the shared inbox core (routes: `scripts/routes.py`). It returns up to
`budget.itemsPerRun` (at most 3) tickets addressed to this instance: an `in-progress`
ticket from an earlier run first (resume it), then `open` or `accepted` ones ordered by
priority, agenda position, id; each with its **route** and, when the routed agent is heavier than the ticket's `max_model`,
`over_budget`. With ticket ids as arguments, take those, still at most three.
Say how many remain.

## 2. For each ticket, serially

1. Read it (`tickets_get`). `open` → `accepted` (`tickets_update`), then
   `in-progress` when work starts, each with a thread note.
2. By route:
   - `experimenter`: `/scientist:experiment` with the ticket id. A `test` ticket
     tests the falsifier named in the ask **first**; its report packet is linked to
     the ticket (`report.py file --ticket T-NNNN`).
   - `developer`: dispatch `developer` with the ticket id; when it returns, dispatch
     `test-engineer` to review the diff (never the same agent). Findings go back to
     the developer through the thread; at most the ticket's `budget.runs` agent runs.
   - `upstream-contributor`: dispatch it with the ticket id; it returns a packet for
     Roey.
   - `human`: put the ticket to Roey with `AskUserQuestion`, and record his answer in
     the thread.
   - `reject`: `rejected`, with the reason and the usual receiver in the thread.
   - `over_budget`: `blocked`, `waiting_on: [human]`, a thread line asking for more
     budget. Do not run it.
3. Finish: `delivered` with a one-line `result` (and `packets` when a packet came
   out), or `blocked` with what it waits on. Nothing else starts because a ticket
   was delivered. Checkpoint before the next: `py "${CLAUDE_PLUGIN_ROOT}/scripts/inbox.py"
   --check T-NNNN` (exit 0: delivered, blocked with its reason or rejected; exit 3:
   unfinished, so report it and take nothing more).

## Rules

Budget: `${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md` (three items, serial,
the lightest agent, no relaunch after a limit error, which also stops the run and is
recorded in the ticket thread). Independence:
`${CLAUDE_PLUGIN_ROOT}/../academy/references/roster-rules.md` (whoever wrote code or
an experiment never reviews it). The board changes only through the MCP tools or
the academy's `board.py`; field ownership is `docs/protocol.md` section 4.

## Report

Per ticket: id, route, the transitions made, the result line, packets produced; then
how many tickets remain.
