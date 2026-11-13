"""academy_common -- the shared plumbing every academy plugin codes against.

This module is the single implementation of the contracts in
``docs/protocol.md``, ``docs/packet-template.md`` and ``docs/config.md``.
It is stdlib-only (Windows Python 3.10 via ``py``) and self-contained: the
package is vendored verbatim into each plugin as ``scripts/_academy/`` and a test
fails if a copy drifts, so its modules import nothing but the standard library
and, relatively, each other.

It is a package of parts, imported in this order (a part imports only from earlier
ones); callers never import a part, they use ``ac.<name>`` on the package:

    _base       vocabulary, the error classes, paths
    _config     a home's academy.json, an Author home's tex conventions, path sets
    _workspace  workspace.json, the workspace's environment, model tiers, agent files
    _touched    the touch ledger: files a role wrote in another role's home
    _agents     agent identity, permissions, the caller handshake
    _files      the frontmatter subset, atomic writes, ids
    _tickets    ticket vocabulary, transitions, edges, blocking, validation, the thread
    _store      the board store, and the ticket rules that read other tickets through it
    _inbox      the inbox core
    _packets    packets
    _hooks      hook I/O and the shell-command parser

Every name of every part is a name of the package, and assigning one on the package
(``ac.load_workspace = fake``, ``mock.patch.object(ac, ...)``) rebinds it in every part
that holds it, so the functions of the library see the replacement, as they did when
the library was one module.

Contents
--------
Homes and config
    find_home(path)                 the directory holding ``.claude/academy.json``
    load_config(home)               that file, validated, with defaults and ``_home``
    validate_config(config)         list of problems (empty when valid)
    load_workspace(path=None)       ``workspace.json`` (the instance map), with defaults
    human_name / human_login / primary_models / derived_plugins   workspace.json keys
    registry_rule_set(profile)      ``registry.profile`` with old aliases resolved
    verify_checklist_path / author_provenance   academy.json keys with defaults
    author_status_levels / author_tex   an Author home's draft levels and tex conventions
    validate_author(block)          problems with an ``author`` block's tex keys
    path_in_role(path, config, role)  is ``path`` in the home / in a named path set
Agents and permissions
    agent_identity(event)           (namespace, bare_name) of the acting agent
    load_permissions(path=None)     ``academy/permissions.json``
    may_call(perms, tool, bare)     (allowed, reason) for an MCP write tool
    record_caller / claim_caller    the hook-to-server caller handshake
Frontmatter
    read_frontmatter(text)          (dict, body) for the simple YAML subset
    write_frontmatter(meta, body)   the inverse; canonical output
Files and ids
    atomic_write(path, text, newline='\\n')
    allocate_id(board, kind)        'T-0007' / 'P-0012', under board/.ids/lock
Tickets
    TICKET_STATUSES, TRANSITIONS, can_transition(...), validate_ticket(...)
    slugify, ticket_filename, find_ticket, thread_lines, append_thread,
    thread_is_append_only, new_ticket, parties, editable_fields
Inbox (one core, thin per-role wrappers)
    inbox_core.select(board, instance, limit, all=False, route=..., campaign=None)
    inbox_core.serial_checkpoint(meta) / check(board, tid), is_dead_route(meta)
    inbox_core.parser(desc) / run(args, instance, board, limit, route)   the shared CLI
    inbox_core.ship_checkpoint(...)  a finished --check runs the workspace's ship.py checkpoint
Touch ledger (cross-home writes the checkpoint ships)
    record_touch / claim_touches / drop_touches / touch_entries / is_cross_home
Packets
    PACKET_KEY_ORDER, validate_packet, packet_decisions, packet_answers,
    record_decision, packet_is_decided, packet_filename, find_packet
Hook I/O (Claude Code hook conventions)
    read_event, tool_name, mcp_tool, edited_path, shell_command, is_git_commit,
    emit, emit_permission, emit_context, emit_block
Shell commands (which repository a ``git commit`` runs in)
    split_segments(command)         token lists per segment; heredocs are data
    resolve_dir(base, path)         a cd target as the shell resolves it (Git Bash aware)
    commit_targets(command, cwd)    every directory a ``git commit`` commits in
    ShellParseFailure               an untokenisable command (unbalanced quote)
"""

import sys
import types

from . import (_base, _config, _workspace, _touched, _agents, _files, _tickets, _store,
               _inbox, _packets, _hooks)

#: the parts, in import order
_PARTS = (_base, _config, _workspace, _touched, _agents, _files, _tickets, _store,
          _inbox, _packets, _hooks)

#: names a part rebinds while running (a ``global`` statement): the package holds no
#: copy of them, it reads the owner's current value
_LIVE = {"WORKSPACE_TAGS": _workspace}


class _Library(types.ModuleType):
    """The package as one namespace over its parts (see the package docstring)."""

    def __getattr__(self, name):
        # reached only for a name the package does not hold itself
        owner = _LIVE.get(name)
        if owner is None:
            raise AttributeError("module %r has no attribute %r" % (self.__name__, name))
        return getattr(owner, name)

    def __setattr__(self, name, value):
        if name.startswith("__") or isinstance(value, types.ModuleType) and \
                getattr(value, "__package__", None) == self.__name__:
            return types.ModuleType.__setattr__(self, name, value)   # import machinery
        for part in _PARTS:
            if name in part.__dict__:
                setattr(part, name, value)
        if name not in _LIVE:
            types.ModuleType.__setattr__(self, name, value)

    def __dir__(self):
        return sorted(set(types.ModuleType.__dir__(self)) | set(_LIVE))


def _publish():
    names = globals()
    for part in _PARTS:
        for name, value in vars(part).items():
            if not name.startswith("__") and name not in _LIVE:
                names[name] = value
    sys.modules[__name__].__class__ = _Library


_publish()
