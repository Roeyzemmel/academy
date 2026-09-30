# Routing, and what the tier pass taught

`/author:inbox` (which replaced `/author:next`, and before it `/paper:tier`) chooses its
tickets by script (`scripts/inbox.py` over the shared inbox core, tested in
`tests/test_inbox.py`); this file explains the routing the scripts implement
(`scripts/routes.py`), and keeps the lessons of the tier pass that still bind.

## The routing table (`inbox.py`, `routes.py`)

Every roadmap item is filed once (`inbox.py sync`, or `--sync`), and the board is the
single queue; the roadmap stays the place the human edits.

| Item | Filed as | Who works it |
|---|---|---|
| `[write]` (prose, definitions, a write-up from a source) | self-ticket, kind `write` | `math-writer` |
| `[apply]`, mechanical `[write]`, `[copy]` | self-ticket, kind `apply` (or `copy`) | `math-editor` |
| `[figure]` | self-ticket, kind `figure` | `figure-maker` (opus when the picture carries data) |
| `[build]` | self-ticket, kind `build` | `tex-engineer` |
| `[notation]` | self-ticket, kind `notation` | `notation-auditor` |
| `[sweep]` | self-ticket, kind `sweep` | `note-sweeper` |
| `[lead]` | ticket `research`, `final_to: researcher`, to the Expert | the Expert instance (research-intake prepares it and relays it to the Researcher) |
| `[verify]` | ticket `verify` to the Expert | review-chair, two rigor-reviewer runs |
| `[cite]` | ticket `cite` to the Expert | the librarian |
| `[experiment]` | ticket `research`, `final_to: scientist`, to the Expert | relayed to the Researcher, whose experiment-spec files it to the Scientist |
| `[referee]` | ticket `referee` to the Expert | the referee |
| ticketed item, ticket `delivered`/`closed` (a return row) | land | `math-writer` (lead, experiment), `math-editor` (verify, cite), `/author:notes` (referee) |
| ticket to the Author of kind `build` / `figure` / `notation` / `note` | routed by kind | `tex-engineer` / `figure-maker` / `notation-auditor` / `math-writer` |
| ticket of any other kind | `human` | Roey decides, in the main session; a route is never guessed |

An item's `route:` field overrides the agent: the self-ticket takes the kind that routes
back to that agent (`math-writer` `write`, `math-editor` `apply`, `figure-maker`
`figure`, `tex-engineer` `build`, `notation-auditor` `notation`, `note-sweeper`
`sweep`). Where several instances of a role share the domain, the first by name is
taken and the plan says so in `note`; re-route by filing the ticket by hand with
`board.py new`. Self-tickets carry the item id (`R-NNNN`) and the claim in `refs`, so
filing is idempotent: an item already ticketed, or whose ticket is on the board, is
never ticketed twice.

## Ordering

1. Ready (fit to be filed) means every `depends_on` is met: an item `done`; a ticket
   `delivered` or `closed`; an agenda entry (or claim id) at or above its `required`
   status.
2. A `[verify]` item also waits for the inputs of its agenda entry whose status is
   known (a verdict on top of unproved inputs is only a verdict modulo them). Inputs
   with no registry record do not hold it; `/author:agenda gaps` lists them.
3. The inbox takes tickets in progress first (unfinished work is resumed), then returned
   tickets to land, then the rest ordered by the earliest agenda position the ticket
   unblocks: its own entry or any entry resting on it, transitively (a lemma late in the
   paper that the main theorem uses goes first); then priority, then id. `global` and
   unattached tickets sort after every attached one. This puts the position before the
   priority, the Author's precedence; the other roles' inboxes take priority first.
4. At most `budget.itemsPerRun` (never more than 3). The sweep and the filing count
   against no cap.

Status ranks for "at or above": open < conjectured < sketch = supported <
proved-modulo < proved. `refuted` meets only a `refuted` requirement.

## Lessons kept from the tier pass

- **Nothing is proved that the author has not asked for or sketched**, and the Author
  never proves anything itself: a `[lead]` is a `research` ticket to the Expert with `final_to: researcher`, relayed
  to the Researcher, whose `prove` flow commissions the proof and sends it for review. The old tier's
  `top-researcher` inside the paper repo is gone.
- **No verification inside a run.** A writer files a `[verify]` item for every argument
  that could be recoloured; `/author:inbox` turns it into a ticket; the Expert runs the
  pair; math-editor lands the verdict. The old roadmap's `## Verification queue` is
  exactly these items.
- **The lightest agent that can do the work.** `[apply]` never goes through a
  heavyweight agent.
- **Short briefs.** Point at the item or ticket id; the agent reads the files. Pasting
  the roadmap or tex into a brief is paid again on every turn.
- **Serial with a checkpoint after each item**, so no agent is told about siblings and
  every agent may build and run the checker itself.
- **The session-limit stop** (budget.md rule 4). The Tier 3d run turned one limit
  failure into eighteen by relaunching into an exhausted quota.
- **A capped agent is not a failed agent**: record its partial result, do not raise the
  cap, go on.
- **Grouping** is no longer a judgement call made per run: items that stand or fall
  together say so with `depends_on`. Milestones (in the agenda) replace tier headings
  where a real boundary is needed.
