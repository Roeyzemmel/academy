---
name: board
description: 'List, show, file, move and sync tickets on the academy board as Roey. Use for "show the board", "what''s open for the expert", "show T-0007", "close that ticket", "file a ticket to ...", "sync the board", or any ticket id.'
---

# The board

`$ARGUMENTS` is a subcommand and its arguments, or empty (= `list`). Scripts: `$S` as
in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. The ticket format and lifecycle are
`docs/protocol.md` sections 3–4; the main session acts as `human`, who may make any
transition.

| Request | Run |
|---|---|
| `list [filters]` | `py $S/board.py list [--to X] [--from X] [--status S] [--all]` |
| `show T-NNNN` | `py $S/board.py show T-NNNN` |
| `new ...` | Draft it, show the draft, confirm with `AskUserQuestion`, then `py $S/board.py new ...` |
| `close` / `cancel` / `reopen` / any status | `py $S/board.py transition T-NNNN <status> [--reason R] [--result R] [--waiting-on a,b]` |
| `note T-NNNN <text>` | `py $S/board.py append T-NNNN --text "<text>"` |
| `sync` | Commit pending board changes (below) |

Rules:

- A `rejected` or `cancelled` move, and returning a `delivered` ticket to
  `in-progress`, needs `--reason`. If Roey gave none, ask for one.
- Re-routing a ticket is a change of `to`, which only the human makes; the script
  moves the file. Confirm the new receiver first.
- Print the script's output as it is. On exit 2, show the error line and stop.
- Changing a ticket starts no work (`references/budget.md` rule 3).

**sync.** In the board repo (`workspace.json` `board`): `git -C <board> status
--porcelain`; if anything changed, `git -C <board> add -A` and commit with the message
`board: <n> change(s)` followed by a blank line and the session's attribution line.
Never push, never stash. Report the commit hash, or "nothing to commit".
