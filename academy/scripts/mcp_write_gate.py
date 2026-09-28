"""PreToolUse hook on the academy MCP tools (matcher ``mcp__.*academy.*``).

Denies a write tool the calling agent may not use per ``academy/permissions.json``
(docs/protocol.md section 5). The human (no agent_type) passes. Read tools, which
permissions.json does not list, pass for everyone. A call carrying the reserved
``caller`` argument is denied for everyone: identity is never taken from arguments.

For every call it does not deny, the hook records the caller ('human' or the
namespaced agent type) in the caller handshake directory
(``record_caller`` in the vendored lib); the server consumes that record and so learns
who is calling. The allowed call itself is left silent so that Claude Code's own
permission prompts still apply; the server then checks the substance of the call.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402


def decide(event, perms=None):
    """``None`` (no opinion) or ``("deny", reason)`` for one PreToolUse event."""
    tool = ac.mcp_tool(event)
    if not tool:
        return None
    reserved = [k for k in ac.RESERVED_ARGS if k in ac.tool_input(event)]
    if reserved:
        return ("deny", "academy: the argument %r is reserved; the caller is identified "
                        "by the mcp_write_gate hook, never by an argument. Call again "
                        "without it." % reserved[0])
    ns, bare = ac.agent_identity(event)
    if not bare:
        return None                                  # the human may call everything
    if perms is None:
        try:
            perms = ac.load_permissions()
        except ac.AcademyError as exc:
            return ("deny", "academy: permissions.json unreadable (%s); agents may not "
                            "call academy tools until it is fixed" % exc)
    if tool not in perms.get("tools", {}):
        return None                                  # a read tool: open to every caller
    ok, reason = ac.may_call(perms, tool, bare)
    if ok:
        return None
    who = "%s:%s" % (ns, bare) if ns else bare
    return ("deny", "academy: %s may not call %s (%s). Ask the owning agent or file a "
                    "ticket instead (docs/protocol.md section 5)." % (who, tool, reason))


def caller_of(event):
    """The caller string recorded for the server: 'human' or 'plugin:agent'."""
    ns, bare = ac.agent_identity(event)
    if not bare:
        return ac.HUMAN
    return "%s:%s" % (ns, bare) if ns else bare


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    event = ac.read_event()
    verdict = decide(event)
    if verdict:
        ac.emit_permission(verdict[0], verdict[1])
        return 0
    tool = ac.mcp_tool(event)
    if tool:
        try:
            ac.record_caller(tool, ac.tool_input(event), caller_of(event))
        except OSError as exc:       # the server will refuse writes; say why
            sys.stderr.write("academy: could not record the caller (%s)\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
