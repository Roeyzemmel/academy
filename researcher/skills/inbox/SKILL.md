---
name: inbox
description: 'Work this Researcher''s board inbox: take at most three open or accepted tickets and route each by kind (prove, review-experiment, settle, generalize, decision, question). Use for "/researcher:inbox" or when SessionStart reports tickets.'
---

# The Researcher inbox

## Scope notes

- Tickets are taken in order of priority, then agenda position, then id (`inbox.py`).

`$ARGUMENTS` is empty (take the next items) or `--all` (list only). Scripts: `$R`,
`$A` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. The ticket lifecycle is
docs/protocol.md section 4; the budget rules are `academy/references/budget.md` — at
most `budget.itemsPerRun` tickets, one after another, each within its own
`budget.runs` and `budget.max_model`.

1. **Take.** `py $R/inbox.py` (or `--all` to list without taking). It prints the
   tickets to handle and the route of each, and how many more wait.
2. **For each ticket, in order:**
   - Read it (`$A/board.py show T-NNNN`). A ticket outside this role's work — asking for
     prose in a paper, a citation card, an experiment script — is `rejected` with the
     reason and the instance it belongs to (`$A/board.py transition T-NNNN rejected
     --reason "..." --as <instance>`).
   - Move it `accepted` (`--as <instance>`), then run its route with the ticket id:
     `/researcher:prove`, `/researcher:review-experiment` (or `/researcher:settle`
     when the report lists candidates), `/researcher:generalize`,
     `/researcher:explore` for a `question`, `claim-keeper` for a `decision` (a status
     proposal), and `lead-researcher` for everything else.
   - If the work needs more runs or a heavier model than `budget` allows, move it
     `blocked` with `--waiting-on human` and a thread line asking for more budget.
   - The route delivers the ticket with a one-line result. Check it did before taking
     the next.
3. **Stop** after the last taken ticket, or at once on a usage or rate-limit error:
   record what was and was not done in the ticket thread and report. No relaunch.
4. **Report**: each ticket, its route and outcome (delivered / blocked / rejected),
   and how many remain.

Writing a result or a decision starts no further work; the sender picks it up in its
own next run.
