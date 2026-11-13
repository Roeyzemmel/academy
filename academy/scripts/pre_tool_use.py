"""PreToolUse hook on Bash / PowerShell and on Edit / Write / MultiEdit / NotebookEdit:
the base plugin's guards in one process.

Each guard is a script of its own (``<guard>.py``, still runnable standalone) with a
``decide(event)`` that returns ``None`` or ``(decision, reason)``. Registered one by one,
a shell call started three Python processes and three imports of ``_academy``; this
dispatcher reads the event once and calls the guards that the tool selects, in a fixed
order, and emits the first verdict:

=========================  ==================================================
tool                       guards, in order
=========================  ==================================================
Bash, PowerShell           script_path_guard, ship_guard, generated_view_guard
Edit, Write, MultiEdit     explainer_write_guard, role_write_guard,
                           generated_view_guard
NotebookEdit               explainer_write_guard, role_write_guard
=========================  ==================================================

The selection is the matchers the guards had as separate hooks (generated_view_guard
never covered NotebookEdit). The order is the order of their former registration; it
only matters when two guards would deny the same call, and then the first one's reason
is the one shown. A guard that raises is skipped (one line on stderr) and the next one
runs: as a separate process its crash never blocked the call nor the other guards.
The ``mcp_write_gate`` hook and the other events stay separate scripts.
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402

SHELL = ("script_path_guard", "ship_guard", "generated_view_guard")
EDIT = ("explainer_write_guard", "role_write_guard", "generated_view_guard")
#: tool name -> the guards (module names in this folder) it runs, in order
GUARDS = {
    "Bash": SHELL,
    "PowerShell": SHELL,
    "Edit": EDIT,
    "Write": EDIT,
    "MultiEdit": EDIT,
    "NotebookEdit": ("explainer_write_guard", "role_write_guard"),
}


def guards_for(tool):
    """The guard module names that run for ``tool``, in order (empty for any other)."""
    return GUARDS.get(tool, ())


def _decider(name):
    return importlib.import_module(name).decide


def decide(event, deciders=None, errors=None):
    """The first verdict ``(decision, reason)`` of the guards selected by the event's
    tool, or ``None``. ``deciders`` maps a guard name to its ``decide`` (default: the
    guard's module, imported on first use). A guard that raises is skipped; its
    ``(name, exception)`` is appended to ``errors`` when given."""
    for name in guards_for(ac.tool_name(event)):
        try:
            fn = deciders[name] if deciders is not None else _decider(name)
            verdict = fn(event)
        except Exception as exc:   # one guard's bug never blocks the call or the others
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
            sys.stderr.write("academy: %s failed and was skipped: %s: %s\n"
                             % (name, type(exc).__name__, exc))
        except Exception:
            pass
    if verdict:
        ac.emit_permission(verdict[0], verdict[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
