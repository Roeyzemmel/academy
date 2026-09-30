---
name: inbox
description: 'Work the paper''s inbox (replaces /author:next): sweep the machine notes first, file roadmap items as tickets (self-tickets for the Author''s own work), then take at most three tickets, routed by kind or landed. Use for "next", "run the agenda", "work the inbox".'
---

# /author:inbox

The main session **orchestrates and relays only**; every edit happens in an agent. The
choice of tickets is made by `inbox.py`, not by you. It is the Author's wrapper over the
academy's shared inbox core, like `/researcher:inbox`, `/expert:inbox` and
`/scientist:inbox`. Budget and roster rules: `${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md`
and `roster-rules.md` (at most `budget.itemsPerRun` tickets, serially, no relaunch after a
limit error, the lightest agent). Routing table and the lessons kept from the tier pass:
`references/routing.md`. Scripts: `$S` = `${CLAUDE_PLUGIN_ROOT}/scripts`
(`~/.claude/skills/author/scripts` if the variable is not expanded).

`$ARGUMENTS`: empty (take the next tickets), `--all` (list only: also the waiting and
parked items), `--n N`, or ticket ids to take in that order (at most three).

## 1. Sweep first

Run the machine-note sweep as `/author:sweep` does (`note-sweeper`), before any ticket
is taken. It counts against no item cap and is reported first. Answered notes are folded
into roadmap items, open ones are left.

## 2. Plan

`py $S/inbox.py --sync` from the Author home; add `--json` to parse it. `--sync` files
each ready roadmap item once (idempotent): the Author's own work (`write`, `apply`,
`figure`, `build`, `notation`, `sweep`) as a ticket to itself, an ask (`lead`, `verify`,
`cite`, `experiment`, `referee`) to the Expert instance, and closes delivered
self-tickets. The plan lists, in this order: tickets in progress (resume them first),
returned tickets to **land** (`"return": true`), then open and accepted tickets by the
earliest agenda position they unblock, priority, id. Exit 1 means nothing to take:
relay the waiting and parked lists (`--all`) and stop. If the agenda's status column may
be stale, run `py $S/agenda.py status` first.

## 3. Run the taken tickets, one at a time

By each row's `route.how` and `route.target`:

| route | What you do |
|---|---|
| `agent` (`math-writer`, `math-editor`, `figure-maker`, `tex-engineer`, `notation-auditor`, `note-sweeper`) | Move the ticket `accepted` then `in-progress` (`py <academy>/scripts/board.py transition T-NNNN accepted --as <instance>`; `<academy>` is `${CLAUDE_PLUGIN_ROOT}/../academy`). Launch the agent with a short brief: the ticket id (the item id is in `refs`), the files it may touch, anything an earlier ticket of this run changed, and "record the item with `inbox.py mark R-NNNN --status done --note '<one line>'`", which delivers and closes its self-ticket (`--status blocked` or `needs-human` parks the ticket on `human`). |
| `agent` with `"return": true` | A returned ticket to land: launch the named agent (`math-editor` for a verdict or citation, `math-writer` for a proof or experiment) with the ticket id and the item id (`item`). |
| `skill` (`author:notes`) | A returned referee packet: run `/author:notes` on it. |
| `human` | No Author route for this kind: show it (`py <academy>/scripts/board.py show T-NNNN`) and ask Roey with `AskUserQuestion` (accept and file an item, reject with a reason, forward). Never guess a route. |

**Checkpoint after each ticket** before the next: `py $S/inbox.py --check T-NNNN`. Exit 0:
delivered, blocked with its reason, or rejected. Exit 3: unfinished; report it, do not
redispatch it in this run, and take nothing while it is unfinished (it comes first next
time). Nothing runs concurrently.

**Limit stop.** If an agent returns a usage-, rate- or session-limit error, or an empty
result: launch nothing further, do not relaunch, note it on the item
(`py $S/inbox.py mark R-NNNN --note "interrupted: <what was and was not recorded>"`), and
go to the report. A result cut off by `maxTurns` is not a limit error: record what is
unfinished and go on to the next ticket.

**Model fallback.** Only when the primary model is unavailable (not on a limit error),
relaunch through the Agent tool's `model` override set to the agent's `fallback`, and
name the substitution in the report.

## 4. Close the run

1. If an agent reported the build not clean, launch `tex-engineer` once.
2. Run the checker: `py $S/check_paper.py` from the home, and relay its summary lines.
3. Run `py $S/inbox.py sync` once more: a self-ticket the agents delivered is closed and
   its item marked done.

## 5. Report

The sweep counts first. Then one row per ticket: id, kind, route, files and labels
touched, outcome. Then verbatim only: every new sketch claim and machine note the agents
reported, every ticket filed (id, receiver, ask), every item they filed (verification
items especially), and every blast-radius finding (a defect reaching past its item).
Then the build and checker lines, how many tickets remain, and every model substitution.
If the run was interrupted, say so in the first line. Never ask a question except for a
`human` route.
