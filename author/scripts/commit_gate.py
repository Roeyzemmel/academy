"""PreToolUse (Bash|PowerShell): run the paper checker before a commit to an Author
home, and block on findings outside the recorded baseline.

Scope -- the repo actually being committed, not the session's cwd. The parser is
``academy_common.commit_targets`` (shared with the Scientist gate). The command is
split into segments (``;``, newlines, ``&&``, ``||``, ``|``) with quotes respected,
and walked in order while tracking the directory:

- ``cd``/``chdir``/``pushd``/``popd`` (bash) and ``Set-Location``/``sl``/
  ``Push-Location``/``Pop-Location`` (PowerShell) move the tracked directory;
- ``git -C <dir>`` (repeatable, each relative to the last) and ``--work-tree=<dir>``
  name the repo of that one git call;
- otherwise the tracked directory, which starts at the tool call's cwd.

Each ``git ... commit`` found this way is gated only when its directory lies in an
Author home (``.claude/academy.json`` with ``role: author``). Commits to any other
repo pass silently, whatever the session's cwd is (the misfire of the old gate, which
ran the Author's checker for a commit to the lab made from a paper session).
``bash -c "..."`` and ``powershell -Command "..."`` are parsed recursively; bash
heredocs and PowerShell here-strings are skipped as data.

Mode: ``gate_mode(config, branch)`` -- ``gate.commit`` with the per-branch override
(an exact branch name, e.g. ``academy-migration`` sets ``off``, or a glob such as
``????-??-??/*/*``). ``strict`` also fails on warnings; ``warn`` reports the new
findings on stderr (``commit gate (warn):``) and lets the commit through (exit 0).
``gate_check(home, cfg, branch)`` is the importable core (``scripts/ship.py`` in the
workspace calls it before committing): ``(mode, new_findings)``, no blocking.
Baseline: ``gate.baseline`` (default ``.claude/paper-gate-baseline.txt``), one
``file|label|rule`` key per line. Regenerate it, from inside the home, with

    py <plugin>/scripts/commit_gate.py --write-baseline [--root HOME]

Blocking is exit code 2 with the reason on stderr, which Claude Code feeds back.
"""

import os
import subprocess
import sys

import _author as au

ac = au.ac

# The command parser is shared with the Scientist commit gate and lives in
# academy_common (vendored as _academy.py); these names keep the old API.
ParseFailure = ac.ShellParseFailure
split_segments = ac.split_segments
resolve_dir = ac.resolve_dir
git_commit_dir = ac.git_commit_dir
commit_targets = ac.commit_targets


# ----------------------------------------------------------------------------
# The gate
# ----------------------------------------------------------------------------

def current_branch(repo):
    """The checked-out branch of ``repo`` (also on an unborn branch), or None."""
    for argv in (["symbolic-ref", "--quiet", "--short", "HEAD"],
                 ["rev-parse", "--abbrev-ref", "HEAD"]):
        try:
            p = subprocess.run(["git", "-C", repo] + argv, capture_output=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return None
        out = p.stdout.decode("utf-8", "replace").strip()
        if p.returncode == 0 and out and out != "HEAD":
            return out
    return None


def homes_to_gate(command, cwd):
    """[(home, config)] of the Author homes the command commits to, deduplicated."""
    try:
        dirs = commit_targets(command, cwd)
    except ParseFailure:
        dirs = [cwd] if ac.is_git_commit(command) else []
    seen, out = set(), []
    for d in dirs:
        home, cfg = au.author_home(d)
        if not home:
            continue
        key = os.path.normcase(os.path.abspath(home))
        if key in seen:
            continue
        seen.add(key)
        out.append((home, cfg, d))
    return out


def _gate_run(home, cfg, branch):
    """(mode, new findings, checker exit code, checker output) -- gate_check's core."""
    mode = ac.gate_mode(cfg, branch)
    if mode == "off":
        return "off", {}, None, ""
    code, output = au.run_checker(home, cfg, strict=(mode == "strict"))
    if code is None:
        return "unavailable", {}, None, output
    if code == 0:
        return mode, {}, code, output
    return mode, au.new_findings(home, cfg, output), code, output


def gate_check(home, cfg, branch):
    """``(mode, new_findings)`` for a commit to the Author home ``home`` on ``branch``.

    mode is ``gate_mode(cfg, branch)`` ('strict'|'normal'|'warn'|'off'), or
    'unavailable' when the checker could not run. new_findings maps the finding key
    ``file|label|rule`` to the checker's line for every finding outside the recorded
    baseline (all of them when no baseline is recorded); it is empty for 'off'
    (checker not run), 'unavailable', and a checker exit 0. The checker inspects the
    working tree (cwd=home), not the index. Deciding what to do is the caller's.
    """
    mode, new, _code, _output = _gate_run(home, cfg, branch)
    return mode, new


def check_home(home, cfg, repo):
    """None if the commit may go ahead, else the reason to block it.

    In mode 'warn' the findings are written to stderr (``commit gate (warn):``) and
    the commit goes ahead.
    """
    mode, new, code, output = _gate_run(home, cfg, current_branch(repo))
    if not new:
        return None
    if mode == "warn":
        sys.stderr.write("commit gate (warn): %s: %d finding(s) not in the recorded "
                         "baseline; not blocking on this branch.\n%s\n"
                         % (cfg.get("instance", home), len(new),
                            "\n".join(sorted(new.values()))))
        return None
    here = os.path.abspath(__file__)
    if not au.load_baseline(home, cfg):
        return ("Commit to %s blocked: check_paper.py%s exited %d and no baseline is "
                "recorded.\n\n%s\nFix these, or record the draft's known open state once "
                "with\n    py \"%s\" --write-baseline --root \"%s\"\nso the gate blocks "
                "regressions instead." % (cfg.get("instance", home),
                                          " --strict" if mode == "strict" else "", code,
                                          output, here, home))
    return ("Commit to %s blocked: %d finding(s) that are not in the recorded baseline "
            "(%s).\n\n%s\n\nThese appeared since the baseline was written. Fix them, or "
            "-- if they are a deliberate change to the draft's open state -- regenerate "
            "the baseline with\n    py \"%s\" --write-baseline --root \"%s\""
            % (cfg.get("instance", home), len(new),
               os.path.relpath(au.baseline_path(home, cfg), home).replace("\\", "/"),
               "\n".join(sorted(new.values())), here, home))


def write_baseline(root):
    home, cfg = au.author_home(root)
    if not home:
        sys.stderr.write("not an Author home: no .claude/academy.json with role author "
                         "at or above %s\n" % root)
        return 1
    strict = ac.gate_mode(cfg, current_branch(home)) == "strict"
    code, output = au.run_checker(home, cfg, strict=strict)
    if code is None:
        sys.stderr.write(output + "\n")
        return 1
    keys = sorted(au.findings(output))
    path = au.baseline_path(home, cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Findings accepted as the draft's known open state.\n")
        handle.write("# Key: file|label|rule. Regenerate with commit_gate.py "
                     "--write-baseline; shrinking this file is progress.\n")
        for key in keys:
            handle.write(key + "\n")
    sys.stdout.write("wrote %d baseline findings to %s\n" % (len(keys), path))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--write-baseline" in argv:
        root = os.getcwd()
        if "--root" in argv and argv.index("--root") + 1 < len(argv):
            root = argv[argv.index("--root") + 1]
        return write_baseline(os.path.abspath(root))

    event = ac.read_event()
    command = ac.shell_command(event)
    if not command or not ac.is_git_commit(command):
        return 0                       # cheap prefilter; errs towards "maybe a commit"
    blocks = []
    for home, cfg, repo in homes_to_gate(command, ac.event_cwd(event)):
        why = check_home(home, cfg, repo)
        if why:
            blocks.append(why)
    if not blocks:
        return 0
    sys.stderr.write("\n\n".join(blocks) + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
