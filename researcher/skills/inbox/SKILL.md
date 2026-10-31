---
name: inbox
description: 'Work this Researcher''s board inbox: take at most three open or accepted tickets, route each by kind (prove, review-experiment, settle, generalize, decision, question; relays; else lead-researcher). Use for "/researcher:inbox".'
---

# The Researcher's inbox

The inbox rules are code: `/academy:inbox`'s workflow (`<academy plugin>/workflows/inbox.js`,
docs/workflows.md) takes at most `budget.itemsPerRun` tickets (never more than 3), one at a
time, by the routes of `${CLAUDE_PLUGIN_ROOT}/scripts/routes.py`, with the `--check`
checkpoint after each, and makes every relay leg and its conclusion: a relay ticket ready
for its return leg (`blocked`, waiting only on tickets that are all `delivered` or terminal)
is closed by the script without the relay. Run from the Researcher home.

`$ARGUMENTS`: empty, `--n N`, `--all` (list only: `py ${CLAUDE_PLUGIN_ROOT}/scripts/inbox.py --all`
and stop), or ticket ids.

1. **Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/../academy/workflows/inbox.js`
   and `args: {root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>", only: ["<this instance>"], n: <N>, ids: [...]}`.
2. **Finish what it hands back**, as `/academy:inbox` section 2 says: a `for_main` ticket
   (prove, explore, generalize, review-experiment and settle's first leg run nested in the
   workflow. What can come back here: `/researcher:explore` for a claim with no falsifier
   yet, and, rarely, the falsifier tests the lead could not file, with the command in
   `to_file` and then the generalize workflow again with `mode: "deliver"`), then its
   `inbox.py --check T-NNNN`, then the workflow again with the cap lowered; `stopped` ends
   the run (a limit; `budget.md` rule 4).
3. **Report**: each ticket, its route and outcome, and how many remain. Never ask
   questions.

A ticket's `budget.max_model`, if present, is an advisory note and never blocks a route;
each agent runs on its agent file's model.
