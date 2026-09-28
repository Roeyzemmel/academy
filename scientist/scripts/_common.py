"""Shared helpers for the Scientist plugin's hooks and scripts.

Adapted from the old flatsurf plugin's ``_common.py``. The difference is scoping:
the old gates recognised FlatSurfLab by its files (``scripts/check_experiments.py``
plus ``fslab/``); these recognise a **Scientist home** by its
``.claude/academy.json`` (``role: scientist``), cross-checked against
``workspace.json`` (the config's ``instance`` must be a scientist instance there).
Outside such a home every hook is a silent no-op. Inside one, the old flatsurf
plugin's hooks would still fire too until its ``_common.py`` gets the early return on
``academy.json`` that plan section 9 phase 3 asks for -- that edit is to a read-only
repo and is recorded as a hand-off in ``docs/migration-log.md`` (Group B); it must
land before any lab home gets ``.claude/academy.json``.

The workspace check compares the instance *name*, not the home path, so a
worktree of the lab (``../FlatSurfLab-academy`` on the ``academy-migration``
branch, plan section 9b) is recognised as the lab too.

Exit-code contract (Claude Code hooks):
    0  silent, nothing to say
    2  stderr goes back to the model: blocking for PreToolUse, advisory context
       for PostToolUse
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _academy as ac  # noqa: E402

#: files under the experiments directory that are not experiments
EXEMPT = {"_template.py", "smoke_sage.py", "__init__.py"}
#: the lab's own checker, relative to the home (a switched-over lab has a shim there that
#: forwards to the plugin's parameterised scripts/check_experiments.py; a home can name
#: the plugin's copy directly with scientist.checker, as FlatSurfLab's academy.json does).
DEFAULT_CHECKER = "scripts/check_experiments.py"


def plugin_root():
    return os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))


# ----------------------------------------------------------------------------
# Scoping
# ----------------------------------------------------------------------------

def lab_config(path, workspace=None):
    """The validated academy config of the Scientist home containing ``path``, or None.

    None when ``path`` is in no academy home, the home's role is not ``scientist``,
    its config does not load, or ``workspace.json`` (when readable) does not list the
    config's instance as a scientist instance.
    """
    if not path:
        return None
    home = ac.find_home(path)
    if not home:
        return None
    try:
        cfg = ac.load_config(home)
    except ac.AcademyError:
        return None
    if cfg.get("role") != "scientist":
        return None
    try:
        ws = workspace if workspace is not None else ac.load_workspace(cfg.get("workspace"))
    except ac.AcademyError:
        ws = None
    if ws is not None:
        inst = ws.get("instances", {}).get(cfg.get("instance"))
        if not inst or inst.get("role") != "scientist":
            return None
    return cfg


#: what the scripts assume of a lab home that has no academy.json yet (before its
#: switch-over): the FlatSurfLab layout of docs/config.md, and no env profiles
PRE_SWITCH_DEFAULTS = {
    "paths": {"experiments": "experiments/*.py", "results": "results", "queue": "queue"},
    "scientist": {"envs": {}, "policy": {},
                  "experimentTypes": ["search", "measure", "verify", "probe"]},
    "budget": dict(ac.CONFIG_DEFAULTS["budget"]),
}


def resolve_lab(home=None, cwd=None, workspace_path=None):
    """Find the Scientist instance a script acts for.

    Order: ``home`` if given; else the Scientist home containing ``cwd``; else the
    single scientist instance of workspace.json (the first by name if there are
    several, reported in ``note``). Returns a dict with ``instance``, ``home``,
    ``cfg`` (the loaded config, or ``PRE_SWITCH_DEFAULTS`` plus ``_home`` when the
    home has no academy.json yet), ``switched`` (bool), ``ws`` (or None) and ``note``.
    Raises ``ac.AcademyError`` when no lab can be found.
    """
    try:
        ws = ac.load_workspace(workspace_path)
    except ac.AcademyError:
        ws = None
    note = ""
    if not home:
        found = ac.find_home(cwd or os.getcwd())
        if found:
            try:
                if ac.load_config(found).get("role") == "scientist":
                    home = found
            except ac.AcademyError:
                pass
    if not home and ws:
        labs = sorted(n for n, i in ws["instances"].items() if i.get("role") == "scientist")
        if not labs:
            raise ac.AcademyError("workspace.json lists no scientist instance")
        if len(labs) > 1:
            note = "several scientist instances (%s); took %s" % (", ".join(labs), labs[0])
        home = ws["instances"][labs[0]]["home"]
    if not home:
        raise ac.AcademyError("no Scientist home: pass --home, run from the lab, or "
                              "list the lab in workspace.json")
    home = os.path.abspath(home)
    if os.path.isfile(os.path.join(home, ac.CONFIG_REL)):
        cfg = ac.load_config(home)
        if cfg.get("role") != "scientist":
            raise ac.AcademyError("%s is a %s home, not a Scientist home"
                                  % (home, cfg.get("role")))
        switched = True
        instance = cfg["instance"]
    else:
        cfg = json_copy(PRE_SWITCH_DEFAULTS)
        cfg["_home"] = home.replace("\\", "/")
        switched = False
        instance = ac.instance_for_home(ws, home) if ws else None
        if not instance:
            raise ac.AcademyError("%s has no .claude/academy.json and is no instance of "
                                  "workspace.json" % home)
        cfg["instance"] = instance
        cfg["domains"] = list(ws["instances"][instance].get("domains") or [])
    return {"instance": instance, "home": home, "cfg": cfg, "switched": switched,
            "ws": ws, "note": note}


def json_copy(obj):
    import json
    return json.loads(json.dumps(obj))


def relative(root, path):
    try:
        return os.path.relpath(os.path.abspath(path), root).replace("\\", "/")
    except ValueError:
        return str(path)


def is_experiment(cfg, path):
    """True for a file in the home's ``paths.experiments`` that carries a header."""
    if not path or not cfg:
        return False
    if os.path.basename(path) in EXEMPT or not path.endswith(".py"):
        return False
    return ac.path_in_role(path, cfg, "experiments")


def experiments_dir(cfg):
    """The directory part of ``paths.experiments`` (``experiments/*.py`` -> ``experiments``)."""
    pats = (cfg.get("paths") or {}).get("experiments") or "experiments"
    pat = pats[0] if isinstance(pats, list) else pats
    parts = []
    for seg in pat.replace("\\", "/").split("/"):
        if any(c in seg for c in "*?"):
            break
        parts.append(seg)
    return "/".join(parts) or "experiments"


def results_dir(cfg):
    pats = (cfg.get("paths") or {}).get("results") or "results"
    return pats[0] if isinstance(pats, list) else pats


# ----------------------------------------------------------------------------
# The checker
# ----------------------------------------------------------------------------

def checker_path(cfg):
    """The experiment-header checker: ``scientist.checker`` if configured, else the
    home's ``scripts/check_experiments.py``. None if it does not exist."""
    home = cfg["_home"]
    cand = (cfg.get("scientist") or {}).get("checker") or DEFAULT_CHECKER
    cand = cand.replace("${CLAUDE_PLUGIN_ROOT}", plugin_root())
    full = cand if os.path.isabs(cand) else os.path.join(home, cand)
    return full if os.path.isfile(full) else None


def run_checker(cfg, args=(), strict=False):
    """Run the checker in the home. Returns (exit code, output), or (None, '') if it
    could not be run at all -- a gate never fails a task over its own tooling."""
    script = checker_path(cfg)
    if not script:
        return None, ""
    cmd = [sys.executable, script, "--quiet"] + (["--strict"] if strict else []) + list(args)
    try:
        proc = subprocess.run(cmd, cwd=cfg["_home"], capture_output=True, text=True,
                              timeout=60, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None, ""
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


# ----------------------------------------------------------------------------
# git
# ----------------------------------------------------------------------------

def git(root, *args):
    try:
        proc = subprocess.run(["git"] + list(args), cwd=root, capture_output=True,
                              text=True, timeout=30, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_toplevel(path):
    out = git(path, "rev-parse", "--show-toplevel") if os.path.isdir(path) else None
    return os.path.abspath(out.strip()) if out and out.strip() else None


def git_branch(root):
    """The checked-out branch (also on an unborn branch), or None when detached."""
    out = git(root, "symbolic-ref", "--short", "-q", "HEAD")
    return out.strip() if out and out.strip() else None


def commit_targets(command, cwd):
    """The directories in which ``command`` runs ``git commit``, in order.

    The shared parser of ``academy_common`` (also the Author gate's): ``cd`` /
    ``Set-Location`` / ``pushd`` segments, ``git -C`` / ``--work-tree`` /
    ``--git-dir``, Git Bash drive paths (``/c/Work/...``), nested ``bash -c`` /
    ``powershell -Command``, heredocs and here-strings as data. An untokenisable
    command falls back to the cwd, so the gate errs towards checking.
    """
    return ac.commit_targets_or_cwd(command, os.path.abspath(cwd or os.getcwd()))


def speak(message):
    """Hand ``message`` back to the model (exit code 2)."""
    sys.stderr.write(message.rstrip() + "\n")
    return 2
