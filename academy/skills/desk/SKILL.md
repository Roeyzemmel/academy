---
name: desk
description: Roey's front desk for the whole academy. With a plain-language request ("check whether Lemma 4.2 is really needed", "run that example on the server", "what does Theorem 1.3 of that paper assume?", "explain this definition"), the concierge classifies it and routes it — a quick question to the Expert's clerk, "explain X" to a deep-dive, a single action to that role's skill, anything larger to a ticket Roey confirms before it is filed. With no argument, prints one screen across all instances — what needs Roey, what is in flight, what came back since the last visit, and the week's usage. Use as the default entry point whenever Roey asks for anything across roles, or asks "what's going on", "what needs me", "where are we".
---

# The front desk

`$ARGUMENTS` is Roey's request in plain words, or empty. Scripts: `$S` as in
`${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Budget: `references/budget.md`.

## No argument: the one-screen summary

1. Run `py $S/academy_status.py --since last --usage --mark-visit`.
2. Show its output as it is, in one block. Its `NEEDS YOU (N)` line is the
   pending-decision count — every ticket to human, every ticket blocked on human, and
   every open packet, the same three sources `/academy:decide` works from. Below the
   block, at most three lines: the most urgent thing that needs Roey and the command
   that handles it (`/academy:decide` when `NEEDS YOU` is non-zero, `/academy:review`
   for the packet dashboard specifically, `/academy:board show T-NNNN` for one ticket).
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
   - `ticket`: show the draft and ask Roey with `AskUserQuestion`: file as drafted,
     change the receiver or priority, or drop it. Only on a yes, file it with
     `py $S/board.py new ...` (as `human`), and print the ticket id and its folder.
   - `unclear`: ask Roey the card's one question with `AskUserQuestion`, then route
     again (once).
3. If the concierge returns a limit error or nothing, report that and stop
   (budget rule 4). Never relaunch it.

Nothing the desk files runs on its own: the receiver's `/<role>:inbox` picks it up.
