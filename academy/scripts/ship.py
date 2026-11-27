#!/usr/bin/env python3
"""Branch, commit and push in one repo of an academy workspace, one plain command per step.

    py scripts/ship.py [--workspace DIR] status [--all]             # then the worktrees holding work
    py scripts/ship.py start  <sub> <topic> [--role R] [--worktree] [--on BRANCH]
    py scripts/ship.py commit <sub> -m MSG (--paths P... | --all)
    py scripts/ship.py push   <sub> [--no-gate]
    py scripts/ship.py stack  <sub> [--json]                         # the branch's stack and the PRs to open
    py scripts/ship.py accept-baseline <sub>                         # Author homes: rewrite the gate baseline
    py scripts/ship.py ship   <sub> -m MSG (--paths P... | --all)    # commit + push
    py scripts/ship.py merge  <sub> <branch> --sha TIP [-m MSG] [--bump]   # reviewed branch -> local main
    py scripts/ship.py publish <sub> --sha MAIN_TIP                  # local main -> origin main
    py scripts/ship.py checkpoint --ticket T-NNNN [--role R] [--title T] [--remote NAME] [--only SUB...]
                                  [--touched SUB:PATH...] | [--manifest FILE] [--wip OUTCOME]

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
``workspace`` is the workspace repo's own files: everything of the superproject except
the board's directory and the submodules (its CLAUDE.md, ``scripts/``, ``docs/``, the
template). ``start`` / ``commit`` / ``push`` / ``ship`` / ``stack`` take it; a path inside
the board or a submodule is refused (that is the other target), a submodule pointer is
never staged, and ``checkpoint`` does not include it (a ticket's work is not there).

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
another ticket's template branch is carried over with a note, unless another live inbox
run holds its lease (``<workspace>/.academy/leases/<sub>.json``, #96; ``--run RUN`` names the
ticket's run, the manifest's ``run`` by default): then it is refused, never switched. A refused repo's line says
which branch it was left on and whether its changes are staged. Submodule pointers
(tracked gitlinks) are never staged. ``board`` is in scope whatever ``board.backend`` is
(with ``github`` the tickets are on GitHub, but packets and deep-dives are files there);
as a plain directory of the superproject only ``board/`` paths are staged and committed
(``add -A -- board/``, ``commit -- board/``), whatever else is dirty or staged there. While
another live inbox run holds a lease in the workspace (#96: that run works in the same
checkout) the checkout is not switched instead: the board's paths are committed onto the
ticket's branch with git plumbing (a temporary index from the branch's tip, or HEAD for a
new branch; ``write-tree``, ``commit-tree``, ``update-ref``) and that ref is pushed; HEAD,
the index and the working tree stay as they were, on whatever branch (``checkpoint_tree``).
The academy plugin's ``inbox.py --check`` runs ``checkpoint --only <the ticket's repos>``
itself after a finished ticket: with ``--only`` the other submodules are not touched and
a dirty repo of the set that is on main/master is refused instead of moved. With
``--touched SUB:PATH...`` (from the inbox's touch ledger: files the ticket's role wrote in
another role's home, such as an Expert's entry in an Author home's references.bib or an
evidence row in another home's registry) each such submodule outside ``--only`` is
checkpointed too, for those paths only: they alone are staged and committed, on the same
``<date>/<ticket-id>/<role>`` branch (the acting role's, given by ``--role``), through that
home's commit gate and push gate; the repo is refused, and nothing is shipped there, when
it is on main/master, or when it would have to switch branches while anything else in it
is uncommitted (that work is not the ticket's).

``--manifest FILE`` (#101 part 1; instead of ``--only``/``--touched``) is the inbox's snapshot
diff of the ticket, ``{"repos": {TARGET: [paths relative to it]}}``: the paths that were clean
before the ticket, or whose content changed during it, in every home. Each target with paths
is checkpointed for exactly those (as ``--touched`` paths: never a dirty repo on main/master,
never moved while other work there is uncommitted; a board path is relative to the board's
directory, and the usage summary rides along); no other repo is looked at. A listed path that
is no longer dirty is passed over. ``--wip OUTCOME`` commits as ``WIP: <ticket> unfinished
(OUTCOME)``: the inbox ships an unfinished, blocked or lost ticket's manifest that way.

**Stacks.** ``start`` branches from where the checkout is, so a second ``start`` on a
template branch stacks on it; ``--on BRANCH`` names the base explicitly (a local branch,
or ``origin/<branch>``). The base is recorded (``git config branch.<name>.ship-base``) and
``stack`` prints the chain from the current branch down to ``main``: each branch, its tip,
whether it is pushed, and the pull request it wants (``head`` and ``base``; a stacked
branch's base is the branch under it, never ``main``). ``stack`` opens nothing: the
session opens each PR with its GitHub tool (or ``gh pr create --head H --base B``),
bottom first.

**The push gate.** Nothing runs on GitHub for these repos, so what CI would run is run
here, before a push. The description of the checks stays where CI keeps it: the repo's
``.github/workflows/*.yml``. ``push`` / ``ship`` / ``checkpoint`` run the ``run:`` steps of
every workflow triggered by ``push`` (``ci_local.py``, whose docstring says how a step is
read locally: setup and install steps skipped, ``python`` mapped to this interpreter,
``CI=true``), and refuse the push when a step fails, with the tail of its output; the
commit stays. ``py ci_local.py list --repo <dir>`` shows the plan, ``run`` runs it by hand.

A repo's ``ship.json`` (at its top level) is optional: ``{"pushGate": false}`` gives the
repo no push gate, and a list adds steps that are local only, run before the workflows,

    {"pushGate": [{"name": "build", "run": ["{python}", "tools/build.py"], "optional": true,
                   "timeout": 900, "env": {"X": "1"}}]}

from the repo's top level (``{python}`` is the interpreter running ship.py; a step whose
executable is not installed is a failure unless it is ``optional``). A tree that passed is remembered (``<git dir>/ship-gate/<tree sha>``, clean
trees only), so pushing the same tree again, or the next branch of a stack before it
changed, does not rerun the steps. ``--no-gate`` on ``push`` / ``ship`` skips it with a
warning, as for the commit gate: only on the human's word. ``"pushGate": false`` in
workspace.json switches it off for the workspace. A repo with neither a push-triggered
workflow nor a ``ship.json`` has no push gate.

Usage on the board: when the ``board`` target is part of a checkpoint, ``usage_ledger``
first appends one content-free summary per recently active session of this machine
(id, instance bucket, turns, cache read/write, models, subagent counts, a hashed host;
no prompts, paths or tool inputs) to ``board/.usage/<instance>.<host>.jsonl``, so cloud sessions
show in ``usage_report.py``. It is plain board content: the ``add -A -- board/`` staging
commits it exactly as it does ``.errors/``. It is skipped by ``"shipCheckpoint": false``
or ``"usageCheckpoint": false`` in workspace.json, and a failure in it is a warning only.
The same step compacts this host's files (last record per session, sessions older than
``"usageKeepDays"`` days, default 90, dropped); ``usage_ledger.py compact`` does it by hand.

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
import time
import sys

#: the academy checkout (marketplace root) this script belongs to
ACADEMY_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#: the workspace root; set by ``main`` (``find_workspace``), or by a caller/test directly
ROOT = None
ROLES = ("author", "expert", "researcher", "scientist", "human")
BRANCH = re.compile(r"^\d{4}-\d{2}-\d{2}/[a-z0-9][a-z0-9-]*/(%s)$" % "|".join(ROLES))
#: a branch made before ``start`` lowercased the topic (2026-11-13/T-1179-statement-hash/...):
#: ``merge`` accepts it with a warning (#120); nothing else does
LEGACY_BRANCH = re.compile(r"^\d{4}-\d{2}-\d{2}/[A-Za-z0-9][A-Za-z0-9_.-]*/(%s)$" % "|".join(ROLES))
#: append-only ledgers a sync resolves by the union of their lines, and counters it
#: resolves by the larger value (#119, #90 (c)): every other conflict is the human's
UNION_LEDGERS = re.compile(r"(^|/)\.errors/[^/]+\.jsonl$")
MAX_COUNTERS = re.compile(r"(^|/)\.ids/[^/]+$")
PROTECTED = ("main", "master")


class Refuse(Exception):
    pass


def _run_pin():
    """``run_pin.py`` beside this script (#97), or None when it cannot be loaded."""
    try:
        spec = importlib.util.spec_from_file_location(
            "_ship_run_pin", os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_pin.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:   # noqa: BLE001 -- a warning's helper never fails a command
        return None


def warn_live_runs(repo, what):
    """Warn on stderr when a workflow run is live on ``repo`` (#97): it reads its scripts and
    nested workflows from its pin, which ``what`` leaves alone, but the agent definitions,
    hooks and skills of a plugin loaded from this checkout change under it. Never refuses."""
    rp = _run_pin()
    try:
        runs = rp.live(repo) if rp else []
    except Exception:   # noqa: BLE001
        return
    if not runs:
        return
    print("ship: warning: %d workflow run%s live on %s: %s; %s changes this checkout under "
          "%s: its scripts and nested workflows run from the pin and do not move, but the "
          "agent definitions, hooks and skills of a plugin loaded from this checkout do. A run "
          "that is over and still listed: py %s end --run <run>"
          % (len(runs), " is" if len(runs) == 1 else "s are", repo,
             "; ".join(rp.describe(m) for m in runs), what, "it" if len(runs) == 1 else "them",
             os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_pin.py")),
          file=sys.stderr)


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


#: the target of the workspace repo's own files (not the board, not a submodule)
WORKSPACE = "workspace"


def prefix_of(sub):
    """The pathspec (a directory relative to the workspace root) a superproject target is
    limited to, or None for a submodule. ``workspace`` is ``.``: the whole superproject,
    less what ``scope_specs`` excludes."""
    if sub in submodule_names():
        return None
    if sub == WORKSPACE and os.path.exists(os.path.join(ROOT, ".git")):
        return "."
    return root_dirs().get(sub)


def scope_spec(prefix):
    """The git pathspec for a superproject target's directory (top-anchored, literal)."""
    return ":(top,literal)%s" % prefix.rstrip("/")


def foreign_dirs():
    """The directories of the superproject that are other targets' (the board's, each
    submodule's), relative to the workspace root."""
    return sorted(set(root_dirs().values()) | set(submodule_names()))


def scope_specs(prefix):
    """The pathspecs of a superproject target: its directory, or for ``workspace`` the
    whole tree without the other targets' directories."""
    if prefix != ".":
        return [scope_spec(prefix)]
    return [":(top)"] + [":(top,exclude,literal)%s" % d for d in foreign_dirs()]


def common_dir(path):
    """The real, case-normalised ``git rev-parse --git-common-dir`` of the checkout ``path``."""
    out = git(path, "rev-parse", "--git-common-dir")
    full = out if os.path.isabs(out) else os.path.join(path, out)
    return os.path.normcase(os.path.realpath(full))


def main_checkout(repo):
    """The main working tree of ``repo``'s repository (``repo`` itself unless it is a linked
    worktree), as an absolute path.

    Not the first line of ``git worktree list``: for a submodule whose git directory lives
    in the superproject (``.git`` is a ``gitdir:`` file, what ``git submodule update``
    makes) that line is the git directory, and a worktree "under the main checkout" landed
    inside the superproject's ``.git`` (review, 2026-11-14)."""
    repo = os.path.abspath(repo)
    top = git(repo, "rev-parse", "--show-toplevel", check=False) or repo
    gd = git(repo, "rev-parse", "--absolute-git-dir", check=False)
    try:
        common = common_dir(repo)
    except Refuse:
        return os.path.abspath(top)
    if not gd or os.path.normcase(os.path.realpath(gd)) == common:
        return os.path.abspath(top)             # not a linked worktree: this is the main one
    # a linked worktree: the main tree is where the common git dir says it is
    wt = git(common, "config", "--file", os.path.join(common, "config"), "--get",
             "core.worktree", check=False)
    if wt:
        return os.path.abspath(wt if os.path.isabs(wt) else os.path.join(common, wt))
    if os.path.basename(common) == ".git":
        return os.path.dirname(common)
    return os.path.abspath(top)


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


def main_branch(repo):
    for b in PROTECTED:
        if git(repo, "rev-parse", "--verify", "--quiet", "refs/heads/" + b, check=False) \
                or git(repo, "rev-parse", "--verify", "--quiet", "refs/remotes/origin/" + b, check=False):
            return b
    return PROTECTED[0]


def base_of(repo, branch):
    """The branch ``branch`` was started on (``start`` records it), else the main branch."""
    b = git(repo, "config", "--get", "branch.%s.ship-base" % branch, check=False)
    return b or main_branch(repo)


def cmd_start(a):
    repo = repo_of(a.sub, a.repo)
    name = branch_name(a.topic, a.role or default_role(repo))
    exists = git(repo, "rev-parse", "--verify", "--quiet", "refs/heads/" + name, check=False)
    on = getattr(a, "on", None)
    if on:
        if exists:
            raise Refuse("%s exists already; --on names the base of a new branch" % name)
        if not git(repo, "rev-parse", "--verify", "--quiet", on + "^{commit}", check=False):
            raise Refuse("--on %r is not a branch or commit of %s" % (on, repo))
    # the base of the new branch: --on, else the branch the checkout is on (a stack)
    base = (on[len("origin/"):] if on and on.startswith("origin/") else on) or current(repo)
    if a.worktree:
        # always beside the other worktrees, under the main checkout: started from a
        # worktree (--repo), the new one must not be nested inside it, and a relative
        # --repo must not be joined twice (git runs in ``repo``)
        wt = os.path.join(main_checkout(repo), ".claude", "worktrees", name.replace("/", "-"))
        args = ["worktree", "add", wt] + ([name] if exists else ["-b", name] + ([on] if on else []))
        git(repo, *args)
        print("worktree %s on %s" % (wt, name))
    else:
        git(repo, "switch", name) if exists else git(repo, "switch", "-c", name, *([on] if on else []))
        print("%s on %s (uncommitted changes carried along)" % (repo, name))
    main = main_branch(repo)
    if not exists and base and base not in PROTECTED:
        # a session's clone can hold an old origin/main, against which a fresh session
        # branch looks like work of its own; ask the remote once, and go on without it
        try:
            subprocess.run(["git", "-C", repo, "fetch", "-q", "origin", main], capture_output=True,
                           env=git_env(), stdin=subprocess.DEVNULL, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
    main_ref = next((r for r in ("refs/remotes/origin/" + main, "refs/heads/" + main)
                     if git(repo, "rev-parse", "--verify", "--quiet", r, check=False)), None)
    own = git(repo, "rev-list", "--count", "%s..%s" % (main_ref, on or base), check=False) \
        if (main_ref and base) else "1"
    # a base with no commit of its own over main (a fresh session branch) is not a stack
    if not exists and base and base != name and base not in PROTECTED and own != "0":
        git(repo, "config", "branch.%s.ship-base" % name, base)
        print("stacked on %s (its pull request's base; 'stack %s' shows the chain)" % (base, a.sub))


def stack_of(repo, branch=None):
    """The chain from ``branch`` (default: the current one) down to the main branch:
    ``[{branch, base, sha, pushed, ahead}]``, top first. ``ahead`` counts the commits the
    branch has over its base; ``pushed`` says the remote branch is at the local tip."""
    out, seen = [], set()
    b = branch or current(repo)
    main = main_branch(repo)
    while b and b not in PROTECTED and b not in seen:
        seen.add(b)
        tip = git(repo, "rev-parse", "--verify", "--quiet", "refs/heads/" + b, check=False)
        if not tip:
            break
        base = base_of(repo, b)
        # main is counted from the remote's (a local main is often behind in a session)
        order = ("refs/remotes/origin/" + base, "refs/heads/" + base) if base in PROTECTED \
            else ("refs/heads/" + base, "refs/remotes/origin/" + base)
        base_ref = next((r for r in order
                         if git(repo, "rev-parse", "--verify", "--quiet", r, check=False)), None)
        ahead = git(repo, "rev-list", "--count", "%s..%s" % (base_ref, tip), check=False) if base_ref else ""
        remote = git(repo, "rev-parse", "--verify", "--quiet", "refs/remotes/origin/" + b, check=False)
        out.append({"branch": b, "base": base, "sha": tip[:12], "pushed": remote == tip,
                    "ahead": int(ahead) if ahead.isdigit() else None})
        b = base
    if not out:
        raise Refuse("%s is on %r: no stack (run 'start' first)" % (repo, current(repo) or "(detached)"))
    out[-1].setdefault("root", main)
    return out


def cmd_stack(a):
    repo = repo_of(a.sub, a.repo)
    chain = stack_of(repo)
    forks = fork_branches(repo, remote=True)
    if a.json:
        print(json.dumps(chain, indent=1))
        return
    n = len(chain)
    print("%s: a stack of %d branch(es), bottom first; open the pull requests in this order" % (a.sub, n))
    for k, row in enumerate(reversed(chain), 1):
        print("%d/%d  %s @ %s  %s commit(s) over %s  [%s]" % (
            k, n, row["branch"], row["sha"][:7], "?" if row["ahead"] is None else row["ahead"],
            row["base"], "pushed" if row["pushed"] else "NOT pushed: 'push' first"))
        print("     pull request: head %s -> base %s" % (row["branch"], row["base"]))
    if forks:
        # the stack above shows only this branch's own chain; work committed on another
        # recent ticket branch is not in it (#130: "a stack of 1 branch" hid eight forks)
        print("FORKS: %d recent work branch(es) hold commits this tip lacks (merge them in, "
              "or they never reach main with it):" % len(forks))
        for f in forks:
            print("     %s @ %s" % (f["branch"], f["sha"][:7]))


# ----------------------------------------------------------------------------
# The push gate: what CI would run, run here before a push (module docstring)
# ----------------------------------------------------------------------------

GATE_FILE = "ship.json"
GATE_TAIL = 25


def push_gate_steps(repo):
    """The steps of ``repo``'s push gate (``ship.json`` at its top level), or []."""
    top = git(repo, "rev-parse", "--show-toplevel", check=False) or repo
    try:
        with open(os.path.join(top, GATE_FILE), encoding="utf-8") as f:
            steps = json.load(f).get("pushGate")
    except (OSError, ValueError, AttributeError):
        return top, []
    if steps is False:
        return top, None                    # the repo declares it has no push gate
    out = []
    for s in steps if isinstance(steps, list) else []:
        if isinstance(s, dict) and isinstance(s.get("run"), list) and s["run"]:
            out.append(s)
    return top, out


def run_push_gate(repo):
    """Run the push gate of ``repo``. Returns ``(ok, lines)``: ``lines`` say what ran, was
    skipped or failed (a failure with the tail of the step's output)."""
    if workspace_json().get("pushGate") is False:
        return True, []
    top, steps = push_gate_steps(repo)
    if steps is None:
        return True, []
    ci_steps, ci_problems = ci_plan(top)
    if not steps and not ci_steps and not ci_problems:
        return True, []
    tree = git(repo, "rev-parse", "HEAD^{tree}", check=False)
    clean = not git(repo, "status", "--porcelain", "--untracked-files=no", check=False)
    gdir = git(repo, "rev-parse", "--absolute-git-dir", check=False)
    marker = os.path.join(gdir, "ship-gate", tree) if (gdir and tree and clean) else None
    if marker and os.path.isfile(marker):
        return True, ["push gate: this tree passed before (%s)" % tree[:12]]
    lines = []
    if not clean:
        lines.append("push gate: note: uncommitted changes in tracked files; the gate runs "
                     "on the working tree, not on what is pushed")
    for s in steps:
        name = str(s.get("name") or s["run"][0])
        argv = [sys.executable if str(x) == "{python}" else str(x) for x in s["run"]]
        env = dict(os.environ, **{str(k): str(v) for k, v in (s.get("env") or {}).items()})
        try:
            p = subprocess.run(argv, cwd=top, capture_output=True, text=True, env=env,
                               stdin=subprocess.DEVNULL, timeout=int(s.get("timeout") or 900))
        except FileNotFoundError:
            if s.get("optional"):
                lines.append("push gate: %s skipped (%s is not installed)" % (name, argv[0]))
                continue
            return False, lines + ["push gate: %s: %s is not installed" % (name, argv[0])]
        except subprocess.TimeoutExpired:
            return False, lines + ["push gate: %s timed out" % name]
        if p.returncode:
            tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-GATE_TAIL:]
            return False, lines + ["push gate: %s failed (exit %d):" % (name, p.returncode)] \
                + ["    " + t for t in tail]
        lines.append("push gate: %s ok" % name)
    if ci_steps or ci_problems:
        ok, ci_lines = _ci().run(top)
        lines += ["push gate: " + ln if not ln.startswith("    ") else ln for ln in ci_lines]
        if not ok:
            return False, lines
    if marker:
        try:
            os.makedirs(os.path.dirname(marker), exist_ok=True)
            with open(marker, "w", encoding="utf-8") as f:
                f.write(datetime.datetime.now(datetime.timezone.utc).isoformat() + "\n")
        except OSError:
            pass
    return True, lines


def _ci():
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import ci_local
    return ci_local


def ci_plan(top):
    """The workflow steps the push gate runs for the repo at ``top`` (``ci_local.plan``)."""
    try:
        return _ci().plan(top)
    except Exception as exc:        # a broken runner must fail the gate, not pass it
        return [], ["the workflow files could not be planned (%s)" % exc]


def require_push_gate(repo, no_gate=False):
    if no_gate:
        top, steps = push_gate_steps(repo)
        if steps or (steps is not None and any(ci_plan(top))):
            print("ship: warning: --no-gate given, the push gate is skipped", file=sys.stderr)
        return
    ok, lines = run_push_gate(repo)
    for ln in lines if ok else []:
        print("ship: " + ln, file=sys.stderr)
    if not ok:
        raise Refuse("the push gate refused the push (the commit is kept):\n  %s\n"
                     "(fix it and push again; --no-gate only on the human's word)"
                     % "\n  ".join(lines))


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
    # run from a workflow run's pin (#97): the pin's gate, never the live checkout's
    rp = _run_pin()
    if rp and rp.is_pin_path(ACADEMY_REPO):
        return os.path.join(ACADEMY_REPO, "author", "scripts")
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
        base = os.path.realpath(os.path.join(top, prefix)) if prefix else top
        rels = []
        for p in paths:
            pp = p.replace("\\", "/")
            if prefix and not os.path.isabs(p) and pp.startswith(prefix.rstrip("/") + "/") \
                    and not os.path.exists(os.path.join(base, p)):
                # --paths are relative to the target; "board/x" for target board meant "x"
                # (ledger 2026-10-31: :(top)board/board/.errors/... did not match)
                p = pp[len(prefix.rstrip("/")) + 1:]
                print("ship: note: --paths are relative to %s/; read %r as %r"
                      % (prefix.rstrip("/"), pp, p), file=sys.stderr)
            full = os.path.realpath(p if os.path.isabs(p) else os.path.join(base, p))
            try:
                inside = os.path.commonpath([base, full]) == base
            except ValueError:  # different drives
                inside = False
            if not inside:
                raise Refuse("path %r is outside the %s %s" % (p, "directory" if prefix else "repo", base))
            rels.append(os.path.relpath(full, top).replace(os.sep, "/"))
            if prefix == ".":
                other = next((d for d in foreign_dirs()
                              if rels[-1] == d or rels[-1].startswith(d + "/")), None)
                if other:
                    raise Refuse("path %r is in %s/, which is the target %s, not %s"
                                 % (p, other, next((n for n, r in root_dirs().items() if r == other),
                                                   other), WORKSPACE))
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
        scope = ["--"] + (paths or scope_specs(prefix))
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
             git(repo, "diff", "--cached", "--raw", "--no-renames", "--ignore-submodules=none",
                 *scope).splitlines()
             if "\t" in l and "160000" in l.lstrip(":").split()[:2]]
    if links:
        git(repo, "reset", "-q", "--", *links)
    return links


def cmd_push(a):
    repo = repo_of(a.sub, a.repo)
    b = require_template(repo)
    require_push_gate(repo, getattr(a, "no_gate", False))
    git(repo, "push", "-q", "-u", "origin", "HEAD:refs/heads/" + b)
    print("%s -> origin/%s @ %s" % (a.sub, b, git(repo, "rev-parse", "--short", "HEAD")))
    base = base_of(repo, b)
    if base not in PROTECTED:
        print("stacked on %s: its pull request's base is %s ('stack %s')" % (base, base, a.sub))


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
    if branch in PROTECTED or not (BRANCH.match(branch) or LEGACY_BRANCH.match(branch)):
        raise Refuse("%r is not a <date>/<topic>/<role> template branch; refusing to merge it" % branch)
    if not BRANCH.match(branch):
        print("ship: warning: %s is a legacy branch name (uppercase or '_' in the topic, made "
              "before start lowercased topics): merged as it is (#120)" % branch, file=sys.stderr)
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
    warn_live_runs(repo, "the merge")
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
            git(ROOT, "add", "-f", "--", a.sub)   # -f: under ignore = all a plain add skips the pointer
            git(ROOT, "commit", "-q", "-m", "Bump %s to %s" % (a.sub, short), "--", a.sub)
        except Refuse as e:
            raise Refuse("merge done; bump failed: %s" % e)
        print("superproject: Bump %s to %s @ %s" % (a.sub, short, git(ROOT, "rev-parse", "--short", "HEAD")))


def _stage_bytes(repo, stage, path):
    """The file at merge stage ``stage``, as bytes (never decoded: a ledger line is kept
    byte for byte, whatever the locale); None when that side has no such file."""
    p = subprocess.run(["git", "-C", repo, "show", ":%d:%s" % (stage, path)], capture_output=True,
                       env=git_env(), stdin=subprocess.DEVNULL)
    return p.stdout if p.returncode == 0 else None


def resolve_ledger(repo, path):
    """Resolve one conflicted ledger or counter in the merge in progress, or return False:
    a ``.errors/*.jsonl`` ledger is ours then every line of theirs ours lacks (order kept,
    each line once); an ``.ids/*`` counter is the larger number."""
    top = git(repo, "rev-parse", "--show-toplevel")
    ours, theirs = _stage_bytes(repo, 2, path), _stage_bytes(repo, 3, path)
    if ours is None or theirs is None:
        return False         # a delete/modify conflict is the human's, never resolved here
    if UNION_LEDGERS.search(path):
        # records are separated by b"\n" only (a JSON string may hold U+2028); our lines
        # first, then theirs beyond the common start: an appended line is kept even when
        # it repeats an earlier record
        a, b = ours.split(b"\n"), theirs.split(b"\n")
        a = a[:-1] if a and a[-1] == b"" else a
        b = b[:-1] if b and b[-1] == b"" else b
        n = 0
        while n < min(len(a), len(b)) and a[n] == b[n]:
            n += 1
        out = a + [ln for ln in b[n:] if ln not in set(a[n:])]
        data = b"\n".join(out) + (b"\n" if out else b"")
    elif MAX_COUNTERS.search(path):
        vals = [x.strip() for x in (ours, theirs)]
        if not all(re.fullmatch(rb"\d+", v) for v in vals):
            return False
        data = b"%d\n" % max(int(v) for v in vals)
    else:
        return False
    with open(os.path.join(top, path), "wb") as f:
        f.write(data)
    git(repo, "add", "--", path)
    return True


def unmerged(repo):
    return [p for p in git(repo, "diff", "--name-only", "--diff-filter=U").splitlines() if p]


def cmd_sync(a):
    """Bring origin/main into the current work branch (#91, #119): ``git merge`` of
    origin/main; the append-only ledgers and counters are resolved (``resolve_ledger``);
    any other conflict stops with the files listed and the merge left in progress, for
    the human to resolve and record with ``sync --continue``, which commits the whole
    merge (a pathspec commit is refused during a merge). Never pushes: ``push`` does."""
    repo = repo_of(a.sub, a.repo)
    b = require_template(repo)
    key = "branch.%s.ship-sync" % b
    if a.cont:
        if not merge_in_progress(repo):
            raise Refuse("%s has no merge in progress; nothing to continue" % repo)
        # only the merge this command started (review of a651426: any merge was committed)
        want = git(repo, "config", "--get", key, check=False)
        head = git(repo, "rev-parse", "MERGE_HEAD")
        if not want or want.split()[0] != head:
            raise Refuse("the merge in progress (%s) is not one 'sync' started; finish it with git, "
                         "or 'git merge --abort'" % head[:9])
        left = unmerged(repo)
        if left:
            raise Refuse("still unmerged: %s; resolve them and 'git add' each, then sync --continue"
                         % ", ".join(left))
        git(repo, "commit", "-q", "-m", "Sync %s with origin/%s" % (b, want.split()[1]))
        git(repo, "config", "--unset", key, check=False)
        print("%s %s @ %s: merge recorded; 'push %s' sends it through the gate"
              % (a.sub, b, git(repo, "rev-parse", "--short", "HEAD"), a.sub))
        return 0
    require_clean(repo, ignore_submodules=bool(prefix_of(a.sub)))
    # a stacked branch syncs with the branch it was started on, else with main
    base = base_of(repo, b)
    src = a.source or (base if base not in PROTECTED else main_branch(repo))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", src):
        raise Refuse("--from %r is not a branch name" % src)
    git(repo, "fetch", "-q", "origin", src)
    ref = "refs/remotes/origin/" + src
    if subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", ref, "HEAD"],
                      capture_output=True, env=git_env(), stdin=subprocess.DEVNULL).returncode == 0:
        print("%s %s already contains origin/%s; nothing to sync" % (a.sub, b, src))
        return 0
    p = subprocess.run(["git", "-C", repo, "merge", "-q", "--no-ff", "--no-commit", ref],
                       capture_output=True, text=True, env=git_env(), stdin=subprocess.DEVNULL)
    if p.returncode and not merge_in_progress(repo):
        raise Refuse("git merge origin/%s failed in %s: %s" % (src, repo, (p.stderr or p.stdout).strip()))
    git(repo, "config", key, "%s %s" % (git(repo, "rev-parse", ref), src))
    if prefix_of(a.sub):
        # a superproject target: main's own pointer and file changes come with it (a merge
        # cannot take only board/); say so, the push gate and the review see them
        outside = [f for f in git(repo, "diff", "--cached", "--name-only", "HEAD").splitlines()
                   if f and not f.startswith(prefix_of(a.sub).rstrip("/") + "/")]
        if outside:
            print("ship: note: the sync also brings main's changes outside %s: %s"
                  % (prefix_of(a.sub), ", ".join(outside[:12]) + (" ..." if len(outside) > 12 else "")),
                  file=sys.stderr)
    resolved = [f for f in unmerged(repo) if resolve_ledger(repo, f)]
    left = unmerged(repo)
    if left:
        print("ship: sync stopped on conflicts in %s%s; resolve them and 'git add' each, then "
              "'ship.py sync %s --continue' (or 'git merge --abort')"
              % (", ".join(left), (" (ledgers resolved: %s)" % ", ".join(resolved)) if resolved else "",
                 a.sub), file=sys.stderr)
        return 1
    git(repo, "commit", "-q", "-m", "Sync %s with origin/%s" % (b, src))
    git(repo, "config", "--unset", key, check=False)
    print("%s %s @ %s: synced with origin/%s%s; 'push %s' sends it through the gate"
          % (a.sub, b, git(repo, "rev-parse", "--short", "HEAD"), src,
             (" (ledgers resolved: %s)" % ", ".join(resolved)) if resolved else "", a.sub))
    return 0


def cmd_bump(a):
    """Commit the superproject pointer of each submodule to its reviewed main tip (#91):
    the bump without a merge (``merge --bump`` does both). The pointer must be the sha
    given, which must be the submodule's origin/main or an ancestor of it."""
    if not a.subs:
        raise Refuse("name the submodules to bump")
    shas = a.sha or []
    if len(shas) != len(a.subs):
        raise Refuse("give one --sha per submodule (%d submodules, %d --sha)" % (len(a.subs), len(shas)))
    names = submodule_names()
    done = []
    checked = []
    for sub, sha in zip(a.subs, shas):
        if sub not in names:
            raise Refuse("%s is not a submodule path in %s" % (sub, os.path.join(ROOT, ".gitmodules")))
        repo = os.path.join(ROOT, sub)
        git(repo, "fetch", "-q", "origin", "main")
        full = git(repo, "rev-parse", "--verify", "--quiet", sha + "^{commit}", check=False)
        if not full:
            raise Refuse("%s: no commit %s" % (sub, sha))
        if subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", full,
                           "refs/remotes/origin/main"], capture_output=True, env=git_env(),
                          stdin=subprocess.DEVNULL).returncode:
            raise Refuse("%s: %s is not on origin/main; publish it first" % (sub, full[:9]))
        head = git(repo, "rev-parse", "HEAD")
        if head != full:
            raise Refuse("%s's checkout is at %s, not %s: check out %s there first (the pointer "
                         "is the checkout's commit)" % (sub, head[:9], full[:9], full[:9]))
        checked.append(sub)
        done.append("%s to %s" % (sub, full[:9]))
    for sub in checked:          # every one checked first: a refusal stages nothing
        git(ROOT, "add", "-f", "--", sub)   # -f: under ignore = all a plain add skips the pointer
    # --ignore-submodules=none: the workspace's .gitmodules sets ignore = all, which hides
    # every pointer change from a plain diff (2026-11-20: every real bump said "nothing to bump")
    if not git(ROOT, "diff", "--cached", "--name-only", "--ignore-submodules=none", "--", *a.subs):
        raise Refuse("the pointers already name those commits; nothing to bump")
    git(ROOT, "commit", "-q", "-m", "Bump " + ", ".join(done), "--", *a.subs)
    print("superproject: Bump %s @ %s" % (", ".join(done), git(ROOT, "rev-parse", "--short", "HEAD")))
    return 0


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
    warn_live_runs(repo, "the publish")
    # the verified SHA is the source, not the ref: main moving after the check changes nothing
    p = subprocess.run(["git", "-C", repo, "push", "--no-follow-tags", "--recurse-submodules=no",
                        "origin", "%s:refs/heads/main" % head], capture_output=True, text=True,
                       env=git_env(), stdin=subprocess.DEVNULL)
    if p.returncode:
        raise Refuse("the remote rejected the push of main:\n%s" % (p.stderr or p.stdout).strip())
    print("%s: origin/main @ %s" % (a.sub, head[:9]))


def drifted_pointers():
    """The submodules whose checked-out commit differs from the superproject's pointer.
    Read with ``--ignore-submodules=none``: the workspace's .gitmodules sets
    ``ignore = all`` (2026-10-31) so that git status stays quiet about pointer-only drift,
    which moves only through 'merge --bump'."""
    out = git(ROOT, "diff", "--ignore-submodules=none", "--name-only", check=False) or ""
    subs = set(submodule_names())
    return [p for p in out.splitlines() if p in subs]


#: the label of the superproject's own worktrees in ``status``
SUPERPROJECT = "superproject"
#: git calls of ``status``'s worktree scan run side by side (each is mostly waiting on disk)
SCAN_WORKERS = 8
AHEAD = re.compile(r"\bahead (\d+)")


def _git_quiet(repo, *args):
    """``git --no-optional-locks -C repo args``: (returncode, stdout). Never refreshes the
    index on disk, so a scan cannot race an agent committing in that worktree."""
    p = subprocess.run(["git", "--no-optional-locks", "-C", repo, *args], capture_output=True,
                       text=True, env=git_env(), stdin=subprocess.DEVNULL)
    return p.returncode, p.stdout


def linked_worktrees(repo):
    """The linked worktrees of ``repo``'s repository, as dicts ``path``, ``head`` (sha or
    ''), ``branch`` (short name, or '' when detached): every entry of ``git worktree list``
    but the first (the main one: for a submodule whose git directory is absorbed into
    the superproject that entry is the git directory), a bare one, and ``repo`` itself."""
    rc, out = _git_quiet(repo, "worktree", "list", "--porcelain")
    if rc:
        return []
    entries, cur = [], None
    for line in out.splitlines() + [""]:
        if not line:
            if cur is not None:
                entries.append(cur)
            cur = None
            continue
        key, _, val = line.partition(" ")
        if key == "worktree":
            cur = {"path": val, "head": "", "branch": "", "bare": False, "locked": False}
        elif cur is None:
            continue
        elif key == "HEAD":
            cur["head"] = val
        elif key == "branch":
            cur["branch"] = val[len("refs/heads/"):] if val.startswith("refs/heads/") else val
        elif key == "bare":
            cur["bare"] = True
        elif key == "locked":
            cur["locked"] = True
    me = os.path.normcase(os.path.realpath(repo))
    return [e for e in entries[1:]
            if not e["bare"] and os.path.normcase(os.path.realpath(e["path"])) != me]


def branch_ahead(repo):
    """``{branch: commits ahead of its upstream}`` for every local branch with an
    upstream, from one ``for-each-ref`` (no fetch: the remote-tracking refs as they are)."""
    rc, out = _git_quiet(repo, "for-each-ref", "--format=%(refname)%00%(upstream:track)",
                         "refs/heads")
    ahead = {}
    for line in out.splitlines() if not rc else ():
        name, _, track = line.partition("\0")
        name = name[len("refs/heads/"):] if name.startswith("refs/heads/") else name   # a tag of the same name made :short ambiguous
        m = AHEAD.search(track)
        if m:
            ahead[name] = int(m.group(1))
    return ahead


def worktree_work(repo, wt, ahead):
    """The state of one linked worktree ``wt`` (a ``linked_worktrees`` entry) of ``repo``:
    ``wt`` plus ``missing`` (its directory is gone), ``dirty`` (entries of ``git status
    --porcelain``, untracked files included: new files are work too; None if unreadable),
    ``unpushed`` (commits of its HEAD on no remote-tracking branch) and ``ahead`` (of its
    branch's upstream)."""
    st = dict(wt, missing=not os.path.isdir(wt["path"]), dirty=0, unpushed=0,
              ahead=ahead.get(wt["branch"], 0))
    if not st["missing"]:
        rc, out = _git_quiet(wt["path"], "status", "--porcelain")
        st["dirty"] = None if rc else len(out.splitlines())
    if wt["head"] and set(wt["head"]) != {"0"}:      # an unborn (orphan) HEAD has no commits
        rc, out = _git_quiet(repo, "rev-list", "--count", wt["head"], "--not", "--remotes")
        st["unpushed"] = None if rc else int(out.strip() or 0)
    return st


def worktree_report(repos, show_all=False):
    """The rows of ``status``'s worktree section: for each ``(label, checkout)`` in
    ``repos``, every linked worktree holding work (uncommitted changes, commits on no
    remote branch, a branch ahead of its upstream; an unreadable count counts as work),
    and with ``show_all`` the others too, marked removable. The git calls run side by
    side; the rows keep the order of ``repos`` and of ``git worktree list``."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=SCAN_WORKERS) as pool:
        listed = list(pool.map(lambda r: (linked_worktrees(r[1]), branch_ahead(r[1])), repos))
        jobs = [(label, repo, wt, ahead) for (label, repo), (wts, ahead) in zip(repos, listed)
                for wt in wts]
        states = list(pool.map(lambda j: worktree_work(j[1], j[2], j[3]), jobs))
    rows = []
    rp = _run_pin()
    for (label, repo, _wt, _ahead), st in zip(jobs, states):
        # a workflow run's pinned code (run_pin.py, #97) holds no work: never offered as removable
        pin = bool(rp and rp.is_pin_path(st["path"]))
        work = not pin and (st["dirty"] != 0 or st["unpushed"] != 0 or st["ahead"])
        if not (work or show_all):
            continue
        top = os.path.realpath(repo)
        full = os.path.realpath(st["path"])
        try:
            inside = os.path.commonpath([top, full]) == top
        except ValueError:  # different drives
            inside = False
        shown = os.path.relpath(full, top) if inside else st["path"]
        count = lambda n: "?" if n is None else n  # noqa: E731
        # a clean one: a gone directory needs `git worktree prune`, a locked one `remove -f -f`
        marks = (["missing"] if st["missing"] else []) + (
            [] if work else ["prunable"] if st["missing"] else ["run pin"] if pin else
            ["locked"] if st.get("locked") else ["removable"])
        rows.append("  %-26s %-58s %-44s dirty=%s unpushed=%s%s%s" % (
            label, shown, st["branch"] or "(detached)", count(st["dirty"]),
            count(st["unpushed"]), " ahead=%d" % st["ahead"] if st["ahead"] else "",
            " [%s]" % ", ".join(marks) if marks else ""))
    return rows


def status_repos():
    """``(label, checkout)`` for each checked-out submodule, then the superproject."""
    repos = [(sub, os.path.join(ROOT, sub)) for sub in submodule_names()
             if os.path.exists(os.path.join(ROOT, sub, ".git"))]
    if os.path.exists(os.path.join(ROOT, ".git")):
        repos.append((SUPERPROJECT, ROOT))
    return repos


def cmd_status(a):
    drift = drifted_pointers()
    if drift:
        print("superproject pointers behind their checkouts (moved only by 'merge --bump'): %s"
              % ", ".join(drift))
    for sub in targets() + ([WORKSPACE] if prefix_of(WORKSPACE) == "." else []):
        try:
            repo = repo_of(sub)
        except Refuse:
            print("%-28s (not checked out)" % sub)
            continue
        prefix = prefix_of(sub)
        b = current(repo)
        # a superproject target counts its own directory only (submodule pointers aside)
        spec = ["--"] + scope_specs(prefix) if prefix else []
        dirty = len([l for l in git(repo, "status", "--porcelain", *spec).splitlines()
                     if not l.startswith("??")])
        up = git(repo, "rev-list", "--count", "@{u}..HEAD", check=False) if b else ""
        flag = "ok" if BRANCH.match(b) else ("PROTECTED" if b in PROTECTED else "off-template")
        if BRANCH.match(b) and prefix != ".":
            # a superproject target counts the forks inside its own directory only
            n = len([f for f in fork_branches(repo, remote=True)
                     if not prefix or not _outside(repo, f["sha"], prefix)])
            if n:
                flag += ", %d fork(s): 'stack %s'" % (n, sub)
        print("%-28s %-44s dirty=%s unpushed=%s [%s]%s" % (sub, b or "(detached)", dirty, up or "-", flag,
                                                       (" (superproject, without the board and the submodules)"
                                                        if prefix == "." else
                                                        " (superproject, %s/ only)" % prefix) if prefix else ""))
    show_all = getattr(a, "all", False)
    rows = worktree_report(status_repos(), show_all)
    if rows:
        print("worktrees %s (dirty includes untracked files):"
              % ("of every repo; the clean, pushed ones are removable" if show_all else
                 "holding work not on a remote (--all: the clean ones too)"))
        for row in rows:
            print(row)


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


def path_specs(paths):
    """Literal, top-anchored git pathspecs for repo-relative file paths (``--touched``)."""
    return [":(top,literal)%s" % p for p in paths]


def worktree_state(repo, pathspec=None, specs=None):
    """(dirty, skipped) from ``git status --porcelain -z --untracked-files=all``: dirty is
    True when any entry is left once untracked nested repositories and worktrees (an
    untracked directory with a ``.git`` of its own) are set aside; skipped lists those,
    '/'-terminated. Ignored files are not entries at all. With ``pathspec`` (a directory
    of a superproject target) only entries under it count; with ``specs`` (git pathspecs)
    only entries they match."""
    spec = ["--"] + list(specs) if specs else (["--", scope_spec(pathspec)] if pathspec else [])
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


def dirty_among(repo, paths):
    """The entries of ``paths`` (repo-relative) that ``git status`` reports now (both sides
    of a rename), in their order: a path made and removed again during the ticket is not
    dirty, and ``git add`` of its pathspec would fail."""
    if not paths:
        return []
    raw = git(repo, "status", "--porcelain", "-z", "--untracked-files=all", "--",
              *path_specs(paths), strip=False)
    fields, seen, i = raw.split("\0"), set(), 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        seen.add(entry[3:].rstrip("/"))
        if entry[0] in "RC" and i < len(fields):
            seen.add(fields[i].rstrip("/"))
            i += 1
    return [p for p in paths if p.rstrip("/") in seen]


NAMES_SHOWN = 20


def checkpoint_repo(sub, repo, name, message, remote, scoped=False, pathspec=None, paths=None,
                    run=None):
    """One repo of a checkpoint; returns its result dict (see ``run_checkpoint``).

    ``pathspec`` (a superproject target such as ``board``: the directory, relative to the
    workspace root): only changes under it are looked at, staged (``add -A -- <dir>/``,
    not ``:/``) and committed (``commit -- <dir>/``), so whatever else is dirty or staged
    in the superproject -- another directory, a moved submodule pointer -- is left
    exactly as it was.

    ``paths`` (``--touched``: the files the ticket's role wrote in another role's home,
    repo-relative): only these are looked at, staged and committed, and the repo is never
    moved to the ticket's branch while anything else in it is uncommitted -- that work is
    not the ticket's, and a switch would carry it onto the ticket's branch: the repo is
    then refused and nothing is shipped there. Already on the ticket's branch, only the
    paths are committed. Always scoped (a dirty repo on main/master is refused).

    While another live run holds a lease anywhere in the workspace (``foreign_lease``), a
    pathspec target is committed by ``checkpoint_tree`` instead: onto the ticket's branch
    without switching the checkout, which that run shares (#96; the human's ruling
    2026-11-27, "plumbing only in parallel"); with no other run it is switched and
    committed as above. A repo whose lease (``.academy/leases``) belongs to a live run
    other than ``run`` is never switched: it is refused (#96)."""
    if pathspec and foreign_lease(run):
        return checkpoint_tree(sub, repo, name, message, remote, pathspec, paths)
    res = {"sub": sub, "branch": name, "sha": "", "files": 0, "status": "unchanged", "detail": "",
           "names": [], "skipped": [], "merged": [], "forks": []}
    given = bool(paths)
    if given:
        scoped = True
        # a path made and removed again is not dirty: 'git add' of it would fail
        paths = dirty_among(repo, paths)
    specs = path_specs(paths) if paths else None

    def sha():
        return git(repo, "rev-parse", "--short", "HEAD", check=False)

    def refused(why):
        res.update(status="skipped", sha=sha(), detail="refused: " + why)
        return res

    tip = git(repo, "rev-parse", "-q", "--verify", "refs/heads/" + name, check=False)
    dirty, res["skipped"] = (False, []) if given and not paths else \
        worktree_state(repo, pathspec, specs)
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
        if specs and cur != name:
            others, _ = worktree_state(repo, specs=[scope_spec(pathspec) if pathspec else ":/"] + [
                ":(top,literal,exclude)%s" % p for p in paths])
            if others:
                return refused("%s has other uncommitted changes besides %s, which are not "
                               "this ticket's; nothing is shipped there (commit or stash them, "
                               "then re-run the ticket's --check)"
                               % (cur, ", ".join(paths)))
        if cur != name:
            # #96: a checkout another live run holds the lease of is that run's to switch
            holder = lease_holder(sub, run)
            if holder:
                return refused("%s is leased by %s; it is not switched to %s (its changes "
                               "may be that run's): re-run this ticket's --check once that run "
                               "has ended" % (sub, holder, name))
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
            scope = ["--"] + specs if specs else (["--", scope_spec(pathspec)] if pathspec else [])
            if specs:
                # 'add -A -- <path>' fails ("pathspec did not match") on a path in neither
                # the worktree nor the index -- a staged 'git rm', the old side of a staged
                # 'git mv' -- so those are left to 'commit -- <path>', which takes them
                indexed = set(git(repo, "ls-files", "-z", "--", *specs, strip=False).split("\0"))
                present = [p for p in paths if p in indexed
                           or os.path.lexists(os.path.join(repo, *p.split("/")))]
                if present:
                    git(repo, "add", "-A", "--", *path_specs(present), *excl)
            else:
                git(repo, "add", "-A", "--", *(scope[1:] if scope else [":/"]), *excl)
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
    if tip and current(repo) == name:
        # stack, don't fork: bring in the other recent ticket branches' work (#130)
        try:
            res["merged"], res["forks"] = merge_forks(repo, name, pathspec)
        except Refuse as e:
            res["merged"], res["forks"] = [], [{"branch": "?", "why": str(e)}]
        if res["merged"]:
            tip = git(repo, "rev-parse", "refs/heads/" + name)
    if not res["files"] and not res.get("merged"):  # no new commit: push only what the remote lacks
        if not tip:
            res["sha"] = sha()
            return res
    return push_tip(repo, name, tip, remote, res)


def push_tip(repo, name, tip, remote, res):
    """Push ``tip`` of branch ``name`` to ``remote`` through the push gate, unless the
    remote has it already (with no new commit: ``res["files"]`` 0); ``res`` updated."""
    if not res["files"]:
        out = git(repo, "ls-remote", remote, "refs/heads/" + name, check=False)
        if out and out.split()[0] == tip:
            res["sha"] = git(repo, "rev-parse", "--short", tip)
            return res
    assert BRANCH.match(name) and name not in PROTECTED, name
    res["sha"] = git(repo, "rev-parse", "--short", tip)
    ok, gate_lines = run_push_gate(repo)
    if not ok:
        res.update(status="push-failed", detail="not pushed, the commit is kept: "
                   + " / ".join(l.strip() for l in gate_lines[-6:]))
        return res
    p = subprocess.run(["git", "-C", repo, "push", "-q", "--no-follow-tags", "--recurse-submodules=no",
                        remote, "refs/heads/%s:refs/heads/%s" % (name, name)],
                       capture_output=True, text=True, env=git_env(), stdin=subprocess.DEVNULL)
    if p.returncode:
        lines = (p.stderr or p.stdout or "exit %d" % p.returncode).strip().splitlines()
        res.update(status="push-failed", detail=" / ".join(l.strip() for l in lines[-2:]))
    else:
        res["status"] = "pushed"
    return res


# ----------------------------------------------------------------------------
# Forks: work branches holding commits the current tip lacks (#130)
# ----------------------------------------------------------------------------

#: how far back a work branch counts as recent work a checkpoint stacks on (#130: the
#: forks were 1 to 5 days old); older unmerged branches are left alone
FORK_DAYS = 7


def _main_ref(repo):
    main = main_branch(repo)
    return next((r for r in ("refs/remotes/origin/" + main, "refs/heads/" + main)
                 if git(repo, "rev-parse", "--verify", "--quiet", r, check=False)), None)


def _is_ancestor(repo, a, b):
    return subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", a, b],
                          capture_output=True, env=git_env(),
                          stdin=subprocess.DEVNULL).returncode == 0


def fork_branches(repo, ref="HEAD", remote=False, days=FORK_DAYS, now=None):
    """The recent ``<date>/<topic>/<role>`` branches with commits ``ref`` lacks and main
    lacks too, oldest first: ``[{branch, sha, remote}]``. Local branches always; with
    ``remote`` also ``origin/`` ones that have no local branch of that name. A branch whose
    tip is older than ``days`` is not counted (old unmerged work is the human's, not a
    fork of today's stack)."""
    head = git(repo, "rev-parse", "--verify", "--quiet", ref, check=False)
    if not head:
        return []
    main = _main_ref(repo)
    cutoff = (now if now is not None else time.time()) - days * 86400
    pats = ["refs/heads/"] + (["refs/remotes/origin/"] if remote else [])
    rows = git(repo, "for-each-ref", "--sort=committerdate",
               "--format=%(refname)%09%(objectname)%09%(committerdate:unix)", *pats,
               check=False).splitlines()
    local = {r.split("\t")[0][len("refs/heads/"):] for r in rows
             if r.startswith("refs/heads/")}
    out, seen = [], set()
    for row in rows:
        parts = row.split("\t")
        if len(parts) != 3 or not parts[2].strip().isdigit():
            continue
        full, sha, when = parts
        is_remote = full.startswith("refs/remotes/origin/")
        name = full[len("refs/remotes/origin/"):] if is_remote else full[len("refs/heads/"):]
        if not BRANCH.match(name) or int(when) < cutoff or (is_remote and name in local):
            continue
        if sha in seen or sha == head or _is_ancestor(repo, sha, head):
            continue
        if main and _is_ancestor(repo, sha, main):
            continue
        seen.add(sha)
        out.append({"branch": ("origin/" + name) if is_remote else name, "sha": sha[:12],
                    "remote": is_remote})
    return out


def _outside(repo, ref, prefix):
    """The files ``ref`` changes, over its merge base with HEAD, outside ``prefix/``."""
    base = git(repo, "merge-base", "HEAD", ref, check=False)
    if not base:
        return ["(no common history)"]
    names = git(repo, "diff", "--name-only", base, ref, check=False).splitlines()
    return [n for n in names if n and not n.startswith(prefix.rstrip("/") + "/")]


def merge_forks(repo, name, pathspec=None):
    """Merge into ``name`` (checked out) every local fork of it (``fork_branches``), so the
    checkpoint's tip holds the work committed on the other recent ticket branches instead
    of forking from it (#130: eight library branches held decision records the tip
    lacked). Ledgers and counters are resolved as ``sync`` does (``resolve_ledger``); any
    other conflict aborts that merge and leaves the branch as a fork. Nothing is merged
    while the worktree has uncommitted changes (an abort could not restore them), and in
    a superproject target (``pathspec``) a branch changing files outside it is left as a
    fork, so a board branch takes board files only. Returns ``(merged, forks)``: the
    branches merged, and those still forked, each ``{branch, why}``."""
    forks = fork_branches(repo, "refs/heads/" + name)
    if not forks:
        return [], []
    if current(repo) != name:
        return [], [dict(f, why="not checked out") for f in forks]
    dirty = git(repo, "status", "--porcelain", "--untracked-files=no",
                "--ignore-submodules=all", check=False).strip()
    if dirty:
        return [], [dict(f, why="the worktree has uncommitted changes") for f in forks]
    merged, left = [], []
    for f in forks:
        b = f["branch"]
        if pathspec:
            out = _outside(repo, "refs/heads/" + b, pathspec)
            if out:
                left.append(dict(f, why="changes files outside %s/ (%s)"
                                 % (pathspec.rstrip("/"), ", ".join(out[:3]))))
                continue
        if _is_ancestor(repo, "refs/heads/" + b, "HEAD"):
            continue                 # an earlier merge of this loop brought it in
        p = subprocess.run(["git", "-C", repo, "merge", "-q", "--no-ff", "--no-commit",
                            "refs/heads/" + b], capture_output=True, text=True,
                           env=git_env(), stdin=subprocess.DEVNULL)
        if p.returncode and not merge_in_progress(repo):
            left.append(dict(f, why="git merge failed: %s"
                             % ((p.stderr or p.stdout).strip().splitlines() or ["?"])[-1]))
            continue
        for path in unmerged(repo):
            resolve_ledger(repo, path)
        rest = unmerged(repo)
        if rest:
            git(repo, "merge", "--abort", check=False)
            left.append(dict(f, why="conflicts in %s" % ", ".join(rest[:3])))
            continue
        if merge_in_progress(repo):
            git(repo, "commit", "-q", "-m", "Merge %s into %s (checkpoint: stack the ticket "
                "branches, #130)" % (b, name))
        merged.append(b)
    return merged, left


def _lib():
    """The academy library vendored beside this script (``scripts/_academy``): leases and
    the shipped-board ledger (#96). Standard library only, as this script."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import _academy
    return _academy


def lease_holder(sub, run=None):
    """A description of the live lease of ``sub`` held by a run other than ``run``
    (``.academy/leases/<sub>.json`` of the workspace), else ''. No library, no lease."""
    try:
        ac = _lib()
        lease = ac.lease_holder(ROOT, sub, run)
        return ac.describe_lease(lease) if lease else ""
    except Exception:  # noqa: BLE001 -- an unreadable lease is no lease
        return ""


def foreign_lease(run=None):
    """A description of a live lease in the workspace held by a run other than ``run``
    (any live lease when ``run`` is None), else '': another inbox run is working in this
    checkout. No library, no lease."""
    try:
        ac = _lib()
        for lease in ac.live_leases(ROOT):
            if run is None or lease.get("run") != run:
                return "%s: %s" % (lease.get("target"), ac.describe_lease(lease))
    except Exception:  # noqa: BLE001 -- an unreadable lease is no lease
        return ""
    return ""


def _status_paths(repo, specs):
    """``(paths, skipped)``: the entries of ``git status`` under ``specs`` (both sides of a
    rename), and the untracked nested repositories and tracked gitlinks among them."""
    raw = git(repo, "status", "--porcelain", "-z", "--untracked-files=all", "--", *specs, strip=False)
    links = {line.split("\t", 1)[1] for line in git(repo, "ls-files", "-s", "-z", "--", *specs).split("\0")
             if line.startswith("160000 ") and "\t" in line}
    fields, out, skipped, i = raw.split("\0"), [], [], 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, ps = entry[:2], [entry[3:]]
        if xy[0] in "RC" and i < len(fields):
            ps.append(fields[i])
            i += 1
        for p in ps:
            p = p.rstrip("/")
            if p in links or (xy == "??" and os.path.exists(os.path.join(repo, p, ".git"))):
                if p + "/" not in skipped:
                    skipped.append(p + "/")
            elif p not in out:
                out.append(p)
    return out, skipped


def checkpoint_tree(sub, repo, name, message, remote, pathspec, paths=None):
    """A superproject target's checkpoint while another live run works in the checkout (the
    board, #96; ``checkpoint_repo`` uses it only then): its changes are committed onto
    ``name`` with git plumbing -- a temporary index (``GIT_INDEX_FILE``) read from the
    branch's tip, or from HEAD when the branch is new, the paths added from the working
    tree, ``write-tree``, ``commit-tree`` with that tip as parent, ``update-ref`` (compare and
    swap) -- and that ref is pushed. The checkout is never switched: its HEAD, its index
    and its working tree stay as they were (when HEAD is that very branch, the committed
    paths' index entries follow it), so another run working in the same checkout is not
    moved. Committed files stay dirty against a HEAD on another branch until that branch is
    merged; they are recorded in ``.academy/shipped/<target>.json`` with their content hash,
    and a later run without ``paths`` passes over a file committed and unchanged since.

    ``paths`` (``--manifest``; repo-relative, under ``pathspec``): only these. Without:
    everything dirty under ``pathspec``. Untracked nested repositories and gitlinks are
    never committed. The branch of the checkout does not matter: main/master, a branch off
    the template, a detached HEAD are all fine, as nothing is committed there; a merge or
    rebase under way is refused."""
    res = {"sub": sub, "branch": name, "sha": "", "files": 0, "status": "unchanged", "detail": "",
           "names": [], "skipped": [], "merged": [], "forks": []}
    pre = pathspec.rstrip("/")
    try:
        ac = _lib()
    except Exception:  # noqa: BLE001
        ac = None

    def refused(why):
        res.update(status="skipped", sha=git(repo, "rev-parse", "--short", tip or "HEAD", check=False),
                   detail="refused: " + why)
        return res

    tip = git(repo, "rev-parse", "-q", "--verify", "refs/heads/" + name, check=False)
    head = git(repo, "rev-parse", "-q", "--verify", "HEAD^{commit}", check=False)
    base = tip or head
    if paths is not None:
        cand, res["skipped"] = _status_paths(repo, path_specs(paths)) if paths else ([], [])
    else:
        cand, res["skipped"] = _status_paths(repo, [scope_spec(pre)])
        done = ac.shipped_paths(ROOT, sub) if ac else {}
        if done:
            cand = [p for p in cand if done.get(p[len(pre) + 1:]) is None
                    or done[p[len(pre) + 1:]] != ac.manifest_hash(os.path.join(repo, *p.split("/")))]
    if cand:
        op = operation_in_progress(repo)
        if op:
            return refused("a %s is in progress" % op)
        if not base:
            return refused("the checkout has no commit to branch %s from" % name)
        mode, findings, cause = run_gate_detail(repo)
        if mode == "unavailable":
            gate_unavailable_note(cause)
        if findings and mode in ("normal", "strict"):
            return refused("commit gate (%s) found new problems: %s (changes uncommitted)"
                           % (mode, "; ".join(findings.values())))
        gd = git(repo, "rev-parse", "--absolute-git-dir")
        idx = os.path.join(gd, "ship-index-%d-%s" % (os.getpid(), os.urandom(3).hex()))
        env = dict(git_env(), GIT_INDEX_FILE=idx)

        def gi(*args):
            p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=env,
                               stdin=subprocess.DEVNULL)
            if p.returncode:
                raise Refuse("git %s failed in %s: %s" % (" ".join(args), repo, (p.stderr or p.stdout).strip()))
            return p.stdout
        try:
            gi("read-tree", base)
            present = [p for p in cand if os.path.lexists(os.path.join(repo, *p.split("/")))]
            gone = [p for p in cand if p not in present]
            if present:
                gi("add", "-A", "--", *path_specs(present))
            if gone:
                gi("rm", "-q", "-r", "--cached", "--ignore-unmatch", "--", *path_specs(gone))
            staged = [p for p in gi("diff", "--cached", "--name-only", "-z", base, "--",
                                    *path_specs(cand)).split("\0") if p]
            if staged:
                tree = gi("write-tree").strip()
                new = git(repo, "commit-tree", tree, "-p", base, "-m", message)
                git(repo, "update-ref", "-m", "ship: checkpoint " + name.split("/")[1],
                    "refs/heads/" + name, new, tip or "")
        except Refuse as e:
            return refused("%s (nothing committed)" % e)
        finally:
            if os.path.exists(idx):
                try:
                    os.remove(idx)
                except OSError:
                    pass
        if staged:
            tip = new
            res["files"], res["names"] = len(staged), staged
            on = git(repo, "symbolic-ref", "-q", "HEAD", check=False)
            if on == "refs/heads/" + name:
                # the checkout is on that branch: its index follows the new commit there
                git(repo, "reset", "-q", new, "--", *path_specs(staged), check=False)
            if ac:
                try:
                    dirty, _ = _status_paths(repo, [scope_spec(pre)])
                    rel = [p[len(pre) + 1:] for p in staged if p.startswith(pre + "/")]
                    ac.record_shipped(ROOT, sub, pre, [] if on == "refs/heads/" + name else rel,
                                      [p[len(pre) + 1:] for p in dirty])
                except Exception as exc:  # noqa: BLE001 -- the ledger only spares a later re-commit
                    print("ship: warning: shipped ledger not written: %s" % exc, file=sys.stderr)
    if not tip:
        res["sha"] = git(repo, "rev-parse", "--short", "HEAD", check=False)
        return res
    return push_tip(repo, name, tip, remote, res)


#: tests point this at a temp directory; None means ``~/.claude/projects``
USAGE_PROJECTS = None


def usage_summaries(only):
    """Before the board commit: append content-free usage summaries of this machine's recent
    sessions to ``<board>/.usage/<instance>.<host>.jsonl`` (``usage_ledger``), which the board's
    ordinary staging then picks up like ``.errors/``. Skipped when workspace.json says
    ``"shipCheckpoint": false`` or ``"usageCheckpoint": false``, or when the board target is
    not part of this run. Only ever a warning on stderr, never a failed checkpoint."""
    ws = workspace_json()
    if ws.get("shipCheckpoint") is False or ws.get("usageCheckpoint") is False:
        return
    try:
        if only is not None and BOARD not in only:
            return
        rel = root_dirs().get(BOARD) or (BOARD if BOARD in submodule_names() else None)
        if not rel:
            return
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import usage_ledger
        _, warning = usage_ledger.checkpoint(ROOT, os.path.join(ROOT, rel), USAGE_PROJECTS,
                                                keep_days=ws.get("usageKeepDays"))
        if warning:
            print("ship: warning: %s" % warning, file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 -- the usage summary must never fail a checkpoint
        print("ship: warning: usage summary skipped: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)


def parse_touched(items):
    """``{sub: [repo-relative paths]}`` from ``--touched SUB:PATH`` items; Refuse on a
    malformed one (absolute, '..', empty, or a sub that is no submodule)."""
    out = {}
    subs = submodule_names()
    for item in items or []:
        sub, sep, path = str(item).partition(":")
        path = path.replace("\\", "/").strip()
        parts = path.split("/")
        if (not sep or not sub or not path or path.startswith("/") or os.path.isabs(path)
                or ".." in parts or re.match(r"^[A-Za-z]:", path)):
            raise Refuse("--touched %r: expected SUB:PATH, PATH relative to the submodule"
                         % item)
        if sub not in subs:
            raise Refuse("--touched %r: %s is not a submodule in .gitmodules (known: %s)"
                         % (item, sub, " ".join(subs)))
        lst = out.setdefault(sub, [])
        if path not in lst:
            lst.append(path)
    return out


def read_manifest(path):
    """``{target: [paths relative to the target]}`` from a ``--manifest`` file (``{"repos":
    {...}}``, as the inbox writes it from its snapshot diff); Refuse on an unreadable file, a
    target that is neither a submodule nor a superproject target, or a malformed path."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise Refuse("--manifest %s: unreadable (%s)" % (path, e))
    repos = doc.get("repos") if isinstance(doc, dict) else None
    if not isinstance(repos, dict):
        raise Refuse("--manifest %s: no 'repos' object" % path)
    known = targets()
    out = {}
    for target, paths in repos.items():
        if target == WORKSPACE:
            raise Refuse("--manifest %s: the workspace target is never part of a checkpoint "
                         "(a ticket's work is not there)" % path)
        if target not in known:
            raise Refuse("--manifest %s: %r is not a target (known: %s)" % (path, target, " ".join(known)))
        if not isinstance(paths, list):
            raise Refuse("--manifest %s: %s: a list of paths expected" % (path, target))
        for p in paths:
            p = str(p).replace("\\", "/").strip()
            if (not p or p.startswith("/") or os.path.isabs(p) or ".." in p.split("/")
                    or re.match(r"^[A-Za-z]:", p)):
                raise Refuse("--manifest %s: %s: %r is not a path relative to it" % (path, target, p))
            lst = out.setdefault(target, [])
            if p not in lst:
                lst.append(p)
    return {t: ps for t, ps in out.items() if ps}


def run_checkpoint(ticket, role, title, remote, only=None, touched=None, manifest=None, wip=None,
                   run=None):
    """Commit and push, on ``<date>/<ticket-id>/<role>``, every checked-out submodule that
    has uncommitted changes (tracked or untracked, .gitignore honoured) or commits on that
    branch the remote does not have. One dict per submodule: sub, branch, sha, files,
    status ("pushed" / "unchanged" / "push-failed" / "skipped"; a refused repo is
    "skipped" with a detail starting "refused: "), detail. Never touches main, never
    forces; merges only the other recent ticket branches into the ticket's branch
    (``merge_forks``: merged, forks; #130); a refused or failed repo (including a Refuse raised inside
    ``checkpoint_repo``) does not stop the others. Also: names (the committed files) and
    skipped (untracked nested repos/worktrees and tracked submodule pointers left out,
    '/'-terminated).

    ``only`` (the automatic run from the inbox hook): just these targets (each must be a
    .gitmodules path or a superproject target such as ``board``, else Refuse before
    anything is touched); the others are not looked at, and a dirty repo of the set that
    is on main/master is refused instead of moved. A superproject target is committed in
    the workspace's own repository, limited to its directory (``checkpoint_repo``).

    ``touched`` (``{sub: [paths]}``, with ``only``): files the ticket's role wrote in
    another role's home (the inbox reads them from the touch ledger). Each such submodule
    not already in ``only`` is checkpointed for those paths only (``checkpoint_repo``'s
    ``paths``), on the same branch name, after the ``only`` targets.

    ``run`` (``--run``; with ``--manifest``, default the manifest's ``run``): the inbox run
    the ticket was worked in. A submodule leased by another live run is never switched
    (#96); without ``run`` every live lease is another run's."""
    t = (ticket or "").strip()
    if not TICKET.match(t):
        raise Refuse("ticket id %r is not a ticket id like T-0059 (letters, digits, '-')" % ticket)
    if role is not None:
        branch_name(t, role)  # a bad --role is refused before anything is touched
    remote = remote or ship_remote()
    if not REMOTE.match(remote):
        raise Refuse("remote %r is not a plain remote name" % remote)
    if manifest is not None and (only is not None or touched):
        raise Refuse("--manifest names every repo and path itself: not with --only or --touched")
    if wip is not None:
        message = "WIP: %s unfinished (%s)" % (t, (str(wip).strip() or "unfinished").replace("\n", " "))
    else:
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
    if manifest is not None:
        return manifest_checkpoint(t, role, message, remote, read_manifest(manifest), subs, dirs,
                                   run=run or manifest_run(manifest))
    extra = parse_touched(touched) if not isinstance(touched, dict) else dict(touched or {})
    if extra and only is None:
        raise Refuse("--touched needs --only (an unscoped run commits every dirty repo anyway)")
    if only is not None:
        unknown = [s for s in only if s not in subs]
        if unknown or not only:
            raise Refuse("--only %s: not a submodule in .gitmodules nor a superproject "
                         "directory (known: %s)" % (" ".join(unknown) or "(nothing)", " ".join(subs)))
        subs = [s for s in subs if s in only]
    extra = {s: p for s, p in extra.items() if s not in subs and p}
    if BOARD in subs:
        usage_summaries(only)  # before the board is staged and committed
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
                                           pathspec=None if sub in submodule_names() else dirs.get(sub),
                                           run=run))
        except Refuse as e:  # one repo's failure is its own result; the others go on
            results.append({"sub": sub, "branch": name, "sha": git(repo, "rev-parse", "--short", "HEAD", check=False),
                            "files": 0, "status": "skipped", "detail": "refused: %s" % e,
                            "names": [], "skipped": []})
    for sub, paths in extra.items():
        try:
            repo = repo_of(sub)
        except Refuse:
            results.append({"sub": sub, "branch": "", "sha": "", "files": 0, "status": "skipped",
                            "detail": "not checked out"})
            continue
        name = branch_name(t, role or default_role(repo))
        try:
            results.append(checkpoint_repo(sub, repo, name, message, remote, scoped=True,
                                           paths=paths, run=run))
        except Refuse as e:
            results.append({"sub": sub, "branch": name, "sha": git(repo, "rev-parse", "--short", "HEAD", check=False),
                            "files": 0, "status": "skipped", "detail": "refused: %s" % e,
                            "names": [], "skipped": []})
    return results


def manifest_run(path):
    """The ``run`` a ``--manifest`` file names (the inbox run of its ticket), else None."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return None
    r = doc.get("run") if isinstance(doc, dict) else None
    return r if isinstance(r, str) and r else None


def manifest_checkpoint(t, role, message, remote, repos, subs, dirs, run=None):
    """``run_checkpoint`` with ``--manifest``: each target that has paths, in ``targets()``
    order, is checkpointed for exactly those paths (``checkpoint_repo``'s ``paths``: always
    scoped, a dirty repo on main/master refused, nothing moved while other work there is
    uncommitted); every other repo is not looked at. A board path is relative to the board's
    directory; the usage summary is added to it when the board is shipped."""
    results = []
    for sub in [s for s in subs if s in repos]:
        try:
            repo = repo_of(sub)
        except Refuse:
            results.append({"sub": sub, "branch": "", "sha": "", "files": 0, "status": "skipped",
                            "detail": "not checked out", "names": [], "skipped": []})
            continue
        name = branch_name(t, role or default_role(repo))
        prefix = None if sub in submodule_names() else dirs.get(sub)
        paths = list(repos[sub])
        if prefix:
            pre = prefix.rstrip("/")
            paths = ["%s/%s" % (pre, p) for p in paths]
            if sub == BOARD:
                usage_summaries([BOARD])        # before the board is staged, as without a manifest
                raw = git(repo, "status", "--porcelain", "-z", "--untracked-files=all", "--",
                          scope_spec(pre + "/.usage"), strip=False)
                paths += [e[3:] for e in raw.split("\0") if len(e) > 3 and e[3:] not in paths]
        try:
            results.append(checkpoint_repo(sub, repo, name, message, remote, scoped=True,
                                           pathspec=prefix, paths=paths, run=run))
        except Refuse as e:
            results.append({"sub": sub, "branch": name, "sha": git(repo, "rev-parse", "--short", "HEAD", check=False),
                            "files": 0, "status": "skipped", "detail": "refused: %s" % e,
                            "names": [], "skipped": []})
    return results


def cmd_checkpoint(a):
    results = run_checkpoint(a.ticket, a.role, a.title, a.remote, a.only, a.touched,
                             manifest=a.manifest, wip=a.wip, run=a.run)
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
        for b in r.get("merged") or []:
            print("    merged %s (stacked, not forked; #130)" % b)
        for f in r.get("forks") or []:
            print("    FORK: %s holds commits %s lacks (%s); merge it in by hand"
                  % (f["branch"], r["branch"], f["why"]), file=sys.stderr)
    if bad:
        raise Refuse("checkpoint incomplete (commits made are kept locally); see the lines above")


def parser():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--workspace", metavar="DIR",
                   help="the workspace root (or its workspace.json); default: found from the "
                        "cwd, $ACADEMY_WORKSPACE or this academy checkout (module docstring)")
    sp = p.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("status", help="each target's branch, dirty and unpushed counts; then the "
                                     "linked worktrees holding work not on a remote")
    c.add_argument("--all", action="store_true",
                   help="list every linked worktree, the clean pushed ones marked removable")
    c.set_defaults(fn=cmd_status)
    s = sp.add_parser("start")
    s.add_argument("sub"); s.add_argument("topic")
    s.add_argument("--role"); s.add_argument("--worktree", action="store_true")
    s.add_argument("--on", metavar="BRANCH",
                   help="the base of the new branch (default: where the checkout is); the "
                        "new branch is stacked on it")
    s.set_defaults(fn=cmd_start)
    for name, fn in (("commit", cmd_commit), ("ship", cmd_ship)):
        c = sp.add_parser(name)
        c.add_argument("sub"); c.add_argument("-m", required=True)
        c.add_argument("--paths", nargs="+"); c.add_argument("--all", action="store_true")
        c.add_argument("--no-gate", action="store_true",
                       help="skip the Author commit gate%s (warns)"
                            % (" and the push gate" if name == "ship" else ""))
        c.set_defaults(fn=fn)
    c = sp.add_parser("accept-baseline"); c.add_argument("sub"); c.set_defaults(fn=cmd_accept_baseline)
    c = sp.add_parser("push"); c.add_argument("sub")
    c.add_argument("--no-gate", action="store_true", help="skip the push gate (warns)")
    c.set_defaults(fn=cmd_push)
    c = sp.add_parser("stack", help="the current branch's stack and the pull requests to open")
    c.add_argument("sub"); c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_stack)
    c = sp.add_parser("merge", help="merge a reviewed branch into local main (no push)")
    c.add_argument("sub"); c.add_argument("branch")
    c.add_argument("--sha", required=True, help="the reviewed tip of origin/<branch> (>= 7 hex chars)")
    c.add_argument("-m", help="merge commit message (default: Merge <branch> into main)")
    c.add_argument("--bump", action="store_true", help="then commit the new pointer in the superproject")
    c.set_defaults(fn=cmd_merge)
    c = sp.add_parser("sync", help="merge origin/main into the current work branch; ledgers and "
                      "counters resolved, any other conflict left for --continue (#119)")
    c.add_argument("sub")
    c.add_argument("--from", dest="source", default=None, help="the origin branch to merge (default: the branch it was started on, else main)")
    c.add_argument("--continue", dest="cont", action="store_true",
                   help="record the resolved merge (after 'git add' of each file)")
    c.set_defaults(fn=cmd_sync)
    c = sp.add_parser("bump", help="commit superproject pointers to reviewed main tips (the human's)")
    c.add_argument("subs", nargs="+")
    c.add_argument("--sha", action="append", help="one per submodule, in order")
    c.set_defaults(fn=cmd_bump)
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
    c.add_argument("--touched", nargs="+", metavar="SUB:PATH",
                   help="with --only: files the ticket's role wrote in another role's home "
                        "(the inbox reads them from the touch ledger); each such submodule is "
                        "checkpointed for these paths only, and refused, not moved, while "
                        "anything else in it is uncommitted")
    c.add_argument("--manifest", metavar="FILE",
                   help="the ticket's manifest (JSON {\"repos\": {TARGET: [paths]}}, the inbox's "
                        "snapshot diff): exactly these paths are committed, in each repo that "
                        "has any; not with --only / --touched")
    c.add_argument("--wip", metavar="OUTCOME",
                   help="the ticket is unfinished: commit as 'WIP: <ticket> unfinished (OUTCOME)'")
    c.add_argument("--run", metavar="RUN",
                   help="the inbox run the ticket was worked in (default: the manifest's): a "
                        "submodule leased by another live run is never switched (#96)")
    c.set_defaults(fn=cmd_checkpoint)
    for x in sp.choices.values():
        if x.prog.split()[-1] not in ("status", "checkpoint", "bump"):
            x.add_argument("--repo", help="the checkout to use instead of <workspace>/<sub>: that "
                                          "checkout or one of its worktrees (same git-common-dir)")
    return p


def main(argv):
    global ROOT
    a = parser().parse_args(argv)
    try:
        if a.workspace or ROOT is None:
            ROOT = find_workspace(a.workspace)
        rc = a.fn(a)
    except Refuse as e:
        print("ship: refused: %s" % e, file=sys.stderr)
        return 1
    # a command may say it stopped (sync on a conflict returns 1); anything else is success
    return rc if isinstance(rc, int) and not isinstance(rc, bool) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
