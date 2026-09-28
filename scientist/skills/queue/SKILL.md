---
name: queue
description: Drive the lab's job queue — file a run on an env profile, check the profile's preflight (the VPN for a remote one), tick it, poll while jobs are pending, read a log, settle finished jobs and report what came back. Handles the preflight-gated remote target, the uncommitted-script skip, and the remote runner that caps concurrency and never starts a job twice. Use for anything about running an experiment, checking on a run, "is it done yet", "start the jobs", or when a session has pending jobs and should keep watching them.
---

# The job queue

`$ARGUMENTS` is what to do: a script to add, a job id, or nothing (then: tick and
report).

Every command below comes from

```
py "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" cmd <queue|vpn|run> [ARGS ...]
```

which prints the one command line that performs it: the plugin's runner, `env.py
--home <lab> queue ARGS` (it takes the legacy flags below as well as the subcommands
`add | list | check | tick | fetch | status | log`; `env.py --help`). Run what it
prints. Read-only views need no shell: `queue_status`, `queue_log`, `env_list`,
`env_check` (MCP; they never contact a host).

Experiments run only on the `policy.run` profile (`env_list` shows the policy). The
queue state lives in the lab home (`<queue dir>/{pending,running,done,parked}/`). A
job's label is a registry id (`lab:<name>`); a run that checks code rather than a
claim is `test:<name>`. How the runner and its host work is in the lab's docs; read
them only when something misbehaves.

## The actions

| Intent | ARGS to `lab.py cmd queue` (the legacy flags) |
|---|---|
| file a job | `-Add experiments/<stem>.py -Label lab:<name> -Note "..." -ScriptArgs "--bound 40"` |
| what is queued | `-List` |
| is the target reachable | `-Check` (exit 0 reachable, 1 not) |
| do a round | `-Tick` |
| collect only | `-Fetch` |
| what the remote runner sees | `-Status` |
| tail a job's log | `-Log <id-prefix>` |

The preflight alone (no network round trip): `lab.py cmd vpn`. `queue_add` (MCP)
checks that the script is committed, defaults the profile to `policy.run` and builds
the same job file; until the lab's academy.json sets `scientist.queue.mcpAdd: "on"`
it is a dry run that returns the file and the `-Add` command instead of writing it.

Arguments go through `-ScriptArgs`; the bare `-- --bound 40` form loses tokens
under PowerShell 5.1. `-Tick` submits pending jobs, reads the remote spool, moves
each local job to the state the spool reports, then fetches and settles finished
ones. The remote runner starts the next job by itself; ticking only brings results
home. If `-Tick` says the remote runner differs from the plugin's copy, deploying it
is Roey's call: it changes the remote host.

## Four rules that decide what you do next

1. **A failed preflight means the target is unreachable** (for a VPN-gated profile,
   the VPN is down). Only Roey fixes that. Say so and stop: do not debug ssh, do not
   try another host, do not fall back to running here. The queue waits; that is
   what it is for.
2. **A job whose script is uncommitted or not in HEAD is skipped**, and the tick says
   which. The fix is Roey's commit, not a retry.
3. **The runner holds the cap** (`maxJobs`, default 1, at most 3). Filing many jobs is
   fine. A submit that "returned exit 255" is not a failed start: the lines after it
   show what the remote accepted. Never resubmit or re-add a job to retry it; a job
   id runs at most once.
4. **Remote scratch may be purged.** Results come back to the lab's `results/`; the
   lab home is the source of truth.

## Polling

With pending or running jobs, watch rather than declare victory: `/loop 15m
/scientist:queue`, or a wake-up matched to the job. Report only transitions (a job
started or finished, the target came or went). Stop when the queue is empty, when
Roey says so, or when the answer is "waiting on the preflight" and another check will
not change it.

## Settling a finished job

`-Tick` records `status` (`ok`, `failed`, `exited-without-result`, `cancelled`,
`lost`), `exit`, `files` and `result`. When one lands:

1. Read the JSON: the bound actually reached, the class actually searched, the
   commit hash (is it the commit you meant to run?).
2. Hand over to `/scientist:experiment report <script>`: the experimenter fills the
   `Result:` field and the report draft, and the report packet and review ticket
   are generated from them.
3. A failed job: `-Log <id>` has the remote log. Read the actual traceback before
   proposing anything; a rerun with a bigger bound is not a diagnosis. **A
   surprising result is a bug until shown otherwise** (`superpowers:systematic-debugging`).

## Reporting

What is true, with the evidence: "3 pending, 1 running (`lab:x`, started 14:02),
2 done", from `-List` or `queue_status`, not from memory of an earlier tick. Never
"the run should be finished by now".
