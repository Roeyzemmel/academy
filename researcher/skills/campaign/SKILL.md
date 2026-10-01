---
name: campaign
description: 'Run an opt-in, capped, autonomous campaign on one target claim: independent approaches, blocked routes, a concrete artifact per round, serial ticket dispatch. Use for "/researcher:campaign <target> --rounds N --agents M", "attack this claim with several approaches".'
---

# Campaign on a target

`$ARGUMENTS`: `<target-id> --rounds N --agents M [--runs K] [--profile <env>]`. The
default `/researcher:explore` is unchanged; this skill is opt-in and never starts
itself. Scripts: `$R`, `$A` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`.
The caps, what they suspend, serial dispatch and who enforces them are
`academy/references/budget.md` ("Campaigns"): read it first. The dispatch step, lab
runs, decisions and approach-ticket moves are
`${CLAUDE_PLUGIN_ROOT}/references/campaign-dispatch.md`. Discipline: `roster-rules.md`
(rule 7) and the `rigor` skill (reduction audit, theorem-strength lemma, no artifact no
result). No new agent: the main session briefs, relays and drives; `lead-researcher`
and `prover` do the work.

## Caps

Run `notebook.py campaign-check --rounds N --agents M [--runs K --profile P]` (add
`--cloud` in a cloud session). A missing required cap is an error: stop and ask,
suggesting 3 and 4, never applying them silently. Keep the normalized caps it prints
and count against them yourself.

## Round 0: seeding

`lead-researcher` creates at least four **approach** objects (`notebook.py new approach
AP-n --title ... --statement "the mechanism" --target <id>`), substantially different
mechanisms grouped by idea, not wording, duplicates merged; each has at least one
concrete direction (`new direction D-n --approach AP-n`; one approach per direction).
`notebook.py approach check --campaign <target>` confirms the count. It files one
target-level prior-art check as a `lookup` or `cite` ticket to the Expert, tagged for
the campaign, and records the result. Only the lead makes it: provers search background
and standard theorems for their own approach, never whether the target is solved, which
also keeps them independent.

## Each round (until a stop condition)

1. **Land what came back.** Returned tickets and results through
   `/researcher:inbox`, `/researcher:review-experiment`, `/researcher:settle`. A
   returned counterexample may block an approach; a returned confirmation may deliver one.
2. **One prover per active approach** that has work not waiting, one after another,
   each **blind**: briefed only with its approach id, its directions and the target
   statement. `notebook.py next <direction>` gives nothing for a blocked, dropped or
   delivered approach, and fails on a dangling `approach:`.
3. **A concrete artifact each**: a lemma with proof attempt, a construction, an
   equation, a counterexample to a sublemma. A report without one is no result and is
   logged as a wasted slot.
4. **Adversarial audit** with the `rigor` reduction audit. Anything claimed proved goes
   to the Expert's verify route (`/researcher:prove` files it); nothing is graded here.
5. **Lead updates the approaches**: continue, block, deliver or reopen with
   `notebook.py approach set AP-n <lifecycle> ...` (`blocked` needs `--blocked-by <lemma
   id> --reopen-if "..."`; reopening needs `--note` naming the new mechanism).
   `approach check` finds violations. Blocking and reopening move the approach's
   tickets: add `--apply` and see the reference.
6. **Diversity check**: more than half the active directions in one family, and the
   lead redirects the extras to underexplored formulations.
7. **Dispatch step** (reference; first skip `approach tickets --held`):
   `/academy:inbox --campaign <target>`, one ticket, one subagent, checkpoint, next; each
   counts against `--agents`.

Cross-pollination only after every surviving approach has had two rounds, and only
when the lead calls it. **A failed wave** (every approach blocked, or a round with no
artifact) is followed by a reseeding round: fresh formulations, plus any approach whose
`reopen_if` now holds.

## Tickets

Filed as the Researcher through the chain gate, tagged `campaign: <target>` (MCP
`tickets_create` field `campaign`, or `board.py new --campaign`), `refs` naming the
approach and direction. A direction with an open ticket is waiting on it: a pending
question, not a blocked approach. The lead keeps working everything else.

## Stops

**Stop only** when the target has two agreeing verify reviews (claim-keeper then sets
the status), after `--rounds` rounds, on a limit error (write `board/human/RESUME.md`
if unattended), or on a pause: `notebook.py approach status` says `PAUSE` when every
active approach waits on a human decision, and the reference says what else pauses.
Reaching `--agents` ends only the round.

## Final report

Per `honest-reporting` ("The final report of a long run"), plus the tickets filed and
the subagent runs used against the caps.
