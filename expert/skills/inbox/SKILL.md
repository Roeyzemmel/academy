---
name: inbox
description: 'Work the Expert''s inbox: take at most three open or accepted tickets, route each by kind (verify, cite, lookup, question, referee, notation; research or beyond-Expert tickets to a relay agent), logging each. Use for "work the expert inbox".'
---

# The Expert's inbox

The inbox rules are code: `/academy:inbox`'s workflow (`<academy plugin>/workflows/inbox.js`,
docs/workflows.md) takes at most `budget.itemsPerRun` tickets (never more than 3), one at a
time, by the routes of `${CLAUDE_PLUGIN_ROOT}/scripts/routes.py`, with the `--check`
checkpoint after each, and makes every relay leg and its conclusion: a relay ticket ready
for its return leg (`blocked`, waiting only on tickets that are all `delivered` or terminal)
is closed by the script without the relay. Run from the library home.

`$ARGUMENTS`: empty, `--n N`, `--all` (list only: `py ${CLAUDE_PLUGIN_ROOT}/scripts/inbox.py --all`
and stop), or ticket ids.

1. **Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/../academy/workflows/inbox.js`
   and `args: {root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>", only: ["<this instance>"], n: <N>, ids: [...]}`.
2. **Finish what it hands back**, as `/academy:inbox` section 2 says: a `for_main` ticket
   (a skill route, run here with the ticket id: `expert:cite`, `expert:referee`, `expert:domain`), then its
   `inbox.py --check T-NNNN`, then the workflow again with the cap lowered; `stopped` ends
   the run (a limit; `budget.md` rule 4).
3. **Report**: each ticket, its route and outcome, and how many remain. Never ask
   questions.

A ticket's `budget.max_model`, if present, is an advisory note and never blocks a route;
each agent runs on its agent file's model.
