#!/usr/bin/env python3
"""Shim: run the academy plugin's workspace bootstrap for this workspace, same arguments.

The code is ``academy/scripts/workspace_bootstrap.py`` of the academy checkout
($ACADEMY_ROOT, else this workspace's ``academy/`` submodule, else an ``academy`` checkout
next to the workspace, as a cloud session attaches it); with none, the ``academy``
submodule is initialised first. ``scripts/cloud-setup.sh`` runs this file."""
import os
import runpy
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = ("academy", "scripts", "workspace_bootstrap.py")


def academy_script():
    for base in (os.environ.get("ACADEMY_ROOT"), os.path.join(ROOT, "academy"),
                 os.path.join(os.path.dirname(ROOT), "academy")):
        if base and os.path.isfile(os.path.join(base, *SCRIPT)):
            return os.path.join(base, *SCRIPT)
    return None


if __name__ == "__main__":
    script = academy_script()
    if not script:
        subprocess.run(["git", "-C", ROOT, "submodule", "update", "--init", "--", "academy"],
                       env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
        script = academy_script()
    if not script:
        print("bootstrap: no academy checkout with %s: grant access to the academy repo "
              "(or set ACADEMY_ROOT) and rerun" % "/".join(SCRIPT))
        sys.exit(1 if "--strict" in sys.argv else 0)
    sys.argv = [script, "--workspace", ROOT] + sys.argv[1:]
    runpy.run_path(script, run_name="__main__")
