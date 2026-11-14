# maintainer (opt-in)

Maintenance rounds on the academy plugins themselves. Install it only in a session that
works on the academy's own code (`/plugin install maintainer@academy`); the role plugins
do not need it and no other session pays for its text.

| Part | What |
|---|---|
| `/maintainer:round` | the round: survey, then each fix on its own branch, reviewed by another agent and gated. By default the session does it; `--workflow` fans the tasks out; `--survey` only shows the candidates |
| `scripts/maintain.py survey` | candidates with evidence: ledger families, daily commands over the time or size budget on the live board, definitions the harness cannot read, worktrees left |
| `scripts/maintain.py union` | branches made side by side merged in a throwaway worktree and gated together |
| `workflows/round.js` | the fanned-out round: plan rules, lanes, develop / review / fix / push per task, the union |

It imports nothing from the other plugins. `maintain.py` runs the base plugin's
`error_ledger.py` and `ci_local.py` as commands from `../academy/scripts`, and the round
ships with the workspace's `scripts/ship.py`. Tests: `py -m unittest discover -s
maintainer/tests -t maintainer/tests` (they also hold every agent, skill and command
definition of the repo to what the harness can read).
