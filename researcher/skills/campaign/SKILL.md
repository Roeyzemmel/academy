---
name: campaign
description: 'Run an opt-in, capped, autonomous research campaign on one target claim, led by lead-researcher: independent approaches, an artifact per round; other roles only by tagged tickets. Use for "/researcher:campaign <target> --rounds N --agents M".'
---

# Campaign on a target

`$ARGUMENTS`: `<target-id> --rounds N --agents M [--runs K] [--profile <env>]`. The
default `/researcher:explore` is unchanged; this skill is opt-in and never starts
itself. Scripts: `$R`, `$A` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`.

**What a campaign is.** Autonomous and research-focused: the Researcher attacks one
target with several independent approaches, led by `lead-researcher`, with blind
`prover` runs. The human sets the caps and is asked nothing until a decision is due
(the interactive, human-led counterpart is `/academy:cowork`). The caps, what they
suspend and who enforces them are `academy/references/budget.md` ("Campaigns"): read it
first. Ticket mechanics, waiting and pausing are
`${CLAUDE_PLUGIN_ROOT}/references/campaign-dispatch.md`. Discipline: `roster-rules.md`
(rule 7 and the "Role cut") and the `rigor` skill (reduction audit, theorem-strength
lemma, no artifact no result).

**The role cut holds throughout.** The campaign runs the Researcher's own agents only
(`lead-researcher`, `prover`, and the Researcher's own skills). Work for another role
(a verification, a citation, an experiment, landing in a paper) is **only ever a
ticket**, tagged `campaign: <target>`, and then the campaign **waits for the next
actor**: that role's own inbox run (`/<role>:inbox --campaign <target>`, in that role's
session, or `/academy:inbox --campaign <target>` run by the human). The campaign never
runs another role's agents and never works another role's ticket.

## Caps

Run `notebook.py campaign-check --rounds N --agents M [--runs K --profile P]` (add
`--cloud` in a cloud session). A missing required cap is an error: stop and ask,
suggesting 3 and 4, never applying them silently. Keep the normalized caps it prints
and count against them yourself (`academy/lib/workplan.py` `caps`).

## Round 0: seeding

`lead-researcher` creates at least four **approach** objects (`notebook.py new approach
AP-n --title ... --statement "the mechanism" --target <id>`), substantially different
mechanisms grouped by idea, not wording, duplicates merged; each has at least one
concrete direction (`new direction D-n --approach AP-n`; one approach per direction).
`notebook.py approach check --campaign <target>` confirms the count. It files one
target-level prior-art check as a `lookup` or `cite` ticket to the Expert, tagged for
the campaign, and records the answer when it comes back. Only the lead makes it:
provers search background and standard theorems for their own approach, never whether
the target is solved, which also keeps them independent.

## Each round (until a stop condition)

1. **Take what came back.** The tickets returned to this Researcher (delivered by
   another role, or addressed to it) through `/researcher:inbox --campaign <target>`,
   and results through `/researcher:review-experiment` and `/researcher:settle`. A
   returned counterexample may block an approach; a returned confirmation may deliver one.
2. **One prover per active approach that is not waiting**, one after another (serial,
   `budget.md` rule 2), each **blind**: briefed only with its approach id, its directions and the target
   statement. `notebook.py approach status` gives each approach's state: `WAITING`
   (its tickets are out with another role's next actor) and `PAUSE` (a human decision)
   approaches get no prover this round. `notebook.py next <direction>` gives nothing
   for a blocked, dropped or delivered approach, and fails on a dangling `approach:`.
3. **A concrete artifact each**: a lemma with proof attempt, a construction, an
   equation, a counterexample to a sublemma. A report without one is no result and is
   logged as a wasted slot.
4. **Adversarial audit** with the `rigor` reduction audit. Anything claimed proved goes
   to the Expert's verify route as a ticket (`/researcher:prove` files it); nothing is
   graded here.
5. **Lead updates the approaches**: continue, block, deliver or reopen with
   `notebook.py approach set AP-n <lifecycle> ...` (`blocked` needs `--blocked-by <lemma
   id> --reopen-if "..."`; reopening needs `--note` naming the new mechanism).
   `approach check` finds violations. Blocking and reopening move the approach's
   tickets: add `--apply` and see the reference.
6. **Diversity check**: more than half the active directions in one family, and the
   lead redirects the extras to underexplored formulations.
7. **Hand-off step** (reference): file every ask for another role as a tagged ticket,
   then list what is out (`notebook.py approach status`, `py $A/cowork.py list --kind
   campaign`). Those tickets wait for the next actor; the round goes on with every
   approach that is not waiting. Each prover run counts against `--agents`; a ticket
   filed counts against nothing.

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
if unattended), or when nothing can move: `notebook.py approach status` says `PAUSE`
(every active approach waits on a human decision) or `WAITING` (every active approach
waits on another role's next actor). Report which tickets the campaign waits on and
whose inbox run moves them; the next invocation resumes from the approach objects and
the board. Reaching `--agents` ends only the round.

## Final report

Per `honest-reporting` ("The final report of a long run"), plus the tickets filed,
the tickets still out (with the inbox run that moves each), and the subagent runs used
against the caps.
