"""The checkpoint manifest: which files a ticket changed, by a snapshot diff (#101 part 1).

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.

The inbox works one ticket at a time. Before a ticket, ``manifest_snapshot`` records the dirty set
of every home of the workspace -- each checked-out submodule of ``.gitmodules`` and the
board when it is a plain directory of the superproject -- as ``{path: content hash}``
(``git status --porcelain``, untracked files included, ``.gitignore`` honoured, submodule
pointers and nested repositories left out), and writes it as the run's *claim*:
``<workspace>/.academy/run-claims/<run>.json`` = ``{run, ticket, started, pid, host,
repos: {target: {path: hash}}}``. After the ticket, ``manifest_changed`` gives the paths
dirty now that were clean at the snapshot or whose content changed since: the ticket's
manifest ``{target: [paths relative to the target]}``. A path already dirty before the
ticket and unchanged is not claimed (it is not the ticket's work).

The inbox's ``--check`` turns the claim into a *pending manifest*
(``.academy/manifests/<ticket>.json``), releases the claim, and hands the manifest to
``ship.py checkpoint --manifest``; a target that shipped leaves the pending manifest, so a
refused or failed repo is retried by the next ``--check`` of the same ticket.

The stop check (``unclaimed_dirty``) skips the paths a *live* claim's run changed since its
snapshot and flags every other dirty path. A claim is live while it is younger than
``CLAIM_MAX_HOURS`` and, when it names a pid of this host, that process exists.

``.academy/`` carries its own ``.gitignore`` (``*``), so none of this is ever committed or
shows as untracked in the superproject.
"""

import hashlib
import json
import os
import re
import socket
import subprocess
import time

#: hours after which a claim is stale whatever its pid says (a run that died)
CLAIM_MAX_HOURS = 12

#: a run id or a ticket id usable as a file name
_MF_NAME = re.compile(r"^[A-Za-z0-9@+._-]{1,120}$")


class ManifestError(Exception):
    """A malformed argument (run id, ticket id) or an unreadable workspace layout."""


def manifest_dir(root):
    """``<root>/.academy``, created with a ``.gitignore`` of ``*`` (nothing in it is ever
    tracked, and the directory never shows as untracked)."""
    d = os.path.join(str(root), ".academy")
    os.makedirs(d, exist_ok=True)
    gi = os.path.join(d, ".gitignore")
    if not os.path.isfile(gi):
        with open(gi, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("*\n")
    return d


def _mf_git(repo, *args):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, stdin=subprocess.DEVNULL)
    if p.returncode:
        raise ManifestError("git %s in %s: %s" % (" ".join(args), repo,
                                                  p.stderr.decode("utf-8", "replace").strip()))
    return p.stdout.decode("utf-8", "surrogateescape")


def _mf_submodules(root):
    subs = []
    try:
        with open(os.path.join(str(root), ".gitmodules"), encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"^\s*path\s*=\s*(.+?)\s*$", line)
                if m:
                    subs.append(m.group(1).replace("\\", "/"))
    except OSError:
        pass
    return subs


def manifest_targets(root, board="board"):
    """``[(target, repo, prefix)]``: every checked-out submodule (``prefix`` None) and the
    board when it is a plain directory of the superproject (``target`` ``board``, ``repo``
    the workspace root, ``prefix`` its directory relative to it). ``board`` is the board's
    path (relative to ``root`` or absolute; workspace.json ``board``)."""
    root = str(root)
    out = []
    subs = _mf_submodules(root)
    for s in subs:
        repo = os.path.join(root, s)
        if os.path.exists(os.path.join(repo, ".git")):
            out.append((s, repo, None))
    if board:
        b = board if os.path.isabs(board) else os.path.join(root, board)
        b, top = os.path.realpath(b), os.path.realpath(root)
        rel = os.path.relpath(b, top).replace(os.sep, "/")
        if (os.path.isdir(b) and not rel.startswith("..") and rel != "."
                and rel not in subs and not os.path.exists(os.path.join(b, ".git"))
                and os.path.exists(os.path.join(root, ".git"))):
            out.append(("board", root, rel))
    return out


def manifest_dirty(repo, prefix=None):
    """The dirty paths of ``repo`` (under ``prefix``, and then relative to it): tracked
    changes, deletions, both sides of a staged rename, untracked files one by one;
    ignored files, submodule pointers and untracked nested repositories left out."""
    spec = ["--", ":(top)%s/" % prefix] if prefix else []
    raw = _mf_git(repo, "status", "--porcelain", "-z", "--untracked-files=all", *spec)
    links = {line.split("\t", 1)[1] for line in _mf_git(repo, "ls-files", "-s", "-z", *spec).split("\0")
             if line.startswith("160000 ") and "\t" in line}
    fields, out, i = raw.split("\0"), [], 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        paths = [path]
        if xy[0] in "RC" and i < len(fields):
            paths.append(fields[i])           # -z: the source path is the next field
            i += 1
        for p in paths:
            p = p.rstrip("/")
            if p in links or (xy == "??" and os.path.exists(os.path.join(repo, p, ".git"))):
                continue
            if prefix:
                if not p.startswith(prefix.rstrip("/") + "/"):
                    continue
                p = p[len(prefix.rstrip("/")) + 1:]
            if p not in out:
                out.append(p)
    return out


def manifest_hash(path):
    """A content hash of ``path``: sha1 of its bytes, ``-`` when it does not exist,
    ``dir`` for a directory, ``link:<target>`` for a symlink."""
    try:
        if os.path.islink(path):
            return "link:" + os.readlink(path)
        if os.path.isdir(path):
            return "dir"
        h = hashlib.sha1()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        return "-"
    except OSError:
        return "?"


def _mf_full(repo, prefix, rel):
    return os.path.join(repo, *(([prefix] if prefix else []) + rel.split("/")))


def manifest_state(root, board="board"):
    """``{target: {path: hash}}`` of every dirty path of every home (``manifest_targets``);
    a target whose status cannot be read is left out."""
    state = {}
    for target, repo, prefix in manifest_targets(root, board):
        try:
            paths = manifest_dirty(repo, prefix)
        except ManifestError:
            continue
        state[target] = {p: manifest_hash(_mf_full(repo, prefix, p)) for p in paths}
    return state


def _mf_check_name(value, what):
    if not isinstance(value, str) or not _MF_NAME.match(value):
        raise ManifestError("%s %r: letters, digits and @+._- only" % (what, value))
    return value


def claim_path(root, run):
    return os.path.join(manifest_dir(root), "run-claims", _mf_check_name(run, "run id") + ".json")


def _mf_write(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def _mf_read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def manifest_snapshot(root, ticket, run=None, board="board", pid=None, now=None):
    """Record the dirty set of every home as run ``run``'s claim for ``ticket`` (replacing
    the run's previous claim: one ticket at a time). ``run`` defaults to ``inbox-<ticket>``.
    ``pid``: a process of this host whose death ends the claim (none: only its age does).
    Returns the claim."""
    _mf_check_name(ticket, "ticket id")
    run = run or "inbox-" + ticket
    claim = {"run": run, "ticket": ticket, "started": time.time() if now is None else now,
             "pid": int(pid) if pid else None, "host": socket.gethostname(),
             "board": board, "repos": manifest_state(root, board)}
    _mf_write(claim_path(root, run), claim)
    return claim


def run_claims(root):
    """``[(claim file, claim)]`` of the workspace, newest first."""
    d = os.path.join(manifest_dir(root), "run-claims")
    try:
        names = [n for n in os.listdir(d) if n.endswith(".json")]
    except OSError:
        return []
    out = []
    for n in names:
        doc = _mf_read(os.path.join(d, n))
        if doc and isinstance(doc.get("repos"), dict):
            out.append((os.path.join(d, n), doc))
    out.sort(key=lambda fc: float(fc[1].get("started") or 0), reverse=True)
    return out


def find_claim(root, ticket):
    """``(claim file, claim)`` of the newest claim for ``ticket``, else ``(None, None)``."""
    for f, c in run_claims(root):
        if c.get("ticket") == ticket:
            return f, c
    return None, None


def _mf_pid_alive(pid):
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError, ValueError, TypeError, OverflowError):
        return True        # it exists but is not ours, or this platform cannot say
    return True


def claim_live(claim, now=None, max_hours=None):
    """Whether ``claim``'s run is still going: younger than ``max_hours`` (default
    ``CLAIM_MAX_HOURS``) and, when it names a pid of this host, that process exists."""
    now = time.time() if now is None else now
    hours = CLAIM_MAX_HOURS if max_hours is None else max_hours
    try:
        started = float(claim.get("started") or 0)
    except (TypeError, ValueError):
        return False
    if now - started > hours * 3600:
        return False
    pid = claim.get("pid")
    if pid and claim.get("host") == socket.gethostname() and not _mf_pid_alive(pid):
        return False
    return True


def manifest_changed(root, claim, state=None):
    """``{target: [paths]}``: what is dirty now (``state``, default read now) and was not
    at the claim's snapshot, or whose content hash changed since. Sorted, empty targets
    left out."""
    state = manifest_state(root, claim.get("board", "board")) if state is None else state
    before = claim.get("repos") or {}
    out = {}
    for target, now_paths in state.items():
        was = before.get(target) or {}
        changed = sorted(p for p, h in now_paths.items() if p not in was or was[p] != h)
        if changed:
            out[target] = changed
    return out


def release_claim(path):
    try:
        os.remove(path)
    except OSError:
        pass


def pending_path(root, ticket):
    return os.path.join(manifest_dir(root), "manifests",
                        _mf_check_name(ticket, "ticket id") + ".json")


def load_pending(root, ticket):
    """The pending manifest of ``ticket`` (``{ticket, repos}``) or None."""
    doc = _mf_read(pending_path(root, ticket))
    return doc if doc and isinstance(doc.get("repos"), dict) else None


def merge_manifest(*parts):
    """The union of ``{target: [paths]}`` maps, sorted, empty targets left out."""
    out = {}
    for part in parts:
        for target, paths in (part or {}).items():
            out.setdefault(target, set()).update(p for p in paths or [] if p)
    return {t: sorted(ps) for t, ps in out.items() if ps}


def save_pending(root, ticket, repos):
    """Write (or, with no paths left, remove) ``ticket``'s pending manifest; its path."""
    path = pending_path(root, ticket)
    repos = merge_manifest(repos)
    if repos:
        _mf_write(path, {"ticket": ticket, "repos": repos})
    else:
        release_claim(path)
    return path


def unclaimed_dirty(root, board="board", now=None, max_hours=None):
    """``{target: [paths]}``: every dirty path of every home except those a live claim's
    run changed since its snapshot (the stop check). Stale claims count for nothing."""
    state = manifest_state(root, board)
    skip = {}
    for _f, c in run_claims(root):
        if claim_live(c, now, max_hours):
            for target, paths in manifest_changed(root, c, state).items():
                skip.setdefault(target, set()).update(paths)
    out = {}
    for target, paths in state.items():
        left = sorted(p for p in paths if p not in skip.get(target, ()))
        if left:
            out[target] = left
    return out
