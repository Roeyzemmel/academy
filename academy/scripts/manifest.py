#!/usr/bin/env python3
"""The checkpoint manifest of an inbox ticket: snapshot before it, diff after it (#101).

    py manifest.py [--workspace WS] snapshot --ticket T-NNNN [--run RUN] [--pid PID]
    py manifest.py [--workspace WS] diff --ticket T-NNNN [--json]
    py manifest.py [--workspace WS] release --ticket T-NNNN
    py manifest.py [--workspace WS] unclaimed [--json]
    py manifest.py [--workspace WS] lease take (--run RUN | --prefix P) (--instances A,B | --targets T...) [--pid PID]
    py manifest.py [--workspace WS] lease heartbeat --run RUN
    py manifest.py [--workspace WS] lease release --run RUN [--targets T...]
    py manifest.py [--workspace WS] lease list [--json]

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

``lease`` (#96) is the run leases: an inbox run takes one on the home submodule of each
instance it runs (``<workspace>/.academy/leases/<target>.json``), so two runs with disjoint
instance sets can work in one checkout. ``take`` prints ``run RUN`` first (with ``--prefix``
the run id is made unique here: the prefix, a UTC timestamp and a random suffix), then one
line per instance (or target): ``leased <instance>: <target>``, or ``skipped <instance>:
<target> is leased by run ...`` when another live run holds it (the inbox skips that
instance this run), or ``unleased <instance>: ...`` when it has no home to lease. A lease is
live while its heartbeat is younger than ``LEASE_TIMEOUT_MINUTES`` (30), or, when it names
a pid of this host, while that process exists, up to ``CLAIM_MAX_HOURS`` (6) after the last
heartbeat; a stale one is taken over. ``snapshot --run RUN`` heartbeats the
run's leases; ``release`` removes them (never another run's). The board is never leased:
while another run holds a lease, a checkpoint commits it without moving the checkout.

The workspace is ``--workspace`` (a directory or its workspace.json), else the one the
academy library finds (``$ACADEMY_WORKSPACE``, the checkout's workspace). Standard library
only.
"""
import argparse
import datetime
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


def lease_targets(root, ws, instances):
    """``({target: [instances]}, {instance: target}, [instances without a home])``."""
    by_target, of, homeless = {}, {}, []
    known = ws.get("instances") or {}
    for name in instances:
        inst = known.get(name)
        target = ac.instance_target(root, inst.get("home")) if isinstance(inst, dict) else None
        if not target:
            homeless.append(name)
            continue
        by_target.setdefault(target, []).append(name)
        of[name] = target
    return by_target, of, homeless


def new_run_id(prefix):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    return ("%s-%s-%s" % (prefix, stamp, os.urandom(2).hex()))[-120:].lstrip("-.")


def cmd_lease(a, root, ws):
    if a.action == "list":
        rows = ac.leases(root)
        if a.json:
            print(json.dumps([dict(r, live=ac.lease_live(r)) for r in rows], indent=1, sort_keys=True))
        elif not rows:
            print("(no leases)")
        for r in rows if not a.json else []:
            print("%s: %s%s" % (r.get("target"), ac.describe_lease(r),
                                "" if ac.lease_live(r) else " -- stale"))
        return 0
    run = a.run or (new_run_id(a.prefix) if a.action == "take" and a.prefix else None)
    if not run:
        print("manifest: lease %s needs --run%s" % (a.action, " or --prefix" if a.action == "take" else ""),
              file=sys.stderr)
        return 2
    if a.action == "heartbeat":
        done = ac.lease_heartbeat(root, run)
        print("heartbeat of run %s: %s" % (run, " ".join(done) or "(no leases)"))
        return 0
    if a.action == "release":
        done = ac.lease_release(root, run, a.targets or None)
        print("released for run %s: %s" % (run, " ".join(done) or "(no leases)"))
        return 0
    insts = [n for part in (a.instances or []) for n in part.split(",") if n.strip()]
    if a.targets:
        by_target, of, homeless = {t: [] for t in a.targets}, {}, []
    else:
        by_target, of, homeless = lease_targets(root, ws, insts)
    taken, refused = ac.lease_take(root, run, by_target, pid=a.pid)
    print("run %s" % run)
    if a.targets:
        for t in a.targets:
            print("leased %s" % t if t in taken else
                  "skipped %s: leased by %s" % (t, ac.describe_lease(refused[t])))
        return 0
    for name in insts:
        if name in homeless:
            print("unleased %s: no home in workspace.json to lease" % name)
        elif of[name] in taken:
            print("leased %s: %s" % (name, of[name]))
        else:
            print("skipped %s: %s is leased by %s" % (name, of[name], ac.describe_lease(refused[of[name]])))
    return 0


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
    le = sp.add_parser("lease")
    le.add_argument("action", choices=["take", "heartbeat", "release", "list"])
    le.add_argument("--run")
    le.add_argument("--prefix", help="take: make a unique run id from this prefix")
    le.add_argument("--instances", action="append", help="take: instances (comma-separated)")
    le.add_argument("--targets", nargs="+", help="lease targets (home submodule paths) instead")
    le.add_argument("--pid", type=int)
    le.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        root, ws = workspace(a.workspace)
        board = board_rel(root, ws)
        if a.cmd == "lease":
            return cmd_lease(a, root, ws)
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
