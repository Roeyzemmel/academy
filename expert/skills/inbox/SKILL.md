---
name: inbox
description: 'Work the Expert''s inbox: take at most three open or accepted tickets, route each by kind (verify, cite, lookup, question, referee, notation; research or final_to beyond the Expert to a relay agent), logging each in the thread. Use for "work the expert inbox".'
---

# The Expert's inbox

`$ARGUMENTS` is empty, or a number (at most 3) of tickets to take (`--n N`, or `--limit N`), `--all` (list only), or ticket ids.
Scripts: `$E` = `${CLAUDE_PLUGIN_ROOT}/scripts`. Run from the library home, so the MCP
tools act for the Expert instance. The budget rules are `academy/references/budget.md`;
the ticket lifecycle is `docs/protocol.md` section 4.

1. **Plan**: `py $E/inbox.py --json [--n N]` (the shared inbox core; routes are
   `scripts/routes.py`). It lists what waits, takes at most `budget.itemsPerRun` (never
   more than 3), and gives each ticket its route. A ticket still `in-progress` from an
   earlier run comes first and is resumed. Besides `open` and `accepted` tickets it takes a relay ticket ready for its **return leg**:
   `blocked`, routed to a relay by its `final_to`, waiting only on ticket ids (never
   `human`), every one of them `delivered` or terminal; its route carries
   `"return": true` on its row. Say how many are taken and how many wait.
2. **One ticket at a time**, each finished and checkpointed in its thread before the
   next starts (`budget.md` rules 1–2):

   | route | what to do |
   |---|---|
   | `expert:verify` | run the `verify` skill with the claim id from the refs and the ticket id |
   | `expert:cite` | run the `cite` skill with the ticket id |
   | `clerk` | `open -> accepted -> in-progress`; one `clerk` run with the ask; its answer becomes the `result` and `## Result`, then `delivered`. An `ESCALATE` answer: append it to the thread and, if the ticket's `budget.runs` allows a second run, dispatch one `librarian` with the escalated ask; otherwise `blocked`, `waiting_on: [human]`, asking for the budget |
   | `expert:referee` | run the `referee` skill with the ticket id |
   | `expert:domain` | run the `domain` skill with the ticket id |
   | `research-intake` | one `research-intake` run on the ticket (a `final_to` toward the Researcher or the Scientist, whatever the kind, or a `research` ticket with no `final_to`); with `"return": true`, the same agent's return leg: it closes the child and delivers the ticket. Make no transition yourself |
   | `paper-liaison` | one `paper-liaison` run on the ticket (a `final_to` toward an Author, whatever the kind); with `"return": true`, the same agent's return leg: it closes the child and delivers the ticket. Make no transition yourself |
   | `human` | `blocked`, `waiting_on: [human]`, with a thread line naming the decision needed |
   | `reject` | `rejected`, with the script's reason in the same write (for Researcher or Scientist work it tells the sender to ask through a `research` ticket to the Expert with `final_to`) |

   Each transition goes through `tickets_update`; never edit a ticket file. After each
   ticket, `py $E/inbox.py --check T-NNNN` (exit 0: delivered, blocked with its reason or
   rejected; exit 3: unfinished, so report it and take nothing more).
3. **Stop at once** on a limit error: record in the current ticket's thread what was
   and was not done, launch nothing further, and report (`budget.md` rule 4). A ticket
   whose `budget.runs` or `budget.max_model` cannot cover its route goes to `blocked`
   with `waiting_on: [human]` and a thread line asking for the budget.

## Report

One line per ticket taken: id, route, final status, result or packet id. Then how many
wait for the next run. Never ask questions.
