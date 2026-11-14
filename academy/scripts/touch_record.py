"""PostToolUse hook on Edit|Write|MultiEdit|NotebookEdit: record a role's write in another
role's home in the touch ledger, so the checkpoint after the ticket ships it.

The checkpoint after a ticket is scoped to the acting role's repos; a sanctioned
cross-role write (``permissions.json`` ``files.cross_role`` forbids only some), such as
the Expert's librarian adding an entry to an Author home's ``references.bib``, would
otherwise stay uncommitted. This hook records the file (``ac.record_touch``) when:

* the edit was made by an agent with a role (its plugin namespace, else its roster
  entry); the main session is the human, whose edits are never recorded;
* the file lies in the home of a workspace instance whose role is not the agent's;
* workspace.json does not say ``"shipCheckpoint": false``.

The acting instance is the home the session runs in when that home has the agent's role,
else unknown (the ledger then matches by role). PostToolUse: only a write that happened
is recorded. A hook bug never blocks anything: every failure is silence.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _academy as ac  # noqa: E402

OWN_PERMISSIONS = os.path.join(os.path.dirname(HERE), "permissions.json")


def load_permissions():
    if not os.environ.get("ACADEMY_PERMISSIONS") and os.path.isfile(OWN_PERMISSIONS):
        return ac.load_permissions(OWN_PERMISSIONS)
    return ac.load_permissions()


def agent_role(event, perms):
    ns, bare = ac.agent_identity(event)
    if not bare:
        return None, ""
    if ns in ac.ROLES:
        return ns, "%s:%s" % (ns, bare)
    try:
        role = ac.roster(perms).get(bare)
    except ac.AcademyError:
        role = None
    return (role if role in ac.ROLES else None), ("%s:%s" % (ns, bare) if ns else bare)


def acting_instance(ws, cwd, role):
    """The instance whose home holds the session's cwd, when it has ``role``; else None."""
    name, inst = ac.home_of_path(ws, cwd) if cwd else (None, None)
    return name if inst and inst.get("role") == role else None


def decide(event, perms=None, ws=None):
    """``(root, path, role, instance, agent, tool)`` to record, or None."""
    perms = perms if perms is not None else load_permissions()
    role, agent = agent_role(event, perms)
    if not role:
        return None
    path = ac.edited_path(event)
    if not path:
        return None
    cwd = ac.event_cwd(event)
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    ws = ws if ws is not None else ac.load_workspace()
    if ws.get("shipCheckpoint") is False:
        return None
    if not ac.is_cross_home(ws, path, role):
        return None
    root = os.path.dirname(ws["_path"])
    return root, path, role, acting_instance(ws, cwd, role), agent, ac.tool_name(event)


def main():
    try:
        hit = decide(ac.read_event())
        if hit:
            root, path, role, instance, agent, tool = hit
            ac.record_touch(root, [path], role, instance, agent=agent, via=tool)
    except Exception:            # a recording bug never blocks an edit
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
