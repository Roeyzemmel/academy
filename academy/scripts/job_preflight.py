#!/usr/bin/env python3
"""The first step of a scheduled (or manual) workspace job: is the workspace there?

    python3 job_preflight.py --workspace ROOT --job NAME [--need SUB,SUB] [--repo OWNER/NAME]
                             [--no-gh] [--manual CMD] [--environment NAME]

Checks, in order: ROOT is a workspace checkout (it has a ``.gitmodules``); every submodule
it names (or only those of ``--need``) is populated; the board repository is readable
through ``gh`` (``--repo``, else ``board.repo`` of ROOT's ``workspace.json`` when its
``board.backend`` is ``github``; skipped with ``--no-gh``, a file board, or no repo known).

Prints ``PREFLIGHT OK: <job> ...`` and exits 0, or prints ``FAILED: <job> could not start:
<every reason>`` as its FIRST line, then the manual command to run instead, and exits 2. A
job whose preflight fails does nothing else, and its final reply starts with that line
(T-1673: a fresh scheduled session had no repository attached, and the run said SUCCEEDED).

Generic: no machine, repo or job is named here; the caller passes them.
"""
import argparse
import json
import os
import subprocess
import sys

FAILED_EXIT = 2
GH_TIMEOUT = 30


def submodule_paths(root):
    """The ``path =`` values of ROOT/.gitmodules, in file order (no git needed)."""
    paths = []
    with open(os.path.join(root, ".gitmodules"), encoding="utf-8") as fh:
        for line in fh:
            key, sep, value = line.strip().partition("=")
            if sep and key.strip() == "path":
                paths.append(value.strip())
    return paths


def populated(path):
    """A checked-out submodule has a ``.git`` (file or directory) and something besides it."""
    if not os.path.isdir(path):
        return False
    names = os.listdir(path)
    return ".git" in names and len(names) > 1


def board_repo(root):
    """(repo or None, note) from ROOT/workspace.json's board block."""
    path = os.path.join(root, "workspace.json")
    if not os.path.isfile(path):
        return None, "no workspace.json (run the bootstrap); board repo not checked"
    try:
        with open(path, encoding="utf-8") as fh:
            board = (json.load(fh) or {}).get("board") or {}
    except (OSError, ValueError) as e:
        return None, "workspace.json unreadable (%s); board repo not checked" % e
    if board.get("backend") != "github":
        return None, "no GitHub board (backend %s); gh not checked" % (board.get("backend") or "file")
    if not board.get("repo"):
        return None, "board.backend is github but board.repo is unset; gh not checked"
    return board["repo"], None


def gh_reads(repo):
    """None when ``gh api repos/<repo>`` works, else the reason (its first stderr line)."""
    try:
        p = subprocess.run(["gh", "api", "repos/" + repo, "--jq", ".full_name"],
                           capture_output=True, text=True, timeout=GH_TIMEOUT,
                           stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return "gh is not installed, so %s cannot be read" % repo
    except (OSError, subprocess.SubprocessError) as e:
        return "gh failed on %s: %s" % (repo, e)
    if p.returncode == 0:
        return None
    err = next((ln.strip() for ln in (p.stderr or p.stdout or "").splitlines() if ln.strip()),
               "exit %d" % p.returncode)
    return "gh cannot read %s: %s" % (repo, err)


def check(root, need=None, repo=None, use_gh=True):
    """(reasons, notes): every reason the job cannot start, and what was checked."""
    reasons, notes = [], []
    if not os.path.isfile(os.path.join(root, ".gitmodules")):
        return ["no workspace checkout at %s" % root], notes
    subs = submodule_paths(root)
    if need:
        unknown = [s for s in need if s not in subs]
        if unknown:
            reasons.append("not a submodule of %s: %s" % (root, ", ".join(unknown)))
        subs = [s for s in need if s in subs]
    empty = [s for s in subs if not populated(os.path.join(root, s))]
    if empty:
        reasons.append("submodule not populated: %s" % ", ".join(empty))
    else:
        notes.append("%d submodules populated" % len(subs))
    if use_gh:
        if not repo:
            repo, note = board_repo(root)
            if note:
                notes.append(note)
        if repo:
            why = gh_reads(repo)
            if why:
                reasons.append(why)
            else:
                notes.append("board repo %s readable" % repo)
    return reasons, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--workspace", required=True, help="the workspace root to check")
    ap.add_argument("--job", required=True, help="the job's name, e.g. nightly-inbox")
    ap.add_argument("--need", help="comma-separated submodule paths (default: all)")
    ap.add_argument("--repo", help="OWNER/NAME to read with gh (default: workspace.json's board.repo)")
    ap.add_argument("--no-gh", action="store_true", help="skip the gh check")
    ap.add_argument("--manual", help="the command to run by hand instead (default: /run-<job>)")
    ap.add_argument("--environment", default="Academy-Workspace",
                    help="the environment named in the hint (default: Academy-Workspace)")
    a = ap.parse_args(argv)
    root = os.path.abspath(a.workspace)
    need = [s.strip() for s in a.need.split(",") if s.strip()] if a.need else None
    reasons, notes = check(root, need=need, repo=a.repo, use_gh=not a.no_gh)
    if reasons:
        print("FAILED: %s could not start: %s." % (a.job, "; ".join(reasons)))
        print("Nothing was done. Run %s by hand in a session on the %s environment with the "
              "repositories selected." % (a.manual or "/run-" + a.job, a.environment))
        return FAILED_EXIT
    print("PREFLIGHT OK: %s (%s)" % (a.job, "; ".join(notes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
