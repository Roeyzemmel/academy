"""models.py -- agent -> tier -> model for a workspace (docs/config.md, "models").

Usage:

    py models.py tiers [--workspace PATH] [--json]
    py models.py agent <plugin:name | name> [--launch] [--workspace PATH] [--json]
    py models.py launch [<plugin:name | name> ...] [--tier TIER] [--workspace PATH]
    py models.py list [--plugin P] [--workspace PATH] [--json]
    py models.py launches [--workspace PATH]
    py models.py check [--workspace PATH]

Every academy agent file declares ``tier:`` (base, medium, large, max) and keeps a
``model:`` line, the Agent-tool alias of its tier in the academy's default map, which
Claude Code uses when nothing else is passed. workspace.json ``models.tiers`` maps the
tiers to models for this workspace, over that default.

- ``tiers``: the workspace's tier map.
- ``agent``: one agent's tier, the workspace's model for it, the Agent-tool ``model``
  value (``launch``) and whether it differs from the file's ``model:`` (``override``).
  ``--launch`` prints the launch value alone: the value a skill passes as the Agent
  tool's ``model`` when launching the agent (roster-rules.md, "Models").
- ``launch``: the launch values of the named agents, or of every agent of ``--tier``
  (both may be given), as one JSON object ``{"<plugin:name>": "<launch>"}``: what a
  workflow could pass down as ``args.models`` (a diagnostic; the workflows take
  ``launches`` from their skill, and a max-tier block resolves an agent with ``agent
  --launch`` only when no map was passed). Exit 2 on an unknown agent or tier, or when nothing is named.
- ``list``: every agent (or one plugin's) as a table.
- ``launches``: the JSON object ``{"plugin:name": launch, "tier:<tier>": launch}`` of the
  agents whose tier this workspace maps away from their file's ``model:``, and of those
  tiers themselves (``{}`` with the default map). A skill passes it as a workflow's
  ``args.models``; the workflow's ``launch()`` sets each such agent's ``model``, and the
  model of an agent with no academy file that the script launches by ``tier``
  (docs/workflows.md, "Models").
- ``check``: exit 1 when an agent file declares no valid tier or its ``model:`` is not
  its tier's default alias; otherwise exit 0, naming the agents that need the override
  in this workspace and the floor tiers whose model grants no grading authority.

Read-only. Standard library only.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
#: this checkout: its agent files are the ones resolved (not $ACADEMY_ROOT's)
REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

try:
    import academy_common as ac  # noqa: E402
except ImportError:  # vendored copy
    import _academy as ac  # noqa: E402


def load(path):
    """The workspace (``--workspace``, else the usual lookup), or None outside one: then
    the academy default map applies."""
    try:
        return ac.load_workspace(path)
    except ac.ConfigError:
        if path:
            raise
        return None


def rows(ws, plugin=None, repo=REPO):
    out, bad = [], []
    for agent in ac.agent_files(repo):
        if plugin and agent.split(":", 1)[0] != plugin:
            continue
        try:
            out.append(ac.resolve_agent(agent, ws or {}, repo))
        except ac.ConfigError as exc:
            bad.append(str(exc))
    return out, bad


def file_problems(repo=REPO):
    """Agent files whose tier is missing or whose ``model:`` is not its tier's default."""
    out = []
    for agent, path in ac.agent_files(repo).items():
        fm = ac.read_agent_frontmatter(path)
        tier = fm.get("tier")
        if tier not in ac.TIERS:
            out.append("%s: tier %r is not one of %s" % (agent, tier, ", ".join(ac.TIERS)))
            continue
        want = ac.launch_model(ac.DEFAULT_MODEL_TIERS[tier])
        if fm.get("model") != want:
            out.append("%s: model %r, but tier %s's default is %r"
                       % (agent, fm.get("model"), tier, want))
    return out


def launches(ws):
    """A workflow's ``args.models``: the launch value of every agent the workspace maps away
    from its file's ``model:``, and as ``tier:<tier>`` of every tier whose launch value is
    not its default's (the tiers of the agents a workflow launches with no academy file)."""
    found, _bad = rows(ws)
    out = {r["agent"]: r["launch"] for r in found if r["override"]}
    tiers = ac.model_tiers(ws or {})
    for tier in ac.TIERS:
        launch = ac.launch_model(tiers[tier])
        if launch != ac.launch_model(ac.DEFAULT_MODEL_TIERS[tier]):
            out["tier:" + tier] = launch
    return out


def grading_warnings(ws):
    """``ac.model_warnings``: floor tiers that give no grading authority."""
    return ac.model_warnings(ws)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("tiers", "agent", "launch", "list", "launches", "check"):
        p = sub.add_parser(name)
        p.add_argument("--workspace")
        p.add_argument("--json", action="store_true")
        if name == "agent":
            p.add_argument("agent")
            p.add_argument("--launch", action="store_true")
        if name == "list":
            p.add_argument("--plugin")
        if name == "launch":
            p.add_argument("agents", nargs="*")
            p.add_argument("--tier")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        ws = load(a.workspace)
    except ac.ConfigError as exc:
        print("models: %s" % exc, file=sys.stderr)
        return 2
    if a.cmd == "tiers":
        tiers = ac.model_tiers(ws or {})
        if a.json:
            print(json.dumps(tiers, indent=2))
        else:
            for t in ac.TIERS:
                print("%-7s %s" % (t, tiers[t]))
        return 0
    if a.cmd == "agent":
        try:
            r = ac.resolve_agent(a.agent, ws or {}, REPO)
        except ac.ConfigError as exc:
            print("models: %s" % exc, file=sys.stderr)
            return 2
        if a.launch:
            print(r["launch"])
        elif a.json:
            print(json.dumps(r, indent=2))
        else:
            print("%s  tier %s  model %s  launch %s%s"
                  % (r["agent"], r["tier"], r["model"], r["launch"],
                     "  (override: the file says %s)" % r["frontmatter"]
                     if r["override"] else ""))
        return 0
    if a.cmd == "launch":
        if not a.agents and not a.tier:
            print("models: launch needs agent names or --tier", file=sys.stderr)
            return 2
        if a.tier and a.tier not in ac.TIERS:
            print("models: tier %r is not one of %s" % (a.tier, ", ".join(ac.TIERS)),
                  file=sys.stderr)
            return 2
        out = {}
        try:
            for name in a.agents:
                r = ac.resolve_agent(name, ws or {}, REPO)
                out[r["agent"]] = r["launch"]
        except ac.ConfigError as exc:
            print("models: %s" % exc, file=sys.stderr)
            return 2
        if a.tier:
            found, _bad = rows(ws)
            out.update((r["agent"], r["launch"]) for r in found if r["tier"] == a.tier)
        print(json.dumps(out, sort_keys=True))
        return 0
    if a.cmd == "list":
        found, bad = rows(ws, a.plugin)
        if a.json:
            print(json.dumps({"tiers": ac.model_tiers(ws or {}), "agents": found,
                              "problems": bad}, indent=2))
        else:
            print("| agent | tier | model | launch | file says | override |")
            print("|---|---|---|---|---|---|")
            for r in found:
                print("| %s | %s | %s | %s | %s | %s |"
                      % (r["agent"], r["tier"], r["model"], r["launch"], r["frontmatter"],
                         "yes" if r["override"] else ""))
            for b in bad:
                print("PROBLEM: %s" % b)
        return 0
    if a.cmd == "launches":
        print(json.dumps(launches(ws), sort_keys=True))
        return 0
    # check
    problems = file_problems()
    found, _bad = rows(ws)
    over = [r for r in found if r["override"]]
    for p in problems:
        print("PROBLEM: %s" % p)
    for w in grading_warnings(ws):
        print("WARNING: %s" % w)
    if over:
        print("this workspace's map differs from the files for %d agent(s); launchers pass "
              "the Agent tool's model:" % len(over))
        for r in over:
            print("  %s -> %s (file: %s)" % (r["agent"], r["launch"], r["frontmatter"]))
    else:
        print("every agent runs on its file's model in this workspace (no override)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
