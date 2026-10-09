---
name: agenda
description: 'Maintain the paper''s agenda (Drafts/agenda.md): results in paper order with claim id, required status, dependencies, owner; refresh statuses, show milestones, turn gaps into tickets. Use for "update the agenda", "what does the paper need".'
---

# /author:agenda

`$ARGUMENTS` is one of `status` (default), `check`, `gaps`, `milestones`, `vision
[<section>]`, `edit <what>`. Formats: `${CLAUDE_PLUGIN_ROOT}/references/formats.md`. Scripts: `$S` =
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
only for mechanical ones (a renamed label), and ask the human about the rest.

## gaps: file the missing work

The board is the Author's only queue. `py $S/agenda.py gaps --json` lists entries below
their required status that no non-terminal ticket is attached to (by its `agenda`
field), with a proposed kind of ticket:

- `verify`: an argument exists (`sketch`); the paper needs two agreeing verdicts. Held
  (`waits_for`) while the entry's own inputs are below their required status.
- `lead`: no argument yet; a proof must come from the Researcher, asked through the Expert (`final_to: researcher`).
- `hold`: only the human can close it, so `--file` reports it and files nothing: the claim is
  `refuted` (nobody verifies or proves it: change what the entry requires, repair the
  statement, or drop it), or it has no registry record (`missing`: create it with
  `claims_new` at an unsettled status; claim records are not the math-editor's).

Show the list and ask the human with `AskUserQuestion` which to file (all / a subset /
none, and whether any entry's `required` should be lowered instead). For each one to
file: `py $S/agenda.py gaps --file` files every proposed ticket (add `--dry-run` to see
them first, `--campaign TARGET` to tag them for a campaign; to file a subset, file those by hand with `board.py new --agenda
<ns>:<label> --refs <claim id> ...`). Filing is idempotent (a filed gap has a ticket,
so it is no longer a gap) and starts no work: `/author:inbox` picks the tickets up in
agenda order (budget.md rule 3). `milestones` and `show` list each entry's tickets.

## vision: the aesthetic pass

The Author owns the paper's form and taste (`${CLAUDE_PLUGIN_ROOT}/references/aesthetic-vision.md`;
this paper's own taste is `Drafts/vision.md`). One section per run: the one named, else
the first section holding an entry of the next milestone. Launch one `math-editor` in
**vision mode** with the section file, `Drafts/vision.md` and the pinned list
(`py $S/pinned.py`); it returns at most five proposals, each with its owner. Show them
and ask the human with `AskUserQuestion` which to file (all / a subset / none).

Filing, as the role cut says (`${CLAUDE_PLUGIN_ROOT}/../academy/references/roster-rules.md`,
"Role cut"): an `author` proposal is a `write` or `apply` ticket to this Author; a
`researcher` one (a different statement, a unifying lemma, a cleaner definition) is a
`research` ticket to the Expert with `final_to: researcher`, which must pass
`routes.check_filed`; an `expert` one is a `notation` ticket; a `human` one is a line
in the report. A proposal touching a pinned statement (`py $S/pinned.py`) is never an
Author ticket. Skip a proposal already ticketed. Nothing is edited during the pass.

If `Drafts/vision.md` is missing, say so and stop: `/academy:init` scaffolds it, or copy
`${CLAUDE_PLUGIN_ROOT}/templates/vision.md`; its content is the human's to state.

## milestones

`py $S/agenda.py milestones`: for each milestone (a coauthor round, a submission), how
many of its entries reach their target. To add one, edit the `## Milestones` section:
`` - `name`: label=status, label=status ``, then run `check`.

## edit

Order, `required`, `depends_on` and `owner` are the human's decisions: make an edit only
when they state it, with the Edit tool on the agenda file, then run `check`. The default
order is paper order; moving an entry up moves every ticket that unblocks it up in
`/author:inbox`.

Never ask questions except where this skill says to.
