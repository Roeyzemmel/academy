"""usage_report.py -- a window of Claude Code usage, by instance, role and agent.

Usage:

    py usage_report.py [--days 7 | --since YYYY-MM-DD] [--projects DIR]
                       [--workspace PATH] [--max-subagents 12] [--json | --brief]

It wraps ``session_usage.tally`` (the per-transcript counter, moved here from
claude-paper) over every session transcript under ``~/.claude/projects`` modified
in the window, and aggregates:

- **by instance**: the project directory is matched to the workspace instance whose
  home it encodes (Claude Code names a project directory after its cwd, with every
  non-alphanumeric character replaced by ``-``); anything else is ``other``;
- **by role**: an agent's plugin namespace or its bare name in the roster of
  ``permissions.json``; the old plugins' namespaces read as ``legacy:<ns>``; agents
  outside any plugin are ``builtin``; the main session is ``main``;
- **by agent**: runs, turns, cache volume, the models seen, the model its
  frontmatter declares (from ``<repo>/<plugin>/agents/*.md``), limit failures.

Flags (deterministic, for the usage-analyst to explain): sessions with limit
failures, sessions with more than ``--max-subagents`` subagents, and agents seen on
a model heavier than the one they declare. Model-downgrade suggestions are the
analyst's judgement, not this script's.

Output is Markdown (default), JSON (``--json``), or one line (``--brief``, used by
the desk). Cache reads are the volume that tracks cost; output tokens are not shown
(see session_usage.py).
"""

import argparse
import collections
import datetime as _dt
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(PLUGIN)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

try:
    import academy_common as ac  # noqa: E402
except ImportError:  # vendored copy
    import _academy as ac  # noqa: E402
import session_usage  # noqa: E402

MODEL_RANK = {"haiku": 0, "sonnet": 1, "opus": 2, "fable": 3}
#: agent namespaces of the pre-academy plugins (claude-paper, claude-flatsurf); their
#: runs are tallied as "legacy:<ns>" until those plugins are retired (plan phase 8)
LEGACY_NAMESPACES = ("paper", "flatsurf")
COUNTED = ("turns", "read", "write", "limit_failures")


def model_family(model):
    """'claude-opus-5-5' -> 'opus'; unknown -> the name itself (or '?')."""
    m = (model or "").lower()
    for fam in MODEL_RANK:
        if fam in m:
            return fam
    return m or "?"


def encode_home(path):
    """The project-directory name Claude Code derives from a cwd."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path).rstrip("/\\"))


def instance_of_project(project_dir_name, workspace):
    """The workspace instance whose home the project directory encodes, or 'other'.

    A worktree or subdirectory of a home (``<home>-academy``, ``<home>/sub``)
    counts for that home; the longest matching home wins.
    """
    name = project_dir_name.lower()
    best, best_len = "other", -1
    for inst, row in ((workspace or {}).get("instances") or {}).items():
        enc = encode_home(row.get("home", "")).lower()
        if not enc:
            continue
        if (name == enc or name.startswith(enc + "-")) and len(enc) > best_len:
            best, best_len = inst, len(enc)
    return best


def load_roster(perms=None):
    """bare agent name -> plugin, from permissions.json."""
    if perms is None:
        try:
            perms = ac.load_permissions()
        except (ac.AcademyError, OSError, ValueError):
            return {}
    out = {}
    for plugin, names in (perms.get("roster") or {}).items():
        for n in names:
            out[n] = plugin
    return out


def role_of_agent(agent_type, roster):
    """The role (plugin) an agent type belongs to."""
    if not agent_type or agent_type == "MAIN":
        return "main"
    ns, _, bare = agent_type.rpartition(":")
    if ns in ac.PLUGINS:
        return ns
    if ns in LEGACY_NAMESPACES:
        return "legacy:" + ns
    if bare in roster:
        return roster[bare]
    return "builtin"


RE_FM_MODEL = re.compile(r"^model:\s*([A-Za-z0-9._-]+)\s*$", re.M)
RE_FM_NAME = re.compile(r"^name:\s*([A-Za-z0-9._-]+)\s*$", re.M)


def declared_models(repo=REPO):
    """bare agent name -> declared model family, from every plugin's agents/*.md."""
    out = {}
    for path in glob.glob(os.path.join(repo, "*", "agents", "*.md")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        if not text.startswith("---"):
            continue
        head = text.split("---", 2)[1] if text.count("---") >= 2 else ""
        mm, nm = RE_FM_MODEL.search(head), RE_FM_NAME.search(head)
        if mm:
            name = nm.group(1) if nm else os.path.splitext(os.path.basename(path))[0]
            out[name] = model_family(mm.group(1))
    return out


def _window(days=None, since=None, now=None):
    now = now or _dt.datetime.now()
    if since:
        start = _dt.datetime.strptime(since, "%Y-%m-%d")
    else:
        start = now - _dt.timedelta(days=days if days is not None else 7)
    return start, now


def collect(projects_root, start, end=None, workspace=None):
    """Tally every session transcript modified in [start, end].

    Returns a list of session dicts:
    ``{session, project, instance, main: {counts, models}, subagents: [
    {agent_type, depth, description, counts, models}]}``.
    """
    lo = start.timestamp()
    hi = end.timestamp() if end else None
    sessions = []
    for path in sorted(glob.glob(os.path.join(projects_root, "*", "*.jsonl"))):
        mtime = os.path.getmtime(path)
        if mtime < lo or (hi is not None and mtime > hi):
            continue
        base = os.path.dirname(path)
        sid = os.path.splitext(os.path.basename(path))[0]
        project = os.path.basename(base)
        t, m = session_usage.tally(path)
        subs = []
        for meta in sorted(glob.glob(os.path.join(base, sid, "subagents", "*.meta.json"))):
            try:
                with open(meta, "r", encoding="utf-8") as fh:
                    md = json.load(fh)
            except (OSError, ValueError):
                md = {}
            jl = meta[: -len(".meta.json")] + ".jsonl"
            st, sm = session_usage.tally(jl) if os.path.isfile(jl) else (collections.Counter(), collections.Counter())
            subs.append({"agent_type": md.get("agentType", "?"),
                         "depth": md.get("spawnDepth"),
                         "description": md.get("description", ""),
                         "counts": {k: st.get(k, 0) for k in COUNTED},
                         "models": dict(sm)})
        sessions.append({"session": sid, "project": project,
                         "instance": instance_of_project(project, workspace),
                         "main": {"counts": {k: t.get(k, 0) for k in COUNTED},
                                  "models": dict(m)},
                         "subagents": subs})
    return sessions


def _add(acc, counts):
    for k in COUNTED:
        acc[k] += counts.get(k, 0)


def aggregate(sessions, roster=None, declared=None, max_subagents=12):
    """Aggregate collected sessions into the report dict."""
    roster = roster or {}
    declared = declared or {}
    by_instance = collections.defaultdict(collections.Counter)
    by_role = collections.defaultdict(collections.Counter)
    by_agent = {}
    flags = []
    total = collections.Counter()
    for s in sessions:
        inst = s["instance"]
        by_instance[inst]["sessions"] += 1
        by_instance[inst]["subagents"] += len(s["subagents"])
        _add(by_instance[inst], s["main"]["counts"])
        _add(by_role["main"], s["main"]["counts"])
        by_role["main"]["runs"] += 1
        _add(total, s["main"]["counts"])
        limit = s["main"]["counts"].get("limit_failures", 0)
        for sub in s["subagents"]:
            at = sub["agent_type"]
            role = role_of_agent(at, roster)
            bare = at.rpartition(":")[2]
            _add(by_instance[inst], sub["counts"])
            _add(by_role[role], sub["counts"])
            by_role[role]["runs"] += 1
            _add(total, sub["counts"])
            limit += sub["counts"].get("limit_failures", 0)
            a = by_agent.setdefault(at, {"agent": at, "role": role,
                                         "declared": declared.get(bare),
                                         "runs": 0, "models": collections.Counter(),
                                         **{k: 0 for k in COUNTED}})
            a["runs"] += 1
            for k in COUNTED:
                a[k] += sub["counts"].get(k, 0)
            for model, n in sub["models"].items():
                a["models"][model_family(model)] += n
        if limit:
            flags.append({"kind": "limit", "session": s["session"], "instance": inst,
                          "count": limit})
        if len(s["subagents"]) > max_subagents:
            flags.append({"kind": "fan-out", "session": s["session"], "instance": inst,
                          "count": len(s["subagents"])})
    for a in by_agent.values():
        dec = a["declared"]
        if dec in MODEL_RANK:
            heavier = sorted(m for m in a["models"]
                             if m in MODEL_RANK and MODEL_RANK[m] > MODEL_RANK[dec])
            if heavier:
                flags.append({"kind": "heavier-than-declared", "agent": a["agent"],
                              "declared": dec, "seen": heavier})
        a["models"] = dict(a["models"])
        a["mean_turns"] = round(a["turns"] / a["runs"], 1) if a["runs"] else 0
    return {
        "sessions": len(sessions),
        "subagents": sum(len(s["subagents"]) for s in sessions),
        "total": {k: total[k] for k in COUNTED},
        "by_instance": {k: dict(v) for k, v in sorted(by_instance.items())},
        "by_role": {k: dict(v) for k, v in sorted(by_role.items())},
        "by_agent": sorted(by_agent.values(), key=lambda a: -a["read"]),
        "flags": flags,
    }


def _k(n):
    return "%dk" % (n // 1000)


def render_markdown(report, start, end):
    out = ["# Usage %s .. %s" % (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")), ""]
    out.append("%d sessions, %d subagents, cache read %s, cache write %s, "
               "limit failures %d." % (report["sessions"], report["subagents"],
                                       _k(report["total"]["read"]),
                                       _k(report["total"]["write"]),
                                       report["total"]["limit_failures"]))
    out += ["", "## By instance", "",
            "| instance | sessions | subagents | turns | read | write | limit |",
            "|---|---|---|---|---|---|---|"]
    for k, v in report["by_instance"].items():
        out.append("| %s | %d | %d | %d | %s | %s | %d |" % (
            k, v.get("sessions", 0), v.get("subagents", 0), v.get("turns", 0),
            _k(v.get("read", 0)), _k(v.get("write", 0)), v.get("limit_failures", 0)))
    out += ["", "## By role", "", "| role | runs | turns | read | write | limit |",
            "|---|---|---|---|---|---|"]
    for k, v in report["by_role"].items():
        out.append("| %s | %d | %d | %s | %s | %d |" % (
            k, v.get("runs", 0), v.get("turns", 0), _k(v.get("read", 0)),
            _k(v.get("write", 0)), v.get("limit_failures", 0)))
    out += ["", "## By agent", "",
            "| agent | role | declared | seen | runs | mean turns | read | limit |",
            "|---|---|---|---|---|---|---|---|"]
    for a in report["by_agent"]:
        seen = ",".join("%s x%d" % (m, n) for m, n in sorted(a["models"].items()))
        out.append("| %s | %s | %s | %s | %d | %s | %s | %d |" % (
            a["agent"], a["role"], a["declared"] or "-", seen or "-", a["runs"],
            a["mean_turns"], _k(a["read"]), a["limit_failures"]))
    out += ["", "## Flags", ""]
    if not report["flags"]:
        out.append("None.")
    for f in report["flags"]:
        if f["kind"] == "limit":
            out.append("- limit: session %s (%s): %d limit failure(s)"
                       % (f["session"], f["instance"], f["count"]))
        elif f["kind"] == "fan-out":
            out.append("- fan-out: session %s (%s): %d subagents"
                       % (f["session"], f["instance"], f["count"]))
        else:
            out.append("- heavier-than-declared: %s declares %s, seen on %s"
                       % (f["agent"], f["declared"], ", ".join(f["seen"])))
    return "\n".join(out) + "\n"


def render_brief(report, days_label):
    return ("usage %s: %d sessions, %d subagents, cache read %s, %d limit failure(s), "
            "%d flag(s)" % (days_label, report["sessions"], report["subagents"],
                            _k(report["total"]["read"]),
                            report["total"]["limit_failures"], len(report["flags"])))


def build(days=None, since=None, projects=None, workspace_path=None, max_subagents=12,
          now=None, perms=None, repo=REPO):
    start, end = _window(days, since, now)
    projects = projects or os.path.expanduser("~/.claude/projects")
    try:
        ws = ac.load_workspace(workspace_path)
    except ac.AcademyError:
        ws = None
    # A live window has no upper bound: a transcript still being written (this
    # session's own, or the scheduled job's) can carry an mtime just after ``now``,
    # whose resolution on Windows is coarse. Only an explicit ``now`` caps it.
    sessions = collect(projects, start, end if now is not None else None, ws)
    report = aggregate(sessions, load_roster(perms), declared_models(repo), max_subagents)
    report["window"] = {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}
    return report, start, end


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--days", type=int, default=None)
    g.add_argument("--since")
    ap.add_argument("--projects", help="default: ~/.claude/projects")
    ap.add_argument("--workspace")
    ap.add_argument("--max-subagents", type=int, default=12)
    out = ap.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true")
    out.add_argument("--brief", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    report, start, end = build(a.days, a.since, a.projects, a.workspace, a.max_subagents)
    if a.json:
        print(json.dumps(report, indent=2))
    elif a.brief:
        label = ("since %s" % a.since) if a.since else ("%dd" % (a.days if a.days is not None else 7))
        print(render_brief(report, label))
    else:
        sys.stdout.write(render_markdown(report, start, end))
    return 0


if __name__ == "__main__":
    sys.exit(main())
