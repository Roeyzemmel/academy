# Campaign mode: portfolio of approaches, blocked routes, concrete artifacts

Status: base design agreed with Roey, 2026-09-29, section by section. Revision 2
(same day) makes the campaign autonomous and lets it launch the other plugins
itself (decisions 6-8, sections 4.1-4.3). Next: Roey reviews this file, then the
implementation plan.

## 1. Purpose

Bring the working attitude of OpenAI's CDC prompt
(`cdc_prompt.pdf`, "Prompt used for a proof of the Cycle Double Cover Conjecture")
into the academy plugins. The subject of that prompt is irrelevant; the attitude is:

- start with a genuinely diverse portfolio of approaches, kept independent early;
- keep an explicit registry of approach families, grouped by mathematical idea;
- a route that ends at a lemma as strong as the target is blocked, and is reopened
  only for a materially new mechanism, invariant or construction;
- adversaries work from a concrete list of failure modes;
- agents return concrete lemmas, constructions, equations or counterexamples;
  status reports and "routine" are rejected;
- a failed wave is not a stopping point; the root synthesizes and relaunches;
- the end is an audited proof, or the strongest rigorously proved derivation and
  its exact remaining gap;
- search is for background, not for looking the answer up.

Today none of this exists. `researcher:explore` is one serial pass over at most
three items with one prover per item (`researcher/skills/explore/SKILL.md`,
`researcher/agents/lead-researcher.md`), bound by `academy/references/budget.md`.
Nothing gives approaches independence, nothing records a blocked route beyond
the informal phrase in `academy/skills/rigor/SKILL.md` §4.

## 2. Decisions

1. **Opt-in.** The default `explore` is unchanged. A new skill
   `researcher:campaign` carries the loop, under explicit caps set by Roey.
2. **`approach` is a new object kind**, a mathematical idea that gathers several
   concrete directions.
3. **Campaigns are asynchronous.** They use the Scientist and the Expert through
   tickets and keep working other directions while tickets are open.
6. **Autonomous to the stop condition.** Once invoked with its caps, a campaign
   runs rounds, relaunches after a failed wave and reseeds without asking Roey. It
   stops only at the stop conditions of section 4 or when nothing but a human-only
   decision remains (parked as a packet, section 4.3).
7. **The campaign launches the other roles itself.** It dispatches one subagent per
   ticket to the receiving role and lands the result, instead of leaving the other
   inboxes to Roey (section 4.1). This suspends board rule 3 ("nothing starts
   itself") inside a campaign only.
8. **Lab runs are preapproved by a cap**, not run by default (section 4.2).
4. **Discipline rules are shared and stated once** (`rigor`, `honest-reporting`,
   `budget.md`, `roster-rules.md`); everything else points to them.
5. **Search discipline deviates from the CDC prompt on purpose** (section 6).

## 3. The `approach` object

`objects/approach/<ID>.md` in a Researcher notebook. Fields:

| field | meaning |
|---|---|
| `id`, `kind: approach`, `title` | as other objects |
| `statement` | the mechanism, one line |
| `target` | registry id of the claim the campaign aims at |
| `lifecycle` | `active`, `blocked`, `delivered`, `dropped` |
| `blocked_by` | registry id of the theorem-strength lemma; required when `blocked` |
| `reopen_if` | the new mechanism, invariant or construction that would justify reopening |
| `history` | rows `date | lifecycle | what`, as on other objects |

- `lifecycle` is a lifecycle, like a direction's, not a claim status. Claim-keeper
  is not involved; the lead-researcher sets it.
- **The direction owns the link.** A direction gets an optional `approach: <id>`.
  The approach's members are computed by `notebook.py`, never hand-kept.
  A direction belongs to at most one approach.
- **Blocking has teeth.** `notebook.py next` skips directions of a blocked
  approach. `blocked` without `blocked_by` is an error. Reopening needs a history
  row naming the new mechanism; nothing else reopens.
- A lemma is theorem-strength if it implies the target, or is implied by it under
  known reductions. Deciding that stays a recorded judgement (the lead names the
  lemma; a reviewer may challenge it); the registry does not decide it.

## 4. `/researcher:campaign <target> --rounds N --agents M`

A thin skill (under the 120-line limit). The main session briefs and relays; the
lead-researcher and prover do the work; no new agent (the agent set in
`researcher/tests/test_plugin.py` is unchanged).

**Caps.** `--rounds` and `--agents` are required; `--runs K` (lab runs, 0 if
omitted) and `--profile <env>` (the only lab profile the campaign may queue on)
are optional. The skill stops and asks if a required cap is missing. A suggested
starting point is 3 rounds and 4 agents, never applied silently. `budget.md` gets
one rule: a campaign's caps are set by Roey per invocation, and its rules 1-3
(three items, serial, nothing starts itself) are suspended only inside them.
Rule 4 holds: a limit error ends the campaign with a report. Rules 5-9 hold for
every dispatched subagent.
`--agents M` caps parallel provers; tickets filed do not count against it but are
counted in the report. Each ticket keeps its own `budget.runs`.

**Round 0, seeding.** Lead-researcher creates at least four approach objects,
substantially different mechanisms, each with at least one concrete direction,
grouped by mathematical idea and not by wording, duplicates merged. It files one
target-level prior-art check as a lookup or cite ticket to the Expert and records
the result (section 6).

**Each round.**
1. Land what came back: returned tickets through `researcher:inbox`, experiment
   results through `settle` / `review-experiment`. A returned counterexample may
   block an approach; a returned confirmation may deliver one.
2. One prover per active approach with work not waiting, up to M in parallel,
   each blind to the others: briefed only with its approach, its directions and
   the target statement.
3. Each prover returns a concrete artifact (lemma with proof attempt,
   construction, equation, counterexample to a sublemma). A report without one is
   no result and is logged as a wasted slot.
4. Adversarial audit with the checklist of section 5. Anything claimed as proved
   goes to the Expert's verify route; nothing is graded here.
5. Lead updates the registry: continue, block (with `blocked_by`, `reopen_if`) or
   deliver.
6. Diversity check: if more than half of the active directions share one family,
   the lead redirects the extras to underexplored formulations.

**Tickets.** All go through the existing chain gate
(`2026-09-28-ticket-chain-gate-design.md`): falsifiers, counterexample searches
and sanity checks to the Scientist through the `experiment-spec` relay; verify,
cite, lookup and literature questions to the Expert through `lit-request` and the
Expert's own routes. Each ticket names its approach and direction.
A direction with an open ticket is `waiting on T-nnnn`. That is not a blocked
approach: it is a pending question. The lead keeps working everything else.

**Cross-pollination** only after every surviving approach has had at least two
rounds, and only when the lead calls it.

**A failed wave** (every approach blocked, or a round with no concrete artifact)
is followed by a reseeding round: fresh formulations, plus any approach whose
`reopen_if` now holds.

**Pause, not spin.** When every remaining direction waits on a ticket that no
dispatch can move (blocked on a lab run beyond `--runs`, an unreachable profile,
or a human), the campaign stops with "paused, waiting on T-a, T-b". It resumes from
the registry and the board on the next invocation; the approach objects carry all
the state. Waiting on a ticket that section 4.1 can dispatch is not a pause: the
campaign dispatches it.

**Stop conditions, only these:** the target has two agreeing verify reviews (then
claim-keeper sets the status); the round or agent cap; a limit error.

**Final report**, status first: the audited proof, or the strongest rigorously
proved derivation plus the exact remaining gap as a claim id; the approach table
(lifecycle, `blocked_by`, `reopen_if`); open tickets and what each waits for.
No "best effort" summary, no explanation of why the problem is hard.

### 4.1 Launching the other roles

Inside a campaign the main session is the driver. After filing tickets it runs a
**dispatch step** and lands what comes back before the next round:

1. List open tickets addressed to the Scientist, the Expert and the Researcher's own
   relays that carry this campaign's approach tag (`board.py list`, filtered).
2. For each, dispatch **one subagent** for the receiving role, briefed with the
   ticket id only (budget rule 9), through that role's existing route:
   Scientist tickets via `scientist:experimenter` (experiments) or
   `scientist:developer` / `test-engineer` (code); Expert tickets via
   `expert:librarian` (cite, lookup), `expert:review-chair` (verify) and the two
   relays (`research-intake`, `paper-liaison`); Researcher relays via
   `experiment-spec` and `lit-request`; returned tickets via `claim-keeper` and
   `experiment-reviewer`. Independent tickets go in one message, in parallel, up to
   `--agents M` in flight across provers and dispatched subagents together.
3. Each dispatched subagent works as the role's inbox would: it moves the ticket
   `accepted`, then delivers or blocks it with a thread line, under its own
   `budget.runs` and `max_model`. The driver checks the ticket state afterwards; a
   ticket left `accepted` with no delivery is logged as a wasted slot and not
   redispatched in the same round.
4. Relays whose child tickets delivered get their return leg the same way.

No new agent is added: subagents cannot themselves spawn subagents, so the driver
stays in the main session and the role agents are the existing ones (the agent set
in `researcher/tests/test_plugin.py` is unchanged). Roles that nest in their own
definitions (`review-chair` launching rigor-reviewers, `lead-researcher` launching
provers) keep doing so; where nesting is unavailable in a session, the driver runs
that level itself, one step at a time.

The ticket chain gate is untouched: the driver files tickets as the Researcher and
never as another role, and each receiving role files only its own neighbour
tickets. The driver grants no permissions.

### 4.2 Lab runs

`--runs K` is a preapproval of at most K queued lab runs on `--profile`, in place
of a per-run header approval by Roey. Inside the cap the Scientist's experimenter
still writes the header and the validation case and files the run, and the header
is still recorded in the ticket, but it is not held for a human. Preflight,
provenance and the environment policy are unchanged. A failed preflight, an
experiment that needs a different profile, or the K+1st run parks its ticket as
waiting on human. K=0 (the default) means every experiment ticket pauses at its
header, as today. In a cloud session the workspace CLAUDE.md rule against heavy
environments still applies: K is forced to 0 there.

### 4.3 Decisions and unattended operation

The campaign never records a human decision and never applies a recommended
option. A packet or ticket that needs Roey is created or left `blocked` with
`waiting_on: [human]`, and the approach it concerns is marked `waiting on
decision`; other approaches continue. If every approach waits on a human, the
campaign pauses. The report lists them and points at `/academy:decide`. An
unattended run writes `board/human/RESUME.md` as budget rule 4 describes. Status
changes still go only through claim-keeper on two agreeing reviews.

## 5. Shared discipline (stated once, pointed to elsewhere)

In `academy/skills/rigor/SKILL.md`:
- **§4, theorem-strength lemma.** A route ending at one has made no progress
  toward the target unless it supplies a new proof of the lemma; it is marked
  blocked. This formalizes the informal "blocked route" phrase already there.
- **§3, reduction audit for adversaries**, generic forms of the CDC failure modes:
  the constructed object is not the one defined (a weaker notion passing for it);
  a quantity counted with the wrong multiplicity; degenerate cases dropped (empty,
  disconnected, repeated); a reduction that introduces a case violating the
  hypotheses; circular use of the target or an equivalent statement.
- **§5, no artifact, no result.** A report without a lemma, construction,
  equation, proof attempt or counterexample counts as nothing. "Promising" and
  "routine" are not accepted for an unproved compatibility or global statement;
  it is written down as a lemma and treated as open.

In `academy/skills/honest-reporting/SKILL.md`: the final-report shape of §4.

In `academy/references/roster-rules.md`: the independence rule for blind provers.
In `academy/references/budget.md`: the campaign-caps rule, which also states that
inside a campaign rule 3 is suspended for dispatching tickets and for lab runs up
to `--runs`, and for nothing else.

`explore`, `lead-researcher` and `prover` get one-line pointers, not copies.
The rigor-reviewer's VERDICT block is untouched (the Expert's hooks read it).
The plugin tests ban domain words, so nothing domain-specific goes in. Domain
items for a home's `verification-checklist.md` and the domain pack's `traps.md`
are an optional follow-up through an `expert:domain` ticket.

## 6. Search discipline (deliberate deviation)

The CDC prompt forbids searching for a solution to the target; that was a
benchmark-integrity rule. The academy is built the other way: `citation-discipline`
says cite before reproving, and the prover's scout treats a hit against the claim
as the most valuable outcome. That stays.

In campaign mode, provers search only for background and standard theorems
relevant to their approach; they do not search for whether the target itself is
solved, which also keeps them independent. The lead makes the single
target-level prior-art check at seeding, through the Expert, and records it.
Outside campaign mode the scout is unchanged.

## 7. Tests and order of work

Tests first (TDD), then code:

1. `researcher/tests/test_notebook.py`: the approach kind parses; membership is
   computed from directions' `approach:`; `next` skips blocked approaches;
   `blocked` without `blocked_by` fails; reopening without a history row fails.
2. `notebook.py` and the object template: the `approach` kind, `approach:` on
   directions.
3. Shared rules: `rigor`, `honest-reporting`, `budget.md`, `roster-rules.md`.
4. `researcher/skills/campaign/SKILL.md` (round loop, the dispatch step of 4.1,
   caps, pause, report), and `SKILLS` in `test_plugin.py` (size limit and
   no-domain-words checks apply). Tests: the skill mentions `--rounds`,
   `--agents` and `--runs`, states the K=0 default, and names no agent outside the
   existing set. If the 120-line limit binds, the dispatch table moves to
   `researcher/references/campaign-dispatch.md` and the skill points to it.
5. One-line pointers in `explore`, `lead-researcher`, `prover`; one line each in
   `researcher/README.md` and `docs/roles.md`.
6. `py -m unittest discover researcher/tests`.

Open risks: (a) the dispatch step assumes the Agent tool is available to the main
session and that a role's ticket route can run as a subagent; the plan verifies
this on one Scientist and one Expert ticket before the skill is written.
(b) Auto-launch multiplies spend; `--agents`, per-ticket `budget.runs` and the
limit-error stop are the only brakes, and `/academy:usage` is how Roey checks.
(c) the registry check (`claims_check`) must accept the new kind. If that
lives in the MCP server (`academy/mcp/`), it is a second change and is flagged in
the plan before it is touched. `test_vendored_lib_is_in_sync` requires
`researcher/scripts/_academy.py` to equal `academy/lib/academy_common.py`, so any
change to the shared library is made there and re-vendored.
