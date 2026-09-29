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
| `ssh` | any remote Linux workstation | `host` (required), `prefix`, `env`, `repo`, `maxJobs` |

Any profile may carry a **preflight** `<name>:<arg>` (for example
`vpn:globalprotect`), a pluggable check run before anything is sent. A failing
preflight on an `ssh` profile means **queued, not failed**: the job waits.

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
  preflight (for `vpn:globalprotect`, the GlobalProtect adapter's status; no network).
  `env.py check <profile> --live` then asks the machine itself: for `ssh`, only
  `fsq version` (compared with the plugin's `fsq.sh`) and `fsq status`; for `wsl`,
  whether the env's python exists. Report "reachable", "unreachable: preflight <name>
  failed (queued jobs wait)", or the error verbatim. Never debug a failed VPN or ssh
  connection; only Roey fixes it.
- `setup <profile>`: `env.py setup <profile>` installs the conda environment the
  profile names (`setup_env.sh`; `--dry-run` prints the commands). On an `ssh` profile
  this changes a remote machine: show Roey the commands and run them only on his
  word (`AskUserQuestion`).
- `switch <work> <profile>` and `add <name> <kind> ...`: edit
  `scientist.envs` / `scientist.policy` in `.claude/academy.json`. Show the diff and
  ask before writing; after writing, `/academy:status` (or the SessionStart line)
  validates the config. A `policy.run` that points at a `wsl` or `local` profile
  lifts "no laptop compute": say so explicitly when asking.

## Status of the implementation

`env.py` (Group C, 2026-09-28; tests `tests/test_env.py`) replaces the lab's
`queue.ps1`, `run.ps1`, `vpn.ps1` and `run.sh`: the plugin's `queue.ps1` / `run.ps1`
are thin frontends to it, `run.sh` is the Linux side of `wsl` / `local` runs, and
`vpn.ps1` is the preflight. A switched-over lab keeps one-line shims at the old paths.
`fsq.sh` is deployed from the plugin's copy; deploying is Roey's call. The
byte-exact originals stay in `${CLAUDE_PLUGIN_ROOT}/scripts/legacy/` until the old
plugins are retired.

Budget and independence: `${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md`,
`${CLAUDE_PLUGIN_ROOT}/../academy/references/roster-rules.md`.
