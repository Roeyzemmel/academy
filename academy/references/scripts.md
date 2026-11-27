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
| `decisions.py` | decide, secretary | `list [--json] [--instance X]` · `batches [--size 4] [--json] [--instance X]` · `record <id> (--choice <letter\|proceed\|decline> \| --action <rerun\|accept\|wait\|split\|decline>) [--force] [--comment TEXT]` (a ticket's own lettered options win, #125) · `accept-recommended [--mechanical-only] [--dry-run] [--json]` · `proceed [--instance X] [--dry-run] [--json]` (work goes on under each pending decision's recommendation, marked provisional; nothing is decided) · `policy [--dry-run] [--json] [--instance X]` (accepts what workspace.json `decisions.routine` covers; one digest line) · `select --ticked T-1,T-2 --unticked T-3` (one multi-select batch: proofs, experiments, tests; unticked stay on the board, not now) · `undo <T-id>` (reverts a policy acceptance until an inbox run touches the ticket) · `batches --out D` + `phrased D` (the secretary's phrasing, written to `D/batch-<n>.phrased.json`, read back) · `record-batch D/answers-<n>.json` (one batch of answers in one call; results in `answers-<n>.results.json`) · `lead <id> TEXT` / `record ... --lead TEXT` (free text as a `lead:` line) · `record P-NNNN` with no choice acknowledges a packet that asks nothing |
| `render_packets.py` | review, deep-dive | `[--out FILE] [--all]` (dashboard; default `<board>/.render/review.html`) · `--deep-dive FILE.json [--bundle GATHERED.json] [--kind K] [--out FILE]` (default `<board>/deep-dives/<id>.html`; FILE is the explainer's `{"sections": [...]}`, laid over the gathered bundle) |
| `gather_deep_dive.py` | deep-dive | `SUBJECT [--kind K] [--out FILE] [--depth N]` |
| `deep_dive_index.py` | deep-dive, review | `id SUBJECT` · `get ID` (exit 1 if none) · `set ID --url U [--kind K] [--title T] [--subject S]` · `path ID` · `list` |
| `weekly_review.py` | weekly-review | `[--since YYYY-MM-DD] [--until YYYY-MM-DD] [--ref REF] [--json] [--out FILE] [--no-problems]` (read-only; the week's paper changes, statements ready to read, pending decisions, unmerged work branches and problems, as markdown or JSON; never publishes) |
| `init_instance.py` | init | `<role>@<name> --home PATH --domain D [--domain D2] [--ns NS] [--expert I] [--scientist I] [--no-board] [--force] [--dry-run]` |
| `usage_report.py` | usage, usage-analyst, desk | `[--days 7\|--since YYYY-MM-DD] [--max-subagents 12] [--json\|--brief]` |
| `maintain.py` | maintain | `survey [--days 7] [--json] [--no-probes]` (candidates for a round: ledger families, daily commands over the time or size budget, unreadable definitions, worktrees left) · `union --base B --branches B1 B2 ... [--json]` (the branches merged in a throwaway worktree and gated together; exit 1 on a conflict or a failed gate) |
| `error_ledger.py` | usage-analyst, the PostToolUseFailure hook | `hook` (event on stdin) · `report [--days 7\|--since D] [--json]` · `settle [--packet P-NNNN] [--quiet-days 7]` · `resolve [SIG...] [--family NAME] [--note T] [--commit SHA] [--version V]` · `sync [--repo O/N] [--dry-run]` · `migrate [--repo O/N] [--dry-run] [--skip-resolved]` · `report --local`: with workspace.json `errors.repo` the error FAMILIES are GitHub issues (label `error-family`, `error_issues.py`; the repo may be public, so only the allowlisted family, counts, dates, roles, shell causes and code versions are posted, never a message, path, session, instance name or note): the hook appends to a local spool, `sync` posts it (one comment per family per sync, reopening a closed issue as `regression` or `stale-code`), `report` / `resolve --family` / `settle` read and close the issues (`report --local`: the local detail), `migrate` imports the git ledger once, by family; without it (or without `gh`) the git ledger `<board>/.errors/<instance>.jsonl`. Each error record carries the code it came from (`rev`, `ver`), so an error from a copy older than a fix reads `stale code`, not `regression` |
| `error_issues.py` | `error_ledger.py` (never its hook) | library: the error-family issues (marker `<!-- family:<hash> -->`, hidden JSON fields and occurrence rows `[day, role, cause, rev, ver]`, read only from the poster's comments), the family allowlist (`public_family`: `VOCAB` words, placeholders, punctuation, else `<tool>: (unlisted family <hash of its skeleton>)`), the write gate (`Gate`, `check_public`), the spool cursor, sync, report, resolve, settle, migrate; over `board_gh.GhTransport` |
| `pre_tool_use.py` | the PreToolUse hook (Bash/PowerShell; Edit/Write/MultiEdit/NotebookEdit) | (hook: one process per call; reads the event once and calls the guards' `decide(event)` in order, the first verdict wins, a guard that raises is skipped: Bash/PowerShell `script_path_guard`, `ship_guard`, `generated_view_guard`; Edit/Write/MultiEdit `explainer_write_guard`, `role_write_guard`, `generated_view_guard`; NotebookEdit the first two. Each guard still runs standalone) |
| `script_path_guard.py` | `pre_tool_use.py` (Bash/PowerShell); standalone | (hook: a `py <path>/<academy script>.py` whose file is not there is denied with the script's real path; on Windows, `python` that is the Store stub is denied with "use `py`") |
| `session_usage.py` | usage | `<session-id> [--project DIR]`: one session, per subagent |
| `session_start.py` | the SessionStart hook | (no arguments; reads the hook event) |
| `ci_local.py` | `ship.py`'s push gate; by hand | `list [--repo DIR]` (the local plan of the repo's push-triggered workflows: what runs, what is skipped and why) · `run [--repo DIR] [--workflow FILE] [--job ID]` (exit 1 on a failed step) |
| `ship_guard.py` | `pre_tool_use.py` (Bash/PowerShell); standalone | (hook: in a workspace repo, raw `git commit` / `git push` / a new branch is denied with the `ship.py` command; reads, staging and repos outside the workspace pass) |
| `ship.py` | inbox `--check` (checkpoint hook), board `sync`, sessions at a workspace root | `[--workspace DIR] status` · `start <sub> <topic> [--on BRANCH]` (on a template branch: stacked on it) · `commit\|ship <sub> -m MSG (--paths P...\|--all)` · `push <sub> [--no-gate]` (runs the push gate first: the repo's push-triggered workflows, through `ci_local.py`) · `stack <sub> [--json]` (the chain and each pull request's head and base) · `checkpoint --ticket T [--role R] [--title T] [--only SUB...] [--touched SUB:PATH...]` · (the human's) `merge`, `publish`, `accept-baseline`; `docs/branching.md`. A workspace runs it through its `scripts/ship.py` shim |
| `workspace_bootstrap.py` | a workspace's `scripts/bootstrap.py` shim, `cloud-setup.sh` | `[--workspace DIR] [--no-submodules] [--no-plugins] [--strict] [--adopt-siblings]`: writes `workspace.json`, the environment and the permission rules (`templates/workspace/`) |
| `job_preflight.py` | a workspace's scheduled jobs and their manual `/run-*` skills (first step) | `--workspace DIR --job NAME [--need SUB,SUB] [--repo OWNER/NAME] [--no-gh] [--manual CMD] [--environment NAME]`: the checkout, its submodules populated, the board repo readable through `gh`; prints `PREFLIGHT OK: ...` (exit 0) or, as its first line, `FAILED: <job> could not start: <reasons>.` and the manual command to run instead (exit 2) |
| `cowork.py` | cowork, desk, inbox | `new SLUG --goal G [--agents A]` (the plan `<board>/cowork/<slug>.md`) · `status SLUG [--json]` (state from the tagged tickets: ACTIVE, WAITING, PAUSE, DONE) · `list [--kind cowork\|campaign\|all] [--json]` (the active workplans; exit 1 none); the mechanics are `academy/lib/workplan.py` |
| `role_write_guard.py` | `pre_tool_use.py` (Edit/Write/NotebookEdit); standalone | (hook: `permissions.json` `files.cross_role`; roster-rules.md, "Role cut") |
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
hook, and `/academy:board sync` on demand), on the inbox run's `<date>/run-<run>/<role>`
branch (#102; each ticket's commit tagged `ticket/<id>/<n>`), or, by hand without `--run`,
on a `<date>/<ticket>/<role>` branch.
