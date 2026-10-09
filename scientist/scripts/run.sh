#!/usr/bin/env bash
# Run a lab script in a conda env from a Linux / WSL shell -- the plugin's copy of
# the lab's scripts/run.sh, called by env.py for the wsl and local profile kinds.
#
#   LAB_ROOT=/path/to/lab bash run.sh experiments/foo.py [args...]
#   LAB_ROOT=/path/to/lab bash run.sh -c "import sys; print(sys.version)"
#   SAGE=1 LAB_ROOT=... bash run.sh -c "print(factor(2^64-1))"
#
# The only difference from the lab's copy is where the lab is: LAB_ROOT (default:
# the current directory) instead of this file's parent. The lab keeps its own
# scripts/run.sh, because the fsq runner on a remote host runs `bash scripts/run.sh`
# inside the job's worktree, where no plugin exists.
#
# Env layout as created by setup_env.sh. env.py sets MINIFORGE_PREFIX and
# ACADEMY_CONDA_ENV from the profile's prefix and conda (FLATSURF_ENV, the older
# name, is still read); there is no default env name.
set -euo pipefail
PREFIX="${MINIFORGE_PREFIX:-$HOME/miniforge3}"
ENV_NAME="${ACADEMY_CONDA_ENV:-${FLATSURF_ENV:-}}"
[ -n "$ENV_NAME" ] || {
  echo "no conda env named (ACADEMY_CONDA_ENV): set conda in the profile" >&2; exit 2; }
ENV_PREFIX="$PREFIX/envs/$ENV_NAME"
INTERP=python; [ "${SAGE:-0}" = "1" ] && INTERP=sage
ROOT="$(cd "${LAB_ROOT:-.}" && pwd)"
cd "$ROOT"
# Activate with a sourced `conda activate` rather than `mamba run`. `mamba run`
# captures the child's stdout and releases it only when the process exits, so
# progress output never appears and an interactive tool (the Tk viewer) is
# unusable through it; a sourced activation has no such problem. A full
# activation is required, not just PATH: the compiler packages' activate.d
# scripts set CXX, CONDA_BUILD_SYSROOT and friends, and without them cling (under
# pyflatsurf, and so under canonicalize() and GL2ROrbitClosure) segfaults in
# AddHostArguments while building its precompiled header -- exit 139, diagnosed
# on a remote worker 2026-09-22. Sage also needs the env's bin on PATH to find Singular and
# friends (FeatureNotPresentError otherwise), which activation provides.
[ -x "$ENV_PREFIX/bin/$INTERP" ] || {
  echo "no $INTERP in $ENV_PREFIX -- run env.py setup <profile> first" >&2; exit 1; }
if [ -f "$PREFIX/etc/profile.d/conda.sh" ]; then
  set +u  # the activate.d scripts read unset variables
  # shellcheck disable=SC1091
  . "$PREFIX/etc/profile.d/conda.sh"
  conda activate "$ENV_PREFIX"
  set -u
else
  echo "warning: no conda.sh under $PREFIX; activating by PATH only (packages with activate.d scripts may crash)" >&2
  export PATH="$ENV_PREFIX/bin:$PATH"
  export CONDA_PREFIX="$ENV_PREFIX"
fi
PYTHONPATH="$ROOT" exec "$ENV_PREFIX/bin/$INTERP" "$@"
