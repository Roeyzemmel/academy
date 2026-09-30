---
name: campaign
description: 'Run an opt-in, capped, autonomous campaign on one target claim: independent approaches, blocked routes, a concrete artifact per round, serial ticket dispatch. Use for "/researcher:campaign <target> --rounds N --agents M", "attack this claim with several approaches".'
---

# Campaign on a target

`$ARGUMENTS`: `<target-id> --rounds N --agents M [--runs K] [--profile <env>]`. The
default `/researcher:explore` is unchanged; this skill is opt-in and never starts
itself. Scripts: `$R`, `$A` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`.
Details of the dispatch step, lab runs and decisions:
`${CLAUDE_PLUGIN_ROOT}/references/campaign-dispatch.md`. Rules: `academy/references/budget.md`
("Campaigns"), `roster-rules.md` (rule 7), and the `rigor` skill (reduction audit,
theorem-strength lemma, no artifact no result). No new agent: the main session briefs,
relays and drives; `lead-researcher` and `prover` do the work.

## Caps (stop and ask if a required one is missing)

- `--rounds N` and `--agents M` are **required**. Suggest 3 and 4, never apply silently.
  `--agents` caps subagent runs per round (provers and dispatched tickets together);
  filed tickets are counted in the report, not against it.
- `--runs K`: preapproved lab runs on `--profile`, **K = 0 if omitted**, and forced to
  0 in a cloud session (the workspace rule against heavy environments applies).
- Rules 1 to 3 of `budget.md` are suspended only inside these caps; **rule 2 (serial)
  never**: one subagent at a time. Rule 4 holds: a limit error ends the campaign.

## Round 0: seeding

`lead-researcher` creates at least four **approach** objects (`notebook.py new approach
AP-n --title ... --statement "the mechanism" --target <id>`), substantially different
mechanisms grouped by idea, not wording, duplicates merged; each has at least one
concrete direction (`new direction D-n --approach AP-n`). It files one target-level
prior-art check as a `lookup` or `cite` ticket to the Expert, tagged for the campaign,
and records the result. Only the lead makes it: provers do not search for whether the
target itself is solved (they search background and standard theorems for their own
approach), which also keeps them independent.

## Each round (until a stop condition)

1. **Land what came back.** Returned tickets and results through
   `/researcher:inbox`, `/researcher:review-experiment`, `/researcher:settle`. A
   returned counterexample may block an approach; a returned confirmation may deliver one.
2. **One prover per active approach** that has work not waiting, one after another,
   each **blind**: briefed only with its approach id, its directions and the target
   statement. `notebook.py next <direction>` gives nothing for a blocked approach.
3. **A concrete artifact each**: a lemma with proof attempt, a construction, an
   equation, a counterexample to a sublemma. A report without one is no result and is
   logged as a wasted slot.
4. **Adversarial audit** with the `rigor` reduction audit. Anything claimed proved goes
   to the Expert's verify route (`/researcher:prove` files it); nothing is graded here.
5. **Lead updates the approaches**: continue, block, or deliver
   (`notebook.py approach set AP-n blocked --blocked-by <lemma id> --reopen-if "..."`;
   it lists the approach's open tickets and the dead-route moves for them; reopening
   needs `--note` naming the new mechanism; `approach check` finds violations).
6. **Diversity check**: more than half the active directions in one family, and the
   lead redirects the extras to underexplored formulations.
7. **Dispatch step** (serial, see the reference): `/academy:inbox --campaign <target>`,
   one ticket, one subagent, checkpoint, next; each counts against `--agents`.

Cross-pollination only after every surviving approach has had two rounds, and only
when the lead calls it. **A failed wave** (every approach blocked, or a round with no
artifact) is followed by a reseeding round: fresh formulations, plus any approach whose
`reopen_if` now holds.

## Tickets

Filed as the Researcher through the chain gate, tagged `campaign: <target>` (MCP
`tickets_create` field `campaign`, or `board.py new --campaign`), `refs` naming the
approach and direction. A direction with an open ticket is waiting on it: a pending
question, not a blocked approach. The lead keeps working everything else.

## Pause, not spin, and stops

When every remaining direction waits on a ticket that no dispatch can move (a lab run
beyond `--runs`, an unreachable profile, a human decision), stop with "paused, waiting
on T-a, T-b"; the state is in the approach objects and the board, and the next
invocation resumes from them. **Human decisions are never recorded and no recommended
option applied**: leave the ticket `blocked` with `waiting_on: [human]`, note the
approach as waiting on decision, continue the others, point at `/academy:decide`.
**Stop only** when the target has two agreeing verify reviews (claim-keeper then sets
the status), at the round or agent cap, or on a limit error (write
`board/human/RESUME.md` if unattended).

## Final report

Status first, per `honest-reporting`: the audited proof, or the strongest rigorously
proved derivation and the exact remaining gap as a claim id; the approach table
(lifecycle, `blocked_by`, `reopen_if`); open tickets and what each waits for; tickets
filed and subagent runs used against the caps. No "best effort" summary.
