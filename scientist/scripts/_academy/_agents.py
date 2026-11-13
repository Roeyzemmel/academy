"""Who is acting: agent identity, ``permissions.json``, and the hook-to-server
caller handshake.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import hashlib
import json
import os
import time

from ._base import ConfigError, HUMAN, repo_root
from ._config import _read_json

# ----------------------------------------------------------------------------
# Agents and permissions
# ----------------------------------------------------------------------------

#: event keys the acting agent's identity has been observed under, in precedence order
AGENT_KEYS = ("agent_type", "subagent_type", "agentType", "subagentType")


def agent_identity(event):
    """The acting agent as ``(namespace, bare_name)``; ``("", "")`` for the main session.

    ``event`` is the hook/MCP event as a dict or a JSON string. The identity is read
    from the first non-empty of ``agent_type``, ``subagent_type``, ``agentType``,
    ``subagentType`` at the top level of the event -- never from ``tool_input``,
    where ``subagent_type`` names the agent being *launched*, not the caller.
    A plugin agent arrives namespaced (``author:math-writer``); the namespace names
    the plugin that shipped it and is everything before the *last* colon, the bare
    name everything after it. Both are stripped and lower-cased. A session with no
    agent is the human (the human's main session).
    """
    if isinstance(event, (str, bytes)):
        try:
            event = json.loads(event)
        except ValueError:
            return ("", "")
    if not isinstance(event, dict):
        return ("", "")
    for key in AGENT_KEYS:
        raw = event.get(key)
        if isinstance(raw, str) and raw.strip():
            raw = raw.strip()
            if ":" in raw:
                ns, bare = raw.rsplit(":", 1)
                return (ns.strip().lower(), bare.strip().lower())
            return ("", raw.lower())
    return ("", "")


def is_human(event):
    """True when the event comes from the main session (no agent)."""
    return agent_identity(event)[1] == ""


def load_permissions(path=None):
    """Load ``academy/permissions.json`` (``$ACADEMY_PERMISSIONS`` or under repo_root())."""
    path = path or os.environ.get("ACADEMY_PERMISSIONS") or os.path.join(
        repo_root(), "academy", "permissions.json")
    perms = _read_json(path)
    if not isinstance(perms, dict) or "tools" not in perms or "roster" not in perms:
        raise ConfigError("%s: 'roster' and 'tools' are required" % path)
    return perms


def roster(perms):
    """Map bare agent name -> plugin (role) name, from permissions.json's roster."""
    out = {}
    for plugin, agents in perms.get("roster", {}).items():
        for a in agents:
            out[a] = plugin
    return out


def _expand(perms, names):
    out = set()
    groups = perms.get("groups", {})
    for n in names or []:
        if n == "@all":
            out.update(roster(perms))
        elif n.startswith("@"):
            out.update(_expand(perms, groups.get(n[1:], [])))
        else:
            out.add(n)
    return out


def may_call(perms, tool, bare_name):
    """Whether agent ``bare_name`` ('' = human) may call MCP write tool ``tool``.

    Returns ``(allowed, reason)``. The human may call everything. An agent must be in
    the roster, the tool must be listed, and the agent must be in its expanded
    ``allow`` set and not in its ``deny`` set (deny wins). A tool not listed in
    permissions.json is treated as read-only and allowed.
    """
    if not bare_name:
        return True, "human"
    ros = roster(perms)
    if bare_name not in ros:
        return False, "agent %r is not in the academy roster" % bare_name
    spec = perms.get("tools", {}).get(tool)
    if spec is None:
        return True, "%s is not a gated write tool" % tool
    if bare_name in _expand(perms, spec.get("deny")):
        return False, "%s is denied to %s" % (tool, bare_name)
    if bare_name in _expand(perms, spec.get("allow")):
        return True, "allowed"
    return False, "%s is not granted to %s (%s)" % (tool, bare_name, ros[bare_name])


# ----------------------------------------------------------------------------
# Caller handshake (who is calling an MCP tool)
# ----------------------------------------------------------------------------
#
# The MCP server cannot see the calling agent, and the PreToolUse hook cannot
# change a call's arguments without also auto-approving it (updatedInput needs
# permissionDecision 'allow', which would skip Claude Code's own prompts). So
# the hook and the server meet in a directory instead: for every call it does
# not deny, ``mcp_write_gate`` records the caller under a key derived from the
# tool name and the exact arguments; the server derives the same key, consumes
# the record and takes the caller from it. The main session is recorded as
# 'human'. No record means the hook did not run: the server then refuses every
# write tool (fail closed). A ``caller`` argument is never trusted: the hook
# denies it and the server refuses it.
#
# Residual trust: an agent with a shell could forge a record by writing the
# directory directly. The directory lives outside every home and repo
# (``~/.claude/academy/callers``; ``$ACADEMY_CALLER_DIR`` overrides it).

CALLER_TTL_SECONDS = 600.0
RESERVED_ARGS = ("caller",)
#: claim_caller's answer when live records for one call name different callers
AMBIGUOUS = "?ambiguous"


def caller_dir():
    """The handshake directory (``$ACADEMY_CALLER_DIR`` or ``~/.claude/academy/callers``)."""
    return os.environ.get("ACADEMY_CALLER_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude", "academy", "callers")


def call_key(tool, args):
    """A stable hex key for one call: the bare tool name and its canonical arguments."""
    blob = json.dumps({"tool": tool, "args": args if isinstance(args, dict) else {}},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:40]


def record_caller(tool, args, caller, folder=None, now=None):
    """Record that ``caller`` ('human' or 'plugin:agent') is about to call ``tool``.

    Returns the record's path. Called by the mcp_write_gate hook only.
    """
    folder = folder or caller_dir()
    os.makedirs(folder, exist_ok=True)
    now = time.time() if now is None else now
    name = "%s-%020d-%d-%s.json" % (call_key(tool, args), int(now * 1e6), os.getpid(),
                                    os.urandom(4).hex())
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"caller": caller or HUMAN, "tool": tool, "created": now}, fh)
    return path


def _prune_callers(folder, now):
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for n in names:
        p = os.path.join(folder, n)
        try:
            if now - os.path.getmtime(p) > CALLER_TTL_SECONDS:
                os.remove(p)
        except OSError:
            pass


def claim_caller(tool, args, folder=None, now=None):
    """Consume the hook's record for this call; return the caller string or None.

    ``None`` means no live record: the hook did not run (or ran more than
    CALLER_TTL_SECONDS ago). When live records for the same call disagree
    (two identical calls from different callers in flight), nothing is consumed
    and ``AMBIGUOUS`` is returned; the server refuses writes until one expires.
    """
    folder = folder or caller_dir()
    now = time.time() if now is None else now
    _prune_callers(folder, now)
    key = call_key(tool, args)
    try:
        names = sorted(n for n in os.listdir(folder) if n.startswith(key + "-"))
    except OSError:
        return None
    live = []
    for n in names:
        p = os.path.join(folder, n)
        try:
            with open(p, "r", encoding="utf-8") as fh:
                rec = json.load(fh)
        except (OSError, ValueError):
            continue
        who = rec.get("caller") if isinstance(rec, dict) else None
        if isinstance(who, str) and who:
            live.append((p, who))
    if not live:
        return None
    if len(set(w for _, w in live)) > 1:
        return AMBIGUOUS
    for p, who in live:              # oldest first; the first one we can remove is ours
        try:
            os.remove(p)
            return who
        except OSError:
            continue                 # a concurrent server consumed it
    return None
