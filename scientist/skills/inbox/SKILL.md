---
name: inbox
description: 'Work the lab''s board inbox: take at most three open or accepted tickets and route each by kind (experiment/test, code, Upstream, question). Use for "work the inbox", "handle T-NNNN", or when SessionStart reports tickets.'
---

# The Scientist's inbox

The inbox rules are code: `/academy:inbox`'s workflow (`<academy plugin>/workflows/inbox.js`,
docs/workflows.md) takes at most `budget.itemsPerRun` tickets (never more than 3), one at a
time, by the routes of `${CLAUDE_PLUGIN_ROOT}/scripts/routes.py`, with the `--check`
checkpoint after each, and makes every relay leg and its conclusion. A `code` ticket runs
`developer`, then `test-engineer` on the diff (never the same agent), within `budget.runs`;
an "Upstream: ..." one runs `upstream-contributor`. Run from the lab home.

`$ARGUMENTS`: empty, `--n N`, `--all` (list only: `py ${CLAUDE_PLUGIN_ROOT}/scripts/inbox.py --all`
and stop), or ticket ids.

1. **Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/../academy/workflows/inbox.js`
   and `args: {root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>", only: ["<this instance>"], n: <N>, ids: [...]}`.
2. **Finish what it hands back**, as `/academy:inbox` section 2 says: a `for_main` ticket
   (an `experiment`, `test` or `question` ticket: `/scientist:experiment` with the ticket id,
   a `test` ticket testing the falsifier in the ask **first** and linking its report packet
   with `report.py file --ticket T-NNNN`; a ticket with no route: `AskUserQuestion`, the
   answer recorded in the thread), then its
   `inbox.py --check T-NNNN`, then the workflow again with the cap lowered; `stopped` ends
   the run (a limit; `budget.md` rule 4).
3. **Report**: each ticket, its route and outcome, and how many remain. Ask no question
   except for a ticket with no route.

A ticket's `budget.max_model`, if present, is an advisory note and never blocks a route;
each agent runs on its agent file's model.
