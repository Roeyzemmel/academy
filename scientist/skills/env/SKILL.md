---
name: env
description: 'Manage the lab''s environment profiles: list, check, set up, switch which profile probe / test / run work uses, add a wsl, local or ssh profile. Use for "which machine does this run on", "is the server reachable", "add a profile".'
---

# Environment profiles

`$ARGUMENTS` is one of `list`, `check [profile]`, `setup <profile>`,
`switch <probe|test|run> <profile>`, `policy`, `add <name> <kind> ...`.

## The model

A **profile** is one place code can run, in the Scientist home's
`.claude/academy.json` under `scientist.envs`. Each has a **kind**; a named machine
is a profile, never a kind:

| Kind | What it is | Keys (docs/config.md, scientist block) |
|---|---|---|
| `wsl` | a WSL distro on the Windows laptop | `distro` (required), `conda` |
| `local` | the Linux machine Claude itself runs on | `conda`, `maxJobs` |
| `ssh` | any remote Linux workstation | `host` (required), `user`, `prefix`, `env`, `repo`, `maxJobs`, `gateway` |

A **remote worker** is not spelled out in the home: the profile is
`{"worker": "<name>"}`, and the worker (host, user, remoteRoot, conda prefix and env,
its gateway) is the workspace's, in `workspace.json` under `compute.workers`
(docs/config.md, "compute"). Its **gateway** (`compute.gateways`: a VPN with a
pluggable check, or `none`) is checked locally before anything is sent. A gateway that
is down on an `ssh` profile means **queued, not failed**: the job waits, and the
gateway's `onDown` says what to tell the human. The plugin knows no machine of its
own: a profile the home does not define is refused.

The **policy** maps each kind of work to a profile: `probe` (one-line API checks),
`test` (unit and validation tests), `run` (experiments). "No laptop compute for
experiments" is simply `policy.run` naming a remote profile. The `fsq` runner works
on any Linux target, over ssh or locally.

## What each action does

The runner is `py "${CLAUDE_PLUGIN_ROOT}/scripts/env.py" [--home <lab>] <command>`
(`--help` lists everything). A profile argument may also be a policy key (`probe`,
`test`, `run`) or a legacy target (`wsl`, `wsl:<distro>`, `ssh:<host>`).

- `list` / `policy`: `env_list` (MCP, read-only), or `env.py list`.
- `check [profile]` (default `policy.run`): `env_check` for the static check (keys
  present, kind known, policy consistent). `env.py check <profile>` adds the
  gateway check (local; for a VPN client, the tunnel's status; no ssh).
  `env.py check <profile> --live` then asks the machine itself: for `ssh`, only
  `fsq version` (compared with the plugin's `fsq.sh`) and `fsq status`; for `wsl`,
  whether the env's python exists. Report "reachable", "unreachable: gateway <name>
  is down (queued jobs wait)" with the gateway's `onDown`, or the error verbatim. Never
  debug a failed gateway or ssh connection: follow the `onDown` and stop.
  `env.py gateway [--profile P] [--probe]` is the gateway check alone.
- `setup <profile>`: `env.py setup <profile>` installs the conda environment the
  profile names (`setup_env.sh`, with the packages of the home's domain packs,
  `domains/<pack>/computation/env.txt`; `--dry-run` prints the commands). On an `ssh` profile
  this changes a remote machine: show Roey the commands and run them only on his
  word (`AskUserQuestion`).
- `switch <work> <profile>` and `add <name> <kind> ...`: edit
  `scientist.envs` / `scientist.policy` in `.claude/academy.json` (a remote machine
  is added as a worker in the workspace's `compute` block, and the profile names it). Show the diff and
  ask before writing; after writing, `/academy:status` (or the SessionStart line)
  validates the config. A `policy.run` that points at a `wsl` or `local` profile
  lifts "no laptop compute": say so explicitly when asking.

## Status of the implementation

`env.py` (Group C, 2026-09-28; tests `tests/test_env.py`) replaces the lab's
`queue.ps1`, `run.ps1`, `vpn.ps1` and `run.sh`: the plugin's `queue.ps1` / `run.ps1`
are thin frontends to it, `run.sh` is the Linux side of `wsl` / `local` runs,
`workers.py` resolves workers and checks gateways, and `vpn.ps1` is the Windows
GlobalProtect check one kind of gateway uses. A switched-over lab keeps one-line shims at the old paths.
`fsq.sh` is deployed from the plugin's copy; deploying is Roey's call. The
byte-exact originals stay in `${CLAUDE_PLUGIN_ROOT}/scripts/legacy/` until the old
plugins are retired.

Budget and independence: `${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md`,
`${CLAUDE_PLUGIN_ROOT}/../academy/references/roster-rules.md`.
