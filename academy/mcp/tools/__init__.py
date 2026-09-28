"""Tool modules of the academy MCP server (plan sections 5 and 6).

Each module exposes ``TOOLS``, a list of :class:`Tool`. A handler takes
``(ctx, args)`` and returns a JSON-serialisable value, or raises
:class:`ToolError` for a refusal the caller should read.

Caller identity. The server cannot see the calling agent. The PreToolUse hook
``mcp_write_gate`` records every call it lets through (the main session as
``human``, an agent by its namespaced type) in the caller handshake directory,
keyed by the tool name and the exact arguments; ``server.call_tool`` consumes
that record (``academy_common.claim_caller``). No record means the hook did not
run, and every write tool is then refused (reads proceed as the human). The
argument ``caller`` is reserved and refused: identity never comes from the
arguments. The server exposes the caller as ``ctx.agent`` (bare name, '' for the
human), ``ctx.agent_ns`` (its plugin namespace) and ``ctx.instance`` (the
instance of the home containing the server's cwd, or ``'human'``); an agent of a
role plugin running in another role's home has no instance there and is refused.
"""

import os

import academy_common as ac


class ToolError(Exception):
    """A refusal or failure reported to the caller as an ``isError`` result."""


class Tool(object):
    def __init__(self, name, description, schema, handler, write=False):
        self.name = name
        self.description = description
        self.schema = schema
        self.handler = handler
        self.write = write

    def listing(self):
        schema = dict(self.schema)
        schema.setdefault("type", "object")
        return {"name": self.name, "description": self.description, "inputSchema": schema}


def obj(props, required=()):
    """A JSON-schema object with ``props`` and ``required``."""
    out = {"type": "object", "properties": props, "additionalProperties": False}
    if required:
        out["required"] = list(required)
    return out


S = {"type": "string"}
I = {"type": "integer"}
B = {"type": "boolean"}
L = {"type": "array", "items": {"type": "string"}}


class Context(object):
    """Per-call view of the workspace, the caller and its instance."""

    def __init__(self, cwd=None, agent="", workspace=None, agent_ns="", verified=True):
        self.cwd = os.path.abspath(cwd or os.environ.get("ACADEMY_CWD") or os.getcwd())
        self.agent = agent or ""
        self.agent_ns = agent_ns or ""
        #: False when no mcp_write_gate record identified the caller (reads only)
        self.verified = verified
        self._ws = workspace
        self._perms = None

    # -- workspace ---------------------------------------------------------
    @property
    def workspace(self):
        if self._ws is None:
            self._ws = ac.load_workspace()
        return self._ws

    @property
    def academy_root(self):
        return os.path.dirname(self.workspace["_path"])

    @property
    def board(self):
        return self.workspace["board"]

    @property
    def perms(self):
        if self._perms is None:
            self._perms = ac.load_permissions()
        return self._perms

    def instances(self):
        return self.workspace.get("instances", {})

    def home_of(self, instance):
        inst = self.instances().get(instance)
        if not inst:
            raise ToolError("unknown instance %r" % instance)
        return inst["home"]

    def instance_by_ns(self, ns):
        for name, inst in self.instances().items():
            if inst.get("ns") == ns:
                return name
        return None

    def instances_by_role(self, role, domains=None):
        out = []
        for name, inst in self.instances().items():
            if inst.get("role") != role:
                continue
            if domains and not set(domains) & set(inst.get("domains", [])):
                continue
            out.append(name)
        return out

    def home_instance(self):
        """The instance whose home contains cwd (academy.json first, then the path)."""
        home = ac.find_home(self.cwd)
        if home:
            name = ac.instance_for_home(self.workspace, home)
            if name:
                return name
        best, best_len = None, -1
        cwd = ac._norm(self.cwd)
        for name, inst in self.instances().items():
            h = ac._norm(inst.get("home", ""))
            if h and (cwd == h or cwd.startswith(h + "/")) and len(h) > best_len:
                best, best_len = name, len(h)
        return best

    @property
    def is_human(self):
        return self.agent == ""

    def agent_plugin(self):
        """The plugin that ships the calling agent: its namespace, else the roster's."""
        if self.agent_ns in ac.PLUGINS:
            return self.agent_ns
        try:
            return ac.roster(self.perms).get(self.agent, "")
        except ac.AcademyError:
            return ""

    @property
    def instance(self):
        """'human' for the human; otherwise the home's instance (None outside every home).

        An agent of a role plugin acts only for an instance of that role: an
        ``expert:`` agent in an author home is refused rather than filing as the
        author. Base-plugin agents (``academy:``) act for whichever home they run in.
        """
        if self.is_human:
            return ac.HUMAN
        name = self.home_instance()
        if not name:
            return None
        plugin = self.agent_plugin()
        role = self.instances().get(name, {}).get("role")
        if plugin in ac.ROLES and role and plugin != role:
            raise ToolError("agent %s:%s belongs to the %s role but runs in the home of "
                            "%s (%s); it cannot act for that instance"
                            % (plugin, self.agent, plugin, name, role))
        return name

    @property
    def speaker(self):
        """Thread speaker for this caller."""
        if self.is_human:
            return ac.HUMAN
        inst = self.instance
        if not inst:
            raise ToolError("agent %r runs outside every academy home; it has no instance"
                            % self.agent)
        return ac.format_who(inst, self.agent)

    def my_domains(self):
        inst = self.instances().get(self.home_instance() or "", {})
        return inst.get("domains", [])


def parse_caller(value):
    """'author:math-writer' -> ('author', 'math-writer'); '', None, 'human' -> ('', '')."""
    if not value or not isinstance(value, str):
        return ("", "")
    ns, bare = ac.agent_identity({"agent_type": value})
    return ("", "") if bare in ("", ac.HUMAN) else (ns, bare)
