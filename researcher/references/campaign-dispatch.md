# Campaign dispatch, lab runs and decisions

Read by `/researcher:campaign`. The caps, the suspension of budget rules, serial
dispatch and K are `academy/references/budget.md` ("Campaigns"); this file is the
mechanics. The main session is the driver.

## The dispatch step

0. **Skip held tickets.** The shared inbox does not know approaches, so the lead first
   runs `notebook.py approach tickets --held`: the open tickets of a blocked, dropped or
   delivered approach. Do not dispatch them; a skipped ticket costs no `--agents`.
1. `/academy:inbox --campaign <target>` lists the tickets carrying the campaign's tag,
   not cut at three (`docs/protocol.md` section 4). Order is **per instance**, in that
   skill's fixed instance order (Author, Expert, Researcher, Scientist); inside one
   instance in-progress tickets come first, then relay return legs, then open and
   accepted ones. An in-progress ticket of a later instance is not ahead of an earlier
   instance's rows. Dead-route and pending blocked tickets are never listed. `--all`
   only looks (it adds the blocked ones, marked `blocked: pending` or `dead-route`);
   never dispatch from it.
2. Take the first ticket not held. Dispatch one subagent for the receiving role,
   briefed with the ticket id only (`budget.md` rule 9), through the route that role's
   inbox names for that ticket (`py <role plugin>/scripts/inbox.py --instance <name>
   --json`).
3. The subagent moves the ticket `accepted`, then `in-progress`, works, and delivers or
   blocks it with a thread line, under the ticket's own `budget.runs` (the agent runs on its agent file's model;
   a `budget.max_model` is only an advisory note, T-0071).
4. **Checkpoint** as in `/academy:inbox` step 3: the driver runs `inbox.py --instance
   <name> --check T-NNNN` once per ticket (the subagent does not; a finished ticket's
   `--check` also runs the workspace's ship.py checkpoint); exit 3 means unfinished: not
   redispatched this round, first in line next time. Then the next ticket. Relay tickets whose children delivered get their return
   leg the same way.

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
human. With K = 0 every experiment ticket pauses at its header.

## Decisions, waiting and pausing

The campaign never records a human decision and never applies a recommended option. A
packet or ticket that needs Roey is created or left `blocked` with `waiting_on:
[human]`; other approaches continue, and the report points at `/academy:decide`. An
approach is **waiting on a decision** when any ticket naming it (or its directions) is
blocked with `human` in `waiting_on`; it is derived from the tickets, never recorded on
the approach (`notebook.py approach status` prints it per approach). The campaign
**pauses**, with "paused, waiting on T-a, T-b", when every active approach waits on a
decision (`approach status` prints `PAUSE`), or every remaining direction waits on a
ticket that no dispatch can move (a run beyond `--runs`, an unreachable profile). The
approach objects and the board carry all the state; the next invocation resumes from
them. Status changes still go only through claim-keeper on two agreeing reviews.

## Blocking an approach moves its tickets

`notebook.py approach set AP-n blocked --blocked-by <id> --reopen-if "..." [--apply]`
moves the approach's open tickets (found by `refs`, through the board store) to
dead-route blocked with the same `blocked_by` and `reopen_if` and a `tried:` line.
Only a ticket's receiver (or Roey) may block it, so `--apply` moves only the tickets
addressed to this instance; for the others it prints the exact `board.py transition ...
blocked --as <receiver>` command, which that role or Roey runs. Until then such tickets
are **held** (step 0). `approach set AP-n active --note "<new mechanism>" [--apply]` does
the same for the way back: the tickets blocked with that approach's fields return by
`blocked -> accepted --reopen "<the new mechanism>"`. A move to `dropped` or
`delivered` leaves its tickets as they are: the sender cancels or closes them.
