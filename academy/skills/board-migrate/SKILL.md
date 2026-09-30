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
1. `mcp__github__get_me` works; the target repo is in the session scope (else `add_repo`,
   then `read_documentation` topic `github.access`).
2. Numbering is empty: `list_issues` (state all) and `list_pull_requests` (state all) on
   the repo return nothing, otherwise issue number != ticket id (use a fresh repo).
3. Permissions: a labelled test issue can be created and deleted-by-closing
   (issues write); note whether `list_issue_fields`/Projects tools exist. Without Projects
   tools, project fields are filled by `board-sync` or by Roey with a token.

**export.** `py $S/board_export.py --repo OWNER/NAME --out <scratchpad>/manifest.json`
prints the counts (tickets, placeholders, comments, closed, relations). Stop if
`unreadable` or `problems` is non-empty.

**run** (resumable; keep `<scratchpad>/migration-state.json` = `{number: done-step}`).
For each issue in manifest order, skipping steps already recorded, and batching through
subagents in blocks of ~10 issues (strictly in order: numbers must come out equal):
1. labels are created implicitly by the first `issue_write` that uses them (default colour; `board_project.py` recolours later);
2. `issue_write create` with title, body, labels; check the returned `number` equals the
   manifest number, else STOP (numbering broke) and report;
3. one `add_issue_comment` per entry of `comments`, in order;
4. if `state` is closed: `issue_write update state=closed state_reason=<reason>`.
After all issues: apply `relations` (`sub_issue_write add` with the child's issue id for
`sub_issue`; `dependency` (a ticket's `waiting_on` ticket ids; unrelated to the ticket field `blocked_by`) is not in the MCP: list them in the report for Roey/`board_project`).
Before any create, `search_issues "T-NNNN: in:title repo:R"` to make a retry idempotent.

**verify.** Fetch every issue (`issue_read` issue + comments) into a dump
`[{"issue": {...}, "comments": [...]}]`, then
`py $S/board_verify.py --issues <dump>`. Exit 1 lists the drift; fix or report, never
"fix" by editing the file board.

**cutover** (Roey confirms first). Copy `templates/github-board/.github/` and
`scripts/{board_sync,board_codec}.py` + `lib/academy_common.py` into the board repo's
`.github/academy/{scripts,lib}/`; set `boardBackend: github` (docs/github-board.md);
leave the file tickets in place with a `MIGRATED.md` pointer. Commits go on the session
branch; report the branches pushed.
