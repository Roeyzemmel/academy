# Workflow triage, 2026-10-09

The process proposals from the 2026-10-08 flat-structures campaign that the Phase 4 tool
fixes did not settle. Each row gives the source, a proposal and an owner. Nothing here is
decided. Roey accepts, edits or drops each row, and an accepted row becomes a ticket to
its owner.

**Sources** (`repo branch:file`):

- **WS**: `BilliardIllumination origin/2026-10-08/flat-orbifold-order/author:Drafts/workflow-suggestions-2026-10-08.md`, item n.
- **PP**: `BilliardIllumination origin/ccr-aed4946c-yxu3gy:Drafts/academy-plugin-proposals-2026-10-08.md`, item n.
- **CL**: `BilliardIlluminationWorkspace main:board/campaign-2026-10-08-flat-structures.md`. It was on board `ccr-aed4946c-yxu3gy` before the fold.
- **EL**: the error ledgers `board/.errors/*.jsonl`, as merged from the board branches.

**Already fixed in Phase 4** (academy `wip/fixes`), so they have no row below:

| Item | Fix |
|---|---|
| WS 3, PP 6 | `land_verdict` idempotent, no silent `not-in-brief/` (fix 7) |
| WS 4, PP 2 | per-call instance (fix 1); `claims_new` on a ticket (fix 2) |
| PP 1 | proved-modulo (fix 3) |
| PP 4 | `new-pass` refuses a concurrent pass (fix 8) |
| PP 7 | `proof-review` alias (fix 4) |
| PP 18 | `domain_get` in the cloud (fix 5) |

**Owned by plan Phase 3**, so they have no row below:

- the pinned-statement guard (WS 2);
- hypothesis findings routed to the Researcher (WS 1);
- `/academy:cowork`, which replaces `/author:campaign` (PP 12);
- the campaign seeding step: records for new labels (WS 5) and the cost estimate shown to Roey.

## Triage

| # | Item | Source | Proposal | Owner |
|---|---|---|---|---|
| 1 | **Input-disagreement rule** (T-0148, second question). Two CONFIRMED runs split only because one lists a definition, or an unverified card, as a `modulo` input. This happened on prop:equivalence-foliation and lem:lift-affine-in-charts. | PP 3; CL "Decision recorded", "Update"; T-0148 | (a) The rigor-reviewer brief says that a definition is never a `modulo` input unless it asserts something, and that a `bib:` card is listed only when its quote could not be checked. (b) `decision_table.py` treats a difference made only of definitions as agreement and flags it in `decision.md`. Roey answers T-0148 first, then the Expert applies (a) and (b). | expert (Roey decides) |
| 2 | **`\cref`-derived `depends_on` edges.** Reviewers keep flagging missing or stale edges, for example lem:lift-affine-in-charts with none. | PP 11; WS 5; CL "Follow-ups" | `check_paper.py` (or `registry.py check --tex`) derives suggested edges from the `\cref`s in each statement and proof. It warns on a registry edge the text never cites, and on a cited label with no edge. The claim-keeper applies the edges; nothing is auto-written. Seeding records for new labels is already part of cowork (3f). | author (checker); researcher (claim-keeper applies) |
| 3 | **Register of named `bib:` inputs.** `bib:...` modulo inputs have no status, so "established" cannot be computed. Every statement in the chain is CONFIRMED only modulo Thurston Ch. 13. | WS 8; WS 7 | A small register in the library, `inputs/<key>.md` or rows in `index.md`, gives each named input a status: `verified-citation`, `folklore`, `unreachable`. `decision_table.py --established` reads it, and the librarian owns it. | expert |
| 4 | **Standing reviewer brief.** Rules such as statement style, proof level and dependency order arrived mid-session and had to be retyped into every brief. | WS 9; WS "Smaller points" | Add `expert/references/reviewer-brief.md` (generic) plus an optional per-home `.claude/rules/reviewer-brief.md`. Every rigor-reviewer brief points to them by path, so a new rule applies to the next run. The brief also gives the file's sha256 or the pinned text, since a reviewer without git cannot confirm the commit. | expert |
| 5 | **Non-blocking-findings ledger.** Wording findings are scattered over decision records and held back, because editing a statement voids its hash. | WS 10; CL "Follow-ups not applied" | Each `decision.md` appends its non-blocking findings to one ledger per statement (`reviews/<ns>/<slug>/findings.md`). A "wording batch" step (cowork close-out) edits only those statements and re-reviews only the ones it changed. | expert (ledger); author (batch) |
| 6 | **Cost estimates and parallelism.** About 130k tokens per run and two runs per statement, run sequentially, and the cost was invisible until late. | WS 11; PP 10 | Show the cowork pre-dispatch estimate (3f) to Roey. Add `/expert:verify --batch <ids>`: A then B per statement, never two runs at once on one statement (fix 8 enforces this), statements in parallel up to `--agents`. | expert (batch); academy (estimate, in cowork) |
| 7 | **Commit gate on `claude/*` branches.** Commits on the assigned `claude/...` branch were blocked by W1, so work moved to a date branch and was mirrored. | WS 12 | Set the commit gate to `warn` on `claude/*` as on `<date>/<topic>/<role>` (Author `academy.json` `commitGate` branch rules). Document in the workspace CLAUDE.md that a cloud session works on its assigned branch and mirrors by push. | author (gate config); human (workspace CLAUDE.md) |
| 8 | **Margin-note caps and an R7 baseline keyed by label.** One `\Claude` note clips (R7). R7 is pagination-flaky, and its per-file baseline breaks whenever pages shift. | WS 14; PP 16 | Cap a machine note at three lines in the math-writer and math-editor briefs. Run `/author:sweep` after every landing batch (a cowork after-landing step). Key the R7 baseline by label, and skip R7 with a warning, rather than blocking, when the PDF is older than the sources. | author |
| 9 | **Fable and turn-limit fallback.** The Fable limit killed two runs with no partial result; the turn limit cut three agents before they reported. | WS 15; PP 9 | On a rate-limit failure, `expert:verify` (and the other role skills) relaunch the run on `opus` (Opus 5.5 is an equal primary) and record the fallback in `decision.md` or the thread. Agent briefs ask for the report first and edits second. The error ledger now records the failing command or path (fix 9), so the analyst can measure how often this happens. | expert (verify); academy (agent-brief rule) |
| 10 | **Roadmap leaks to blind reviewers; `review_blind_guard` over-blocking.** Verdict-bearing notes in the paper home's legacy roadmap file reached a reviewer, while the guard blocked legitimate globs. | PP 8; CL "Session artefacts" | Interim verdict notes live only in the board (cowork plan file), never in the paper home. The guard also denies roadmap/agenda lines that name a subject's verdicts. It narrows its glob rule to patterns that can reach `reviews/`, with a regression test for each pattern it wrongly blocked. | expert (guard); author (roadmap discipline) |
| 11 | **Auto-closing agenda items; recolouring.** Stale agenda items (one was already done; three more still read `open` though their runs exist) are not closed when the claim lands. Removing the `sketch` wrapper after `proved` is done by hand. `/author:campaign` is replaced by `/academy:cowork` (3f). | PP 13; PP 14; CL "Follow-ups" | `/author:agenda` closes an item when its ticket closes. Add `check_paper.py --recolour <label>`, which removes the status wrapper pair of statement and proof once the registry says `proved` and keeps `added`. | author |
| 12 | **Cloud TeX toolchain.** The cloud image lacks cm-super and lmodern, and needs `openout_any=a`. | PP 17 | Install them in the workspace `cloud-setup.sh`, then check with `latexmk` on a cloud session. This is workspace setup, not plugin code. | human (workspace setup) |
| 13 | **Network-blocked sources workflow.** WebFetch `EGRESS_BLOCKED` (30 errors, e.g. library.msri.org). One source (Thurston Ch. 13) was never readable. | WS 7; EL `WebFetch` | At campaign/cowork start, list the cited-but-unreadable sources and file one Expert ticket. An Expert session with internet tries first; then Roey gets the exact page and the statement it supports. The librarian records the outcome in the register of row 3 (`unreachable` until fetched). | expert (Roey supplies pages) |
| 14 | **The cloud-experiments rule** (not merged). Cloud sessions may write and run experiments in their own environment unless Sage is needed and absent; heavy runs still go to lingo. | `FlatSurfLab origin/ccr-aed4946c-yxu3gy:CLAUDE.md` ("Cloud sessions (Roey, 2026-10-08)"); `BilliardIlluminationWorkspace origin/ccr-aed4946c-yxu3gy:CLAUDE.md` | Roey decides whether to merge both branches' CLAUDE.md text. If merged, `scientist/references` gets a generic "run where the environment allows" policy hook (`scientist.policy.cloud`) instead of lab-specific prose. | human (Roey decides); scientist |
| 15 | **Deleting stale branches.** | BI `claude/focused-euler-o4thg2`, `claude/wizardly-pascal-p1swia`, `claude/inspiring-cerf-7smadp`, `rescue/neighbour-checkout-2026-09-30` (the only `rescue/*` branch on origin today); board `ccr-aed4946c-yxu3gy` (now a workspace branch after the fold) | Once their content is confirmed merged (`git branch -r --merged origin/main`, or a diff review for the unmerged ones), Roey deletes them with `git push origin --delete <branch>`. No agent deletes a branch. | human |

## Not an academy hook (Phase 4 fix 11)

The stop-hook noise has two parts: submodule-pointer drift, and generated views or
hook-landed files left uncommitted (WS 13; PP 19). It comes from Claude Code's cloud
stop hook, `~/.claude/stop-hook-git-check.sh`. That hook blocks the stop on any
uncommitted or untracked file in the session's repository. The academy plugins register
no `Stop` hook. Their `SessionStart` hook (`academy/scripts/session_start.py`) only
commits pending board changes, and reports nothing about submodules or views. That user
hook was left untouched, as the plan says.

What the academy can do instead:

- `ship.py checkpoint` after each landed verdict, scoped to the library (PP 19). It is
  already run from the inbox `--check` step.
- Generated views stay gitignored, or are regenerated and committed by the same
  checkpoint.
