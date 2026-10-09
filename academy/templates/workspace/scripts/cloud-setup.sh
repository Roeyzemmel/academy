#!/bin/bash
# The cloud environment's setup script: `bash scripts/cloud-setup.sh`.
# Finds a working Python, runs the bootstrap (the scripts/bootstrap.py shim, which runs the
# academy's workspace_bootstrap.py), keeps a log, and never fails the environment (a failed
# setup shows no output); read bootstrap.log or this output.
cd "$(dirname "$0")/.." || exit 0
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" --version >/dev/null 2>&1; then PY=$c; break; fi
done
if [ -z "$PY" ]; then echo "cloud-setup: no working python found" | tee bootstrap.log; exit 0; fi
echo "cloud-setup: using $PY ($("$PY" --version 2>&1)), git $(git --version)"
"$PY" scripts/bootstrap.py --adopt-siblings 2>&1 | tee bootstrap.log
exit 0
