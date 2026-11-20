# Workflows: the academy's sequencing rules in code

The harness's **Workflow** tool runs a JavaScript script that launches subagents
deterministically (`agent()`, `pipeline()`, `parallel()`, structured results by schema).
Since 2026-10-31 (the human's decision) the academy moves its sequencing rules out of skill and agent
prose and into such scripts. A rule that a model had to remember ("B only if A is
CONFIRMED") becomes a branch the model cannot take, and the prose loaded into every
session gets shorter. Prose keeps what still needs judgement (how to write a record,
how to route a finding). Hooks keep doing what they did: landing verdicts and keeping
reviewers blind.

## What the 2026-10-31 pilot established (B0)

- **Where the scripts live.** Named workflows come from `.claude/workflows/` and from
  each plugin's `workflows/` folder, registered as `<plugin>:<meta.name>`. A few turns
  after `expert/workflows/verify.js` was committed, the same session listed it as
  `expert:academy-verify`, but a pilot copy written into `.claude/workflows/` mid-session
  was not found by name. When the registry refreshes is not documented, so the skills
  invoke each workflow by **`scriptPath`**
  (`${CLAUDE_PLUGIN_ROOT}/workflows/<name>.js`), which works in every session and
  checkout. The registered name is an alias.
- **Plugin hooks fire for workflow agents.** An `agent(..., {agentType:
  'expert:rigor-reviewer'})` keeps that agent's `agent_type`, so the expert plugin's
  `SubagentStop` hook (`land_verdict.py`) landed its VERDICT block as `A.md`, with run
  id and model, exactly as for an `Agent` launch.
- **Workflow agents keep their definition.** The agent ran with its declared tools only
  (Read, Grep, Glob and its MCP read tools; no shell, Write or Edit) and under its own
  instructions. The pilot did not exercise the PreToolUse blind guard, because the
  reviewer itself refused to read `reviews/`. The guard is the same plugin hook
  mechanism.
- **The MCP server sees a workflow agent as itself.** A workflow agent of type
  `expert:clerk` called `workspace_get`, and the server reported the caller
  `expert:clerk`, verified, acting for the workspace's Expert instance. So `mcp_write_gate`'s caller record,
  `permissions.json` and the ticket chain apply to workflow agents unchanged. A relay
  launched by a workflow files its child as itself, a liaison.
- **Plugin agents and workflows refresh during a session, with a delay.** An agent file
  added mid-session was not a valid `agentType` a few minutes later; the workflow then
  failed at once, before any agent ran. Later in the same session both new clerks, and the
  plugins' workflows (as skills `<plugin>:academy-<name>`), were listed. So a fresh agent
  may need a later turn, or a new session.
- **A workflow agent is not launched through the `Agent` tool.** So a PreToolUse hook
  on `Agent|Task` sees only hand launches. That is what `review_launch_guard.py` uses.
- No filesystem in the script: every file operation is an agent stage, and the script
  checks the structured results it gets back (pass names, hashes, run files).

## The pattern

1. A clerical **prepare** stage (the role's chair or relay agent, `effort: 'low'`)
   returns the ids the run needs. The script validates them (the same regexes as the
   hooks).
2. The graders are launched by the script with `agentType` (their own model, tools and
   hooks) from a **brief built in code**, so run B's brief is A's byte for byte.
3. A **table** stage runs the decision-table script and returns its JSON. The script
   branches on it: it never branches on a model's reading.
4. A **conclude** stage writes the record, the evidence, the proposal, the tickets and the
   packet. It cannot launch agents (no `Agent` tool), and the script checks afterwards
   that no run it did not launch appeared.
5. A **PreToolUse guard** refuses the hand launch of the graders, with an opt-out the
   human sets (`ACADEMY_ALLOW_MANUAL_REVIEW=1`).
6. Tests run the script under node with a fake `agent()` (`expert/tests/test_verify_workflow.py`).

## The workflows

| workflow | script | state |
|---|---|---|
| proof review (`/expert:verify`) | `expert/workflows/verify.js` | done 2026-10-31, with `review_launch_guard.py`. A CONFIRMED A with `launch_b` launches B at once; a falsifier is triggered by a GAP verdict (A, or B after a CONFIRMED A), never a gate between A and B: with no clean falsifier on record for the statement hash and none pending, the chair files the request (to the Researcher `decision_table.researcher_for` names, naming the blocking step and the hash) alongside the follow-up repair, blocking nothing (2026-11-20). An A CONFIRMED with `add_dependency` (an existing result: `ns:id` or `bib:key#pinpoint`) pauses the pass: a `prove` repair to the producer, marked `amendment for verify T-NNNN pass P`, the verify ticket blocked on it; on the rerun B runs in amend mode (told the suggestion only, `reviews.py amend-brief`) only once that repair ended delivered or closed, the attempt differs from the one A reviewed, and each dependency is declared with its pinpoint; A + B are the two verdicts (`decision_table.py` mode amend). Two CONFIRMED runs on differing inputs (#121, the table's `settle-dependencies`; the retired `confirmed-union` wiring of 93e5325 is gone): a stage writes `S-table.json`, one `expert:dependency-settler` run (through `launchMax`) classifies each differing input in the fixed order, a stage writes its report and record (`S.md`, `S.json`) and runs `settle_deps.py check` then `apply` (one retry of the settler with the problems; invalid twice is a `disagreement` with an anomaly). `confirmed-settled` files the declaration repair (the amendment's marker, so prove.js files no verify ticket; it carries the routine and remark notes), a `cite` ticket per missing source and, for a paper remark, a `write` ticket to the Author, none blocking anything, and the concluder proposes apply's status with apply's grounds; a stop is a `disagreement` with the settler's classification for the human. The new stages' schemas require no field (code defaults) |
| experiment review / settle (`/researcher:review-experiment`, `/researcher:settle`) | `researcher/workflows/review-experiment.js` | done 2026-10-31, with the researcher's `review_launch_guard.py` and the clerk agent `review-clerk`. Modes `review`, `settle-audit` (at most three re-derivation tickets, filed by lead-researcher and read back), `settle-review` (a verify ticket only for a candidate whose re-derivation came back) and `settle-conclude`; the brief is `reviews.py brief`'s text, pinned by a test |
| all inboxes (`/academy:inbox` and the four role inboxes, `only: [instance]`) | `academy/workflows/inbox.js` | done 2026-10-31, with the clerk `academy:inbox-clerk`. A listing with no instance, or with an instance whose `waiting` is above 0 and no rows (without `ids`), is a failed stage: listed once more; no instance twice ends the run with `list_failed` and says so, never "nothing to do" (#94, 2026-11-20). The test-engineer's verdict on a `code` ticket is the structured field `verdict` (`approved` or `findings`), never read from its prose (#94). It holds the instance order, the cap over the run, one ticket at a time with its `--check` (which runs `ship.py checkpoint`), the stop on a lost agent and every route of `routes.py`. Relays: the forward leg is the relay's decision and child, then the script's chain check and conclusion; the return leg is made without the relay. verify, review-experiment (and settle's first leg), prove, cite, explore, generalize, referee, domain, notes and the experiment's design leg run nested. With `loop: true` the inbox passes over every instance until nothing moves; a ticket that needs the human is set aside as a gate and the others go on, and the gates come back together as `for_main`. What comes back is only a human gate: an experiment header to approve, a script to commit, a rendered report to see, a ticket with no route, a campaign's decisions; and one hand-off (T-1271, 2026-11-16): a Researcher ticket whose lead-researcher needs a proof attempt (an agent inside the run has no Agent or Workflow tool) comes back as `/researcher:prove` with its `args` (`handback: lead-researcher`), the claim checked by `registry.py statement` (a ticket with no registry claim: the lead registers it with `claims_new` first), the falsifier the lead reports noted on the ticket's thread for prove.js, the ticket left `in-progress`, never blocked on the human. No falsifier is needed before the hand-back (2026-11-20, the human's design): with none on record the hand-back is the same, its `why` says so and `pending` names falsifier tickets still open; a failed attempt or a GAP verdict triggers it |
| prove (`/researcher:prove`, and nested from the inbox for a `prove` ticket) | `researcher/workflows/prove.js` | done 2026-10-31: an attack-only run first, the outcome read from the attempt file by the clerk, a verify ticket filed by the prover (a liaison) only for a complete attempt and checked by the script, nothing above `sketch`. Since 2026-11-20 (the human's design): the attempt never waits for a falsifier; a falsifier is triggered by a failed attempt or a GAP verdict. The state stage says whether one is on record (on the claim, a declared input or the parent lead, or waived by the human on the ticket, #117) and whether one is pending; an attempt that is not complete (failed, or with gaps or undeclared dependencies after the fix round, an incomplete amendment included) on a claim with neither gets one: `lead-researcher` (a researcher->scientist liaison; the prover is none) files an `experiment` or `test` ticket to the Scientist targeting the failed step, checked by the clerk; the delivery is unchanged and names it (`falsifier_ticket`). A lost run files nothing. The result (`falsifier_on_record`, `falsifier_source`) and the verify ask say whether one is on record. A clerk stage lists the related registry statements (paper and notebooks) and a second one confirms each id with `claims_show` (an unconfirmed one is dropped and noted; duplicates and the claim itself are dropped by the id with its namespace); at most twelve, proved and proved-modulo first (`related`), go into the prover's brief: cite each that does the work, never reprove a proved one, say for each "used as input" or why not. The attempt declares its `dependencies:` in its frontmatter (ids and `bib:<key>#<pinpoint>`, the same items as its inputs); a complete attempt without the list, with an input it uses left out of it, or with an empty list next to inputs it uses, gets one fix round (the prover fixes the frontmatter of the same file, the clerk reads it again) and, still undeclared, is incomplete and filed for no review; the verify ticket names the dependencies in its refs and ask (`dependencies` in the result). A repair (`mode: repair`, or a ticket the state stage reads as one) is attempted whatever the status; a `proved` claim with no repair asked is never delivered (#85): it returns `already_proved`, which the inbox hands back with `args` (`mode: repair`, `handback: prove`). A repair a verify pass asked for (the marker `amendment for verify T-NNNN pass P`, or `args.for_verify`) files no verify ticket and delivers with the attempt's path (`amendment-delivered`); an incomplete one is blocked on the human (`amendment-incomplete`). Any other repair records, before its attempt, what its status rests on (a `repair before` clerk stage: the last confirmed pass, the proof it reviewed and that proof's hash); after an incomplete attempt a `repair after` stage hashes the statement and that proof again, and a changed record with a review standing on the old text (proved, proved-modulo or a confirmed pass) gets a verify ticket from `lead-researcher`, checked by the clerk: reword mode (`Verify <claim> (reword of <pass>)`, which the inbox passes to `verify.js` as `mode: reword`, `base_pass`) when only the statement moved over a confirmed pass, else blind with the reason (no confirmed pass, or a proof not comparable); a changed proof files nothing and says, in the result and a thread note, that the status no longer stands on the reviewed text and a verify follows the next complete attempt (`record_stale`); unchanged, the result names why none is needed (`record_verify_why`); a complete repair's own verify ticket covers the new text (#85) |
| campaign and cowork (`/researcher:campaign`, `/academy:cowork` step 3) | `academy/workflows/workplan.js` | done 2026-10-31, one script with shared components (caps, state, next actor, stop rules, report) over `academy/lib/workplan.py`. Campaign: the seeding, then rounds of blind provers, `--agents` per round, the artifact check, the lead's update, cross-pollination after two rounds per survivor, reseeding after a failed wave. Cowork: one pass per call (the next actors of its released tickets within `--agents`); the human is asked between passes. The inbox runs nested (`nested: true`: its own nested routes come back as `for_main`); a campaign's rounds end at a lead-researcher hand-back (`for_main.handback`, T-1271), which the session runs before calling again; any other `for_main` (the cost gate, a route that cannot nest) is reported and the rounds go on |
| citation (`/expert:cite`, and nested for a `cite` ticket) | `expert/workflows/cite.js` | done 2026-10-31: one librarian run briefed by the script (one retry when it returns no result or throws, then `lost` with a thread note, never an error that ends a nesting inbox: #94, 2026-11-20; after a retry `cards.py dups` counts the bib entries and cards, and a duplicate is `lost` too); the card checked by `cards.py validate` with one fix; the packet and the delivery only after the check; a mismatch reported first as a mathematical finding, an unreachable source as an unverified input |
| explore (`/researcher:explore`, and nested for a `question` ticket) | `researcher/workflows/explore.js` | done 2026-10-31; order 2026-11-20 (the human's ruling, #87): the items from `notebook.py next` (at most three), one lead-researcher briefed with ids only, one step per item in prove's order: prior art, then prove (the claim checked by `registry.py statement` and handed back as `for_main` `/researcher:prove` with `args`, `handback: lead-researcher`, `runs` for several; the ticket stays in-progress and prove.js delivers it; nested from the inbox, the hand-back is passed on to the main session), and a falsifier only after a failed or incomplete attempt or a GAP verdict (the trigger read by a clerk; one before an attempt is an anomaly); the script checks the falsifier's ticket and today's journal, and delivers a ticket only on an artefact the clerk found (a ticket, an object, a notebook file), named in its result; with none it stays in-progress with a thread note (`no-artefact`) |
| generalize (`/researcher:generalize`, and nested for a `generalize` ticket) | `researcher/workflows/generalize.js` | done 2026-10-31: `generalize.py source` refuses an uncleared review; one prover writes only the proposals file; `validate` with one retry, then the failing proposal is dropped; `create --apply` and the packet by the clerk; lead-researcher (the researcher -> scientist liaison) files the falsifier tests `generalize.py tickets` prints, the script checks a test names each conjecture and delivers |
| referee (`/expert:referee`, and nested for a `referee` ticket) | `expert/workflows/referee.js` | done 2026-10-31: the PDF checked fresh by the clerk (rebuilt when stale, never under `author.build.lock`); the cold brief built in code from facts only; a hand launch refused by `review_launch_guard`; the packet landed by `land_referee`, found and linked by the script |
| domain pack (`/expert:domain`, and nested for a `notation` ticket) | `expert/workflows/domain.js` | done 2026-10-31: one change per ticket (a second is split off, noted in the thread); one librarian run; the `git diff` of the pack checked against the change's files and the new `CHANGELOG.md` line, a mismatch parking the ticket on the human; a `notation` packet when other instances rely on the change |
| notes (`/author:notes`, and nested for a returned referee ticket) | `author/workflows/notes.js` | done 2026-10-31: the inventory from git; one classifier that files nothing; every proposed ticket through `routes.check_filed` (`routes.py --check-filed`) and the kind rules, one retry; exactly the checked tickets filed and read back; the four lists computed in code |
| experiment (`/scientist:experiment`; its design leg nested for an experiment ticket) | `scientist/workflows/experiment.js` | done 2026-10-31: modes design, build, queue, report, file, with the human gates unskippable: no body before the header is approved, nothing queued before the human commits, nothing filed before the human saw the rendered packet; `lab.py check --strict` and `report.py check` each with one fix round |
| literature watch (`/expert:litwatch`) | `expert/workflows/litwatch.js` | done 2026-10-31: return-only scouts in parallel (`parallel()`), hits deduplicated in code, one writer, a file written elsewhere is an anomaly. The first fan-out of read-only work |
| weekly usage and error settle (`/academy:usage --weekly`) | `academy/workflows/weekly.js` | done 2026-10-31: usage-analyst stages data / write / settle; the script drops a grader's downgrade and a downgrade that is not a lower tier, keeps at most three decisions (regressions first), and settles only after `packets.py show` finds the filed packet |
| maintenance round on the plugins (`/academy:maintain --workflow`; without it the session does the round itself) | `academy/workflows/maintain.js` | done 2026-11-14: `maintain.py survey` gives the candidates (ledger families, commands over budget, unreadable definitions); the script applies the plan's rules (a usable topic, a file, a measure, the cap), puts tasks that share a file in one stacked lane and runs the lanes side by side, each task developed in its own worktree, reviewed by another agent, one fix round, pushed through the gate; `maintain.py union` gates the lanes together. Returns the pull requests for the session to open |

## What the first live loop taught (2026-10-31)

- `inbox.py --json` cuts the list at `itemsPerRun`, and `--all` (304 rows) is too long for the list clerk to transcribe (it returned one instance of five). So a run with `ids` lists with `--ids` (the ids, the tickets handled and their children, filtered in the script, no cut) and skips pending blocked rows.
- A row carries `to`, `parent` and `final_to` (`academy_common._row`): `follow` needs the parent, and a row the list clerk put under an instance it is not addressed to is dropped with an anomaly, never run with the wrong role. A relay's child id is followed directly, so the child moves even if the parent field is lost.
- A ticket the route parks on its child (a relay's forward, a research ask) ends blocked by design: its `--check` exit 3 does not close the instance.
- A `cite` whose source cannot be read is parked on the human with the exact ask (project rule "inaccessible sources") and comes back as a gate, not delivered; there is no card to validate.
- `ship.py checkpoint` refuses a repo on a branch that is neither `main` nor `<date>/<topic>/<role>` (a cloud session's own branch): it reports, and the session commits by hand.

## Models

A workflow launches every agent on the workspace's model for its tier (T-0350; the tiers
and the map are docs/config.md, "`models`: agent tiers"). An agent file's `model:` line is
its tier's default alias, so under the academy default map nothing needs passing; where the
workspace maps a tier elsewhere, the launch must carry the Agent tool's `model`. A workflow
script cannot read workspace.json, so the map comes in its arguments:

- **`args.models`.** The skill that calls the Workflow tool passes, as the first key of its
  `args`, the JSON object `py <academy repo>/academy/scripts/models.py launches` prints:
  `{"<plugin:name>": <launch>}` for every agent whose tier the workspace maps away from its
  file's `model:`, and `{"tier:<tier>": <launch>}` for every such tier (`{}` with the
  default map).
- **Given or not given (#83).** A map that is given stands, `{}` included: `{}` is what
  `models.py launches` prints when the workspace maps nothing away, so it means
  *no override* (every agent on its file's model), never *not given*. The map may also be
  passed as its JSON text. Not given (`args.models` absent or `null`), the run's first
  `launch()` resolves it first: one `general-purpose` stage at tier `base` runs
  `models.py launches` (from `args.root`, else the academy repo `workspace_get` names), once
  per run, and its JSON object is the map (`MODELS.source` is then `resolved`, else
  `args`). Anything else given (an array, a number, text that is no JSON object), or a
  stage that returns no JSON object, **throws** before any agent is launched, naming the
  command to rerun with. (Until 2026-11-20 a missing map was read as `{}` and passed down
  as given: an inbox started without it launched the max-tier graders on their file's
  `opus`.)
  A lookup that returns nothing (a usage limit at the start) stops the run as three null launches do, never a throw; its output must be the JSON object alone (a code fence allowed), never a map read out of prose. The lookup runs `py <academy>/academy/scripts/models.py launches` (python3 where there is no py), which no permission template allowlists today: a scheduled or unattended run passes `args.models` itself, or the human allowlists that command.
- **`launch()`.** Every workflow carries the same block, between `// ---- Models` and
  `// ---- end Models` (pinned identical by `academy/tests/test_workflow_models.py`), and
  launches every agent through its `launch(prompt, opts)`, never `agent()` directly. An
  agent the map names gets `model: <launch>`; any other agent's options are passed
  unchanged.
- **Scripts name no model.** An academy agent's model is its tier's, so a script never
  passes `model:`. An agent with no academy file (`general-purpose`, the notes filer) is
  given a tier instead: `launch(p, {agentType: 'general-purpose', tier: 'medium'})` runs it
  on the map's `tier:medium`, else on the default alias of that tier (the block's
  `TIER_DEFAULTS`, pinned to `DEFAULT_MODEL_TIERS`); an unknown tier throws before anything
  is launched. Both rules are tests.
- **Nested workflows** get the same map: every `workflow(...)` call passes
  `models: await modelsMap()` (the inbox to its routes, the workplan to the inbox), the
  map given or resolved once for the run, so a nested run never resolves it again and
  never receives a stand-in `{}`.

The launch value is an alias (`claude-opus-5-5` launches as `opus`): the per-call `model`
takes no full id. The id still decides the grading floor, read by the graders' own report
of the model they ran on (roster-rules.md, "Model fallback").

**A usage limit (#115).** `launch()` counts launches that return nothing: after three in a
row (under a usage limit every launch fails until it resets; two can be one lost run and
its fallback, and the stage that records them still runs) it launches nothing more and
returns `null` at once, so each caller's "returned nothing" path ends the run quickly;
`LAUNCH_LIMIT.stopped` says so, and the inbox reports `usage_limit: true` with
`stopped` naming it. A script cannot read the reset time (the agent's error is not
passed to it): the session's own error names it, and a scheduled run resumes after it.

## Shipping is a step of the workflow, not a habit of the session

A workflow that changes files ends by shipping them, in code: the inbox's `--check` runs
`ship.py checkpoint --only <the ticket's repos>`, and any new workflow that writes to a
home, the library or the board does the same as its last stage (a clerk stage that runs
the scoped `checkpoint`, or `ship ... --paths` for work that belongs to no ticket). The
stage's result is part of the workflow's return (`pushed`, or the refusal: a branch off
the template, a commit gate, a push gate), so a refused push is reported and never
retried in a loop. Outside a workflow the same default is held by the `ship_guard` hook
(`docs/branching.md`): raw `git commit` / `git push` / a new branch in a workspace repo is
denied with the `ship.py` command.

**The ship stage** (2026-11-13). The workflow runtime cannot import across files, so each
workflow that ships carries the same block (`SHIP` and `ship()`; `tests/test_workflow_ship_stage.py`
pins that it is identical). It returns `ship: {status: pushed | nothing | refused | not-run,
detail, branches?, command?}`:

- It runs only standalone. The inbox calls every child with `nested: true`, and a nested
  run has no `ship` field: the inbox's own `--check` ships the ticket.
- With a finished ticket, one clerk stage (the workflow's clerical agent type) runs the
  inbox's exact command, `<role>/scripts/inbox.py [--instance I] --check T-NNNN`, once. Its
  output is read in code like the inbox's check: the ticket's state from its first line,
  each repo from ship.py's lines. `inbox.py` does the scoping (home, `board`, `library` for
  the Expert, and `--touched` for what the role wrote in another role's home), refuses a session outside the workspace or in a worktree, and runs nothing
  under `"shipCheckpoint": false`, which comes back `not-run`.
- A ticket the run left unfinished (parked on the human, tests still to file) is `not-run`
  without a stage, with the `--check` command: the inbox would not ship it either.
- A refusal (off-template branch, commit gate, push gate, timeout) is returned with the
  command, and one sentence goes into the workflow's `notes`. Nothing retries it.
- Without a ticket nothing is run (a direct `ship.py checkpoint` would bypass the scoping,
  the worktree guard and `"shipCheckpoint": false`): `not-run` with `py scripts/ship.py
  checkpoint --ticket <slug> --role <role> --only <targets>` for the session to run from the
  workspace root. The slug is one the run already has (`cite-<key>`, `verify-<claim>`,
  `prove-<claim>`, `explore-<direction>`, `review-<subject>`, `referee-<instance>`,
  `report-<stem>`, `litwatch-<instance>`, `campaign-<target>`, the usage packet's id), so the
  branch is `<date>/<slug>/<role>`.

| Workflow | Writes | Standalone `ship` |
|---|---|---|
| `cite` | library (card, index), the Author home's `references.bib`, board | ticket: the check, which ships the bib too (`--touched`); else `not-run`, with a note to add `--touched` for the bib |
| `verify` | library (`reviews/`), registry evidence (in the home owning the claim), board | ticket: the check (the evidence through `--touched`); else `not-run` |
| `referee` | library (`reviews/referee/`), board | ticket: the check; else `not-run` |
| `domain` | the academy repo's pack, board | the check (ships the board; the pack is the human's commit) |
| `prove`, `explore` | the notebook, board | ticket: the check; else `not-run` |
| `review-experiment` | the notebook, the claim-keeper's status and evidence (in the lab's registry), board | ticket: the check (the registry through `--touched`); else `not-run` |
| `generalize` | the notebook, board | the check once the ticket is delivered (`mode: deliver` too) |
| `experiment` | the lab | `file` leg only (the check); the other legs end at a human gate |
| `notes` | tickets (board files on a file board) | `not-run` (no ticket) |
| `litwatch` | library ledger | `not-run` (no ticket) |
| `weekly` | board (packet, error ledger) | `not-run` (no ticket) |
| `maintain` | the academy repo (one branch per task) | its own: `ship.py commit` by the developer, `ship.py push` after the review; no checkpoint (no ticket) |
| `workplan` campaign | the notebook (approaches, artifacts) | `not-run`; its tickets ship by the nested inbox's `--check` |
| `workplan` cowork, `inbox` | only through the inbox | no stage: the `--check` ships each ticket |

### Known gaps

- **Writes in another role's home** are shipped from the touch ledger (`docs/branching.md`,
  "Writes in another role's home"), closed 2026-11-13; until then the Author home's
  `references.bib` (cite) and evidence or statuses in another home's registry (verify,
  review-experiment, claim-keeper) were left uncommitted. What remains open:
  - A cross-home repo with other uncommitted work is refused, not shipped (the ticket's
    entries wait for its next `--check`): the human commits or stashes that work first.
  - The ticket is told by sequence: the role's unclaimed entries go to the next ticket of
    that role whose `--check` runs. A write made with no ticket (a standalone `/expert:cite`)
    is carried by the next Expert ticket's checkpoint unless shipped by hand first with
    `--touched`.
  - A write through a shell (a script an agent runs that writes another role's home) is not
    recorded; the audit found none (the claim-keeper has no shell; the review and settle
    scripts write the acting role's own home or the library).
  - The domain pack (`domain`) is in the academy repo: the human's commit, not shipped.

## Around the workflows

- **Plugin versions and updates** (2026-11-07): Claude Code caches a plugin per version, and the
  bootstrap used to install only missing plugins, so an installed one kept its old skills (a session
  ran 0.1.0 skills, which call no workflow). The bootstrap now runs `claude plugin marketplace update
  academy` and `claude plugin update <name>@academy` for every installed plugin (`--no-plugin-update`
  skips it; restart Claude Code after an update), and the plugins carry one version, pinned with the MCP
  server's by `academy/tests/test_bootstrap_plugins.py`. Raise it with any change to skills, agents,
  hooks or workflows.
- **Scheduled tasks** (cloud, a fresh session each run, push notification): the weekly
  usage packet and settle (Sundays 20:40 Asia/Jerusalem) and the weekly Expert sources run
  (litwatch and at most three `cite`/`lookup` tickets, Sundays 19:47).
- **Source allowlist**: the Expert's web fetches stay on `expert/references/sources.json`
  plus the library's `expert.sources.allow` (`source_guard.py`). The same hosts belong in
  the cloud environment's Allowed domains.
- **Eval suites** (`evals/`, `claude plugin eval . --eval-dir evals`): the decisions the
  scripts leave to a model (a relay's fail-fast or forward, the clerk's escalation, the
  analyst's proposals), each pinned by a case.
- **Review dashboard**: `/academy:review` publishes the dashboard with a shared store, so
  decisions recorded on the page are applied (the human's) or recorded as input (a
  coauthor's) by the next run.
