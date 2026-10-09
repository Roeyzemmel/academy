# The base plugin's scripts, as the skills call them

`$S` below is `${CLAUDE_PLUGIN_ROOT}/scripts`. If the variable is not expanded in the
session, use `~/.claude/skills/academy/scripts` (the plugin's link). Every script is
stdlib Python run with `py` (`python3` where there is no `py`; the plugins' hooks pick
`$ACADEMY_PYTHON`, else `py`, else `python3`), finds the board and the workspace through
`workspace.json` (`--board`, `--workspace` override), and prints UTF-8. Exit code 0 is
success; 1 is "nothing found" where noted; 2 is an error with a one-line message on
stderr. A skill reports a non-zero exit as it is and does not retry in a loop.

| Script | Used by | Command lines |
|---|---|---|
| `academy_status.py` | desk (no arg), status | `py $S/academy_status.py [--since last\|YYYY-MM-DD] [--mark-visit] [--usage] [--instances-only] [--json]` |
| `board.py` | board, desk | `list [--to X] [--from X] [--status S] [--all] [--json]` · `show T-NNNN` · `new --as INSTANCE --to X --title T --ask A --deliverable D [--agent NAME] [--final-to ROLE] [--kind K] [--priority P] [--refs a,b] [--agenda ID] [--parent T-NNNN] [--runs N] [--max-model M (advisory note only)] [--detail TEXT]` · `transition T-NNNN STATUS [--reason R] [--result R] [--waiting-on a,b]` · `append T-NNNN --text TEXT` |
| `packets.py` | review, desk | `list [--open] [--instance X] [--json]` · `show P-NNNN` · `decide P-NNNN --choice a\|b\|c\|d\|other\|ack [--decision K] [--comment TEXT]` |
| `decisions.py` | decide, secretary | `list [--json] [--instance X]` · `batches [--size 4] [--json] [--instance X]` · `record <id> --choice <letter\|proceed\|decline> [--comment TEXT]` · `accept-recommended [--mechanical-only] [--dry-run] [--json]` |
| `render_packets.py` | review, deep-dive | `[--out FILE] [--all]` (dashboard; default `<board>/.render/review.html`) · `--deep-dive BUNDLE.json [--kind K] [--out FILE]` (default `<board>/deep-dives/<id>.html`) |
| `gather_deep_dive.py` | deep-dive | `SUBJECT [--kind K] [--out FILE] [--depth N]` |
| `deep_dive_index.py` | deep-dive, review | `id SUBJECT` · `get ID` (exit 1 if none) · `set ID --url U [--kind K] [--title T] [--subject S]` · `path ID` · `list` |
| `init_instance.py` | init | `<role>@<name> --home PATH --domain D [--domain D2] [--ns NS] [--expert I] [--scientist I] [--no-board] [--force] [--dry-run]` |
| `usage_report.py` | usage, usage-analyst, desk | `[--days 7\|--since YYYY-MM-DD] [--max-subagents 12] [--json\|--brief]` |
| `error_ledger.py` | usage-analyst, the PostToolUseFailure hook | `hook` (event on stdin) · `report [--days 7\|--since D] [--json]` · `settle --packet P-NNNN [--quiet-days 7]` · `resolve SIG... [--note T]`: the error ledger `<board>/.errors/<instance>.jsonl` |
| `session_usage.py` | usage | `<session-id> [--project DIR]`: one session, per subagent |
| `session_start.py` | the SessionStart hook | (no arguments; reads the hook event) |
| `board_templates.py` | board-migrate | `ticket-form [--workspace F]` · `render --out REPO` · `check --out REPO` (exit 1 on drift): the GitHub board's `.github/` files, the issue form's instance dropdown filled from workspace.json |

`board.py new` requires `--as <instance>` (the main session inside a home files as
`<instance>`, agent `main`; `--agent <name>` names another agent) and applies the
ticket-chain check. The identity is self-declared: without `--agent` it records
`main`, so this half of the gate is advisory; the MCP tool `tickets_create` is the
enforced path. `--final-to <role>` sets `final_to` on a relayed ticket. Only
/academy:board, /academy:desk and /academy:decide pass `--as human`, after Roey
confirms. For `transition` and `append`, `--as` is optional and the caller is the human
without it; `packets.py` acts as `human` unless `--as <instance>` is given. Only the
main session runs `packets.py decide`.

Board commits: tool writes never commit. `session_start` commits pending board
changes, and `/academy:board sync` does the same on demand.
