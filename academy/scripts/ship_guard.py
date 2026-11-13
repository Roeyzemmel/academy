"""PreToolUse hook on Bash / PowerShell: in a workspace's repos, commits, pushes and new
branches go through ship.py.

A workspace's branch and ship protocol (docs/branching.md) is carried by one tool,
``py scripts/ship.py``: it names the branch ``<date>/<topic>/<role>``, never touches
``main`` or a submodule pointer, runs the commit gate and the push gate, and knows the
base of a stacked branch. A session that reaches for ``git commit`` / ``git push`` /
``git switch -c`` instead gets none of that (2026-11-13: a stack of pull requests was
cut by hand on off-template branches, past both gates). This hook makes the tool the
default: a shell command that would

* commit (``git commit``),
* push (``git push``), or
* create a branch (``git switch -c|-C``, ``git checkout -b|-B``, ``git branch <new>``)

in the workspace's superproject or in one of its submodule checkouts (or a worktree of
one) is denied, and the reason gives the ship.py command that does it. Everything else
passes: reading (status, log, diff, fetch), staging, stashing, switching to an existing
branch, any git command in a repository that is not part of the workspace (a scratch
clone, a test fixture), and any command whose directory the hook cannot work out.

ship.py itself runs git as a subprocess, not through the shell tool, so it is not
affected. The human's own ``! git ...`` in the session is not a tool call either. Off for
a workspace with ``"shipGuard": false`` in workspace.json; a session outside every
workspace is never touched.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402

BRANCH_FLAGS = ("-c", "-C", "-b", "-B", "--create", "--force-create", "--orphan")
#: ``git branch`` switches that do not create a branch
BRANCH_READS = ("-d", "-D", "--delete", "-l", "--list", "-a", "--all", "-r", "--remotes",
                "-v", "-vv", "--verbose", "--show-current", "-m", "-M", "--move",
                "--merged", "--no-merged", "--contains", "--no-contains", "--points-at",
                "-u", "--set-upstream-to", "--unset-upstream", "--edit-description",
                "--format", "--sort", "--column", "--no-column", "--color", "--no-color")


def git_calls(command, cwd, _depth=0):
    """``[(directory, verb, args)]`` for every git call of ``command``, each with the
    directory it runs in (the cwd moved by ``cd`` / ``pushd`` / ``git -C``); the walk of
    ``ac.commit_targets``, for any verb. Raises ``ac.ShellParseFailure``."""
    out, here, stack = [], cwd, []
    for seg in ac.split_segments(command):
        toks = ac._strip_prefix(seg)
        if not toks:
            continue
        head = toks[0].lower()
        if head in ac.SHELL_CD:
            tgt = ac._cd_target(toks[1:])
            if tgt is None and head == "cd" and len(toks) == 1:
                here = os.path.expanduser("~")
            elif tgt == "-" or (tgt and any(c in tgt for c in "$`*?")):
                return out                   # from here on the directory is unknown
            elif tgt:
                here = ac.resolve_dir(here, tgt)
            continue
        if head in ac.SHELL_PUSHD:
            tgt = ac._cd_target(toks[1:])
            if tgt:
                stack.append(here)
                here = ac.resolve_dir(here, tgt)
            continue
        if head in ac.SHELL_POPD:
            if stack:
                here = stack.pop()
            continue
        if _depth < 3 and head in ac.SHELLS_C and len(toks) >= 3 and toks[1] == ac.SHELLS_C[head]:
            out.extend(git_calls(toks[2], here, _depth + 1))
            continue
        if not ac._is_git(toks[0]):
            continue
        repo, k = here, 1
        while k < len(toks):
            t = toks[k]
            if t == "-C" and k + 1 < len(toks):
                repo = ac.resolve_dir(repo, toks[k + 1])
                k += 2
            elif t.lower() in ac.GIT_OPTS_WITH_ARG:
                k += 2
            elif t.startswith("-"):
                k += 1
            else:
                break
        if k < len(toks):
            out.append((repo, toks[k].lower(), toks[k + 1:]))
    return out


def action_of(verb, args):
    """``commit`` / ``push`` / ``branch`` (a new one) for a git call the tool owns, else None."""
    if verb in ("commit", "push"):
        return verb
    if verb in ("switch", "checkout") and any(a in BRANCH_FLAGS for a in args):
        return "branch"
    if verb == "branch":
        if any(a in BRANCH_READS or a.split("=", 1)[0] in BRANCH_READS for a in args):
            return None
        return "branch" if [a for a in args if not a.startswith("-")] else None
    return None


def _git(path, *args):
    try:
        p = subprocess.run(["git", "-C", path] + list(args), capture_output=True, text=True,
                           timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def _real(p):
    return os.path.normcase(os.path.realpath(p))


def workspace_targets(ws_root):
    """``{git common dir: target name}`` for the workspace's superproject (``board`` is
    the only thing committed there) and each checked-out submodule."""
    out = {}
    names = []
    try:
        with open(os.path.join(ws_root, ".gitmodules"), encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln.startswith("path") and "=" in ln:
                    names.append(ln.split("=", 1)[1].strip())
    except OSError:
        pass
    for name in names:
        d = os.path.join(ws_root, *name.split("/"))
        common = _git(d, "rev-parse", "--path-format=absolute", "--git-common-dir") \
            if os.path.isdir(d) else ""
        if common:
            out[_real(common)] = name
    common = _git(ws_root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common:
        out.setdefault(_real(common), "board")
    return out


def target_of(directory, targets):
    """The ship target whose repository ``directory`` is in (a checkout or one of its
    worktrees), or None."""
    if not os.path.isdir(directory):
        return None
    common = _git(directory, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return targets.get(_real(common)) if common else None


def advice(action, target):
    if action == "commit":
        if target == "board":
            return ("py scripts/ship.py commit board -m \"...\" --paths P...  for board/ "
                    "files, or `commit workspace ...` for the workspace's own files (its "
                    "CLAUDE.md, scripts/, docs/); a submodule pointer is never committed")
        return "py scripts/ship.py commit %s -m \"...\" (--paths P... | --all)" % target
    if action == "push":
        return ("py scripts/ship.py push %s  (it runs the push gate; 'ship' is commit + push, "
                "'stack %s' names the pull requests of a stack)" % (target, target))
    return ("py scripts/ship.py start %s <topic> [--on BASE]  (the branch is "
            "<date>/<topic>/<role>; started on another branch it is stacked on it)" % target)


def decide(event, workspace=None):
    """``None`` or ``("deny", reason)`` for one PreToolUse event."""
    if ac.tool_name(event) not in ("Bash", "PowerShell"):
        return None
    cmd = ac.shell_command(event)
    if not cmd or "git" not in cmd:
        return None
    try:
        calls = [(d, action_of(v, a)) for d, v, a in git_calls(cmd, ac.event_cwd(event))]
    except ac.ShellParseFailure:
        return None
    calls = [(d, a) for d, a in calls if a]
    if not calls:
        return None
    try:
        ws = workspace if workspace is not None else ac.load_workspace()
    except ac.AcademyError:
        return None
    if not ws or ws.get("shipGuard") is False or not ws.get("_path"):
        return None
    root = os.path.dirname(ws["_path"])
    targets = workspace_targets(root)
    for directory, action in calls:
        target = target_of(directory, targets)
        if not target:
            continue
        return ("deny", "academy: in this workspace a %s goes through the ship tool, not raw "
                        "git (nothing was run). From the workspace root %s:\n  %s\n"
                        "`py scripts/ship.py --help` lists the steps; docs/branching.md is "
                        "the protocol."
                % ({"commit": "commit", "push": "push", "branch": "new branch"}[action],
                   root.replace("\\", "/"), advice(action, target)))
    return None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        verdict = decide(ac.read_event())
    except Exception:           # the guard never blocks a call by failing itself
        return 0
    if verdict:
        ac.emit_permission(verdict[0], verdict[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
