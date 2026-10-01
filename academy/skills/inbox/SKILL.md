---
name: inbox
description: 'Work every instance''s board inbox in one run, in a fixed order (Author, Expert, Researcher, Scientist), one ticket at a time under the 3-item cap; with --campaign TARGET only the tickets tagged for that campaign. Use for "work all the inboxes", "run the board".'
---

# /academy:inbox

The cross-role inbox. Each role keeps its own `/author:inbox`, `/expert:inbox`,
`/researcher:inbox` and `/scientist:inbox`; this skill runs them in turn and adds no
routing of its own. `/academy:desk` is unchanged. The shared selection is the academy
library's `inbox_core` (`docs/protocol.md` section 4; every role's `scripts/inbox.py` is a
thin wrapper over it). Budget rules: `references/budget.md` (rule 1: three items, rule 2:
serial, rule 4: a limit error ends the run).

`$ARGUMENTS`: empty, `--n N` (fewer than 3), `--all` (list only, take nothing), or
`--campaign <target-id>` (only tickets carrying `campaign: <target-id>`, section 4.1 of
the campaign design).

## 1. Order the instances

Read `workspace.json` (`workspace_get`). The roles go in this fixed order: **Author,
Expert, Researcher, Scientist**; instances of one role by name. Nothing is taken from an
instance that is not in `workspace.json`.

## 2. Look, instance by instance

For each instance, in order, run its role's script from any directory:

```
py "${CLAUDE_PLUGIN_ROOT}/../<role>/scripts/inbox.py" --instance <name> --json [--n N] [--campaign T]
```

(`~/.claude/skills/<role>/scripts/inbox.py` if the variable is not expanded.) Each row has
`id`, `kind`, `priority`, `return`, `route: {how, target, why}` and `over_budget`; rows
come already ordered: tickets in progress first (resume), then return legs, then `open` and
`accepted` by priority, agenda position, id. Dead-route and pending blocked tickets are
never listed. With `--all`, print each instance's list and stop.

## 3. Take, one at a time, under one cap

Count the cap over the **whole run**, not per instance: at most 3 tickets, or `--n`
(`budget.itemsPerRun` of the instance may lower it). With `--campaign` each instance's
listing is not cut at three and the campaign's own caps apply (`references/budget.md`,
"Campaigns"). Take the first row of the first instance that has one; "first" is per
instance: in-progress first is the order inside one instance's list, and the instances
keep their fixed order. Run the row as that role's inbox skill says: follow its step 2
with the row's route (`/author:inbox`, `/expert:inbox`, `/researcher:inbox` or
`/scientist:inbox`), in the session or subagent that skill names, never as another role.
An Author instance sweeps first (`/author:inbox` step 1) and this sweep counts against no
cap.

**Checkpoint before the next ticket** (serial, `budget.md` rule 2). The role skill's own
step already ends with `py <role plugin>/scripts/inbox.py --check T-NNNN`: that run
counts; do not run `--check` again here (a finished ticket's `--check` also runs the
workspace's `scripts/ship.py checkpoint`, `docs/protocol.md` section 4, so a second run
would checkpoint twice). Read its exit code: exit 0 means delivered,
blocked with its reason or rejected. Exit 3 means unfinished: report it, do not
redispatch it in this run, and take nothing more from that instance while it is
unfinished (it comes first next run). Then take the next row. Tickets a role files
while running (a relay, a child) are picked up by the run that reaches their receiver;
do not restart from the top.

**Stop at once** on a usage or rate-limit error: record in the ticket thread what was and
was not done, launch nothing further, and report (`budget.md` rule 4).

## 4. Report

One line per ticket taken: instance, id, route, outcome (delivered, blocked with its
reason, rejected, unfinished). Then per instance how many tickets remain, and anything
parked on Roey (`/academy:decide`).
