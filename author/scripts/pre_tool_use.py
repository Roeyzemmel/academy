"""PreToolUse hook on Edit / Write / MultiEdit / NotebookEdit: the Author plugin's edit
guards in one process.

Each guard is a script of its own (``<guard>.py``, still runnable standalone) with a
``decide(event)`` that returns ``None`` or ``("deny", reason)``. Registered one by one,
an edit started four Python processes and four imports of ``_academy``; this dispatcher
reads the event once, calls the guards the tool selects in a fixed order and emits the
first denial:

=========================  ==================================================
tool                       guards, in order
=========================  ==================================================
Edit, Write, MultiEdit     bib_gate, pinned_guard, preamble_guard,
                           notation_scope_guard
NotebookEdit               notation_scope_guard
=========================  ==================================================

The selection is the matchers the guards had as separate hooks (only
notation_scope_guard covered NotebookEdit); the order is that of their former
registration. All four guards have the same contract (a denial, or silence: none emits
context, an "ask", or exits with 2), so results combine simply: the first denial wins
and later guards do not run; with no denial nothing is printed and the exit code is 0.
A guard that raises, or cannot be imported, is skipped with one line on stderr and the
next one runs: as a separate process its crash never blocked the edit nor the other
guards. Unreadable input exits 0 silently. The other hooks (``commit_gate`` on Bash,
``tex_edit_check``, ``build_gate``) stay separate scripts.
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402

EDIT = ("bib_gate", "pinned_guard", "preamble_guard", "notation_scope_guard")
#: tool name -> the guards (module names in this folder) it runs, in order
GUARDS = {
    "Edit": EDIT,
    "Write": EDIT,
    "MultiEdit": EDIT,
    "NotebookEdit": ("notation_scope_guard",),
}


def guards_for(tool):
    """The guard module names that run for ``tool``, in order (empty for any other)."""
    return GUARDS.get(tool, ())


def _decider(name):
    return importlib.import_module(name).decide


def decide(event, deciders=None, errors=None):
    """The first denial ``("deny", reason)`` of the guards selected by the event's tool,
    or ``None``. ``deciders`` maps a guard name to its ``decide`` (default: the guard's
    module, imported on first use). A guard that raises is skipped; its
    ``(name, exception)`` is appended to ``errors`` when given."""
    for name in guards_for(ac.tool_name(event)):
        try:
            fn = deciders[name] if deciders is not None else _decider(name)
            verdict = fn(event)
        except Exception as exc:   # one guard's bug never blocks the edit or the others
            if errors is not None:
                errors.append((name, exc))
            continue
        if verdict:
            return verdict
    return None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    errors = []
    try:
        verdict = decide(ac.read_event(), errors=errors)
    except Exception:
        return 0
    for name, exc in errors:
        try:
            sys.stderr.write("author: %s failed and was skipped: %s: %s\n"
                             % (name, type(exc).__name__, exc))
        except Exception:
            pass
    if verdict:
        ac.emit_permission(verdict[0], verdict[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
