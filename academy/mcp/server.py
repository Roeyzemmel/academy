"""The academy MCP server: stdlib-only MCP over stdio (plan sections 5 and 6).

Transport: newline-delimited JSON-RPC 2.0 on stdin/stdout, UTF-8. Methods:
``initialize``, ``notifications/initialized`` (and any other notification,
ignored), ``ping``, ``tools/list``, ``tools/call``. Nothing is ever printed to
stdout except protocol messages; diagnostics go to stderr.

Run:  py <plugin>/mcp/server.py      (the plugin's .mcp.json does this)

Config: the workspace comes from ``academy_common.load_workspace`` (so
``$ACADEMY_WORKSPACE`` overrides it), the caller's instance per call
(``tools.Context.instance``: the ``instance`` argument, the call's ticket, the
server's cwd, the only instance of the agent's role). The caller comes from the record the ``mcp_write_gate``
hook leaves for each call (the caller handshake, see ``tools/__init__.py``).
"""

import json
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
for p in (os.path.join(PLUGIN, "lib"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import academy_common as ac  # noqa: E402
from tools import Context, ToolError, parse_caller  # noqa: E402
from tools import claims, config, domain, library, packets, queue, tickets  # noqa: E402

SERVER_NAME = "academy"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

MODULES = (claims, library, queue, tickets, packets, domain, config)

#: tools whose ``instance`` argument names the instance the caller acts for (it is
#: removed from the arguments before the handler runs)
ACTING_INSTANCE_TOOLS = ("tickets_create", "tickets_update", "tickets_get",
                         "claims_new", "claims_attach_evidence", "claims_propose_status",
                         "claims_set_status")
#: tools whose own ``instance`` argument is the instance acted for (kept for the handler)
TARGET_INSTANCE_TOOLS = ("packets_create", "config_get")


def all_tools():
    out = {}
    for mod in MODULES:
        for t in mod.TOOLS:
            if t.name in out:
                raise RuntimeError("duplicate tool %s" % t.name)
            out[t.name] = t
    return out


TOOLS = all_tools()


def _result(value, is_error=False):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False,
                                                           indent=1)
    return {"content": [{"type": "text", "text": text}], "isError": bool(is_error)}


def call_tool(name, args, cwd=None, caller=None):
    """Run one tool; returns the MCP ``tools/call`` result object.

    ``caller`` ('human' or 'plugin:agent') is for in-process callers only; over
    the wire it is always None and the caller is taken from the hook's record.
    """
    tool = TOOLS.get(name)
    if tool is None:
        return _result("unknown tool %r" % name, True)
    args = dict(args or {})
    reserved = [k for k in ac.RESERVED_ARGS if k in args]
    if reserved:
        return _result("refused: the argument %r is reserved; the caller is identified "
                       "by the mcp_write_gate hook, never by an argument" % reserved[0],
                       True)
    verified = True
    if caller is None:
        try:
            caller = ac.claim_caller(name, args)
        except OSError:
            caller = None
        if caller is None or caller == ac.AMBIGUOUS:
            if tool.write:
                why = ("identical calls from different callers are in flight; retry "
                       "shortly" if caller == ac.AMBIGUOUS else
                       "no mcp_write_gate record for this call (is the academy "
                       "plugin's PreToolUse hook loaded? If an argument contains a "
                       "non-ASCII character, retrying it in plain ASCII tells an "
                       "encoding fault apart: docs/protocol.md section 1)")
                return _result("refused: the caller of %s could not be identified: %s"
                               % (name, why), True)
            verified, caller = False, None
    ns, agent = parse_caller(caller)
    # the acting instance (fix 1, 2026-10-09): the server's cwd is not the agent's, so a
    # call may name the instance it acts for; on these tools ``instance`` means that
    requested = None
    if name in ACTING_INSTANCE_TOOLS:
        requested = args.pop("instance", None)
    elif name in TARGET_INSTANCE_TOOLS:
        requested = args.get("instance")
    ctx = Context(cwd=cwd, agent=agent, agent_ns=ns, verified=verified,
                  requested_instance=requested)
    try:
        if tool.write and agent:
            ok, why = ac.may_call(ctx.perms, name, agent)
            if not ok:
                raise ToolError("refused: %s" % why)
        return _result(tool.handler(ctx, args))
    except ToolError as exc:
        return _result(str(exc), True)
    except ac.AcademyError as exc:
        return _result("%s: %s" % (type(exc).__name__, exc), True)
    except Exception as exc:  # a server bug must not kill the session
        traceback.print_exc(file=sys.stderr)
        return _result("internal error in %s: %s: %s" % (name, type(exc).__name__, exc),
                       True)


def handle(msg):
    """Handle one decoded JSON-RPC message; return the response dict or None."""
    if not isinstance(msg, dict):
        return {"jsonrpc": "2.0", "id": None,
                "error": {"code": -32600, "message": "invalid request"}}
    method = msg.get("method")
    mid = msg.get("id")
    is_note = "id" not in msg
    params = msg.get("params") or {}
    if is_note:
        return None                      # notifications/initialized and friends
    try:
        if method == "initialize":
            want = params.get("protocolVersion")
            ver = want if want in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            res = {"protocolVersion": ver,
                   "capabilities": {"tools": {"listChanged": False}},
                   "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                   "instructions": "Academy board, registry, library and queue tools. "
                                   "Writes are gated by permissions.json."}
        elif method == "ping":
            res = {}
        elif method == "tools/list":
            res = {"tools": [t.listing() for t in TOOLS.values()]}
        elif method == "tools/call":
            res = call_tool(params.get("name"), params.get("arguments") or {})
        else:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32601, "message": "method not found: %s" % method}}
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32603, "message": str(exc)}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}


def serve(stdin=None, stdout=None):
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    for raw in stdin:
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            resp = {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": "parse error"}}
        else:
            if isinstance(msg, list):     # batch (older clients)
                resp = [r for r in (handle(m) for m in msg) if r is not None] or None
            else:
                resp = handle(msg)
        if resp is not None:
            stdout.write((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
            stdout.flush()


if __name__ == "__main__":
    serve()
