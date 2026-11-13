"""ci_local.py -- run a repo's GitHub workflow files here, as ship.py's push gate does.

    py ci_local.py list [--repo DIR]                       the local plan: what would run, what is skipped and why
    py ci_local.py run  [--repo DIR] [--workflow FILE] [--job ID]

The workflow files under ``.github/workflows/`` are kept as the one description of a
repo's checks. Nothing runs them on GitHub for these repos, so they are run on the
machine that pushes: ``ship.py push / ship / checkpoint`` call ``plan`` and ``run`` here
(the push gate), and this command runs them by hand.

What is taken from a workflow, and how it is read locally:

* only a workflow triggered by ``push`` (``on: push``, a list or a map holding it) is a
  check of a push; one triggered by issues, a schedule or by hand only is never run here
  (it may write to GitHub);
* every job's ``run:`` steps, in order, through ``bash -e -c`` from the repo's top level
  (or the step's ``working-directory``), with the job's and the step's ``env``;
* ``uses:`` steps are the runner's setup (checkout, setup-python) and are skipped. A
  checkout of the repo itself into ``path: P`` makes ``P`` a name for the repo's top
  level, so ``working-directory: P`` is the top level here; a checkout of another
  repository into ``path: Q`` is expected to be there already (a sibling or a submodule)
  and is not fetched;
* a setup step -- every line an install or a global configuration (``pip install``,
  ``python -m pip install``, ``sudo ...``, ``apt-get ...``, ``git config --global``) --
  is skipped: a push gate does not install software or rewrite the user's git identity.
  A later step of the job that then exits 127 (command not found) is reported as
  skipped, not failed: the workflow installs that tool, this machine has not;
* a step that needs GitHub's context (``${{ ... }}`` in its command or its ``env``) is
  skipped, with the reason;
* the shell is ``bash``; on Windows that is Git Bash (found beside ``git``), never the
  WSL launcher in System32, which would run the steps in another system
  (``CI_LOCAL_BASH`` names a shell explicitly);
* ``python`` in a command is the interpreter running this script (a shim directory is
  put first on PATH), so a workflow written for the runner's ``python`` works where only
  ``py`` or ``python3`` exists;
* ``CI=true`` and ``SHIP_GATE=1`` are set, as on a runner: a test that reads a real home
  of the workspace skips itself on ``CI``;
* a step with ``if:`` naming ``always()`` or ``!cancelled()`` runs even after a failure
  in its job, as on GitHub; any other step is skipped once its job has failed. Every
  job runs; the result is a failure when any step failed.
* the jobs run at the same time (up to the machine's processors; ``CI_LOCAL_JOBS=N``
  sets the number, ``1`` runs them one after another), as on GitHub, and the report keeps
  the workflow's order. Unlike GitHub's runners they share one checkout: jobs that write
  into the tree need ``CI_LOCAL_JOBS=1``, or belong in one job.

The YAML read is the subset workflow files use (maps, lists, plain and quoted scalars,
``|`` and ``>`` blocks, flow lists, comments); anything else in a file makes that file
unreadable, which is reported and fails the gate rather than passing silently.

Exit 0 when every step that ran passed (or nothing is to run), 1 on a failure, 2 on an
error. Standard library only.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

WORKFLOW_DIR = os.path.join(".github", "workflows")
TAIL = 25
RE_SETUP = re.compile(r"^\s*(?:pip3?\s+install|python3?\s+-m\s+pip\s+install|sudo\s|apt-get\s|"
                      r"git\s+config\s+--global)\b")
RE_KEY = re.compile(r"^((?:\"[^\"]*\"|'[^']*'|[^\s:#\[\]{}][^:#]*?))\s*:(?:\s+(.*)|\s*)$")


class WorkflowError(Exception):
    pass


# ----------------------------------------------------------------------------
# The YAML subset of a workflow file
# ----------------------------------------------------------------------------

def _strip_comment(s):
    out, quote = [], None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _scalar(text):
    t = text.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    if t.startswith("[") and t.endswith("]"):
        inner = t[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    low = t.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~", ""):
        return None
    return t


class _Lines(object):
    def __init__(self, text):
        self.rows = []                      # (indent, content, raw)
        for raw in text.replace("\r\n", "\n").replace("\t", "    ").split("\n"):
            body = _strip_comment(raw)
            self.rows.append((len(raw) - len(raw.lstrip(" ")), body.strip(), raw))
        self.i = 0

    def peek(self):
        while self.i < len(self.rows) and not self.rows[self.i][1]:
            self.i += 1
        return self.rows[self.i] if self.i < len(self.rows) else None


def _block_scalar(L, parent_indent, style):
    """The text of a ``|`` / ``>`` block whose lines are indented past ``parent_indent``."""
    rows, base = [], None
    while L.i < len(L.rows):
        indent, _body, raw = L.rows[L.i]
        if raw.strip() and indent <= parent_indent:
            break
        if raw.strip() and base is None:
            base = indent
        rows.append(raw[base:] if (base is not None and raw.strip()) else "")
        L.i += 1
    while rows and not rows[-1]:
        rows.pop()
    text = ("\n" if style.startswith("|") else " ").join(rows)
    return text + ("" if "-" in style else "\n")


def _value(L, rest, indent):
    """The value after ``key:`` or ``- ``: inline, a block scalar, or a nested block."""
    if rest is None or rest == "":
        nxt = L.peek()
        if nxt is None or nxt[0] <= indent and not (nxt[0] == indent and nxt[1].startswith("- ")):
            return None
        return _node(L, nxt[0])
    if rest[0] in "|>" and re.match(r"^[|>][+-]?\d?$", rest):
        return _block_scalar(L, indent, rest)
    return _scalar(rest)


def _node(L, indent):
    row = L.peek()
    if row is None:
        return None
    if row[1].startswith("- ") or row[1] == "-":
        out = []
        while True:
            row = L.peek()
            if row is None or row[0] != indent or not (row[1].startswith("- ") or row[1] == "-"):
                return out
            L.i += 1
            rest = row[1][1:].strip()
            m = RE_KEY.match(rest) if rest else None
            if m and not (rest[0] in "\"'" and rest.endswith(rest[0]) and ":" not in rest[1:-1]):
                # "- key: value": a map whose first key sits on the dash line
                inner = indent + (len(row[1]) - len(row[1][1:].lstrip(" ")))
                item = {_scalar(m.group(1)): _value(L, m.group(2), inner)}
                nxt = L.peek()
                if nxt is not None and nxt[0] == inner and not nxt[1].startswith("- "):
                    more = _node(L, inner)
                    if not isinstance(more, dict):
                        raise WorkflowError("line %d: expected a map" % (L.i + 1))
                    item.update(more)
                out.append(item)
            else:
                out.append(_value(L, rest, indent))
    out = {}
    while True:
        row = L.peek()
        if row is None or row[0] < indent:
            return out
        if row[0] > indent:
            raise WorkflowError("line %d: unexpected indentation" % (L.i + 1))
        m = RE_KEY.match(row[1])
        if not m:
            raise WorkflowError("line %d: not a 'key: value' line: %s" % (L.i + 1, row[1][:60]))
        L.i += 1
        out[_scalar(m.group(1))] = _value(L, m.group(2), indent)


def parse_yaml(text):
    L = _Lines(text)
    first = L.peek()
    if first is None:
        return {}
    node = _node(L, first[0])
    if L.peek() is not None:
        raise WorkflowError("line %d: could not be read" % (L.i + 1))
    return node


# ----------------------------------------------------------------------------
# From workflow files to a local plan
# ----------------------------------------------------------------------------

def triggered_by_push(doc):
    on = doc.get("on", doc.get(True))           # a bare `on:` key reads as true in YAML 1.1
    if isinstance(on, str):
        return on == "push"
    if isinstance(on, list):
        return "push" in on
    return isinstance(on, dict) and "push" in on


def _needs_context(*values):
    return any("${{" in str(v) for v in values if v is not None)


def plan(top, workflow=None, job=None):
    """The local plan of the repo at ``top``: ``(steps, problems)``. A step is ``{label,
    run, cwd, env, always, skip}`` (``skip`` is the reason it does not run here, or
    None); ``problems`` are workflow files that could not be read."""
    wdir = os.path.join(top, WORKFLOW_DIR)
    steps, problems = [], []
    try:
        names = sorted(n for n in os.listdir(wdir) if n.endswith((".yml", ".yaml")))
    except OSError:
        return [], []
    for name in names:
        if workflow and name != workflow:
            continue
        try:
            with open(os.path.join(wdir, name), encoding="utf-8") as fh:
                doc = parse_yaml(fh.read())
            if not isinstance(doc, dict):
                raise WorkflowError("not a map")
        except (OSError, WorkflowError, RecursionError) as exc:
            problems.append("%s: cannot be read here (%s)" % (name, exc))
            continue
        if not triggered_by_push(doc) and not workflow:
            continue
        wenv = doc.get("env") if isinstance(doc.get("env"), dict) else {}
        for jid, jd in (doc.get("jobs") or {}).items():
            if (job and jid != job) or not isinstance(jd, dict):
                continue
            jenv = dict(wenv, **(jd.get("env") if isinstance(jd.get("env"), dict) else {}))
            self_path, skipped_setup = None, False
            for n, st in enumerate(jd.get("steps") or [], 1):
                if not isinstance(st, dict):
                    continue
                if "uses" in st:
                    w = st.get("with") if isinstance(st.get("with"), dict) else {}
                    if str(st["uses"]).startswith("actions/checkout") and not w.get("repository") \
                            and w.get("path"):
                        self_path = str(w["path"]).strip("/")
                    continue
                run = st.get("run")
                if not isinstance(run, str) or not run.strip():
                    continue
                label = "%s/%s: %s" % (name, jid, st.get("name") or run.strip().splitlines()[0][:50])
                env = dict(jenv, **(st.get("env") if isinstance(st.get("env"), dict) else {}))
                wd = str(st.get("working-directory") or "").strip("/")
                if self_path and (wd == self_path or wd.startswith(self_path + "/")):
                    wd = wd[len(self_path):].strip("/")
                cond = str(st.get("if") or "")
                skip = None
                lines = [ln for ln in run.splitlines() if ln.strip()]
                if _needs_context(run, wd, *env.values()):
                    skip = "needs GitHub's context (${{ ... }})"
                elif all(RE_SETUP.match(ln) for ln in lines):
                    skip, skipped_setup = "a setup step of the runner (an install or global configuration)", True
                steps.append({"label": label, "run": run, "cwd": os.path.join(top, wd) if wd else top,
                              "env": {str(k): "" if v is None else str(v) for k, v in env.items()},
                              "always": bool(re.search(r"always\(\)|!\s*cancelled\(\)", cond)),
                              "job": "%s/%s" % (name, jid), "skip": skip,
                              "after_skipped_setup": skipped_setup})
    return steps, problems


def find_bash(which=shutil.which, windows=None, exists=os.path.isfile):
    """The ``bash`` the steps run in, or None.

    On Windows ``bash`` on PATH is often ``C:\\Windows\\System32\\bash.exe``, the WSL
    launcher: it would run the steps in another system, with other paths and another
    Python. The workflows are meant for the shell the session's Bash tool is, Git Bash,
    which sits beside ``git``: ``<Git>/bin/bash.exe``. So on Windows the candidates are
    ``$CI_LOCAL_BASH``, Git's own bash (found from ``git``), then a ``bash`` on PATH that
    is not under System32 or WindowsApps. Elsewhere: ``$CI_LOCAL_BASH``, then PATH."""
    override = os.environ.get("CI_LOCAL_BASH")
    if override and exists(override):
        return override
    if not (os.name == "nt" if windows is None else windows):
        return which("bash")
    git = which("git")
    if git:
        d = os.path.dirname(os.path.abspath(git))
        for rel in (("..", "bin", "bash.exe"), ("..", "..", "bin", "bash.exe"),
                    ("bash.exe",), ("..", "usr", "bin", "bash.exe")):
            cand = os.path.normpath(os.path.join(d, *rel))
            if exists(cand):
                return cand
    found = which("bash")
    if found and not re.search(r"(?i)[\\/](system32|sysnative|windowsapps)[\\/]", found):
        return found
    return None


def _shim_dir():
    """A directory whose ``python`` is the interpreter running this script."""
    d = tempfile.mkdtemp(prefix="ci-local-")
    exe = sys.executable.replace("\\", "/")
    for name in ("python",):
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write('#!/bin/sh\nexec "%s" "$@"\n' % exe)
        os.chmod(p, 0o755)
    return d


def max_jobs(environ=None):
    """How many jobs run at once: ``CI_LOCAL_JOBS`` (1 = one after another), else the
    machine's processors."""
    env = os.environ if environ is None else environ
    try:
        n = int(env.get("CI_LOCAL_JOBS", ""))
    except ValueError:
        n = os.cpu_count() or 1
    return max(1, n)


def _run_job(steps, top, bash, shim, timeout):
    """One job's steps, in order. Returns ``(ok, [(position, [lines])])``."""
    ok, failed, out = True, False, []
    for pos, st in steps:
        if st["skip"]:
            out.append((pos, ["ci: %s skipped: %s" % (st["label"], st["skip"])]))
            continue
        if failed and not st["always"]:
            out.append((pos, ["ci: %s skipped: an earlier step of its job failed" % st["label"]]))
            continue
        if not os.path.isdir(st["cwd"]):
            ok, failed = False, True
            out.append((pos, ["ci: %s failed: its working directory %s is not here"
                              % (st["label"], os.path.relpath(st["cwd"], top))]))
            continue
        env = dict(os.environ, CI="true", SHIP_GATE="1", **st["env"])
        env["PATH"] = shim + os.pathsep + env.get("PATH", "")
        try:
            p = subprocess.run([bash, "-e", "-c", st["run"]], cwd=st["cwd"], env=env,
                               capture_output=True, text=True, stdin=subprocess.DEVNULL,
                               timeout=timeout, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            ok, failed = False, True
            out.append((pos, ["ci: %s timed out" % st["label"]]))
            continue
        if p.returncode == 0:
            out.append((pos, ["ci: %s ok" % st["label"]]))
        elif p.returncode == 127 and st["after_skipped_setup"]:
            last = (p.stderr or "").strip().splitlines()[-1:]
            out.append((pos, ["ci: %s skipped: a tool the workflow installs is not on this "
                              "machine (%s)" % (st["label"], last and last[0][:80])]))
        else:
            ok, failed = False, True
            tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-TAIL:]
            out.append((pos, ["ci: %s failed (exit %d):" % (st["label"], p.returncode)]
                        + ["    " + t for t in tail]))
    return ok, out


def run(top, workflow=None, job=None, timeout=1800, jobs=None):
    """Run the local plan. Returns ``(ok, lines)``; ``lines`` name each step as ok,
    skipped (with the reason) or failed (with the tail of its output), in the plan's order.

    The steps of a job run in order; the jobs run at the same time, up to ``jobs`` of them
    (default ``max_jobs()``), as they do on GitHub, where each job has its own runner. Here
    they share the checkout, so a workflow whose jobs write into the tree must be run with
    ``CI_LOCAL_JOBS=1``."""
    steps, problems = plan(top, workflow, job)
    lines = ["ci: " + p for p in problems]
    ok = not problems
    if not steps:
        return ok, lines
    bash = find_bash()
    if not bash:
        return False, lines + ["ci: no bash to run the workflow steps in (on Windows: Git Bash, "
                               "beside git; WSL's bash is not used; CI_LOCAL_BASH names one)"]
    by_job = {}
    for pos, st in enumerate(steps):
        by_job.setdefault(st["job"], []).append((pos, st))
    shim = _shim_dir()
    try:
        workers = min(len(by_job), jobs or max_jobs())
        if workers <= 1:
            results = [_run_job(g, top, bash, shim, timeout) for g in by_job.values()]
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(lambda g: _run_job(g, top, bash, shim, timeout),
                                        by_job.values()))
    finally:
        shutil.rmtree(shim, ignore_errors=True)
    for job_ok, out in results:
        ok = ok and job_ok
    for _pos, ls in sorted(p for _ok, out in results for p in out):
        lines += ls
    return ok, lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "run"):
        p = sub.add_parser(name)
        p.add_argument("--repo", default=".")
        p.add_argument("--workflow", help="one workflow file name (it then runs whatever its trigger)")
        p.add_argument("--job")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    top = os.path.abspath(a.repo)
    if not os.path.isdir(top):
        print("ci_local: no directory %s" % a.repo, file=sys.stderr)
        return 2
    if a.cmd == "list":
        steps, problems = plan(top, a.workflow, a.job)
        for p in problems:
            print("UNREADABLE  " + p)
        for st in steps:
            print("%-8s %s%s" % ("skip" if st["skip"] else "run", st["label"],
                                 "  (%s)" % st["skip"] if st["skip"] else ""))
        if not steps and not problems:
            print("no workflow triggered by push under %s" % WORKFLOW_DIR.replace(os.sep, "/"))
        return 2 if problems else 0
    ok, lines = run(top, a.workflow, a.job)
    print("\n".join(lines) if lines else "nothing to run")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
