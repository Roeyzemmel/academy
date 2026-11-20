#!/usr/bin/env python3
"""Stop hook: uncommitted work in the workspace's homes, minus what a live run has claimed.

Opt-in: it does anything only when the workspace's workspace.json says ``"stopCheck":
true``. Then, at a session's Stop, it lists every dirty path of every home (each
checked-out submodule and the board's directory of the superproject) except the paths a
*live* inbox run changed since its snapshot (``manifest.py``; academy_common._manifest):
those belong to a ticket still being worked, and its ``--check`` commits them. A claim
whose run is dead (older than ``CLAIM_MAX_HOURS``, or its pid of this host gone) hides
nothing. Anything left blocks the stop once (``{"decision": "block", "reason": ...}``),
naming at most 20 paths; with ``stop_hook_active`` it is silent, so it never loops.

Claude Code's own cloud stop check (``~/.claude/stop-hook-git-check.sh``) is not the
academy's and looks only at the session's repository; this hook does not change it.
A hook bug never blocks anything: every failure is silence.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402

SHOWN = 20


def decide(event):
    if event.get("stop_hook_active"):
        return None
    ws = ac.load_workspace()
    if ws.get("stopCheck") is not True:
        return None
    root = os.path.dirname(os.path.abspath(ws["_path"]))
    b = ws.get("board") or "board"
    left = ac.unclaimed_dirty(root, b if os.path.isabs(b) else os.path.join(root, b))
    paths = ["%s/%s" % (t, p) for t, ps in left.items() for p in ps]
    if not paths:
        return None
    more = "" if len(paths) <= SHOWN else " (+%d more)" % (len(paths) - SHOWN)
    return ("Uncommitted changes no live inbox run has claimed: %s%s. Commit them on a work "
            "branch (py scripts/ship.py ...) or say why they stay." % (", ".join(paths[:SHOWN]), more))


def main():
    try:
        reason = decide(ac.read_event())
    except Exception:  # noqa: BLE001 -- a hook bug never blocks
        return 0
    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
