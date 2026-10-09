"""PreToolUse hook on Edit|Write|MultiEdit|NotebookEdit: no role writes another role's work.

academy/references/roster-rules.md, "Role cut", rule 5; the rules are data, in
``permissions.json`` ``files.cross_role.rules``. Each rule names a ``role`` and what an
agent of that role may not write:

* ``homes``: roles whose homes it writes nothing in (an Author agent in a Researcher
  home: no object, proof attempt or record -- it asks through a ``research`` ticket);
* ``suffixes``: file types it never edits, wherever they are (a Researcher agent and
  ``.tex``: the Author lands).

An agent's role is its plugin namespace (``author:math-writer``), else its roster
entry. The main session (the human, or the orchestrator acting for the human) is not
scoped here; its charter is ``academy/references/orchestrator.md``. A home is found by
its ``.claude/academy.json``, else by a workspace.json instance whose home contains the
path.

A hook bug never blocks an edit: an unreadable permissions file or workspace is silence.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _academy as ac  # noqa: E402

#: the rules ship with the hook: this plugin's permissions.json, unless overridden
OWN_PERMISSIONS = os.path.join(os.path.dirname(HERE), "permissions.json")


def load_permissions():
    if not os.environ.get("ACADEMY_PERMISSIONS") and os.path.isfile(OWN_PERMISSIONS):
        return ac.load_permissions(OWN_PERMISSIONS)
    return ac.load_permissions()


def rules(perms):
    block = ((perms or {}).get("files") or {}).get("cross_role") or {}
    return [r for r in block.get("rules") or [] if isinstance(r, dict) and r.get("role")]


def agent_role(event, perms):
    """The acting agent's role, or None for the main session or an unknown agent."""
    ns, bare = ac.agent_identity(event)
    if not bare:
        return None, bare
    if ns in ac.ROLES:
        return ns, bare
    role = ac.roster(perms).get(bare)
    return (role if role in ac.ROLES else None), bare


def home_role(path, ws=None):
    """The role of the home that contains ``path`` (its academy.json, else workspace.json),
    or None."""
    home = ac.find_home(path)
    if home:
        try:
            return ac.load_config(home).get("role")
        except (ac.AcademyError, OSError, ValueError):
            pass
    try:
        ws = ws if ws is not None else ac.load_workspace()
    except ac.AcademyError:
        return None
    best, role = "", None
    full = os.path.abspath(path)
    for inst in (ws or {}).get("instances", {}).values():
        h = inst.get("home")
        if h and ac._rel_to(h, full) is not None and len(h) > len(best):
            best, role = h, inst.get("role")
    return role


def decide(event, perms=None, ws=None):
    """``None`` or ``("deny", reason)`` for one PreToolUse event."""
    perms = perms if perms is not None else load_permissions()
    role, bare = agent_role(event, perms)
    if not role:
        return None
    path = ac.edited_path(event)
    if not path:
        return None
    if not os.path.isabs(path):
        path = os.path.join(ac.event_cwd(event), path)
    for r in rules(perms):
        if r["role"] != role:
            continue
        if bare in (r.get("except") or []):
            continue
        if any(path.lower().endswith(s.lower()) for s in r.get("suffixes") or []):
            return ("deny", "role_write_guard: %s (%s) may not write %s: %s. "
                            "roster-rules.md, 'Role cut': file a ticket to the role that "
                            "owns it." % (bare, role, path, r.get("why") or "another role's file"))
        homes = r.get("homes") or []
        if homes:
            hr = home_role(path, ws)
            if hr in homes:
                return ("deny", "role_write_guard: %s (%s) may not write in a %s home "
                                "(%s): %s. roster-rules.md, 'Role cut'."
                        % (bare, role, hr, path, r.get("why") or "another role's home"))
    return None


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
