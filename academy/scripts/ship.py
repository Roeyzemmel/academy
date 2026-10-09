#!/usr/bin/env python3
"""Branch, commit and push in one repo of an academy workspace, one plain command per step.

    py scripts/ship.py [--workspace DIR] status
    py scripts/ship.py start  <sub> <topic> [--role R] [--worktree]
    py scripts/ship.py commit <sub> -m MSG (--paths P... | --all)
    py scripts/ship.py push   <sub>
    py scripts/ship.py accept-baseline <sub>                         # Author homes: rewrite the gate baseline
    py scripts/ship.py ship   <sub> -m MSG (--paths P... | --all)    # commit + push
    py scripts/ship.py merge  <sub> <branch> --sha TIP [-m MSG] [--bump]   # reviewed branch -> local main
    py scripts/ship.py publish <sub> --sha MAIN_TIP                  # local main -> origin main
    py scripts/ship.py checkpoint --ticket T-NNNN [--role R] [--title T] [--remote NAME] [--only SUB...]

This is the academy plugin's ``academy/scripts/ship.py``; a workspace keeps a one-line shim
at ``scripts/ship.py`` that runs it with ``--workspace <its root>`` and the same arguments,
so the allowlisted ``py scripts/ship.py ...`` strings keep matching. The workspace root is
``--workspace`` (a directory, or its workspace.json), else the nearest directory at or above
the cwd holding workspace.json (or workspace.template.json), else ``$ACADEMY_WORKSPACE``,
else the directory holding this academy checkout when that is a workspace, else the
nearest directory above the cwd with a .gitmodules.

A target ``<sub>`` is a submodule path from the workspace's .gitmodules, or ``board``
when the workspace's board (workspace.json ``board``, default ``board/``) is a plain
directory of the superproject: then the repo is the workspace itself and every staging,
status and commit is limited to the pathspec ``board/`` (``--paths`` are relative to
``board/``), so nothing outside it is committed, and never a submodule pointer.

Works from the workspace root in an ordinary CLI session (git is run with ``-C <sub>``
from here; nothing needs a worktree), and equally from a session isolated in a
worktree of the superproject or of the submodule (``--repo PATH`` names the checkout; it
must share ``<workspace>/<sub>``'s git-common-dir, i.e. be that checkout or one of its
worktrees). ``--paths`` are relative to the submodule, not the cwd.

In an Author home ``commit``/``ship``/``checkpoint``/``merge`` run the academy commit gate
(``gate_check_detail``, or ``gate_check`` from an older academy checkout) with
``--no-registry`` added to the checker's args, so a gate run never rewrites the tracked
Drafts/statements.md. Mode 'unavailable' (the checker could not run, or exited non-zero
without a finding line) is reported with its cause: ``commit``/``ship``/``checkpoint`` go
on, ``merge`` refuses. The merge summary names changed gate inputs (.claude/academy.json,
the baseline file) with a ``gate inputs changed:`` line.

Branches are ``<YYYY-MM-DD>/<topic>/<role>`` (UTC date, kebab-case topic, role one of
author, expert, researcher, scientist, human). The role defaults to the ``role`` in the
submodule's ``.claude/academy.json``, else ``human``. By construction ``start/commit/push/
ship`` never touch ``main``/``master``, and nothing ever forces, deletes a branch or
rewrites history, or stages what it was not told to (``--paths`` or an explicit ``--all``).

``merge`` and ``publish`` are the human's steps and are deliberately not allowlisted: the
permission prompt is the approval, tied to exact SHAs (``accept-baseline`` prompts too). ``merge`` takes a template branch
whose remote tip equals ``--sha`` into local ``main`` (``--no-ff``; strict gate on the
merged tree in an Author home; refusal leaves the repo as it was) and never pushes;
``publish`` pushes ``main`` only when its tip equals ``--sha``. The superproject's
submodule pointer is committed only by ``merge --bump``, as a separate commit.

``checkpoint`` ends an inbox ticket: in every checked-out submodule (and the superproject's
``board/``) with uncommitted changes (``add -A``, .gitignore honoured) or unpushed commits on ``<date>/<ticket-id>/<role>``
it switches to that branch (changes carried along), runs the Author gate as ``commit``
does, commits ``<TICKET>: <title>`` (plus the line in env ``SHIP_TRAILER`` if set) and
pushes the branch to ``shipRemote`` from workspace.json (default ``origin``). One line
per repo, the committed files listed under it (20 at most); exit 1 if any repo was
refused or failed to push (commits are kept locally). Untracked nested repositories and
worktrees are never committed (they are listed as skipped); a dirty repo on a branch that
is neither main/master nor a template branch is refused without switching; one on
another ticket's template branch is carried over with a note. A refused repo's line says
which branch it was left on and whether its changes are staged. Submodule pointers
(tracked gitlinks) are never staged. ``board`` is in scope whatever ``board.backend`` is
(with ``github`` the tickets are on GitHub, but packets and deep-dives are files there);
as a plain directory of the superproject only ``board/`` paths are staged and committed
(``add -A -- board/``, ``commit -- board/``), whatever else is dirty or staged there.
The academy plugin's ``inbox.py --check`` runs ``checkpoint --only <the ticket's repos>``
itself after a finished ticket: with ``--only`` the other submodules are not touched and
a dirty repo of the set that is on main/master is refused instead of moved.

Standard library only.
"""
import argparse
import copy
import datetime
import importlib.util
import json
import os
import re
import subprocess
import sys

#: the academy checkout (marketplace root) this script belongs to
ACADEMY_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#: the workspace root; set by ``main`` (``find_workspace``), or by a caller/test directly
ROOT = None
ROLES = ("author", "expert", "researcher", "scientist", "human")
BRANCH = re.compile(r"^\d{4}-\d{2}-\d{2}/[a-z0-9][a-z0-9-]*/(%s)$" % "|".join(ROLES))
PROTECTED = ("main", "master")


class Refuse(Exception):
    pass


def git_env():
    """The environment for every git call: never wait on an editor, pager or prompt
    (every commit and merge here passes its message explicitly)."""
    env = dict(os.environ)
    env.update({"GIT_EDITOR": "true", "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat",
                "GIT_MERGE_AUTOEDIT": "no", "GCM_INTERACTIVE": "never"})
    return env


def git(repo, *args, check=True, strip=True):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                       env=git_env(), stdin=subprocess.DEVNULL)
    if check and p.returncode:
        raise Refuse("git %s failed in %s: %s" % (" ".join(args), repo, (p.stderr or p.stdout).strip()))
    return p.stdout.strip() if strip else p.stdout


WS_MARKERS = ("workspace.json", "workspace.template.json")


def _ws_dir(path):
    """``path`` (a directory, or a file in it such as workspace.json) as a directory, or None."""
    if not path:
        return None
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isfile(path) or (path.endswith(".json") and not os.path.isdir(path)):
        path = os.path.dirname(path)
    return path if os.path.isdir(path) else None


def _walk_up(start, names):
    d = os.path.abspath(start)
    while True:
        if any(os.path.exists(os.path.join(d, n)) for n in names):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def find_workspace(explicit=None, cwd=None):
    """The workspace root (see the module docstring for the order); Refuse if none."""
    if explicit:
        d = _ws_dir(explicit)
        if not d:
            raise Refuse("--workspace %s is not a directory or a file in one" % explicit)
        return d
    cwd = cwd or os.getcwd()
    d = _walk_up(cwd, WS_MARKERS)
    if d:
        return d
    d = _ws_dir(os.environ.get("ACADEMY_WORKSPACE"))
    if d:
        return d
    parent = os.path.dirname(ACADEMY_REPO)
    if any(os.path.exists(os.path.join(parent, n)) for n in WS_MARKERS + (".gitmodules",)):
        return parent
    d = _walk_up(cwd, (".gitmodules",))
    if d:
        return d
    raise Refuse("cannot find the workspace root from %s: run from inside the workspace, "
                 "or pass --workspace DIR (or set ACADEMY_WORKSPACE)" % cwd)


def submodule_names():
    out = subprocess.run(["git", "config", "-f", os.path.join(ROOT, ".gitmodules"),
                          "--get-regexp", r"^submodule\..*\.path$"], capture_output=True, text=True).stdout
    return [line.split(None, 1)[1] for line in out.splitlines()]


BOARD = "board"


def root_dirs():
    """``{name: rel}``: the targets that are plain directories of the superproject, not
    submodules. Today only ``board``: the workspace's board (workspace.json ``board``, a
    path or ``{"path": ...}``; default ``board``) when it is a directory inside the
    workspace root that is neither a .gitmodules path nor a repository of its own."""
    b = workspace_json().get("board")
    path = b.get("path") if isinstance(b, dict) else b
    root = os.path.realpath(ROOT)
    if isinstance(path, str) and path.strip():
        full = os.path.realpath(path if os.path.isabs(path) else os.path.join(ROOT, path))
    else:
        full = os.path.join(root, BOARD)
    try:
        inside = os.path.commonpath([root, full]) == root and full != root
    except ValueError:  # different drives
        inside = False
    if not inside:
        return {}
    rel = os.path.relpath(full, root).replace(os.sep, "/")
    if (rel in submodule_names() or not os.path.isdir(full)
            or os.path.exists(os.path.join(full, ".git"))
            or not os.path.exists(os.path.join(root, ".git"))):
        return {}
    return {BOARD: rel}


def targets():
    """Every target name: the submodule paths, then the superproject directories."""
    subs = submodule_names()
    return subs + [n for n in root_dirs() if n not in subs]


def prefix_of(sub):
    """The pathspec (a directory relative to the workspace root) a superproject target is
    limited to, or None for a submodule."""
    if sub in submodule_names():
        return None
    return root_dirs().get(sub)


def scope_spec(prefix):
    """The git pathspec for a superproject target's directory (top-anchored, literal)."""
    return ":(top,literal)%s" % prefix.rstrip("/")


def common_dir(path):
    """The real, case-normalised ``git rev-parse --git-common-dir`` of the checkout ``path``."""
    out = git(path, "rev-parse", "--git-common-dir")
    full = out if os.path.isabs(out) else os.path.join(path, out)
    return os.path.normcase(os.path.realpath(full))


def repo_of(sub, explicit=None):
    """The checkout to work in: ``<ROOT>/<sub>``, or ``--repo`` when it is a checkout of that
    same repository (the checkout itself or one of its worktrees: same git-common-dir).
    For a superproject target (``board``) the checkout is the workspace root itself
    (``--repo``: it or one of its worktrees)."""
    home = ROOT if prefix_of(sub) else os.path.join(ROOT, sub)
    path = explicit or home
    if not os.path.exists(os.path.join(path, ".git")):
        raise Refuse("%s is not a checked-out repo (run scripts/bootstrap.py)" % path)
    if explicit:
        if not os.path.exists(os.path.join(home, ".git")):
            raise Refuse("--repo %s: cannot check it against %s, which is not checked out" % (explicit, home))
        try:
            same = common_dir(path) == common_dir(home)
        except Refuse as e:
            raise Refuse("--repo %s: %s" % (explicit, e))
        if not same:
            raise Refuse("--repo %s is not a checkout of %s's repository (git-common-dir differs); "
                         "give that checkout or one of its worktrees" % (explicit, home))
    return path


def slug(topic):
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    if not s:
        raise Refuse("topic %r has no usable characters" % topic)
    return s


def default_role(repo):
    try:
        with open(os.path.join(repo, ".claude", "academy.json"), encoding="utf-8") as f:
            role = json.load(f).get("role")
        return role if role in ROLES else "human"
    except (OSError, ValueError):
        return "human"


def branch_name(topic, role, today=None):
    if role not in ROLES:
        raise Refuse("role must be one of %s" % ", ".join(ROLES))
    day = today or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    name = "%s/%s/%s" % (day, slug(topic), role)
    assert BRANCH.match(name), name
    return name


def current(repo):
    return git(repo, "branch", "--show-current")


def require_template(repo):
    b = current(repo)
    if b in PROTECTED or not BRANCH.match(b):
        raise Refuse("%s is on %r, not a <date>/<topic>/<role> branch; run 'start' first" % (repo, b or "(detached)"))
    return b


def cmd_start(a):
    repo = repo_of(a.sub, a.repo)
    name = branch_name(a.topic, a.role or default_role(repo))
    exists = git(repo, "rev-parse", "--verify", "--quiet", "refs/heads/" + name, check=False)
    if a.worktree:
        wt = os.path.join(repo, ".claude", "worktrees", name.replace("/", "-"))
        args = ["worktree", "add", wt] + ([name] if exists else ["-b", name])
        git(repo, *args)
        print("worktree %s on %s" % (wt, name))
    else:
        git(repo, "switch", name) if exists else git(repo, "switch", "-c", name)
        print("%s on %s (uncommitted changes carried along)" % (repo, name))


def academy_cfg(repo):
    try:
        with open(os.path.join(repo, ".claude", "academy.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


def is_author_home(repo):
    return academy_cfg(repo).get("role") == "author"


def gate_dir():
    d = os.environ.get("SHIP_GATE_DIR")
    if d:
        return d
    return os.path.join(os.environ.get("ACADEMY_ROOT") or os.path.join(ROOT, "academy"), "author", "scripts")


GATE_MODES = ("normal", "strict", "warn", "off", "unavailable")


def load_gate():
    path = os.path.join(gate_dir(), "commit_gate.py")
    if not os.path.isfile(path):
        raise Refuse("author home but the commit gate module is missing (%s); "
                     "refusing to go on unchecked (commit: pass --no-gate to bypass)" % path)
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec = importlib.util.spec_from_file_location("commit_gate", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod  # before exec: dataclasses etc. look the module up here
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            if sys.modules.get(spec.name) is mod:
                del sys.modules[spec.name]
            raise
    except Exception as e:
        raise Refuse("commit gate module %s failed to load: %s" % (path, e))
    finally:
        sys.path.remove(os.path.dirname(path))
    return mod


NO_DETAIL = "academy checkout predates gate_check_detail"


def gate_cfg(cfg, strict):
    """The copy of the home's config the gate runs with: ``--no-registry`` appended to the
    checker's args (a gate run must never rewrite the tracked registry view,
    Drafts/statements.md; the args are used on the strict path too), and for ``strict``
    the commit mode forced to strict with no branch overrides."""
    cfg = copy.deepcopy(cfg)
    author = cfg.get("author") if isinstance(cfg.get("author"), dict) else {}
    checker = author.get("checker") if isinstance(author.get("checker"), dict) else {}
    args = [str(x) for x in (checker.get("args") or [])] if isinstance(checker.get("args"), list) else []
    if "--no-registry" not in args:
        args.append("--no-registry")
    checker["args"] = args
    author["checker"] = checker
    cfg["author"] = author
    if strict:
        gate = cfg.get("gate") if isinstance(cfg.get("gate"), dict) else {}
        gate["commit"] = "strict"
        gate["branches"] = {}
        cfg["gate"] = gate
    return cfg


def run_gate_detail(repo, strict=False):
    """(mode, new_findings, cause) from the author plugin's commit gate; ("skip", {}, "")
    outside an Author home. cause explains mode 'unavailable' (the checker could not run,
    or exited non-zero without a finding line), else ''.

    The gate evaluates the whole working tree of the home as it is on disk, not only the
    paths a commit names (``commit --paths``): a finding in an unrelated, unstaged file
    blocks too. Uses the gate's ``gate_check_detail``, or ``gate_check`` from an older
    academy checkout. Fails closed: a gate module with neither, a gate that raises, reports
    a mode other than normal/strict/warn/off/unavailable, findings that are not a dict of
    str -> str or a cause that is not a string, is a Refuse.
    """
    cfg = academy_cfg(repo)
    if cfg.get("role") != "author":
        return "skip", {}, ""
    cfg = gate_cfg(cfg, strict)
    mod = load_gate()
    detail, check = getattr(mod, "gate_check_detail", None), getattr(mod, "gate_check", None)
    if not callable(detail) and not callable(check):
        raise Refuse("academy checkout predates gate_check: update the academy submodule")
    branch = current(repo) or None
    try:
        if callable(detail):
            mode, findings, cause = detail(repo, cfg, branch)
        else:
            (mode, findings), cause = check(repo, cfg, branch), NO_DETAIL
    except Exception as e:
        raise Refuse("gate failed: %s" % e)
    if mode not in GATE_MODES:
        raise Refuse("unknown gate mode %s" % mode)
    if findings is None:
        findings = {}
    if not isinstance(findings, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in findings.items()):
        raise Refuse("gate returned malformed findings")
    if cause is None:
        cause = ""
    if not isinstance(cause, str):
        raise Refuse("gate returned a malformed cause")
    if mode == "unavailable" and not cause.strip():
        cause = "no cause given"
    return mode, dict(findings), cause


def run_gate(repo, strict=False):
    """(mode, new_findings): ``run_gate_detail`` without the cause."""
    mode, findings, _cause = run_gate_detail(repo, strict)
    return mode, findings


def gate_unavailable_note(cause):
    """commit / ship / checkpoint go on when the checker is unavailable, and say why."""
    print("ship: gate unavailable: %s" % cause.strip().replace("\n", "\n    "), file=sys.stderr)


def cmd_accept_baseline(a):
    repo = repo_of(a.sub, a.repo)
    require_template(repo)
    if not is_author_home(repo):
        raise Refuse("%s is not an Author home; there is no baseline" % repo)
    script = os.path.join(gate_dir(), "commit_gate.py")
    if not os.path.isfile(script):
        raise Refuse("commit gate module is missing (%s)" % script)
    p = subprocess.run([sys.executable, script, "--write-baseline", "--root", repo],
                       capture_output=True, text=True)
    if p.stdout:
        print(p.stdout.strip())
    if p.stderr and p.returncode == 0:
        print(p.stderr.strip(), file=sys.stderr)
    if p.returncode:
        raise Refuse("write-baseline failed: %s" % (p.stderr or p.stdout).strip())


def cmd_commit(a):
    """Commit on the current template branch. In an Author home the gate runs first and
    evaluates the whole working tree of the home, not only the ``--paths`` committed."""
    repo = repo_of(a.sub, a.repo)
    prefix = prefix_of(a.sub)
    b = require_template(repo)
    if a.all == bool(a.paths):
        raise Refuse("give exactly one of --paths P... or --all")
    paths = list(a.paths or [])
    if paths:
        top = os.path.realpath(repo)
        base = os.path.join(top, prefix) if prefix else top
        rels = []
        for p in paths:
            full = os.path.realpath(p if os.path.isabs(p) else os.path.join(base, p))
            try:
                inside = os.path.commonpath([base, full]) == base
            except ValueError:  # different drives
                inside = False
            if not inside:
                raise Refuse("path %r is outside the %s %s" % (p, "directory" if prefix else "repo", base))
            rels.append(os.path.relpath(full, top).replace(os.sep, "/"))
        if prefix:  # superproject target: top-anchored, so the cwd of git does not matter
            paths = [":(top)%s" % r for r in rels]
    if a.no_gate:
        if is_author_home(repo):
            print("ship: warning: --no-gate given, the commit gate is skipped", file=sys.stderr)
    else:
        mode, findings, cause = run_gate_detail(repo)
        if mode == "unavailable":
            gate_unavailable_note(cause)
        if findings and mode in ("normal", "strict"):
            raise Refuse("commit gate (%s) found new problems:\n  %s\n(fix them, or 'accept-baseline' if intended)"
                         % (mode, "\n  ".join(findings.values())))
        if findings and mode == "warn":
            for line in findings.values():
                print("ship: gate warning: %s" % line, file=sys.stderr)
    if prefix:
        # a superproject target: stage and commit its directory only, never a pointer
        scope = ["--"] + (paths or [scope_spec(prefix)])
        git(repo, "add", *(["-A"] if a.all else []), *scope)
        unstage_gitlinks(repo, scope)
    else:
        scope = ["--"] + paths if paths else []
        git(repo, "add", *(["-A"] if a.all else scope))
    if not git(repo, "diff", "--cached", "--name-only", *scope):
        raise Refuse("nothing staged; nothing to commit")
    git(repo, "commit", "-q", "-m", with_ticket_ref(a.m, b), *scope)
    print("%s %s @ %s" % (a.sub, b, git(repo, "rev-parse", "--short", "HEAD")))


def unstage_gitlinks(repo, scope=()):
    """Unstage every staged gitlink (a submodule pointer, or a nested repository ``add``
    recorded as one) within ``scope`` (``["--", spec...]``; empty: the whole index), so
    pins move only through the human-run 'merge --bump'. Returns the paths unstaged."""
    links = [l.split("\t", 1)[1] for l in
             git(repo, "diff", "--cached", "--raw", "--no-renames", *scope).splitlines()
             if "\t" in l and "160000" in l.lstrip(":").split()[:2]]
    if links:
        git(repo, "reset", "-q", "--", *links)
    return links


def cmd_push(a):
    repo = repo_of(a.sub, a.repo)
    b = require_template(repo)
    git(repo, "push", "-q", "-u", "origin", "HEAD:refs/heads/" + b)
    print("%s -> origin/%s @ %s" % (a.sub, b, git(repo, "rev-parse", "--short", "HEAD")))


def cmd_ship(a):
    cmd_commit(a)
    cmd_push(a)


HEX = re.compile(r"^[0-9a-f]+$")


def check_sha(given, full, what):
    """Refuse unless ``given`` is ``full`` or a prefix of it of at least 7 hex characters."""
    g = (given or "").strip().lower()
    if len(g) < 7 or not HEX.match(g):
        raise Refuse("--sha %r must be a full SHA or a hex prefix of at least 7 characters" % given)
    if not full.lower().startswith(g):
        raise Refuse(what % full)


def remote_tip(repo, branch):
    """Full SHA of ``origin/<branch>`` after a fetch; Refuse if the remote has no such branch."""
    git(repo, "fetch", "-q", "origin")
    out = git(repo, "ls-remote", "origin", "refs/heads/" + branch)
    tip = out.split()[0] if out else ""
    if not tip:
        raise Refuse("branch %s does not exist on origin" % branch)
    if git(repo, "cat-file", "-t", tip, check=False) != "commit":
        raise Refuse("origin/%s is at %s, which the fetch did not bring in" % (branch, tip))
    return tip


def require_clean(repo, ignore_submodules=False):
    """Refuse on uncommitted changes to tracked files or a merge in progress; with
    ``ignore_submodules`` (the superproject, for a ``board`` target) submodule pointer
    drift does not count."""
    extra = ["--ignore-submodules=all"] if ignore_submodules else []
    if git(repo, "status", "--porcelain", "--untracked-files=no", *extra):
        raise Refuse("%s has uncommitted changes to tracked files; the tree must be clean" % repo)
    if merge_in_progress(repo):
        raise Refuse("%s has a merge in progress; the tree must be clean" % repo)


def merge_in_progress(repo):
    return bool(git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False))


def committed_role(repo, ref):
    try:
        cfg = json.loads(git(repo, "show", "%s:.claude/academy.json" % ref, check=False) or "{}")
    except ValueError:
        return None
    return cfg.get("role") if isinstance(cfg, dict) else None


GATE_CONFIG = ".claude/academy.json"
DEFAULT_BASELINE = ".claude/paper-gate-baseline.txt"


def baseline_rel(cfg):
    """The gate baseline path a config names (``gate.baseline``), '/'-separated and relative."""
    gate = cfg.get("gate") if isinstance(cfg, dict) and isinstance(cfg.get("gate"), dict) else {}
    rel = gate.get("baseline") if isinstance(gate.get("baseline"), str) and gate.get("baseline") else DEFAULT_BASELINE
    rel = rel.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def committed_cfg(repo, ref):
    try:
        cfg = json.loads(git(repo, "show", "%s:%s" % (ref, GATE_CONFIG), check=False) or "{}")
    except ValueError:
        return {}
    return cfg if isinstance(cfg, dict) else {}


def gate_inputs_changed(repo, main_before, tip):
    """The gate's inputs the branch changes: .claude/academy.json and the baseline file
    (``gate.baseline`` as main or the branch configures it, default
    .claude/paper-gate-baseline.txt), in the order of that list."""
    inputs = [GATE_CONFIG] + [baseline_rel(committed_cfg(repo, ref)) for ref in (main_before, tip)]
    changed = set(git(repo, "diff", "--name-only", "%s...%s" % (main_before, tip)).splitlines())
    return [p for p in dict.fromkeys(inputs) if p in changed]


def cmd_merge(a):
    """Merge a reviewed branch into local main, --no-ff, tied to the reviewed tip SHA.

    Order: template check, --bump preconditions, fetch + tip == --sha, clean tree,
    origin/main an ancestor of main; summary; switch to main, ``merge --no-ff --no-commit``
    of the exact SHA; in an Author home the strict gate on the merged tree; commit. Any
    refusal after the switch aborts the merge and switches back, so the repo is left as
    it was. Never pushes (``publish`` does that).
    """
    branch = a.branch
    if branch in PROTECTED or not BRANCH.match(branch):
        raise Refuse("%r is not a <date>/<topic>/<role> template branch; refusing to merge it" % branch)
    repo = repo_of(a.sub, a.repo)
    if a.bump:
        if a.sub not in submodule_names():
            raise Refuse("--bump: %s is not a submodule path in %s" % (a.sub, os.path.join(ROOT, ".gitmodules")))
        if os.path.realpath(repo) != os.path.realpath(os.path.join(ROOT, a.sub)):
            raise Refuse("--bump needs the merge done in the workspace checkout %s, not %s"
                         % (os.path.join(ROOT, a.sub), repo))
    tip = remote_tip(repo, branch)
    check_sha(a.sha, tip, "branch moved since review: %s")
    require_clean(repo, ignore_submodules=bool(prefix_of(a.sub)))
    if not git(repo, "rev-parse", "-q", "--verify", "refs/heads/main", check=False):
        raise Refuse("%s has no local main" % repo)
    if not git(repo, "rev-parse", "-q", "--verify", "refs/remotes/origin/main", check=False):
        raise Refuse("%s has no origin/main" % repo)
    if subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", "refs/remotes/origin/main",
                       "refs/heads/main"], capture_output=True, env=git_env(),
                      stdin=subprocess.DEVNULL).returncode:
        raise Refuse("local main is behind or diverged from origin/main; update main by hand first")
    main_before = git(repo, "rev-parse", "refs/heads/main")
    n = int(git(repo, "rev-list", "--count", "%s..%s" % (main_before, tip)))
    if n == 0:
        raise Refuse("%s @ %s is already in main; nothing to merge" % (branch, tip[:9]))
    stat = git(repo, "diff", "--shortstat", "%s...%s" % (main_before, tip)) or "no file changes"
    print("merge %s @ %s into main @ %s: %d commit%s; %s"
          % (branch, tip[:9], main_before[:9], n, "" if n == 1 else "s", stat))
    touched = gate_inputs_changed(repo, main_before, tip)
    if touched:
        print("!! gate inputs changed: %s -- the branch changes what its own merge gate checks "
              "against; review these files before approving" % ", ".join(touched))

    was_author = is_author_home(repo) or committed_role(repo, main_before) == "author"
    orig = current(repo) or git(repo, "rev-parse", "HEAD")
    detached = not current(repo)
    msg = a.m or "Merge %s into main" % branch
    git(repo, "switch", "-q", "main")
    try:
        git(repo, "merge", "-q", "--no-ff", "--no-commit", tip)
        mode, findings, cause = run_gate_detail(repo, strict=True)
        if mode == "unavailable":
            raise Refuse("merge needs the strict gate, but the checker was unavailable; refusing:\n  %s"
                         % cause.strip().replace("\n", "\n  "))
        if mode == "skip":
            if was_author:
                raise Refuse("main is an Author home but the merged tree is not (the branch changes "
                             ".claude/academy.json's role); refusing to merge without the gate")
            print("gate: skipped (not an Author home)")
        elif mode != "strict":
            raise Refuse("merge needs the strict gate, but the gate ran in mode %s; refusing%s"
                         % (mode, "".join("\n  " + v for v in findings.values())))
        elif findings:
            raise Refuse("strict gate (%s) found problems in the merged tree:\n  %s"
                         % (mode, "\n  ".join(findings.values())))
        else:
            print("gate: %s, no findings" % mode)
        git(repo, "commit", "-q", "--no-edit", "-m", msg)
    except BaseException:
        rollback(repo, main_before, orig, detached)
        raise
    merged = git(repo, "rev-parse", "HEAD")
    print("main @ %s (local only; 'publish %s --sha %s' pushes it)" % (merged[:9], a.sub, merged[:9]))
    if a.bump:
        try:
            short = git(repo, "rev-parse", "--short", merged)
            git(ROOT, "add", "--", a.sub)
            git(ROOT, "commit", "-q", "-m", "Bump %s to %s" % (a.sub, short), "--", a.sub)
        except Refuse as e:
            raise Refuse("merge done; bump failed: %s" % e)
        print("superproject: Bump %s to %s @ %s" % (a.sub, short, git(ROOT, "rev-parse", "--short", "HEAD")))


def rollback(repo, main_before, orig, detached):
    """Undo a half-done merge: abort it, check main did not move, switch back; warn loudly
    when any step leaves the repo other than it was."""
    if merge_in_progress(repo):
        git(repo, "merge", "--abort", check=False)
    main_now = git(repo, "rev-parse", "refs/heads/main", check=False)
    if main_now != main_before or merge_in_progress(repo):
        print("ship: WARNING: rollback incomplete in %s (main %s, was %s); inspect by hand"
              % (repo, main_now, main_before), file=sys.stderr)
        return
    if detached:
        git(repo, "switch", "-q", "--detach", orig, check=False)
        back = not current(repo) and git(repo, "rev-parse", "HEAD", check=False) == orig
    else:
        git(repo, "switch", "-q", orig, check=False)
        back = current(repo) == orig
    if not back:
        print("ship: WARNING: rollback could not switch %s back to %s (now on %s); main is unchanged, "
              "switch back by hand" % (repo, orig, current(repo) or "(detached)"), file=sys.stderr)


def cmd_publish(a):
    """Push local main to origin main (plain, never forced), only if HEAD is the approved SHA."""
    repo = repo_of(a.sub, a.repo)
    if current(repo) != "main":
        raise Refuse("%s is on %r, not main; publish pushes main only" % (repo, current(repo) or "(detached)"))
    head = git(repo, "rev-parse", "HEAD")
    check_sha(a.sha, head, "HEAD of main is %s, not the approved --sha")
    require_clean(repo, ignore_submodules=bool(prefix_of(a.sub)))
    # the verified SHA is the source, not the ref: main moving after the check changes nothing
    p = subprocess.run(["git", "-C", repo, "push", "--no-follow-tags", "--recurse-submodules=no",
                        "origin", "%s:refs/heads/main" % head], capture_output=True, text=True,
                       env=git_env(), stdin=subprocess.DEVNULL)
    if p.returncode:
        raise Refuse("the remote rejected the push of main:\n%s" % (p.stderr or p.stdout).strip())
    print("%s: origin/main @ %s" % (a.sub, head[:9]))


def cmd_status(a):
    for sub in targets():
        try:
            repo = repo_of(sub)
        except Refuse:
            print("%-28s (not checked out)" % sub)
            continue
        prefix = prefix_of(sub)
        b = current(repo)
        # a superproject target counts its own directory only (submodule pointers aside)
        spec = ["--", scope_spec(prefix)] if prefix else []
        dirty = len([l for l in git(repo, "status", "--porcelain", *spec).splitlines()
                     if not l.startswith("??")])
        up = git(repo, "rev-list", "--count", "@{u}..HEAD", check=False) if b else ""
        flag = "ok" if BRANCH.match(b) else ("PROTECTED" if b in PROTECTED else "off-template")
        print("%-28s %-44s dirty=%s unpushed=%s [%s]%s" % (sub, b or "(detached)", dirty, up or "-", flag,
                                                       " (superproject, %s/ only)" % prefix if prefix else ""))


TICKET = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
REMOTE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def workspace_json():
    """The workspace's workspace.json (next to .gitmodules) as a dict; {} if unreadable."""
    try:
        with open(os.path.join(ROOT, "workspace.json"), encoding="utf-8") as f:
            ws = json.load(f)
    except (OSError, ValueError):
        return {}
    return ws if isinstance(ws, dict) else {}


TICKET_IN = re.compile(r"(?:^|/)t-(\d+)(?:/|$)", re.I)


def ticket_ref(ticket_or_branch):
    """``OWNER/NAME#N`` for a ticket id (``T-0059``) or a ``<date>/t-0059/<role>`` branch when
    the board is on GitHub (``board.backend: github`` with ``board.repo`` in workspace.json):
    a commit naming it shows on the ticket's issue, whichever repo the commit lands in.
    None on the file board or when no ticket id is found."""
    board = workspace_json().get("board")
    if not (isinstance(board, dict) and board.get("backend") == "github" and board.get("repo")):
        return None
    m = TICKET_IN.search(ticket_or_branch or "")
    return "%s#%d" % (board["repo"], int(m.group(1))) if m else None


def with_ticket_ref(message, ticket_or_branch):
    """``message`` with a ``Ticket: OWNER/NAME#N`` line before any trailer (see ticket_ref)."""
    ref = ticket_ref(ticket_or_branch)
    if not ref or ("Ticket: " + ref) in message:
        return message
    head, sep, rest = message.partition("\n\n")
    return head + "\n\nTicket: " + ref + (sep + rest if sep else "")


def ship_remote():
    """The remote checkpoint pushes to: ``shipRemote`` in the workspace's workspace.json
    (next to .gitmodules), else ``origin``."""
    r = workspace_json().get("shipRemote")
    return r if isinstance(r, str) and r else "origin"


def operation_in_progress(repo):
    """The name of a merge / rebase / cherry-pick / revert under way in ``repo``, else ''."""
    for ref in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        if git(repo, "rev-parse", "-q", "--verify", ref, check=False):
            return ref.split("_HEAD")[0].lower().replace("_", "-")
    for d in ("rebase-merge", "rebase-apply"):
        path = git(repo, "rev-parse", "--git-path", d, check=False)
        if path and os.path.exists(path if os.path.isabs(path) else os.path.join(repo, path)):
            return "rebase"
    return ""


def worktree_state(repo, pathspec=None):
    """(dirty, skipped) from ``git status --porcelain -z --untracked-files=all``: dirty is
    True when any entry is left once untracked nested repositories and worktrees (an
    untracked directory with a ``.git`` of its own) are set aside; skipped lists those,
    '/'-terminated. Ignored files are not entries at all. With ``pathspec`` (a directory
    of a superproject target) only entries under it count."""
    spec = ["--", scope_spec(pathspec)] if pathspec else []
    # unstripped: a first entry ' M x' would otherwise lose its leading space
    raw = git(repo, "status", "--porcelain", "-z", "--untracked-files=all", *spec, strip=False)
    # tracked submodule pointers (gitlinks): never committed by a checkpoint; pins move
    # only through the human-run 'merge --bump'
    gitlinks = {line.split("\t", 1)[1] for line in
                git(repo, "ls-files", "-s", "-z", *spec).split("\0")
                if line.startswith("160000 ") and "\t" in line}
    fields = raw.split("\0")
    dirty, skipped, i = False, [], 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if xy[0] in "RC":
            i += 1  # -z puts a rename's or copy's source path in the next field
        if path.rstrip("/") in gitlinks or (
                xy == "??" and os.path.exists(os.path.join(repo, path.rstrip("/"), ".git"))):
            skipped.append(path.rstrip("/") + "/")
            continue
        dirty = True
    return dirty, skipped


NAMES_SHOWN = 20


def checkpoint_repo(sub, repo, name, message, remote, scoped=False, pathspec=None):
    """One repo of a checkpoint; returns its result dict (see ``run_checkpoint``).

    ``pathspec`` (a superproject target such as ``board``: the directory, relative to the
    workspace root): only changes under it are looked at, staged (``add -A -- <dir>/``,
    not ``:/``) and committed (``commit -- <dir>/``), so whatever else is dirty or staged
    in the superproject -- another directory, a moved submodule pointer -- is left
    exactly as it was."""
    res = {"sub": sub, "branch": name, "sha": "", "files": 0, "status": "unchanged", "detail": "",
           "names": [], "skipped": []}

    def sha():
        return git(repo, "rev-parse", "--short", "HEAD", check=False)

    def refused(why):
        res.update(status="skipped", sha=sha(), detail="refused: " + why)
        return res

    tip = git(repo, "rev-parse", "-q", "--verify", "refs/heads/" + name, check=False)
    dirty, res["skipped"] = worktree_state(repo, pathspec)
    if dirty:  # untracked included, ignored files and nested repos/worktrees not
        cur = current(repo)
        if not cur:
            return refused("HEAD is detached; switch to a branch by hand")
        op = operation_in_progress(repo)
        if op:
            return refused("a %s is in progress" % op)
        if scoped and cur in PROTECTED:
            return refused("dirty on %s; move your work to a template branch first: "
                           "py scripts/ship.py start %s <topic>" % (cur, sub))
        if cur != name and cur not in PROTECTED and not BRANCH.match(cur):
            return refused("on %r, which is neither main/master nor a <date>/<topic>/<role> branch; "
                           "its changes are not this ticket's to sweep up -- commit or move them by hand"
                           % cur)
        if cur != name and BRANCH.match(cur):
            print("ship: note: %s is on %s (another ticket's branch); its leftover changes are "
                  "committed under %s" % (sub, cur, message.split(":", 1)[0]), file=sys.stderr)
        if cur != name:
            try:
                git(repo, "switch", "-q", name) if tip else git(repo, "switch", "-q", "-c", name)
            except Refuse as e:
                return refused(str(e))
        where = "left on %s" % name
        try:
            mode, findings, cause = run_gate_detail(repo)
        except Refuse as e:
            return refused("%s (%s, changes uncommitted)" % (e, where))
        if mode == "unavailable":
            gate_unavailable_note(cause)
        if findings and mode in ("normal", "strict"):
            return refused("commit gate (%s) found new problems: %s (fix them, or 'accept-baseline'; %s, "
                           "changes uncommitted)" % (mode, "; ".join(findings.values()), where))
        if findings and mode == "warn":
            for line in findings.values():
                print("ship: gate warning: %s" % line, file=sys.stderr)
        try:
            # everything but the nested repositories/worktrees, which 'add -A' would record
            # as gitlinks
            excl = [":(top,literal,exclude)%s" % p.rstrip("/") for p in res["skipped"]]
            scope = ["--", scope_spec(pathspec)] if pathspec else []
            git(repo, "add", "-A", "--", scope_spec(pathspec) if pathspec else ":/", *excl)
            # a pointer staged beforehand (moved or new) would ride along with the index:
            # unstage every staged gitlink (of the scope), so pins move only through
            # 'merge --bump'
            links = unstage_gitlinks(repo, scope)
            res["skipped"] += [p + "/" for p in links if p + "/" not in res["skipped"]]
            staged = git(repo, "diff", "--cached", "--name-only", *scope).splitlines()
        except Refuse as e:
            return refused("%s (%s, changes uncommitted or partly staged)" % (e, where))
        try:
            if staged:
                # with a scope, 'commit -- <dir>' takes that directory only: anything
                # else staged in the superproject stays staged and uncommitted
                git(repo, "commit", "-q", "-m", message, *scope)
        except Refuse as e:
            return refused("%s (%s, changes staged)" % (e, where))
        res["files"] = len(staged)
        res["names"] = staged
        if staged:
            tip = git(repo, "rev-parse", "refs/heads/" + name)
    if not res["files"]:  # no new commit: push only what the remote lacks
        if not tip:
            res["sha"] = sha()
            return res
        out = git(repo, "ls-remote", remote, "refs/heads/" + name, check=False)
        if out and out.split()[0] == tip:
            res["sha"] = git(repo, "rev-parse", "--short", tip)
            return res
    assert BRANCH.match(name) and name not in PROTECTED, name
    res["sha"] = git(repo, "rev-parse", "--short", tip)
    p = subprocess.run(["git", "-C", repo, "push", "-q", "--no-follow-tags", "--recurse-submodules=no",
                        remote, "refs/heads/%s:refs/heads/%s" % (name, name)],
                       capture_output=True, text=True, env=git_env(), stdin=subprocess.DEVNULL)
    if p.returncode:
        lines = (p.stderr or p.stdout or "exit %d" % p.returncode).strip().splitlines()
        res.update(status="push-failed", detail=" / ".join(l.strip() for l in lines[-2:]))
    else:
        res["status"] = "pushed"
    return res


def run_checkpoint(ticket, role, title, remote, only=None):
    """Commit and push, on ``<date>/<ticket-id>/<role>``, every checked-out submodule that
    has uncommitted changes (tracked or untracked, .gitignore honoured) or commits on that
    branch the remote does not have. One dict per submodule: sub, branch, sha, files,
    status ("pushed" / "unchanged" / "push-failed" / "skipped"; a refused repo is
    "skipped" with a detail starting "refused: "), detail. Never touches main, never
    merges, never forces; a refused or failed repo (including a Refuse raised inside
    ``checkpoint_repo``) does not stop the others. Also: names (the committed files) and
    skipped (untracked nested repos/worktrees and tracked submodule pointers left out,
    '/'-terminated).

    ``only`` (the automatic run from the inbox hook): just these targets (each must be a
    .gitmodules path or a superproject target such as ``board``, else Refuse before
    anything is touched); the others are not looked at, and a dirty repo of the set that
    is on main/master is refused instead of moved. A superproject target is committed in
    the workspace's own repository, limited to its directory (``checkpoint_repo``)."""
    t = (ticket or "").strip()
    if not TICKET.match(t):
        raise Refuse("ticket id %r is not a ticket id like T-0059 (letters, digits, '-')" % ticket)
    if role is not None:
        branch_name(t, role)  # a bad --role is refused before anything is touched
    remote = remote or ship_remote()
    if not REMOTE.match(remote):
        raise Refuse("remote %r is not a plain remote name" % remote)
    message = "%s: %s" % (t, (title or "").strip() or "checkpoint")
    ref = ticket_ref(t)
    if ref:
        message += "\n\nTicket: " + ref
    trailer = os.environ.get("SHIP_TRAILER", "").strip()
    if trailer:
        message += "\n\n" + trailer
    results = []
    subs = targets()
    dirs = root_dirs()
    if only is not None:
        unknown = [s for s in only if s not in subs]
        if unknown or not only:
            raise Refuse("--only %s: not a submodule in .gitmodules nor a superproject "
                         "directory (known: %s)" % (" ".join(unknown) or "(nothing)", " ".join(subs)))
        subs = [s for s in subs if s in only]
    for sub in subs:
        try:
            repo = repo_of(sub)
        except Refuse:
            results.append({"sub": sub, "branch": "", "sha": "", "files": 0, "status": "skipped",
                            "detail": "not checked out"})
            continue
        name = branch_name(t, role or default_role(repo))
        try:
            results.append(checkpoint_repo(sub, repo, name, message, remote,
                                           scoped=only is not None,
                                           pathspec=None if sub in submodule_names() else dirs.get(sub)))
        except Refuse as e:  # one repo's failure is its own result; the others go on
            results.append({"sub": sub, "branch": name, "sha": git(repo, "rev-parse", "--short", "HEAD", check=False),
                            "files": 0, "status": "skipped", "detail": "refused: %s" % e,
                            "names": [], "skipped": []})
    return results


def cmd_checkpoint(a):
    results = run_checkpoint(a.ticket, a.role, a.title, a.remote, a.only)
    bad = False
    for r in results:
        if r["status"] == "pushed" or r["status"] == "unchanged":
            what = r["status"]
        elif r["status"] == "push-failed":
            what, bad = "PUSH FAILED: " + r["detail"], True
        elif r["detail"].startswith("refused: "):
            what, bad = "REFUSED: " + r["detail"][len("refused: "):], True
        else:
            what = "SKIPPED: " + r["detail"]
        print("%s %s @ %s (%d files) %s" % (r["sub"], r["branch"] or "-", r["sha"] or "-", r["files"], what))
        names = r.get("names") or []
        for n in names[:NAMES_SHOWN]:
            print("    %s" % n)
        if len(names) > NAMES_SHOWN:
            print("    +%d more" % (len(names) - NAMES_SHOWN))
        for p in r.get("skipped") or []:
            print("    skipped nested repo: %s (not committed)" % p)
    if bad:
        raise Refuse("checkpoint incomplete (commits made are kept locally); see the lines above")


def parser():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--workspace", metavar="DIR",
                   help="the workspace root (or its workspace.json); default: found from the "
                        "cwd, $ACADEMY_WORKSPACE or this academy checkout (module docstring)")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status").set_defaults(fn=cmd_status)
    s = sp.add_parser("start")
    s.add_argument("sub"); s.add_argument("topic")
    s.add_argument("--role"); s.add_argument("--worktree", action="store_true")
    s.set_defaults(fn=cmd_start)
    for name, fn in (("commit", cmd_commit), ("ship", cmd_ship)):
        c = sp.add_parser(name)
        c.add_argument("sub"); c.add_argument("-m", required=True)
        c.add_argument("--paths", nargs="+"); c.add_argument("--all", action="store_true")
        c.add_argument("--no-gate", action="store_true", help="skip the Author commit gate (warns)")
        c.set_defaults(fn=fn)
    c = sp.add_parser("accept-baseline"); c.add_argument("sub"); c.set_defaults(fn=cmd_accept_baseline)
    c = sp.add_parser("push"); c.add_argument("sub"); c.set_defaults(fn=cmd_push)
    c = sp.add_parser("merge", help="merge a reviewed branch into local main (no push)")
    c.add_argument("sub"); c.add_argument("branch")
    c.add_argument("--sha", required=True, help="the reviewed tip of origin/<branch> (>= 7 hex chars)")
    c.add_argument("-m", help="merge commit message (default: Merge <branch> into main)")
    c.add_argument("--bump", action="store_true", help="then commit the new pointer in the superproject")
    c.set_defaults(fn=cmd_merge)
    c = sp.add_parser("publish", help="push local main to origin")
    c.add_argument("sub"); c.add_argument("--sha", required=True, help="the approved tip of local main")
    c.set_defaults(fn=cmd_publish)
    c = sp.add_parser("checkpoint", help="end of an inbox ticket: commit and push every touched repo "
                                         "on <date>/<ticket-id>/<role>")
    c.add_argument("--ticket", required=True, help="the ticket id, e.g. T-0059")
    c.add_argument("--role", help="default: each repo's academy.json role, else human")
    c.add_argument("--title", help="commit message after '<TICKET>: ' (default: checkpoint)")
    c.add_argument("--remote", help="default: shipRemote in workspace.json, else origin")
    c.add_argument("--only", nargs="+", metavar="SUB",
                   help="only these submodules or superproject directories (board) -- the inbox "
                        "hook's automatic run: the others are not touched, and a dirty one on "
                        "main/master is refused, not moved")
    c.set_defaults(fn=cmd_checkpoint)
    for x in sp.choices.values():
        if x.prog.split()[-1] not in ("status", "checkpoint"):
            x.add_argument("--repo", help="the checkout to use instead of <workspace>/<sub>: that "
                                          "checkout or one of its worktrees (same git-common-dir)")
    return p


def main(argv):
    global ROOT
    a = parser().parse_args(argv)
    try:
        if a.workspace or ROOT is None:
            ROOT = find_workspace(a.workspace)
        a.fn(a)
    except Refuse as e:
        print("ship: refused: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
