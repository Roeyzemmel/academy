# Campaign tickets: hand-off, the next actor, lab runs, decisions

Read by `/researcher:campaign`. The caps, the suspension of budget rules and K are
`academy/references/budget.md` ("Campaigns"); the role cut is
`academy/references/roster-rules.md`; the shared state mechanics are
`academy/lib/workplan.py`. This file is the mechanics. The campaign is led by the
Researcher (`lead-researcher`, driven from the main session in the Researcher's home);
it runs no other role's agents.

## The hand-off step

1. **File, tagged.** Each ask for another role is one ticket from this Researcher
   instance, through the chain gate, tagged `campaign: <target>`, `refs` naming the
   approach and direction: `verify`, `cite` or `lookup` to the Expert; `experiment` or
   `test` to the Scientist; anything for an Author through the Expert with `final_to`.
2. **Wait for the next actor.** A filed ticket is worked by its receiver's own inbox
   run: `/<role>:inbox --campaign <target>` in that role's session, or
   `/academy:inbox --campaign <target>` run by the human, which acts as each instance
   in turn under the chain gate. `/academy:inbox --campaign <target>` lists the
   tickets carrying the campaign's tag, not cut at three (`docs/protocol.md`
   section 4), per instance in its fixed order; dead-route and pending blocked tickets
   are never listed, and `--all` only looks (it adds the blocked ones, marked
   `blocked: pending` or `dead-route`): never dispatch from it. The campaign does not
   run that inbox for another role and never works another role's ticket in its own
   session.
3. **Keep working.** `notebook.py approach status` derives each approach's state from
   its tickets: `WAITING` while its tickets are out with another role, `PAUSE` while
   one waits on the human, `ACTIVE` otherwise. The lead keeps every `ACTIVE` approach
   moving; nothing is redispatched while it waits.
4. **Take what comes back.** A ticket delivered back to this Researcher (or a new one
   addressed to it, tagged for the campaign) is worked by `/researcher:inbox --campaign
   <target>`: one ticket, one subagent of this role, then the **Checkpoint**
   `inbox.py --instance <name> --check T-NNNN` (exit 0 delivered, blocked with its
   reason or rejected; exit 3 means unfinished: not redispatched this round, first in
   line next time; a finished ticket's `--check` also runs the workspace's ship.py
   checkpoint).

**Held tickets.** The shared inbox does not know approaches, so the lead runs
`notebook.py approach tickets --held` first: the open tickets of a blocked, dropped or
delivered approach. They are not worked; their receivers are told through the moves
below.

Subagents cannot spawn subagents: the driver stays in the main session. The chain gate
is untouched: the driver files tickets as the Researcher, never as another role or as
the human, and grants no permissions.

## Lab runs

`--runs K` preapproves at most K queued runs on `--profile` in place of a per-run
header approval, recorded in each `experiment` ticket. The Scientist still writes the
header and the validation case and files the run when its inbox takes the ticket; the
header is recorded in the ticket, but is not held for a human. Preflight, provenance
and the environment policy are unchanged. A failed preflight, an experiment needing
another profile, or the K+1st run parks its ticket as waiting on human. With K = 0
every experiment ticket pauses at its header.

## Decisions, waiting and pausing

The campaign never records a human decision and never applies a recommended option. A
packet or ticket that needs the human is created or left `blocked` with `waiting_on:
[human]`; other approaches continue, and the report points at `/academy:decide`. An
approach is **waiting on a decision** when any ticket naming it (or its directions) is
blocked with `human` in `waiting_on`, and **waiting** (`WAITING`) when its tickets are
out with another role's next actor; both are derived from the tickets, never recorded
on the approach (`notebook.py approach status` prints them per approach). The campaign
**pauses** (`PAUSE`, "paused, waiting on T-a, T-b") when every active approach waits on
a decision, and **waits** (`WAITING`) when every active approach waits on tickets out
with other roles: it then stops with the list of tickets and the inbox run that moves
each, and the next invocation resumes from the approach objects and the board. Status
changes still go only through claim-keeper on two agreeing reviews.

## Blocking an approach moves its tickets

`notebook.py approach set AP-n blocked --blocked-by <id> --reopen-if "..." [--apply]`
moves the approach's open tickets (found by `refs`, through the board store) to
dead-route blocked with the same `blocked_by` and `reopen_if` and a `tried:` line.
Only a ticket's receiver (or the human) may block it, so `--apply` moves only the
tickets addressed to this instance; for the others it prints the exact `board.py
transition ... blocked --as <receiver>` command, which that role or the human runs.
Until then such tickets are **held**. `approach set AP-n active --note "<new
mechanism>" [--apply]` does the same for the way back: the tickets blocked with that
approach's fields return by `blocked -> accepted --reopen "<the new mechanism>"`. A
move to `dropped` or `delivered` leaves its tickets as they are: the sender cancels or
closes them.
