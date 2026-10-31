---
name: inbox
description: 'Work the paper''s inbox (replaces /author:next): sweep the machine notes, then take at most three tickets from the board, routed by kind, landed if returned, or released if unblocked. Use for "next", "run the agenda", "work the inbox".'
---

# /author:inbox

The main session **orchestrates and relays only**; every edit happens in an agent. The
inbox rules are code: `/academy:inbox`'s workflow (`<academy plugin>/workflows/inbox.js`,
docs/workflows.md) runs the machine-note sweep first (`note-sweeper`, no cap), takes at
most `budget.itemsPerRun` tickets in `inbox.py`'s order (in progress, returned tickets to
**land**, **released** blocked tickets, then by agenda position, priority, id), one at a
time, with the `--check` checkpoint after each, and closes the delivered self-tickets.
Routing table and the lessons of the tier pass: `references/routing.md`. Scripts: `$S` =
`${CLAUDE_PLUGIN_ROOT}/scripts`.

There is no roadmap: the board is the Author's only queue. A work item is a ticket (to
this Author for `write`, `apply`, `copy`, `figure`, `build`, `notation`, `sweep`; to the
Expert for an ask) with `--agenda <ns>:<label>` and the claim in `--refs`, or filed by
`py $S/agenda.py gaps --file` (a refuted claim or one with no record is held for the
human). If the agenda's status column may be stale, run `py $S/agenda.py status` first.

`$ARGUMENTS`: empty, `--all` (list only: `py $S/inbox.py --all` and stop), `--n N`, or
ticket ids (at most three).

1. **Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/../academy/workflows/inbox.js`
   and `args: {root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>", only: ["<this instance>"], n: <N>, ids: [...]}`.
   The workflow starts each agent ticket (`math-writer`, `math-editor`, `figure-maker`,
   `tex-engineer`, `notation-auditor`, `note-sweeper`) in-progress and briefs the agent
   with the pinned statements (`pinned.py`); a returned ticket goes to `math-editor`
   (a verdict or citation) or `math-writer` (a proof or experiment) to land and close;
   `reject` rows are rejected with the route's reason.
2. **Finish what it hands back** (`for_main`), then its `py $S/inbox.py --check T-NNNN`,
   then the workflow again with the cap lowered:
   - a returned referee packet (skill `author:notes`): run `/author:notes` on it;
   - a self-ticket that needs an argument nobody has delivered (`research`,
     `routes.needs_argument`): file a `research` ticket to the Expert with
     `final_to: researcher` (it must pass `routes.check_filed`), move this ticket
     `blocked` waiting on it, and land what returns. Never write the argument;
   - a ticket with no Author route (`human`): show it (`board.py show T-NNNN`) and ask the
     human with `AskUserQuestion` (accept and file a work ticket, reject with a reason,
     forward). Never guess a route.

   `stopped` (an agent returned nothing: a limit) ends the run with no relaunch. Only
   when the primary model is unavailable (not on a limit) relaunch through the Agent
   tool's `model` override set to the agent's `fallback`, and name it in the report.
3. **Close the run**: if an agent reported the build not clean, launch `tex-engineer`
   once; run `py $S/check_paper.py` from the home and relay its summary lines.
4. **Report**. The sweep counts first. Then one row per ticket: id, kind, route, files
   and labels touched, outcome. Then verbatim: every new sketch claim and machine note
   the agents reported, every ticket filed (id, receiver, ask; the verification tickets
   especially), every blast-radius finding. Then the build and checker lines, how many
   tickets remain, and every model substitution. If the run was interrupted, say so in
   the first line. Ask no question except for a `human` route.
