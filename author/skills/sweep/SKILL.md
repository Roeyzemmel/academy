---
name: sweep
description: 'The machine-note sweep: a script plans it (changed files, cached verdicts, notes by kind); retire ended await notes, fold answered ones into their ticket''s thread and delete them, report counts. Use after /author:inbox runs, before /author:presync, or when margins are full.'
---

# /author:sweep

Machine notes accumulate: every judgement call left one, and after a few runs the
margins carry notes whose question has since been answered. The sweep is the garbage
collection.

First the plan, a script (`$SW` = `py ${CLAUDE_PLUGIN_ROOT}/scripts/sweep.py`, from the
home): `$SW plan`. It reads only the tex files changed since the last complete sweep and
skips every note whose cached verdict still holds, and sorts the rest by kind (#110):
`await` notes whose ticket ended with a result are retired, `prov` notes are moved into
the record, `human` notes are listed for the human, the rest are judged. Its first line
is `sweep: todo N (...)`. **`todo 0`: relay that line and stop**; nothing is launched (the
plan has recorded itself). A plan that exits non-zero: relay its error and stop; the
sweeper is not launched without a plan. A cached verdict expires after
`author.notes.maxAge` days (default 14), so every pass (the inbox, presync, the weekly
run) re-judges the oldest ones in turn. `$ARGUMENTS` may add `--full` (read every tex file:
after an Overleaf sync, or when the state was lost) or `--max-age DAYS` (override).
A plan line ending in `WARNING: ...` says the last sweep never ran `record`: relay it.

Otherwise launch `note-sweeper` (`subagent_type: author:note-sweeper`). It carries the
deletion rule, where an answer can live, and the mechanics, works the plan and records
it (`$SW record`). The main session briefs and relays. Budget: one agent, one run
(`${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md`).

## The brief

> Sweep the machine notes of this paper: work the plan of `sweep.py plan<the flags
> given>` and record it. <The tickets closed since the last sweep, by id, if known; any
> replies the human left, and where.> Apply your deletion rule exactly:
> a note goes only when its question has a durable recorded answer, and the answer is
> recorded in a ticket's thread before the note is deleted.

Add nothing else.

## Afterwards

Relay the agent's table, its list of notes left open and the plan's `human` list (the
lists the human reads), and the record line (whether the recorded commit moved). If the
sweep deleted a note whose answer was a pair of verdicts, check that the recolouring
it implies is on its way: a landed `verify` ticket, or an open `verify` ticket (the
sweep does not recolour). Never ask questions.
