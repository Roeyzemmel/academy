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
| `to` | label `to:<instance>`; Project **Instance**; native *assignee* only for `to: human` and real collaborators (instances are not GitHub users) |
| role of `to` | label `role:<author\|researcher\|expert\|scientist\|human>`, derived from `to` and rewritten by `board-sync`; Project **Role** |
| `from`, `kind`, `priority` | labels `from:`, `kind:`, `prio:`; Project **Kind**, **Priority** (P0/P1/P2 = high/normal/low) |
| `parent` | native sub-issue |
| `waiting_on` / `blocks` | native issue dependencies for ticket targets; the rest in the meta line; `status:blocked` is the queryable signal |
| `## Ask`, `## Result` | issue body, after the line `<!-- academy:meta {json} -->` that carries the other fields |
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
- Server backstop (`.github/workflows/board-sync.yml` -> `board_sync.py`): one label of each
  kind, role derived from `to`, state follows status, ticket decodes and validates; one
  comment lists what a human must fix. It does not judge who made a status move.
- Cloud sessions write issues live, so the `cloud/<date>` review branch cannot apply to
  them. A cloud session acts as `<instance>/<agent>`, must not close or re-route a ticket
  (the human or the addressee's own inbox flow does), and Roey reviews the thread; packets still
  go on the branch.

## Scripts

`board_codec.py` (offline encode/decode/validate/transition), `board_export.py` (manifest),
`board_verify.py` (issues or manifest against the files, byte for byte), `board_import.py`
(issues back to files: backup, rollback), `board_sync.py` (the workflow). The runbook is
`/academy:board-migrate`. Templates: `academy/templates/github-board/.github/`.

## Permissions (connector or token)

Issues read/write, Metadata read, Contents read/write (packets, workflow files), Actions read;
Projects read/write for field writes (the MCP `projects` toolset, or a token with the `project`
scope for `board-sync`'s later Project step). Without Projects access the board works from
labels alone; Project fields lag until they are synced. The board repo must be in the session's
repository scope.

## Status

Done: codec, export/verify/import, `board_sync` backstop, workflow and issue form, runbook.
Campaign mode (shared inbox core, dead-route blocking, `campaign:` tag, kinds `write` `apply` `copy` `sweep`)
round-trips through the codec and validates in `board-sync`; the inbox core and `board.py` still read the
file board, so `/academy:inbox` and campaigns need the `BoardStore` seam below before they can run on a
GitHub board (until then, run them on a checkout made by `board_import.py`).
Not yet: the `BoardStore` seam behind `board.py` and the MCP `tickets_*` tools (github mode is
reached through the skills and the codec until then), the write hook, `board_project.py`
(Project fields and views), the Project-field half of `board-sync`.
