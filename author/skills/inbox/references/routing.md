# Routing, and what the tier pass taught

`/author:inbox` (which replaced `/author:next`, and before it `/paper:tier`) chooses its
tickets by script (`scripts/inbox.py` over the shared inbox core, tested in
`tests/test_inbox.py`); this file explains the routing the scripts implement
(`scripts/routes.py`), and keeps the lessons of the tier pass that still bind.

## The routing table (`inbox.py`, `routes.py`)

The board is the Author's only queue; there is no roadmap. A work item is a ticket,
filed with `board.py new` / `tickets_create` (`--agenda <claim id>` gives its place in
the paper, `--refs` the claim), or from an agenda gap with `agenda.py gaps --file`.

| Work | Filed as | Who works it |
|---|---|---|
| `write` (prose, definitions, a write-up from a source) | ticket to the Author itself, kind `write` | `math-writer` |
| `apply`, mechanical `write`, `copy` | ticket to the Author itself, kind `apply` (or `copy`) | `math-editor` |
| `figure` | ticket to the Author itself, kind `figure` | `figure-maker` (opus when the picture carries data) |
| `build` | ticket to the Author itself, kind `build` | `tex-engineer` |
| `notation` | ticket to the Author itself, kind `notation` | `notation-auditor` |
| `sweep` | ticket to the Author itself, kind `sweep` | `note-sweeper` |
| `lead` (ask for a proof) | ticket `research`, `final_to: researcher`, to the Expert | the Expert instance (research-intake prepares it and relays it to the Researcher) |
| `verify` | ticket `verify` to the Expert | review-chair, two rigor-reviewer runs |
| `cite` | ticket `cite` to the Expert | the librarian |
| `experiment` (ask for a run) | ticket `research`, `final_to: scientist`, to the Expert | relayed to the Researcher, whose experiment-spec files it to the Scientist |
| `referee` | ticket `referee` to the Expert | the referee |
| a ticket this Author filed to another role, now `delivered` (a return row) | land, then the Author closes it | `math-writer` (`research`: a proof or an experiment), `math-editor` (`verify`, `cite`), `/author:notes` (`referee`) |
| a blocked ticket to the Author whose `waiting_on` tickets are all back (a released row) | move `blocked -> accepted`, then route by kind | as its kind |
| ticket to the Author of kind `build` / `figure` / `notation` / `note` | routed by kind | `tex-engineer` / `figure-maker` / `notation-auditor` / `math-writer` |
| ticket of any other kind | `human` | Roey decides, in the main session; a route is never guessed |

The kind picks the agent (`math-writer` `write`, `math-editor` `apply`, `figure-maker`
`figure`, `tex-engineer` `build`, `notation-auditor` `notation`, `note-sweeper`
`sweep`). Where several instances of a role share the domain, `agenda.py gaps --file`
takes the first by name and says so; to choose, file the ticket by hand with
`board.py new`. Tickets carry the claim in `refs` and in `agenda`. Gap filing is
idempotent: an agenda entry with a non-terminal ticket attached (by `agenda`) is not a
gap, so the same gap is never ticketed twice.

## Ordering

1. A ticket that must wait for another is `blocked` with `waiting_on: [T-NNNN, ...]`
   (or `human`). When every ticket it waits on is `delivered` or terminal, the inbox
   offers it again as a released row. A wait on an agenda entry or a claim reaching a
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
