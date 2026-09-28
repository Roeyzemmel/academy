---
name: inbox
description: Work the Expert instance's inbox — take at most three open or accepted tickets addressed to it, in priority order, serially, and route each by kind (verify to the review-chair, cite to the librarian, lookup and question to the clerk, referee to the referee, notation to the domain skill), recording every step in the ticket thread. Use for "work the expert inbox", "what's waiting for the library", and when the SessionStart line reports open tickets to the Expert.
---

# The Expert's inbox

`$ARGUMENTS` is empty, or a number (at most 3) of tickets to take, or ticket ids.
Scripts: `$E` = `${CLAUDE_PLUGIN_ROOT}/scripts`. Run from the library home, so the MCP
tools act for the Expert instance. The budget rules are `academy/references/budget.md`;
the ticket lifecycle is `docs/protocol.md` section 4.

1. **Plan**: `py $E/inbox.py --json [--limit N]`. It lists what waits, takes at most
   `budget.itemsPerRun` (never more than 3), and gives each ticket its route. Say how
   many are taken and how many wait.
2. **One ticket at a time**, each finished and checkpointed in its thread before the
   next starts (`budget.md` rules 1–2):

   | route | what to do |
   |---|---|
   | `expert:verify` | run the `verify` skill with the claim id from the refs and the ticket id |
   | `expert:cite` | run the `cite` skill with the ticket id |
   | `clerk` | `open -> accepted -> in-progress`; one `clerk` run with the ask; its answer becomes the `result` and `## Result`, then `delivered`. An `ESCALATE` answer: append it to the thread and, if the ticket's `budget.runs` allows a second run, dispatch one `librarian` with the escalated ask; otherwise `blocked`, `waiting_on: [human]`, asking for the budget |
   | `expert:referee` | run the `referee` skill with the ticket id |
   | `expert:domain` | run the `domain` skill with the ticket id |
   | `human` | `blocked`, `waiting_on: [human]`, with a thread line naming the decision needed |
   | `reject` | `rejected`, with the script's reason in the same write |

   Each transition goes through `tickets_update`; never edit a ticket file.
3. **Stop at once** on a limit error: record in the current ticket's thread what was
   and was not done, launch nothing further, and report (`budget.md` rule 4). A ticket
   whose `budget.runs` or `budget.max_model` cannot cover its route goes to `blocked`
   with `waiting_on: [human]` and a thread line asking for the budget.

## Report

One line per ticket taken: id, route, final status, result or packet id. Then how many
wait for the next run. Never ask questions.
