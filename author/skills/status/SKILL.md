---
name: status
description: 'The paper''s state at a glance: agenda progress, what /author:next would run, what waits on which ticket, tickets to this Author, checker summary. Read-only. Use for "where is the paper", "author status", "how far is the milestone".'
---

# /author:status

Read-only. Scripts: `$S` = `${CLAUDE_PLUGIN_ROOT}/scripts`; run from the Author home.

1. `py $S/agenda.py show`: entries with status and whether each meets its requirement
   (status column as last refreshed; say when `/author:agenda status` would refresh it).
2. `py $S/agenda.py milestones`.
3. `py $S/next.py plan`: what the next run would take, what waits and on what, and
   what is parked.
4. The inbox: `py ${CLAUDE_PLUGIN_ROOT}/../academy/scripts/board.py list --to <instance>`
   and the tickets this instance is waiting on:
   `board.py list --from <instance>` (`<instance>` from `.claude/academy.json`).
5. The checker: `py $S/check_paper.py --no-registry` and relay the counts lines only
   (statements, violations, warnings, BUILD).

Show each output as it is, under a one-line heading. Add at most three lines of your
own: the milestone closest to done, the item that would unblock the most, and anything
parked on Roey. Change nothing.
