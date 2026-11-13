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

