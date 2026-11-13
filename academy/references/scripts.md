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
| `render_packets.py` | review, deep-dive | `[--out FILE] [--all]` (dashboard; default `<board>/.render/review.html`) · `--deep-dive FILE.json [--bundle GATHERED.json] [--kind K] [--out FILE]` (default `<board>/deep-dives/<id>.html`; FILE is the explainer's `{"sections": [...]}`, laid over the gathered bundle) |
| `gather_deep_dive.py` | deep-dive | `SUBJECT [--kind K] [--out FILE] [--depth N]` |
| `deep_dive_index.py` | deep-dive, review | `id SUBJECT` · `get ID` (exit 1 if none) · `set ID --url U [--kind K] [--title T] [--subject S]` · `path ID` · `list` |
| `init_instance.py` | init | `<role>@<name> --home PATH --domain D [--domain D2] [--ns NS] [--expert I] [--scientist I] [--no-board] [--force] [--dry-run]` |
| `usage_report.py` | usage, usage-analyst, desk | `[--days 7\|--since YYYY-MM-DD] [--max-subagents 12] [--json\|--brief]` |
| `error_ledger.py` | usage-analyst, the PostToolUseFailure hook | `hook` (event on stdin) · `report [--days 7\|--since D] [--json]` · `settle --packet P-NNNN [--quiet-days 7]` · `resolve [SIG...] [--family NAME] [--note T] [--commit SHA] [--version V]`: the error ledger `<board>/.errors/<instance>.jsonl`; each error record carries the code it came from (`rev`, `ver`), so an error from a copy older than a fix reads `stale code`, not `regression` |
| `script_path_guard.py` | the PreToolUse hook (Bash/PowerShell) | (hook: a `py <path>/<academy script>.py` whose file is not there is denied with the script's real path; on Windows, `python` that is the Store stub is denied with "use `py`") |
| `session_usage.py` | usage | `<session-id> [--project DIR]`: one session, per subagent |
| `session_start.py` | the SessionStart hook | (no arguments; reads the hook event) |
| `ci_local.py` | `ship.py`'s push gate; by hand | `list [--repo DIR]` (the local plan of the repo's push-triggered workflows: what runs, what is skipped and why) · `run [--repo DIR] [--workflow FILE] [--job ID]` (exit 1 on a failed step) |
| `ship_guard.py` | the PreToolUse hook (Bash/PowerShell) | (hook: in a workspace repo, raw `git commit` / `git push` / a new branch is denied with the `ship.py` command; reads, staging and repos outside the workspace pass) |
| `ship.py` | inbox `--check` (checkpoint hook), board `sync`, sessions at a workspace root | `[--workspace DIR] status` · `start <sub> <topic> [--on BRANCH]` (on a template branch: stacked on it) · `commit\|ship <sub> -m MSG (--paths P...\|--all)` · `push <sub> [--no-gate]` (runs the push gate first: the repo's push-triggered workflows, through `ci_local.py`) · `stack <sub> [--json]` (the chain and each pull request's head and base) · `checkpoint --ticket T [--role R] [--title T] [--only SUB...]` · (the human's) `merge`, `publish`, `accept-baseline`; `docs/branching.md`. A workspace runs it through its `scripts/ship.py` shim |
| `workspace_bootstrap.py` | a workspace's `scripts/bootstrap.py` shim, `cloud-setup.sh` | `[--workspace DIR] [--no-submodules] [--no-plugins] [--strict] [--adopt-siblings]`: writes `workspace.json`, the environment and the permission rules (`templates/workspace/`) |
| `cowork.py` | cowork, desk, inbox | `new SLUG --goal G [--agents A]` (the plan `<board>/cowork/<slug>.md`) · `status SLUG [--json]` (state from the tagged tickets: ACTIVE, WAITING, PAUSE, DONE) · `list [--kind cowork\|campaign\|all] [--json]` (the active workplans; exit 1 none); the mechanics are `academy/lib/workplan.py` |
| `role_write_guard.py` | the PreToolUse hook (Edit/Write) | (hook: `permissions.json` `files.cross_role`; roster-rules.md, "Role cut") |
| `board_relations.py` | board (sync), the human | `plan [--ids T-NNNN,...] [--repo OWNER/NAME] [--json]` (reads only) · `apply [--ids ...] [--dry-run] [--json]` (exit 1 if a write failed; rerun to resume): the GitHub board's native sub-issues (`parent`) and "blocked by" dependencies (`waiting_on` ticket ids) brought in step with the meta lines; `docs/github-board.md`, "Native relations" |
| `board_templates.py` | board-migrate | `ticket-form [--workspace F]` · `render --out REPO` · `check --out REPO` (exit 1 on drift): the GitHub board's `.github/` files, the issue form's instance dropdown filled from workspace.json |

`board.py new` requires `--as <instance>` (the main session inside a home files as
`<instance>`, agent `main`; `--agent <name>` names another agent) and applies the
ticket-chain check. The identity is self-declared: without `--agent` it records
`main`, so this half of the gate is advisory; the MCP tool `tickets_create` is the
enforced path. `--final-to <role>` sets `final_to` on a relayed ticket. Only
/academy:board, /academy:desk and /academy:decide pass `--as human`, after the human
confirms. For `transition` and `append`, `--as` is optional and the caller is the human
without it; `packets.py` acts as `human` unless `--as <instance>` is given. Only the
main session runs `packets.py decide`.

Board commits: tool writes never commit. `session_start` commits pending board changes
only when the board is a standalone clone; a board that is a plain directory of the
workspace (or a submodule) is committed by `ship.py checkpoint --only board` (the inbox
hook, and `/academy:board sync` on demand), on a `<date>/<ticket>/<role>` branch.
