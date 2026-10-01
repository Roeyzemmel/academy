---
name: inbox
description: 'Work this Researcher''s board inbox: take at most three open or accepted tickets, route each by kind (prove, review-experiment, settle, generalize, decision, question; final_to beyond the Researcher to a relay; else lead-researcher). Use for "/researcher:inbox".'
---

# The Researcher inbox

## Scope notes

- The shared inbox core orders them (`inbox.py` is its thin wrapper; routes are `scripts/routes.py`): tickets in progress first (resume), then return legs, then `open` and `accepted` by priority, agenda position, id. Dead-route and pending blocked tickets are never taken.

`$ARGUMENTS` is empty (take the next items), `--n N` (fewer than the limit) or `--all` (list only). Scripts: `$R`,
`$A` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. The ticket lifecycle is
docs/protocol.md section 4; the budget rules are `academy/references/budget.md` — at
most `budget.itemsPerRun` tickets, one after another, each within its own
`budget.runs`. Each agent runs on its agent file's model; a ticket's
`budget.max_model`, if present, is an advisory note and never blocks a route.

1. **Take.** `py $R/inbox.py` (or `--all` to list without taking). It prints the
   tickets to handle and the route of each, and how many more wait; a ticket still
   `in-progress` from an earlier run comes first and is resumed before anything new
   starts. Besides `open` and `accepted` tickets it takes a relay ticket ready for its **return leg**: `blocked`,
   routed to a relay by its `final_to`, waiting only on ticket ids (never `human`),
   every one of them `delivered` or terminal; it is marked `(return)` (`"return": true`
   in `--json`).
2. **For each ticket, in order:**
   - Read it (`$A/board.py show T-NNNN`). A ticket outside this role's work — asking for
     prose in a paper, a citation card, an experiment script — is `rejected` with the
     reason and the instance it belongs to (`$A/board.py transition T-NNNN rejected
     --reason "..." --as <instance>`).
   - A return-leg ticket goes straight to the same relay with the ticket id; make no
     transition yourself (the relay closes the child and delivers the ticket).
   - Otherwise move it `accepted` (`--as <instance>`), then run its route with the
     ticket id:
     `/researcher:prove`, `/researcher:review-experiment` (or `/researcher:settle`
     when the report lists candidates), `/researcher:generalize`,
     `/researcher:explore` for a `question`, `claim-keeper` for a `decision` (a status
     proposal), and `lead-researcher` for everything else. A ticket whose `final_to`
     lies beyond the Researcher goes to its relay (`experiment-spec` toward the
     Scientist, `lit-request` toward the Expert or the Author), whatever its kind; a
     `research` ticket without `final_to` goes to `lead-researcher`.
   - If the work needs more runs or a heavier model than `budget` allows, move it
     `blocked` with `--waiting-on human` and a thread line asking for more budget.
   - The route delivers the ticket with a one-line result. **Checkpoint** before taking
     the next: `py $R/inbox.py --check T-NNNN` (exit 0: delivered, blocked with its
     reason or rejected; exit 3: unfinished, so report it and take nothing more).
3. **Stop** after the last taken ticket, or at once on a usage or rate-limit error:
   record what was and was not done in the ticket thread and report. No relaunch.
4. **Report**: each ticket, its route and outcome (delivered / blocked / rejected),
   and how many remain.

Writing a result or a decision starts no further work; the sender picks it up in its
own next run.
