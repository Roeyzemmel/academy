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


def _models(ctx, role):
    """The workspace's tier map and the agents of the academy plugin and of ``role``,
    each resolved agent -> tier -> model (docs/config.md, "models"); agents read from
    this server's own checkout."""
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    agents = {}
    for name in ac.agent_files(repo):
        if name.split(":", 1)[0] in ("academy", role):
            try:
                r = ac.resolve_agent(name, ctx.workspace, repo)
            except ac.ConfigError as exc:
                r = {"problem": str(exc)}
            agents[name] = {k: r.get(k) for k in ("tier", "model", "launch", "override",
                                                  "problem") if k in r}
    return {"tiers": ac.model_tiers(ctx.workspace), "agents": agents}


def _config(ctx, a):
    name = a.get("instance")
    if name and name not in ctx.instances():
        raise ToolError("unknown instance %r (have: %s)"
                        % (name, ", ".join(sorted(ctx.instances()))))
    if not name and not ctx.is_human:
        try:
            name = ctx.instance         # the agent's own instance, resolved per call
        except ToolError as exc:
            # a read: an agent of a role with several instances (two researchers)
            # gets each candidate's config instead of a refusal
            cands = sorted(ctx.instances_by_role(ctx.agent_plugin()))
            if len(cands) < 2:
                raise
            return {"instance": None, "ambiguous": str(exc),
                    "candidates": {c: _one(ctx, c) for c in cands},
                    "note": "pass instance=<one of %s> for one config; writes still need "
                            "the instance" % ", ".join(cands)}
    name = name or ctx.home_instance()
    if not name:
        raise ToolError("the server's cwd is in no academy home; name an instance "
                        "(instance=<one of %s>)" % ", ".join(sorted(ctx.instances())))
    return _one(ctx, name)


def _one(ctx, name):
    home = ctx.home_of(name)
    models = _models(ctx, name.split("@", 1)[0])
    path = os.path.join(home, ac.CONFIG_REL)
    if not os.path.isfile(path):
        return {"instance": name, "workspace_entry": ctx.instances()[name],
                "config": None, "models": models,
                "note": "%s has no .claude/academy.json yet (not switched over)" % home}
    try:
        cfg = ac.load_config(home)
    except ac.ConfigError as exc:
        return {"instance": name, "config": None, "problems": str(exc), "models": models}
    return {"instance": name, "config": cfg, "models": models}


TOOLS = [
    Tool("workspace_get", "The instance map (workspace.json) and who the caller is.",
         obj({}), _workspace),
    Tool("config_get", "An instance's .claude/academy.json with defaults merged "
         "(default: the instance of the caller's home), and its role's agents resolved "
         "agent -> tier -> model for the workspace (models).",
         obj({"instance": S}), _config),
]
