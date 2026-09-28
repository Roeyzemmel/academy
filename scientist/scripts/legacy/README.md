# Legacy copies of the lab's generic scripts

Byte-exact copies (working tree and git blob) of `FlatSurfLab/scripts/` as of
2026-09-28, taken for plan section 3.6: `queue.ps1`, `fsq.sh`, `run.ps1`, `run.sh`,
`vpn.ps1`, `setup_env.sh`, `test_fsq.sh`, `test_queue.ps1`, `check_experiments.py`.
The originals stay in the lab untouched.

They are **reference copies for the port, not runnable from here**: each finds its
repository from its own location (`$PSScriptRoot/..`, `dirname $BASH_SOURCE/..`,
`Path(__file__).parents[1]`). The port landed in Group C (2026-09-28):
`scientist/scripts/env.py` with the thin `queue.ps1` / `run.ps1` frontends, `run.sh`
parameterised by `LAB_ROOT`, `fsq.sh` (a byte copy, pinned to this one by
`tests/test_env.py`), `vpn.ps1` and `setup_env.sh` (copies), and
`check_experiments.py` parameterised by `academy.json`. `test_queue.ps1` (the
laptop side against a WSL stand-in) was not ported as a script: its protocol cases
(skip uncommitted, commit pinning, no resubmission, reconcile, collect, ack, runner
check) are in `tests/test_env.py` against a fake ssh. `test_fsq.sh` tests the runner
itself, which is unchanged; it still runs from the lab on a Linux host
(`bash scripts/test_fsq.sh`) and was not ported. Do not edit these files; they are the record
of what was ported, kept until phase 8.

Also here, moved out of `_import/flatsurf` in Group B's review fixes (2026-09-28), as
reference for the same Group C port:

- `flatsurf-run.ps1` and `setup_env.domain-skill.sh`: the `flatsurf-computation`
  skill's runner and environment setup (plan section 3.6: merged into `env.py`). The
  second is renamed so it does not collide with the lab's `setup_env.sh` above.
- `flatsurf_plugin_common.py`: the old flatsurf plugin's `scripts/_common.py`, which
  `scientist/scripts/_common.py` was adapted from (scoping by `academy.json`; the
  commit parser is now `academy_common.commit_targets`).
