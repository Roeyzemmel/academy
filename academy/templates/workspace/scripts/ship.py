#!/usr/bin/env python3
"""Shim: run the academy plugin's ship.py for this workspace, with the same arguments.

The code is ``academy/scripts/ship.py`` of the academy checkout ($ACADEMY_ROOT, else this
workspace's ``academy/`` submodule, else an ``academy`` checkout next to the workspace);
this file only keeps the allowlisted ``py scripts/ship.py ...`` commands working."""
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = ("academy", "scripts", "ship.py")


def academy_script():
    for base in (os.environ.get("ACADEMY_ROOT"), os.path.join(ROOT, "academy"),
                 os.path.join(os.path.dirname(ROOT), "academy")):
        if base and os.path.isfile(os.path.join(base, *SCRIPT)):
            return os.path.join(base, *SCRIPT)
    return None


if __name__ == "__main__":
    script = academy_script()
    if not script:
        sys.exit("ship: refused: no academy checkout with %s (set ACADEMY_ROOT, or run "
                 "scripts/bootstrap.py)" % "/".join(SCRIPT))
    sys.argv = [script, "--workspace", ROOT] + sys.argv[1:]
    runpy.run_path(script, run_name="__main__")
