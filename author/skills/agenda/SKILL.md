---
name: agenda
description: Maintain the paper's agenda (Drafts/agenda.md) — the results in paper order, each with its claim id, required status, dependencies and owner — refresh its generated status column from the registry, check it against the roadmap, show milestone progress, and turn gaps (an entry below its required status that nothing is working on) into roadmap items or tickets. Use for "update the agenda", "what does the paper still need", "add a milestone", "reorder the agenda", after tickets came back, and before /author:next when statuses may be stale.
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

`py $S/agenda.py check`: unknown labels, bad statuses, dependency cycles, roadmap
items attached to entries that do not exist. Relay the problems; fix the agenda file
only for mechanical ones (a renamed label), and ask Roey about the rest.

## gaps: file the missing work

`py $S/agenda.py gaps --json` lists entries below their required status that no open
item or ticket is attached to, with a proposed tag:

- `verify`: an argument exists (`sketch`); the paper needs two agreeing verdicts.
- `lead`: no argument yet; a proof must come from the Researcher, asked through the Expert (`final_to: researcher`).
- `apply`: no registry record; create one (math-editor, `claims_new` at an unsettled
  status).

Show the list and ask Roey with `AskUserQuestion` which to file (all / a subset /
none, and whether any entry's `required` should be lowered instead). For each one to
file: `py $S/next.py add --tag <tag> --title "<verb> <label>" --attach <ns>:<label>
--source "agenda gaps <date>"`. Filing an item starts no work: `/author:next` picks it
up in agenda order (budget.md rule 3).

## milestones

`py $S/agenda.py milestones`: for each milestone (a coauthor round, a submission), how
many of its entries reach their target. To add one, edit the `## Milestones` section:
`` - `name`: label=status, label=status ``, then run `check`.

## edit

Order, `required`, `depends_on` and `owner` are Roey's decisions: make an edit only
when he states it, with the Edit tool on the agenda file, then run `check`. The default
order is paper order; moving an entry up moves every item that unblocks it up in
`/author:next`.

Never ask questions except where this skill says to.
