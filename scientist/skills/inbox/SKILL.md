---
name: inbox
description: Work the lab's board inbox — take at most three open or accepted tickets addressed to this Scientist instance, in priority order, route each by kind (experiment and test tickets to the experimenter, code tickets to the developer with test-engineer review, "Upstream:" code tickets to upstream-contributor, questions to the experimenter), run them one after another within each ticket's budget, and move each through its lifecycle with a thread note. Use for "work the inbox", "what does the lab have to do", "handle T-NNNN", and when the SessionStart line says tickets are waiting.
---

# The lab's inbox

`$ARGUMENTS`: nothing (take the next ones), or ticket ids to take in that order.

## 1. Select (script, not judgement)

```
py "${CLAUDE_PLUGIN_ROOT}/scripts/inbox.py" --json
```

It returns up to `budget.itemsPerRun` (at most 3) tickets addressed to this
instance, status `open` or `accepted`, ordered by priority then id, each with its
**route** and, when the routed agent is heavier than the ticket's `max_model`,
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
   was delivered.

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
