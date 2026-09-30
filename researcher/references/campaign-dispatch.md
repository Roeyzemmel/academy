# Campaign dispatch, lab runs and decisions

Read by `/researcher:campaign`. The main session is the driver and dispatches
**strictly one subagent at a time**; there is no fan-out, so a limit error or a crash
loses at most the one ticket in hand, which the checkpoint has already recorded.

## The dispatch step

1. `/academy:inbox --campaign <target>` lists the tickets carrying the campaign's tag,
   in inbox order: in-progress first (unfinished work is resumed before anything new
   starts), then relay return legs, then open and accepted ones. Dead-route and pending
   blocked tickets are never listed, and the cap of three is lifted (the campaign's
   `--agents` cap applies). `--all` only looks: it adds the blocked ones, marked
   `blocked: pending` or `dead-route`, and takes nothing; never dispatch from it.
2. Take the first ticket. Dispatch one subagent for the receiving role, briefed with
   the ticket id only (`budget.md` rule 9), through the route that role's inbox names
   for that ticket (`py <role plugin>/scripts/inbox.py --instance <name> --json`).
3. The subagent moves the ticket `accepted`, then `in-progress`, works, and delivers or
   blocks it with a thread line, under the ticket's own `budget.runs` and `max_model`.
4. **Checkpoint before the next:** `py <role plugin>/scripts/inbox.py --instance <name>
   --check T-NNNN`. Exit 0: delivered, blocked with its reason or rejected. Exit 3:
   unfinished; report it, do not redispatch it in the same round, it is first in line
   next time. Then take the next ticket.
5. Relay tickets whose child tickets delivered get their return leg the same way, in
   inbox order.

Subagents cannot spawn subagents: the driver stays in the main session. Roles that
nest in their own definitions keep doing so; where nesting is unavailable, the driver
runs that level itself, one step at a time. The chain gate is untouched: the driver
files tickets as the Researcher, never as another role, and grants no permissions.

## Lab runs

`--runs K` preapproves at most K queued runs on `--profile` in place of a per-run
header approval. The receiving role still writes the header and the validation case and
files the run, and the header is recorded in the ticket, but is not held for a human.
Preflight, provenance and the environment policy are unchanged. A failed preflight, an
experiment needing another profile, or the K+1st run parks its ticket as waiting on
human. K = 0 (the default): every experiment ticket pauses at its header. In a cloud
session K is forced to 0.

## Decisions and unattended operation

The campaign never records a human decision and never applies a recommended option. A
packet or ticket that needs Roey is created or left `blocked` with `waiting_on:
[human]`, and the approach it concerns is noted as waiting on decision; other
approaches continue. If every approach waits on a human the campaign pauses. Status
changes still go only through claim-keeper on two agreeing reviews.

## Blocking an approach moves its tickets

A blocked approach's open tickets become dead-route blocked with the same `blocked_by`
and `reopen_if`, and reopen with the approach. The ticket chain lets only a ticket's
receiver block it, so `notebook.py approach set ... blocked` lists the exact
`board.py transition ... blocked --blocked-by ... --reopen-if ...` moves; the
receiving role (through the dispatch step) or Roey makes them, each with a `tried:`
reason. Reopening a ticket is `blocked -> accepted --reopen "<the new mechanism>"`.
