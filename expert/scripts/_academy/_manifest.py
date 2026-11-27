"""The checkpoint manifest: which files a ticket changed, by a snapshot diff (#101 part 1).

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.

The inbox works one ticket at a time. Before a ticket, ``manifest_snapshot`` records the dirty set
of every home of the workspace -- each checked-out submodule of ``.gitmodules`` and the
board when it is a plain directory of the superproject -- as ``{path: content hash}``
(``git status --porcelain``, untracked files included, ``.gitignore`` honoured, submodule
pointers and nested repositories left out), and writes it as the run's *claim*:
``<workspace>/.academy/run-claims/<run>-<ticket>.json`` = ``{run, ticket, started, pid,
host, board, repos: {target: {path: hash}}, failed: [targets whose status failed]}``. After the ticket, ``manifest_changed`` gives the paths
dirty now that were clean at the snapshot or whose content changed since: the ticket's
manifest ``{target: [paths relative to the target]}``. A path already dirty before the
ticket and unchanged is not claimed (it is not the ticket's work); nothing is claimed in a
home listed in ``failed``. A file above ``MANIFEST_HASH_CAP`` is compared by size and mtime.
A snapshot diff cannot tell who changed a path: concurrent runs in one checkout are kept
apart by the run leases at the end of this module (#96), one per home, so they never
share an instance.

The inbox's ``--check`` turns the claim into a *pending manifest*
(``.academy/manifests/<ticket>.json``), releases the claim, and hands the manifest to
``ship.py checkpoint --manifest``; a target that shipped leaves the pending manifest, so a
refused or failed repo is retried by the next ``--check`` of the same ticket.

The stop check (``unclaimed_dirty``) skips the paths a *live* claim's run changed since its
snapshot, the homes a live run holds the lease of, and the board files committed onto a
ticket's branch without moving the checkout, and flags every other dirty path. A claim is live while it is younger than
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

#: hours after which a claim is stale whatever its pid says (a run that died); stale
#: claims are removed at each snapshot and --check
CLAIM_MAX_HOURS = 6

#: bytes above which a file is compared by size and mtime, not hashed (a large results
#: directory must not time out the stop check)
MANIFEST_HASH_CAP = 5 * 1024 * 1024

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
        st = os.stat(path)
        if st.st_size > MANIFEST_HASH_CAP:
            return "size:%d:mtime:%d" % (st.st_size, st.st_mtime_ns)
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


def manifest_state(root, board="board", failed=None):
    """``{target: {path: hash}}`` of every dirty path of every home (``manifest_targets``);
    a target whose status cannot be read is left out, and appended to ``failed`` when a
    list is given."""
    state = {}
    for target, repo, prefix in manifest_targets(root, board):
        try:
            paths = manifest_dirty(repo, prefix)
        except ManifestError:
            if failed is not None:
                failed.append(target)
            continue
        state[target] = {p: manifest_hash(_mf_full(repo, prefix, p)) for p in paths}
    return state


def _mf_check_name(value, what):
    if not isinstance(value, str) or not _MF_NAME.match(value):
        raise ManifestError("%s %r: letters, digits and @+._- only" % (what, value))
    return value


def claim_path(root, run, ticket):
    """``.academy/run-claims/<run>-<ticket>.json``: one claim per run and ticket, so two
    runs that share a run id never overwrite each other's claim."""
    return os.path.join(manifest_dir(root), "run-claims", "%s-%s.json" % (
        _mf_check_name(run, "run id"), _mf_check_name(ticket, "ticket id")))


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
    """Record the dirty set of every home as run ``run``'s claim for ``ticket``
    (``claim_path``; a snapshot of the same run and ticket replaces it). ``run`` defaults
    to ``inbox``. ``pid``: a process of this host whose death ends the claim (none: only
    its age does). A home whose status cannot be read is listed in the claim's ``failed``
    and never claimed from. Stale claims are removed first. Returns the claim."""
    _mf_check_name(ticket, "ticket id")
    run = run or "inbox"
    _mf_check_name(run, "run id")
    prune_claims(root)
    try:
        lease_heartbeat(root, run, now)         # #96: each ticket's snapshot is its run's heartbeat
    except ManifestError:
        pass
    failed = []
    claim = {"run": run, "ticket": ticket, "started": time.time() if now is None else now,
             "pid": int(pid) if pid else None, "host": socket.gethostname(),
             "board": board, "repos": manifest_state(root, board, failed), "failed": failed}
    _mf_write(claim_path(root, run, ticket), claim)
    return claim


def prune_claims(root, now=None):
    """Remove the stale claims (``claim_live``); how many were removed."""
    n = 0
    for f, c in run_claims(root):
        if not claim_live(c, now):
            release_claim(f)
            n += 1
    return n


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
    # On Windows os.kill(pid, 0) is not a probe: signal 0 is CTRL_C_EVENT, so it sends a
    # Ctrl+C to that process group. There the claim's age alone decides (claim_live).
    if os.name == "nt":
        return True
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
    return not _mf_proc_gone(claim)


def _mf_proc_gone(doc):
    """Whether ``doc`` (a claim or a lease) names a pid of this host that no longer exists."""
    pid = doc.get("pid")
    return bool(pid and doc.get("host") == socket.gethostname() and not _mf_pid_alive(pid))


def manifest_changed(root, claim, state=None):
    """``{target: [paths]}``: what is dirty now (``state``, default read now) and was not
    at the claim's snapshot, or whose content hash changed since. Sorted, empty targets
    left out."""
    state = manifest_state(root, claim.get("board", "board")) if state is None else state
    before = claim.get("repos") or {}
    unread = set(claim.get("failed") or [])
    out = {}
    for target, now_paths in state.items():
        if target in unread:    # its dirty set before the ticket is unknown: claim nothing
            continue
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


def save_pending(root, ticket, repos, run=None):
    """Write (or, with no paths left, remove) ``ticket``'s pending manifest; its path.
    ``run``: the inbox run the ticket was worked in (``ship.py checkpoint`` reads it: a
    home leased by that run is its own, #96)."""
    path = pending_path(root, ticket)
    repos = merge_manifest(repos)
    if repos:
        doc = {"ticket": ticket, "repos": repos}
        if run:
            doc["run"] = run
        _mf_write(path, doc)
    else:
        release_claim(path)
    return path


def unclaimed_dirty(root, board="board", now=None, max_hours=None):
    """``{target: [paths]}``: every dirty path of every home except those a live claim's
    run changed since its snapshot, every path of a home a live run holds the lease of
    (#96: that run's --check ships them), and the board paths a checkpoint committed onto a
    ticket's branch without moving the checkout (``shipped_paths``, unchanged since): the
    stop check. Stale claims and leases count for nothing."""
    state = manifest_state(root, board)
    skip = {}
    for _f, c in run_claims(root):
        if claim_live(c, now, max_hours):
            for target, paths in manifest_changed(root, c, state).items():
                skip.setdefault(target, set()).update(paths)
    leased = {lease.get("target") for lease in live_leases(root, now)}
    shipped = shipped_paths(root, "board")
    out = {}
    for target, paths in state.items():
        if target in leased:        # a live run's home: its own --check ships what is there
            continue
        done = shipped if target == "board" else {}
        left = sorted(p for p in paths if p not in skip.get(target, ())
                      and not (p in done and done[p] == paths[p]))
        if left:
            out[target] = left
    return out


# ---- Run leases (#96) ------------------------------------------------------------------------
# Two inbox runs with disjoint instance sets may work in one checkout at once. Each run takes a
# *lease* on the home submodule of every instance it runs: ``.academy/leases/<target>.json`` =
# ``{target, run, pid, host, started, heartbeat, instances}``. A lease is live while its
# heartbeat is younger than ``LEASE_TIMEOUT_MINUTES``; one that names a pid of this host is
# live while that process exists, up to ``CLAIM_MAX_HOURS`` after the last heartbeat
# (``claim_live``'s host and pid rule). A target leased by another live run is not
# taken: the inbox skips that instance for the run. The board is never leased: while another
# live run holds a lease, a checkpoint commits it onto the ticket's branch without moving
# the checkout (ship.py); alone, it switches as before. Every read and
# write of the leases holds ``.academy/leases/.lock`` (create-exclusive, as ``IdLock``).

#: minutes after the last heartbeat (each ticket's snapshot) when a lease is stale
LEASE_TIMEOUT_MINUTES = 30
#: seconds after which the leases' lock file belongs to a crashed process and is broken
LEASE_LOCK_STALE = 30.0


def lease_dir(root):
    return os.path.join(manifest_dir(root), "leases")


def lease_key(target):
    """The file name of ``target``'s lease (a submodule path, '/' made '__')."""
    key = str(target or "").strip().strip("/").replace("\\", "/").replace("/", "__")
    return _mf_check_name(key, "lease target")


def lease_path(root, target):
    return os.path.join(lease_dir(root), lease_key(target) + ".json")


class _LeaseLock(object):
    def __init__(self, root, timeout=10.0):
        self.path = os.path.join(lease_dir(root), ".lock")
        self.timeout = timeout

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write("%d %f\n" % (os.getpid(), time.time()))
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > LEASE_LOCK_STALE:
                        os.remove(self.path)
                        continue
                except OSError:
                    continue
                if time.monotonic() > deadline:
                    raise ManifestError("could not lock %s" % self.path)
                time.sleep(0.05)

    def __exit__(self, *exc):
        release_claim(self.path)
        return False


def lease_live(lease, now=None, timeout_minutes=None):
    """Whether ``lease``'s run is still going: when it names a pid of this host, that
    process exists and the heartbeat is younger than ``CLAIM_MAX_HOURS`` (one ticket, a
    nested verify say, can outlast the timeout between two heartbeats); otherwise its
    heartbeat is younger than ``LEASE_TIMEOUT_MINUTES``."""
    now = time.time() if now is None else now
    minutes = LEASE_TIMEOUT_MINUTES if timeout_minutes is None else timeout_minutes
    try:
        beat = float(lease.get("heartbeat") or lease.get("started") or 0)
    except (TypeError, ValueError):
        return False
    if _mf_proc_gone(lease):
        return False
    pid_here = bool(lease.get("pid")) and lease.get("host") == socket.gethostname() and os.name != "nt"
    return now - beat <= (CLAIM_MAX_HOURS * 3600 if pid_here else minutes * 60)


def read_lease(root, target):
    """The lease of ``target`` (live or not), or None."""
    doc = _mf_read(lease_path(root, target))
    return doc if doc and doc.get("run") else None


def leases(root):
    """Every lease of the workspace, live or not, sorted by target."""
    try:
        names = sorted(n for n in os.listdir(lease_dir(root)) if n.endswith(".json"))
    except OSError:
        return []
    out = []
    for n in names:
        doc = _mf_read(os.path.join(lease_dir(root), n))
        if doc and doc.get("run"):
            out.append(doc)
    return out


def live_leases(root, now=None):
    return [lease for lease in leases(root) if lease_live(lease, now)]


def lease_holder(root, target, run=None, now=None):
    """The live lease of ``target`` held by a run other than ``run``, else None."""
    lease = read_lease(root, target)
    if lease and lease_live(lease, now) and lease.get("run") != run:
        return lease
    return None


def describe_lease(lease, now=None):
    now = time.time() if now is None else now
    try:
        age = int(max(0, now - float(lease.get("heartbeat") or 0)) // 60)
    except (TypeError, ValueError):
        age = -1
    return "run %s (%s%s, heartbeat %s min ago)" % (
        lease.get("run"), "pid %s on " % lease["pid"] if lease.get("pid") else "",
        lease.get("host") or "?", age if age >= 0 else "?")


def lease_take(root, run, targets, instances=None, pid=None, now=None):
    """Take a lease for run ``run`` on each of ``targets`` (``{target: [instances]}`` or a
    list). A target with no lease, a stale one, or one of ``run`` already is taken (a stale
    lease is taken over); one leased by another live run is not. Returns ``(taken,
    refused)``: ``[targets]`` and ``{target: lease}``."""
    _mf_check_name(run, "run id")
    now = time.time() if now is None else now
    if not isinstance(targets, dict):
        targets = {t: list(instances or []) for t in targets}
    taken, refused = [], {}
    with _LeaseLock(root):
        for target, insts in targets.items():
            path = lease_path(root, target)
            old = read_lease(root, target)
            if old and old.get("run") != run and lease_live(old, now):
                refused[target] = old
                continue
            started = old.get("started") if old and old.get("run") == run else now
            _mf_write(path, {"target": target, "run": run, "pid": int(pid) if pid else None,
                             "host": socket.gethostname(), "started": started,
                             "heartbeat": now, "instances": sorted(set(insts or []))})
            taken.append(target)
    return taken, refused


def lease_heartbeat(root, run, now=None):
    """Refresh the heartbeat of every lease ``run`` holds; the targets refreshed."""
    _mf_check_name(run, "run id")
    now = time.time() if now is None else now
    done = []
    if not os.path.isdir(lease_dir(root)):
        return done
    with _LeaseLock(root):
        for lease in leases(root):
            if lease.get("run") == run and lease.get("target"):
                _mf_write(lease_path(root, lease["target"]), dict(lease, heartbeat=now))
                done.append(lease["target"])
    return done


def lease_release(root, run, targets=None):
    """Remove the leases ``run`` holds (of ``targets`` only, when given); the targets
    released. Another run's lease is never removed."""
    _mf_check_name(run, "run id")
    done = []
    if not os.path.isdir(lease_dir(root)):
        return done
    with _LeaseLock(root):
        for lease in leases(root):
            t = lease.get("target")
            if lease.get("run") == run and t and (targets is None or t in targets):
                release_claim(lease_path(root, t))
                done.append(t)
    return done


def instance_target(root, home):
    """The lease target of an instance whose home is ``home``: its path relative to the
    workspace root (a submodule path), else the home's directory name (an attached checkout
    outside the root); None without a home."""
    if not home:
        return None
    h, top = os.path.realpath(str(home)), os.path.realpath(str(root))
    rel = os.path.relpath(h, top).replace(os.sep, "/")
    if rel == "." or rel.startswith(".."):
        return os.path.basename(h.rstrip(os.sep)) or None
    return rel


# ---- Board paths committed without moving the checkout (#96) -----------------------------------
# A checkpoint commits the board onto the ticket's branch with a temporary index, so the
# checkout's HEAD keeps its branch and the committed files stay dirty against it until that
# branch is merged. ``.academy/shipped/<target>.json`` = ``{path: content hash}`` records them, so
# the stop check and a later ``--only board`` checkpoint pass over a file committed and unchanged
# since.


def shipped_file(root, target):
    return os.path.join(manifest_dir(root), "shipped", lease_key(target) + ".json")


def shipped_paths(root, target):
    """``{path relative to the target: content hash}`` committed without moving the checkout."""
    doc = _mf_read(shipped_file(root, target))
    paths = (doc or {}).get("paths")
    return paths if isinstance(paths, dict) else {}


def record_shipped(root, target, prefix, committed, dirty=None):
    """Record ``committed`` (``[paths relative to the target]``, each hashed now) as committed
    onto a ticket's branch without moving the checkout; ``prefix`` is the target's directory
    relative to ``root``. With ``dirty`` (the target's dirty paths now) the entries no longer
    dirty -- merged since, or reverted -- are dropped. Returns the recorded map."""
    full = shipped_file(root, target)
    paths = dict(shipped_paths(root, target))
    if dirty is not None:
        keep = set(dirty)
        paths = {p: h for p, h in paths.items() if p in keep}
    for p in committed:
        paths[p] = manifest_hash(_mf_full(str(root), prefix, p))
    if paths:
        _mf_write(full, {"target": target, "paths": paths})
    else:
        release_claim(full)
    return paths
