# The academy's docs are one level up

The documents the plugins cite as `docs/<name>.md` (`protocol.md`, `config.md`,
`branching.md`, `workflows.md`, `roles.md`, `packet-template.md`, `github-board.md`,
`migration-log.md`) are in the `docs/` folder at the root of the academy repository,
beside the plugin folders: `$ACADEMY_ROOT/docs/<name>.md`, which from a workspace root is
`academy/docs/<name>.md`. This folder (`academy/academy/docs`) holds only this pointer,
because sessions looked for the docs here (error ledger, 2026-10-31..11-08: 20 searches
of a path that did not exist).

An installed plugin copy has no `docs/`; read them in the academy checkout of the
workspace (`workspace.json` names it).
