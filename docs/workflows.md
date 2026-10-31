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
| all inboxes (`/academy:inbox`) | `academy/workflows/inbox.js` | planned: the fixed instance order, at most three tickets each, one at a time, `ship.py checkpoint` after each |
| weekly usage and error settle (`/academy:usage --weekly`) | `academy/workflows/weekly.js` | planned: the usage-analyst packet, then `error_ledger.py settle --packet` |
