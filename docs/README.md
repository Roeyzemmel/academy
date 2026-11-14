# The docs moved into the base plugin

The academy's documents (`protocol.md`, `config.md`, `branching.md`, `workflows.md`,
`roles.md`, `packet-template.md`, `github-board.md`, `migration-log.md`, the reviews and
plans) are in **`academy/docs/`**, inside the base plugin, since 2026-11-13: an installed
plugin copy then has them, and `${CLAUDE_PLUGIN_ROOT}/docs/<name>.md` resolves for the
base plugin. From a workspace root that is `academy/academy/docs/<name>.md`; the MCP tool
`workspace_get` returns the folder as `academy.docs`.

The plugins still cite them as `docs/<name>.md`: read that as relative to the base plugin.
