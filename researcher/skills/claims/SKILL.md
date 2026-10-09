---
name: claims
description: 'Answer "what is known about X" from the claim registry: show, list, search and query objects with status and evidence, follow dependents, route status changes to claim-keeper. Use whenever a statement''s status is asked or before relying on a result.'
---

# The claim registry

## Scope notes

- Covers every namespace (this instance's own, `paper:`, `lab:` and future instances) through the same MCP tools; also use it when an experiment needs a claim id.

`$ARGUMENTS` is an id (`<ns>:<id>`), a text to search, or what to do. The MCP tools
are `mcp__plugin_academy_academy__claims_*` (or `mcp__academy__claims_*`, see
`${CLAUDE_PLUGIN_ROOT}/references/scripts.md`); the status words are the
`academy:status-vocabulary` skill.

**Do not reconstruct a status from prose** — a roadmap, a header, a journal, a chat
log. If the registry is missing something, fix the registry.

## Reading

| Question | Tool |
|---|---|
| One object, its evidence and who cites it | `claims_show {id}` (`full: true` for the body) |
| Everything with a status, kind or text | `claims_list {ns, status?, kind?, where?, text?}` |
| What it rests on / what rests on it | `claims_deps {id}` / `{id, reverse: true, transitive: true}` |
| A precise question | `claims_query {ns, sql}` (one read-only SELECT on the derived tables) |
| Consistency | `claims_check {ns}` |
| This notebook's objects on disk | `py $R/notebook.py ls [--kind K] [--status S]` |
| An experiment review pair | `py $R/reviews.py decide <lab-id>` |

Easy to misread: `supported` is a bounded computation that found no counterexample —
**not a proof**. `sketch` is an argument never verified. `proved-modulo` names its
missing inputs in `modulo`.

## Writing

- **A new object** (unsettled only: `open`, `conjectured`, `sketch`): `claims_new {id,
  title, status?, kind?}` in this instance's namespace, then `prover` fills the
  statement, `depends_on`, `bears_on` and history in the file. A definition, example,
  assumption or direction carries no status: `py $R/notebook.py new <kind> <id>
  --title ...`.
- **Evidence** is append-only: `claims_attach_evidence {id, row}` with a row
  `type | ref | verdict | run_id | note`. A grader's verdict is attached by claim-keeper
  (or the Expert's review-chair), never by the grader.
- **A status change** goes only through `claim-keeper` (`claims_set_status`), with its
  grounds: two agreeing reviews or the human's word. Anyone else proposes it with
  `claims_propose_status {id, status, reason, grounds}`, which files a `decision` ticket
  to claim-keeper. The `status_guard` hook denies every other agent the `status:` line.
- **Nothing is deleted.** A false claim becomes `refuted`; a repaired statement is a new
  object that `supersedes` the old one, whose lifecycle becomes `superseded`: create the
  new object (`claims_new`), then propose status `superseded` for the old one with
  `grounds.superseded_by` naming the new id; claim-keeper's `claims_set_status` writes
  the lifecycle and the one-way `supersedes` link.
- After an edit to a record file, the `claims_edit_check` hook runs the registry
  engine's `check <file>` (and, on the s1 profile, a blocking `build`); fix what it
  reports. From a shell the same engine is `py -m registry --repo <home> <command>`
  (cwd `academy/academy`), or the old command lines, which are now shims onto it.
