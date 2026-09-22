# `paper` — a plugin for writing a research mathematics paper

A roster of subagents, slash-command passes and build gates for a LaTeX research
paper kept under git. Everything here is paper-independent; everything specific to
one paper lives in that repo's `CLAUDE.md` and `.claude/rules/`, which every
subagent loads at startup.

Installed as a skills-directory plugin: the directory is linked at
`~/.claude/skills/paper`, so it loads in every project as `paper@skills-dir` with no
marketplace and no install step. Skills are namespaced: `/paper:tier`, `/paper:verify`.
Changes to `SKILL.md` take effect immediately; changes to `agents/`, `hooks/` need
`/reload-plugins` or a restart.

## The project contract

An agent here may assume, without being told:

| Thing | Where |
|---|---|
| the paper | `main.tex`, a preamble plus `\input{sections/<name>}`; write in the section files |
| sections | `sections/*.tex`, **CRLF** |
| bibliography | `references.bib` |
| build | `latexmk -pdf main.tex`, artifacts in `.build/` (gitignored) |
| mechanical gate | `py scripts/check_paper.py [--strict]`, `file:line: LABEL: message` output |
| ledgers under `Drafts/`, line endings **not uniform — check each file and preserve what it has** | `comment_roadmap.md` (task queue), `sources.md` (citations), `related_work.md` (prior-art searches), `experiments.md` (computations), `statements.md` (generated registry), `verdicts.md` (verifier sign-offs), `referee_report.md` |
| draft colours | `sketch` / `conjectural` / `meta` environments, `\Sketch{}` / `\Conjectural{}` / `\Meta{}` spans, uncoloured = established |
| machine margin notes | `\Claude{…}`, inline `\cl{…}` |
| roadmap tags | `[write] [apply] [lead] [verify] [needs Roey] [dropped] [done]` |
| a paper cache, **only if the project's `.claude/rules/` define one** | full texts of cited sources on disk: read it before fetching a paper, add to it after |

Anything else — notation decisions, standard examples, coauthor macros, the accepted
baseline warnings, keyword lists, the compute repo — comes from the project's own
`CLAUDE.md` and `.claude/rules/`. An agent that needs such a fact and cannot find it
says so in its report rather than inventing one.

## Standing rules for every agent here

1. **Verifying agents never edit; editing agents never grade their own work**, and
   **whoever commissions work never grades it.** A blue statement turns black only on a
   `proof-verifier` sign-off, adjudicated by an agent that did not do the reading.
2. **Nothing is proved that the author has not asked for or sketched.** What an agent
   argues beyond a precise citation is blue.
3. **Never invent a bibliography entry or a pinpoint.** New entries come from a record
   fetched in this run and are added by `source-checker` alone; the bib gate enforces it.
4. **Every judgement call or unverified step gets a `\Claude{…}` note** naming what is
   unverified. Never sign a note as a human coauthor.
5. **Never run `git add`, `commit`, `stash`, `checkout`, `reset`.** The author commits.
6. **Never touch the preamble** unless the task says so.
7. **Never ask questions.** Make the routine call and state the assumption.

## Model fallback — stated once, here

Each agent's frontmatter carries `model:`, `effort:` and `fallback:`. When the primary
model is unavailable the **launching session** — the main session, or the agent that
spawns it — launches the agent through the Agent tool's `model` override set to the
fallback, at the same effort, and **names the substitution in its report**. The override
is otherwise never passed: setting it out of habit forces the fallback and silently
costs the run whatever authority its primary model carried. The one other sanctioned
override is `model: fable` when launching `math-writer` for a `[lead]`. The Agent tool
cannot override **effort**, which comes only from frontmatter, so a task that deserves a
lighter effort gets its own agent (`math-editor`) rather than a flag. Two agents degrade
rather than substitute:

- `proof-verifier` on its fallback returns PLAUSIBLE, never CONFIRMED; the statement
  stays blue until re-run on the primary.
- `referee` on its fallback marks its report reduced-strength; clean sections are not
  treated as cleared.

## The roster

| Agent | Model / effort (fallback) | Role |
|---|---|---|
| `top-researcher` | sonnet / high (opus), 40 turns | owns one `[lead]` issue: falsifier, citations, writer; queues the result for verification; writes and grades nothing itself |
| `master-verifier` | sonnet / high (opus), 20 turns | owns one verification: runs A, then B only if A is positive, adjudicates, lands the ledgers; never verifies itself |
| `math-writer` | opus / high (sonnet), 40 turns; `model: fable` override for `[lead]` (still at high) | prose `[write]` and `[lead]` into `sections/*.tex`, blue unless cited |
| `math-editor` | sonnet / medium (opus), 25 turns | `[apply]` and mechanical `[write]`; no new prose or mathematics |
| `proof-verifier` | fable / xhigh (opus → PLAUSIBLE) | adversarial check of one label; read-only |
| `source-checker` | sonnet / medium (opus), 25 turns | quotes cited statements verbatim, keeps `sources.md`, owns `references.bib` |
| `related-work-scout` | sonnet / medium (opus) | prior-art search into `related_work.md`; finds overlap, cannot certify absence |
| `figure-maker` | sonnet / medium (opus; opus primary for data-carrying pictures) | standalone TikZ, compiled and inspected as an image |
| `copy-editor` | opus / medium (sonnet) | prose, `\cref`, colour audit, overfull boxes; no mathematics |
| `latex-fixer` | sonnet / low (opus), 25 turns | build and rendering defects only |
| `note-sweeper` | sonnet / medium (opus) | deletes `\Claude` notes whose question has a recorded answer |
| `notation-auditor` | sonnet / medium (opus) | notation sheet versus the draft; reports clashes, never fixes them in the paper |
| `referee` | fable / high (opus → reduced-strength) | reads the PDF cold, writes `referee_report.md` |

### How the roster nests

The roster is not flat, but it has two separate trees. **Writing:** a tier routes each
issue to the lightest agent that can do it — `math-editor`, `math-writer` or
`source-checker` directly, and a `[lead]` to one `top-researcher`, which commissions the
experiment, citation, writing and figure agents at layer 2. **Verification:**
`/paper:verify` launches `master-verifier`, which launches the `proof-verifier` runs at
layer 2. The two meet only through the roadmap's `## Verification queue`, which writers
fill and `/paper:verify` drains. No chain is deeper than two layers, under the harness
default of three.

Nesting is what the `Agent` tool in a frontmatter `tools:` list buys; the eleven leaf agents
below deliberately lack it. The point of the arrangement is that one agent holds an
issue's whole history instead of the main session re-briefing a fresh agent per step —
so an orchestrating agent **writes the ledgers itself** rather than summarising back, and
its report to the caller is a convenience, not the record.

## Budget — stated once, here

The Tier 3d run exhausted a session quota: 35 subagents, 14 fable verifier runs, three
source hunts of 35–51 turns, and 18 agents killed by the session limit, several of them
relaunches into the exhausted quota. These rules bind every pass and every agent:

1. **A tier run is at most three issues, executed serially**, each checkpointed in the
   roadmap before the next starts. The rest of the tier waits for the next run.
2. **No verification inside a tier.** Writers queue recolourable arguments; the author
   spends fable runs through `/paper:verify`, one label at a time. Run B launches only
   after a positive run A.
3. **The lightest agent that can do the work.** `[apply]` goes to `math-editor`, not
   through `top-researcher`; `top-researcher` is for `[lead]` issues only.
4. **Turn caps** (`maxTurns` in frontmatter) on every agent that can wander. A capped
   agent returns a partial result: record what is unfinished and move on. Neither
   relaunch it nor raise the cap. `proof-verifier` has no cap, because a verdict cut off
   mid-run is worthless.
5. **The session-limit stop.** An agent that returns a usage-limit or session-limit error,
   or an empty result, is not relaunched, and nothing further is launched. Record what
   was and was not done, and report.
6. **Short briefs.** Point at the roadmap item and the labels; the agent reads the files.
   Pasting tex and ledger history into a brief is paid again on every turn of the agent.

`scripts/session_usage.py <session-id>` prints the per-agent turns and token volume of a
session, with its session-limit failures, for comparing a run against that baseline.

## The passes

| Command | What it does |
|---|---|
| `/paper:tier` | runs the next batch — at most three issues, serially — of the current roadmap tier; resumable |
| `/paper:verify [label]` | one `master-verifier` on one label (default: head of the verification queue): run A, run B only if A is positive, adjudicated and landed; recolours only on agreement |
| `/paper:cite <DOI\|arXiv\|key>` | the only sanctioned route for a new bibliography entry |
| `/paper:sweep` | clears answered `\Claude` notes, once per tier |
| `/paper:audit-notation` | reconciles the notation sheet with the draft |
| `/paper:referee` | cold whole-paper report |
| `/paper:litwatch` | dated arXiv watch for new overlapping work |
| `/paper:presync` | the bundle before a coauthor round or a submission |

## The gates (`hooks/hooks.json`)

Inert in any repo without `scripts/check_paper.py`.

| When | What |
|---|---|
| after an edit to a `.tex` file | runs the checker, feeds its findings back as context, marks the build dirty |
| before an edit to `references.bib` | denied unless the editor is `source-checker` |
| before `git commit` | runs the checker at the configured level; blocks on failure |
| when a writing agent stops with a dirty build | builds, and blocks the stop if the build is not clean |

Gate strictness is read from `.claude/paper-gate.json` in the project, if present:
`{"commit": "strict" | "normal" | "off", "build": true | false}`. The default is
`normal` plus the build gate.
