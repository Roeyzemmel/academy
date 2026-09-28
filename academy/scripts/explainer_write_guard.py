"""PreToolUse hook on Edit|Write|MultiEdit|NotebookEdit: the explainer writes one kind of file.

The explainer is in ``permissions.json`` ``groups.readonly``: it may read every home but
edits none. Its one output is the deep-dive bundle ``<board>/deep-dives/<id>.json``
(skills/deep-dive, step 3), so it keeps the Write tool, and this hook makes that
limit mechanical instead of a sentence in its prompt:

* the caller is the explainer (``agent_identity``, namespace-stripped; a namespaced
  caller must come from the ``academy`` plugin);
* the tool is ``Write`` and the path is a ``.json`` file directly inside
  ``<board>/deep-dives/`` (board from workspace.json) -> allowed;
* anything else the explainer tries to write -> denied, with the reason.

Every other caller passes silently (the explainer is the only agent this hook scopes).
A hook bug never blocks an edit: a malformed event or an unreadable workspace is
silence, except that the explainer is then denied, because it has no other file to
write.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402

AGENT = "explainer"
NAMESPACES = ("", "academy")
OUTPUT_DIR = "deep-dives"


def deep_dive_dir(ws=None):
    """``<board>/deep-dives`` from workspace.json, or None when it cannot be read."""
    try:
        ws = ws if ws is not None else ac.load_workspace()
    except ac.AcademyError:
        return None
    return os.path.join(os.path.abspath(ws["board"]), OUTPUT_DIR)


def decide(event, ws=None):
    """``None`` or ``("deny", reason)`` for one PreToolUse event."""
    ns, bare = ac.agent_identity(event)
    if bare != AGENT or ns not in NAMESPACES:
        return None
    path = ac.edited_path(event)
    tool = ac.tool_name(event)
    if path and not os.path.isabs(path):
        path = os.path.join(ac.event_cwd(event), path)
    out_dir = deep_dive_dir(ws)
    if tool == "Write" and path and out_dir and path.lower().endswith(".json"):
        full = os.path.normcase(os.path.abspath(path))
        if os.path.dirname(full) == os.path.normcase(out_dir):
            return None
    return ("deny", "academy: the explainer is read-only on every home and writes only "
                    "its deep-dive bundle, <board>/deep-dives/<id>.json, with the Write "
                    "tool (%s %s was refused). Put everything in that one file and say "
                    "in your report what you could not write." % (tool or "?", path or ""))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        verdict = decide(ac.read_event())
    except Exception:            # a guard bug never blocks an edit
        return 0
    if verdict:
        ac.emit_permission(verdict[0], verdict[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
