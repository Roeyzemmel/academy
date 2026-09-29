---
name: inbox
description: Work this Researcher instance's board inbox — take at most three open or accepted tickets (by priority, agenda, id), serially, and route each by kind to the skill or agent that handles it (prove, review-experiment or settle, generalize, a decision to claim-keeper, a question to explore, anything else to lead-researcher), within each ticket's own run budget. Use for "/researcher:inbox", "what's waiting for the researcher", and when the SessionStart line reports open tickets.
---

# The Researcher inbox

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
     proposal), and `lead-researcher` for everything else. A ticket whose `final_to`
     lies beyond the Researcher goes to its relay (`experiment-spec` toward the
     Scientist, `lit-request` toward the Expert or the Author), whatever its kind; a
     `research` ticket without `final_to` goes to `lead-researcher`. A relay ticket
     comes back to you when its child is delivered: run the same relay again to deliver it.
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
