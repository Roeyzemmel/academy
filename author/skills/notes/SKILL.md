---
name: notes
description: 'File the human''s new margin notes as roadmap items on the agenda entry they concern (or tickets for other roles), and referee-packet points. Use when Roey has left notes in the PDF, after an Overleaf sync, or when a referee packet comes back.'
---

# /author:notes

The main session launches **one** subagent for the whole ingest and relays its report
(budget.md: serial, the lightest model). This pass has no agent file: launch
`general-purpose` on `sonnet` (fallback `haiku`, whose "already covered" and
"discrepancy" calls are then provisional, and the report says so), with the brief
below. `$ARGUMENTS` may name a base commit, or `referee P-NNNN` for a referee packet.

## The brief

> You file new margin notes into the Author's work for this paper (the Author home is
> the cwd). Read `${CLAUDE_PLUGIN_ROOT}/references/formats.md` for the roadmap and
> agenda formats, and the home's `.claude/academy.json`: the note macros are
> `author.noteMacros.human` and `.coauthors` (the human's main macro is
> workspace.json `human.noteMacro`), the tex files `paths.tex`, the agenda and roadmap
> `paths.agenda` and `paths.roadmap`. You write **only** through
> `py ${CLAUDE_PLUGIN_ROOT}/scripts/next.py add ...` and `next.py mark ...`, plus the
> MCP `tickets_create` for work another role owns. You never edit the tex, the
> bibliography, the agenda, or any other file, and you run no git writes.
>
> 1. **Collect.** New notes: `git diff --cached -U0 -- <tex paths>` and
>    `git diff -U0 -- <tex paths>` (or against the base commit given), lines adding a
>    note macro. Full inventory: `git grep -n` for each macro. Take the whole brace
>    group from the file, not the diff line.
> 2. **For each note decide:** *already covered* (an open roadmap item or active ticket
>    carries the same question: search a distinctive phrase; if the item is weaker,
>    add a line with `next.py mark R-NNNN --note "<the new words>"`); *answers a machine
>    note* (read the statement, the machine note it replies to, and record which
>    question is now answered, so the sweep can delete it); *new work* (step 4).
> 3. **Announced but unmade changes.** A note that says something was changed ("I
>    removed ...", "renamed to ...") while the file shows only the note: report it with
>    file, label, the claim and the actual text. File it as `[apply]` if plainly an
>    instruction, else as status `needs-human`. Never reconcile silently.
> 4. **File** each new note: `next.py add --tag <apply|write|lead|verify|cite|figure|
>    notation> --title "<short>" --attach <ns>:<label of the statement it sits on, or
>    global> --source "<macro> note <file>:<line>" --body "<the note quoted, lightly;
>    file:line and enough words to find it again>"`, with `--depends-on` when one note
>    builds on another. Tag from that vocabulary only. A note asking for a proof is
>    `[lead]` (it becomes a `research` ticket to the Expert with `final_to: researcher` when `/author:next` reaches it), never
>    `[write]`. A decision only the human can make: add the item, then
>    `next.py mark R-NNNN --status needs-human`.
> 5. **Referee packet** (`referee P-NNNN`): read the packet (`packets_get`); file each
>    point as above, attached to the entry it concerns, with `--source "P-NNNN point
>    <k>"`; judgement points as `needs-human`, objective ones as `[apply]`/`[write]`.
>
> **Report** four lists: Found (every new note: file, label, one line); Filed (item id,
> tag, entry, the text); Already covered (note, item or ticket); Discrepancies (claim
> vs file, proposed tag). Plus the total note count from the inventory, and every note
> in the inventory that no item or ticket carries. Never ask questions.

## Afterwards

Relay the four lists. Filing starts no work; `/author:next` takes the items in agenda
order.
