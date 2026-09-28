---
name: presync
description: The bundle to run at a milestone — before a coauthor round, an Overleaf sync or a submission — the checker, the note sweep, the notation audit, a literature-watch ticket and a referee ticket to the Expert, a clean build, and a one-page summary of what the coauthors are being handed. Use when the author says they are about to share, sync or send the paper, or a milestone in the agenda is reached.
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
4. **Literature watch, as a ticket.** The watch belongs to the Expert. File one ticket
   with the MCP tool `tickets_create` (or `py <academy>/scripts/board.py new --as
   <instance>`): `to` the Expert instance of this paper's domain, `kind: other`,
   title "Literature watch before <milestone>", ask "Run the literature watch for this
   paper's keywords and report hits since the last watch", `agenda: global`.
5. **Referee, as a ticket.** `kind: referee`, to the same Expert instance, ask "Cold
   referee report on the built PDF at <home>/<build.dir>/<main>.pdf", `refs` naming the
   milestone's entries. The referee packet comes back later; `/author:notes referee
   P-NNNN` then files its points.
6. **A clean build and the checker once more.** Launch `tex-engineer` only if the build
   is not clean. The PDF the coauthors receive is the one that was checked.

If a pass fails or comes back blocked, say so and continue with the rest.

## The summary (in the chat, not a file)

- **What changed** since the last sync, by section, one line each (from the roadmap
  items marked done since then).
- **What the coauthors are asked for**: every `needs-human` item and every open machine
  note, grouped by section, each quoted in its own words.
- **What is not established**: every agenda entry below its required status that the
  introduction mentions, with what it waits for (`py $S/agenda.py gaps` and
  `py $S/next.py plan`).
- **Milestone progress**: `py $S/agenda.py milestones`.
- **Tickets filed**: the literature-watch and referee ticket ids; their results arrive
  as packets.
- **The build**: exit status, the `??` count, the warnings and which are the accepted
  baseline.

Close with the one sentence that matters: what a coauthor should read first. Never ask
questions.
