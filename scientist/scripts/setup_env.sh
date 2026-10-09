#!/usr/bin/env bash
# Create or update a conda env (conda-forge) for a lab profile. No root needed. Works in
# WSL, on the local Linux machine, and on a remote worker (env.py copies this file there).
#
# Called by `env.py setup <profile>`, which sets everything from the profile and the
# home's domain packs; nothing here names a machine or a package:
#
#   ACADEMY_CONDA_ENV    the env name                 (the profile's conda / the worker's conda.env)
#   ACADEMY_CONDA_PKGS   the package specs, space-separated (domains/<pack>/computation/env.txt)
#   ACADEMY_CONDA_CHECK  optional: a Python file run in the new env to verify it
#                        (domains/<pack>/computation/env-check.py)
#   MINIFORGE_PREFIX     where Miniforge is or goes   (default ~/miniforge3)
#   ACADEMY_CONDA_CHANNEL  default conda-forge
#
# Afterwards run things with:  $MINIFORGE_PREFIX/bin/mamba run -n $ACADEMY_CONDA_ENV python script.py
set -euo pipefail

PREFIX="${MINIFORGE_PREFIX:-$HOME/miniforge3}"
case "$PREFIX" in "~/"*) PREFIX="$HOME/${PREFIX#\~/}" ;; esac
ENV_NAME="${ACADEMY_CONDA_ENV:-${FLATSURF_ENV:-}}"
PKGS="${ACADEMY_CONDA_PKGS:-}"
CHANNEL="${ACADEMY_CONDA_CHANNEL:-conda-forge}"
MAMBA="$PREFIX/bin/mamba"
[ -n "$ENV_NAME" ] || { echo "setup_env.sh: no env name (ACADEMY_CONDA_ENV); run it through env.py setup <profile>" >&2; exit 2; }
[ -n "$PKGS" ] || { echo "setup_env.sh: no packages (ACADEMY_CONDA_PKGS); run it through env.py setup <profile>" >&2; exit 2; }

if [ ! -x "$MAMBA" ]; then
  echo ">> Installing Miniforge to $PREFIX"
  url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
  curl -fsSL -o /tmp/miniforge.sh "$url"
  bash /tmp/miniforge.sh -b -p "$PREFIX"
  rm -f /tmp/miniforge.sh
fi

# shellcheck disable=SC2086  # PKGS is a word list on purpose
if "$MAMBA" env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo ">> Env $ENV_NAME exists; updating"
  "$MAMBA" install -y -n "$ENV_NAME" -c "$CHANNEL" $PKGS
else
  echo ">> Creating env $ENV_NAME (a large env can take 10-30 minutes)"
  "$MAMBA" create -y -n "$ENV_NAME" -c "$CHANNEL" $PKGS
fi

echo ">> Verifying"
if [ -n "${ACADEMY_CONDA_CHECK:-}" ]; then
  "$MAMBA" run -n "$ENV_NAME" python "$ACADEMY_CONDA_CHECK"
else
  "$MAMBA" run -n "$ENV_NAME" python -c 'import sys; print("python", sys.version.split()[0])'
fi
echo ">> Done. Use: $MAMBA run -n $ENV_NAME python <script>"
