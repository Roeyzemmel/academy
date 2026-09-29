# Routing, and what the tier pass taught

`/author:next` replaces `/paper:tier`. The choice of items is computed
(`scripts/next.py`, tested in `tests/test_next.py`); this file explains the routing
table the script implements, and keeps the lessons of the tier pass that still bind.

## The routing table (`next.py`)

| Item | Action | Who |
|---|---|---|
| `[apply]`, mechanical `[write]` | agent | `math-editor` |
| `[write]` (prose, definitions, a write-up from a source) | agent | `math-writer`; `route: figure-maker` on the item for an illustration |
| `[figure]` | agent | `figure-maker` (opus when the picture carries data) |
| `[build]` | agent | `tex-engineer` |
| `[notation]` | agent | `notation-auditor` |
| `[sweep]` | agent | `note-sweeper` |
| `[lead]` | ticket `research`, `final_to: researcher` | the Expert instance (research-intake prepares it and relays it to the Researcher) |
| `[verify]` | ticket `verify` | the Expert instance (review-chair, two rigor-reviewer runs) |
| `[cite]` | ticket `cite` | the Expert instance (librarian) |
| `[experiment]` | ticket `research`, `final_to: scientist` | the Expert instance (relayed to the Researcher, whose experiment-spec files it to the Scientist) |
| `[referee]` | ticket `referee` | the Expert instance (referee) |
| ticketed item, ticket `delivered`/`closed` | land | `math-writer` (lead, experiment), `math-editor` (verify, cite), `/author:notes` (referee) |
| inbox ticket `build` / `figure` / `notation` | agent | `tex-engineer` / `figure-maker` / `notation-auditor` |
| inbox ticket of another kind | triage | Roey decides, in the main session |

Delivered `note` tickets from the Expert land with math-writer as roadmap items.

An item's `route:` field overrides the agent. Where several instances of a role share
the domain, the first by name is taken and the plan says so in `note`; re-route by
filing the ticket by hand with `board.py new`.

## Ordering

1. Ready means every `depends_on` is met: an item `done`; a ticket `delivered` or
   `closed`; an agenda entry (or claim id) at or above its `required` status.
2. A `[verify]` item also waits for the inputs of its agenda entry whose status is
   known (a verdict on top of unproved inputs is only a verdict modulo them). Inputs
   with no registry record do not hold it; `/author:agenda gaps` lists them.
3. Sorted by the earliest agenda position the item unblocks: its own entry or any entry
   resting on it, transitively. A lemma late in the paper that the main theorem uses
   goes first. Then priority, then file order (roadmap items before inbox tickets).
   `global` items sort after every attached one.
4. At most `budget.itemsPerRun` (never more than 3).

Status ranks for "at or above": open < conjectured < sketch = supported <
proved-modulo < proved. `refuted` meets only a `refuted` requirement.

## Lessons kept from the tier pass

- **Nothing is proved that the author has not asked for or sketched**, and the Author
  never proves anything itself: a `[lead]` is a `research` ticket to the Expert with `final_to: researcher`, relayed
  to the Researcher, whose `prove` flow commissions the proof and sends it for review. The old tier's
  `top-researcher` inside the paper repo is gone.
- **No verification inside a run.** A writer files a `[verify]` item for every argument
  that could be recoloured; `/author:next` turns it into a ticket; the Expert runs the
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
