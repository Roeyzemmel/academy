# Routing, and what the tier pass taught

`/author:inbox` (which replaced `/author:next`, and before it `/paper:tier`) chooses its
tickets by script (`scripts/inbox.py` over the shared inbox core, tested in
`tests/test_inbox.py`); this file explains the routing the scripts implement
(`scripts/routes.py`), and keeps the lessons of the tier pass that still bind.

## The routing table (`inbox.py`, `routes.py`)

The board is the Author's only queue; there is no roadmap. A work item is a ticket,
filed with `board.py new` / `tickets_create` (`--agenda <ns>:<label>` gives its place in
the paper, `--refs` the claim), or from an agenda gap with `agenda.py gaps --file`.

Generated from `scripts/routes.py` (`py scripts/routes.py --sync <this file>`; a test
compares them), the single source of which kind goes to which agent:

Tickets addressed to the Author, by kind:

<!-- routes:kinds -->
| kind | how | target | why |
|---|---|---|---|
| `write` | agent | `math-writer` | prose, definitions, a write-up from a source |
| `apply` | agent | `math-editor` | the edit is already decided |
| `copy` | agent | `math-editor` | copy-edit a settled section; no mathematics |
| `figure` | agent | `figure-maker` | an illustration |
| `build` | agent | `tex-engineer` | toolchain or build repair |
| `notation` | agent | `notation-auditor` | a notation decision or clash |
| `sweep` | agent | `note-sweeper` | the machine-note sweep |
| `note` | agent | `math-writer` | fold the literature result into the paper |
| any other kind | human | `human` | asked, never guessed |
<!-- /routes:kinds -->

The asks the Author files (`agenda.py gaps --file`):

<!-- routes:out -->
| ask | kind | to | final_to |
|---|---|---|---|
| `lead` | `research` | expert | `researcher` |
| `verify` | `verify` | expert | - |
| `cite` | `cite` | expert | - |
| `experiment` | `research` | expert | `scientist` |
| `referee` | `referee` | expert | - |
<!-- /routes:out -->

A returned ticket (this Author filed it elsewhere, it came back `delivered`) is landed by:

<!-- routes:land -->
| returned kind | how | target |
|---|---|---|
| `cite` | agent | `math-editor` |
| `experiment` | agent | `math-writer` |
| `prove` | agent | `math-writer` |
| `research` | agent | `math-writer` |
| `verify` | agent | `math-editor` |
| `referee` | skill | `author:notes` |
| `(any other)` | agent | `math-editor` |
<!-- /routes:land -->

How the work is filed: a work item for the Author itself (kinds `write`, `apply`, `copy`,
`figure`, `build`, `notation`, `sweep`) is a ticket to this Author; an ask that leaves it
(the second table) is a ticket to the Expert, which relays a `research` ticket to the
Researcher or the Scientist by `final_to` (`lead`: the Researcher's `prove` flow;
`experiment`: the Researcher's experiment-spec files it to the Scientist). A blocked
ticket to the Author whose `waiting_on` tickets are all `delivered` is offered again as a
released row (move `blocked -> accepted`, then route by kind). `figure-maker` runs on opus
when the picture carries data.

Where several instances of a role share the domain, `agenda.py gaps --file` takes the
first by name and says so; to choose, file the ticket by hand with `board.py new`.
Tickets carry the claim in `refs`, and in `agenda` the entry's qualified label
(`<ns>:<label>`). Gap filing is idempotent: an agenda entry with a non-terminal ticket
attached (by `agenda`) is not a gap, so the same gap is never ticketed twice. A gap no
ticket can close is **held** and reported, never filed: a refuted claim (nobody verifies
or proves it), a claim with no registry record (the human creates it with `claims_new`).

## Ordering

1. A ticket that must wait for another is `blocked` with `waiting_on: [T-NNNN, ...]`
   (or `human`). When every ticket it waits on is `delivered` or `closed`, the inbox
   offers it again as a released row. A wait on a `rejected` or `cancelled` ticket (or on
   one that is not on the board) never ends by itself: the ticket stays blocked and the
   inbox prints a NOTE; decide whether to re-file, repoint or reject it. A wait on an agenda entry or a claim reaching a
   status is not a ticket wait: say it in the ticket's ask, and file the ticket when the
   status is reached.
2. `agenda.py gaps --file` holds a `verify` for an entry whose own inputs (its agenda
   `depends_on`, where the status is known) are not at their required status: a verdict
   on top of unproved inputs is only a verdict modulo them. Inputs with no registry
   record do not hold it; `agenda.py gaps` lists them.
3. The inbox takes tickets in progress first (unfinished work is resumed), then returned
   tickets to land, then the rest ordered by the earliest agenda position the ticket
   unblocks: its own entry or any entry resting on it, transitively (a lemma late in the
   paper that the main theorem uses goes first); then priority, then id. `global` and
   unattached tickets sort after every attached one. This puts the position before the
   priority, the Author's precedence; the other roles' inboxes take priority first.
4. At most `budget.itemsPerRun` (never more than 3). The sweep counts against no cap.

Status ranks for "at or above": open < conjectured < sketch = supported <
proved-modulo < proved. `refuted` meets only a `refuted` requirement.

## Lessons kept from the tier pass

- **Nothing is proved that the author has not asked for or sketched**, and the Author
  never proves anything itself: a a `lead` is a `research` ticket to the Expert with `final_to: researcher`, relayed
  to the Researcher, whose `prove` flow commissions the proof and sends it for review. The old tier's
  `top-researcher` inside the paper repo is gone.
- **No verification inside a run.** A writer files a `verify` ticket (to the Expert) for
  every argument that could be recoloured; the Expert runs the pair; math-editor lands
  the verdict.
- **The lightest agent that can do the work.** `apply` never goes through a
  heavyweight agent.
- **Short briefs.** Point at the ticket id; the agent reads the files. Pasting the
  ticket or tex into a brief is paid again on every turn.
- **Serial with a checkpoint after each item**, so no agent is told about siblings and
  every agent may build and run the checker itself.
- **The session-limit stop** (budget.md rule 4). The Tier 3d run turned one limit
  failure into eighteen by relaunching into an exhausted quota.
- **A capped agent is not a failed agent**: record its partial result, do not raise the
  cap, go on.
- **Grouping** is no longer a judgement call made per run: tickets that stand or fall
  together say so with `waiting_on`. Milestones (in the agenda) replace tier headings
  where a real boundary is needed.
