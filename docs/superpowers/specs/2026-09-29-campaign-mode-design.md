# Campaign mode: portfolio of approaches, blocked routes, concrete artifacts

Status: base design agreed with Roey, 2026-09-29, section by section. Revision 2
(same day) makes the campaign autonomous and lets it launch the other plugins
itself (decisions 6-8, sections 4.1-4.3). Revision 3 (same day) makes all
launching serial, adds dead-route blocking on tickets and a shared inbox core with
`/author:inbox` (decisions 9-11, sections 8-10). The work is three subsystems, built
in this order, each with its own plan: **inbox (section 8, 10), ticket blocking
(section 9), campaign (sections 3-6)**. Next: Roey reviews this file, then the first
plan.

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
7. **The campaign launches the other roles itself, serially.** It runs the shared
   inbox (section 8) one ticket at a time and lands each result before the next
   starts, instead of leaving the other inboxes to Roey (section 4.1). This
   suspends board rule 3 ("nothing starts itself") inside a campaign only.
   Nothing runs in parallel, so no result can be lost to a concurrent run.
8. **Lab runs are preapproved by a cap**, not run by default (section 4.2).
9. **One inbox core, thin role skills** (section 8). Selection, ordering, return
   legs, the blocked filter and the serial checkpoint live once in the shared
   library; each role keeps only its routing table.
10. **Two kinds of blocked ticket** (section 9): pending (`waiting_on`, unchanged)
    and dead route (`blocked_by` + `reopen_if`, new). The `approach` object's
    blocking (section 3) uses the same fields and words.
11. **The Author works through `/author:inbox`** (section 10), and the board is its
    only queue: the roadmap is dropped (Roey, 2026-09-30), work items are tickets, and
    the note sweep runs on every invocation.
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
`--agents M` caps the subagent runs per round (provers and dispatched tickets
together, all serial); tickets filed do not count against it but are
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
2. One prover per active approach with work not waiting, one after another,
   each blind to the others: briefed only with its approach, its directions and
   the target statement. Independence comes from the brief, not from concurrency.
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

Inside a campaign the main session is the driver, and it drives the shared inbox
of section 8, **strictly serially**. The **dispatch step** follows filing:

1. `inbox --campaign <target>` lists open, accepted or in-progress tickets that
   carry this campaign's approach tag, in inbox order, skipping dead-route blocked
   ones (section 9). In-progress tickets come first: unfinished work is resumed
   before anything new starts.
2. Take the first ticket. Dispatch **one subagent** for the receiving role,
   briefed with the ticket id only (budget rule 9), through the role's existing
   route in its routing table (`scientist:experimenter`, `expert:librarian`,
   `expert:review-chair`, the relays, `claim-keeper`, `experiment-reviewer`, ...).
3. The subagent moves the ticket `accepted` then `in-progress`, works, and
   delivers or blocks it with a thread line, under its own `budget.runs` and
   `max_model`. **Checkpoint before the next:** the driver reads the ticket back and
   confirms the state and thread line. A ticket left `in-progress` with no
   delivery is reported as unfinished and is not redispatched in the same round; it
   is first in line next time. Then take the next ticket.
4. Relays whose child tickets delivered get their return leg the same way, in
   inbox order.

There is no fan-out: at most one subagent runs at a time, so a limit error or a
crash loses at most the one ticket in hand, which the checkpoint has already
recorded. No new agent is added: subagents cannot spawn subagents, so the driver
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
to `--runs`, and for nothing else; rule 2 (serial) is never suspended.

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

Tests first (TDD) within each phase. Three phases, each its own plan, in order:

**Phase 1, shared inbox and `/author:inbox` (sections 8, 10).** Vendored core and its
tests; the three role wrappers ported; `/academy:inbox`; the Author's inbox
(tickets only, no roadmap), landings and sweep-first; `next` retired; docs and skill tables.

**Phase 2, ticket blocking (section 9).** `validate_ticket`, `transition_ticket`,
`docs/protocol.md`, the MCP `tickets_update`; the core's dead-route filter.

**Phase 3, campaign (sections 3-6, 4.1-4.3).**

1. `researcher/tests/test_notebook.py`: the approach kind parses; membership is
   computed from directions' `approach:`; `next` skips blocked approaches;
   `blocked` without `blocked_by` fails; reopening without a history row fails.
2. `notebook.py` and the object template: the `approach` kind, `approach:` on
   directions.
3. Shared rules: `rigor`, `honest-reporting`, `budget.md`, `roster-rules.md`.
4. `researcher/skills/campaign/SKILL.md` (round loop, the serial dispatch step of
   4.1, caps, pause, report), and `SKILLS` in `test_plugin.py` (size limit and
   no-domain-words checks apply). Tests: the skill mentions `--rounds`,
   `--agents` and `--runs`, states the K=0 default and that dispatch is serial, and
   names no agent outside the existing set. If the 120-line limit binds, the
   dispatch table moves to `researcher/references/campaign-dispatch.md` and the
   skill points to it.
5. One-line pointers in `explore`, `lead-researcher`, `prover`; one line each in
   `researcher/README.md` and `docs/roles.md`.
6. `py -m unittest discover researcher/tests`.

Open risks: (a) the dispatch step assumes the Agent tool is available to the main
session and that a role's ticket route can run as a subagent; the plan verifies
this on one Scientist and one Expert ticket before the skill is written.
(b) Auto-launch multiplies spend; `--agents`, per-ticket `budget.runs` and the
limit-error stop are the only brakes, and `/academy:usage` is how Roey checks.
Serial dispatch bounds loss, not cost, and makes a campaign slower.
(d) `academy/lib/academy_common.py` and the MCP files have uncommitted edits in
Roey's checkout; phases 1-2 touch the same files, so they are rebased onto whatever
Roey merges first. (e) Retiring `/author:next` changes a habit and the skill
listing; the plan keeps a one-line redirect for one release.
(c) the registry check (`claims_check`) must accept the new kind. If that
lives in the MCP server (`academy/mcp/`), it is a second change and is flagged in
the plan before it is touched. `test_vendored_lib_is_in_sync` requires
`researcher/scripts/_academy.py` to equal `academy/lib/academy_common.py`, so any
change to the shared library is made there and re-vendored.

## 8. The shared inbox core

**Today** the researcher, expert and scientist `scripts/inbox.py` are three copies
with their own selection, ordering, limit flag (`--n` / `--limit`) and return-leg
handling (the scientist's has none); the Author has no inbox, and
`author/scripts/next.py` mixes roadmap items and tickets (the roadmap is dropped in
section 10).

**Design.** One library `inbox_core` in `academy/lib/academy_common.py` (vendored
into every plugin's `_academy.py` like the rest, `test_vendored_lib_is_in_sync`):

- `select(board, instance, limit, all=False)`: the tickets to handle. Takes, in
  order: in-progress tickets of the instance (resume first), return-leg relay
  parents (`relay_return_ready`), then open and accepted tickets, by priority, then
  the ticket's `agenda` position if it has one, then id. Skips dead-route blocked
  tickets (section 9) and pending blocked ones. Limit `budget.itemsPerRun`, never
  above 3 outside a campaign. `all` lists without cutting.
- One output shape, JSON or text: `{id, kind, priority, return, route: {how, target,
  why}, over_budget}`; how is `skill`, `agent`, `human` or `reject`.
- `serial_checkpoint(ticket)`: after a route runs, the ticket must be delivered,
  blocked with its reason, rejected, or reported unfinished; the inbox says which.
  No ticket is taken while another is unfinished.

**Per role** only the routing table stays in the plugin: `route(ticket)` in a small
`routes.py` beside `inbox.py`, which becomes a thin wrapper over `select`. The
Expert's and Scientist's `--limit` become `--n`, with the old flag an alias; the
Expert gets `--all`. The `(return)` marking, `over_budget` and the expert's
`BELONGS` rejections carry over unchanged.

**Skills.** `/researcher:inbox`, `/expert:inbox`, `/scientist:inbox` stay, each a
thin wrapper (the return-leg wording that `test_interface_scripts.py` requires
stays). New `/academy:inbox` runs across every instance in `workspace.json`, in a
fixed order (Author, Expert, Researcher, Scientist), one ticket at a time under the
same 3-item cap; `/academy:desk` is unchanged. A campaign uses `/academy:inbox
--campaign` (section 4.1).

**Tests.** A new `academy/tests/test_inbox_core.py` covers ordering, resume-first,
return legs, the blocked filter, the limit and the checkpoint, against fixture
boards; the existing researcher, scientist and (new) expert inbox tests are
ported to the wrappers and must still pass.

## 9. Blocking on tickets

**Today** a blocked ticket only needs `waiting_on` (ids, instances or `human`); no
reason is required, and nothing records why a route was abandoned
(`academy_common.py` `validate_ticket`, `board.py` `transition_ticket`,
`docs/protocol.md` section 4).

**Two kinds, told apart by their fields.**

| kind | fields | meaning | inbox |
|---|---|---|---|
| pending | `waiting_on` non-empty | waiting for a ticket, an instance or Roey | not taken; return legs as today |
| dead route | `blocked_by` (a ticket or claim id) and `reopen_if` (one line) | the route ends at a result as strong as the goal, or at a refutation; reopens only for a materially new mechanism, invariant or construction | never taken |

- `blocked` needs `waiting_on` **or** both `blocked_by` and `reopen_if`; a dead-route
  block also needs a thread line naming what was tried. Both kinds at once is an
  error. `validate_ticket` and `transition_ticket` enforce it; `permissions.json`
  `tickets.transitions` is unchanged (the transitions are the same).
- **Reopening** is `blocked -> accepted` by the receiver with
  `--reopen "<the new mechanism>"`, required for a dead-route ticket; it appends a
  `reopened:` thread line and clears both fields. Nothing else reopens one. The
  sender may still cancel, with a reason.
- **Same words as the campaign.** An approach object's `blocked_by` / `reopen_if`
  (section 3) and a ticket's are the same fields with the same rules; when a lead
  blocks an approach, its open tickets are moved to dead-route blocked with the
  same `blocked_by`, and the tickets reopen with the approach.
- Docs: `docs/protocol.md` section 4 (statuses and the two kinds), the MCP
  `tickets_update` accepts the new fields (an `academy/mcp/` change, flagged in the
  plan before it is touched).
- **Tests:** in `academy/tests/test_board.py` and `test_common.py`: blocked with
  neither kind fails; both kinds fails; dead-route without `reopen_if` fails;
  reopen without `--reopen` fails; the core skips dead-route tickets.

## 10. The Author through `/author:inbox`

**Today** `author/scripts/next.py` plans a batch from the agenda's roadmap items and
the tickets to the instance together, and `author:next` is how the Author runs its
own work. The Author has no `inbox`.

**Amendment (Roey, 2026-09-30): the roadmap is dropped.** The first version of this
section kept `Drafts/roadmap.md` (R-NNNN items, `inbox.py sync` / `file` / `mark` /
`add`) as a second queue that was filed into the board. That was a mistake: two queues
with a sync between them. **The board is the Author's only queue.** There is no roadmap
file, no `R-NNNN` id, no item store and no sync. The text below is the design as
amended.

**Design.**
- **`/author:inbox` replaces `/author:next`.** Same interface as the other roles:
  the shared core (section 8) plus the Author's routing table.
- **Work items are tickets.** The Author's own work is a ticket from the author
  instance to itself (allowed by the chain gate: same role) of kind `write`, `apply`,
  `copy`, `figure`, `build`, `notation` or `sweep`; an ask that leaves the Author is a
  ticket to the Expert (`verify`, `cite`, `referee`; `research` with `final_to:
  researcher` or `scientist` for a proof or an experiment). Every such ticket carries the
  claim in `refs` and, in `agenda`, the claim id of the agenda entry it serves (its
  position in the paper). They are filed with `board.py new` / `tickets_create`; the
  margin-notes skill files one per note, and `agenda.py gaps --file` files one per
  agenda gap through `board.create_ticket` (no separate item store, no `inbox.py file`).
  An agenda entry is a gap only while no non-terminal ticket to or from the Author
  carries its `agenda`, so filing is idempotent: the same gap twice is one ticket. A
  `verify` for an entry whose own inputs are below their required status is held, as
  before.
- **Dependencies are ticket waits.** A ticket that must wait is `blocked` with
  `waiting_on` (other tickets, or `human` for a decision only Roey can make). The
  Author's inbox offers a blocked ticket again (a "released" row) once every ticket it
  waits on is `delivered` or terminal; a wait on an agenda entry reaching a status is
  not filed until it does.
- **Returned tickets land.** A ticket the Author filed to another role that comes back
  `delivered` is a landing row (ahead of the open tickets, after those in progress); the
  Author closes it after landing.
- **Routing by kind** (the existing `TICKET_KIND_ROUTES`, extended): write to
  math-writer, apply and copy to math-editor, figure to figure-maker, build to
  tex-engineer, notation to notation-auditor, a delivered verify or cite ticket landed
  by math-editor, a returned experiment or proof landed by math-writer. A ticket of no
  known kind is `human` (asked, never guessed).
- **Agenda, milestones, status** are computed from the registry's claim statuses and
  the tickets attached to each entry (`agenda.py show`, `milestones`), not from items.
- **Sweep on every run.** Before it takes tickets, `/author:inbox` runs the machine
  note sweep (`note-sweeper`, as `/author:sweep` does), so answered notes are folded
  into the thread of their ticket first and open ones are left. `/author:sweep` stays
  as a standalone entry. The sweep counts against no item cap and is reported first.
- **Kept:** `agenda`, `audit-notation`, `notes`, `presync`, `status`, `sweep`.
  **Retired:** `next` (its planning moves into the inbox wrapper; `author:status`
  points at `/author:inbox --all`).
- **Migration of an existing roadmap.** `author/scripts/agenda_migrate.py` is a
  one-shot converter from a `Drafts/roadmap.md` to tickets: dry run by default, `--apply`
  files them, idempotent, and the roadmap file is only read; the human archives it
  afterwards. `paths.roadmap` is no longer required in `academy.json`; an old config
  that still has the key validates and the key is ignored.
- **Tests:** `author/tests/test_next.py` is ported to the inbox (tickets only); a new
  `author/tests/test_plugin.py` lists the Author's skills; the generated skill
  tables in `author/README.md` are regenerated with `skill_index.py`. Added: no code
  path reads or writes a roadmap; gap filing is idempotent; the converter is dry-run by
  default and maps items to tickets; an old config with a `roadmap` key validates.
