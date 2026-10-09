"""config_get / workspace_get: the instance map and a home's academy.json."""

import os

import academy_common as ac

from . import Tool, ToolError, obj, S


def _workspace(ctx, a):
    ws = dict(ctx.workspace)
    try:
        inst = ctx.instance
    except ToolError as exc:
        inst = None
        ws["caller_problem"] = str(exc)
    who = (ctx.agent_ns + ":" + ctx.agent if ctx.agent_ns else ctx.agent) \
        if ctx.agent else ac.HUMAN
    ws["caller"] = {"agent": who, "instance": inst, "verified": ctx.verified,
                    "home_instance": ctx.home_instance(), "cwd": ctx.cwd.replace("\\", "/")}
    return ws


def _config(ctx, a):
    name = a.get("instance")
    if name and name not in ctx.instances():
        raise ToolError("unknown instance %r (have: %s)"
                        % (name, ", ".join(sorted(ctx.instances()))))
    if not name and not ctx.is_human:
        name = ctx.instance             # the agent's own instance, resolved per call
    name = name or ctx.home_instance()
    if not name:
        raise ToolError("the server's cwd is in no academy home; name an instance "
                        "(instance=<one of %s>)" % ", ".join(sorted(ctx.instances())))
    home = ctx.home_of(name)
    path = os.path.join(home, ac.CONFIG_REL)
    if not os.path.isfile(path):
        return {"instance": name, "workspace_entry": ctx.instances()[name],
                "config": None,
                "note": "%s has no .claude/academy.json yet (not switched over)" % home}
    try:
        cfg = ac.load_config(home)
    except ac.ConfigError as exc:
        return {"instance": name, "config": None, "problems": str(exc)}
    return {"instance": name, "config": cfg}


TOOLS = [
    Tool("workspace_get", "The instance map (workspace.json) and who the caller is.",
         obj({}), _workspace),
    Tool("config_get", "An instance's .claude/academy.json with defaults merged "
         "(default: the instance of the caller's home).",
         obj({"instance": S}), _config),
]
