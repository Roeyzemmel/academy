"""academy_common -- the shared plumbing every academy plugin codes against.

This module is the single implementation of the contracts in
``docs/protocol.md``, ``docs/packet-template.md`` and ``docs/config.md``.
It is stdlib-only (Windows Python 3.10 via ``py``) and self-contained: it is
vendored verbatim into each role plugin as ``scripts/_academy.py`` and a test
fails if a copy drifts, so it must never import anything relative to itself.

Contents
--------
Homes and config
    find_home(path)                 the directory holding ``.claude/academy.json``
    load_config(home)               that file, validated, with defaults and ``_home``
    validate_config(config)         list of problems (empty when valid)
    load_workspace(path=None)       ``workspace.json`` (the instance map)
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

import datetime as _dt
import hashlib
import json
import os
import re
import sys
import tempfile
import time

SCHEMA_VERSION = 1

# ----------------------------------------------------------------------------
# Vocabulary
# ----------------------------------------------------------------------------

ROLES = ("author", "researcher", "expert", "scientist")
#: plugin names that ship agents (the base plugin has agents but no instances)
PLUGINS = ("academy",) + ROLES
MODELS = ("fable", "opus", "sonnet", "haiku")
HUMAN = "human"

RE_INSTANCE = re.compile(r"^(author|researcher|expert|scientist)@[a-z0-9][a-z0-9-]*$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_TICKET_ID = re.compile(r"^T-\d{4,}$")
RE_PACKET_ID = re.compile(r"^P-\d{4,}$")

CONFIG_REL = os.path.join(".claude", "academy.json")

def _same_file(a, b):
    return bool(a and b) and os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def env_home_name(instance):
    """The environment variable that overrides an instance's home: ``author@bi`` ->
    ``ACADEMY_HOME_AUTHOR_BI`` (scripts/bootstrap.py of the workspace sets them all)."""
    return "ACADEMY_HOME_" + re.sub(r"[^A-Za-z0-9]+", "_", instance).strip("_").upper()


class AcademyError(Exception):
    """Base class for every error raised here."""


class ConfigError(AcademyError):
    """A missing or invalid academy.json / workspace.json."""


class FrontmatterError(AcademyError):
    """Frontmatter outside the supported YAML subset."""


class LockTimeout(AcademyError):
    """board/.ids/lock could not be acquired in time."""


def today():
    """Today's date as 'YYYY-MM-DD' (local time), the only date format used."""
    return _dt.date.today().isoformat()


# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------

def _norm(path):
    """Absolute, normalised, forward-slash path; lower-cased on Windows for comparison."""
    p = os.path.normpath(os.path.abspath(str(path))).replace("\\", "/")
    return p.lower() if os.name == "nt" else p


def _rel_to(root, path):
    """``path`` relative to ``root`` with '/' separators, or None if outside it."""
    try:
        rel = os.path.relpath(os.path.abspath(str(path)), os.path.abspath(str(root)))
    except ValueError:              # different drives on Windows
        return None
    rel = rel.replace("\\", "/")
    if rel == ".":
        return ""
    if rel == ".." or rel.startswith("../"):
        return None
    return rel


def repo_root():
    """The academy repo root.

    ``ACADEMY_ROOT`` wins. Otherwise it is three levels above this file, which
    holds both for ``academy/lib/academy_common.py`` and for a vendored copy at
    ``<plugin>/scripts/_academy.py``; symlinks (``~/.claude/skills/<name>``) are
    resolved first.
    """
    env = os.environ.get("ACADEMY_ROOT")
    if env:
        return os.path.abspath(env)
    here = os.path.realpath(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


def find_home(path):
    """The nearest directory at or above ``path`` that contains ``.claude/academy.json``.

    ``path`` may be a file or a directory, and need not exist. The user's own home
    directory is never a home (``~/.claude`` is Claude Code's global config).
    Returns an absolute path, or None.
    """
    if not path:
        return None
    cur = os.path.abspath(str(path))
    if not os.path.isdir(cur):
        cur = os.path.dirname(cur)
    user_home = _norm(os.path.expanduser("~"))
    while True:
        if _norm(cur) != user_home and os.path.isfile(os.path.join(cur, CONFIG_REL)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


# ----------------------------------------------------------------------------
# Config and workspace
# ----------------------------------------------------------------------------

#: defaults merged under every config (see docs/config.md)
CONFIG_DEFAULTS = {
    "budget": {"itemsPerRun": 3, "serial": True, "orchestratorModel": "sonnet",
               "maxModel": "fable", "ticketDefault": {"runs": 1, "max_model": "sonnet"}},
    "gate": {"commit": "normal", "build": True, "baseline": None, "branches": {}},
    "paths": {},
}

#: path keys each role must define in ``paths`` (docs/config.md)
REQUIRED_PATHS = {
    "author": ("tex", "bib", "drafts", "agenda", "roadmap", "records", "views"),
    "researcher": ("objects", "proofs", "journal", "audits", "records", "views"),
    "expert": ("index", "cards", "ledgers", "reviews", "hot", "cache", "views"),
    "scientist": ("package", "experiments", "results", "queue", "records", "views"),
}

REGISTRY_PROFILES = ("paper", "s1", "lab", "none")
ENV_KINDS = ("wsl", "local", "ssh")
POLICY_KEYS = ("probe", "test", "run")
COMMIT_MODES = ("strict", "normal", "off")


def _deep_merge(base, over):
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except OSError as exc:
        raise ConfigError("cannot read %s: %s" % (path, exc))
    except ValueError as exc:
        raise ConfigError("invalid JSON in %s: %s" % (path, exc))


def validate_config(config):
    """Return a list of human-readable problems with a loaded academy.json (empty if valid)."""
    probs = []
    if not isinstance(config, dict):
        return ["config is not a JSON object"]
    if config.get("schema") != SCHEMA_VERSION:
        probs.append("schema must be %d" % SCHEMA_VERSION)
    role = config.get("role")
    if role not in ROLES:
        probs.append("role must be one of %s" % ", ".join(ROLES))
    inst = config.get("instance")
    if not isinstance(inst, str) or not RE_INSTANCE.match(inst):
        probs.append("instance must look like '<role>@<name>' (lower-case, digits, '-')")
    elif role in ROLES and inst.split("@", 1)[0] != role:
        probs.append("instance %r does not start with role %r" % (inst, role))
    doms = config.get("domains")
    if not (isinstance(doms, list) and doms and all(isinstance(d, str) and d for d in doms)):
        probs.append("domains must be a non-empty list of pack names")
    reg = config.get("registry")
    if not isinstance(reg, dict) or reg.get("profile") not in REGISTRY_PROFILES:
        probs.append("registry.profile must be one of %s" % ", ".join(REGISTRY_PROFILES))
    elif reg.get("profile") != "none" and not config.get("ns"):
        probs.append("ns is required when registry.profile is not 'none'")
    paths = config.get("paths")
    if not isinstance(paths, dict):
        probs.append("paths must be an object")
    elif role in REQUIRED_PATHS:
        for key in REQUIRED_PATHS[role]:
            if key not in paths:
                probs.append("paths.%s is required for role %s" % (key, role))
    budget = config.get("budget", {})
    n = budget.get("itemsPerRun") if isinstance(budget, dict) else None
    if not (isinstance(n, int) and 1 <= n <= 3):
        probs.append("budget.itemsPerRun must be an integer 1..3")
    for key in ("orchestratorModel", "maxModel"):
        if isinstance(budget, dict) and budget.get(key) not in MODELS:
            probs.append("budget.%s must be one of %s" % (key, ", ".join(MODELS)))
    gate = config.get("gate", {})
    if isinstance(gate, dict):
        if gate.get("commit") not in COMMIT_MODES:
            probs.append("gate.commit must be one of %s" % ", ".join(COMMIT_MODES))
        for br, over in (gate.get("branches") or {}).items():
            if not isinstance(over, dict) or over.get("commit", "normal") not in COMMIT_MODES:
                probs.append("gate.branches.%s.commit must be one of %s"
                             % (br, ", ".join(COMMIT_MODES)))
    if role in ROLES and not isinstance(config.get(role), dict):
        probs.append("a '%s' block is required for role %s" % (role, role))
    if role == "scientist" and isinstance(config.get("scientist"), dict):
        sci = config["scientist"]
        envs = sci.get("envs")
        if not isinstance(envs, dict) or not envs:
            probs.append("scientist.envs must name at least one profile")
            envs = {}
        for name, prof in envs.items():
            kind = prof.get("kind") if isinstance(prof, dict) else None
            if kind not in ENV_KINDS:
                probs.append("scientist.envs.%s.kind must be one of %s"
                             % (name, ", ".join(ENV_KINDS)))
            elif kind == "ssh" and not prof.get("host"):
                probs.append("scientist.envs.%s: kind ssh needs host" % name)
            elif kind == "wsl" and not prof.get("distro"):
                probs.append("scientist.envs.%s: kind wsl needs distro" % name)
        pol = sci.get("policy")
        if not isinstance(pol, dict):
            probs.append("scientist.policy must map probe/test/run to profiles")
        else:
            for key in POLICY_KEYS:
                if pol.get(key) not in envs:
                    probs.append("scientist.policy.%s must name a profile in scientist.envs"
                                 % key)
    return probs


def load_config(home):
    """Load ``<home>/.claude/academy.json`` with defaults merged in.

    Adds ``_home`` (absolute path of the home, '/' separators). Raises ConfigError
    if the file is missing, not JSON, or fails ``validate_config``.
    """
    if not home:
        raise ConfigError("no academy home")
    path = os.path.join(str(home), CONFIG_REL)
    raw = _read_json(path)
    if not isinstance(raw, dict):
        raise ConfigError("%s is not a JSON object" % path)
    cfg = _deep_merge(CONFIG_DEFAULTS, raw)
    probs = validate_config(cfg)
    if probs:
        raise ConfigError("%s: %s" % (path, "; ".join(probs)))
    cfg["_home"] = os.path.abspath(str(home)).replace("\\", "/")
    return cfg


def gate_mode(config, branch=None):
    """The effective commit-gate mode for ``branch`` ('strict'|'normal'|'off')."""
    gate = config.get("gate") or {}
    mode = gate.get("commit", "normal")
    if branch:
        over = (gate.get("branches") or {}).get(branch)
        if isinstance(over, dict) and "commit" in over:
            mode = over["commit"]
    return mode


def load_workspace(path=None):
    """Load workspace.json: ``{"instances": {...}, "board": ..., "human": {...}}``.

    Lookup order: ``path``; ``$ACADEMY_WORKSPACE``; ``<repo_root()>/workspace.json``;
    ``<repo_root()>/../workspace.json`` (the academy checked out inside the workspace).
    ``$ACADEMY_BOARD`` and ``$ACADEMY_HOME_<INSTANCE>`` override the file's ``board`` and
    instance homes, but only for the file ``$ACADEMY_ENV_WORKSPACE`` names (the one the
    workspace bootstrap derived them from), never for a fixture. Raises ConfigError if none is readable or the file is malformed.
    """
    candidates = [path, os.environ.get("ACADEMY_WORKSPACE"),
                  os.path.join(repo_root(), "workspace.json"),
                  os.path.join(repo_root(), os.pardir, "workspace.json")]
    chosen = next((c for c in candidates if c and os.path.isfile(c)), None)
    if not chosen:
        raise ConfigError("workspace.json not found")
    ws = _read_json(chosen)
    if not isinstance(ws, dict) or not isinstance(ws.get("instances"), dict):
        raise ConfigError("%s: 'instances' object missing" % chosen)
    if _same_file(chosen, os.environ.get("ACADEMY_ENV_WORKSPACE")):
        if os.environ.get("ACADEMY_BOARD"):
            ws["board"] = os.environ["ACADEMY_BOARD"]
        for name, inst in ws["instances"].items():
            if isinstance(inst, dict) and os.environ.get(env_home_name(name)):
                inst["home"] = os.environ[env_home_name(name)]
    if not isinstance(ws.get("board"), str) or not ws["board"]:
        raise ConfigError("%s: 'board' path missing" % chosen)
    for name, inst in ws["instances"].items():
        if not RE_INSTANCE.match(name):
            raise ConfigError("%s: bad instance name %r" % (chosen, name))
        if not isinstance(inst, dict) or inst.get("role") != name.split("@", 1)[0]:
            raise ConfigError("%s: instance %r: role must match its name" % (chosen, name))
        if not inst.get("home") or not inst.get("domains"):
            raise ConfigError("%s: instance %r needs home and domains" % (chosen, name))
    ws.setdefault("human", {"name": "human"})
    ws["_path"] = os.path.abspath(chosen).replace("\\", "/")
    return ws


def instance_for_home(workspace, home):
    """The instance name whose ``home`` is ``home``, or None."""
    target = _norm(home)
    for name, inst in workspace.get("instances", {}).items():
        if _norm(inst.get("home", "")) == target:
            return name
    return None


def _glob_regex(pattern):
    """Translate a path glob ('**' any segments, '*' within a segment, '?' one char)."""
    out, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif ch == "*":
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(ch))
            i += 1
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE if os.name == "nt" else 0)


def _match_path(rel, pattern):
    pattern = pattern.replace("\\", "/").strip("/")
    if pattern in ("", "."):
        return True
    if any(c in pattern for c in "*?"):
        return _glob_regex(pattern).match(rel) is not None
    a, b = (rel.lower(), pattern.lower()) if os.name == "nt" else (rel, pattern)
    return a == b or a.startswith(b + "/")


def path_in_role(path, config, role):
    """Does ``path`` belong to ``role`` in this home?

    ``role`` is either
      * a role name (``config['role']``): True iff ``path`` lies inside the home;
        a different role name gives False, since a home has exactly one role;
      * a key of ``config['paths']`` (e.g. ``"tex"``, ``"views"``): True iff the
        path, taken relative to the home, matches one of that key's patterns.
        A pattern without glob characters matches the file itself or anything
        under it as a directory; ``*`` stays within a segment, ``**`` spans them.
    Relative ``path`` values are taken relative to the home. Unknown keys give False.
    """
    home = config.get("_home")
    if not home or not path:
        return False
    full = path if os.path.isabs(str(path)) else os.path.join(home, str(path))
    rel = _rel_to(home, full)
    if rel is None:
        return False
    if role in ROLES:
        return role == config.get("role")
    pats = (config.get("paths") or {}).get(role)
    if pats is None:
        return False
    if isinstance(pats, str):
        pats = [pats]
    return any(_match_path(rel, p) for p in pats)


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
    agent is the human (Roey's main session).
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



# ----------------------------------------------------------------------------
# Frontmatter: the simple YAML subset
# ----------------------------------------------------------------------------
#
# Supported (docs/protocol.md, "Frontmatter subset"):
#   key: scalar                 str | int | float | true/false | null (~, null, empty)
#   key: [a, "b, c", 3]         inline list of scalars
#   key: {a: 1, b: x}           inline one-level map (read only; written as a block)
#   key:                        block map, one level, 2-space indented scalars
#     sub: scalar
#   key:                        block list of scalars (read only; written inline)
#     - a
# Keys match [A-Za-z_][A-Za-z0-9_-]*. Comments (' #...' outside quotes) are dropped.

RE_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?$")
RE_INT = re.compile(r"^-?\d+$")
RE_FLOAT = re.compile(r"^-?\d+\.\d+$")
_SPECIAL_START = set("[]{}\"'!&*?|>%@`#,-")


def _strip_comment(s):
    out, q, i = [], None, 0
    while i < len(s):
        ch = s[i]
        if q:
            out.append(ch)
            if ch == "\\" and q == '"' and i + 1 < len(s):
                out.append(s[i + 1])
                i += 1
            elif ch == q:
                q = None
        elif ch in "\"'" and (i == 0 or s[i - 1] in " \t[{,:"):
            q = ch                      # an apostrophe inside a word is not a quote
            out.append(ch)
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _parse_scalar(s):
    s = s.strip()
    if s in ("", "~", "null", "Null", "NULL"):
        return None
    if s.startswith('"'):
        try:
            val, end = json.JSONDecoder().raw_decode(s)
        except ValueError:
            raise FrontmatterError("bad double-quoted string: %s" % s)
        if s[end:].strip():
            raise FrontmatterError("trailing text after string: %s" % s)
        return val
    if s.startswith("'"):
        if len(s) < 2 or not s.endswith("'"):
            raise FrontmatterError("bad single-quoted string: %s" % s)
        return s[1:-1].replace("''", "'")
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if RE_INT.match(s):
        return int(s)
    if RE_FLOAT.match(s):
        return float(s)
    return s


def _split_flow(s):
    """Split the inside of [..] / {..} on top-level commas, respecting quotes."""
    parts, cur, q, depth, i = [], [], None, 0, 0
    while i < len(s):
        ch = s[i]
        if q:
            cur.append(ch)
            if ch == "\\" and q == '"' and i + 1 < len(s):
                cur.append(s[i + 1])
                i += 1
            elif ch == q:
                q = None
        elif ch in "\"'" and not "".join(cur).strip():
            q = ch                      # a quote opens only at the start of an item
            cur.append(ch)
        elif ch in "[{":
            depth += 1
            cur.append(ch)
        elif ch in "]}":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    if q:
        raise FrontmatterError("unterminated quote in: %s" % s)
    tail = "".join(cur)
    if tail.strip() or parts:
        parts.append(tail)
    return [p.strip() for p in parts]


def _parse_value(s):
    s = s.strip()
    if s.startswith("["):
        if not s.endswith("]"):
            raise FrontmatterError("unterminated list: %s" % s)
        items = _split_flow(s[1:-1])
        if any(p.startswith(("[", "{")) for p in items):
            raise FrontmatterError("nested collections are not supported: %s" % s)
        return [_parse_scalar(p) for p in items if p != ""]
    if s.startswith("{"):
        if not s.endswith("}"):
            raise FrontmatterError("unterminated map: %s" % s)
        out = {}
        for p in _split_flow(s[1:-1]):
            if not p:
                continue
            k, sep, v = p.partition(":")
            if not sep or not RE_KEY.match(k.strip() + ":"):
                raise FrontmatterError("bad map entry %r in: %s" % (p, s))
            if v.strip().startswith(("[", "{")):
                raise FrontmatterError("nested collections are not supported: %s" % s)
            out[k.strip()] = _parse_scalar(v)
        return out
    return _parse_scalar(s)


def _parse_yaml(lines):
    meta, i = {}, 0
    while i < len(lines):
        raw = lines[i]
        line = _strip_comment(raw)
        if not line.strip():
            i += 1
            continue
        if line[0] in " \t":
            raise FrontmatterError("unexpected indentation: %r" % raw)
        m = RE_KEY.match(line)
        if not m:
            raise FrontmatterError("not a 'key: value' line: %r" % raw)
        key, rest = m.group(1), (m.group(2) or "").strip()
        if key in meta:
            raise FrontmatterError("duplicate key %r" % key)
        i += 1
        if rest:
            meta[key] = _parse_value(rest)
            continue
        block = []
        while i < len(lines):
            nxt = _strip_comment(lines[i])
            if not nxt.strip():
                i += 1
                continue
            if nxt[0] not in " \t":
                break
            block.append(nxt.strip())
            i += 1
        if not block:
            meta[key] = None
        elif all(b.startswith("- ") or b == "-" for b in block):
            meta[key] = [_parse_scalar(b[1:]) for b in block]
        else:
            sub = {}
            for b in block:
                mm = RE_KEY.match(b)
                if not mm:
                    raise FrontmatterError("bad entry under %r: %r" % (key, b))
                sk, sv = mm.group(1), (mm.group(2) or "")
                if sv.strip().startswith(("[", "{")):
                    raise FrontmatterError("nested collections are not supported under %r"
                                           % key)
                if sk in sub:
                    raise FrontmatterError("duplicate key %r under %r" % (sk, key))
                sub[sk] = _parse_scalar(sv)
            meta[key] = sub
    return meta


def read_frontmatter(text):
    """Split a Markdown file into ``(meta, body)``.

    The frontmatter is the block between a first line ``---`` and the next line
    ``---``. CRLF input is accepted and normalised to LF. Without frontmatter the
    result is ``({}, text)``. ``body`` is everything after the closing ``---`` line,
    exactly (so ``write_frontmatter(*read_frontmatter(t)) == t`` for canonical files).
    Raises FrontmatterError for YAML outside the subset described above.
    """
    text = text.replace("\r\n", "\n")
    if text.startswith("\ufeff"):
        text = text[1:]
    if not (text.startswith("---\n") or text == "---"):
        return {}, text
    lines = text.split("\n")
    for j in range(1, len(lines)):
        if lines[j].rstrip() == "---":
            meta = _parse_yaml(lines[1:j])
            return meta, "\n".join(lines[j + 1:])
    raise FrontmatterError("frontmatter is not closed by a '---' line")


def _needs_quotes(s, in_flow):
    if s == "":
        return True
    if "'" in s or '"' in s:
        return True
    if s != s.strip() or "\n" in s or "\r" in s or "\t" in s:
        return True
    if s[0] in _SPECIAL_START:
        return True
    if ": " in s or s.endswith(":") or " #" in s:
        return True
    if s in ("~", "null", "Null", "NULL", "true", "True", "false", "False"):
        return True
    if RE_INT.match(s) or RE_FLOAT.match(s):
        return True
    if in_flow and any(c in s for c in ",[]{}"):
        return True
    return False


def _fmt_scalar(v, in_flow=False):
    if v is None:
        return "null" if in_flow else ""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if not isinstance(v, str):
        raise FrontmatterError("unsupported value type %s" % type(v).__name__)
    return json.dumps(v, ensure_ascii=False) if _needs_quotes(v, in_flow) else v


def write_frontmatter(meta, body=""):
    """Render ``meta`` (insertion order kept) and ``body`` as a Markdown file with LF.

    Scalars are written bare unless they would read back differently, then as a
    JSON double-quoted string. Lists are written inline (``[a, b]``), dicts as a
    one-level block map indented by two spaces, None as an empty value.
    Nested collections raise FrontmatterError.
    """
    out = ["---"]
    for key, val in meta.items():
        if not RE_KEY.match(str(key) + ":"):
            raise FrontmatterError("bad key %r" % key)
        if isinstance(val, (list, tuple)):
            if any(isinstance(x, (list, tuple, dict)) for x in val):
                raise FrontmatterError("nested collections are not supported (%s)" % key)
            out.append("%s: [%s]" % (key, ", ".join(_fmt_scalar(x, True) for x in val)))
        elif isinstance(val, dict):
            if not val:
                out.append("%s: {}" % key)
                continue
            out.append("%s:" % key)
            for sk, sv in val.items():
                if not RE_KEY.match(str(sk) + ":"):
                    raise FrontmatterError("bad key %r under %r" % (sk, key))
                if isinstance(sv, (list, tuple, dict)):
                    raise FrontmatterError("nested collections are not supported (%s.%s)"
                                           % (key, sk))
                s = _fmt_scalar(sv)
                out.append(("  %s: %s" % (sk, s)) if s != "" else ("  %s:" % sk))
        else:
            s = _fmt_scalar(val)
            out.append(("%s: %s" % (key, s)) if s != "" else ("%s:" % key))
    out.append("---")
    return "\n".join(out) + "\n" + body.replace("\r\n", "\n")


# ----------------------------------------------------------------------------
# Files and ids
# ----------------------------------------------------------------------------

def atomic_write(path, text, newline="\n"):
    """Write ``text`` (UTF-8, no BOM) to ``path`` atomically.

    Line endings are normalised to LF and then written as ``newline`` ('\\n' for
    every academy file; '\\r\\n' only for a home file that is CRLF, e.g. BI's
    sections). The data goes to a temporary file in the same directory which then
    replaces ``path``; the replace is retried briefly because Windows refuses it
    while an editor or indexer holds the target open.
    """
    path = os.path.abspath(str(path))
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    data = text.replace("\r\n", "\n")
    if newline != "\n":
        data = data.replace("\n", newline)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".part", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        for attempt in range(20):
            try:
                os.replace(tmp, path)
                return path
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.05)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return path


ID_KINDS = {"ticket": "T", "packet": "P"}
IDS_DIR = ".ids"
LOCK_NAME = "lock"
LOCK_STALE_SECONDS = 30.0


class IdLock(object):
    """Exclusive lock on ``<board>/.ids/lock`` (O_CREAT|O_EXCL), a context manager.

    The lock file holds 'pid timestamp'. A lock older than LOCK_STALE_SECONDS is
    taken to belong to a crashed process and is broken. Raises LockTimeout after
    ``timeout`` seconds.
    """

    def __init__(self, board, timeout=10.0):
        self.path = os.path.join(str(board), IDS_DIR, LOCK_NAME)
        self.timeout = timeout

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
                    fh.write("%d %f\n" % (os.getpid(), time.time()))
                return self
            except FileExistsError:
                try:
                    age = time.time() - os.path.getmtime(self.path)
                    if age > LOCK_STALE_SECONDS:
                        os.remove(self.path)
                        continue
                except OSError:
                    continue
                if time.monotonic() > deadline:
                    raise LockTimeout("could not lock %s" % self.path)
                time.sleep(0.05)

    def __exit__(self, *exc):
        try:
            os.remove(self.path)
        except OSError:
            pass
        return False


def _max_id_on_disk(board, prefix):
    rx = re.compile(r"^%s-(\d+)(?:-.*)?\.md$" % prefix)
    best = 0
    for dirpath, dirnames, filenames in os.walk(str(board)):
        dirnames[:] = [d for d in dirnames if d not in (".git", IDS_DIR)]
        for f in filenames:
            m = rx.match(f)
            if m:
                best = max(best, int(m.group(1)))
    return best


def format_id(prefix, n):
    """'T', 7 -> 'T-0007' (at least four digits, never truncated)."""
    return "%s-%04d" % (prefix, n)


def allocate_id(board, kind):
    """Allocate the next id of ``kind`` ('ticket'|'packet', or 'T'|'P') on ``board``.

    Under the lock: read ``<board>/.ids/next-<kind>`` (the next free number, one
    integer and a newline), take the maximum of it and one past the highest id
    already on disk (so a lost or stale counter can never reissue an id), write
    back that number plus one, and return the formatted id ('T-0001').
    """
    kind = {"T": "ticket", "P": "packet"}.get(kind, kind)
    if kind not in ID_KINDS:
        raise AcademyError("unknown id kind %r" % kind)
    prefix = ID_KINDS[kind]
    counter = os.path.join(str(board), IDS_DIR, "next-" + kind)
    with IdLock(board):
        n = 1
        try:
            with open(counter, "r", encoding="utf-8") as fh:
                n = int(fh.read().strip() or "1")
        except (OSError, ValueError):
            n = 1
        n = max(n, _max_id_on_disk(board, prefix) + 1)
        atomic_write(counter, "%d\n" % (n + 1))
    return format_id(prefix, n)


# ----------------------------------------------------------------------------
# Tickets
# ----------------------------------------------------------------------------

TICKET_STATUSES = ("open", "accepted", "in-progress", "delivered", "closed",
                   "rejected", "cancelled", "blocked")
TERMINAL = ("closed", "rejected", "cancelled")
TICKET_KINDS = ("verify", "cite", "lookup", "prove", "review-experiment", "generalize",
                "experiment", "test", "code", "notation", "referee", "build", "figure",
                "decision", "question", "research", "note", "other")
PRIORITIES = ("high", "normal", "low")

#: (from, to) -> parties who may make the transition; 'human' may make any, always.
#: Mirrors permissions.json "tickets.transitions" (a test keeps them equal).
TRANSITIONS = {
    ("open", "accepted"): ("receiver",),
    ("open", "rejected"): ("receiver",),
    ("open", "blocked"): ("receiver",),
    ("open", "cancelled"): ("sender",),
    ("accepted", "in-progress"): ("receiver",),
    ("accepted", "blocked"): ("receiver",),
    ("accepted", "rejected"): ("receiver",),
    ("accepted", "cancelled"): ("sender",),
    ("in-progress", "delivered"): ("receiver",),
    ("in-progress", "blocked"): ("receiver",),
    ("in-progress", "cancelled"): ("sender",),
    ("blocked", "accepted"): ("receiver",),
    ("blocked", "in-progress"): ("receiver",),
    ("blocked", "cancelled"): ("sender",),
    ("delivered", "closed"): ("sender",),
    ("delivered", "in-progress"): ("sender",),
}

#: ticket frontmatter fields by owner (mirrors permissions.json "tickets.fields")
TICKET_FIELDS = {
    "system": ("id", "from", "created", "updated"),
    "human_only": ("to",),
    "sender": ("title", "kind", "ask", "deliverable", "refs", "priority", "budget",
               "parent", "blocks", "agenda", "domain", "final_to"),
    "receiver": ("status", "result", "waiting_on", "packets"),
}
TICKET_KEY_ORDER = ("id", "title", "kind", "from", "to", "status", "priority", "ask",
                    "deliverable", "refs", "agenda", "domain", "parent", "final_to", "blocks",
                    "waiting_on", "budget", "result", "packets", "created", "updated")
REQUIRED_TICKET_FIELDS = ("id", "title", "kind", "from", "to", "status", "ask",
                          "deliverable", "priority", "budget", "created", "updated")
THREAD_HEADING = "## Thread"
RE_THREAD_LINE = re.compile(r"^- (\d{4}-\d{2}-\d{2}) ([^\s:]+): (.*)$")
RE_WHO = re.compile(r"^(human|(author|researcher|expert|scientist)@[a-z0-9][a-z0-9-]*"
                    r"(/[a-z0-9][a-z0-9-]*)?)$")


def is_party(name):
    """True for a valid 'from'/'to' value: an instance name or 'human'."""
    return name == HUMAN or (isinstance(name, str) and RE_INSTANCE.match(name) is not None)


#: the ticket chain (docs/protocol.md section 5); permissions.json tickets.edges overrides
CHAIN_DEFAULT = ("author", "expert", "researcher", "scientist")
#: the directional relay of a crossing: (from role, middle role, "down" or "up") -> agent
RELAYS = {("author", "expert", "down"): "research-intake",
          ("researcher", "expert", "up"): "paper-liaison",
          ("expert", "researcher", "down"): "experiment-spec",
          ("scientist", "researcher", "up"): "lit-request"}
#: the agent name of a role skill running in the main session inside a home
MAIN_AGENT = "main"


def role_of(party, workspace=None):
    """The role of an instance name ('author@bi' -> 'author'); None for 'human'."""
    if not party or party == HUMAN:
        return None
    inst = (workspace or {}).get("instances", {}).get(party)
    if inst and inst.get("role"):
        return inst["role"]
    m = RE_INSTANCE.match(str(party))
    return m.group(1) if m else None


def ticket_edges(perms):
    """permissions.json tickets.edges with defaults: chain, maxHops, liaisons, exempt."""
    e = ((perms or {}).get("tickets") or {}).get("edges") or {}
    return {"chain": list(e.get("chain") or CHAIN_DEFAULT),
            "maxHops": int(e.get("maxHops", 3)),
            "liaisons": dict(e.get("liaisons") or {}),
            "exempt": list(e.get("exempt") or [])}


def relay_depth(board, parent):
    """How many consecutive ancestors, starting at ``parent``, carry ``final_to``.

    Only relay links count toward the hop limit; an ordinary ``parent`` (a review
    ticket filed against the ticket that commissioned the experiment) stops the count.
    """
    n, seen, tid = 0, set(), parent
    while tid and tid not in seen:
        seen.add(tid)
        path = find_ticket(board, tid)
        if not path:
            break
        with open(path, "r", encoding="utf-8") as fh:
            meta, _ = read_frontmatter(fh.read())
        if not meta.get("final_to"):
            break
        n += 1
        tid = meta.get("parent")
    return n


def relay_return_ready(meta, status_of, workspace=None):
    """Whether a blocked relay parent is ready for its return leg (protocol section 5.2).

    True when ``meta`` is ``blocked``, carries a ``final_to`` beyond its receiver's own
    role, waits on ticket ids only (no ``human``), and every one of them is
    ``delivered`` or terminal. ``status_of`` maps a ticket id to its status (None when
    the ticket is not found). A ``research`` ticket to an Expert with no ``final_to``
    (or ``final_to`` the Expert) reads as ``final_to: researcher``, as research-intake
    reads it.
    """
    if meta.get("status") != "blocked":
        return False
    ft = meta.get("final_to")
    final = (ft if ft in ROLES else role_of(ft, workspace)) if ft else None
    receiver = role_of(meta.get("to"), workspace)
    if meta.get("kind") == "research" and receiver == "expert" and \
            final in (None, "expert"):
        final = "researcher"
    if final is None or final == receiver:
        return False
    waits = [str(w) for w in (meta.get("waiting_on") or [])]
    if not waits or not all(RE_TICKET_ID.match(w) for w in waits):
        return False
    return all(status_of(w) in ("delivered",) + TERMINAL for w in waits)


def ticket_edge_allowed(frm, to, agent, perms, workspace=None, final_to=None, depth=0,
                        clerical=False):
    """Whether ``agent`` of instance ``frm`` may file a ticket to ``to``.

    Rules (docs/protocol.md section 5): 'human' at either end is allowed; a clerical
    ticket or an exempt agent is allowed; the same role is allowed; otherwise the roles
    must be adjacent in the chain and ``agent`` a liaison of that direction.
    ``final_to`` (a role or instance) must lie beyond ``to`` as seen from ``frm``, and
    ``depth`` (relay_depth of the parent) + 1 may not exceed maxHops.
    Returns ``(allowed, reason)``.
    """
    edges = ticket_edges(perms)
    chain = edges["chain"]
    rf, rt = role_of(frm, workspace), role_of(to, workspace)
    if final_to:
        rF = final_to if final_to in chain else role_of(final_to, workspace)
        if rF not in chain:
            return False, "final_to must be a chain role or an instance, not %r" % final_to
        if rt is None:
            return False, "final_to needs a receiver with a role, not 'human'"
        if rF != rt and rf in chain and rt in chain:
            i, j, k = chain.index(rf), chain.index(rt), chain.index(rF)
            if not (min(i, k) < j < max(i, k)):
                return False, ("final_to %s does not lie beyond %s as seen from %s"
                               % (rF, rt, rf))
        if depth + 1 > edges["maxHops"]:
            return False, "the relay chain would exceed %d hops" % edges["maxHops"]
    if frm == HUMAN or to == HUMAN:
        return True, "human"
    if clerical or agent in edges["exempt"]:
        return True, "clerical"
    if rf == rt:
        return True, "same role"
    if rf not in chain or rt not in chain:
        return False, "unknown role for %r or %r" % (frm, to)
    i, j = chain.index(rf), chain.index(rt)
    if abs(i - j) != 1:
        step = chain[i + (1 if j > i else -1)]
        relay = RELAYS.get((rf, step, "down" if j > i else "up"), "its relay")
        return False, ("%s may not file to %s: file to the %s with final_to %s; "
                       "%s relays it" % (rf, rt, step, rt, relay))
    names = edges["liaisons"].get("%s->%s" % (rf, rt), [])
    who = agent or MAIN_AGENT
    if who in names:
        return True, "liaison"
    return False, ("%s is not a liaison for %s->%s (liaisons: %s)"
                   % (who, rf, rt, ", ".join(names) or "none"))


def parties(meta, instance):
    """The parties ``instance`` plays on a ticket: a subset of {'sender','receiver'}.

    ``instance`` is the caller's instance name, or 'human' for Roey (who is also
    allowed everything regardless).
    """
    out = set()
    if meta.get("from") == instance:
        out.add("sender")
    if meta.get("to") == instance:
        out.add("receiver")
    return out


def can_transition(old, new, party_set, human=False):
    """Whether a caller playing ``party_set`` may move a ticket from ``old`` to ``new``.

    The human may make any change between two valid statuses, including
    re-opening a terminal ticket (-> 'open'). Returns (allowed, reason).
    """
    if old not in TICKET_STATUSES or new not in TICKET_STATUSES:
        return False, "unknown status %r -> %r" % (old, new)
    if old == new:
        return True, "no change"
    if human:
        return True, "human"
    who = TRANSITIONS.get((old, new))
    if who is None:
        return False, "%s -> %s is not a transition" % (old, new)
    if set(who) & set(party_set):
        return True, "allowed"
    return False, "%s -> %s is made by the %s" % (old, new, " or ".join(who))


def editable_fields(party_set, human=False):
    """The frontmatter fields a caller may change directly (status goes via can_transition)."""
    if human:
        return set(TICKET_KEY_ORDER)
    out = set()
    for p in party_set:
        if p in ("sender", "receiver"):
            out.update(TICKET_FIELDS[p])
    return out


def validate_ticket(meta, body=None):
    """Return a list of problems with a ticket (empty when valid). See docs/protocol.md."""
    probs = []
    for f in REQUIRED_TICKET_FIELDS:
        if meta.get(f) in (None, ""):
            probs.append("missing %s" % f)
    known = set(TICKET_KEY_ORDER)
    for k in meta:
        if k not in known:
            probs.append("unknown field %s" % k)
    if meta.get("id") and not RE_TICKET_ID.match(str(meta["id"])):
        probs.append("id must look like T-0001")
    if meta.get("kind") and meta["kind"] not in TICKET_KINDS:
        probs.append("kind %r is not one of %s" % (meta["kind"], ", ".join(TICKET_KINDS)))
    for f in ("from", "to"):
        if meta.get(f) and not is_party(meta[f]):
            probs.append("%s must be an instance name or 'human'" % f)
    st = meta.get("status")
    if st and st not in TICKET_STATUSES:
        probs.append("status %r is not one of %s" % (st, ", ".join(TICKET_STATUSES)))
    if meta.get("priority") and meta["priority"] not in PRIORITIES:
        probs.append("priority must be one of %s" % ", ".join(PRIORITIES))
    for f in ("created", "updated"):
        if meta.get(f) and not RE_DATE.match(str(meta[f])):
            probs.append("%s must be YYYY-MM-DD" % f)
    for f in ("refs", "blocks", "waiting_on", "packets"):
        if meta.get(f) is not None and not isinstance(meta[f], list):
            probs.append("%s must be a list" % f)
    for f in ("blocks",):
        for t in meta.get(f) or []:
            if not RE_TICKET_ID.match(str(t)):
                probs.append("%s entry %r is not a ticket id" % (f, t))
    for p in meta.get("packets") or []:
        if not RE_PACKET_ID.match(str(p)):
            probs.append("packets entry %r is not a packet id" % p)
    if meta.get("parent") and not RE_TICKET_ID.match(str(meta["parent"])):
        probs.append("parent must be a ticket id")
    ft = meta.get("final_to")
    if ft and ft not in ROLES and not RE_INSTANCE.match(str(ft)):
        probs.append("final_to must be a role or an instance name, not %r" % ft)
    b = meta.get("budget")
    if b is not None:
        if not isinstance(b, dict):
            probs.append("budget must be a map {runs, max_model}")
        else:
            if not (isinstance(b.get("runs"), int) and b["runs"] >= 1):
                probs.append("budget.runs must be a positive integer")
            if b.get("max_model") not in MODELS:
                probs.append("budget.max_model must be one of %s" % ", ".join(MODELS))
    if st == "blocked" and not meta.get("waiting_on"):
        probs.append("a blocked ticket needs waiting_on")
    if st != "blocked" and meta.get("waiting_on"):
        probs.append("waiting_on must be empty unless status is blocked")
    if st in ("delivered", "closed") and not meta.get("result"):
        probs.append("a %s ticket needs result" % st)
    if body is not None:
        if THREAD_HEADING not in body.split("\n"):
            probs.append("missing '## Thread' section")
        else:
            for ln in thread_lines(body, raw=True):
                if not RE_THREAD_LINE.match(ln) and not ln.startswith("  "):
                    probs.append("malformed thread line: %r" % ln)
                    continue
                m = RE_THREAD_LINE.match(ln)
                if m and not RE_WHO.match(m.group(2)):
                    probs.append("bad speaker %r in thread" % m.group(2))
    return probs


def slugify(title, maxlen=40, default="ticket"):
    """Lower-case ASCII slug of ``title``: [a-z0-9-], at most ``maxlen`` chars."""
    s = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rstrip("-")
    return s or default


def ticket_filename(tid, title):
    """'T-0007', 'Check Lemma 4.2' -> 'T-0007-check-lemma-4-2.md' (never renamed later)."""
    return "%s-%s.md" % (tid, slugify(title))


def packet_filename(pid, title):
    """'P-0003', 'Verify lem:x' -> 'P-0003-verify-lem-x.md'."""
    return "%s-%s.md" % (pid, slugify(title, default="packet"))


def find_ticket(board, tid):
    """Path of the ticket file with id ``tid`` anywhere on the board, or None."""
    return _find_by_id(board, tid)


def find_packet(board, pid):
    """Path of the packet file with id ``pid`` (under board/packets/), or None."""
    return _find_by_id(os.path.join(str(board), "packets"), pid)


def _find_by_id(root, xid):
    rx = re.compile(r"^%s(?:-.*)?\.md$" % re.escape(xid))
    for dirpath, dirnames, filenames in os.walk(str(root)):
        dirnames[:] = [d for d in dirnames if d not in (".git", IDS_DIR)]
        for f in filenames:
            if rx.match(f):
                return os.path.join(dirpath, f)
    return None


def thread_lines(body, raw=False):
    """The entries of the body's '## Thread' section (the last section of a ticket).

    With ``raw`` the non-blank lines are returned as they are (continuation lines
    included); otherwise a list of ``(date, who, text)`` with continuation lines
    (indented two spaces) joined to their entry by a newline.
    """
    lines = body.replace("\r\n", "\n").split("\n")
    try:
        start = lines.index(THREAD_HEADING) + 1
    except ValueError:
        return []
    section = []
    for ln in lines[start:]:
        if ln.startswith("## "):
            break
        if ln.strip():
            section.append(ln.rstrip())
    if raw:
        return section
    out = []
    for ln in section:
        m = RE_THREAD_LINE.match(ln)
        if m:
            out.append([m.group(1), m.group(2), m.group(3)])
        elif ln.startswith("  ") and out:
            out[-1][2] += "\n" + ln[2:]
    return [tuple(x) for x in out]


def format_who(instance, agent=""):
    """Thread speaker: 'human', '<instance>' or '<instance>/<bare agent>'."""
    if not instance or instance == HUMAN:
        return HUMAN
    return "%s/%s" % (instance, agent) if agent else instance


def append_thread(body, who, text, date=None):
    """Return ``body`` with one entry appended to its '## Thread' section.

    Creates the section at the end if it is missing. Multi-line ``text`` is written
    as continuation lines indented by two spaces. Existing lines are never touched.
    """
    if not RE_WHO.match(who):
        raise AcademyError("bad thread speaker %r" % who)
    date = date or today()
    parts = str(text).strip().replace("\r\n", "\n").split("\n")
    entry = ["- %s %s: %s" % (date, who, parts[0])] + ["  " + p for p in parts[1:]]
    body = body.replace("\r\n", "\n")
    lines = body.split("\n")
    if THREAD_HEADING not in lines:
        base = body.rstrip("\n")
        return (base + "\n\n" if base else "") + THREAD_HEADING + "\n\n" + \
            "\n".join(entry) + "\n"
    start = lines.index(THREAD_HEADING) + 1
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    last = end
    while last > start and not lines[last - 1].strip():
        last -= 1
    if last == start:                      # empty section: keep one blank line
        new = lines[:start] + [""] + entry + lines[end:] if end < len(lines) else \
            lines[:start] + [""] + entry + [""]
    else:
        new = lines[:last] + entry + lines[last:]
    out = "\n".join(new)
    return out if out.endswith("\n") else out + "\n"


def thread_is_append_only(old_body, new_body):
    """True when ``new_body``'s thread starts with every line of ``old_body``'s thread."""
    old, new = thread_lines(old_body, raw=True), thread_lines(new_body, raw=True)
    return new[:len(old)] == old


def new_ticket(meta, ask_detail=""):
    """Render a new ticket file (frontmatter in canonical order + the standard body)."""
    ordered = {k: meta[k] for k in TICKET_KEY_ORDER if k in meta}
    for k in meta:
        if k not in ordered:
            ordered[k] = meta[k]
    body = "\n## Ask\n\n%s\n\n## Result\n\n\n%s\n\n" % (
        ask_detail.strip() or ordered.get("ask", ""), THREAD_HEADING)
    return write_frontmatter(ordered, body)


# ----------------------------------------------------------------------------
# Packets (docs/packet-template.md)
# ----------------------------------------------------------------------------

PACKET_KEY_ORDER = ("packet", "title", "instance", "kind", "by", "ticket", "agenda",
                    "subject", "status_before", "status_proposed", "state", "created",
                    "decided")
REQUIRED_PACKET_FIELDS = ("packet", "title", "instance", "kind", "by", "state", "created")
PACKET_KINDS = ("verification", "citation", "referee", "experiment-report",
                "experiment-review", "generalization", "proof", "notation", "agenda",
                "migration", "handover", "usage", "failure", "other")
PACKET_STATES = ("open", "decided", "withdrawn")
CLAIM_STATUSES = ("open", "conjectured", "sketch", "supported", "proved-modulo",
                  "proved", "refuted", "refuted-as-stated")
PACKET_SECTIONS = ("## Summary", "## Produced", "## Established vs assumed",
                   "## Evidence", "## Decisions needed", "## Machine notes",
                   "## Decision")
RE_DECISION_Q = re.compile(r"^### D(\d+)\. (.+)$")
RE_OPTION = re.compile(r"^- \(([a-d])\) (.+)$")
RE_DECISION_LINE = re.compile(
    r"^- D(\d+): (\([a-d]\)|other|ack) \| (\d{4}-\d{2}-\d{2}) \| ([^\s|]+)(?: \| (.*))?$")


def _sections(body):
    """Map '## Heading' -> list of lines under it (up to the next '## ')."""
    out, cur = {}, None
    for ln in body.replace("\r\n", "\n").split("\n"):
        if ln.startswith("## "):
            cur = ln.rstrip()
            out.setdefault(cur, [])
        elif cur is not None:
            out[cur].append(ln)
    return out


def packet_decisions(body):
    """The decisions asked in '## Decisions needed': {k: {"question", "options", "recommendation"}}.

    ``options`` maps letter -> text. An informational packet ('None.') gives {}.
    """
    lines = _sections(body).get("## Decisions needed", [])
    out, cur = {}, None
    for ln in lines:
        m = RE_DECISION_Q.match(ln.strip())
        if m:
            cur = int(m.group(1))
            out[cur] = {"question": m.group(2).strip(), "options": {},
                        "recommendation": None}
            continue
        if cur is None:
            continue
        mo = RE_OPTION.match(ln.strip())
        if mo:
            out[cur]["options"][mo.group(1)] = mo.group(2).strip()
        elif ln.strip().startswith("- Recommendation:"):
            out[cur]["recommendation"] = ln.strip()[len("- Recommendation:"):].strip()
    return out


def packet_answers(body):
    """The answers in '## Decision': {k: (choice, date, speaker, note)}; last line wins."""
    out = {}
    for ln in _sections(body).get("## Decision", []):
        m = RE_DECISION_LINE.match(ln.rstrip())
        if m:
            out[int(m.group(1))] = (m.group(2), m.group(3), m.group(4), m.group(5) or "")
    return out


def validate_packet(meta, body):
    """Return a list of problems with a packet (empty when valid)."""
    probs = []
    for f in REQUIRED_PACKET_FIELDS:
        if meta.get(f) in (None, ""):
            probs.append("missing %s" % f)
    for k in meta:
        if k not in PACKET_KEY_ORDER:
            probs.append("unknown field %s" % k)
    if meta.get("packet") and not RE_PACKET_ID.match(str(meta["packet"])):
        probs.append("packet must look like P-0001")
    if meta.get("instance") and not RE_INSTANCE.match(str(meta["instance"])):
        probs.append("instance must be an instance name")
    if meta.get("kind") and meta["kind"] not in PACKET_KINDS:
        probs.append("kind %r is not one of %s" % (meta["kind"], ", ".join(PACKET_KINDS)))
    if meta.get("state") and meta["state"] not in PACKET_STATES:
        probs.append("state must be one of %s" % ", ".join(PACKET_STATES))
    if meta.get("by") and not RE_WHO.match(str(meta["by"])):
        probs.append("by must be a speaker")
    if meta.get("ticket") and not RE_TICKET_ID.match(str(meta["ticket"])):
        probs.append("ticket must be a ticket id")
    if meta.get("subject") is not None and not isinstance(meta["subject"], list):
        probs.append("subject must be a list")
    for f in ("status_before", "status_proposed"):
        if meta.get(f) and meta[f] not in CLAIM_STATUSES:
            probs.append("%s %r is not a registry status" % (f, meta[f]))
    heads = [ln.rstrip() for ln in body.replace("\r\n", "\n").split("\n")
             if ln.startswith("## ")]
    pos = []
    for h in PACKET_SECTIONS:
        if h not in heads:
            probs.append("missing section %r" % h)
        else:
            pos.append(heads.index(h))
    if len(pos) == len(PACKET_SECTIONS):
        if pos != sorted(pos):
            probs.append("sections out of order")
        extra = heads[pos[3] + 1:pos[4]]
        other = [h for h in heads if h not in PACKET_SECTIONS and h not in extra]
        if other:
            probs.append("extra sections only between Evidence and Decisions needed: %s"
                         % ", ".join(other))
    secs = _sections(body)
    summary = [ln for ln in secs.get("## Summary", []) if ln.strip()]
    if len(summary) > 3:
        probs.append("## Summary has more than three lines")
    asked = packet_decisions(body)
    needed = [ln.strip() for ln in secs.get("## Decisions needed", []) if ln.strip()]
    if not asked and needed != ["None."]:
        probs.append("## Decisions needed must be 'None.' or D1.. decisions")
    if asked and sorted(asked) != list(range(1, len(asked) + 1)):
        probs.append("decisions must be numbered D1..Dn without gaps")
    for k, d in asked.items():
        if not 2 <= len(d["options"]) <= 4:
            probs.append("D%d needs 2-4 options" % k)
        if not d["recommendation"]:
            probs.append("D%d needs a Recommendation line" % k)
    for ln in secs.get("## Decision", []):
        if ln.strip() and not RE_DECISION_LINE.match(ln.rstrip()):
            probs.append("malformed decision line: %r" % ln)
    return probs


def record_decision(body, k, choice, note="", who=HUMAN, date=None):
    """Append one answer line to '## Decision' and return the new body.

    ``choice`` is an option letter ('a'..'d'), 'other' (``note`` required) or 'ack'
    (``k`` must be 0). The caller then checks ``packet_answers`` against
    ``packet_decisions`` to decide whether the packet becomes 'decided'.
    """
    date = date or today()
    if choice in ("other", "ack"):
        token = choice
    elif re.match(r"^[a-d]$", str(choice)):
        token = "(%s)" % choice
    else:
        raise AcademyError("choice must be a-d, 'other' or 'ack'")
    if choice == "other" and not note.strip():
        raise AcademyError("an 'other' answer needs its text")
    if (choice == "ack") != (k == 0):
        raise AcademyError("'ack' is exactly the D0 answer")
    line = "- D%d: %s | %s | %s" % (k, token, date, who)
    if note.strip():
        line += " | " + " ".join(note.split())
    lines = body.replace("\r\n", "\n").rstrip("\n").split("\n")
    if "## Decision" not in lines:
        raise AcademyError("packet has no '## Decision' section")
    start = lines.index("## Decision") + 1
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    last = end
    while last > start and not lines[last - 1].strip():
        last -= 1
    if last == start:
        new = lines[:start] + [""] + [line] + lines[end:]
    else:
        new = lines[:last] + [line] + lines[last:]
    return "\n".join(new) + "\n"


def packet_is_decided(body):
    """True once every asked decision has an answer (or D0 is acknowledged)."""
    asked, answers = packet_decisions(body), packet_answers(body)
    if not asked:
        return 0 in answers
    return all(k in answers for k in asked)


# ----------------------------------------------------------------------------
# Hook I/O (Claude Code conventions)
# ----------------------------------------------------------------------------
#
# A hook reads one JSON event on stdin and exits 0. To speak it prints one JSON
# object on stdout:
#   PreToolUse   {"hookSpecificOutput": {"hookEventName": "PreToolUse",
#                  "permissionDecision": "allow"|"deny"|"ask",
#                  "permissionDecisionReason": "..."}}
#   PostToolUse / SessionStart / UserPromptSubmit / SubagentStart
#                {"hookSpecificOutput": {"hookEventName": ..., "additionalContext": "..."}}
#   Stop / SubagentStop / PostToolUse (block)   {"decision": "block", "reason": "..."}
# Silence (no output, exit 0) means "no opinion". A gate never fails a tool call
# because of its own bug: malformed events read as {}.

def read_event(stream=None):
    """Parse the hook event from ``stream`` (default stdin). Never raises; bad input -> {}.

    Claude Code writes the event as UTF-8. A text stream's own decoding is bypassed
    (its ``buffer`` is read): on Windows, Python decodes a piped stdin with the ANSI
    codepage, which mangles non-ASCII arguments (T-0070). A leading BOM is dropped.
    """
    stream = stream or sys.stdin
    try:
        raw = getattr(stream, "buffer", stream).read()
    except Exception:
        return {}
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig", "replace")
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def event_cwd(event):
    """The event's ``cwd`` if it is a directory, else the process cwd."""
    root = event.get("cwd") if isinstance(event, dict) else None
    return root if root and os.path.isdir(root) else os.getcwd()


def tool_name(event):
    """The event's ``tool_name`` or ''."""
    name = event.get("tool_name") if isinstance(event, dict) else None
    return name if isinstance(name, str) else ""


def mcp_tool(event, server="academy"):
    """For ``mcp__<server>__<tool>`` return '<tool>', else ''.

    Plugin-provided servers may appear as ``mcp__plugin_<plugin>_<server>__<tool>``;
    any server segment ending in ``server`` is accepted.
    """
    name = tool_name(event)
    m = re.match(r"^mcp__([A-Za-z0-9_-]+)__(.+)$", name)
    if not m:
        return ""
    srv = m.group(1)
    if srv == server or srv.endswith("_" + server):
        return m.group(2)
    return ""


def tool_input(event):
    ti = event.get("tool_input") if isinstance(event, dict) else None
    return ti if isinstance(ti, dict) else {}


def edited_path(event):
    """The file an Edit/Write/MultiEdit/NotebookEdit event touches, or None."""
    ti = tool_input(event)
    path = ti.get("file_path") or ti.get("notebook_path")
    return path if isinstance(path, str) and path else None


def shell_command(event):
    """The command of a Bash or PowerShell event, or ''."""
    cmd = tool_input(event).get("command")
    return cmd if isinstance(cmd, str) else ""


def is_git_commit(command):
    """True when some segment of a shell command (bash or PowerShell) runs git commit.

    Errs towards True (``git log --grep commit`` matches): a false positive costs a
    checker run, a false negative lets a commit through ungated. PowerShell's ``;``
    and newlines separate segments as in bash; ``git.exe`` and ``& git`` count.
    """
    return re.search(r"\bgit(?:\.exe)?\b[^;&|\n]*\bcommit\b", command or "") is not None


# ----------------------------------------------------------------------------
# Shell commands: which repository a ``git commit`` runs in
# ----------------------------------------------------------------------------
# One parser for every commit gate (author, scientist). The command is split into
# segments (``;``, newlines, ``&&``, ``||``, ``|``) with quotes respected, and walked
# in order while tracking the directory:
#   - ``cd``/``chdir``/``pushd``/``popd`` (bash) and ``Set-Location``/``sl``/
#     ``Push-Location``/``Pop-Location`` (PowerShell) move the tracked directory;
#   - ``git -C <dir>`` (repeatable) and ``--work-tree``/``--git-dir`` name the repo
#     of that one git call;
#   - Git Bash drive paths (``/c/Work``) resolve to ``C:/Work`` on Windows;
#   - ``bash -c "..."`` and ``powershell -Command "..."`` are parsed recursively;
#   - bash heredocs and PowerShell here-strings are data, not commands.

SHELL_CD = {"cd", "chdir", "set-location", "sl"}
SHELL_PUSHD = {"pushd", "push-location"}
SHELL_POPD = {"popd", "pop-location"}
SHELL_PREFIX_WORDS = {"command", "exec", "time", "nohup", "env", "&", "."}
GIT_OPTS_WITH_ARG = {"-c", "--namespace", "--super-prefix", "--config-env",
                     "--git-dir", "--work-tree", "--exec-path"}
SHELLS_C = {"bash": "-c", "sh": "-c", "bash.exe": "-c", "sh.exe": "-c"}
SHELLS_PS = {"powershell", "powershell.exe", "pwsh", "pwsh.exe"}
RE_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
RE_GITBASH_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")
RE_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


class ShellParseFailure(AcademyError):
    """The command could not be tokenised (e.g. an unbalanced quote)."""


def _skip_heredocs(command):
    """Blank out bash heredoc bodies (they are data, not commands)."""
    out, pending = [], []
    for line in command.split("\n"):
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            out.append("")
            continue
        out.append(line)
        pending.extend(m.group(2) for m in RE_HEREDOC.finditer(line))
    return "\n".join(out)


def split_segments(command):
    """Split a shell command into segments of tokens, honouring quotes.

    Returns a list of token lists. Single quotes are literal; double quotes allow
    ``\\"`` (bash) and a backtick escape (PowerShell). Outside quotes a backslash
    escapes only a space, a quote, a backslash or a separator character, so a
    Windows path such as ``C:\\Work\\Math`` survives. PowerShell here-strings
    (``@'`` ... ``'@``) become one token. A lone ``&`` at the start of a segment
    is PowerShell's call operator and is dropped; elsewhere it separates.
    Raises ShellParseFailure on an unbalanced quote or here-string.
    """
    command = _skip_heredocs(command or "")
    segments, tokens, cur = [], [], []
    state = {"have": False}
    i, n = 0, len(command)

    def end_token():
        if state["have"]:
            tokens.append("".join(cur))
        del cur[:]
        state["have"] = False

    def end_segment():
        end_token()
        if tokens:
            segments.append(list(tokens))
        del tokens[:]

    while i < n:
        ch = command[i]
        two = command[i:i + 2]
        if two in ("@'", '@"') and command[i + 2:i + 3] in ("\n", "\r"):
            close = "\n" + two[1] + "@"
            j = command.find(close, i + 2)
            if j < 0:
                raise ShellParseFailure("unterminated here-string")
            cur.append(command[i + 3:j])
            state["have"] = True
            i = j + len(close)
            continue
        if ch == "'":
            j = command.find("'", i + 1)
            if j < 0:
                raise ShellParseFailure("unbalanced single quote")
            cur.append(command[i + 1:j])
            state["have"] = True
            i = j + 1
            continue
        if ch == '"':
            j = i + 1
            buf = []
            while j < n and command[j] != '"':
                if command[j] in "\\`" and j + 1 < n and command[j + 1] in '"\\`$':
                    buf.append(command[j + 1])
                    j += 2
                    continue
                buf.append(command[j])
                j += 1
            if j >= n:
                raise ShellParseFailure("unbalanced double quote")
            cur.append("".join(buf))
            state["have"] = True
            i = j + 1
            continue
        if ch == "\\" and i + 1 < n and command[i + 1] in " \t'\"\\;&|":
            cur.append(command[i + 1])
            state["have"] = True
            i += 2
            continue
        if two in ("&&", "||"):
            end_segment()
            i += 2
            continue
        if ch in ";|\n\r":
            end_segment()
            i += 1
            continue
        if ch == "&":
            end_token()
            if not tokens:            # PowerShell call operator: `& git commit`
                i += 1
                continue
            end_segment()             # bash background
            i += 1
            continue
        if ch in " \t":
            end_token()
            i += 1
            continue
        if ch in "()" and not state["have"]:
            end_token()               # subshell / grouping parentheses
            i += 1
            continue
        if ch == ")":
            end_token()
            i += 1
            continue
        cur.append(ch)
        state["have"] = True
        i += 1
    end_segment()
    return segments


def resolve_dir(base, path):
    """``path`` as the shell would resolve it from ``base`` (Windows-aware).

    ``~``/``$HOME`` expand; on Windows a Git Bash drive path ``/c/Work`` becomes
    ``C:/Work`` (the Bash tool is Git Bash, so this is how agents name the lab).
    """
    p = (path or "").strip()
    if not p:
        return base
    if p == "~" or p.startswith("~/") or p.startswith("~\\"):
        p = os.path.expanduser("~") + p[1:]
    for var in ("$HOME", "$env:USERPROFILE", "$env:HOME", "${HOME}"):
        if p.startswith(var):
            p = os.path.expanduser("~") + p[len(var):]
    if os.name == "nt":
        m = RE_GITBASH_DRIVE.match(p.replace("\\", "/"))
        if m:                                   # Git Bash: /c/Work -> C:/Work
            p = m.group(1).upper() + ":/" + p.replace("\\", "/")[3:]
    if os.path.isabs(p) or re.match(r"^[A-Za-z]:", p):
        return os.path.normpath(p)
    return os.path.normpath(os.path.join(base, p))


def _cd_target(args):
    """The directory argument of a cd-like command, skipping PowerShell switches."""
    k = 0
    while k < len(args):
        low = args[k].lower()
        if low in ("-path", "-literalpath"):
            return args[k + 1] if k + 1 < len(args) else None
        if low.startswith("-") and low != "-":   # bash -L/-P, PowerShell switches
            k += 1
            continue
        return args[k]
    return None


def _strip_prefix(tokens):
    k = 0
    while k < len(tokens) and (tokens[k].lower() in SHELL_PREFIX_WORDS
                               or RE_ASSIGN.match(tokens[k])):
        k += 1
    return tokens[k:]


def _is_git(token):
    base = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return base in ("git", "git.exe")


def git_commit_dir(tokens, cwd):
    """For a ``git ... commit`` token list, the repo directory; else None."""
    if not tokens or not _is_git(tokens[0]):
        return None
    repo, work_tree, git_dir = cwd, None, None
    k = 1
    while k < len(tokens):
        t = tokens[k]
        low = t.lower()
        if t == "-C":
            if k + 1 >= len(tokens):
                return None
            repo = resolve_dir(repo, tokens[k + 1])
            k += 2
            continue
        if low.startswith("--work-tree="):
            work_tree = t.split("=", 1)[1]
            k += 1
            continue
        if low.startswith("--git-dir="):
            git_dir = t.split("=", 1)[1]
            k += 1
            continue
        if low in GIT_OPTS_WITH_ARG:
            if low == "--work-tree" and k + 1 < len(tokens):
                work_tree = tokens[k + 1]
            if low == "--git-dir" and k + 1 < len(tokens):
                git_dir = tokens[k + 1]
            k += 2
            continue
        if t.startswith("-"):
            k += 1
            continue
        if low != "commit":
            return None
        if work_tree:
            return resolve_dir(repo, work_tree)
        if git_dir:
            gd = resolve_dir(repo, git_dir)
            return os.path.dirname(gd) if os.path.basename(gd).lower() == ".git" else repo
        return repo
    return None


def commit_targets(command, cwd, _depth=0):
    """Every directory a ``git commit`` in ``command`` commits in, in order.

    Raises ShellParseFailure when the command cannot be tokenised; a gate then falls
    back to ``[cwd] if is_git_commit(command) else []``.
    """
    out = []
    here = cwd
    stack = []
    for seg in split_segments(command):
        toks = _strip_prefix(seg)
        if not toks:
            continue
        head = toks[0].lower()
        if head in SHELL_CD:
            tgt = _cd_target(toks[1:])
            if tgt is None and head == "cd" and len(toks) == 1:
                here = os.path.expanduser("~")      # bash: cd alone goes home
            elif tgt and tgt != "-":
                here = resolve_dir(here, tgt)
            continue
        if head in SHELL_PUSHD:
            tgt = _cd_target(toks[1:])
            if tgt:
                stack.append(here)
                here = resolve_dir(here, tgt)
            continue
        if head in SHELL_POPD:
            if stack:
                here = stack.pop()
            continue
        if _depth < 3 and head in SHELLS_C and len(toks) >= 3 and toks[1] == SHELLS_C[head]:
            out.extend(commit_targets(toks[2], here, _depth + 1))
            continue
        if _depth < 3 and head in SHELLS_PS:
            for k, t in enumerate(toks[1:], 1):
                if t.lower() in ("-command", "-c") and k + 1 < len(toks):
                    out.extend(commit_targets(" ".join(toks[k + 1:]), here, _depth + 1))
                    break
            continue
        d = git_commit_dir(toks, here)
        if d:
            out.append(d)
    return out


def commit_targets_or_cwd(command, cwd):
    """``commit_targets``, falling back to ``[cwd]`` (or ``[]`` when the command is no
    commit at all) when it cannot be tokenised -- a gate errs towards checking."""
    try:
        return commit_targets(command, cwd)
    except ShellParseFailure:
        return [cwd] if is_git_commit(command) else []


def emit(payload, stream=None):
    """Write ``payload`` as one JSON object to ``stream`` (default stdout); return 0."""
    (stream or sys.stdout).write(json.dumps(payload, ensure_ascii=False))
    return 0


def emit_permission(decision, reason="", stream=None):
    """PreToolUse decision: 'allow', 'deny' or 'ask', with a reason shown to the model."""
    if decision not in ("allow", "deny", "ask"):
        raise ValueError("decision must be allow, deny or ask")
    block = {"hookEventName": "PreToolUse", "permissionDecision": decision}
    if reason:
        block["permissionDecisionReason"] = reason
    return emit({"hookSpecificOutput": block}, stream)


def emit_context(event_name, text, stream=None):
    """Add ``text`` to the model's context (PostToolUse, SessionStart, UserPromptSubmit...)."""
    return emit({"hookSpecificOutput": {"hookEventName": event_name,
                                        "additionalContext": text}}, stream)


def emit_block(reason, stream=None):
    """Block a Stop/SubagentStop (the agent must continue) or flag a PostToolUse result."""
    return emit({"decision": "block", "reason": reason}, stream)
