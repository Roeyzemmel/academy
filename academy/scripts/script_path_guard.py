"""PreToolUse hook on Bash / PowerShell: a call to an academy script at a path where it
is not gets the path where it is.

The plugins' scripts live in ``<academy repo>/<plugin>/scripts`` (an installed plugin:
``<cache>/<plugin>/<version>/scripts``). A prompt often names one by its bare name
(``cowork.py status ...``) and the agent guesses the folder: ``academy/scripts/cowork.py``
from the workspace root, ``scripts/notebook.py`` in a home, ``cards.py`` under the base
plugin instead of the Expert's. The error ledger of 2026-10-31..11-13 has 22 such
failures, up to nine in a row for one script. The hook denies the call only when

* the command runs ``py`` / ``python`` / ``python3`` on a ``*.py`` path that it can
  resolve (no variable, glob or substitution in it) and that file does not exist,
* the command does not write that file itself, and
* the file's name is the name of an academy script,

and the reason carries the full path to use.

On Windows it also denies a command that runs ``python`` / ``python3`` when that name is
the Microsoft Store stub ("Python was not found", 6 failures) and ``py`` exists: the
reason says to use ``py``.

Every other command passes untouched; the hook never fails a call for a reason of its own.
"""

import glob
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RE_RUN = re.compile(r"""(?:^|[\s;&|(])(?:py|python3?)(?:\.exe)?\s+(?:-[A-Za-z]\s+)*
                        (?:"([^"]+\.py)"|'([^']+\.py)'|([^\s"';|&<>()]+\.py))(?=$|[\s;&|)])""",
                    re.X)
UNRESOLVABLE = re.compile(r"[$`*?%~]")


def script_roots():
    """Folders that hold ``<plugin>/scripts``: the academy repo of this checkout (or
    $ACADEMY_ROOT), and for an installed plugin the cache's ``<plugin>/<version>``."""
    out = []
    for base in (os.environ.get("ACADEMY_ROOT"), os.path.dirname(PLUGIN_ROOT)):
        if base and os.path.isdir(base) and base not in out:
            out.append(base)
    return out


def find_scripts(name, roots=None):
    """Every academy script called ``name`` (sorted, forward slashes)."""
    found = set()
    for root in roots if roots is not None else script_roots():
        for pat in ("*/scripts/%s", "*/*/scripts/%s"):
            for p in glob.glob(os.path.join(root, pat % name)):
                if os.path.isfile(p):
                    found.add(os.path.realpath(p))
    return sorted(p.replace("\\", "/") for p in found)


def _native(path):
    """A Git-Bash or WSL drive path (``/c/x``, ``/mnt/c/x``) as a Windows one."""
    if os.name == "nt":
        m = re.match(r"^/(?:mnt/)?([A-Za-z])/(.*)$", path)
        if m:
            return "%s:/%s" % (m.group(1), m.group(2))
    return path


RE_CD_ANY = re.compile(r"""(?:^|[;&|(]\s*|&&\s*|\|\|\s*)(?:cd|pushd|Set-Location)\s+
                           (?:"([^"]*)"|'([^']*)'|([^\s;&|)]+))""", re.X | re.M)
RE_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n.*?^\s*\2\s*$",
                        re.S | re.M)


def shell_text(command):
    """``command`` without the bodies of its here-documents, which are data (a script
    fed to an interpreter, a file being written), not commands the shell runs."""
    return RE_HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0] + "\n", command)


def missing_scripts(command, cwd):
    """``[(path as written, name)]`` for each ``py <path>.py`` of ``command`` whose file
    does not exist, read from the directory in force where it is run: ``cwd``, moved by
    every ``cd`` that precedes it in the command. Here-document bodies are not read.
    Once a ``cd`` cannot be followed (a variable, ``cd -``, ``popd``, a directory that
    does not exist) nothing after it is judged: a guard that cannot tell where a command
    runs says nothing."""
    whole = command
    command = shell_text(command)
    moves = []                                        # (position, directory or None)
    for m in RE_CD_ANY.finditer(command):
        d = next((g for g in m.groups() if g is not None), "")
        moves.append((m.start(), None if (not d or d == "-" or UNRESOLVABLE.search(d))
                      else _native(d)))
    for m in re.finditer(r"(?:^|[;&|(]\s*)popd\b", command, re.M):
        moves.append((m.start(), None))
    moves.sort()
    out = []
    for m in RE_RUN.finditer(command):
        written = next(g for g in m.groups() if g)
        if UNRESOLVABLE.search(written):
            continue
        here, known = cwd, True
        for pos, d in moves:
            if pos > m.start():
                break
            if d is None:
                known = False
                break
            here = os.path.normpath(os.path.join(here, d))
            if not os.path.isdir(here):
                known = False
                break
        if not known:
            continue
        name = os.path.basename(written.replace("\\", "/"))
        if re.search(r">\s*[\"']?[^\s\"']*%s" % re.escape(name), whole):
            continue                                  # the command writes it first
        full = os.path.join(here, _native(written))
        if not os.path.exists(full):
            out.append((written, name))
    return out


RE_PYTHON_WORD = re.compile(r"(?:^|[;&|(]\s*|&&\s*|\|\|\s*)(python3?)(?=\s|$)", re.M)


def store_stub(which=shutil.which, windows=None):
    """True on Windows when ``python`` is missing or the Store's alias while ``py`` works."""
    if not (os.name == "nt" if windows is None else windows):
        return False
    exe = which("python") or ""
    return bool(which("py")) and (not exe or "windowsapps" in exe.lower())


def decide(event, roots=None, stub=None):
    """``None`` or ``("deny", reason)`` for one PreToolUse event."""
    if ac.tool_name(event) not in ("Bash", "PowerShell"):
        return None
    cmd = ac.shell_command(event)
    if not cmd:
        return None
    m = RE_PYTHON_WORD.search(shell_text(cmd))
    if m and (store_stub() if stub is None else stub):
        return ("deny", "academy: on this machine `%s` is the Microsoft Store stub (it "
                        "prints \"Python was not found\"); run the same command with "
                        "`py` (references/windows.md)." % m.group(1))
    if ".py" not in cmd:
        return None
    for written, name in missing_scripts(cmd, ac.event_cwd(event)):
        where = find_scripts(name, roots)
        if not where:
            continue
        if len(where) == 1:
            tail = "the academy script %s is %s; run the same command with that path" % (
                name, where[0])
        else:
            tail = ("%s is a script of several plugins; use your role's: %s"
                    % (name, ", ".join(where)))
        return ("deny", "academy: %s does not exist (nothing was run): %s. The plugins' "
                        "scripts are in <plugin>/scripts of the academy repo; a home and "
                        "the workspace root have none of their own." % (written, tail))
    return None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        verdict = decide(ac.read_event())
    except Exception:           # a guard of convenience never blocks a call by failing
        return 0
    if verdict:
        ac.emit_permission(verdict[0], verdict[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
