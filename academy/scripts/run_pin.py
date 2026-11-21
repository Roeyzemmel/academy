#!/usr/bin/env python3
"""Pin the academy code a workflow run uses (#97).

    py run_pin.py [--repo DIR] start [--label L] [--keep-days N] [--json]
    py run_pin.py [--repo DIR] end --run RUN [--json]
    py run_pin.py [--repo DIR] live [--json]
    py run_pin.py [--repo DIR] clean [--keep-days N] [--json]

A long workflow run (the inbox, a campaign) used to read its nested workflows and every
script it calls from the academy checkout's current branch, so a merge, a branch switch
or a ``ship.py publish`` during the run changed its code half-way. ``start`` takes a
detached ``git worktree`` of the academy repo at the commit its HEAD points to now,
``<main checkout>/.worktrees/run-<sha12>`` (reused when it is already there for that
commit), and records the run as live in ``.worktrees/live/<run>.json``; the workflow then
gives that worktree as the root of everything it runs. ``end`` removes the run's marker.
``live`` lists the live runs (``ship.py merge`` and ``publish`` warn on them). ``clean``
removes the pins that no live run uses and that nothing used for ``--keep-days`` days
(default ``KEEP_DAYS``); ``start`` runs it first.

A marker is stale (its run is taken for dead) when it is older than ``RUN_MAX_HOURS``
hours, or when it names a process of this host that is gone: the first ancestor of
``start`` that is not a shell or an interpreter, which is the session that ran the
workflow (found on Linux only; elsewhere the age alone decides).

``DIR`` is any checkout of the academy repo (default: the one this script is in). A
directory that is no git checkout (an installed plugin's cache, a copy at a version) is
left as it is: ``start`` prints ``"pinned": false`` with the reason, and writes nothing.
Uncommitted changes of the checkout are not in the pin; ``start`` counts them (``dirty``).

``.worktrees/`` carries its own ``.gitignore`` (``*``), so the checkout stays clean
whatever its own ignore file says. Standard library only; ``ship.py`` imports it.
"""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time

#: the folder of the pins, under the main checkout
PIN_DIR = ".worktrees"
#: the live markers' folder, inside PIN_DIR
LIVE_DIR = "live"
#: a pin is ``run-<first SHA_LEN hex digits of the commit>``
PIN_PREFIX = "run-"
SHA_LEN = 12
#: days a pin no live run uses is kept after its last use (a hand-back of a finished run,
#: /researcher:prove with the run's root, still finds its code)
KEEP_DAYS = 2.0
#: hours after which a live marker is stale whatever its pid says (a run that died)
RUN_MAX_HOURS = 12.0
#: process names skipped when looking for the session above ``start``
_WRAPPERS = {"bash", "sh", "dash", "zsh", "fish", "ksh", "env", "timeout", "nohup", "stdbuf",
             "sudo", "su", "bwrap", "sandbox-exec", "git", "py", "python", "python3"}
_RUN = re.compile(r"^[A-Za-z0-9@+._-]{1,120}$")
_PIN_NAME = re.compile(r"^%s[0-9a-f]{%d}$" % (PIN_PREFIX, SHA_LEN))


class PinError(Exception):
    """A git call that failed, or a malformed argument."""


def git(repo, *args, check=True):
    p = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    if p.returncode and check:
        raise PinError("git %s: %s" % (" ".join(args), (p.stderr or p.stdout).strip()))
    return p.stdout.strip() if not p.returncode else ""


def is_pin_path(path):
    """Whether ``path`` is a pin: ``<checkout>/.worktrees/run-<sha12>`` (the same rule as
    the academy library's ``repo_root``)."""
    path = os.path.normpath(os.path.abspath(str(path)))
    return bool(_PIN_NAME.match(os.path.basename(path))) and \
        os.path.basename(os.path.dirname(path)) == PIN_DIR


def _same(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def toplevel(path):
    """The checkout ``path`` is in, or None when it is in none."""
    if not os.path.isdir(path):
        return None
    out = git(path, "rev-parse", "--show-toplevel", check=False)
    return os.path.abspath(out) if out else None


def main_checkout(top):
    """The main working tree of the repository of checkout ``top`` (ship.py's rule: a
    linked worktree's main tree is where its common git dir says, which for an absorbed
    submodule is ``core.worktree``)."""
    if is_pin_path(top):
        return os.path.dirname(os.path.dirname(os.path.abspath(top)))
    gd = git(top, "rev-parse", "--absolute-git-dir", check=False)
    common = git(top, "rev-parse", "--git-common-dir", check=False)
    if not gd or not common:
        return top
    common = os.path.realpath(common if os.path.isabs(common) else os.path.join(top, common))
    if os.path.normcase(os.path.realpath(gd)) == os.path.normcase(common):
        return top
    wt = git(common, "config", "--file", os.path.join(common, "config"), "--get",
             "core.worktree", check=False)
    if wt:
        return os.path.abspath(wt if os.path.isabs(wt) else os.path.join(common, wt))
    if os.path.basename(common) == ".git":
        return os.path.dirname(common)
    return top


def pin_dir(main, create=False):
    d = os.path.join(main, PIN_DIR)
    if create:
        os.makedirs(os.path.join(d, LIVE_DIR), exist_ok=True)
        ign = os.path.join(d, ".gitignore")
        if not os.path.isfile(ign):
            with open(ign, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("# pinned code of workflow runs (run_pin.py): never committed\n*\n")
    return d


def _write(path, doc):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _proc_stat(pid):
    """``(name, ppid, starttime)`` of ``pid`` from /proc, or None."""
    try:
        with open("/proc/%d/stat" % int(pid), encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except (OSError, ValueError):
        return None
    name = text[text.find("(") + 1:text.rfind(")")]
    rest = text[text.rfind(")") + 2:].split()
    try:
        return name, int(rest[1]), rest[19]
    except (IndexError, ValueError):
        return None


def _wrapper(name):
    n = name.lower()
    if n.endswith(".exe"):
        n = n[:-4]
    return n in _WRAPPERS or n.startswith("python3.")


def session_pid(start=None):
    """``(pid, starttime)`` of the first ancestor of this process that is not a shell or an
    interpreter (the session that ran the workflow), else ``(None, None)``. Linux only."""
    pid = os.getppid() if start is None else start
    for _ in range(10):
        st = _proc_stat(pid)
        if not st:
            return None, None
        name, ppid, started = st
        if not _wrapper(name):
            return pid, started
        if ppid <= 1:
            return None, None
        pid = ppid
    return None, None


def pid_alive(pid, started=None):
    """Whether process ``pid`` of this host still exists (and, with ``started``, is the
    same process). Where that cannot be told it counts as alive: the age decides. Never
    signals a process (``os.kill(pid, 0)`` terminates it on Windows)."""
    if os.name == "nt" or not os.path.isdir("/proc"):
        return True
    st = _proc_stat(pid)
    if st is None:
        return False
    return started is None or str(st[2]) == str(started)


def marker_live(m, now=None, max_hours=RUN_MAX_HOURS, alive=pid_alive):
    """Whether live marker ``m``'s run is still going: younger than ``max_hours`` and, when
    it names a process of this host, that process exists."""
    now = time.time() if now is None else now
    try:
        started = float(m.get("started") or 0)
    except (TypeError, ValueError):
        return False
    if not started or now - started > max_hours * 3600:
        return False
    if m.get("pid") and m.get("host") == socket.gethostname() and not alive(m["pid"], m.get("pid_start")):
        return False
    return True


def markers(main):
    """``[(file, marker)]`` of the repository whose main checkout is ``main``."""
    d = os.path.join(main, PIN_DIR, LIVE_DIR)
    try:
        names = sorted(n for n in os.listdir(d) if n.endswith(".json"))
    except OSError:
        return []
    out = []
    for n in names:
        m = _read(os.path.join(d, n))
        if m is not None:
            out.append((os.path.join(d, n), m))
    return out


def live(repo, now=None, prune=False, alive=pid_alive):
    """The live runs' markers (oldest first); with ``prune`` the stale ones are removed."""
    top = toplevel(repo)
    if not top:
        return []
    out = []
    for f, m in markers(main_checkout(top)):
        if marker_live(m, now, alive=alive):
            out.append(m)
        elif prune:
            try:
                os.remove(f)
            except OSError:
                pass
    return sorted(out, key=lambda m: float(m.get("started") or 0))


def _stamp(base, name):
    return os.path.join(base, name + ".json")


def _remove_pin(main, path):
    git(main, "worktree", "remove", "--force", path, check=False)
    if os.path.isdir(path):                      # a directory git no longer knows
        shutil.rmtree(path, ignore_errors=True)
    try:
        os.remove(_stamp(os.path.dirname(path), os.path.basename(path)))
    except OSError:
        pass


def clean(repo, now=None, keep_days=KEEP_DAYS, keep=(), alive=pid_alive):
    """Remove the pins no live run uses whose last use is older than ``keep_days``; the
    names in ``keep`` stay. Returns the removed pins' names."""
    now = time.time() if now is None else now
    top = toplevel(repo)
    if not top:
        return []
    main = main_checkout(top)
    base = os.path.join(main, PIN_DIR)
    try:
        names = sorted(n for n in os.listdir(base) if _PIN_NAME.match(n))
    except OSError:
        return []
    used = {os.path.basename(os.path.normpath(m.get("root") or "")) for m in live(main, now, True, alive)}
    gone = []
    for n in names:
        if n in used or n in keep:
            continue
        st = _read(_stamp(base, n)) or {}
        try:
            last = float(st.get("used") or 0) or os.path.getmtime(os.path.join(base, n))
        except (OSError, TypeError, ValueError):
            last = 0
        if now - last > keep_days * 86400:
            _remove_pin(main, os.path.join(base, n))
            gone.append(n)
    if gone:
        git(main, "worktree", "prune", check=False)
    return gone


def _new_run(label, now):
    label = re.sub(r"[^A-Za-z0-9@+._-]", "-", label or "run")[:60] or "run"
    return "%s-%s-%d" % (label, time.strftime("%Y%m%dT%H%M%S", time.gmtime(now)), os.getpid())


def start(repo, label=None, now=None, keep_days=KEEP_DAYS, alive=pid_alive):
    """Pin checkout ``repo`` at its HEAD for one run (see the module docstring); the pin's
    description, as printed."""
    now = time.time() if now is None else now
    repo = os.path.abspath(repo)
    top = toplevel(repo)
    if not top:
        return {"pinned": False, "root": repo, "sha": None, "run": None,
                "why": "%s is no git checkout (an installed plugin is already a copy at a "
                       "version): the run reads it as it is" % repo}
    sha = git(top, "rev-parse", "HEAD")
    dirty = len([ln for ln in git(top, "status", "--porcelain", "--untracked-files=no",
                                  check=False).splitlines() if ln.strip()])
    main = main_checkout(top)
    base = pin_dir(main, create=True)
    name = PIN_PREFIX + sha[:SHA_LEN]
    path = os.path.join(base, name)
    if is_pin_path(top):                         # started from a pin: that pin
        path, name = top, os.path.basename(top)
    cleaned = clean(main, now, keep_days, keep=(name,), alive=alive)
    # a directory of the main checkout that is no worktree answers with the main's HEAD
    own = toplevel(path)
    reused = bool(own) and _same(own, path) and git(path, "rev-parse", "HEAD", check=False) == sha
    if not reused:
        if os.path.exists(path):
            _remove_pin(main, path)
        git(main, "worktree", "prune", check=False)
        git(main, "worktree", "add", "--detach", "--quiet", path, sha)
    st = _read(_stamp(base, name)) or {"sha": sha, "created": now}
    st["used"] = now
    _write(_stamp(base, name), st)
    run = _new_run(label, now)
    pid, pid_start = session_pid()
    marker = {"run": run, "label": label or "", "sha": sha, "root": path, "source": top,
              "started": now, "host": socket.gethostname(), "pid": pid, "pid_start": pid_start}
    _write(os.path.join(base, LIVE_DIR, run + ".json"), marker)
    return {"pinned": True, "root": path, "sha": sha, "run": run, "source": top,
            "reused": reused, "dirty": dirty, "cleaned": cleaned,
            "why": "pinned at %s%s" % (sha[:SHA_LEN], "; %d uncommitted change(s) of %s are "
                                       "not in the pin" % (dirty, top) if dirty else "")}


def end(repo, run, now=None):
    """End run ``run``: its marker is removed and its pin's last use is now."""
    if not _RUN.match(run or ""):
        raise PinError("bad run id %r" % run)
    now = time.time() if now is None else now
    top = toplevel(repo)
    if not top:
        return {"ended": False, "run": run, "why": "no git checkout"}
    base = os.path.join(main_checkout(top), PIN_DIR)
    f = os.path.join(base, LIVE_DIR, run + ".json")
    m = _read(f)
    if m is None:
        return {"ended": False, "run": run, "why": "no live marker for this run"}
    os.remove(f)
    name = os.path.basename(os.path.normpath(m.get("root") or ""))
    st = _read(_stamp(base, name))
    if st is not None:
        st["used"] = now
        _write(_stamp(base, name), st)
    return {"ended": True, "run": run, "sha": m.get("sha"), "root": m.get("root")}


def describe(m, now=None):
    """One line for a live run (``ship.py``'s warning)."""
    now = time.time() if now is None else now
    mins = int(max(0, now - float(m.get("started") or now)) // 60)
    age = "%dh%02dm" % (mins // 60, mins % 60) if mins >= 60 else "%dm" % mins
    return "%s (live for %s, pinned at %s in %s)" % (m.get("run"), age, str(m.get("sha") or "?")[:SHA_LEN],
                                                     m.get("root"))


def main(argv=None):
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default=here, help="a checkout of the academy repo (default: this one)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("start")
    s.add_argument("--label", default="run")
    s.add_argument("--keep-days", type=float, default=KEEP_DAYS)
    s.add_argument("--json", action="store_true")
    e = sp.add_parser("end")
    e.add_argument("--run", required=True)
    e.add_argument("--json", action="store_true")
    li = sp.add_parser("live")
    li.add_argument("--json", action="store_true")
    c = sp.add_parser("clean")
    c.add_argument("--keep-days", type=float, default=KEEP_DAYS)
    c.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "start":
            r = start(a.repo, a.label, keep_days=a.keep_days)
            text = "%s %s" % ("pinned" if r["pinned"] else "not pinned:", r["root"] if r["pinned"] else r["why"])
        elif a.cmd == "end":
            r = end(a.repo, a.run)
            text = "ended %s" % a.run if r["ended"] else "not ended: %s" % r["why"]
        elif a.cmd == "live":
            r = live(a.repo, prune=False)
            text = "\n".join(describe(m) for m in r) or "no live run"
        else:
            r = clean(a.repo, keep_days=a.keep_days)
            text = "removed %d pin(s)%s" % (len(r), ": " + ", ".join(r) if r else "")
    except PinError as err:
        print("run_pin: %s" % err, file=sys.stderr)
        return 1
    print(json.dumps(r, sort_keys=True) if a.json else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
