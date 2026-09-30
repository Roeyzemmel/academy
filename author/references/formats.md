# The Author's file: agenda.md

Plan section 4. It lives in the Author home (`paths.agenda` in `.claude/academy.json`),
is LF, and is read and written by `scripts/agenda_lib.py` (tested in
`tests/test_agenda.py`). Roey edits it by hand too; the scripts keep his text. The
Author's work items are tickets on the board (below).

## agenda.md: the paper's results in paper order

```markdown
# Agenda: author@main

<!-- academy agenda v1 ... -->

## Milestones

- `coauthor-round`: thm:main=proved, lem:strip=sketch

## Entries

| # | label | claim | required | depends_on | owner | status |
|---|---|---|---|---|---|---|
| 1 | thm:main | paper:thm:main | proved | lem:strip, prop:x | author@main | sketch |
```

| Column | Meaning | Who edits |
|---|---|---|
| `#` | Position; renumbered from the row order on every write | script |
| `label` | The statement's LaTeX label | Roey / `/author:agenda` |
| `claim` | Its registry id (`<ns>:<label>`), `-` if none yet | Roey / `/author:agenda` |
| `required` | The status the entry must reach (one status vocabulary) | Roey |
| `depends_on` | Labels of entries (or claim ids) it rests on, comma separated, `-` if none | Roey / migration |
| `owner` | The instance that must deliver it | Roey |
| `status` | The registry's status now; **generated** by `agenda.py status`; `missing` = no record, `?` = never read | script only |

- **Row order is precedence** (paper order by default). `/author:inbox` takes first the
  tickets whose `agenda` unblocks the earliest entry, transitively through `depends_on`.
- **Satisfied**: `status` at or above `required`, with the ranks open < conjectured <
  sketch = supported < proved-modulo < proved; `refuted` meets only `refuted`.
- **Milestones**: one line each, `` - `name`: label=status, ... ``; a boundary such as a
  coauthor round or a submission. `agenda.py milestones` shows progress.

## There is no roadmap: the board is the only queue

A work item is a **ticket** (`docs/protocol.md`), filed with `board.py new` /
`tickets_create` or, from an agenda gap, `agenda.py gaps --file`. What the old
`roadmap.md` item fields became:

| Old roadmap field | Now |
|---|---|
| tag (`write` `apply` `figure` `build` `notation` `sweep`) | the ticket `kind`, `to` this Author itself |
| tag `lead` / `experiment` | kind `research` to the Expert, `final_to: researcher` / `scientist` |
| tag `verify` / `cite` / `referee` | kind `verify` / `cite` / `referee` to the Expert |
| `agenda` | the ticket's `agenda` field (the entry's claim id; omitted or `global` for none); the claim is also in `refs` |
| `priority` | the ticket's `priority` |
| `status` open / ticketed | ticket `open`; `accepted`, `in-progress`, `delivered`, `closed` |
| `status` needs-human / blocked | ticket `blocked` with `waiting_on: [human]` |
| `status` done / dropped | ticket `closed` / `cancelled` or `rejected` |
| `depends_on` a ticket | `waiting_on: [T-NNNN]` (the inbox offers the ticket again once they are back) |
| `depends_on` an entry or claim | a line in the ticket's ask; file it when the status is reached |
| `route` | the ticket kind that routes to that agent (`inbox` routing table) |
| body and history lines | the ticket's `## Ask` and `## Thread` |
| `R-NNNN` ids | gone; a ticket id is `T-NNNN` |

- Milestone progress and the agenda's status column are computed from the registry
  statuses, plus the tickets attached to each entry (`agenda.py milestones`, `show`).
- `scripts/agenda_migrate.py` is the one-shot converter for a `Drafts/roadmap.md` that
  still exists: dry run by default, `--apply` files the tickets, the file is only read
  (archive it by hand afterwards); see its docstring for every rule. Nothing else reads
  or writes a roadmap; an old `paths.roadmap` key in `academy.json` is accepted and
  ignored.
