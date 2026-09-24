---
name: queue
description: Drive the lingo job queue in FlatSurfLab — file a run, check the VPN, tick it, poll while jobs are pending, read a log, settle finished jobs and report what came back. Handles the VPN-gated target, the uncommitted-script skip, and the runner on lingo that caps concurrency and never starts a job twice. Use for anything to do with running an experiment, checking on a run, "is it done yet", "start the jobs", or when a session has pending jobs and should keep watching them.
---

# The lingo queue

`$ARGUMENTS` is what to do: a script to add, a job id, or nothing (then: tick and
report).

Read `.claude/flatsurf.json` first: `lab` is FlatSurfLab, and every command below runs
there (`cd <lab>;` first when the session is elsewhere). `settle` is this repo's pass for
a returned result.

Experiments never run on the laptop. Every run, validation included, goes through
here. Config is FlatSurfLab's `queue/config.json` — target `ssh:lingo`, prefix
`/data/roeyzemmel/miniforge3`, remote repo `~/FlatSurfLab`, runner spool `~/fsq`,
`maxJobs` 1. How the runner, lingo and the VPN work is in FlatSurfLab's `docs/queue.md`;
read it only when something misbehaves. A job's `-Label` is a registry id
(`lab:<name>`); a run that checks code rather than a claim is `test:<name>`.

## The commands

| Intent | Command |
|---|---|
| is the VPN up (no network round trip) | `scripts\vpn.ps1` (exit 0 up, 1 down, 2 cannot tell); `-Quiet` for scripts |
| file a job | `scripts\queue.ps1 -Add experiments\foo.py -Label lab:<name> -Note "..." -ScriptArgs "--bound 40"` |
| what is queued | `scripts\queue.ps1 -List` |
| is lingo up | `scripts\queue.ps1 -Check` (exit 0 reachable, 1 not) |
| do a round | `scripts\queue.ps1 -Tick` |
| collect only, submit nothing | `scripts\queue.ps1 -Fetch` |
| what lingo's runner sees | `scripts\queue.ps1 -Status` |
| tail a job's log | `scripts\queue.ps1 -Log <id-prefix>` |

`vpn.ps1` reads the GlobalProtect adapter's state, so a poll costs milliseconds instead
of an eight-second TCP timeout; `-Tick` calls it first. DNS is no discriminator:
`lingo.tau.ac.il` resolves from the open internet and only the connection times out.

The scheduling happens on lingo, in the runner `~/fsq/bin/fsq` (`scripts/fsq.sh`).
`-Tick` submits pending jobs, reads the runner's spool, moves every local job to the
state the spool reports, then fetches finished jobs' files and settles them into
`queue/done/`. Jobs move `queue/pending/` → `queue/running/` → `queue/done/`. The runner
starts the next job when one finishes, so a job starts whether or not anyone ticks;
ticking only brings results home.

`-Tick` refuses to work if the runner on lingo differs from `scripts/fsq.sh`. The
remedy is `scripts\queue.ps1 -Deploy`, which is Roey's call: it changes lingo.

## Four rules that decide what you do next

1. **A connection timeout means the VPN is down.** Only Roey can connect it. Say
   "lingo is unreachable — the TAU VPN needs connecting" and stop. Do not debug ssh,
   do not try another host, do not fall back to running it here. The queue waits;
   that is what it is for.
2. **`-Tick` skips a job whose script is uncommitted or not in HEAD**, and says which.
   The remote runs the commit that was HEAD at submission. The fix is a commit by Roey,
   not a retry.
3. **The runner holds the cap, not you.** At most `maxJobs` jobs run at once (default
   1, hard limit 3); the rest wait on lingo in queue-id order. Filing many jobs is fine.
   A submit that "returned exit 255" is not a failed start: the lines after it show what
   lingo accepted. Never resubmit or re-add a job to "retry" it; a job id runs at most
   once, and a new run needs a new `-Add`.
4. **`/data` is world-writable NFS scratch that may be purged.** Nothing lives there
   but the reinstallable env. Results come back to FlatSurfLab's `results/`, and the
   laptop is the source of truth.

## Polling

A session with pending or running jobs watches them rather than declaring victory and
stopping: `/loop 15m /flatsurf:queue`, or a scheduled wake-up at a delay matched to the
job. Between ticks, report only transitions: a job started, a job finished, lingo came
back, lingo went away. Stop when the queue is empty, when the author says to, or when
the answer is "waiting on the VPN" and another check will not change it.

## Settling a finished job

`-Tick` records `status` (`ok`, `failed`, `exited-without-result`, `cancelled`, `lost`),
`exit`, `files` and `result`. When one lands:

1. Read the JSON — the bound actually reached, the class actually searched, the commit
   hash. Check the hash is the commit you meant to run.
2. Fill the script's `Result` field: "no counterexample below bound B over class C",
   never "true", never "confirms" (in Slope1, the `family-experimenter` does this).
3. Run the repo's `settle` pass before the number is cited or recorded anywhere.
4. Script and result JSON are committed together.

If a job failed, `-Log <id>` has the remote log. Read the actual traceback before
proposing anything — a rerun with a bigger bound is not a diagnosis. **A surprising
result is a bug until shown otherwise**; debug it (`superpowers:systematic-debugging`
where enabled) before changing anything.

## Reporting

Say what is true, with the evidence: "3 pending, 1 running (`lab:x`, started 14:02),
2 done" — from `-List`, not from memory of an earlier tick. Never "the run should be
finished by now". Tick, and read the output.
