---
name: board-migrate
description: 'Move the file board to GitHub Issues and a Project, or check it: export the manifest, execute it through the github MCP in resumable batches, verify zero drift, then cut over. Use for "migrate the board to GitHub", "board preflight", "verify the GitHub board".'
---

# Board migration (files -> GitHub)

`$ARGUMENTS` is `preflight`, `export`, `run`, `verify` or `cutover`. Scripts: `$S` as in
`${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Design, mapping and permissions:
`docs/github-board.md`. Runs in a local or a cloud session: the transport is the
`github` MCP, so no token is needed; the file board stays the source of truth until
`cutover`. Ask Roey (AskUserQuestion) for the target repo once, and never run `run`
against the real repo before a rehearsal in a scratch repo has verified clean.

**preflight** (read-only). Check, and stop with the exact remedy for the first failure:
1. `mcp__github__get_me` works; the target repo is in the session scope (else `add_repo`
   with `access: push`, then `read_documentation` topic `github.access`). The Claude
   GitHub App cannot create repositories (`create_repository` answers 403): Roey creates
   the empty private repos (the scratch one and the real one) and installs the App on them.
2. Numbering is empty: `list_issues` (no `state`: it lists open and closed) and
   `list_pull_requests` (state all) on the repo return nothing, otherwise issue number !=
   ticket id (use a fresh repo; a PR takes a number too).
3. Permissions: **never create a test issue in the target** (it would take #1). The
   rehearsal is the write test: its first `issue_write create` (T-0001) proves issues write,
   its first close proves state writes. Note whether `list_issue_fields`/Projects tools
   exist. Without Projects tools, project fields are filled by `board-sync` or by Roey
   with a token.

**export.** `py $S/board_export.py --repo OWNER/NAME --out <scratchpad>/manifest.json`
prints the counts (tickets, placeholders, comments, closed, relations). Stop if
`unreadable` or `problems` is non-empty.

**run** (resumable; keep `<scratchpad>/migration-state.json` = `{number: done-step}`).
For each issue in manifest order, skipping steps already recorded, and batching through
subagents in blocks of ~10 issues (strictly in order: numbers must come out equal):
1. labels are created implicitly by the first `issue_write` that uses them (default colour; `board_project.py` recolours later);
2. `issue_write create` with title, body, labels, `assignees: [<Roey's login>]` when
   `assign_human`, and `parent_issue_number: <parent>` when `parent` is set (a parent is
   always an older ticket, so it exists; this attaches the sub-issue in the same call);
   check the returned `number` equals the manifest number, else STOP (numbering broke)
   and report;
3. one `add_issue_comment` per entry of `comments`, in order;
4. if `state` is closed: `issue_write update state=closed state_reason=<reason>`.
After all issues: check every `sub_issue` relation landed (`issue_read get_parent` on the
child; `sub_issue_write add` takes the child's issue **id**, not its number, for a repair);
`dependency` (a ticket's `waiting_on` ticket ids; unrelated to the ticket field `blocked_by`) is not in the MCP: list them in the report for Roey/`board_project`.
Before any create, make a retry idempotent from the repo itself, not from search
(`search_issues` is semantic and its index lags): `list_issues` with
`orderBy: CREATED_AT, direction: DESC, perPage: 1, fields: [number, title]` gives the
highest number; when it equals the next manifest number with the same title, that create
already happened, so resume at its comments (count them with `issue_read get_comments`);
any other mismatch is a STOP.

**verify.** Fetch every issue (`issue_read` issue + comments) into a dump
`[{"issue": {number,title,body,labels,state,state_reason}, "comments": [body, ...],
"parent": <parent number or null>, "waits_on": []}]` (`parent` from `issue_read
get_parent`; leaving out `parent`/`waits_on` marks the relations unverified), then
`py $S/board_verify.py --issues <dump>`. Exit 1 lists the drift; fix or report, never
"fix" by editing the file board.

**cutover** (Roey confirms first). Copy `templates/github-board/.github/` and
`scripts/{board_sync,board_codec}.py` + `lib/academy_common.py` into the board repo's
`.github/academy/{scripts,lib}/`; set `board.backend: github` in `workspace.json` (`docs/github-board.md`, `docs/migration-campaign-mode.md` section 6);
leave the file tickets in place with a `MIGRATED.md` pointer. Commits go on the session
branch; report the branches pushed.
