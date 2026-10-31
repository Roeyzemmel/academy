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
| proof review (`/expert:verify`) | `expert/workflows/verify.js` | done 2026-10-31, with `review_launch_guard.py` |
| experiment review / settle (`/researcher:review-experiment`, `/researcher:settle`) | `researcher/workflows/review-experiment.js` | done 2026-10-31, with the researcher's `review_launch_guard.py` and the clerk agent `review-clerk`. Modes `review`, `settle-audit` (at most three candidates, returned as `to_file` for the main session, the liaison) and `settle-conclude`; the brief is `reviews.py brief`'s text, pinned by a test |
| all inboxes (`/academy:inbox` and the four role inboxes, `only: [instance]`) | `academy/workflows/inbox.js` | done 2026-10-31, with the clerk `academy:inbox-clerk`. It holds the instance order, the cap over the run, one ticket at a time with its `--check` (which runs `ship.py checkpoint`), the stop on a lost agent and every route of `routes.py`. Relays: the forward leg is the relay's decision and child, then the script's chain check and conclusion; the return leg is made without the relay. verify and review-experiment run nested. A skill route, a question to the human, a ticket only `main` may file, and `/scientist:experiment` (header approval) end the run with `for_main` |
| prove (`/researcher:prove`, and nested from the inbox for a `prove` ticket) | `researcher/workflows/prove.js` | done 2026-10-31: no attempt without a falsifier (`needs_explore`), an attack-only run first, the outcome read from the attempt file by the clerk, a verify ticket filed by the prover (a liaison) only for a complete attempt and checked by the script, nothing above `sketch` |
| campaign and cowork (`/researcher:campaign`, `/academy:cowork` step 3) | `academy/workflows/workplan.js` | done 2026-10-31, one script with shared components (caps, state, next actor, stop rules, report) over `academy/lib/workplan.py`. Campaign: the seeding, then rounds of blind provers, `--agents` per round, the artifact check, the lead's update, cross-pollination after two rounds per survivor, reseeding after a failed wave. Cowork: one pass per call (the next actors of its released tickets within `--agents`); the human is asked between passes. The inbox runs nested (`nested: true`: its own nested routes come back as `for_main`) |
| literature watch (`/expert:litwatch`) | `expert/workflows/litwatch.js` | done 2026-10-31: return-only scouts in parallel (`parallel()`), hits deduplicated in code, one writer, a file written elsewhere is an anomaly. The first fan-out of read-only work |
| weekly usage and error settle (`/academy:usage --weekly`) | `academy/workflows/weekly.js` | done 2026-10-31: usage-analyst stages data / write / settle; the script drops a grader's downgrade and a downgrade that is not a lower tier, keeps at most three decisions (regressions first), and settles only after `packets.py show` finds the filed packet |

## Around the workflows

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
