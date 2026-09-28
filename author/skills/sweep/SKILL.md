---
name: sweep
description: The machine-note sweep — inventory every machine margin note in the paper's tex, decide from the roadmap, the board, the human's later notes and the registry whether each is answered (fold the answer into a roadmap item and delete the note) or still open (leave it), and report counts per file before and after. Use after /author:next runs that closed items, before /author:presync, or when the margins have filled up with machine notes.
---

# /author:sweep

Machine notes accumulate: every judgement call left one, and after a few runs the
margins carry notes whose question has since been answered. The sweep is the garbage
collection.

Launch `note-sweeper` (`subagent_type: author:note-sweeper`). It carries the deletion
rule, where an answer can live, and the mechanics. The main session briefs and relays.
Budget: one agent, one run (`${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md`).

## The brief

> Sweep the machine notes of this paper. <The items closed since the last sweep, by id,
> if known; any replies the human left, and where.> Apply your deletion rule exactly:
> a note goes only when its question has a durable recorded answer, and the answer is
> recorded in the roadmap before the note is deleted.

Add nothing else.

## Afterwards

Relay the agent's table and its list of notes left open (the list Roey reads). If the
sweep deleted a note whose answer was a pair of verdicts, check that the recolouring
it implies is on its way: a landed `verify` ticket, or an open `[verify]` item (the
sweep does not recolour). Never ask questions.
