# Roster rules: who may do what

Stated once, here. Every role plugin's agents and skills follow these rules; the
permission tables that enforce part of them are in `academy/permissions.json`, and
the ticket protocol is `docs/protocol.md`.

## Independence

1. **The producer never grades its own work.** Whoever wrote an argument, an
   experiment, a citation card or a piece of code does not issue the verdict on it.
2. **The grader never edits what it grades.** Graders (`rigor-reviewer`,
   `experiment-reviewer`, `referee`) are read-only. Their verdicts reach the files
   through a SubagentStop hook, never through their own writes or the MCP write tools.
3. **The commissioner never grades.** An agent or skill that commissioned a piece of
   work (a lead-researcher that asked for a proof, a review-chair that launched two
   reviewer runs) adjudicates mechanically at most, by the decision table; it does
   not substitute its own reading for a verdict.
4. **Two agreeing, independent verdicts** are the grounds for raising a status
   (the `status-vocabulary` skill gives the mapping). Run B is launched only if run A
   is positive, and neither run sees the other.
5. **Only the status keeper changes a status** (`registry.statusKeeper`, default
   `claim-keeper`), and only with grounds, or on Roey's word.
6. **Only the human decides a packet.** Agents propose; `packets_decide` is
   human-only.

## Explaining is not grading

`explainer` and `clerk` are read-only. They report the status the registry holds and
never form their own view of whether something is true.

## Model fallback

Each agent's frontmatter carries `model:`, `effort:` and `fallback:`.

- When the primary model is unavailable, the **launching session** (the main session
  or the agent that spawns it) relaunches through the Agent tool's `model` override
  set to the fallback, and **names the substitution in its report** and in the ticket
  thread.
- The override is otherwise never passed. Passing it out of habit silently costs the
  run whatever authority its primary model carried.
- The Agent tool cannot override `effort`; a task that deserves another effort gets
  its own agent.
- **Graders have two equal primaries: Fable and Opus 5.5** (Roey, 2026-09-24,
  reconfirmed 2026-09-28). A verdict of `rigor-reviewer`, `experiment-reviewer` or
  `referee` on either one carries full authority; the graders' frontmatter fallback
  `opus` resolves to Opus 5.5 and so is itself a primary. Every verdict records the
  exact model it ran on (`claude-fable-…`, `claude-opus-5-5`), never a bare family
  name: a bare `opus` names no version and is read as a fallback.
- **Graders degrade rather than substitute.** A proof verdict reached on any other
  model (Sonnet, Haiku, an older Opus) is at most PLAUSIBLE; an experiment verdict on
  one is at most GAP; a referee report on one marks itself reduced-strength. A
  degraded verdict never counts toward the two agreeing verdicts. The scripts apply
  this mechanically: `expert/scripts/decision_table.py` (`PRIMARY_MODELS`),
  `researcher/scripts/_researcher.py` (`PRIMARY_MODELS`, used by `land_review.py` and
  `settle.py`) and `expert/scripts/land_referee.py`.
- A limit error is not "unavailable": it stops the run (budget.md rule 4).

## Standing conduct

- Never invent a citation, a pinpoint, an id or a result (`citation-discipline`).
- Every judgement call gets a machine note (`honest-reporting`).
- No `git stash`, no push. Commit only where the home's config and Roey allow it.
- Agents change the board only through the MCP tools or the board scripts; the human
  may edit by hand.
