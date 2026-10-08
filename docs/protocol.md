# The ticket protocol

Plan sections 2, 5 and 7. This is the contract between instances. Every builder
codes against it. `academy/lib/academy_common.py` implements it (vendored as
`<plugin>/scripts/_academy.py`), and `academy/permissions.json` holds the permission
tables. Where this text and the code disagree, fix one of them in the same commit.

## 1. Parties and names

- An **instance** is a role bound to a home and one or more domains. Its name is
  `<role>@<name>`, where `<role>` is one of `author researcher expert scientist` and
  `<name>` matches `[a-z0-9][a-z0-9-]*`. The name must be a key of `workspace.json`
  `instances`. Examples: `author@main`, `researcher@alpha`, `expert@main`,
  `scientist@main`.
- **`human`** is Roey. The main session has no `agent_type`.
  The main session inside a role home files tickets as that home's instance, speaker
  `<instance>/main`. Only `/academy:board`, `/academy:desk` and `/academy:decide` file
  as `human` from a home (`--as human` / `as_human`), after Roey confirms. Every other
  write by the main session is still the human's.
- **An agent** is named by its bare name, with the plugin namespace stripped:
  `author:math-writer` is read as `math-writer`. `agent_identity(event)` returns
  `(namespace, bare_name)`. Bare names are unique across the five plugins (see the
  roster in `permissions.json`).
- **The caller's instance** is the instance whose home contains the session's `cwd`
  (`find_home` + `instance_for_home`). An agent running in the paper home acts for
  `author@main`. The base plugin's agents (`concierge`, `explainer`, `usage-analyst`,
  `secretary`) act for the instance of the home they run in. From no home at all,
  they act as `human` only when they file something Roey has confirmed. An agent of a role
  plugin acts only for an instance of its own role: `expert:librarian` running in
  the paper home is refused by the server rather than filing as `author@main`.
- **Cloud sessions: no instance for agents.** The MCP server is one long-lived process,
  and it takes the acting instance from *its own* `cwd` (or `$ACADEMY_CWD`), fixed when it
  starts; it never sees the `cwd` of the agent that calls it, so spawning a subagent from
  another directory changes nothing (tested 2026-10-08: `claim-keeper` spawned inside the
  Researcher home was still refused). In a cloud session the server starts outside every
  home, so a role agent has no instance and every ticket write that needs one is refused
  with "agent X runs outside every academy home" (`claim-keeper` could set statuses, which
  do not need an instance, but not update tickets). The main session acts as `human` there
  and closes the tickets itself. A fix has to resolve the agent's instance per call
  (for instance the ticket's recipient when it has the agent's role, or the agent's home
  passed by the caller handshake); until then, record statuses through the agent and close
  tickets from the main session.

- **How the server learns the caller (the caller handshake).** An MCP server does
  not see which agent called it, and a PreToolUse hook can rewrite a call's
  arguments only by also auto-approving it. So `mcp_write_gate` records, for every
  call it does not deny, the caller (`human`, or the namespaced agent type) under a
  key made of the tool name and the exact arguments, in `~/.claude/academy/callers/`
  (`$ACADEMY_CALLER_DIR` overrides it). The server consumes the matching record
  (`record_caller` / `claim_caller` in `academy_common`). With no live record
  (the hook did not run, or ran more than ten minutes earlier) the server refuses
  every write tool, and reads proceed as unverified. The argument `caller` is
  reserved: the hook denies it and the server refuses it, so no agent can name
  itself. Residual trust: an agent with a shell could forge a record by writing the
  directory directly (Edit and Write to it are denied by `generated_view_guard`), so the read-only agents must be given no shell (a requirement on the role plugins).
- **The hook reads its event as UTF-8, and the key must match byte for byte.**
  Claude Code writes the event as UTF-8; the server reads its stdin as UTF-8 too.
  `read_event` therefore reads `sys.stdin.buffer` and decodes it as UTF-8 (a BOM is
  dropped), bypassing the text layer: on Windows, unless `PYTHONIOENCODING` or
  `PYTHONUTF8` is set, Python decodes a piped stdin with the ANSI codepage (cp1255
  here), so a character such as `±` reached the hook mangled (`ֲ\xb1`), the
  hook's key differed from the server's, and the server refused the write with "the
  caller of <tool> could not be identified: no mcp_write_gate record for this call".
  That was seen on 2026-09-28 on `tickets_update` (T-0007) and fixed by T-0070
  (regression test in `academy/tests/test_hooks.py`). Non-ASCII arguments are
  therefore fine. If that refusal ever recurs on a call with a non-ASCII argument,
  retry it in plain ASCII (`+/-`, `--`, LaTeX); if the ASCII call passes, the
  encoding fault is back, so file a ticket.
- **A speaker** in a thread is written `human`, `<instance>` or
  `<instance>/<bare-agent>`, for example `researcher@alpha/prover`. It contains no
  colon and no space.

## 2. The board

`$ACADEMY_BOARD` (`workspace.json` `board`) is a git repo, LF only.

```
board/
  .ids/next-ticket        next free ticket number: one integer, then "\n"
  .ids/next-packet        next free packet number
  .ids/lock               exclusive lock; exists only while an id is being allocated
  author@main/              tickets addressed TO author@main
    T-0007-check-lemma-4-2.md
  researcher@alpha/  expert@main/  scientist@main/
  human/                  tickets addressed TO human, plus RESUME.md and SUMMARY.md
  packets/<instance>/     review packets produced BY <instance>, P-NNNN-<slug>.md
  deep-dives/<id>.html    local copies of /academy:deep-dive artifacts
```

- **Folder rule.** A ticket lives in the folder of its `to`. It never moves, even
  when it closes; git keeps the history. The human re-routes a ticket by changing `to`,
  and the server then moves the file in the same write, keeping the filename.
- **Folder names.** An instance folder is named exactly after the instance (`@` is
  legal on Windows and Linux). `human` is literal. `packets`, `deep-dives` and `.ids`
  are reserved.
- **Non-ticket files.** Inside an instance folder or `human/`, files not matching
  `T-\d{4,}-*.md` are ignored by every tool. `human/RESUME.md` and
  `human/SUMMARY.md` are free Markdown.
- **Committing.** Tool writes do not commit. `session_start` and `/academy:board sync`
  commit all pending board changes in one commit, with the message
  `board: <n> change(s)` and the attribution line. No push, no stash.

### File names

- A ticket file is `T-NNNN-<slug>.md` and a packet file is `P-NNNN-<slug>.md`.
- `NNNN` is at least four digits, zero-padded, and grows past 9999 unchanged
  (`T-10000`).
- `<slug>` is `slugify(title)`: lower-case, runs of anything outside `[a-z0-9]`
  collapsed to `-`, trimmed, at most 40 characters, `ticket` / `packet` if empty.
- The name is fixed at creation. Retitling never renames the file.
- Lookups go by id (`find_ticket(board, "T-0007")`), never by slug.

### Id allocation

`allocate_id(board, "ticket" | "packet")` does the following:

1. Create `board/.ids/lock` with `O_CREAT|O_EXCL` and write `"<pid> <unix time>"`
   into it. If the lock exists, retry every 50 ms for up to 10 s, then raise
   `LockTimeout`. A lock file older than 30 s is stale: break it and retry.
2. Read `next-<kind>`; a missing or unreadable counter reads as 1.
3. Take `n = max(counter, 1 + highest id of that kind anywhere on the board)`. A lost
   counter can therefore never reissue an id.
4. Write `n + 1` back atomically, release the lock and return `T-%04d` / `P-%04d`.

One lock covers both counters. Nothing else takes the lock. After allocating, write
the ticket or packet file with `atomic_write`, outside the lock.

## 3. The ticket file

```markdown
---
id: T-0007
title: Check whether Lemma 4.2 is needed
kind: verify
from: author@main
to: expert@main
status: open
priority: normal
ask: Verify paper:lem:strip-bound and say whether Theorem 1.3 still needs it.
deliverable: A review packet with two verdicts; the ticket result names the verdict.
refs: [paper:lem:strip-bound, paper:thm:main, file:author@main/sections/billiards.tex]
agenda: paper:thm:main
domain: translation-surfaces
parent:
blocks: []
waiting_on: []
budget:
  runs: 2
result:
packets: []
created: 2026-09-27
updated: 2026-09-27
---

## Ask

Free Markdown detail of the ask (sender-owned). Defaults to the `ask` line.

## Result

Free Markdown detail of the result (receiver-owned). Empty until delivered.

## Thread

- 2026-09-27 author@main/math-writer: opened; the proof of 4.2 uses the strip bound twice.
- 2026-09-27 expert@main/review-chair: status open -> accepted
- 2026-09-28 expert@main/review-chair: status accepted -> in-progress
  Run A dispatched; B follows only if A is positive.
```

### Frontmatter schema

The keys are written in this order (`TICKET_KEY_ORDER`). No other keys are allowed.

| Key | Type | Req. | Owner | Meaning |
|---|---|---|---|---|
| `id` | `T-NNNN` | yes | system | From `allocate_id`; equals the filename prefix |
| `title` | str, one line | yes | sender | Short name; the slug source at creation |
| `kind` | enum, below | yes | sender | What sort of work; the receiver routes by it |
| `from` | instance \| `human` | yes | system | The caller's instance at creation |
| `to` | instance \| `human` | yes | human only after creation | The receiver; also the folder |
| `status` | enum, section 4 | yes | receiver (+ the sender's exits) | Lifecycle state |
| `priority` | `high` \| `normal` \| `low` | yes | sender | Default `normal` |
| `ask` | str, one line | yes | sender | The request in one sentence; detail goes in `## Ask` |
| `deliverable` | str, one line | yes | sender | What "done" looks like, checkable by the sender |
| `refs` | list of refs | no | sender | Objects the ask concerns, in the ref forms below |
| `agenda` | claim id \| `global` \| empty | no | sender | The Author agenda entry this unblocks, which sets precedence |
| `domain` | pack name | no | sender | Routing record; defaults to the receiver's first domain |
| `parent` | ticket id \| empty | no | sender | The ticket this one was spawned from |
| `final_to` | role \| instance \| empty | no | sender | The role (or instance) the request is really for; set on relayed tickets; a receiver whose role is not `final_to` hands the ticket to its relay |
| `campaign` | registry id \| empty | no | sender | The target of the campaign this ticket belongs to; `inbox.py --campaign <target>` lists only such tickets. Omitted unless set |
| `blocks` | list of ticket ids | no | sender (server mirrors) | Tickets waiting on this one |
| `waiting_on` | list of ticket ids, instances or `human` | iff `blocked` | receiver | What the receiver waits for |
| `budget` | map `{runs: int >= 1}`, optionally `max_model: fable\|opus\|sonnet\|haiku` | yes | sender | Agent runs allowed; default `runs` from `academy.json` `budget.ticketDefault`. The model is not the sender's: an agent runs on its agent file's `model:`. `max_model`, if given, is an advisory note and never blocks a route |
| `result` | str, one line | iff `delivered`/`closed` | receiver | The answer in one line; detail in `## Result` |
| `packets` | list of packet ids | no | receiver | Packets produced for this ticket |
| `created` | `YYYY-MM-DD` | yes | system | |
| `updated` | `YYYY-MM-DD` | yes | system | Set on every write |

An empty value is written `key:` and reads as null. An empty list is written `[]`.

**`kind`** takes one of these values (`TICKET_KINDS`); anything else is `other`. The
route is required: `to` is the role named. "Filed by" is the sending role, which
section 5.1 restricts to the receiver's neighbours in the chain (or the same role, or
`human`) and, across roles, to the liaisons of that direction:

| kind | Route (required) | Filed by | Asks for |
|---|---|---|---|
| `verify` | → expert | the Author, the Researcher, or the Expert itself (an input that is itself a proof) | a proof review (two rigor-reviewer runs, decision table) |
| `cite` | → expert | the Author, the Researcher (for the Scientist, its `lit-request` relay), or the Expert itself | a bibliography entry plus a card with a verbatim quote |
| `lookup` | → expert | the Author, the Researcher, or the Expert itself | a quick answer from the clerk |
| `referee` | → expert | the Author | a whole-paper referee packet |
| `prove` | → researcher | the Expert (a repair after a review), or the Researcher itself | a proof, or a new argument the Author may not invent (an Author asks through `research`) |
| `research` | → expert, then → researcher, relayed with `final_to` | the Author to the Expert; the Expert's research-intake to the Researcher | a research request (a new argument, an experiment) the Author may not invent; research-intake prepares it and relays it toward `final_to` (5.1) |
| `note` | → author, informational | the Expert | a literature result the Author should know, unsolicited; lands with math-writer |
| `review-experiment` | → researcher | the Scientist | two experiment-reviewer runs on a finished report |
| `generalize` | → researcher | the Researcher itself | conjectured generalizations of a reviewed experiment's `## Conclusion` (see 6.2) |
| `experiment` | → scientist | only the Researcher, from its researcher -> scientist liaisons (5.1); the Scientist also to itself | a new experiment and its report |
| `test` | → scientist | only the Researcher, from its researcher -> scientist liaisons (5.1); the Scientist also to itself | a test of one conjectured generalization, starting from its falsifier |
| `code` | → scientist | only the Researcher, from its researcher -> scientist liaisons (5.1); the Scientist also to itself (an "Upstream:" ticket) | developer or test-engineer work, including academy scripts |
| `notation` | → expert / author | the Author to the Expert (a domain-notation change; the Scientist's goes through the Researcher with `final_to: expert`); the Expert or the Author itself to an Author | a domain-notation change or a project notation decision |
| `build` / `figure` | → author | the Author itself, or the Expert | toolchain or figure work |
| `write` / `apply` / `copy` / `sweep` | → author, the Author's own | the Author itself (filed with `board.py new`, the margin-notes skill or `agenda.py gaps --file`; `refs` carries the claim and `agenda` its entry; the Author has no roadmap, the board is its only queue) | prose, a mechanical edit, a copy-edit, or the note sweep, routed by kind to math-writer, math-editor or note-sweeper |
| `decision` | → human, or → the claim-keeper via `claims_propose_status` | any role (`claims_propose_status` is exempt from the chain) | a choice only the receiver may make |
| `question` | → a neighbour, or the same role | any role, within 5.1 | a question that needs more than a lookup |
| `other` | → a neighbour, or the same role | any role, within 5.1 | anything else |

`human` is outside the chain and may file to any instance (5.1, rule 1).

**Ref forms** (in `refs`, in packets, and in thread text):

- `<ns>:<id>` for a registry object, e.g. `paper:lem:strip-bound`, `lab:ew-check`,
  `s1:Q2`.
- `T-NNNN` for a ticket and `P-NNNN` for a packet.
- `bib:<key>` for a bibliography key, optionally with a pinpoint:
  `bib:LMW16#Thm1.3`.
- `file:<instance>/<path relative to that home>`, with forward slashes.
- A plain `https://` URL.

### Body

The body has three sections, always in this order. It never has any other `##`
heading.

- `## Ask`, owned by the sender;
- `## Result`, owned by the receiver;
- `## Thread`, always last and append-only.

### Thread format

- One entry is one line, `- YYYY-MM-DD <speaker>: <text>`, which matches
  `^- (\d{4}-\d{2}-\d{2}) ([^\s:]+): (.*)$`.
- A multi-line entry continues on lines indented by exactly two spaces.
- Entries are only ever appended, at the end of the section. An existing line is
  never edited, reordered or deleted (`thread_is_append_only`).
- The server appends one line for every status change, as
  `status <old> -> <new>`, optionally followed by `: <reason>`. It also appends one
  line for every field change by a party, as `set <field>: <new value>`.
- A `rejected` or `cancelled` transition, and a `delivered -> in-progress` return,
  must carry a reason in the same write.

### Frontmatter subset

Tickets and packets share one YAML subset (`read_frontmatter` / `write_frontmatter`).

- **Scalars.** A bare string, a JSON double-quoted string, a `'single'` string,
  an int, a float, `true`/`false`, or null (empty, `~`, `null`). Dates stay strings.
- **Inline lists** of scalars: `[a, "b, c", 3]`. Block lists (`- a` lines indented
  under the key) are read but never written.
- **One-level maps.** A block map indented by two spaces. Inline `{a: 1}` is read
  but never written.
- Nothing else: no nesting, no multi-line strings, no anchors.
- `#` after a space outside quotes starts a comment, which is dropped on rewrite.
- The writer quotes (as JSON) any string that would not read back unchanged.
  `write_frontmatter(*read_frontmatter(t)) == t` holds for canonical files.

The registry's object files (`evidence[]`, `history[]`) are richer, so they use the
registry engine's own parser, not this one.

## 4. Lifecycle

```
            +-----------> rejected (receiver)
            |
open --> accepted --> in-progress --> delivered --> closed (sender)
  |         |              |              |
  |         +----> blocked <-+            +--> in-progress (sender: "returned")
  +--------------> blocked --> accepted | in-progress (receiver)
any non-terminal state --> cancelled (sender)
```

Here is the full table (`TRANSITIONS` in the lib, `tickets.transitions` in
permissions.json). **The human may make any transition**, including re-opening
`closed` / `rejected` / `cancelled` to `open` and leaving a dead route (below).

| From | To | Who | Also required |
|---|---|---|---|
| open | accepted | receiver | |
| open | rejected | receiver | reason in thread |
| open | blocked | receiver | `waiting_on` non-empty, or a dead route (below) |
| open | cancelled | sender | reason in thread |
| accepted | in-progress | receiver | |
| accepted | blocked | receiver | `waiting_on` non-empty, or a dead route |
| accepted | rejected | receiver | reason in thread |
| accepted | cancelled | sender | reason in thread |
| in-progress | delivered | receiver | `result` non-empty |
| in-progress | blocked | receiver | `waiting_on` non-empty, or a dead route |
| in-progress | cancelled | sender | reason in thread |
| blocked | accepted | receiver | `waiting_on` cleared; a dead route needs `--reopen` |
| blocked | in-progress | receiver | `waiting_on` cleared (never a dead route, except by the human) |
| blocked | cancelled | sender | reason in thread |
| delivered | closed | sender | |
| delivered | in-progress | sender | reason in thread ("returned") |

Terminal states: `closed`, `rejected`, `cancelled`.

**Party rules:**
- An instance is the *sender* when it equals `from`, and the *receiver* when it
  equals `to`. It may be both.
- A ticket addressed to `human` is handled only by the human, so every transition
  on it is a human transition.

**Field ownership** (`tickets.fields` in permissions.json):
- The sender edits the sender fields and `## Ask`.
- The receiver edits the receiver fields and `## Result`.
- The system fields are written by the server only.
- `to` is changed only by the human.
- Any non-read-only caller may append to `## Thread`.
- The human may edit anything, in VS Code too. `ticket_edit_check` then validates
  the file (`validate_ticket`) and the append-only thread.

**Two kinds of `blocked`**, told apart by their fields (receiver fields):

| kind | fields | meaning | inbox |
|---|---|---|---|
| pending | `waiting_on` non-empty (ticket ids, instances or `human`) | waiting for a ticket, an instance or Roey | not taken; return legs as above |
| dead route | `blocked_by` (a ticket or registry id: `T-0007`, `GEO-31`, `paper:lem:x`) and `reopen_if` (one line) | the route ends at a result as strong as the goal, or at a refutation; reopens only for a materially new mechanism, invariant or construction | never taken |

- `blocked` needs `waiting_on` **or** both `blocked_by` and `reopen_if`; both kinds at
  once is an error. A dead-route block also needs a thread line `tried: <what was
  tried>` (`board.py transition ... blocked --blocked-by ID --reopen-if LINE --reason
  "<what was tried>"` writes it); after a reopening the ticket needs a fresh `tried:` line
  of its own for the next dead-route block. `blocked_by` must be a ticket id or a registry
  id (`GEO-31`, `Q1`, `ns:id`), not free text. `validate_ticket` and the one shared rule
  function (`apply_blocking`, used by `board.py transition` and the MCP `tickets_update`,
  which write the same thread lines in the same order: `tried:`, `set blocked_by ...` or
  `set waiting_on ...`, `reopened:`, then the status line) enforce this; the transitions
  themselves are unchanged.
- **Reopening** a dead-route ticket is `blocked -> accepted` by the receiver with
  `--reopen "<the new mechanism>"` (MCP: `tickets_update` argument `reopen`); it
  appends a `reopened: <mechanism>` thread line and clears both fields. Nothing else
  reopens one (not `blocked -> in-progress`, not the sender). The sender may still
  cancel, with a reason. A pending block reopens as before, with no `--reopen`, and
  `--reopen` / `reopen` on anything but a dead route's `blocked -> accepted` is an error
  (also without a status change).
- **The human** may leave a dead route by any transition (`accepted`, `in-progress`,
  `open`, `cancelled`, ...), giving a `--reason` (or `--reopen`) as the record: it clears
  both fields, and a move to `accepted` writes it as the `reopened:` line. (`board-sync` exempts the human's move when the
  event's sender is a configured human login or the new last thread entry is `human`'s; see
  `docs/github-board.md`.)
- In a campaign, an approach object's `blocked_by` / `reopen_if` are the same fields
  with the same rules.

**Blocking bookkeeping.** When a ticket enters `blocked` with a ticket id in
`waiting_on`, the server adds this ticket's id to that ticket's `blocks`. When the
awaited ticket closes, `session_start` lists the blocked tickets it frees; they are
not auto-resumed.

**Execution.** Nothing runs on its own. `/<role>:inbox` takes, in this order, the
receiver's `in-progress` tickets (unfinished work is resumed before anything new
starts), the relay parents ready for their return leg (5.2), then its `open` and
`accepted` tickets, ordered by priority, then agenda position, then id. Blocked
tickets are never taken except a return leg (a ticket carrying both `blocked_by` and
`reopen_if` is a dead route and is never taken, return leg or not). It handles at most `budget.itemsPerRun` (at most 3) of them, serially, and after
each one the ticket must be `delivered`, `blocked` with its reason, or `rejected`
(`inbox.py --check T-NNNN`); an unfinished ticket is reported, not redispatched, and no
other ticket is taken while it is unfinished. When the checkpoint finds the ticket
finished (`delivered` or `closed`, `rejected` or `cancelled`; not `blocked`) on the
workspace's own board, it runs the workspace's `scripts/ship.py checkpoint --ticket
T-NNNN --role <role> --only <repos>` (in the workspace root, 90 s timeout) to commit and
push the ticket's work on its branch. The repos are the instance's home submodule,
`board`, and `library` for the Expert (`board` alone, said on stderr, when the home is
not a submodule); under `--only` no other repo is touched and a dirty repo still on
`main` is refused, not moved. Skipped when that script is absent, when workspace.json
says `"shipCheckpoint": false`, or when the session (`$CLAUDE_PROJECT_DIR`, else the cwd)
is outside the workspace root or in a worktree under it (a `.claude/worktrees` path
segment); one stderr line then gives the command to run by hand, always with the same
`--only` (the unscoped manual run is for the session that owns the checkout). Never
fatal: anything that goes wrong is one warning line on stderr, and the exit code is
`--check`'s, unchanged. Selection, ordering, return legs and the
checkpoint live once, in the academy library (`inbox_core` in `academy_common.py`); each
role's `scripts/inbox.py` is a thin wrapper and `scripts/routes.py` its routing table.
`--n N` (alias `--limit`) lowers the count, `--all` lists without taking,
`--campaign <target>` lists only tickets carrying `campaign: <target>` and lifts the cap
of 3 on its own (a campaign has its own caps; `--n` still lowers it). An in-progress ticket
of the instance outside the campaign is not listed but is reported in `unfinished` (and as
`outside_campaign` in `--json`): resume it first. `/academy:inbox` runs every instance in turn
(Author, Expert, Researcher, Scientist) under one cap. Each ticket
spends at most its own `budget.runs` agent runs. Each agent runs on the model of its
agent file (never above the home's `budget.maxModel`); a ticket's `budget.max_model`
is an advisory note from the sender, not a gate. If the ticket needs more runs, the
receiver moves it to `blocked` with `waiting_on: [human]` and a thread line asking for
more budget.

## 5. Permissions

`academy/permissions.json` is authoritative. Here is a summary:

- **The human may call everything.** A call with no `agent_type` is the human.
- **An agent** must be in `roster`. For a gated write tool, it must be in the tool's
  expanded `allow` list and not in its `deny` list (deny wins). `@all`, `@producers`,
  `@readonly` and the other groups expand from `groups`. Read tools are open to all.
- **The grader rule.** The `readonly` group holds the graders plus `explainer` and
  `clerk`. It may call no write tool. A grader's verdict reaches the files through a
  SubagentStop hook, which calls the library directly and not the MCP server.
- **Enforcement.** The PreToolUse hook `mcp_write_gate` checks
  `may_call(perms, tool, bare_name)` and records the caller (section 1). The server
  re-checks `may_call` against the recorded caller, then the substance: parties,
  transitions, field ownership, namespace, statuses and grounds.

### 5.1 The ticket chain

`academy/permissions.json` `tickets.edges` is the source of truth (the chain, `maxHops`,
the liaisons per direction, `exempt`); the tables below summarise it.

**The rule.** The chain is `[author, expert, researcher, scientist]`. A ticket from S
to R, filed by agent A, is allowed iff one of:

1. S or R is `human`;
2. S and R have the same role (self-tickets, and researcher to researcher across
   domains);
3. the roles of S and R are adjacent in the chain **and** A is on the liaison list of
   the direction role(S) -> role(R);
4. the ticket is clerical and exempt.

Roles, not instances, are compared. A refusal names the neighbour to file to instead
and its relay for that direction. Replies and deliveries on the same ticket,
`packets_create`, thread appends and re-routing `to` (human-only) create no new edge
and are not checked. A request that must cross a middle plugin carries `final_to`, and
the middle plugin's relay forwards it one hop.

**Liaisons per direction** (agents that may file across it; `main` is the main session
filing as its instance):

| Direction | Liaisons | Carries |
|---|---|---|
| author -> expert | `main`, `math-writer`, `notation-auditor`, `figure-maker` | verify, cite, referee, litwatch, notation, and `research` |
| expert -> author | `librarian`, `review-chair`, `research-intake`, `paper-liaison` | `note`, repair questions on `paper:` claims, forwarded questions and results |
| expert -> researcher | `research-intake`, `review-chair` | the prepared `research` ticket with its research block; prove/repair after a review |
| researcher -> expert | `main`, `lead-researcher`, `prover`, `lit-request` | verify, cite, literature asks; forwarded lab cite asks |
| researcher -> scientist | `main`, `lead-researcher`, `experiment-spec` | exact experiment and test specs |
| scientist -> researcher | `main`, `experimenter` | review-experiment, questions, results bearing on a claim |

**Relays.** The two middle roles each have two crossings, so there are four directional
relays. A relay checks, sharpens and forwards; it writes no mathematics, grades
nothing, uses no web and no shell, and makes one pass.

| Relay | Crossing |
|---|---|
| `expert:research-intake` | author -> (expert) -> researcher |
| `expert:paper-liaison` | researcher side -> (expert) -> author |
| `researcher:experiment-spec` | expert -> (researcher) -> scientist |
| `researcher:lit-request` | scientist -> (researcher) -> expert / author |

Their models are in the agent files' frontmatter.

**Recognising a relay ticket.** The check requires `to` to be a neighbour; `final_to`
may be any role further along the same direction. When a receiver's role is not
`final_to`, its inbox routes the ticket to the relay of the matching crossing, whatever
the kind. The relay fails fast (delivers back with the reason), sharpens (a research
block or an experiment spec), then forwards a child ticket with `parent` = the received
ticket and `final_to` kept, and sets the received ticket `blocked`, `waiting_on` the
child. **The return leg**: once every awaited child is `delivered` or terminal (and the
parent waits on no `human`), the receiver's inbox takes the blocked parent again and
hands it to the same relay, which closes a delivered child (it is the child's sender),
moves the parent `blocked` -> `in-progress` -> `delivered` (`blocked -> delivered` is
not a transition), and writes a short result pointing at the child. A `research`
ticket to the Expert with no `final_to` reads as `final_to: researcher`.

**Hop limit.** A relay chain has at most `maxHops` (3) links. Only consecutive
ancestors that carry `final_to` count; an ordinary `parent` link is not a relay hop.
A relay within a relay can exceed it: a Scientist question with `final_to: author`
filed with `parent` set to an experiment-spec child already sits under three relay
links, and the check refuses the next hop. A new question starts a fresh chain: file
it with no `parent` and name the earlier ticket in `refs`.

**Caller identity.** The MCP tool `tickets_create` is the enforced path: the server
knows the calling agent. The CLI identity (`board.py new --as <instance> --agent
<name>`) is self-declared, and without `--agent` it records `main`, so the CLI half of
the gate is advisory: it catches a wrong edge, not a wrong agent.

**Exempt** (clerical, not requests): claim-keeper `decision` tickets from
`claims_propose_status` (still checked to go to the keeper of the claim's namespace),
usage-analyst (files only to `human`), and concierge (files as `human` after Roey
confirms).

## 6. Worked flows

### 6.1 Verify

1. `author@main` files a `verify` ticket to `expert@main`.
2. review-chair moves it `accepted`, then `in-progress`, and runs the two
   rigor-reviewer runs.
3. review-chair creates packet `P-NNNN` (kind `verification`), sets `packets`, then
   `result: "CONFIRMED x2; recolour proposed"`, then `delivered`.
4. The author's math-editor closes the ticket after the recolour lands.

### 6.2 Generalize from an experiment conclusion (Researcher)

1. `scientist@main` finishes an experiment. `/scientist:experiment` writes a report
   packet (kind `experiment-report`, with a mandatory `## Conclusion`), then files a
   `review-experiment` ticket to `researcher@alpha`.
2. The two experiment-reviewer runs land. claim-keeper attaches the verdicts, and
   the review ticket is delivered and closed.
3. Researcher opens a `generalize` ticket to itself, or the human asks through the
   desk: `refs: [lab:<claim>, P-<report>]`.
4. `/researcher:generalize` has `prover` read the report's `## Conclusion` and
   propose generalizations: a wider class, a relaxed hypothesis, the pattern behind
   the data, or the governing invariant. Each one is created with `claims_new` as a
   `conjectured` object, with `bears_on: [lab:<claim>]` and a falsifier (the smallest
   case where it could fail).
5. One `test` ticket per generalization goes to `scientist@main`:
   - `parent` is the generalize ticket;
   - `refs` are `[s1:<new id>, lab:<claim>]`;
   - `ask` is "test the falsifier first".

   Researcher also creates a packet of kind `generalization` listing them all.
6. A generalization that survives its test is proved through `/researcher:prove`. A
   generalization is never raised above `conjectured` by this flow.

### 6.3 Decision

A packet's decisions are answered by the human in `/academy:review`. The answers are
written into the packet (`docs/packet-template.md`), and one thread line goes into
the packet's ticket: `- <date> human: decision on P-NNNN D<k>: (<letter>) <option>`.

### 6.4 A research request from the Author

1. The Author's main session (`/author:inbox` files as `main`) or an Author agent
   (math-writer, figure-maker) files a `research` ticket to the Expert with
   `final_to: researcher`.
2. The Expert's inbox sees that `final_to` is not the Expert and hands it to
   research-intake, which either fails fast (delivers back with the reason: not pinned
   down, already answered by the library, settled by a registry claim) or writes the
   research block (cards with pinpoints, related claims with statuses, known results,
   open literature gaps) into a child `research` ticket to the Researcher, and blocks
   the parent on it.
3. The Researcher's inbox routes the `research` child to lead-researcher, which does
   the work.
4. The delivery goes back up hop by hop: the Researcher delivers the child; the
   Expert's inbox takes the blocked parent for its return leg, and research-intake
   closes the child and delivers the parent to the Author; math-writer lands it.
   Literature results the Author should know arrive as `note` tickets.

### 6.5 An experiment for the paper

1. The Author files a `research` ticket to the Expert with `final_to: scientist`.
2. research-intake checks it and forwards a child ticket to the Researcher, keeping
   `final_to`.
3. The Researcher's experiment-spec fails fast (no claim named, or the lab already has
   the result) or writes the experiment spec in the lab's header vocabulary, and files
   it to the Scientist.
4. The result is delivered back the same way: Scientist -> Researcher -> Expert ->
   Author (three links, the `maxHops` limit).

## 7. Hooks of the base plugin

The base plugin's hooks (`academy/hooks/hooks.json`) enforce parts of this protocol
directly. Each script imports the vendored lib `scripts/_academy.py`.

### 7.1 Generated views

A generated view is a file written by a script from other records (plan section 6).
It is never edited by hand: the fix is to change the source and rerun the generator.

- **The marker** is the exact text `generated by academy`, matched case-insensitively.
  A file carries it when one of its **first 5 lines** contains it. Every generator
  writes it in the file's own comment syntax, followed by the generator and a
  do-not-edit note:
  - Markdown and HTML: `<!-- generated by academy: <generator>; do not edit -->`
  - Python, shell, YAML, TOML: `# generated by academy: <generator>; do not edit`
  - TeX: `% generated by academy: <generator>; do not edit`
- A format with no comment syntax (JSON) cannot carry the marker. It is protected by
  being listed in the home's `paths.views` (docs/config.md) instead.
- **`generated_view_guard`** (PreToolUse, `Edit|Write|MultiEdit`) denies the edit,
  for every caller including the human, when the target file carries the marker or
  lies in the session's home and matches that home's `paths.views`.

### 7.2 `session_start`

Silent outside an academy home. Inside one, it validates `academy.json` and its
agreement with `workspace.json`. It raises `.ids/next-ticket` and `.ids/next-packet`
to at least one past the highest id on disk, under the id lock; it never lowers them.
It commits pending board changes (section 2); `ACADEMY_BOARD_COMMIT=0` turns the
commit off. It then prints one line of additionalContext:

```
academy: <instance> — N open tickets to you, M packets awaiting <human name>[; freed: T-0003, ...][; config: <problems>]
```

- *N* counts the tickets in `board/<instance>/` with status `open`, `accepted` or
  `in-progress`.
- *M* counts the packets in `board/packets/*/` whose `state` is `open`.
- *freed* lists this instance's `blocked` tickets whose `waiting_on` names only
  tickets, all of them terminal. They are not resumed.

### 7.3 `mcp_write_gate` and `ticket_edit_check`

- **`mcp_write_gate`** (PreToolUse, matcher `mcp__.*academy.*`) denies a tool listed
  in permissions.json `tools` when `may_call` refuses the caller, and any call that
  carries the reserved `caller` argument. It stays silent otherwise, so Claude
  Code's own permission prompts still apply, and records the caller for the server
  (section 1). The human, and read tools, always pass. An agent outside the roster
  may read but not write. It reads its event as UTF-8 whatever the console codepage
  (section 1), so non-ASCII arguments get the same key as on the server.
- **`ticket_edit_check`** (PostToolUse, `Edit|Write|MultiEdit`) looks only at files
  under the board.
  - For a ticket, it reports `validate_ticket` problems, an `id` that differs from
    the file name, a `to` that differs from the folder, and a body whose `##`
    sections are not exactly `Ask`, `Result`, `Thread`.
  - For a packet, it reports `validate_packet` problems.
  - It then compares a ticket with its version at the board's git `HEAD`. The thread
    must be append-only, for everyone. For an agent, it also reports every changed
    field or section the caller's party does not own, and every transition the
    caller may not make, including a `rejected`/`cancelled`/returned transition with
    no new thread line. `updated` is not checked.
  - A direct agent edit to the board is always reported, because agents change the
    board only through the MCP tools.
  - Findings are fed back to the model as a PostToolUse `block`.
