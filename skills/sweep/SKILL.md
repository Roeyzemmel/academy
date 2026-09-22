---
name: sweep
description: The machine-note sweep, run once per tier — inventory every \Claude{…} note in sections/, decide from the roadmap, the author's later notes and the ledgers whether each is answered (fold the answer into the roadmap item and delete the note) or still open (leave it), shrink the "Open from this tier" paragraphs, and report counts per section before and after. Use after finishing a tier, or when the margins have filled up with machine notes.
---

# Sweep the machine notes

Machine margin notes accumulate: every judgement call and unverified step left one
behind, and after two or three tiers the margins carry notes whose question the author
has since answered. The sweep is the garbage collection. Run it **once per tier**,
after `/paper:tier` closes.

Dispatch `note-sweeper` (`subagent_type: note-sweeper`). It carries the deletion rule,
the five places an answer can live, and the mechanics. The main session briefs and
relays.

## The brief

> Sweep the machine notes for this tier. The tier just closed is <N>; its items and its
> "Open from this tier" paragraph are in `Drafts/comment_roadmap.md`. <Any replies the
> author left since the last sweep, and where.> Apply your deletion rule exactly: a note
> goes only when its question has a durable recorded answer, and the answer is folded
> into the roadmap before the note is deleted.

Add nothing else. The agent knows the rest.

## What the main session does afterwards

Relay the agent's table and its list of notes left open — that list is the thing the
author reads. If the sweep deleted a note whose answer lived only in a verifier verdict,
check that the recolouring it implies was actually filed — a line in the roadmap's
`## Verification queue`, or a `[verify]` item; the sweep
does not recolour.

Never ask questions.
