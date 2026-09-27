---
name: presync
description: The bundle to run before a coauthor round, an Overleaf sync or a submission — checker, note sweep, notation audit, literature watch, cold referee report, full build — ending in a one-page summary of what the coauthors are being handed. Use when the author says they are about to share the paper, sync it, or send it out.
---

# Before handing the paper to someone

Six passes, in this order, because each consumes the previous one's output. The point is
that nobody opens the PDF and finds a margin full of answered questions, a symbol that
changed meaning two tiers ago, or a theorem the introduction promises and the body
sketches.

## The order, and why

1. **The paper checker**, `--strict`. Fast, mechanical, and it tells you whether the
   rest is worth running. Relay its output; do not fix anything yet.
2. **`/paper:sweep`** — clears machine notes whose question has been answered. Done
   first because every later pass reads the margins, and a stale note is noise in all of
   them.
3. **`/paper:audit-notation`** — the symbol-level sweep. Before the referee, so the
   referee is not reporting notation clashes that were already known.
4. **`/paper:litwatch`** — what appeared since the last watch. Before the referee only
   because a scooping paper changes what the introduction should claim.
5. **`/paper:referee`** — the cold whole-paper read, on the PDF the coauthors will get.
   Last, and slow; run it in the background while assembling the rest.
6. **A full build**, from clean, and the checker once more. The artifact the coauthors
   receive is the one that was checked.

Run 2 to 5 as their own passes, each in its subagent; do not inline their work here.
If one fails or comes back blocked, say so and continue with the rest — a blocked
notation audit is not a reason to skip the referee.

## The summary

The deliverable is one page in the chat, not a file, and it is what the author forwards:

- **What changed** since the last sync, by section, one line each.
- **What the coauthors are being asked for** — every `[needs Roey]` item and every open
  machine note, grouped by section, each with the question in its own words. This is the
  part they will actually act on, so quote rather than paraphrase.
- **What is not established** — every statement still blue or red that the introduction
  mentions, and what it is waiting for (a verifier, an experiment, a decision).
- **The referee's judgement findings**, verbatim from its list, and separately the
  objective ones with a note that they can be applied mechanically.
- **Literature** — the watch's hits with their verdicts, or the explicit sentence that
  the window was covered and nothing landed.
- **The build** — exit status, the `??` count, the warnings and which are the accepted
  baseline.

Close with the one sentence that matters: what a coauthor should read first.

Never ask questions; if a pass could not run, say which and why in the summary.
