---
name: next
description: 'Run the next batch (at most three items) of the paper''s work, chosen from the agenda, roadmap and board: route items to the Author''s agents or file tickets to other roles, and land returned tickets. Use for "next", "continue the paper", "run the agenda".'
---

# /author:next

The main session **orchestrates and relays only**; every edit happens in an agent.
The choice of items is made by `next.py`, not by you. Budget and roster rules:
`${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md` and `roster-rules.md` (at most
`budget.itemsPerRun` items, serially, no relaunch after a limit error, the lightest
agent). Routing details and the lessons kept from the tier pass:
`references/routing.md`. Script paths: `$S` = `${CLAUDE_PLUGIN_ROOT}/scripts`
(`~/.claude/skills/author/scripts` if the variable is not expanded).

## 1. Plan

Run `py $S/next.py plan` from the Author home and show its output as it is. Exit 1
means nothing is ready: relay the WAITING and PARKED lists and stop. If the agenda's
status column may be stale (the last `/author:agenda status` was before tickets came
back), run `py $S/agenda.py status` first (see the agenda skill).

`$ARGUMENTS` may name item ids to run instead; run `next.py plan --json` and refuse any
named item that is not in `ready`, saying why (its `reason`).

## 2. Run the selected items, one at a time

For each item in SELECTED order, by its `action`:

| action | What you do |
|---|---|
| `agent` | Launch the named agent with a short brief: the item id (or ticket id), the files it may touch, anything an earlier item of this run changed. It reads the item itself. |
| `ticket` | Show the draft (`py $S/next.py file R-NNNN --dry-run`), then file it: `py $S/next.py file R-NNNN`. This files as this instance and marks the item `ticketed`. No agent runs. |
| `land` | Launch the named agent (`math-editor` for a verdict or citation, `math-writer` for a proof or experiment) with the item and ticket ids; for `notes`, run `/author:notes` on the ticket's packet instead. |
| `triage` | An inbox ticket whose kind no agent owns: show it (`py <academy>/scripts/board.py show T-NNNN`) and ask Roey with `AskUserQuestion` what to do (accept and file an item, reject with a reason, forward). |

For an inbox ticket (`source: ticket`) routed to an agent: move it to `accepted` and
then `in-progress` first (`py <academy>/scripts/board.py transition T-NNNN accepted
--as <instance>`, then `in-progress`; `<academy>` is `${CLAUDE_PLUGIN_ROOT}/../academy`),
and include "deliver the ticket when done" in the brief.

**After each item, checkpoint** before starting the next: confirm the item is recorded
(`next.py plan --json` no longer lists it as ready, or the agent reported it blocked
with a reason). Nothing runs concurrently.

**Limit stop.** If an agent returns a usage-, rate- or session-limit error, or an empty
result: launch nothing further, do not relaunch, mark the item
`py $S/next.py mark R-NNNN --note "interrupted: <what was and was not recorded>"`, and
go to the report. A result cut off by `maxTurns` is not a limit error: record what is
unfinished (`mark --note`) and go on to the next item.

**Model fallback.** Only when the primary model is unavailable (not on a limit error),
relaunch through the Agent tool's `model` override set to the agent's `fallback`, and
name the substitution in the report.

## 3. Close the run

After the last item returned:

1. If an agent reported the build not clean, launch `tex-engineer` once.
2. Run the checker: `py $S/check_paper.py` from the home, and relay its summary lines.
3. If this run closed items that answered machine notes, suggest `/author:sweep` (do
   not run it).

## 4. Report

One row per item: id, tag, action, agent or ticket, files and labels touched, outcome.
Then verbatim only: every new sketch claim and machine note the agents reported, every
ticket filed (id, receiver, ask), every item they filed (verification items especially),
and every blast-radius finding (a defect reaching past its item). Then the build and
checker lines, how many ready items remain (`remaining_ready`), and every model
substitution. If the run was interrupted, say so in the first line. Never ask a
question except in `triage`.
