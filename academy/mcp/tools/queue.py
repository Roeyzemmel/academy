"""queue_status / queue_log / queue_add and env_list / env_check: the Scientist's queue.

The queue state is ``<scientist home>/<queue dir>/{pending,running,done,parked}/
<id>.json`` (the lab's ``queue.ps1`` layout; the dir is ``scientist.queue.dir``
or ``paths.queue`` from academy.json, default ``queue``). The server never uses
ssh and never contacts a remote host: a log that exists only remotely is
reported with the command that fetches it.

``queue_add`` checks the substance of a submission (the script exists in the lab
home and is committed; the env profile resolves, defaulting to ``policy.run``), then
builds the job file with the Scientist plugin's ``scripts/env.py`` (the same id,
fields and argument splitting as ``env.py queue add``). Unless the home's
academy.json sets ``scientist.queue.mcpAdd: "on"`` it is a **dry run**: nothing is
written, and the result is the job file it would write plus the command that files
it (the migration run leaves it off; plan section 9b). Writing a job file never
contacts the remote: the next ``env.py queue tick`` submits it. ``env_list`` /
``env_check`` read the profiles in the Scientist home's academy.json (a profile
``{"worker": "<name>"}`` is resolved against the workspace's ``compute`` block, as
``env.py`` does); ``env_check`` is a static check of one profile (reachability is probed by ``env.py check``,
``/scientist:env check``, never by this server).
"""

import json
import os
import subprocess

import academy_common as ac

from . import Tool, ToolError, obj, S, I

STATES = ("pending", "running", "done", "parked")
SUMMARY_KEYS = ("label", "status", "remoteState", "script", "created", "submitted",
                "started", "finished", "commit", "result", "note", "exit")


def scientist_home(ctx):
    cands = ctx.instances_by_role("scientist", ctx.my_domains() or None) \
        or ctx.instances_by_role("scientist")
    if not cands:
        raise ToolError("no scientist instance in workspace.json")
    return cands[0], ctx.home_of(cands[0])


def queue_dir(home):
    rel = "queue"
    try:
        cfg = ac.load_config(home) if os.path.isfile(os.path.join(home, ac.CONFIG_REL)) \
            else None
    except ac.ConfigError:
        cfg = None
    if cfg:
        rel = ((cfg.get("scientist") or {}).get("queue") or {}).get("dir") \
            or (cfg.get("paths") or {}).get("queue") or rel
    return os.path.join(home, rel)


def _load(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {"_unreadable": True}


def iter_jobs(qdir):
    for st in sorted(os.listdir(qdir)) if os.path.isdir(qdir) else []:
        d = os.path.join(qdir, st)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".json"):
                job = _load(os.path.join(d, f))
                yield st, f[:-5], os.path.join(d, f), job


def _status(ctx, a):
    inst, home = scientist_home(ctx)
    qdir = queue_dir(home)
    if not os.path.isdir(qdir):
        raise ToolError("no queue directory at %s" % qdir)
    limit = max(1, min(int(a.get("limit") or 20), 200))
    counts, jobs = {}, []
    for st, jid, path, job in iter_jobs(qdir):
        counts[st] = counts.get(st, 0) + 1
        if a.get("state") and st != a["state"]:
            continue
        if a.get("label") and a["label"] not in str(job.get("label", "")):
            continue
        row = {"id": job.get("id", jid), "state": st}
        row.update({k: job[k] for k in SUMMARY_KEYS if job.get(k) not in (None, "")})
        jobs.append(row)
    jobs.sort(key=lambda j: j["id"], reverse=True)
    cfg = _load(os.path.join(qdir, "config.json"))
    return {"instance": inst, "queue": qdir.replace("\\", "/"), "counts": counts,
            "target": cfg.get("target"), "maxJobs": cfg.get("maxJobs"),
            "shown": len(jobs[:limit]), "jobs": jobs[:limit],
            "note": "local queue state only; remote state is refreshed by the queue skill"}


def _tail(path, n):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.read().replace("\r\n", "\n").split("\n")
    return "\n".join(lines[-n:])


def _log(ctx, a):
    inst, home = scientist_home(ctx)
    qdir = queue_dir(home)
    prefix = str(a.get("id") or "").strip()
    if not prefix:
        raise ToolError("id (or an id prefix) is required")
    hits = [(st, jid, p, j) for st, jid, p, j in iter_jobs(qdir) if jid.startswith(prefix)]
    if not hits:
        raise ToolError("no job %s* in %s" % (prefix, qdir))
    if len(hits) > 1:
        raise ToolError("%s is ambiguous: %s" % (prefix, ", ".join(h[1] for h in hits[:10])))
    st, jid, path, job = hits[0]
    n = max(1, min(int(a.get("lines") or 40), 500))
    cands = [os.path.join(qdir, "logs", jid + ".log"), os.path.join(qdir, "logs", jid, "log"),
             os.path.join(qdir, st, jid + ".log")]
    out = {"id": jid, "state": st, "job": job}
    for c in cands:
        if os.path.isfile(c):
            out["log_file"] = c.replace("\\", "/")
            out["tail"] = _tail(c, n)
            return out
    out["note"] = ("no local copy of the log. Remote log: %s. The server never uses ssh; "
                   "fetch it with the queue skill (scripts\\queue.ps1 -Log %s)."
                   % (job.get("log") or "(not recorded)", jid))
    return out


# -- env profiles -----------------------------------------------------------

REQUIRED_BY_KIND = {"ssh": ("host",), "wsl": ("distro",), "local": ()}


def lab_config(ctx):
    """(instance, home, scientist section or None, problems) for the lab home."""
    inst, home = scientist_home(ctx)
    path = os.path.join(home, ac.CONFIG_REL)
    if not os.path.isfile(path):
        return inst, home, None, ["%s has no .claude/academy.json yet (not switched over)"
                                  % home.replace("\\", "/")]
    try:
        cfg = ac.load_config(home)
    except ac.ConfigError as exc:
        return inst, home, None, [str(exc)]
    return inst, home, cfg.get("scientist") or {}, []


def _env_list(ctx, a):
    inst, home, sci, probs = lab_config(ctx)
    out = {"instance": inst, "home": home.replace("\\", "/")}
    if sci is None:
        legacy = _load(os.path.join(queue_dir(home), "config.json"))
        out.update({"envs": {}, "policy": {}, "problems": probs,
                    "legacy_queue_target": legacy.get("target")})
        return out
    out.update({"envs": sci.get("envs") or {}, "policy": sci.get("policy") or {}})
    resolved = {}
    for name, prof in out["envs"].items():
        if isinstance(prof, dict) and "worker" in prof:
            resolved[name] = _resolve(ctx, name, prof)
    if resolved:
        out["resolved"] = resolved
    return out


def _resolve(ctx, name, prof):
    """The worker reference ``prof`` resolved against the workspace (or its problem)."""
    try:
        envpy = scientist_env()
        p = envpy.wk.expand_profile(name, prof, envpy.wk.load_compute(ctx.workspace))
        return {k: v for k, v in p.items() if not k.startswith("_")}
    except ToolError as exc:
        return {"problem": str(exc)}
    except Exception as exc:  # noqa: BLE001 -- a WorkerError, reported not raised
        return {"problem": str(exc)}


def check_profile(name, prof, policy=None, workspace=None):
    """Static problems of one env profile (no I/O); [] when it is well formed.

    Delegates to the Scientist plugin's own ``env.py:static_problems``, so
    ``env_check`` can never call a profile ok that ``env.py check`` would reject (it
    used to keep its own looser copy here: maxJobs only had to be positive, and the
    preflight format was never checked at all). Falls back to the old, looser rules
    only if the plugin cannot be loaded at all, so the tool still degrades rather than
    hard-failing."""
    if not isinstance(prof, dict):
        return ["profile %s is not an object" % name]
    try:
        envpy = scientist_env()
        compute = envpy.wk.load_compute(workspace) if workspace is not None else None
        return envpy.static_problems(name, prof, compute)
    except ToolError:
        pass
    kind = prof.get("kind")
    if kind not in REQUIRED_BY_KIND:
        return ["profile %s: kind must be one of %s" % (name, ", ".join(ac.ENV_KINDS))]
    probs = []
    for key in REQUIRED_BY_KIND[kind]:
        if not prof.get(key):
            probs.append("profile %s: kind %s needs %s" % (name, kind, key))
    mj = prof.get("maxJobs")
    if mj is not None and (not isinstance(mj, int) or mj < 1):
        probs.append("profile %s: maxJobs must be a positive integer" % name)
    return probs


def _env_check(ctx, a):
    inst, home, sci, probs = lab_config(ctx)
    if sci is None:
        raise ToolError("no env profiles to check: %s" % "; ".join(probs))
    envs, policy = sci.get("envs") or {}, sci.get("policy") or {}
    name = a.get("env") or policy.get("run")
    if name not in envs:
        raise ToolError("unknown env profile %r (profiles: %s)"
                        % (name, ", ".join(sorted(envs)) or "none"))
    problems = check_profile(name, envs[name], workspace=ctx.workspace)
    uses = sorted(k for k, v in policy.items() if v == name)
    out = {"instance": inst, "env": name, "profile": envs[name], "policy_uses": uses,
           "ok": not problems, "problems": problems, "checked": "static",
           "note": "a static check of the profile only; the server never contacts a host. "
                   "Reachability and the gateway are /scientist:env check."}
    if isinstance(envs[name], dict) and "worker" in envs[name]:
        out["resolved"] = _resolve(ctx, name, envs[name])
    return out


# -- queue_add ----------------------------------------------------------------

def _git_committed(home, rel):
    """True/False when git can say whether ``rel`` is committed and clean; None if unknown."""
    try:
        tracked = subprocess.run(["git", "-C", home, "ls-files", "--error-unmatch", rel],
                                 capture_output=True, timeout=20)
        if tracked.returncode != 0:
            return False
        dirty = subprocess.run(["git", "-C", home, "status", "--porcelain", "--", rel],
                               capture_output=True, timeout=20)
        return dirty.returncode == 0 and not dirty.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _queue_add(ctx, a):
    inst, home, sci, probs = lab_config(ctx)
    script = str(a.get("script") or "").strip().replace("\\", "/")
    if not script:
        raise ToolError("script (a path relative to the lab home) is required")
    if os.path.isabs(script) or script.startswith("../") or "/../" in script:
        raise ToolError("script must be a path inside the lab home, got %r" % script)
    if not os.path.isfile(os.path.join(home, script)):
        raise ToolError("no script %s in %s" % (script, home))
    committed = _git_committed(home, script)
    if committed is False:
        raise ToolError("%s is not committed (or has uncommitted changes); the queue runs "
                        "only committed scripts" % script)
    env = a.get("env")
    if sci is not None:
        envs, policy = sci.get("envs") or {}, sci.get("policy") or {}
        env = env or policy.get("run")
        if env not in envs:
            raise ToolError("unknown env profile %r" % env)
        bad = check_profile(env, envs[env], workspace=ctx.workspace)
        if bad:
            raise ToolError("; ".join(bad))
    elif env:
        raise ToolError("env profiles need the lab's academy.json (%s)" % "; ".join(probs))
    cmd = "scripts\\queue.ps1 -Add %s" % script.replace("/", "\\")
    if a.get("label"):
        cmd += " -Label %s" % a["label"]
    if a.get("note"):
        cmd += " -Note \"%s\"" % str(a["note"]).replace('"', "'")
    if a.get("script_args"):
        cmd += " -ScriptArgs \"%s\"" % str(a["script_args"]).replace('"', "'")
    # The job is built by the Scientist's runner, so the MCP path and the CLI path
    # write the same file (id, fields, argument splitting, duplicate check).
    envpy = scientist_env()
    try:
        lab = envpy.load_lab(home, workspace=ctx.workspace)
        q = envpy.Queue(lab, env)
        path, job = q.build_job(script, [a["script_args"]] if a.get("script_args") else [],
                                a.get("label"), a.get("note"))
    except envpy.EnvError as exc:
        raise ToolError(str(exc))
    mode = ((sci or {}).get("queue") or {}).get("mcpAdd") or "dry-run"
    out = {"instance": inst, "env": q.name, "path": path.replace("\\", "/"), "job": job,
           "committed": committed}
    if mode != "on":
        out.update({"dry_run": True, "written": False,
                    "note": "queue_add is in dry-run mode (scientist.queue.mcpAdd is %r, not "
                            "'on'): nothing was written; this is the job file it would write. "
                            "File it from the lab home with: %s" % (mode, cmd)})
        return out
    q.ensure_dirs()
    q.save(job, "pending")
    job.pop("_path", None)
    out.update({"dry_run": False, "written": True,
                "note": "queued; the next tick submits it (env.py queue tick)"})
    return out


def scientist_env():
    """The Scientist plugin's ``scripts/env.py``, loaded from the academy repo beside
    this plugin (the plugins are siblings; the ~/.claude/skills links resolve to them)."""
    import importlib.util
    import sys
    name = "academy_scientist_env"
    if name in sys.modules:
        return sys.modules[name]
    here = os.path.dirname(os.path.realpath(__file__))
    path = os.path.normpath(os.path.join(here, "..", "..", "..", "scientist", "scripts",
                                         "env.py"))
    if not os.path.isfile(path):
        raise ToolError("the Scientist plugin's env.py is not at %s" % path)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:  # report, never crash the server
        sys.modules.pop(name, None)
        raise ToolError("cannot load %s: %s" % (path, exc))
    return mod


TOOLS = [
    Tool("queue_status", "The lab's job queue from local state: counts per state and "
         "the newest jobs (filter by state or label). Never contacts the remote host.",
         obj({"state": {"type": "string", "enum": list(STATES)}, "label": S,
              "limit": I}), _status),
    Tool("queue_log", "One job's record and the tail of its log if a local copy exists; "
         "otherwise where the remote log is and how to fetch it.",
         obj({"id": S, "lines": I}, ["id"]), _log),
    Tool("queue_add", "File a committed experiment script on the lab queue for an env "
         "profile (default: policy.run); the next queue tick submits it. In dry-run mode "
         "(the default until the lab's academy.json sets scientist.queue.mcpAdd to 'on') "
         "it writes nothing and returns the job file it would write.",
         obj({"script": S, "env": S, "label": S, "note": S, "script_args": S}, ["script"]),
         _queue_add, write=True),
    Tool("env_list", "The lab's env profiles and policy (probe/test/run) from its "
         "academy.json.", obj({}), _env_list),
    Tool("env_check", "A static check of one env profile (default: policy.run). Never "
         "contacts a host.", obj({"env": S}), _env_check),
]
