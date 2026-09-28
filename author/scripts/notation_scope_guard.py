"""PreToolUse (Edit|Write|MultiEdit|NotebookEdit): the notation-auditor edits one file.

Plan section 3.2: the notation-auditor "edits only the repo's notation-decisions.md";
a change to the domain pack's notation goes to the Expert as a ticket. This hook makes
that mechanical. When the caller is the notation-auditor (``agent_identity``,
namespace-stripped; a namespaced caller must come from the ``author`` plugin), the
edit is allowed only on ``<author home>/.claude/rules/notation-decisions.md``, where
an Author home is any author instance of workspace.json or any directory whose
``.claude/academy.json`` has role author. Every other edit by it is denied.

The hook scopes by agent, not by path: an edit by any other caller passes silently.
A hook bug never blocks an edit.
"""

import os
import sys

import _author as au

ac = au.ac

AGENT = "notation-auditor"
NAMESPACES = ("", "author")
DECISIONS_REL = os.path.join(".claude", "rules", "notation-decisions.md")


def author_homes(path, ws=None):
    """Author homes to test ``path`` against: the one containing it, and every author
    instance of workspace.json (a home not yet switched over has no academy.json)."""
    homes = []
    home, _ = au.author_home(path)
    if home:
        homes.append(home)
    try:
        ws = ws if ws is not None else ac.load_workspace()
    except ac.AcademyError:
        ws = None
    for inst in (ws or {}).get("instances", {}).values():
        if inst.get("role") == "author" and inst.get("home"):
            homes.append(inst["home"])
    return homes


def decide(event, ws=None):
    """``None`` or ``("deny", reason)``."""
    ns, bare = ac.agent_identity(event)
    if bare != AGENT or ns not in NAMESPACES:
        return None
    path = ac.edited_path(event)
    if path and not os.path.isabs(path):
        path = os.path.join(ac.event_cwd(event), path)
    if path:
        full = os.path.normcase(os.path.abspath(path))
        for home in author_homes(path, ws):
            want = os.path.normcase(os.path.abspath(os.path.join(home, DECISIONS_REL)))
            if full == want:
                return None
    return ("deny", "author: the notation-auditor edits only the home's "
                    ".claude/rules/notation-decisions.md (%s was refused). Report the "
                    "draft's clashes; a change to the domain pack's notation.md is a "
                    "`notation` ticket to the Expert (tickets_create)." % (path or "?"))


def main():
    try:
        verdict = decide(ac.read_event())
    except Exception:            # a guard bug never blocks an edit
        return 0
    if verdict:
        ac.emit_permission(verdict[0], verdict[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
