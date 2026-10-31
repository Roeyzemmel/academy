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

## Run it

The rounds are code (2026-10-31): `academy/workflows/workplan.js`, which a cowork pass
shares (docs/workflows.md). Call the **Workflow** tool with
`scriptPath: ${CLAUDE_PLUGIN_ROOT}/../academy/workflows/workplan.js` and
`args: {kind: "campaign", root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>", home: "<this home>", instance: "<this instance>", target: "<id>", rounds: N, agents: M, runs: K, profile: "<env>", cloud: <true in a cloud session>}`.

The script holds, in this order:
- **The caps** (`notebook.py campaign-check`). A missing required cap stops it; ask the
  human, suggesting 3 rounds and 4 agents, never applying them silently.
- **Round 0** seeding by `lead-researcher` until `approach check` passes: at least four
  substantially different approaches, each with a direction, plus the one target-level
  prior-art ticket to the Expert.
- **Each round:**
  - take what came back: this Researcher's inbox scoped to the campaign, nested;
  - one blind `prover` per `ACTIVE` approach, serially, at most `--agents` per round,
    briefed only with its approach, its directions' next items and the target statement;
  - a concrete artifact each, checked on disk (none is a wasted slot);
  - the lead's reduction audit, approach updates, diversity check and hand-off tickets
    tagged `campaign: <target>`. Cross-pollination comes only after every survivor has
    had two rounds; a failed wave makes the next round a reseeding round.
- **The stops**: the target `proved` (two agreeing verify reviews); every active
  approach waiting on the human (`PAUSE`) or on another role (`WAITING`); `--rounds`
  reached; a lost agent; the token budget spent.

What only this session may do comes back in `for_main` (a nested route, a decision for
the human): run it, then call again to resume, from the approach objects and the board.
Work for another role is only ever a ticket tagged `campaign: <target>` (the
`tickets_create` field `campaign`, or `board.py new --campaign`), and the campaign waits for that
role's next actor (`/<role>:inbox --campaign <target>`). It never runs another role's
agents. If the run is unattended and stops on a limit, write `board/human/RESUME.md`.

## Final report

Per `honest-reporting` ("The final report of a long run"), plus the tickets filed,
the tickets still out (with the inbox run that moves each), and the subagent runs used
against the caps.
