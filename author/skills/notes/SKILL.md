---
name: notes
description: 'File the human''s new margin notes as tickets on the agenda entry they concern (to the Author itself, or to the role that owns the work), and referee-packet points. Use when Roey has left notes in the PDF, after an Overleaf sync, or when a referee packet comes back.'
---

# /author:notes

The main session launches **one** subagent for the whole ingest and relays its report
(budget.md: serial, the lightest model). This pass has no agent file: launch
`general-purpose` on `sonnet` (fallback `haiku`, whose "already covered" and
"discrepancy" calls are then provisional, and the report says so), with the brief
below. `$ARGUMENTS` may name a base commit, or `referee P-NNNN` for a referee packet.

## The brief

> You file new margin notes into the Author's work for this paper (the Author home is
> the cwd). The board is the Author's only queue: every work item is a ticket. Read
> `${CLAUDE_PLUGIN_ROOT}/references/formats.md` for the agenda format, and the home's
> `.claude/academy.json`: the note macros are `author.noteMacros.human` and
> `.coauthors` (the human's main macro is workspace.json `human.noteMacro`), the tex
> files `paths.tex`, the agenda `paths.agenda`, the instance name `instance`. You write
> **only** tickets: `py ${CLAUDE_PLUGIN_ROOT}/../academy/scripts/board.py new ...` (or
> the MCP `tickets_create`) `--as <this instance>`, and `board.py append` to add a line
> to a ticket's thread. You never edit the tex, the bibliography, the agenda, or any
> other file, and you run no git writes.
>
> 1. **Collect.** New notes: `git diff --cached -U0 -- <tex paths>` and
>    `git diff -U0 -- <tex paths>` (or against the base commit given), lines adding a
>    note macro. Full inventory: `git grep -n` for each macro. Take the whole brace
>    group from the file, not the diff line.
> 2. **For each note decide:** *already covered* (an active ticket carries the same
>    question: `board.py list` / `tickets_list`, search a distinctive phrase; if the
>    ticket is weaker, add a line with `board.py append T-NNNN --text "<the new words>"
>    --as <this instance>`); *answers a machine
>    note* (read the statement, the machine note it replies to, and record which
>    question is now answered in that ticket's thread, so the sweep can delete it);
>    *new work* (step 4).
> 3. **Announced but unmade changes.** A note that says something was changed ("I
>    removed ...", "renamed to ...") while the file shows only the note: report it with
>    file, label, the claim and the actual text. File it as an `apply` ticket if plainly an
>    instruction, else as a ticket to the Author blocked on `human` (below). Never
>    reconcile silently.
> 4. **File** each new note as a ticket: `board.py new --as <this instance> --to <who>
>    --kind <kind> --title "<short>" --ask "<the note, one line>" --deliverable "<what
>    done looks like>" --agenda <ns>:<label of the statement it sits on> --refs
>    <ns>:<label> --detail "<macro> note <file>:<line>: <the note quoted, lightly;
>    file:line and enough words to find it again>"`. Work that stays in the Author is
>    `--to <this instance>` with kind `apply`, `write`, `copy`, `figure`, `build` or
>    `notation`; a verification is `--to` the Expert, kind `verify`; a citation, kind
>    `cite`. A note asking for a proof is a `research` ticket to the Expert with
>    `--final-to researcher` (an experiment: `--final-to scientist`), never `write`: the
>    Author invents no argument. A note on no statement takes no `--agenda`. When one
>    note builds on another, file the second, then park it on the first: `board.py
>    transition T-NNNN blocked --waiting-on T-MMMM --reason "<why>" --as <this
>    instance>` (receiver's move, so only for a ticket to the Author itself). A decision
>    only the human can make: file it to this instance and park it on `human`
>    (`transition T-NNNN blocked --waiting-on human --reason "<the question>"`).
> 5. **Referee packet** (`referee P-NNNN`): read the packet (`packets_get`); file each
>    point as above, on the entry it concerns, with `P-NNNN point <k>` in the
>    `--detail` (and `--refs P-NNNN`); judgement points parked on `human`, objective
>    ones as `apply` / `write` tickets.
>
> **Report** four lists: Found (every new note: file, label, one line); Filed (ticket
> id, kind, receiver, entry, the text); Already covered (note, ticket); Discrepancies
> (claim vs file, proposed kind). Plus the total note count from the inventory, and
> every note in the inventory that no ticket carries. Never ask questions.

## Afterwards

Relay the four lists. Filing starts no work; `/author:inbox` takes the tickets in agenda
order.
