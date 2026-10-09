---
name: board
description: 'List, show, file, move and sync tickets on the academy board as the human. Use for "show the board", "what''s open for the expert", "show T-0007", "close that ticket", "file a ticket to ...", "sync the board", or any ticket id.'
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
| `new ...` | Draft it, show the draft, confirm with `AskUserQuestion`, then `py $S/board.py new --as human ...` |
| `close` / `cancel` / `reopen` / any status | `py $S/board.py transition T-NNNN <status> [--reason R] [--result R] [--waiting-on a,b]` |
| `note T-NNNN <text>` | `py $S/board.py append T-NNNN --text "<text>"` |
| `sync` | Commit pending board changes (below) |

Rules:

- A `rejected` or `cancelled` move, and returning a `delivered` ticket to
  `in-progress`, needs `--reason`. If the human gave none, ask for one.
- Re-routing a ticket is a change of `to`, which only the human makes; the script
  moves the file. Confirm the new receiver first.
- Print the script's output as it is. On exit 2, show the error line and stop.
- File as the human (`--as human`) only after they confirmed this ticket through AskUserQuestion; this is the one sanctioned way to file as them from inside a home (docs/protocol.md section 5).
- Changing a ticket starts no work (`references/budget.md` rule 3).

**sync.** Commit the board's files through the workspace's ship tool, never with a bare
`git add -A` (at the workspace root that would sweep up every other change and the
submodule pointers). From the workspace root (the directory of `workspace.json`):
`py scripts/ship.py status` shows the `board` line; if it is dirty (or has untracked
files: `git status --porcelain -- <board>`), run
`py scripts/ship.py checkpoint --ticket <the ticket in hand, else board-sync> --role human
--title "board: <n> change(s)" --only board`. It commits only the board's paths (a plain
directory of the workspace, or the board submodule) on a `<date>/<ticket>/human` branch
and pushes that branch; a dirty board on `main` is refused: then
`py scripts/ship.py start board <topic>` first, and run it again. Never stash. Print its
output as it is and report the branch and commit, or "nothing to commit".
