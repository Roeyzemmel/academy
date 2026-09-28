#!/usr/bin/env bash
# Create a Linux environment with sage-flatsurf + surface_dynamics (conda-forge).
# No root needed. Works in WSL Ubuntu and on a plain remote Linux server.
#
#   bash setup_env.sh              # install to ~/miniforge3, env "flatsurf"
#   MINIFORGE_PREFIX=/opt/mf FLATSURF_ENV=fs bash setup_env.sh
#
# Afterwards run things with:
#   ~/miniforge3/bin/mamba run -n flatsurf python script.py
#   ~/miniforge3/bin/mamba run -n flatsurf sage -c "..."
set -euo pipefail

PREFIX="${MINIFORGE_PREFIX:-$HOME/miniforge3}"
ENV_NAME="${FLATSURF_ENV:-flatsurf}"
MAMBA="$PREFIX/bin/mamba"
# conda-forge names: the surface_dynamics package is "surface-dynamics" (hyphen).
PKGS="sage-flatsurf pyflatsurf pyexactreal sage pip surface-dynamics"

if [ ! -x "$MAMBA" ]; then
  echo ">> Installing Miniforge to $PREFIX"
  url="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
  curl -fsSL -o /tmp/miniforge.sh "$url"
  bash /tmp/miniforge.sh -b -p "$PREFIX"
  rm -f /tmp/miniforge.sh
fi

if "$MAMBA" env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo ">> Env $ENV_NAME exists; updating"
  "$MAMBA" install -y -n "$ENV_NAME" -c conda-forge $PKGS
else
  echo ">> Creating env $ENV_NAME (this downloads SageMath; expect 10-30 minutes)"
  "$MAMBA" create -y -n "$ENV_NAME" -c conda-forge $PKGS
fi

echo ">> Verifying"
"$MAMBA" run -n "$ENV_NAME" python -c '
import flatsurf, surface_dynamics
print("sage-flatsurf", flatsurf.__version__)
print("surface_dynamics", surface_dynamics.version.version)
from flatsurf import translation_surfaces
S = translation_surfaces.mcmullen_L(1,1,1,1)
print("stratum", S.stratum())
'
echo ">> Done. Use: $MAMBA run -n $ENV_NAME python <script>"
