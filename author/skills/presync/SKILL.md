---
name: presync
description: 'The bundle to run at a milestone: checker, note sweep, notation audit, literature-watch and referee tickets, clean build, one-page summary. Use when the author is about to share, sync (Overleaf) or send the paper, or reaches an agenda milestone.'
---

# /author:presync

Run at a milestone (`/author:agenda milestones`). The passes run in this order because
each consumes the previous one's output. Budget: each pass is its own single run,
serially (`${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md`). Scripts: `$S` =
`${CLAUDE_PLUGIN_ROOT}/scripts`.

1. **The checker, strict**: `py $S/check_paper.py --strict` from the home. Relay it;
   fix nothing yet.
2. **`/author:sweep`**: clears machine notes whose question is answered. First, because
   every later pass reads the margins.
3. **`/author:audit-notation`**: before the referee, so the referee does not report
   clashes already known.
4. **The aesthetic pass** (`${CLAUDE_PLUGIN_ROOT}/references/aesthetic-vision.md`): for
   each section changed since the last sync (at most three, the rest named in the
   summary), one `math-editor` run in **vision mode** against `Drafts/vision.md`, read-only,
   briefed with the pinned list (`py $S/pinned.py`). File its proposals as tickets:
   Filing, as the role cut says (`${CLAUDE_PLUGIN_ROOT}/../academy/references/roster-rules.md`,
   "Role cut"): an `author` proposal is a `write` or `apply` ticket to this Author; a
   `researcher` one (a different statement, a unifying lemma, a cleaner definition) is a
   `research` ticket to the Expert with `final_to: researcher`, which must pass
   `routes.check_filed`; an `expert` one is a `notation` ticket; a `human` one is a line
   in the report. A proposal touching a pinned statement (`py $S/pinned.py`) is never an
   Author ticket. Skip a proposal already ticketed. Nothing is edited during the pass.
5. **Literature watch, as a ticket.** The watch belongs to the Expert. File one ticket
   with the MCP tool `tickets_create` (or `py <academy>/scripts/board.py new --as
   <instance>`): `to` the Expert instance of this paper's domain, `kind: other`,
   title "Literature watch before <milestone>", ask "Run the literature watch for this
   paper's keywords and report hits since the last watch", `agenda: global`.
6. **Referee, as a ticket.** `kind: referee`, to the same Expert instance, ask "Cold
   referee report on the built PDF at <home>/<build.dir>/<main>.pdf", `refs` naming the
   milestone's entries; the referee checks the paper against `Drafts/vision.md` too.
   The referee packet comes back later; `/author:notes referee
   P-NNNN` then files its points.
7. **Provenance markers** (only when the home sets `author.provenance`; the mechanism is
   `${CLAUDE_PLUGIN_ROOT}/skills/paper-method/references/draft-colours.md`): list every
   block and span carrying the marker (`git grep` for its environment and command), with
   its `%% added: <kind>` tag and section. Remove none: the list goes in the summary as
   a proposal to the marker's `removedBy` (the human), who removes them once the round
   is accepted.
8. **A clean build and the checker once more.** Launch `tex-engineer` only if the build
   is not clean. The PDF the coauthors receive is the one that was checked.

If a pass fails or comes back blocked, say so and continue with the rest.

## The summary (in the chat, not a file)

- **What changed** since the last sync, by section, one line each (from the tickets
  delivered or closed since then).
- **What the coauthors are asked for**: every ticket parked on `human` (`py $S/inbox.py --all`) and every open machine
  note, grouped by section, each quoted in its own words.
- **What is not established**: every agenda entry below its required status that the
  introduction mentions, with what it waits for (`py $S/agenda.py gaps` and
  `py $S/inbox.py --all`).
- **Milestone progress**: `py $S/agenda.py milestones`.
- **The vision**: the aesthetic pass's proposals, each with its ticket id or "for
  the human", and the sections not reviewed this time.
- **Added since the last round**: the provenance markers, by section and kind, proposed
  for removal (none when the home sets no `author.provenance`).
- **Tickets filed**: the literature-watch and referee ticket ids; their results arrive
  as packets.
- **The build**: exit status, the `??` count, the warnings and which are the accepted
  baseline.

Close with the one sentence that matters: what a coauthor should read first. Never ask
questions.
