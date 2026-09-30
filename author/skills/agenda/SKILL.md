---
name: agenda
description: 'Maintain the paper''s agenda (Drafts/agenda.md): results in paper order with claim id, required status, dependencies, owner; refresh statuses, show milestones, turn gaps into tickets. Use for "update the agenda", "what does the paper need".'
---

# /author:agenda

`$ARGUMENTS` is one of `status` (default), `check`, `gaps`, `milestones`, `edit
<what>`. Formats: `${CLAUDE_PLUGIN_ROOT}/references/formats.md`. Scripts: `$S` =
`${CLAUDE_PLUGIN_ROOT}/scripts`. Run from the Author home.

## status: refresh the generated column

The status column is generated; never edit it by hand.

1. If the academy MCP server is available, call `claims_list` for this home's
   namespace (`ns` in academy.json), write `{id: status}` to a scratch JSON file, and
   run `py $S/agenda.py status --statuses <file>`.
2. Otherwise `py $S/agenda.py status` (it runs the home's `registry.legacy.claims`
   command, read-only).
3. Relay the changed lines. A `missing` status means the claim has no registry record.

## check

`py $S/agenda.py check`: unknown labels, bad statuses, dependency cycles. Relay the problems; fix the agenda file
only for mechanical ones (a renamed label), and ask Roey about the rest.

## gaps: file the missing work

The board is the Author's only queue. `py $S/agenda.py gaps --json` lists entries below
their required status that no non-terminal ticket is attached to (by its `agenda`
field), with a proposed kind of ticket:

- `verify`: an argument exists (`sketch`); the paper needs two agreeing verdicts. Held
  (`waits_for`) while the entry's own inputs are below their required status.
- `lead`: no argument yet; a proof must come from the Researcher, asked through the Expert (`final_to: researcher`).
- `apply`: no registry record; create one (math-editor, `claims_new` at an unsettled
  status).

Show the list and ask Roey with `AskUserQuestion` which to file (all / a subset /
none, and whether any entry's `required` should be lowered instead). For each one to
file: `py $S/agenda.py gaps --file` files every proposed ticket (add `--dry-run` to see
them first; to file a subset, file those by hand with `board.py new --agenda
<ns>:<label> --refs <ns>:<label> ...`). Filing is idempotent (a filed gap has a ticket,
so it is no longer a gap) and starts no work: `/author:inbox` picks the tickets up in
agenda order (budget.md rule 3). `milestones` and `show` list each entry's tickets.

## milestones

`py $S/agenda.py milestones`: for each milestone (a coauthor round, a submission), how
many of its entries reach their target. To add one, edit the `## Milestones` section:
`` - `name`: label=status, label=status ``, then run `check`.

## edit

Order, `required`, `depends_on` and `owner` are Roey's decisions: make an edit only
when he states it, with the Edit tool on the agenda file, then run `check`. The default
order is paper order; moving an entry up moves every ticket that unblocks it up in
`/author:inbox`.

Never ask questions except where this skill says to.
