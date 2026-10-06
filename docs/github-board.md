# The GitHub board

The board can live as files (`docs/protocol.md`; the default and still fully supported)
or as GitHub Issues plus a Project v2. This page is the mapping, the rules for each side
and the permissions. `board_codec.py` is the one implementation of the mapping; every
transport (the github MCP in a session, a token over REST, the migration manifest) goes
through it.

## Mapping

One ticket is one issue and **issue number == ticket number** (a repo whose issue and PR
numbering is empty; an id that was never used is a closed placeholder issue).

| ticket | GitHub |
|---|---|
| open / closed | native issue state; `closed` completed, `rejected`/`cancelled` not planned |
| `status` | label `status:<s>`; Project **Status**: `Todo` = open, `In Progress`, `Done` = closed keep their meaning, `Accepted`, `Blocked`, `Delivered` are added |
| `to` | label `to:<instance>`; Project **Instance**; native *assignee*: the human, exactly while `board_codec.wants_human` (addressed to human and live, or blocked with `human` in `waiting_on`); instances are not GitHub users. The store sets it when `board.assignee` is configured, `board-sync` with `ACADEMY_HUMAN_LOGINS`; other assignees are kept |
| role of `to` | label `role:<author\|researcher\|expert\|scientist\|human>`, derived from `to` and rewritten by `board-sync`; Project **Role** |
| dead route | label `route:dead`, zero or one, derived from the block (present exactly when the ticket is `blocked` with both `blocked_by` and `reopen_if`, `board_codec.is_dead_block` over `ac.is_dead_route`; like `role:` from `to`; a ticket that is not blocked but carries both fields is a validation error, not a dead route) and rewritten by `board-sync`; Project **Block** = `pending` \| `dead-route` on a blocked ticket |
| `from`, `kind`, `priority` | labels `from:`, `kind:`, `prio:`; Project **Kind**, **Priority** (P0/P1/P2 = high/normal/low) |
| `parent` | native sub-issue |
| `waiting_on` / `blocks` | native issue dependencies for ticket targets; the rest in the meta line; `status:blocked` is the queryable signal |
| `## Ask`, `## Result` | issue body, after the line `<!-- academy:meta {json} -->` that carries the other fields (never a label's field, `id` or `title`: decode refuses such a line; a key the schema does not know is kept, after the known ones) |
| `## Thread` | one comment per entry, marked `<!-- academy:thread -->`; other comments are conversation, not Thread |
| `campaign`, `blocked_by`, `reopen_if` | the meta line (ticket-only fields, `docs/protocol.md` section 4 and the campaign design); a dead-route ticket is `status:blocked` like a pending one, told apart by `blocked_by` + `reopen_if` in the meta line. `blocked_by` is **not** a native issue dependency: only `waiting_on` ticket ids are (codec payload key `waits_on`, manifest relation `dependency`), so the ticket field `blocked_by` never gets confused with GitHub's "blocked by" relation |
| `agenda` | Project text field **Agenda**; milestones stay free for the paper's milestones |
| packets, `.render/`, `deep-dives/` | stay files in the board repo (`packets/`) |

The status label is the write surface: it decides, and `board-sync` makes state, role and
Project fields follow. There is no separate `resolution:` label; `rejected` and `cancelled`
are statuses. GitHub identity is one account, so `human` vs `instance/agent` is the speaker
in the comment; the write hook and `board-sync` check the rules, not the account.

## Rules on each side

- Client (hook and skills, before a write): `board_codec.py transition|validate`, i.e. the
  academy's `TRANSITIONS`, `validate_ticket`, edges and required fields.
- Server backstop (`.github/workflows/board-sync.yml` -> `board_sync.py`), on board issues
  only (`board_codec.is_board_issue`: a `T-` title, an academy label or the meta line; the
  repository's ordinary issues and pull requests are left alone): one label of each
  kind, role derived from `to`, state follows status, the human's assignee, ticket decodes and validates; one
  comment lists what a human must fix, and is edited to a "resolved" line when it clears.
  The workflow runs one job per issue at a time (`concurrency`). It does not see who made a
  status move, but it keeps the previous state of each ticket (one hidden
  `<!-- academy:state {...} -->` comment, or `board_sync.py --previous FILE` offline) and
  checks what that state can show of the reopen rule (`board_codec.check_reopen`): a
  dead-route block ends only by `blocked -> accepted` with a new `reopened: <mechanism>`
  thread entry (or by cancellation; the server cannot tell whose), so hand-editing the status
  label or the meta line to reopen a dead route without that thread line is reported.
  - The state is `{status, dead, reopened, entries, digest}`; `digest` is a SHA-256 of the
    thread entries, so a removed, edited or replaced earlier entry is reported (append-only).
  - It is validated strictly (`board_codec.parse_state`): a malformed one is ignored, reported
    and rewritten, never a crash. Only a comment authored by `github-actions[bot]` counts
    (`ACADEMY_STATE_AUTHOR`); of those the last one, and earlier duplicates are deleted;
    another author's state comment is ignored and reported.
  - With no state, a ticket that is not blocked (or cancelled) and whose thread shows a
    dead-route block (`tried:`) never followed by `reopened:` is reported as `state missing`
    (the comment was deleted), and no fresh state is written until that is settled. A clean
    or still-blocked ticket on its first sync is not flagged.
  - The **human** may leave a dead route by any transition (`docs/protocol.md`). The check is
    skipped when the event's sender is in the repository variable `ACADEMY_HUMAN_LOGINS`, or
    when the new last thread entry is spoken by `human`. The append-only check still applies.
  - The remembered state does not advance past a violation, so the report stays until it is
    undone or the `reopened:` line is added. A ticket that is no longer blocked must not carry
    `blocked_by`/`reopen_if` (`validate_ticket`, reported too).
  - **Limit.** GitHub identity is one account: the server checks the state left behind, not
    the person. A forged `reopened:` thread comment with a valid speaker name, or a forged
    `**human**` entry, passes; an invalid speaker name, an edited earlier entry and a deleted
    state do not.
- Cloud sessions write issues live, so the `cloud/<date>` review branch cannot apply to
  them. A cloud session acts as `<instance>/<agent>`, must not close or re-route a ticket
  (the human or the addressee's own inbox flow does), and Roey reviews the thread; packets still
  go on the branch.

## Scripts

`board_codec.py` (offline encode/decode/validate/transition), `board_export.py` (manifest),
`board_verify.py` (issues or manifest against the files, byte for byte; a manifest's relations and each issue's `parent`/`waits_on` are compared too, a dump without link data reports them as unverified), `board_import.py`
(issues back to files: backup, rollback), `board_push.py` (the manifest executed over REST
through `gh api`, resumable, numbering checked by reading issues by number) and
`board_dump.py` (the byte-exact verify dump, parents and dependencies included), both on the
`lib/board_gh.py` transport, `board_batch.py` (a reviewed batch of board changes applied as the
human through the MCP tools' code, `--dry-run` on a copy of the file board, resumable),
`board_sync.py` (the workflow), `board_project.py`
(the Project fields and their option sets as a JSON spec derived from the codec and the
academy constants: Status incl. Accepted/Blocked/Delivered, Instance, Role, Kind = every
ticket kind, Priority, Agenda, Block; `--check` proves it covers every kind and status,
`--live` reports what a live Project lacks; `fields_for(meta)` is a ticket's values). The runbook is
`/academy:board-migrate`. Templates: `academy/templates/github-board/.github/`.

## The Project

The board's Project (v2) is `users/Roeyzemmel/projects/2` ("BilliardIllumination Board"), created
on 2026-10-03 with the fields of `board_project.py` and every issue as an item.

- **New issues join it** by the Project's built-in workflow "Auto-add to project" (filter
  `is:issue`, set in the Project's UI), and "Item closed" / "Item reopened" keep its Status
  Done / Todo. These run on GitHub's side with no token.
- **The fields** (Status, Instance, Role, Kind, Priority, Agenda, Block) are written by
  `board_project_sync.py` on the human's machine, through `gh` logged in with the `project`
  scope (`gh auth login -s project`). It reads every issue, compares each item's fields
  with `board_project.fields_for` of the decoded ticket, and writes only what differs
  (adding the item if it is missing); a value with no option yet (a new instance) is
  appended, keeping the other options' ids; a non-ticket issue gets Status from its state.
  It writes the Project only, never an issue. `--repo` / `--project` default to `board.repo`
  and `board.project` in workspace.json; `--issue N` limits it. About 10 s for 106 issues
  when nothing changed.
- **Why not in `board-sync`:** a user-owned Project cannot be reached by the workflow's
  `GITHUB_TOKEN` nor by a fine-grained token, and no long-lived classic token is stored in the
  repo. Between runs a new issue sits in the Project with Status only; its labels carry the
  rest.
- Views (per instance, per role, blocked) are made in the UI: the API has no mutation for them.

## Permissions (connector or token)

Issues read/write, Metadata read, Contents read/write (packets, workflow files), Actions read;
Projects read/write for field writes (the MCP `projects` toolset, or a token with the `project`
scope for `board-sync`'s later Project step). Without Projects access the board works from
labels alone; Project fields lag until they are synced. The board repo must be in the session's
repository scope.

## The store seam

`academy_common.BoardStore` is the one interface to the tickets: `iter_tickets`, `iter_meta`,
`read_all(instance)`, `find`, `get`, `save`, `create`, `status_of`. `FileBoardStore` is the file board
(unchanged behaviour: it is the old code moved behind the seam). `academy/lib/board_store.py` has
`GithubBoardStore`, which keeps the same tickets as issues through an **injected transport**
(`list_issues`, `get_issue`, `create_issue`, `update_issue`, `list_comments`, `add_comment`, optional
`set_parent`/`add_dependency`; without them the links are not written but listed in `store.skipped_relations` and reported on stderr) and does every encoding with `board_codec`; `MemoryTransport` is the
in-memory reference and the fake the tests use (paging with a cap, pull requests among the issues,
failure injection).

**Transport contract.** `list_issues(labels, state, page, per_page)` and `list_comments(number, page,
per_page)` return one page (1-based) and an empty list past the last; a transport may return fewer than
`per_page` (the REST API caps it at 100), so the store reads until a page is empty. The REST API lists
pull requests among the issues (`"pull_request"` key); the store skips them. Comments are read oldest
first by `id` (else `created_at`) when the transport gives them. `save` writes in this order: the thread
comments, the native links (only those that changed, both ways: a moved parent is replaced, a cleared
one removed, a dependency that left `waiting_on` removed), then the issue's title, body, labels, state
and the human's assignee
(the commit point), so a failure half way leaves something a retry repairs; a failed `create` turns the
new issue into a closed `placeholder` instead of leaving an open "(new ticket)". The store and the
library copy it runs on: `as_store` recognises a store by its methods, not by `isinstance`, because every
plugin vendors its own copy of `academy_common`; `open_store` passes its own copy to the store. `inbox_core.select`/`run`/`check`, `board.py` (every
function takes a directory or a store), the role `inbox.py` wrappers (Researcher, Expert, Scientist, and
the Author's `--check`) and the MCP `tickets_*` tools (`Context.store`) all go through it, so a ticket
rule is written once.

Selection is `workspace.json`: `"board": "<path>"` (files, the default) or an object
`{"path": "<local board dir>", "backend": "files" | "github", "repo": "owner/name",
"transport": "module:factory"}`. The path stays (packets, deep-dives and `.render/` are files either
way); `ac.open_store(workspace, transport=None)` and `board.resolve_store()` pick the store (a github store also carries the board path as `.board`, for
packets), and an
explicit `--board DIR` always means the file board there. `github` without a transport (given, or named
by `board.transport`, a factory called with the config dict) is a `ConfigError`.

`test_board_store.py` builds a GitHub board from a file board through the codec and shows that
`inbox_core.select` (default, `--all`, `--campaign`, return legs, position order, the `--json`/text
`run` output and `--check`), the dead-route and pending-block filtering, every transition rule (legal,
illegal, wrong party, reason and result requirements, `reopened:` entries, `blocks` mirroring), ticket
creation with the chain gate and the `campaign` field, and the MCP `tickets_list/get/create/update`
give identical results on both, and that every issue the GitHub side writes still validates.

## Status

Done: codec, export/verify/import, `board_sync` backstop (roles, `route:dead`, the reopen check against
the previous state), workflow and issue form, runbook, `board_project.py` (the Project field spec and its
coverage check), and the `BoardStore` seam behind `inbox_core`, `board.py`, the role inbox wrappers and
the MCP `tickets_*` tools, with a file and a GitHub implementation proven equivalent offline. Campaign
mode (kinds `write` `apply` `copy` `sweep`, `campaign:`, dead-route blocking) runs through the seam.

Still needs the real transport, which is not in this repository and was never exercised against GitHub:
an object with the transport methods above over the github MCP (in a session) or REST with a token,
named by `board.transport`; native sub-issue and dependency calls (`set_parent`, `add_dependency`);
the label filter on a large repo (the store asks for `to:<instance>` only, and never reads comments
while selecting). Not exercised here: `list_issues` paging against a live repo. The Project's fields are kept by
`board_project_sync.py` from the human's machine (below), not by `board-sync`; its views are
made by hand. Also not done: the write hook on github mode, the Author's agenda-gap filing and `packets.py`,
`session_start.py`, which still reads tickets from the files of the board directory (`packets.py`,
`decisions.py`, `land_referee.py` and the MCP packets/claims tools go through the store now) (the Author's ticket filing already goes through `board.create_ticket`, so it
follows a store only once its `ctx.board` is one). Until the transport exists, run a github board's
inbox from a checkout made by `board_import.py`.
