---
name: domain
description: 'Edit a domain pack from a ticket through the librarian, one change per ticket, logged in CHANGELOG.md: notation, theorem entry, trap, example, figure convention, recipe. Use for notation tickets (incl. final_to: expert) and "add this theorem to the pack".'
---

# Edit a domain pack

## Scope notes

- Pack changes also arrive from an Author's `notation-auditor` or a Scientist's `api-prober`, which route them here as a ticket.

`$ARGUMENTS` is a ticket id (`T-NNNN`), or a pack name and a one-line change, which the
human confirms as a ticket first (the workflow takes only a ticket). Budget: one librarian
run (`academy/references/budget.md`).

A pack (`<academy repo>/domains/<name>/`) is read by every role through the MCP tool
`domain_get`, by its contract file names: `pack.json`, `notation.md`,
`theorems/{INDEX,<topic>,unverified}.md`, `open-problems.md`, `examples.md`, `traps.md`,
`figures.md`, `computation/{README,api/*,scripts/*}`, `CHANGELOG.md`. A pack holds no
plugin logic. Precedence (`notation-discipline`): the pack yields to a project's
decisions, which yield to the draft. So a pack change never rewrites a project, and a
project's decision is not a reason to change the pack unless the ticket says the field's
usage is the project's.

**Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/domain.js` and
`args: {ticket: "T-NNNN"}`. The inbox runs it for a `notation` ticket to the Expert. The
order is code (2026-10-31; docs/workflows.md):
1. the ticket is taken. A ticket that asks for two unrelated changes is split: the first
   is taken, and the thread says so;
2. one `librarian` run makes one change, keeps the file's structure, and appends
   `- <date> <T-NNNN>: <one line>` to `CHANGELOG.md`. A theorem entry carries its real
   hypotheses and a pinpoint with a card; an entry it cannot pin goes to
   `theorems/unverified.md`;
3. the check: `git diff` of `domains/<pack>` may list only the files the change names,
   plus `CHANGELOG.md`, and the last changelog line must name the ticket. A mismatch
   parks the ticket on the human instead of delivering it;
4. a `notation` packet when the change alters a symbol or a statement other instances
   rely on (with a decision when it could clash with a project's), then the ticket.

Nothing is committed: the human commits the academy repo. Report the file and line
changed, the changelog line, the card written if any, the packet id and every `anomalies`
entry. Never ask questions.
