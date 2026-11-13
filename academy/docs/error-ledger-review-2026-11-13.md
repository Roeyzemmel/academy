# Error-ledger review, 2026-11-13

The third pass over the error ledger (`<board>/.errors/*.jsonl`), after
`workflow-triage-2026-10-09.md` and the follow-up of 2026-10-31 (commit `f9e4afc`,
"refusals that say what to do"). Window: 2026-10-14 .. 2026-11-13, 655 errors, 129 open
classes; 369 of the errors are after the 2026-10-31 fixes.

## What the ledger showed

1. **Most "regressions" were stale code.** 33 classes were resolved on 2026-10-31 with
   the fixing commit, and 20 of them recorded errors again. Their messages are the
   pre-fix wording through 2026-11-03 and on the Windows machine through 2026-11-07:
   the cloud sessions ran the academy checkout at the workspace's submodule pointer and
   the laptop the plugin cache `0.1.0`. The fixes held wherever they ran. The ledger
   could not tell, because an error record did not say which code produced it.
2. **A refusal that names the fix is still a failed call.** After the refusals had
   learnt to name the route, `open -> in-progress` was refused 12 more times (to
   2026-11-13), "delivered needs result" 12 times, a multi-line `ask` 8 times (18 in
   five weeks), "nothing to change" 6 times. In each the caller's intent was plain and
   legal; the tool can do it instead of explaining how to ask.
3. **One class held a third of the errors.** `Bash: exit code <n>` had 238 records. By
   cause (of the 161 after 2026-10-31): 22 an academy script called at a path where it
   is not (`academy/scripts/cowork.py`, `scripts/notebook.py` in a home, `cards.py`
   under the base plugin), 9 a here-document with broken quoting, 6 `python` on Windows
   (the Store stub), about 85 a command whose last stage exited non-zero with ordinary
   output (noise), the rest ad hoc Python and LaTeX failures of the work itself.
4. **Paths handed out by the plugin text.** 20 searches of `academy/academy/docs` (the
   docs are at the repo root; the plugins cite them as `docs/x.md`), reads of a
   deep-dive bundle over the Read limit (the explainer was told to copy it), review
   records given as an absolute path, a workspace-root path or the pass's
   `decision.md` and refused as "not found" or "none of the verdicts' refs".
5. **One class per target.** 60 of the 129 open classes were one message with a
   different claim id, instance or host (`the grounds do not support paper:cor:x`,
   `ENOTFOUND ems.press`).

## What changed (plugins 0.2.1)

| # | Change | Where | Ledger classes |
|---|---|---|---|
| 1 | A status move that is not one transition is walked when every status in between is `accepted` or `in-progress` and the caller may make every hop | `tickets_update` | `not a transition` (28 in window) |
| 2 | `deliver: true` on a delivered ticket amends the result or changes nothing; a call that changes nothing answers `changed: false` | `tickets_update` | `deliver ... is delivered`, `nothing to change` |
| 3 | Of a multi-line `ask` / `result` the first line is the field and the whole text goes to the body; a result given only as `result_detail` has its first line as the field; a wrapped title or deliverable is joined | `tickets_create`, `tickets_update` | `ask must be one line`, `delivered needs result`, `result must be one line` |
| 4 | `waiting_on`, `blocked_by`, `reopen_if` as arguments; arguments put inside `fields` are taken; a refused move to `blocked` shows the two call shapes | `tickets_update` | `a blocked ticket needs waiting_on`, `unknown ticket field 'result_detail'` |
| 5 | A non-party role agent acts for the instance of its role whose namespace the ticket names; the refusals say that `instance` is the caller's own instance, not a party | `Context.instance` | `agent cannot act for the instance` (18) |
| 6 | A `ref` / `verdict_file` in any form that names one existing file is recorded in the protocol's form; a `verdict_file` naming the pass means its first verdict; `\|` in an evidence note is rewritten | `workspace.canonical_ref`, `claims_set_status`, `claims_attach_evidence` | `not found on disk`, `none of the verdicts' refs`, `an evidence cell may not contain` |
| 7 | `tickets_get` given a packet id (and `packets_get` a ticket id) names the other tool | both | `a ticket id looks like` |
| 8 | A `py <path>/<academy script>.py` whose file is not there is denied before it runs, with the script's real path; on Windows `python` that is the Store stub is denied with "use `py`" | new hook `script_path_guard.py` | `Bash: script not found`, `Bash: python launcher missing` |
| 9 | The workplan prompts carry the full command of `cowork.py` / `notebook.py` | `workflows/workplan.js`, `inbox-clerk` | the nine `cowork.py` guesses of 2026-11-07 |
| 10 | The explainer writes only `{"sections": [...]}`; the renderer lays it over the gathered bundle (`--bundle`); it reads a large bundle in parts | `render_packets.py`, `explainer`, `/academy:deep-dive` | `file too large to read` (bundles) |
| 11 | A pointer at `academy/academy/docs/README.md` | base plugin | `Grep: path does not exist` (docs) |
| 12 | Error records carry `rev` and `ver`; a class whose errors since its fix all come from older code is `stale code`, not `regression`; `resolve --version`, `resolve --family` | `error_ledger.py` | finding 1 |
| 13 | The shell classes are split by cause in the report's families; signatures fold claim ids, instances and hosts | `error_ledger.py` | findings 3 and 5 |

The rules of the protocol are unchanged: who may make which transition, which fields a
party owns, what a status change needs as grounds. Only the form a legal request may
take is wider (`docs/protocol.md`, "What `tickets_update` and `tickets_create` take as
meant").

## Left for the human

- **Resolve what this round fixed**, after the merge, so that a recurrence is measured:
  `error_ledger.py resolve --family "<family>" --commit <merge sha> --note "2026-11-13 review"`
  for `tickets_update: not a transition`, `tickets_update: delivered needs result`,
  `tickets_update: deliver by a non-receiver`, `tickets_update: agent cannot act for the
  instance`, `Grep: path does not exist`, `Read: file too large to read`, and by
  signature for the single classes of rows 2-4, 6 and 7. This session resolved nothing:
  a resolve is the human's word.
- **No settle was ever recorded** in the ledgers of this checkout, so every class since
  2026-10-01 is still open and "weeks open" keeps growing. Either the weekly task's
  settle did not run, or its board branch was not merged.
- **`in-progress -> accepted` (2) and `in-progress -> rejected` (1)** are not
  transitions; the callers meant "put it back" and "it cannot be done". Whether the
  receiver may make them directly (with a reason) is a protocol decision.
- **Hosts the cloud sessions cannot reach** (17 `WebFetch` failures: arxiv.org,
  ar5iv.labs.arxiv.org, api.crossref.org, doi.org, ems.press): the cloud environment's
  network allowlist, not the plugins. The Expert's source allowlist names the hosts.
- **The homes' own text**: `Slope1illuminationResearch/CLAUDE.md` still calls the
  library `../papers` (reads of `papers/reviews/...` failed); sessions looked for
  `library/cache` and `library/papers`.
- **The docs live outside every plugin**, so an installed plugin copy has none of the
  91 `docs/x.md` it cites. Moving `docs/` into the base plugin would fix that for good;
  it touches the homes' and the workspace's references, so it was not done here.
- **Large section files** (`sections/markings.tex`, 40k tokens): 9 whole-file reads
  refused. The Author's agents could be given the statement by label (`claims_show`)
  or a line range from the checker instead of the file.

## Follow-up the same day: harness and tooling

- **The server says where things are.** The MCP server's `instructions` (read by every
  session before its first call) carry the conventions of rows 1-8 in a dozen lines,
  and `workspace_get` returns `academy.root`, `academy.scripts` per plugin and
  `academy.docs`.
- **`script_path_guard` met its first live session** and wrongly denied two commands:
  one with a second `cd`, one quoting a call inside a here-document. It now follows
  every `cd` before the call, does not read here-document bodies, and says nothing
  once it cannot tell where a command runs.
- **`expert/scripts/sources.py`**: bibliographic records from the arXiv and Crossref
  APIs instead of fetched pages (`lookup`, `search`); the librarian's entry step and
  the scout's arXiv step use the APIs. Two hosts, both on the source allowlist.
- **TeX in the cloud**: the workspace's `scripts/cloud-tex.sh` (apt, about a minute),
  run by `cloud-setup.sh`; a `build` workflow in the paper's repo with the same
  package list.
- **Not done: Sage in the cloud.** The distribution has no `sagemath` package and
  fetching a conda installer was not permitted in the session; experiments that need
  Sage stay on the lab's worker.
- **The docs moved into the base plugin** (`academy/docs/`, a stacked change after this
  review): an installed plugin copy has them, `workspace_get` returns the folder, and the
  repo root's `docs/README.md` is the pointer. Row 11's pointer file is gone with it.

## The whole round, in merge order (plugins 0.2.3 at the end)

The work of 2026-11-13 is one linear chain of pull requests in this repo. Each branch
has the one before it merged in, and each was pushed through the push gate (every suite
and the lint) on that cumulative tree, so they merge cleanly in this order and every
intermediate state is a tested one.

| # | Pull request | What it adds |
|---|---|---|
| 1 | #23 | the error-ledger review itself (rows 1-13 above), `sources.py`, the presync diff, board relations, lint, the library split |
| 2 | #24 | `author/scripts/statement.py`: one statement by its label |
| 3 | #25 | `docs/` moves into the base plugin |
| 4 | #26 | `ship.py`: stacks, the push gate that runs the repo's workflows (`ci_local.py`), the `ship_guard` hook |
| 5 | #27 | the `workspace` target; `.claude/worktrees/` ignored |
| 6 | #35 | `ci_local`: Git Bash on Windows, never the WSL launcher |
| 7 | #32 | the ledger does not count a shell command that exits 1 with ordinary output |
| 8 | #36 | hermetic test suites; the two real-home tests are opt-in (`ACADEMY_TEST_REAL=1`) |
| 9 | #28 | SessionStart says when the running academy code is behind |
| 10 | #31 | the desk's `OVERDUE` block for a weekly review gone quiet |
| 11 | #29 | one PreToolUse process for the base plugin's guards |
| 12 | #33 | the same for the Author's four edit guards |
| 13 | #30 | workflow prompts carry the full path of every script they name |
| 14 | #34 | workflows ship their own work when run outside the inbox (0.2.2) |
| 15 | #37 | the checkpoint ships what a ticket wrote in another home (0.2.3) |
| 16 | #38 | this map |
| 17 | #39 | `paper_diff` defaults that build on a real paper (formula markup off, diagrams whole) |
| 18 | #40 | a commented-out or verbatim statement is not a statement (`pinned.live_text`) |
| 19 | #41 | the checker's registry view keeps every parsed statement |
| 20 | #42 | deep-dive: the explainer supplies the status of the citations it shows |

Rows 17 to 20 were found by running the round's tools on the real paper and board, after
the suites passed: the presync diff never built there, the statement tool listed ten
commented-out statements, the checker's view was five rows short, and a deep-dive of a
claim with cited inputs could not render with a sections-only file. Each has a test now
that fails without its fix.

Outside this repo, from the same round: the workspace (cloud TeX, the max tier, its
`CLAUDE.md`), the lab (tests skip without Sage or numpy, so its push gate passes), a
notebook (the library's path, its workflow step), the paper (a gate finding fixed in
the text).

## The night of 2026-11-13: optimisation, and what measuring found

The human's ask was run time, storage, memory, tokens and context. Everything below was
measured on the live board (1195 tickets, 346 packets) before and after. The chain
continues in the same order:

| # | Pull request | What it adds | Measured |
|---|---|---|---|
| 21 | #43 | this map, brought to the tip | |
| 22 | #44 | the GitHub board's listing is incremental and kept between processes | a listing 20 s -> 1.1 s; `cowork.py list` 3 min 49 s -> 1.6 s |
| 23 | #45 | the push gate runs a workflow's jobs side by side | this repo's gate 4 min 30 s -> 92 s |
| 24 | #46 | MCP listings are paged, filterable and compact | `tickets_list {}` 384 000 characters -> 15 000; `packets_list {}` 166 000 -> 18 000 |
| 25 | #47 | the status screen and the list commands stay one screen; a brief listing for reviews | `academy_status` 47 700 -> 5 700; `board.py list` 149 000 -> 9 900; the review's listing 189 000 -> 19 000 |
| 26 | #48 | an italic note line in a packet's `## Decision` is not a problem | invalid open packets 68 -> 5; packets with a decision to make 5 -> 14 |
| 27 | #49 | `ship.py start --worktree` always lands under the main checkout; the recipe for not waiting on the gate | |
| 28 | #50 | the ship test workspace is built once; the base suite is two jobs | the gate 92 s -> 58 s |
| 29 | #51 | two agent definitions the harness could not read whole (below) | |
| 30 | #52 | the usage ledger records each agent's models; `lighter-than-declared` | |
| 31 | this one | the map again | |

**Found by measuring, not by the suites.**

- **`rigor-reviewer` ran without its definition since 2026-10-31** (#51). An apostrophe
  not doubled in its single-quoted description made its frontmatter unreadable; a
  session lists it as "Agent from expert plugin (Tools: All tools)". Its tool list was
  not applied, and its model, effort, turn limit and preloaded skills sit in the same
  block. `experimenter`'s description was cut at a ` #`. Both are fixed and a test reads
  every agent, skill and command frontmatter for these mistakes. Which model the
  reviews since then ran on cannot be told from the board; #52 makes it visible from
  now on.
- **Nine packets with a decision were never put to the human** (#48): a renumbering note
  under `## Decision` made 64 packets invalid, and an invalid packet is shown but not
  asked. Five packets are still invalid for real reasons; T-1214 (Expert) and T-1215
  (Scientist, whose P-0183 hides a decision since 2026-10-27) ask for the repairs.
- **A listing could silently lose tests** (#50): splitting a suite by file name dropped
  two registry test files until the counts were compared; a test now holds the patterns
  to every file exactly once.
- **Gates can run while work continues** (#49): six gate runs, two at a time in two
  worktrees, all passed. The checkout being gated must not change under the gate, and a
  background push must be read by its own exit status.

**Looked at and left.** Storage is small (the board 6.5 MB, the repositories a few MB
each); nothing to prune beyond finished worktrees. The lab's `test_fsq_sh_behaviour`
(42 s of that suite's 59) drives the real runner with jobs that sleep; it runs in its own
job. The agent definitions cost every session about 36 000 characters (descriptions
16 000, tool lists 20 000, of which 7 400 are the `mcp__academy__` names for a server
registered outside the plugin): see the human's list.

## After merging: the human's list

1. Merge in the order above, then bump the workspace's academy pointer and run
   `scripts/bootstrap.py` on each machine (installed plugins go to 0.2.3). The session's
   first line now says when a checkout or an installed copy is behind.
2. One smoke run on Windows: a shell command and an edit (the two dispatchers), a
   `ship.py push` (the gate needs Git Bash), `/author:presync` (the diff).
3. Resolve the fixed ledger families against the merge commit
   (`error_ledger.py resolve --family "<family>" --commit <sha>`), as listed above.
4. The weekly usage task: it has filed nothing since 2026-09-28 because its session
   starts with no repository and no credentials. The desk shows `OVERDUE` until it does.
5. `board_relations.py plan`, then `apply` (one missing link when last planned).
6. The paper's claim registry has ten errors of its own (`registry.py check` in the
   Author home): three questions and two definitions black in the draft whose records
   say `open` or `sketch`, four records whose label is no longer in the tex, one record
   with an unknown field. They predate this round and are the Author's and the
   claim-keeper's to settle.
7. **First, from the night:** merge #51 early and confirm in a new session's agent list
   that `expert:rigor-reviewer` shows its description and six read tools. Then decide
   about the proof reviews run between 2026-10-31 and that merge: the session
   transcripts on your machine say which model each run used; a pass whose runs were not
   on a primary model is not CONFIRMED x2 at full strength (`grading.primaryModels`).
   Nothing was changed in any registry.
8. Is the MCP server still registered outside the plugin anywhere (tools named
   `mcp__academy__...`)? If not, dropping those names from the 31 agent definitions
   saves about 7 400 characters in every session. Shortening the agent descriptions
   (median 517 characters) would save more, but they carry each agent's guard rails,
   so that is a pass to do together.
9. The board cache is one file per repository under `~/.cache/academy/board`
   (`%LOCALAPPDATA%\academy\board` on Windows); `ACADEMY_BOARD_CACHE=off` disables it.
10. Decisions left open by this round: whether an Expert's commit may land in the paper
   repo through the Author's gate (it does, on an `.../expert` branch), and whether
   other uncommitted work there should block it (it does); `in-progress -> accepted` and
   `in-progress -> rejected` as direct transitions; a hosted collector for telemetry.

