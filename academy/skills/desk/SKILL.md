---
name: desk
description: 'The human''s front desk: classifies a plain-language request and routes it (clerk answer, deep-dive, role skill or confirmed ticket); with no argument, one screen of what needs the human. Use as the default cross-role entry point, or for "what''s going on".'
---

# The front desk

`$ARGUMENTS` is the human's request in plain words, or empty. Scripts: `$S` as in
`${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Budget: `references/budget.md`.

## No argument: the one-screen summary

1. Run `py $S/academy_status.py --since last --usage --mark-visit`.
   Then `py $S/cowork.py list`: the active workplans (each cowork and campaign with its
   state, `WAITING` / `PAUSE` / `ACTIVE`, and its open tickets).
2. Show both outputs as they are, in one block each. The status `NEEDS YOU (N)` line is the
   pending-decision count — every ticket to human, every ticket blocked on human, and
   every open packet, the same three sources `/academy:decide` works from. Below the
   block, at most three lines: the most urgent thing that needs the human and the command
   that handles it (`/academy:decide` when `NEEDS YOU` is non-zero, `/academy:review`
   for the packet dashboard specifically, `/academy:board show T-NNNN` for one ticket,
   `/academy:cowork <slug> --resume` for a cowork that waits on the human).
3. Stop. Start nothing.

## With a request

0. **A request that is plainly about decisions** ("what needs my decision", "ask me",
   "decisions", "what's waiting on me") skips the concierge entirely: run
   `/academy:decide` directly and stop. Everything else goes through routing below.
1. **Route.** Dispatch one `concierge` subagent with the request verbatim, the cwd,
   and nothing else. It returns a routing card (`references/desk-routing.md`): the
   class (`answered`, `explain`, `action`, `ticket`, `unclear`), the target and, for
   a ticket, a draft. For a quick question it has already asked the clerk, and the
   card carries the answer with its source.
2. **Act on the card**, in the main session:
   - `answered`: show the answer and its source. Done.
   - `explain`: run `/academy:deep-dive <subject>` with the card's subject.
   - `action`: name the skill and its arguments, then invoke it (one skill, once).
   - `ticket`: show the draft and ask the human with `AskUserQuestion`: file as drafted,
     change the receiver or priority, or drop it. Only on a yes, file it with
     `py $S/board.py new --as human ...`, and print the ticket id and its folder.
     File as the human (`--as human`) only after they confirmed this ticket through AskUserQuestion; besides an approved /academy:cowork plan, this is the only way to file as them from inside a home (docs/protocol.md section 5).
   - `unclear`: ask the human the card's one question with `AskUserQuestion`, then route
     again (once).
3. If the concierge returns a limit error or nothing, report that and stop
   (budget rule 4). Never relaunch it.

Nothing the desk files runs on its own: the receiver's `/<role>:inbox` picks it up.
