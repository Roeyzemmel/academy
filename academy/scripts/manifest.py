#!/usr/bin/env python3
"""The checkpoint manifest of an inbox ticket: snapshot before it, diff after it (#101).

    py manifest.py [--workspace WS] snapshot --ticket T-NNNN [--run RUN] [--pid PID]
    py manifest.py [--workspace WS] diff --ticket T-NNNN [--json]
    py manifest.py [--workspace WS] release --ticket T-NNNN
    py manifest.py [--workspace WS] unclaimed [--json]

``snapshot`` records the dirty set (path and content hash) of every home of the workspace
-- each checked-out submodule and the board when it is a plain directory of the
superproject -- as run ``RUN``'s claim for the ticket (``<workspace>/.academy/run-claims/
<RUN>-<ticket>.json``; default run ``inbox``; one file per run and ticket, so concurrent runs
never overwrite each other's claim; stale claims are removed first). The inbox workflow runs it before each ticket.

``diff`` prints the ticket's manifest: the paths dirty now that were clean at the snapshot
or whose content changed since, per target (paths relative to it); exit 1 when the ticket
has no claim. ``release`` removes the ticket's claim. The inbox's ``--check`` does the diff,
the release and ``ship.py checkpoint --manifest`` itself (``academy_common._manifest``).

``unclaimed`` is the stop check by hand: every dirty path except those a live claim's run
changed since its snapshot (a claim is stale after ``CLAIM_MAX_HOURS`` hours, 6, or when
its pid of this host is gone). A home whose ``git status`` failed at the snapshot is listed
in the claim's ``failed`` and nothing of it is claimed. The ``Stop`` hook ``stop_check.py`` does the same when
workspace.json says ``"stopCheck": true``.

The workspace is ``--workspace`` (a directory or its workspace.json), else the one the
academy library finds (``$ACADEMY_WORKSPACE``, the checkout's workspace). Standard library
only.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402


def workspace(given):
    path = given
    if path and os.path.isdir(path):
        path = os.path.join(path, "workspace.json")
    ws = ac.load_workspace(path)
    return os.path.dirname(os.path.abspath(ws["_path"])), ws


def board_rel(root, ws):
    b = ws.get("board") or "board"
    return b if os.path.isabs(b) else os.path.join(root, b)


def show(repos, as_json, extra=None):
    if as_json:
        doc = dict(extra or {})
        doc["repos"] = repos
        print(json.dumps(doc, indent=1, sort_keys=True))
        return
    if not repos:
        print("(nothing)")
    for target, paths in repos.items():
        for p in paths:
            print("%s/%s" % (target, p))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--workspace")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("snapshot")
    s.add_argument("--ticket", required=True)
    s.add_argument("--run")
    s.add_argument("--pid", type=int)
    d = sp.add_parser("diff")
    d.add_argument("--ticket", required=True)
    d.add_argument("--json", action="store_true")
    r = sp.add_parser("release")
    r.add_argument("--ticket", required=True)
    u = sp.add_parser("unclaimed")
    u.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        root, ws = workspace(a.workspace)
        board = board_rel(root, ws)
        if a.cmd == "snapshot":
            c = ac.manifest_snapshot(root, a.ticket, run=a.run, board=board, pid=a.pid)
            n = sum(len(v) for v in c["repos"].values())
            print("snapshot of %s (run %s): %d dirty path(s) already there in %d home(s)"
                  % (a.ticket, c["run"], n, len(c["repos"])))
            return 0
        if a.cmd in ("diff", "release"):
            f, c = ac.find_claim(root, a.ticket)
            if not c:
                print("no claim for %s" % a.ticket, file=sys.stderr)
                return 1
            if a.cmd == "release":
                ac.release_claim(f)
                print("released %s (run %s)" % (a.ticket, c.get("run")))
                return 0
            show(ac.manifest_changed(root, c), a.json, {"ticket": a.ticket, "run": c.get("run")})
            return 0
        left = ac.unclaimed_dirty(root, board)
        if a.json:
            show(left, True)
        elif not left:
            print("(nothing unclaimed)")
        else:
            show(left, False)
        return 0
    except (ac.AcademyError, ac.ManifestError) as e:
        print("manifest: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
