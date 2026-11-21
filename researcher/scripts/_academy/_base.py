"""Vocabulary, the error classes and paths: what every other part builds on.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import datetime as _dt
import os
import re

#: the package directory. It sits where the single-file library used to be
#: (``academy/lib/academy_common.py``, a plugin's ``scripts/_academy.py``), so a path
#: counted up from it (the repo root, the academy's lib and scripts) is unchanged.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))

SCHEMA_VERSION = 1

# ----------------------------------------------------------------------------
# Vocabulary
# ----------------------------------------------------------------------------

ROLES = ("author", "researcher", "expert", "scientist")
#: plugin names that ship agents (the base plugin has agents but no instances)
PLUGINS = ("academy",) + ROLES
MODELS = ("fable", "opus", "sonnet", "haiku")
HUMAN = "human"

RE_INSTANCE = re.compile(r"^(author|researcher|expert|scientist)@[a-z0-9][a-z0-9-]*$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_TICKET_ID = re.compile(r"^T-\d{4,}$")
RE_PACKET_ID = re.compile(r"^P-\d{4,}$")
RE_COWORK = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

CONFIG_REL = os.path.join(".claude", "academy.json")
BOARD_BACKENDS = ("files", "github")

def _same_file(a, b):
    return bool(a and b) and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def env_home_name(instance):
    """The environment variable that overrides an instance's home: ``<role>@<name>`` ->
    ``ACADEMY_HOME_<ROLE>_<NAME>`` (scripts/bootstrap.py of the workspace sets them all)."""
    return "ACADEMY_HOME_" + re.sub(r"[^A-Za-z0-9]+", "_", instance).strip("_").upper()


class AcademyError(Exception):
    """Base class for every error raised here."""


class ConfigError(AcademyError):
    """A missing or invalid academy.json / workspace.json."""


class FrontmatterError(AcademyError):
    """Frontmatter outside the supported YAML subset."""


class LockTimeout(AcademyError):
    """board/.ids/lock could not be acquired in time."""


def today():
    """Today's date as 'YYYY-MM-DD' (local time), the only date format used."""
    return _dt.date.today().isoformat()


# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------

def _norm(path):
    """Absolute, normalised, forward-slash path; lower-cased on Windows for comparison."""
    p = os.path.normpath(os.path.abspath(str(path))).replace("\\", "/")
    return p.lower() if os.name == "nt" else p


def _rel_to(root, path):
    """``path`` relative to ``root`` with '/' separators, or None if outside it."""
    try:
        rel = os.path.relpath(os.path.abspath(str(path)), os.path.abspath(str(root)))
    except ValueError:              # different drives on Windows
        return None
    rel = rel.replace("\\", "/")
    if rel == ".":
        return ""
    if rel == ".." or rel.startswith("../"):
        return None
    return rel


#: a workflow run's pinned code: ``<checkout>/.worktrees/run-<sha12>`` (run_pin.py, #97)
_RUN_PIN = re.compile(r"^run-[0-9a-f]{12}$")


def is_run_pin(path):
    """Whether ``path`` is the pinned code of a workflow run (``academy/scripts/run_pin.py``:
    ``<academy checkout>/.worktrees/run-<sha12>``)."""
    path = os.path.normpath(os.path.abspath(str(path)))
    return bool(_RUN_PIN.match(os.path.basename(path))) and \
        os.path.basename(os.path.dirname(path)) == ".worktrees"


def _own_checkout():
    here = os.path.realpath(os.path.abspath(_PKG_DIR))
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


def run_pin_source():
    """The main checkout whose pin this package runs from, or None when it runs from no pin."""
    own = _own_checkout()
    return os.path.dirname(os.path.dirname(own)) if is_run_pin(own) else None


def repo_root():
    """The academy repo root.

    A package inside a workflow run's pin (``is_run_pin``) answers the pin, whatever
    ``ACADEMY_ROOT`` says: a run's scripts read the run's code, never the live checkout's
    (#97). Otherwise ``ACADEMY_ROOT`` wins, and else it is three levels above this package,
    which holds both for ``academy/lib/academy_common/`` and for a vendored copy at
    ``<plugin>/scripts/_academy/``; symlinks (``~/.claude/skills/<name>``) are
    resolved first.
    """
    own = _own_checkout()
    if is_run_pin(own):
        return own
    env = os.environ.get("ACADEMY_ROOT")
    if env:
        return os.path.abspath(env)
    return own


def find_home(path):
    """The nearest directory at or above ``path`` that contains ``.claude/academy.json``.

    ``path`` may be a file or a directory, and need not exist. The user's own home
    directory is never a home (``~/.claude`` is Claude Code's global config).
    Returns an absolute path, or None.
    """
    if not path:
        return None
    cur = os.path.abspath(str(path))
    if not os.path.isdir(cur):
        cur = os.path.dirname(cur)
    user_home = _norm(os.path.expanduser("~"))
    while True:
        if _norm(cur) != user_home and os.path.isfile(os.path.join(cur, CONFIG_REL)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
