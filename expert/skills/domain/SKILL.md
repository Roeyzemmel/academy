---
name: domain
description: Edit a domain pack from a ticket — a notation change, a theorem-sheet entry with its real hypotheses and a card-backed pinpoint, a trap, an example, a figure convention, a computation recipe — through the librarian, one change per ticket, logged in the pack's CHANGELOG.md. Use for notation tickets to the Expert, "add this theorem to the pack", "the pack's notation is wrong", and when an Author's notation-auditor or a Scientist's pack change arrives through the Researcher (`final_to: expert`).
---

# Edit a domain pack

`$ARGUMENTS` is a ticket id (`T-NNNN`), or a pack name and a one-line change for Roey
to confirm as a ticket first. Budget: one librarian run
(`academy/references/budget.md`).

A pack (`<academy repo>/domains/<name>/`) is read by every role through the MCP tool
`domain_get` by its contract file names: `pack.json`, `notation.md`,
`theorems/{INDEX,<topic>,unverified}.md`, `open-problems.md`, `examples.md`,
`traps.md`, `figures.md`, `computation/{README,api/*,scripts/*}`, `CHANGELOG.md`. A
pack holds no plugin logic. Precedence (`notation-discipline`): the pack yields to a
project's decisions, which yield to the draft; so a pack change never rewrites a
project, and a project's decision is not a reason to change the pack unless the
ticket says the field's usage is the project's.

1. **The ticket**: `tickets_get`; `tickets_update` it `open -> accepted ->
   in-progress`. A ticket that asks for two unrelated changes is split: take the first,
   and say so in the thread.
2. **Dispatch one `librarian`** (`subagent_type: expert:librarian`):

   > Edit the `<pack>` domain pack for `<T-NNNN>`: <the ask>. Read the current file
   > with `domain_get` first. A theorem entry carries its real hypotheses and a
   > pinpoint that has a card (write the card first if it has none; an entry you
   > cannot pin goes to `theorems/unverified.md`). Change one thing, keep the file's
   > structure, and append `- <date> <T-NNNN>: <one line>` to `CHANGELOG.md`.

3. **Check**: `domain_get {name, file}` shows the change; `git -C <academy repo> diff
   --stat domains/<pack>` lists only the files named in the changelog line. Do not
   commit: Roey commits the academy repo.
4. **Land**: a `notation` packet (`packets_create`, kind `notation`) when the change
   alters a symbol or a statement other instances rely on, with a decision for Roey if
   it could clash with a project's decisions; then the ticket's `result` and
   `in-progress -> delivered`.

Report the file and line changed, the changelog line, the card written if any, and the
packet id. Never ask questions.
