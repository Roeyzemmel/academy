# The base plugin's scripts, as the skills call them

`$S` below is `${CLAUDE_PLUGIN_ROOT}/scripts`. If the variable is not expanded in the
session, use `~/.claude/skills/academy/scripts` (the plugin's link). Every script is
stdlib Python run with `py`, finds the board and the workspace through
`workspace.json` (`--board`, `--workspace` override), and prints UTF-8. Exit code 0 is
success; 1 is "nothing found" where noted; 2 is an error with a one-line message on
stderr. A skill reports a non-zero exit as it is and does not retry in a loop.

| Script | Used by | Command lines |
|---|---|---|
| `academy_status.py` | desk (no arg), status | `py $S/academy_status.py [--since last\|YYYY-MM-DD] [--mark-visit] [--usage] [--instances-only] [--json]` |
| `board.py` | board, desk | `list [--to X] [--from X] [--status S] [--all] [--json]` · `show T-NNNN` · `new --to X --title T --ask A --deliverable D [--kind K] [--priority P] [--refs a,b] [--agenda ID] [--parent T-NNNN] [--runs N] [--max-model M] [--detail TEXT]` · `transition T-NNNN STATUS [--reason R] [--result R] [--waiting-on a,b]` · `append T-NNNN --text TEXT` |
| `packets.py` | review, desk | `list [--open] [--instance X] [--json]` · `show P-NNNN` · `decide P-NNNN --choice a\|b\|c\|d\|other\|ack [--decision K] [--comment TEXT]` |
| `render_packets.py` | review, deep-dive | `[--out FILE] [--all]` (dashboard; default `<board>/.render/review.html`) · `--deep-dive BUNDLE.json [--kind K] [--out FILE]` (default `<board>/deep-dives/<id>.html`) |
| `gather_deep_dive.py` | deep-dive | `SUBJECT [--kind K] [--out FILE] [--depth N]` |
| `deep_dive_index.py` | deep-dive, review | `id SUBJECT` · `get ID` (exit 1 if none) · `set ID --url U [--kind K] [--title T] [--subject S]` · `path ID` · `list` |
| `init_instance.py` | init | `<role>@<name> --home PATH --domain D [--domain D2] [--ns NS] [--expert I] [--scientist I] [--no-board] [--force] [--dry-run]` |
| `usage_report.py` | usage, usage-analyst, desk | `[--days 7\|--since YYYY-MM-DD] [--max-subagents 12] [--json\|--brief]` |
| `session_usage.py` | usage | `<session-id> [--project DIR]`: one session, per subagent |
| `session_start.py` | the SessionStart hook | (no arguments; reads the hook event) |

Called as the human: the main session has no agent type, so `board.py` and
`packets.py` act as `human` unless `--as <instance>` is given. Only the main session
runs `packets.py decide`.

Board commits: tool writes never commit. `session_start` commits pending board
changes, and `/academy:board sync` does the same on demand.
