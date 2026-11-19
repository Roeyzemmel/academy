#!/usr/bin/env python3
"""The first step of a scheduled (or manual) workspace job: is the workspace there?

    python3 job_preflight.py --workspace ROOT --job NAME [--need SUB,SUB] [--repo OWNER/NAME]
                             [--no-gh] [--manual CMD] [--environment NAME]

Checks, in order: ROOT is a workspace checkout (it has a ``.gitmodules``); every submodule
it names (or only those of ``--need``) is populated, at its path or, as a cloud session's
bootstrap uses it when the clone is refused, as the attached checkout (an instance home in
``workspace.json``, or the repo's checkout next to ROOT); the board repository is readable
through ``gh`` (``--repo``, else ``board.repo`` of ROOT's ``workspace.json`` when its
``board.backend`` is ``github``; skipped with ``--no-gh``, a file board, or no repo known).

Prints ``PREFLIGHT OK: <job> ...`` and exits 0, or prints ``FAILED: <job> could not start:
<every reason>`` as its FIRST line, then the manual command to run instead, and exits 2 (also
when the preflight itself fails: a crash is never a silent pass). A
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


def submodule_table(root):
    """[(path, url)] of ROOT/.gitmodules, in file order (no git needed); url may be ''."""
    rows = []
    with open(os.path.join(root, ".gitmodules"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("["):
                rows.append({})
                continue
            key, sep, value = line.partition("=")
            if sep and rows and key.strip() in ("path", "url"):
                rows[-1][key.strip()] = value.strip()
    return [(r["path"], r.get("url", "")) for r in rows if r.get("path")]


def submodule_paths(root):
    """The ``path =`` values of ROOT/.gitmodules, in file order."""
    return [p for p, _ in submodule_table(root)]


def populated(path):
    """A checked-out submodule has a ``.git`` (file or directory) and something besides it."""
    if not os.path.isdir(path):
        return False
    names = os.listdir(path)
    return ".git" in names and len(names) > 1


def load_json(path):
    """The JSON object at PATH: (dict or None, note or None)."""
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        return None, "%s unreadable (%s)" % (os.path.basename(path), e)
    if not isinstance(data, dict):
        return None, "%s is not a JSON object" % os.path.basename(path)
    return data, None


def instance_homes(root):
    """{submodule path: home} for the instances whose home the bootstrap resolved elsewhere:
    workspace.template.json names each home by its submodule path, workspace.json by where
    it actually is (an attached checkout, in a cloud session)."""
    tpl, _ = load_json(os.path.join(root, "workspace.template.json"))
    ws, _ = load_json(os.path.join(root, "workspace.json"))
    out = {}
    tinst = (tpl or {}).get("instances")
    winst = (ws or {}).get("instances")
    if not isinstance(tinst, dict) or not isinstance(winst, dict):
        return out
    for name, inst in tinst.items():
        rel = inst.get("home") if isinstance(inst, dict) else None
        got = winst.get(name)
        home = got.get("home") if isinstance(got, dict) else None
        if isinstance(rel, str) and isinstance(home, str):
            out[rel.strip("/")] = home
    return out


def locate(root, path, url, homes):
    """Where submodule PATH is usable: its own path, else the attached checkout the bootstrap
    falls back to (the instance home in workspace.json, or ``<parent of ROOT>/<repo>``, the
    repo named by URL); None when none is populated."""
    own = os.path.join(root, path)
    if populated(own):
        return own
    repo = url.rstrip("/").rsplit("/", 1)[-1]
    repo = repo[:-4] if repo.endswith(".git") else repo
    for cand in (homes.get(path), repo and os.path.join(os.path.dirname(root), repo)):
        if cand and os.path.abspath(cand) not in (os.path.abspath(root), os.path.abspath(own)) \
                and populated(cand):
            return cand
    return None


def board_repo(root):
    """(repo or None, note) from ROOT/workspace.json's board block: a dict on a GitHub board,
    a path string on the file board."""
    path = os.path.join(root, "workspace.json")
    if not os.path.isfile(path):
        return None, "no workspace.json (run the bootstrap); board repo not checked"
    ws, note = load_json(path)
    if note:
        return None, note + "; board repo not checked"
    board = ws.get("board")
    if not isinstance(board, dict):
        if board is None or isinstance(board, str):
            return None, "no GitHub board (backend file); gh not checked"
        return None, "workspace.json's board is neither a path nor an object; board repo not checked"
    if board.get("backend") != "github":
        return None, "no GitHub board (backend %s); gh not checked" % (board.get("backend") or "file")
    if not board.get("repo") or not isinstance(board.get("repo"), str):
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
    table = submodule_table(root)
    urls = dict(table)
    subs = [p for p, _ in table]
    if need:
        unknown = [s for s in need if s not in subs]
        if unknown:
            reasons.append("not a submodule of %s: %s" % (root, ", ".join(unknown)))
        subs = [s for s in need if s in subs]
    homes = instance_homes(root)
    where = {s: locate(root, s, urls[s], homes) for s in subs}
    empty = [s for s in subs if not where[s]]
    if empty:
        reasons.append("submodule not populated: %s" % ", ".join(empty))
    else:
        notes.append("%d submodules populated" % len(subs))
    attached = ["%s at %s" % (s, where[s]) for s in subs
                if where[s] and where[s] != os.path.join(root, s)]
    if attached:
        notes.append("attached checkout used for " + ", ".join(attached))
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
    try:
        reasons, notes = check(root, need=need, repo=a.repo, use_gh=not a.no_gh)
    except Exception as e:  # noqa: BLE001 - any crash must still print the FAILED line
        reasons, notes = ["the preflight itself failed (%s: %s)" % (type(e).__name__, e)], []
    if reasons:
        print("FAILED: %s could not start: %s." % (a.job, "; ".join(reasons)))
        print("Nothing was done. Run %s by hand in a session on the %s environment with the "
              "repositories selected." % (a.manual or "/run-" + a.job, a.environment))
        return FAILED_EXIT
    print("PREFLIGHT OK: %s (%s)" % (a.job, "; ".join(notes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
