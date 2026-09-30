# Budget: the rules every run obeys

Stated once, here. Every academy skill and agent that launches work reads this file;
a role plugin's skills point at it rather than restating it. The numbers come from
`.claude/academy.json` `budget` (docs/config.md section 2); the defaults are below.

Origin: one pass once launched 35 subagents, 14 heavyweight verifier runs and three
open-ended source hunts, and 18 agents were killed by the session limit, several of
them relaunches into a quota that was already gone. These rules exist so that cannot
happen again.

## The rules

1. **At most `budget.itemsPerRun` items per run (default 3, never more than 3).** An
   item is a ticket, an agenda item, a packet decision batch or a deep-dive subject.
   The rest waits for the next invocation. Say how many remain.
2. **Serially.** One item finishes and is checkpointed in its file (ticket thread,
   packet, agenda) before the next starts. No parallel fan-out of items.
3. **Nothing starts itself.** Writing a decision, closing a ticket or landing a packet
   starts no work. Work starts only when Roey invokes a skill (or a scheduled job he
   set up, such as the weekly usage report).
4. **No relaunch after a limit error.** If an agent returns a usage-limit, rate-limit
   or session-limit error, or an empty result: do not relaunch it, launch nothing
   further, record what was and was not done (the ticket thread, or
   `board/human/RESUME.md` in an unattended run), and report. No retry loops, no sleep
   and retry.
5. **Never ask questions from a subagent.** A subagent makes the routine call, states
   the assumption in its report, and returns. Only the main session asks Roey, with
   `AskUserQuestion`, at a decision point.
6. **The lightest agent that can do the work.** Orchestration runs on
   `budget.orchestratorModel` (sonnet). No agent runs heavier than `budget.maxModel`
   or than the ticket's `budget.max_model`. Graders run on a primary, Fable or
   Opus 5.5, which count equally (roster-rules.md, "Model fallback"); a grader run on
   a lighter model spends a run for a verdict that cannot count.
7. **A ticket spends at most its own `budget.runs` agent runs.** If it needs more,
   the receiver moves it to `blocked` with `waiting_on: [human]` and a thread line
   asking for more budget (docs/protocol.md section 4).
8. **Turn caps.** Agents that can wander carry `maxTurns`. A capped agent returns a
   partial result: record what is unfinished and move on. Neither relaunch it nor
   raise the cap. Graders whose verdict is worthless when cut off have no cap.
9. **Short briefs.** Point the agent at the ticket, packet or object id; it reads the
   files. Text pasted into a brief is paid again on every turn of the agent.

## Campaigns

The one place the campaign rules are stated (`/researcher:campaign` and its dispatch
reference point here). A campaign runs under caps Roey sets per invocation:

- `--rounds N` (required): the campaign ends after N rounds.
- `--agents M` (required): subagent runs per round, provers and dispatched tickets
  together. Reaching M **ends the round, not the campaign**: what is left waits for the
  next round. Tickets filed are reported, not counted.
- `--runs K` (default 0): lab runs preapproved on `--profile`. **K is 0 unless given, and
  forced to 0 in a cloud session** (the workspace rule against heavy environments).

Without the two required caps it does not start. Inside the caps, and for nothing else:

- **Rule 3 is suspended** for dispatching tickets through the inbox and for lab runs up to
  `--runs`; rule 1 is replaced by the caps (`inbox.py --campaign` lists without the cut of
  three).
- **Rule 2 is never suspended.** Dispatch is one subagent at a time, each checkpointed
  before the next; there is no fan-out, so a limit error loses at most the ticket in hand.
- **Rule 4 holds**: a limit error ends the campaign with a report. Rules 5 to 9 hold for
  every dispatched subagent.

**Who enforces the caps.** The driver (the main session), not code: nothing counts
`--agents`, `--rounds` or `--runs`, or detects a cloud session. `notebook.py
campaign-check` only validates that the caps are present and normalizes them (forcing
K to 0 when `--cloud` or the cloud environment variable says so); the driver then keeps
count.

## Measuring

`/academy:usage` reports turns and cache volume by instance, role and agent, with
limit failures. Compare a run against it before and after changing a pass.
