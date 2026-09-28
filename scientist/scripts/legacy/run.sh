#!/usr/bin/env bash
# Run an experiment in the `flatsurf` conda env from a Linux / WSL shell.
#
#   scripts/run.sh experiments/foo.py [args...]
#   scripts/run.sh -c "from flatsurf import *; print(translation_surfaces.mcmullen_L(1,1,1,1).stratum())"
#   SAGE=1 scripts/run.sh -c "print(factor(2^64-1))"
#
# Env layout as created by scripts/setup_env.sh; override with MINIFORGE_PREFIX
# and FLATSURF_ENV.
set -euo pipefail
PREFIX="${MINIFORGE_PREFIX:-$HOME/miniforge3}"
ENV_NAME="${FLATSURF_ENV:-flatsurf}"
ENV_PREFIX="$PREFIX/envs/$ENV_NAME"
INTERP=python; [ "${SAGE:-0}" = "1" ] && INTERP=sage
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# Activate with a sourced `conda activate` rather than `mamba run`. `mamba run`
# captures the child's stdout and releases it only when the process exits, so
# progress output never appears and an interactive tool (the Tk viewer) is
# unusable through it; a sourced activation has no such problem. A full
# activation is required, not just PATH: the compiler packages' activate.d
# scripts set CXX, CONDA_BUILD_SYSROOT and friends, and without them cling (under
# pyflatsurf, and so under canonicalize() and GL2ROrbitClosure) segfaults in
# AddHostArguments while building its precompiled header -- exit 139, diagnosed
# on lingo 2026-09-22. Sage also needs the env's bin on PATH to find Singular and
# friends (FeatureNotPresentError otherwise), which activation provides.
[ -x "$ENV_PREFIX/bin/$INTERP" ] || {
  echo "no $INTERP in $ENV_PREFIX -- run scripts/setup_env.sh first" >&2; exit 1; }
if [ -f "$PREFIX/etc/profile.d/conda.sh" ]; then
  set +u  # the activate.d scripts read unset variables
  # shellcheck disable=SC1091
  . "$PREFIX/etc/profile.d/conda.sh"
  conda activate "$ENV_PREFIX"
  set -u
else
  echo "warning: no conda.sh under $PREFIX; activating by PATH only (pyflatsurf will crash)" >&2
  export PATH="$ENV_PREFIX/bin:$PATH"
  export CONDA_PREFIX="$ENV_PREFIX"
fi
PYTHONPATH="$ROOT" exec "$ENV_PREFIX/bin/$INTERP" "$@"
