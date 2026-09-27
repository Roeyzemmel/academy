# The ticket protocol

Plan sections 2, 5 and 7. This is the contract between instances. Every builder
codes against it. `academy/lib/academy_common.py` implements it (vendored as
`<plugin>/scripts/_academy.py`), and `academy/permissions.json` holds the permission
tables. Where this text and the code disagree, fix one of them in the same commit.

## 1. Parties and names

- An **instance** is a role bound to a home and one or more domains. Its name is
  `<role>@<name>`, where `<role>` is one of `author researcher expert scientist` and
  `<name>` matches `[a-z0-9][a-z0-9-]*`. The name must be a key of `workspace.json`
  `instances`. Examples: `author@bi`, `researcher@slope1`, `expert@ts`,
  `scientist@ts`.
- **`human`** is Roey. The main session has no `agent_type`, so it always acts as
  `human`, whatever home it runs in.
- **An agent** is named by its bare name, with the plugin namespace stripped:
  `author:math-writer` is read as `math-writer`. `agent_identity(event)` returns
  `(namespace, bare_name)`. Bare names are unique across the five plugins (see the
  roster in `permissions.json`).
- **The caller's instance** is the instance whose home contains the session's `cwd`
  (`find_home` + `instance_for_home`). An agent running in the BI home acts for
  `author@bi`. The base plugin's agents (`concierge`, `explainer`, `usage-analyst`)
  act for the instance of the home they run in. From no home at all, they act as
  `human` only when they file something Roey has confirmed.
- **A speaker** in a thread is written `human`, `<instance>` or
  `<instance>/<bare-agent>`, for example `researcher@slope1/prover`. It contains no
  colon and no space.

## 2. The board

`C:\Work\Math\board\` (from `workspace.json` `board`) is a git repo, LF only.

```
board/
  .ids/next-ticket        next free ticket number: one integer, then "\n"
  .ids/next-packet        next free packet number
  .ids/lock               exclusive lock; exists only while an id is being allocated
  author@bi/              tickets addressed TO author@bi
    T-0007-check-lemma-4-2.md
  researcher@slope1/  expert@ts/  scientist@ts/
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
from: author@bi
to: expert@ts
status: open
priority: normal
ask: Verify paper:lem:strip-bound and say whether Theorem 1.3 still needs it.
deliverable: A review packet with two verdicts; the ticket result names the verdict.
refs: [paper:lem:strip-bound, paper:thm:main, file:author@bi/sections/billiards.tex]
agenda: paper:thm:main
domain: translation-surfaces
parent:
blocks: []
waiting_on: []
budget:
  runs: 2
  max_model: fable
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

- 2026-09-27 author@bi/math-writer: opened; the proof of 4.2 uses the strip bound twice.
- 2026-09-27 expert@ts/review-chair: status open -> accepted
- 2026-09-28 expert@ts/review-chair: status accepted -> in-progress
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
| `blocks` | list of ticket ids | no | sender (server mirrors) | Tickets waiting on this one |
| `waiting_on` | list of ticket ids, instances or `human` | iff `blocked` | receiver | What the receiver waits for |
| `budget` | map `{runs: int >= 1, max_model: fable\|opus\|sonnet\|haiku}` | yes | sender | Agent runs allowed and the heaviest model; default from `academy.json` `budget.ticketDefault` |
| `result` | str, one line | iff `delivered`/`closed` | receiver | The answer in one line; detail in `## Result` |
| `packets` | list of packet ids | no | receiver | Packets produced for this ticket |
| `created` | `YYYY-MM-DD` | yes | system | |
| `updated` | `YYYY-MM-DD` | yes | system | Set on every write |

An empty value is written `key:` and reads as null. An empty list is written `[]`.

**`kind`** takes one of these values (`TICKET_KINDS`); anything else is `other`:

| kind | Typical route | Asks for |
|---|---|---|
| `verify` | → expert | a proof review (two rigor-reviewer runs, decision table) |
| `cite` | → expert | a bibliography entry plus a card with a verbatim quote |
| `lookup` | → expert | a quick answer from the clerk |
| `referee` | → expert | a whole-paper referee packet |
| `prove` | → researcher | a proof, or a new argument the Author may not invent |
| `review-experiment` | → researcher | two experiment-reviewer runs on a finished report |
| `generalize` | → researcher | conjectured generalizations of a reviewed experiment's `## Conclusion` (see 6.2) |
| `experiment` | → scientist | a new experiment and its report |
| `test` | → scientist | a test of one conjectured generalization, starting from its falsifier |
| `code` | → scientist | developer or test-engineer work, including academy scripts |
| `notation` | → expert / author | a domain-notation change or a project notation decision |
| `build` / `figure` | → author | toolchain or figure work |
| `decision` | → human, or → the claim-keeper via `claims_propose_status` | a choice only the receiver may make |
| `question` | any | a question that needs more than a lookup |
| `other` | any | anything else |

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
`closed` / `rejected` / `cancelled` to `open`.

| From | To | Who | Also required |
|---|---|---|---|
| open | accepted | receiver | |
| open | rejected | receiver | reason in thread |
| open | blocked | receiver | `waiting_on` non-empty |
| open | cancelled | sender | reason in thread |
| accepted | in-progress | receiver | |
| accepted | blocked | receiver | `waiting_on` non-empty |
| accepted | rejected | receiver | reason in thread |
| accepted | cancelled | sender | reason in thread |
| in-progress | delivered | receiver | `result` non-empty |
| in-progress | blocked | receiver | `waiting_on` non-empty |
| in-progress | cancelled | sender | reason in thread |
| blocked | accepted | receiver | `waiting_on` cleared |
| blocked | in-progress | receiver | `waiting_on` cleared |
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

**Blocking bookkeeping.** When a ticket enters `blocked` with a ticket id in
`waiting_on`, the server adds this ticket's id to that ticket's `blocks`. When the
awaited ticket closes, `session_start` lists the blocked tickets it frees; they are
not auto-resumed.

**Execution.** Nothing runs on its own. `/<role>:inbox` takes the receiver's `open`
and `accepted` tickets, ordered by priority, then agenda position, then id. It
handles at most `budget.itemsPerRun` (at most 3) of them, serially. Each ticket
spends at most its own `budget.runs` agent runs at no heavier model than
`budget.max_model`. If the ticket needs more, the receiver moves it to `blocked` with
`waiting_on: [human]` and a thread line asking for more budget.

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
  `may_call(perms, tool, bare_name)`. The server then checks the substance: parties,
  transitions, field ownership, namespace, statuses and grounds.

## 6. Worked flows

### 6.1 Verify

1. `author@bi` files a `verify` ticket to `expert@ts`.
2. review-chair moves it `accepted`, then `in-progress`, and runs the two
   rigor-reviewer runs.
3. review-chair creates packet `P-NNNN` (kind `verification`), sets `packets`, then
   `result: "CONFIRMED x2; recolour proposed"`, then `delivered`.
4. The author's math-editor closes the ticket after the recolour lands.

### 6.2 Generalize from an experiment conclusion (Researcher)

1. `scientist@ts` finishes an experiment. `/scientist:experiment` writes a report
   packet (kind `experiment-report`, with a mandatory `## Conclusion`), then files a
   `review-experiment` ticket to `researcher@slope1`.
2. The two experiment-reviewer runs land. claim-keeper attaches the verdicts, and
   the review ticket is delivered and closed.
3. Researcher opens a `generalize` ticket to itself, or the human asks through the
   desk: `refs: [lab:<claim>, P-<report>]`.
4. `/researcher:generalize` has `prover` read the report's `## Conclusion` and
   propose generalizations: a wider class, a relaxed hypothesis, the pattern behind
   the data, or the governing invariant. Each one is created with `claims_new` as a
   `conjectured` object, with `bears_on: [lab:<claim>]` and a falsifier (the smallest
   case where it could fail).
5. One `test` ticket per generalization goes to `scientist@ts`:
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
