"""SubagentStop: a writing agent does not finish on a broken build.

Identity is ``agent_identity`` with the namespace stripped, so ``author:math-writer``
counts as ``math-writer`` (the old gate compared the raw ``agent_type`` and missed
every namespaced agent, and math-editor was not in its list at all). The writers are
``author.writers`` in academy.json, default math-writer, math-editor, tex-engineer,
note-sweeper, figure-maker and librarian (a bib edit is owed a build too).

Scope: an Author home with a dirty marker (``<build.dir>/.dirty``, left by
tex_edit_check after an edit to the home's tex or bib). The home is the one holding
the session's cwd; failing that, the Author homes of workspace.json are looked at, so
a librarian that edited a paper's bibliography from the Expert's home is still covered.
No dirty marker, no build: silent.

The build runs under ``author.build.lock`` (default ``.build/.lock``), so two gates
never build at once; LaTeX Workshop's build-on-save honours the lock only if its
recipe checks it (tex-engineer's setup job). If the lock stays taken, the gate says
so and does not build (it never fails the stop because of the lock).

It blocks the stop (exit 2, reason on stderr) on a build error, on a "??" in the PDF,
or on a checker finding outside the baseline -- never on the draft's known open
state, which would block every writing agent forever.
"""

import os
import re
import subprocess
import sys

import _author as au

ac = au.ac
BUILD_TIMEOUT = 280
LOCK_WAIT = float(os.environ.get("ACADEMY_BUILD_LOCK_WAIT") or 60.0)
ERROR_LINE = re.compile(r"^(?:!|[^ ]+\.tex:\d+:)")
UNRESOLVED = re.compile(r"\?\?\s+([1-9]\d*)")


def is_writer(event, config):
    _ns, bare = ac.agent_identity(event)
    if not bare:
        return False
    writers = au.author_settings(config).get("writers") or list(au.DEFAULT_WRITERS)
    return bare in [w.lower() for w in writers]


def candidate_homes(event):
    """[(home, config)]: the cwd's Author home, then the workspace's Author homes."""
    out, seen = [], set()

    def add(home, cfg):
        if home and os.path.normcase(os.path.abspath(home)) not in seen:
            seen.add(os.path.normcase(os.path.abspath(home)))
            out.append((home, cfg))

    add(*au.author_home(ac.event_cwd(event)))
    try:
        ws = ac.load_workspace()
    except ac.AcademyError:
        ws = {"instances": {}}
    for inst in (ws.get("instances") or {}).values():
        if inst.get("role") == "author" and inst.get("home"):
            add(*au.author_home(inst["home"]))
    return out


def build(home, config):
    cmd = au.author_settings(config)["build"].get("cmd") or ["latexmk", "-pdf", "main.tex"]
    try:
        proc = subprocess.run([str(c) for c in cmd], cwd=home, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=BUILD_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "%s timed out" % cmd[0]
    except OSError as exc:
        return None, "%s could not run: %s" % (cmd[0], exc)
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def gate_home(home, config):
    """None if the home is clean after building, else the reason to block."""
    lock = au.BuildLock(home, config)
    if not lock.acquire(wait=LOCK_WAIT):
        sys.stderr.write("build_gate: %s is held; not building %s now.\n"
                         % (lock.path, home))
        return None
    try:
        code, output = build(home, config)
        if code is None:                 # no latexmk here: not this gate's problem
            au.clear_dirty(home, config)
            return None
        problems = []
        if code != 0:
            errors = [ln for ln in output.splitlines() if ERROR_LINE.match(ln)]
            problems.append("the build exited %d.\n%s"
                            % (code, "\n".join(errors[:20]) or output[-1200:]))
        chk_code, chk_output = au.run_checker(home, config)
        if chk_code is not None:
            new = au.new_findings(home, config, chk_output)
            if new:
                problems.append("%d checker finding(s) outside the baseline:\n%s"
                                % (len(new), "\n".join(sorted(new.values()))))
            unresolved = UNRESOLVED.search(chk_output)
            if unresolved:
                problems.append("the PDF contains %s unresolved cross-reference(s) ('??')."
                                % unresolved.group(1))
        au.clear_dirty(home, config)
    finally:
        lock.release()
    if not problems:
        return None
    return ("You edited %s in this run and left it not clean.\n\n%s\n\nFix what your "
            "edits broke before finishing, then stop again. Findings already in the "
            "baseline are not yours and are not reported here."
            % (config.get("instance", home), "\n\n".join(problems)))


def main():
    event = ac.read_event()
    if event.get("stop_hook_active"):
        return 0
    if not ac.agent_identity(event)[1]:
        return 0
    blocks = []
    for home, cfg in candidate_homes(event):
        if not is_writer(event, cfg):
            continue
        if not (cfg.get("gate") or {}).get("build", True):
            continue
        if not au.is_dirty(home, cfg):
            continue
        why = gate_home(home, cfg)
        if why:
            blocks.append(why)
    if not blocks:
        return 0
    sys.stderr.write("\n\n".join(blocks) + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
