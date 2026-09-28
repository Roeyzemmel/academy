"""_author -- helpers shared by the Author plugin's hooks and scripts.

Plugin-local (not vendored). Everything protocol-level comes from the vendored
``_academy.py`` (never edit that copy; see academy/scripts/sync_common.py). This
module adds only what the Author role needs:

    author_home(path)          (home, config) when ``path`` lies in an Author home
    author_settings(config)    the ``author`` block with the plugin defaults merged in
    checker_command(...)       argv of check_paper.py for a home
    run_checker(...)           (exit code, output) of that command
    findings / new_findings    checker findings keyed file|label|rule, minus the baseline
    dirty marker               ``<build.dir>/.dirty``, left by tex_edit_check for build_gate
    BuildLock                  ``author.build.lock`` (default ``.build/.lock``)

Every hook built on this is a silent no-op outside an Author home: a path whose
nearest ``.claude/academy.json`` is missing, invalid, or of another role gives
``(None, None)``.
"""

import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402

PLUGIN_ROOT = os.path.dirname(HERE)

#: writers whose SubagentStop owes a build (build_gate), when the config names none.
#: librarian is here because a bib edit changes the build (tex_edit_check marks it).
DEFAULT_WRITERS = ("math-writer", "math-editor", "tex-engineer", "note-sweeper",
                   "figure-maker", "librarian")
#: the only agents allowed to edit the bibliography (bib_gate), by bare name
DEFAULT_BIB_WRITERS = ("librarian",)
#: the plugin namespace a bib writer must come from when it arrives namespaced
BIB_WRITER_NAMESPACE = "expert"
DEFAULT_BASELINE = ".claude/paper-gate-baseline.txt"

AUTHOR_DEFAULTS = {
    "main": "main.tex",
    "build": {"dir": ".build", "cmd": ["latexmk", "-pdf", "main.tex"],
              "lock": ".build/.lock"},
    "checker": {"script": "${CLAUDE_PLUGIN_ROOT}/scripts/check_paper.py", "args": [],
                "strictArgs": ["--strict"], "statements": "Drafts/statements.md"},
    "writers": list(DEFAULT_WRITERS),
    "bibWriters": list(DEFAULT_BIB_WRITERS),
}

FINDING = re.compile(
    r"^\s*(?P<file>[^\s:]+):(?P<line>\d+):\s*(?P<label>.*?):\s*\[(?P<rule>[A-Z]\d+)\]"
)


# ----------------------------------------------------------------------------
# Home and config
# ----------------------------------------------------------------------------

def author_home(path):
    """``(home, config)`` if ``path`` lies in an Author home with a valid config.

    ``path`` may be a file or a directory. Returns ``(None, None)`` otherwise and
    never raises: a hook must never fail a tool call because of its own config.
    """
    if not path:
        return None, None
    try:
        home = ac.find_home(path)
        if not home:
            return None, None
        cfg = ac.load_config(home)
    except (ac.AcademyError, OSError, ValueError):
        return None, None
    if cfg.get("role") != "author":
        return None, None
    return home, cfg


def author_settings(config):
    """The config's ``author`` block, with AUTHOR_DEFAULTS merged underneath."""
    block = config.get("author") if isinstance(config, dict) else None
    out = {}
    for key, default in AUTHOR_DEFAULTS.items():
        val = (block or {}).get(key)
        if isinstance(default, dict):
            merged = dict(default)
            if isinstance(val, dict):
                merged.update(val)
            out[key] = merged
        else:
            out[key] = val if val is not None else (list(default)
                                                     if isinstance(default, list)
                                                     else default)
    for key, val in (block or {}).items():
        out.setdefault(key, val)
    return out


def expand_plugin_root(value):
    return str(value).replace("${CLAUDE_PLUGIN_ROOT}", PLUGIN_ROOT)


def home_path(home, rel):
    """``rel`` (config-style, '/' separators) resolved inside ``home``."""
    rel = str(rel).replace("\\", "/")
    if os.path.isabs(rel):
        return os.path.normpath(rel)
    return os.path.normpath(os.path.join(home, *rel.split("/")))


# ----------------------------------------------------------------------------
# The checker
# ----------------------------------------------------------------------------

def checker_command(home, config, strict=False, extra=()):
    s = author_settings(config)["checker"]
    script = expand_plugin_root(s.get("script") or AUTHOR_DEFAULTS["checker"]["script"])
    argv = [sys.executable, script, "--root", home] + [str(a) for a in s.get("args") or []]
    if strict:
        argv += [str(a) for a in (s.get("strictArgs") or ["--strict"])]
    return argv + list(extra)


def run_checker(home, config, strict=False, timeout=120, extra=()):
    """Run the home's checker. Returns ``(exit code, output)``; code None if it could not run."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        proc = subprocess.run(checker_command(home, config, strict, extra), cwd=home,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None, "checker timed out"
    except OSError as exc:
        return None, "checker could not run: %s" % exc
    return proc.returncode, proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n")


def findings(output):
    """Map finding key ``file|label|rule`` -> the first line reporting it.

    Keyed without line numbers, which drift with every edit.
    """
    found = {}
    for line in (output or "").splitlines():
        m = FINDING.match(line)
        if not m:
            continue
        key = "%s|%s|%s" % (m.group("file").replace("\\", "/"),
                            m.group("label").strip(), m.group("rule"))
        found.setdefault(key, line.strip())
    return found


def baseline_path(home, config):
    gate = (config or {}).get("gate") or {}
    rel = gate.get("baseline") or DEFAULT_BASELINE
    return home_path(home, rel)


def load_baseline(home, config):
    path = baseline_path(home, config)
    if not os.path.isfile(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return {ln.strip() for ln in handle if ln.strip() and not ln.startswith("#")}
    except OSError:
        return set()


def new_findings(home, config, output):
    """The findings in ``output`` that the recorded baseline does not accept."""
    base = load_baseline(home, config)
    return {k: v for k, v in findings(output).items() if k not in base}


# ----------------------------------------------------------------------------
# Build state
# ----------------------------------------------------------------------------

def build_dir(home, config):
    return home_path(home, author_settings(config)["build"].get("dir") or ".build")


def dirty_path(home, config):
    return os.path.join(build_dir(home, config), ".dirty")


def mark_dirty(home, config, why="tex edited"):
    try:
        os.makedirs(build_dir(home, config), exist_ok=True)
        with open(dirty_path(home, config), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(why + "\n")
    except OSError:
        pass


def clear_dirty(home, config):
    try:
        os.remove(dirty_path(home, config))
    except OSError:
        pass


def is_dirty(home, config):
    return os.path.isfile(dirty_path(home, config))


class BuildLock(object):
    """``author.build.lock`` (default ``.build/.lock``), held while build_gate builds.

    Created with O_CREAT|O_EXCL and ``"<pid> <unix time>"`` inside. A lock older
    than ``stale`` seconds is broken. ``acquire`` waits up to ``wait`` seconds and
    returns False if it could not take the lock. LaTeX Workshop honours it only if
    its recipe is told to (tex-engineer's job; see agents/tex-engineer.md).
    """

    def __init__(self, home, config, stale=330.0):
        rel = author_settings(config)["build"].get("lock") or ".build/.lock"
        self.path = home_path(home, rel)
        self.stale = stale
        self.held = False

    def acquire(self, wait=60.0, poll=0.25, now=time.time, sleep=time.sleep):
        deadline = now() + wait
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = now() - os.path.getmtime(self.path)
                except OSError:
                    continue
                if age > self.stale:
                    try:
                        os.remove(self.path)
                    except OSError:
                        pass
                    continue
                if now() >= deadline:
                    return False
                sleep(poll)
                continue
            with os.fdopen(fd, "w") as fh:
                fh.write("%d %d\n" % (os.getpid(), int(now())))
            self.held = True
            return True

    def release(self):
        if self.held:
            try:
                os.remove(self.path)
            except OSError:
                pass
            self.held = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()
