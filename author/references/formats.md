# The Author's files: agenda.md and roadmap.md

Plan section 4. Both live in the Author home (`paths.agenda`, `paths.roadmap` in
`.claude/academy.json`), are LF, and are read and written by
`scripts/agenda_lib.py` (tested in `tests/test_agenda.py`). Roey edits them by hand
too; the scripts keep his text.

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
  items that unblock the earliest entry, transitively through `depends_on`.
- **Satisfied**: `status` at or above `required`, with the ranks open < conjectured <
  sketch = supported < proved-modulo < proved; `refuted` meets only `refuted`.
- **Milestones**: one line each, `` - `name`: label=status, ... ``; a boundary such as a
  coauthor round or a submission. `agenda.py milestones` shows progress.

## roadmap.md: the Author's own work items

```markdown
## R-0007 [apply] Delete the stale note after lem:thick-part-compact
- status: open
- agenda: paper:lem:thick-part-compact
- priority: normal
- depends_on: [R-0003, T-0012]
- ticket:
- route:
- source: comment_roadmap.md, Carried over from the archive
- created: 2026-09-28

Free Markdown: what to do, quotes of the notes, history lines
- 2026-09-29: status done; how it was done
```

| Field | Values |
|---|---|
| tag (in the heading) | `write` `apply` `lead` `verify` `cite` `experiment` `figure` `build` `notation` `sweep` `referee` |
| `status` | `open` · `ticketed` (waits for `ticket`) · `blocked` · `needs-human` · `done` · `dropped` |
| `agenda` | a label or claim id of an agenda entry, or `global` |
| `priority` | `high` · `normal` · `low` |
| `depends_on` | item ids `R-NNNN`, ticket ids `T-NNNN`, agenda labels or claim ids |
| `ticket` | the ticket filed for a `lead`/`verify`/`cite`/`experiment`/`referee` item |
| `route` | an agent name overriding the tag's default (e.g. `figure-maker` for an illustration) |
| `source` | where the item came from (a note, a packet point, the old roadmap) |

- Item ids are never reused; `inbox.py add` allocates the next one.
- `##` headings that are not items (free prose sections) are kept verbatim.
- Writes go through `inbox.py add` and `inbox.py mark` (which appends a dated history
  line); hand edits are fine and `agenda.py check` validates them.

## The old roadmap's vocabulary

| `comment_roadmap.md` | Now |
|---|---|
| a tier | agenda precedence plus milestones |
| `[apply]` `[write]` `[lead]` `[verify]` | the same tags; `[lead]` and `[verify]` become tickets |
| `[needs Roey]` | status `needs-human` |
| `[done]` / `[dropped]` | status `done` / `dropped` (moved items only; the old file keeps its history) |
| `## Verification queue` line | a `[verify]` item attached to the label |
| "Open from this tier" | open items and open machine notes (`/author:sweep`) |

`scripts/agenda_migrate.py` converts an old roadmap; see its docstring for every rule.
