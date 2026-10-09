"""env.py -- the lab's environment profiles and job queue (plan section 3.5).

Profiles live in the Scientist home's ``.claude/academy.json`` under
``scientist.envs``; each has a kind:

    wsl     a WSL distro on the Windows laptop           (distro, conda, prefix)
    local   the Linux machine this runs on                (conda, prefix)
    ssh     any remote Linux workstation                  (host, user, prefix, env, repo,
                                                           maxJobs, gateway)

A remote worker is usually not spelled out in the home: the profile is
``{"worker": "<name>"}`` and the worker (host, user, remoteRoot, conda prefix and env,
gateway) is the workspace's, ``workspace.json`` ``compute.workers.<name>``, with its
gateway (a VPN, or none) under ``compute.gateways`` (``workers.py``; docs/config.md,
"compute"). The academy ships no machine of its own: a profile the home does not
define is refused, with that hint. An inline ssh profile may name a ``gateway`` too,
or the older ``preflight: "vpn:<check>"``. ``policy`` maps ``probe`` / ``test`` /
``run`` to profiles; wherever a profile is named, a policy key may stand for it. A
home without academy.json (before its switch-over) gets its queue target from
``queue/config.json`` (profile ``queue``) and a ``laptop-wsl`` profile.

Usage::

    py env.py [--home DIR] list [--json]
    py env.py [--home DIR] check PROFILE [--live]
    py env.py [--home DIR] run PROFILE [--sage] [-u] [--conda ENV] [--prefix P] [--dry-run]
                                   (-c CODE | SCRIPT [ARGS ...])
    py env.py [--home DIR] setup PROFILE [--dry-run]
    py env.py [--home DIR] gateway [--profile P] [--probe] [--quiet]     (alias: vpn)
    py env.py [--home DIR] queue [--profile P] SUB ...

Queue subcommands (the fsq runner protocol of the legacy ``queue.ps1``; job files in
``<home>/<queue dir>/{pending,running,done}/<id>.json``):

    add SCRIPT [--label L] [--note N] [--args "A B"] [--dry-run] [-- ARGS ...]
    list | check | tick | fetch | status | log ID-PREFIX
    preflight | deploy [--no-cron] | pause | resume | setup

The legacy flags are accepted too (``queue -Add x.py -Label l -ScriptArgs "--b 4"``,
``queue -List``, ``-Check``, ``-Tick``, ``-Fetch``, ``-Status``, ``-Log``, ``-Setup``,
``-Preflight``, ``-Deploy [-NoCron]``, ``-Pause``, ``-Resume``), so the frontends
``queue.ps1`` / ``run.ps1`` and ``lab.py cmd`` stay thin.

Semantics kept from queue.ps1: a job runs the commit that was HEAD when it was
submitted; ``tick`` skips a job whose script is uncommitted or not in HEAD; the
commit is pushed to ``refs/fsq/<id>``; submitting is idempotent and never trusted
from an exit code (the remote spool is re-read and decides); a job the remote knows
is never submitted again; the deployed runner must be byte-identical to this
plugin's ``fsq.sh`` (``fsq version`` is its sha256). ``run`` refuses ssh profiles:
remote runs go through the queue.

Home: ``--home``, else ``$ACADEMY_LAB_HOME``, else the Scientist home containing the
cwd, else workspace.json's scientist instance.

Test hooks (no network in the tests): ``ACADEMY_SSH`` / ``ACADEMY_SCP`` (a JSON argv
prefix replacing ``ssh`` / ``scp``), ``ACADEMY_FAKE_PREFLIGHT`` (the gateway check:
0 up, 1 down, 2 cannot tell), and the profile keys ``pushUrl`` / ``remoteEnv`` (as in the legacy
``queue/config.json``).

Exit codes: 0 ok; 1 unreachable / failed (the legacy codes); 2 usage or config error.
"""

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)

import _common as c  # noqa: E402
from _common import ac  # noqa: E402
import workers as wk  # noqa: E402

RUNNER = os.path.join(HERE, "fsq.sh")
RUN_SH = os.path.join(HERE, "run.sh")
SETUP_SH = os.path.join(HERE, "setup_env.sh")
KINDS = ("wsl", "local", "ssh")
REQUIRED_BY_KIND = {"ssh": ("host",), "wsl": ("distro",), "local": ()}
PREFLIGHTS = ("vpn",)          # the older inline form, preflight: "vpn:<check>"
JOB_KEYS = ("id", "script", "args", "label", "note", "created", "status", "started",
            "commit", "log", "finished", "result")
PREFLIGHT_WORDS = {0: "up", 1: "down", 2: "cannot tell"}


class EnvError(Exception):
    """A usage or configuration error (exit 2)."""


class RemoteFailure(Exception):
    """The target answered with a failure the legacy script threw on (exit 1)."""


class Exit(Exception):
    """Leave with this exit code (the legacy script's ``exit N``)."""

    def __init__(self, code):
        Exception.__init__(self, code)
        self.code = code


def say(*parts):
    print(" ".join(str(p) for p in parts), flush=True)


def warn(msg):
    print("WARNING: " + msg, file=sys.stderr, flush=True)


def Q(s):
    """Single-quote one word for a POSIX shell."""
    return "'" + str(s).replace("'", "'\\''") + "'"


def _json_argv(var, default):
    raw = os.environ.get(var)
    if not raw:
        return list(default)
    try:
        val = json.loads(raw)
    except ValueError:
        raise EnvError("%s must be a JSON list (an argv prefix)" % var)
    if not (isinstance(val, list) and val and all(isinstance(v, str) for v in val)):
        raise EnvError("%s must be a non-empty JSON list of strings" % var)
    return val


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def git(home, *args):
    """(exit code, stdout) of a git command in ``home``."""
    p = subprocess.run(["git", "-C", home] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout


def wsl_path(win_path):
    """C:/x/y -> /mnt/c/x/y (the default automount), without calling wslpath."""
    p = os.path.abspath(win_path).replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)$", p)
    if not m:
        return p
    return "/mnt/%s/%s" % (m.group(1).lower(), m.group(2))


# ----------------------------------------------------------------------------
# The lab and its profiles
# ----------------------------------------------------------------------------

class LabHome(object):
    def __init__(self, home, cfg, switched, instance, legacy_queue=None, compute=None):
        self.home = home
        self.compute = compute if compute is not None else wk.load_compute()
        self.cfg = cfg
        self.switched = switched
        self.instance = instance
        sci = cfg.get("scientist") or {}
        self.envs = sci.get("envs") or {}
        self.policy = sci.get("policy") or {}
        self.queue_cfg = sci.get("queue") or {}
        self.legacy_queue = legacy_queue or {}

    @property
    def qdir(self):
        rel = self.queue_cfg.get("dir") or (self.cfg.get("paths") or {}).get("queue") \
            or "queue"
        return os.path.join(self.home, rel)


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _legacy_profiles(qcfg):
    """Profiles for a home with no academy.json, from its queue/config.json."""
    envs = {"laptop-wsl": {"kind": "wsl", "distro": "Ubuntu"}}
    target = (qcfg or {}).get("target")
    prof = {}
    if not target:
        raise EnvError("queue/config.json names no target (ssh:<host> or wsl:<distro>); "
                       "give the home a .claude/academy.json instead -- " + wk.HINT)
    if target.startswith("ssh:"):
        prof = {"kind": "ssh", "host": target[4:]}
    elif target.startswith("wsl:"):
        prof = {"kind": "wsl", "distro": target[4:]}
    else:
        raise EnvError("queue/config.json target must be ssh:<host> or wsl:<distro>")
    for old, new in (("prefix", "prefix"), ("remoteRepo", "repo"), ("maxJobs", "maxJobs"),
                     ("pushUrl", "pushUrl"), ("remoteEnv", "remoteEnv"), ("env", "env"),
                     ("gateway", "gateway"), ("preflight", "preflight")):
        if (qcfg or {}).get(old) not in (None, ""):
            prof[new] = qcfg[old]
    envs["queue"] = prof
    return envs, {"probe": "laptop-wsl", "test": "laptop-wsl", "run": "queue"}


def load_lab(home=None, cwd=None, workspace=None):
    """The lab home: explicit, $ACADEMY_LAB_HOME, the home around cwd, or workspace.json.

    Its workers come from ``workspace`` (a loaded workspace.json) when given, else from
    the workspace.json academy_common finds."""
    home = home or os.environ.get("ACADEMY_LAB_HOME")
    if not home:
        found = ac.find_home(cwd or os.getcwd())
        if found:
            home = found
        else:
            try:
                home = c.resolve_lab(None, cwd or os.getcwd())["home"]
            except ac.AcademyError as exc:
                raise EnvError(str(exc))
    home = os.path.abspath(home)
    if not os.path.isdir(home):
        raise EnvError("no lab home at %s" % home)
    if os.path.isfile(os.path.join(home, ac.CONFIG_REL)):
        try:
            cfg = ac.load_config(home)
        except ac.AcademyError as exc:
            raise EnvError(str(exc))
        if cfg.get("role") != "scientist":
            raise EnvError("%s is a %s home, not a Scientist home" % (home, cfg.get("role")))
        return LabHome(home, cfg, True, cfg.get("instance"),
                       compute=wk.load_compute(workspace) if workspace else None)
    qcfg = _read_json(os.path.join(home, "queue", "config.json")) or {}
    envs, policy = _legacy_profiles(qcfg)
    cfg = {"paths": {"queue": "queue", "experiments": "experiments/*.py",
                     "results": "results"},
           "scientist": {"envs": envs, "policy": policy,
                         "queue": {"dir": "queue", "fsqHome": qcfg.get("fsqHome") or "~/fsq",
                                   "maxJobs": qcfg.get("maxJobs") or 1}}}
    return LabHome(home, cfg, False, None, qcfg,
                   compute=wk.load_compute(workspace) if workspace else None)


def resolve_profile(lab, name):
    """(profile name, profile) for a profile name or a policy key (probe/test/run).

    The profile comes back expanded (``workers.expand_profile``): a worker reference
    is the worker's ssh profile, and a gateway is resolved under ``_gateway``."""
    found = _find_profile(lab, name)
    try:
        return found[0], wk.expand_profile(found[0], found[1], lab.compute, lab.home)
    except wk.WorkerError as exc:
        raise EnvError(str(exc))


def expanded_envs(lab):
    """{name: expanded profile} (a profile that does not resolve maps to its problem)."""
    out = {}
    for name in sorted(lab.envs):
        try:
            out[name] = wk.expand_profile(name, lab.envs[name], lab.compute, lab.home)
        except wk.WorkerError as exc:
            out[name] = {"worker": lab.envs[name].get("worker"), "_problem": str(exc)}
    return out


def _find_profile(lab, name):
    if name in lab.envs:
        return name, lab.envs[name]
    if name in lab.policy and lab.policy[name] in lab.envs:
        return lab.policy[name], lab.envs[lab.policy[name]]
    # the legacy run.ps1 targets: wsl, wsl:<distro>, ssh:<host>
    kind, _, arg = str(name).partition(":")
    if kind in ("wsl", "ssh"):
        key = "distro" if kind == "wsl" else "host"
        envs = expanded_envs(lab)
        cands = [n for n in sorted(envs) if envs[n].get("kind") == kind
                 and (not arg or envs[n].get(key) == arg or
                      (kind == "ssh" and envs[n].get("worker") == arg))]
        pref = lab.policy.get("test" if kind == "wsl" else "run")
        if pref in cands:
            return pref, lab.envs[pref]
        if cands:
            return cands[0], lab.envs[cands[0]]
        if kind == "wsl":
            # an ad-hoc distro: the conda env and prefix of the home's own wsl profile
            base = next((envs[n] for n in sorted(envs) if envs[n].get("kind") == "wsl"), {})
            prof = {"kind": "wsl", "distro": arg or "Ubuntu"}
            for k in ("conda", "prefix"):
                if base.get(k):
                    prof[k] = base[k]
            return "wsl:%s" % (arg or "Ubuntu"), prof
    raise EnvError("unknown profile %r (profiles: %s; policy keys: %s). The academy has no "
                   "built-in machines: %s"
                   % (name, ", ".join(sorted(lab.envs)) or "none",
                      ", ".join(sorted(lab.policy)) or "none", wk.HINT))


def static_problems(name, prof, compute=None, home=None):
    """Problems of one profile that need no I/O; [] when it is well formed.

    A worker reference (``{"worker": ...}``) is expanded against ``compute`` (default:
    the workspace's) first, so a worker the workspace does not define is a problem."""
    if not isinstance(prof, dict):
        return ["profile %s is not an object" % name]
    if "worker" in prof or (prof.get("gateway") and "_gateway" not in prof):
        try:
            prof = wk.expand_profile(name, prof, compute if compute is not None
                                     else wk.load_compute(), home)
        except wk.WorkerError as exc:
            return [str(exc)]
    kind = prof.get("kind")
    if kind not in KINDS:
        return ["profile %s: kind must be one of %s" % (name, ", ".join(KINDS))]
    probs = []
    for key in REQUIRED_BY_KIND[kind]:
        if not prof.get(key):
            probs.append("profile %s: kind %s needs %s" % (name, kind, key))
    mj = prof.get("maxJobs")
    if mj is not None and not (isinstance(mj, int) and 1 <= mj <= 3):
        probs.append("profile %s: maxJobs must be an integer 1..3" % name)
    pf = prof.get("preflight")
    if pf is not None:
        pname = str(pf).partition(":")[0]
        if pname not in PREFLIGHTS or ":" not in str(pf):
            probs.append("profile %s: preflight must be <name>:<arg> with name in %s"
                         % (name, ", ".join(PREFLIGHTS)))
    gw = prof.get("_gateway")
    if gw and not pf:
        probs += ["profile %s: %s" % (name, p) for p in wk.gateway_problems(gw["name"], gw)]
    return probs


# ----------------------------------------------------------------------------
# Preflights
# ----------------------------------------------------------------------------

def run_gateway(prof, probe=False):
    """(code, message) of the profile's gateway check: 0 up, 1 down, 2 cannot tell.
    A profile with no gateway is up (there is nothing to bring up)."""
    return wk.check_gateway(prof.get("_gateway"), probe=probe)


# ----------------------------------------------------------------------------
# Transport: one command line on a profile's machine
# ----------------------------------------------------------------------------

class Transport(object):
    def __init__(self, prof):
        self.prof = prof
        self.kind = prof.get("kind")
        self.host = prof.get("host") or prof.get("distro") or "localhost"
        # the ssh destination: user@host when the worker names a user, else the host
        # (an ssh config alias may supply the user)
        self.dest = ("%s@%s" % (prof["user"], self.host)) if prof.get("user") \
            and self.kind == "ssh" else self.host
        self.why = ""

    def argv(self, cmd, connect_timeout=None):
        if self.kind == "ssh":
            argv = _json_argv("ACADEMY_SSH", ["ssh"]) + ["-o", "BatchMode=yes"]
            if connect_timeout:
                argv += ["-o", "ConnectTimeout=%d" % connect_timeout]
            return argv + [self.dest, cmd]
        if self.kind == "wsl":
            return ["wsl.exe", "-d", self.host, "-e", "bash", "-c", cmd]
        return ["bash", "-c", cmd]

    def remote(self, cmd, connect_timeout=None):
        """(exit code, output lines) -- stdout and stderr, minus ssh's '** ' banner."""
        try:
            p = subprocess.run(self.argv(cmd, connect_timeout), stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        except OSError as exc:
            return 127, ["cannot start %s: %s" % (self.argv(cmd)[0], exc)]
        text = p.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n")
        lines = [l for l in text.split("\n") if not l.startswith("** ")]
        if lines and lines[-1] == "":
            lines.pop()
        return p.returncode, lines

    def _scp(self, src, dest):
        argv = _json_argv("ACADEMY_SCP", ["scp"]) + ["-q", src, dest]
        try:
            return subprocess.run(argv, stdin=subprocess.DEVNULL).returncode == 0
        except OSError:
            return False

    def copy_from(self, remote_path, dest):
        os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
        if self.kind == "ssh":
            return self._scp("%s:%s" % (self.dest, re.sub(r"^~/", "", remote_path)), dest)
        if self.kind == "wsl":
            return subprocess.run(["wsl.exe", "-d", self.host, "-e", "cp", remote_path,
                                   wsl_path(dest)]).returncode == 0
        import shutil
        try:
            shutil.copyfile(os.path.expanduser(remote_path), dest)
            return True
        except OSError:
            return False

    def copy_to(self, src, remote_path):
        if self.kind == "ssh":
            return self._scp(src, "%s:%s" % (self.dest, re.sub(r"^~/", "", remote_path)))
        if self.kind == "wsl":
            return subprocess.run(["wsl.exe", "-d", self.host, "-e", "cp", wsl_path(src),
                                   remote_path]).returncode == 0
        import shutil
        try:
            shutil.copyfile(src, os.path.expanduser(remote_path))
            return True
        except OSError:
            return False

    def scp_argv(self, src, remote_path):
        """The argv that copies a local file to the remote (for --dry-run listings)."""
        return _json_argv("ACADEMY_SCP", ["scp"]) + [
            "-q", src, "%s:%s" % (self.dest, re.sub(r"^~/", "", remote_path))]

    def reachable(self):
        """The legacy Reachable: the gateway first (down = no), then ``ssh host true``.
        Sets ``why`` to what failed."""
        self.why = ""
        if self.kind != "ssh":
            return True
        if self.prof.get("_gateway"):
            code, msg = run_gateway(self.prof)
            if code == 1:
                self.why = msg
                return False
        rc, _ = self.remote("true", connect_timeout=8)
        if rc != 0:
            self.why = "ssh exit %d" % rc
        return rc == 0


# ----------------------------------------------------------------------------
# list / check / run / setup / gateway
# ----------------------------------------------------------------------------

def _profile_line(name, raw, prof):
    keys = [k for k in ("worker", "distro", "host", "user", "conda", "prefix", "env", "repo",
                        "maxJobs", "gateway", "preflight") if prof.get(k) not in (None, "")]
    kind = prof.get("kind") or ("worker" if "worker" in raw else None)
    return "  %-12s %-6s %s" % (name, kind,
                                " ".join("%s=%s" % (k, prof[k]) for k in keys))


def _public(prof):
    return {k: v for k, v in prof.items() if not k.startswith("_")} if isinstance(prof, dict) \
        else prof


def cmd_list(lab, as_json=False):
    expanded = expanded_envs(lab)
    data = {"instance": lab.instance, "home": lab.home.replace("\\", "/"),
            "switched": lab.switched, "envs": lab.envs,
            "resolved": {n: _public(p) for n, p in expanded.items()},
            "gateways": {n: p["_gateway"] for n, p in expanded.items() if p.get("_gateway")},
            "policy": lab.policy,
            "queue": lab.qdir.replace("\\", "/"),
            "fsqHome": lab.queue_cfg.get("fsqHome") or "~/fsq",
            "runner": sha256(RUNNER),
            "compute": {"workspace": lab.compute.path, "workers": sorted(lab.compute.workers),
                        "gateways": sorted(lab.compute.gateways),
                        "problems": wk.compute_problems(lab.compute)}}
    if as_json:
        print(json.dumps(data, indent=1, ensure_ascii=False))
        return 0
    say("%s at %s (%s)" % (lab.instance or "lab", data["home"],
                           ".claude/academy.json" if lab.switched
                           else "no academy.json: profiles from queue/config.json"))
    say("profiles:")
    for name in sorted(lab.envs):
        prof = expanded[name]
        say(_profile_line(name, lab.envs[name], prof))
        if prof.get("_problem"):
            say("    problem: " + prof["_problem"])
            continue
        for p in static_problems(name, prof):
            say("    problem: " + p)
        gw = prof.get("_gateway")
        if gw:
            say("    gateway %s: %s%s" % (gw["name"], gw.get("kind"),
                                         (" (%s)" % (gw.get("check") or gw.get("client")))
                                         if gw.get("kind") == "vpn" else ""))
    say("policy: " + ", ".join("%s = %s" % (k, lab.policy[k]) for k in
                               ("probe", "test", "run") if k in lab.policy))
    if lab.compute.workers or lab.compute.gateways:
        say("workspace compute (%s): workers %s; gateways %s"
            % (lab.compute.path or "workspace.json",
               ", ".join(sorted(lab.compute.workers)) or "none",
               ", ".join(sorted(lab.compute.gateways)) or "none"))
        for p in data["compute"]["problems"]:
            say("    problem: " + p)
    say("queue: %s (fsq home %s; plugin runner sha256 %s)"
        % (data["queue"], data["fsqHome"], data["runner"][:12]))
    return 0


def cmd_check(lab, name, live=False):
    name, prof = resolve_profile(lab, name)
    kind = prof.get("kind")
    probs = static_problems(name, prof)
    uses = sorted(k for k, v in lab.policy.items() if v == name)
    say("%s (%s%s)%s: %s" % (name, kind, (", worker %s" % prof["worker"])
                             if prof.get("worker") else "",
                             (" -- policy " + ", ".join(uses)) if uses else "",
                             "static ok" if not probs else "; ".join(probs)))
    if probs:
        return 2
    gw = prof.get("_gateway")
    if gw:
        code, msg = run_gateway(prof)
        say("gateway " + msg)
        if code == 1:
            if kind == "ssh":
                say("unreachable: gateway %s is down; jobs for %s are queued, not failed. "
                    "%s" % (gw["name"], name, wk.on_down(prof, lab.compute, name)))
            else:
                say("unreachable: gateway %s is down" % gw["name"])
            return 1
    if not live:
        say("not contacted (pass --live to ask the machine itself)")
        return 0
    t = Transport(prof)
    if kind == "ssh":
        fsq_bin = "%s/bin/fsq" % (lab.queue_cfg.get("fsqHome") or "~/fsq")
        env_prefix = (prof.get("remoteEnv") + " ") if prof.get("remoteEnv") else ""
        rc, lines = t.remote("%s%s version" % (env_prefix, fsq_bin), connect_timeout=8)
        if rc != 0:
            say("unreachable: %s (ssh exit %d) -- jobs wait in the queue (queued)"
                % (t.host, rc))
            for l in lines[-3:]:
                say("  " + l)
            return 1
        got = lines[-1].strip() if lines else ""
        want = sha256(RUNNER)
        if got == want:
            say("reachable: %s; runner %s matches the plugin's fsq.sh" % (t.host, got[:12]))
        else:
            say("reachable: %s; runner on the host (%s) differs from the plugin's fsq.sh "
                "(%s); deploying it is %s's call" % (t.host, got[:12] or "none", want[:12],
                                                     lab.compute.human))
        rc, lines = t.remote("%s%s status" % (env_prefix, fsq_bin), connect_timeout=8)
        say("spool (fsq status, exit %d):" % rc)
        for l in lines:
            say("  " + l)
        return 0
    envname = prof.get("conda")
    if not envname:
        say("profile %s names no conda env (set conda in its profile)" % name)
        return 2
    if kind == "wsl":
        prefix = prof.get("prefix") or "~/miniforge3"
        py = "%s/envs/%s/bin/python" % (prefix, envname)
        rc, lines = t.remote("test -x %s && echo ok: %s" % (py, py))
        say("wsl %s: %s" % (t.host, "; ".join(lines) or "no python at %s (exit %d)" % (py, rc)))
        return 0 if rc == 0 else 1
    if os.name == "nt":
        say("kind local means the Linux machine Claude runs on; this is Windows")
        return 1
    prefix = os.path.expanduser(prof.get("prefix") or "~/miniforge3")
    py = os.path.join(prefix, "envs", envname, "bin", "python")
    ok = os.access(py, os.X_OK)
    say("local: %s %s" % (py, "exists" if ok else "missing"))
    return 0 if ok else 1


def _inside(lab, path):
    """The home-relative '/' path of ``path``, or EnvError.

    A relative path is read against the cwd (as the legacy scripts did); when nothing
    is there but the home has it, against the home (the MCP server passes home paths).
    """
    abs_ = os.path.abspath(path)
    if not os.path.isabs(path) and not os.path.exists(abs_)             and os.path.exists(os.path.join(lab.home, path)):
        abs_ = os.path.abspath(os.path.join(lab.home, path))
    root = os.path.abspath(lab.home)
    if os.path.normcase(abs_) != os.path.normcase(root) and not os.path.normcase(
            abs_).startswith(os.path.normcase(root) + os.sep):
        raise EnvError("the script must be inside the lab (%s): %s" % (root, path))
    return os.path.relpath(abs_, root).replace("\\", "/")


def _is_experiment(lab, rel):
    pats = (lab.cfg.get("paths") or {}).get("experiments") or "experiments/*.py"
    pats = pats if isinstance(pats, list) else [pats]
    import fnmatch
    name = rel.rsplit("/", 1)[-1]
    return name not in c.EXEMPT and any(fnmatch.fnmatch(rel, p) for p in pats)


def run_command(lab, name, prof, target, code=None, sage=False, unbuffered=False,
                conda=None, prefix=None):
    """The argv that runs ``target`` (a script plus args) or ``code`` on a wsl/local profile."""
    kind = prof.get("kind")
    if kind == "ssh":
        raise EnvError("profile %s is ssh: remote runs go through the queue "
                       "(env.py queue add <script>), never run" % name)
    if kind == "wsl":
        root, runsh = wsl_path(lab.home), wsl_path(RUN_SH)
    else:
        root, runsh = lab.home, RUN_SH
    assign = "LAB_ROOT=%s " % Q(root)
    if sage:
        assign += "SAGE=1 "
    if unbuffered:
        assign += "PYTHONUNBUFFERED=1 "
    pfx = prefix or prof.get("prefix")
    envname = conda or prof.get("conda")
    if pfx:
        assign += "MINIFORGE_PREFIX=%s " % Q(pfx)
    if envname:
        assign += "ACADEMY_CONDA_ENV=%s " % Q(envname)
    if code is not None:
        tail = "-c %s" % Q(code)
    else:
        words = [a for a in target[1:] if a != "--"]
        rel = _inside(lab, target[0])
        tail = " ".join(Q(w) for w in [rel] + words)
    cmd = "cd %s && %sbash %s %s" % (Q(root), assign, Q(runsh), tail)
    if kind == "wsl":
        return ["wsl.exe", "-d", prof["distro"], "--", "bash", "-lc", cmd]
    return ["bash", "-c", cmd]


def cmd_run(lab, name, target, code=None, dry_run=False, **kw):
    name, prof = resolve_profile(lab, name)
    probs = static_problems(name, prof)
    if probs:
        raise EnvError("; ".join(probs))
    if code is None and not target:
        raise EnvError("give a script path or -c CODE")
    if code is not None and target:
        raise EnvError("give either a script path or -c CODE, not both")
    argv = run_command(lab, name, prof, target, code=code, **kw)
    if target:
        rel = _inside(lab, target[0])
        run_prof = lab.policy.get("run")
        if _is_experiment(lab, rel) and run_prof and run_prof != name:
            warn("experiments run on the policy.run profile (%s) through the queue; "
                 "running %s on %s anyway (probe or test use only)" % (run_prof, rel, name))
    if dry_run:
        print(json.dumps(argv))
        return 0
    return subprocess.call(argv)


def conda_spec(lab):
    """(packages, check script or None) for the home's conda env, from its domain packs:
    ``domains/<d>/computation/env.txt`` (one conda package spec per line, ``#``
    comments) and the optional ``env-check.py`` beside it. The academy names no
    package itself."""
    pkgs, check = [], None
    roots = [os.path.dirname(os.path.dirname(HERE)), ac.repo_root()]   # this marketplace first
    for d in lab.cfg.get("domains") or []:
        bases = [os.path.join(r, "domains", d, "computation") for r in roots]
        base = next((b for b in bases if os.path.isfile(os.path.join(b, "env.txt"))), None)
        if not base:
            continue
        path = os.path.join(base, "env.txt")
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                word = line.split("#", 1)[0].strip()
                if word and word not in pkgs:
                    pkgs.append(word)
        if check is None and os.path.isfile(os.path.join(base, "env-check.py")):
            check = os.path.join(base, "env-check.py")
    if not pkgs:
        raise EnvError("no domain pack of this home names conda packages "
                       "(domains/<pack>/computation/env.txt for %s)"
                       % ", ".join(lab.cfg.get("domains") or ["no domain"]))
    return pkgs, check


def cmd_setup(lab, name, dry_run=False):
    """Install the profile's conda env with the plugin's setup_env.sh and the domain
    packs' package list. On an ssh worker: init the remote repo, push HEAD, copy the
    installer (and the pack's check) to <fsqHome>/bin and run it there."""
    name, prof = resolve_profile(lab, name)
    kind = prof.get("kind")
    envname = prof.get("env") or prof.get("conda")
    if not envname:
        raise EnvError("profile %s names no conda env (conda, or the worker's conda.env)"
                       % name)
    pkgs, check = conda_spec(lab)
    assign = "ACADEMY_CONDA_ENV=%s ACADEMY_CONDA_PKGS=%s " % (Q(envname), Q(" ".join(pkgs)))
    if prof.get("prefix"):
        assign = "MINIFORGE_PREFIX=%s " % Q(prof["prefix"]) + assign
    if kind != "ssh":
        conv = wsl_path if kind == "wsl" else (lambda x: x)
        if check:
            assign += "ACADEMY_CONDA_CHECK=%s " % Q(conv(check))
        cmd = "%sbash %s" % (assign, Q(conv(SETUP_SH)))
        argv = (["wsl.exe", "-d", prof["distro"], "--", "bash", "-lc", cmd] if kind == "wsl"
                else ["bash", "-c", cmd])
        if dry_run:
            print(json.dumps([argv]))
            return 0
        return subprocess.call(argv)
    t = Transport(prof)
    repo = prof.get("repo") or "~/" + os.path.basename(os.path.abspath(lab.home))
    rel = re.sub(r"^~/", "", repo)
    rc, head = git(lab.home, "rev-parse", "HEAD")
    head = head.strip()
    push_url = prof.get("pushUrl") or "%s:%s" % (t.dest, rel)
    bindir = "%s/bin" % (lab.queue_cfg.get("fsqHome") or "~/fsq")
    if check:
        assign += "ACADEMY_CONDA_CHECK=%s/academy-env-check.py " % bindir
    steps = [t.argv("git init -q %s && mkdir -p %s" % (repo, bindir)),
             ["git", "-C", lab.home, "push", "--quiet", push_url, "+HEAD:refs/heads/laptop"],
             t.argv("cd %s && git checkout -q --detach %s" % (repo, head)),
             t.scp_argv(SETUP_SH, "%s/academy-setup-env.sh" % bindir)]
    if check:
        steps.append(t.scp_argv(check, "%s/academy-env-check.py" % bindir))
    steps.append(t.argv("%sbash %s/academy-setup-env.sh" % (assign, bindir)))
    if dry_run:
        print(json.dumps(steps))
        return 0
    for i, argv in enumerate(steps):
        rc = subprocess.call(argv)
        if rc:
            say("setup step %d failed (exit %d): %s" % (i + 1, rc, " ".join(argv)))
            return rc
    return 0


def cmd_gateway(lab, profile=None, probe=False, quiet=False):
    """Check the gateway of a profile (default: the run profile): 0 up, 1 down, 2 cannot
    tell. Down prints the gateway's onDown."""
    name, prof = resolve_profile(lab, profile or "run")
    if not prof.get("_gateway"):
        if not quiet:
            say("profile %s has no gateway: nothing to check" % name)
        return 0
    code, msg = run_gateway(prof, probe=probe)
    if not quiet:
        say(msg)
        if code == 1:
            say(wk.on_down(prof, lab.compute, name))
    return code


cmd_vpn = cmd_gateway       # the older name


# ----------------------------------------------------------------------------
# The queue (the fsq runner protocol of queue.ps1)
# ----------------------------------------------------------------------------

class Queue(object):
    def __init__(self, lab, profile=None):
        self.lab = lab
        self.home = lab.home
        self.name, self.prof = resolve_profile(lab, profile or "run")
        probs = static_problems(self.name, self.prof)
        if probs:
            raise EnvError("; ".join(probs))
        self.t = Transport(self.prof)
        self.host = self.t.host
        self.qdir = lab.qdir
        self.remote_repo = self.prof.get("repo") or "~/" + os.path.basename(os.path.abspath(lab.home))
        self.remote_rel = re.sub(r"^~/", "", self.remote_repo)
        self.fsq_home = lab.queue_cfg.get("fsqHome") or "~/fsq"
        self.fsq_bin = "%s/bin/fsq" % self.fsq_home
        self.max_jobs = int(self.prof.get("maxJobs") or lab.queue_cfg.get("maxJobs") or 1)
        self.prefix = self.prof.get("prefix")
        self.conda_env = self.prof.get("env") or self.prof.get("conda")
        self.remote_env = self.prof.get("remoteEnv") or ""
        self.push_url = self.prof.get("pushUrl") or "%s:%s" % (self.t.dest, self.remote_rel)
        self.rc = 0
        self.remote_paused = False
        self.remote_max = None

    # -- local job files -------------------------------------------------------
    def ensure_dirs(self):
        for d in ("pending", "running", "done"):
            os.makedirs(os.path.join(self.qdir, d), exist_ok=True)

    def load_jobs(self, state):
        d = os.path.join(self.qdir, state)
        out = []
        if not os.path.isdir(d):
            return out
        for f in sorted(os.listdir(d)):
            if not f.endswith(".json"):
                continue
            path = os.path.join(d, f)
            try:
                with open(path, "r", encoding="utf-8-sig") as fh:
                    job = json.load(fh)
            except (OSError, ValueError) as exc:
                warn("unreadable job file %s: %s" % (path, exc))
                continue
            job["_path"] = path
            out.append(job)
        return out

    def save(self, job, state):
        old = job.pop("_path", None)
        path = os.path.join(self.qdir, state, "%s.json" % job["id"])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(job, indent=4, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
        if old and os.path.normcase(os.path.abspath(old)) != os.path.normcase(
                os.path.abspath(path)) and os.path.exists(old):
            os.remove(old)
        job["_path"] = path
        return path

    @staticmethod
    def job_args(job):
        a = job.get("args")
        if a is None:
            return []
        if not isinstance(a, list):
            a = [a]
        return [str(x) for x in a if x is not None and x != ""]

    # -- add / list ------------------------------------------------------------
    def build_job(self, script, args, label, note, now=None):
        """(path it would be written to, job) for a new pending job; writes nothing."""
        rel = _inside(self.lab, script)
        args_ = [a for a in (args or []) if a != "--"]
        if len(args_) == 1 and re.search(r"\s", args_[0]):
            args_ = [w for w in re.split(r"\s+", args_[0]) if w]
        stem = os.path.splitext(rel.rsplit("/", 1)[-1])[0]
        jid = "%s_%s" % (now or time.strftime("%Y%m%d-%H%M%S"), stem)
        if glob.glob(os.path.join(glob.escape(self.qdir), "*", glob.escape(jid) + ".json")):
            raise EnvError("A job with id %s exists already; wait a second and add again."
                           % jid)
        job = {"id": jid, "script": rel, "args": args_,
               "label": label if label is not None else "",
               "note": note if note is not None else "",
               "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "status": "pending",
               "started": None, "commit": None, "log": None, "finished": None,
               "result": None}
        return os.path.join(self.qdir, "pending", jid + ".json"), job

    def committed(self, rel):
        """(dirty, tracked) of a home-relative path."""
        _rc, dirty = git(self.home, "status", "--porcelain", "--", rel)
        _rc, tracked = git(self.home, "ls-files", "--", rel)
        return bool(dirty.strip()), bool(tracked.strip())

    def add(self, script, args, label, note, dry_run=False):
        path, job = self.build_job(script, args, label, note)
        dirty, tracked = self.committed(job["script"])
        if dry_run:
            print(json.dumps({"path": path.replace("\\", "/"), "job": job,
                              "committed": tracked and not dirty}, indent=1))
            return 0
        self.ensure_dirs()
        self.save(job, "pending")
        say("queued %s  (%s %s)" % (job["id"], job["script"], " ".join(job["args"])))
        if dirty or not tracked:
            warn("%s is uncommitted; tick skips it until it is committed (the remote runs "
                 "HEAD)." % job["script"])
        return 0

    @staticmethod
    def _s(v):
        return "" if v is None else str(v)

    def list_lines(self):
        out = []
        for d in ("pending", "running", "done"):
            for j in self.load_jobs(d):
                if d == "running" and "remoteState" in j:
                    st = j["remoteState"]
                elif d == "done":
                    st = j.get("status")
                else:
                    st = d
                out.append("%-8s %-10s %s  %s %s  [%s]  %s" % (
                    d, self._s(st), self._s(j.get("id")), self._s(j.get("script")),
                    " ".join(self.job_args(j)), self._s(j.get("label")),
                    self._s(j.get("note"))))
        return out

    # -- the remote --------------------------------------------------------------
    def remote(self, cmd):
        self.rc, lines = self.t.remote(cmd)
        return lines

    def fsq(self, argline):
        envp = (self.remote_env + " ") if self.remote_env else ""
        return self.remote("%s%s %s" % (envp, self.fsq_bin, argline))

    def why_unreachable(self):
        """Why the last reachability check failed, and what to do about it."""
        gw = self.prof.get("_gateway")
        if gw and self.t.why and not self.t.why.startswith("ssh exit"):
            return "gateway %s down; %s" % (gw["name"],
                                            wk.on_down(self.prof, self.lab.compute, self.name))
        return self.t.why or "ssh failed"

    def require_reachable(self):
        if not self.t.reachable():
            n = len(self.load_jobs("pending"))
            say("unreachable: %s (%s) -- %d pending job(s) wait."
                % (self.host, self.why_unreachable(), n))
            raise Exit(1)

    def require_deployed(self):
        want = sha256(RUNNER)
        lines = self.fsq("version")
        got = lines[-1] if lines else ""
        if self.rc != 0 or got.strip() != want:
            say("the runner on %s is missing or differs from the plugin's fsq.sh (remote: %s)."
                " Deploying it is %s's call: env.py queue deploy."
                % (self.host, got, self.lab.compute.human))
            raise Exit(1)

    def remote_status(self):
        lines = self.fsq("status")
        if self.rc != 0:
            raise RemoteFailure("fsq status failed on %s:\n%s" % (self.host, "\n".join(lines)))
        spool = {}
        self.remote_paused, self.remote_max = False, None
        for l in lines:
            if l == "#paused":
                self.remote_paused = True
                continue
            if l.startswith("#max"):
                parts = l.split("\t")
                self.remote_max = parts[1] if len(parts) > 1 else None
                continue
            f = l.split("\t")
            if len(f) < 9:
                continue
            spool[f[0]] = {"id": f[0], "state": f[1], "status": f[2], "exit": f[3],
                           "commit": f[4], "submitted": f[5], "started": f[6],
                           "finished": f[7], "files": [x for x in f[8].split(",") if x]}
        return spool

    def submit(self, j):
        dirty, _tracked = self.committed(j["script"])
        if dirty:
            say("skip (uncommitted): %s" % j["id"])
            return
        rc, _ = git(self.home, "cat-file", "-e", "HEAD:%s" % j["script"])
        if rc:
            say("skip (not in HEAD): %s" % j["id"])
            return
        _rc, head = git(self.home, "rev-parse", "HEAD")
        head = head.strip()
        p = subprocess.run(["git", "-C", self.home, "push", "--quiet", self.push_url,
                            "+%s:refs/fsq/%s" % (head, j["id"])])
        if p.returncode:
            warn("push of %s failed (exit %d); it stays pending." % (j["id"], p.returncode))
            return
        words = [j["id"], head, j["script"]] + self.job_args(j)
        out = self.fsq("submit " + " ".join(Q(w) for w in words))
        if self.rc != 0:
            warn("submit of %s returned exit %d; reconciling with the remote spool. %s"
                 % (j["id"], self.rc, " ".join(out)))
        else:
            say("\n".join(out))

    def reconcile(self, spool):
        for j in self.load_jobs("pending") + self.load_jobs("running"):
            r = spool.get(j["id"])
            was_running = os.sep + "running" + os.sep in j["_path"]
            if not r:
                if was_running:
                    if "remoteState" in j:
                        warn("%s is running here but unknown on %s (spool lost?). Not "
                             "resubmitted; move it back to queue/pending by hand if it should "
                             "run again." % (j["id"], self.host))
                    else:
                        warn("%s was started by the old run.ps1 -Detach path and is not in "
                             "the runner's spool; settle it by hand." % j["id"])
                continue
            j["remoteState"] = r["state"]
            j["commit"] = r["commit"][:7]
            j["submitted"] = r["submitted"]
            if r["started"]:
                j["started"] = r["started"]
            if r["state"] in ("pending", "running", "incomplete"):
                j["status"] = "running" if r["state"] == "running" else "queued"
                self.save(j, "running")
                say("%-8s %s" % (r["state"], j["id"]))
                continue
            if r["state"] == "done":
                self.collect(j, r)
                continue
            if r["state"] == "collected":
                warn("%s is already collected on %s but not done here; its files are in "
                     "%s/collected/%s/files." % (j["id"], self.host, self.fsq_home, j["id"]))
        for j in self.load_jobs("done"):
            r = spool.get(j["id"])
            if r and r["state"] == "done":
                self.fsq("ack %s" % Q(j["id"]))

    def collect(self, j, r):
        blocked = False
        for f in r["files"]:
            dest = os.path.join(self.home, *f.split("/"))
            if os.path.exists(dest):
                _rc, dirty = git(self.home, "status", "--porcelain", "--", f)
                if dirty.strip():
                    warn("%s has uncommitted changes here; not overwritten. %s stays unsettled "
                         "until that is resolved." % (f, j["id"]))
                    blocked = True
        if blocked:
            return
        for f in r["files"]:
            dest = os.path.join(self.home, *f.split("/"))
            if not self.t.copy_from("%s/done/%s/files/%s" % (self.fsq_home, j["id"], f), dest):
                warn("copy of %s failed; %s stays unsettled." % (f, j["id"]))
                return
            say("fetched %s" % f)
        stem = os.path.splitext(j["script"].rsplit("/", 1)[-1])[0]
        if "results/%s.json" % stem in r["files"]:
            main = "results/%s.json" % stem
        else:
            import fnmatch
            hits = [f for f in r["files"] if fnmatch.fnmatchcase(f, "results/%s/*.json" % stem)]
            main = hits[0] if hits else None
        j["files"] = r["files"]
        j["exit"] = r["exit"]
        j["finished"] = r["finished"]
        j["result"] = main
        j["status"] = "exited-without-result" if r["status"] == "ok" and not main \
            else r["status"]
        j["log"] = "%s/collected/%s/log" % (self.fsq_home, j["id"])
        self.save(j, "done")
        self.fsq("ack %s" % Q(j["id"]))
        if j["result"]:
            say("done: %s -> %s" % (j["id"], j["result"]))
        else:
            say("done: %s (%s, exit %s); log: env.py queue log %s"
                % (j["id"], j["status"], r["exit"], j["id"]))

    # -- the actions --------------------------------------------------------------
    def do_list(self):
        for l in self.list_lines():
            say(l)
        return 0

    def do_check(self):
        if self.t.reachable():
            say("reachable: %s" % self.host)
            return 0
        say("unreachable: %s (%s)" % (self.host, self.why_unreachable()))
        return 1

    def do_log(self, prefix):
        hits = [j for j in self.load_jobs("running") + self.load_jobs("done")
                if str(j.get("id", "")).startswith(prefix)]
        if not hits:
            raise EnvError("No submitted job matching '%s'." % prefix)
        j = hits[0]
        self.require_reachable()
        if "remoteState" not in j and j.get("log"):
            lines = self.remote("tail -n 40 %s" % j["log"])
        else:
            lines = self.fsq("log %s 40" % Q(j["id"]))
        for l in lines:
            say(l)
        return self.rc

    def do_status(self):
        self.require_reachable()
        self.require_deployed()
        for l in self.fsq("status --all"):
            say(l)
        return self.rc

    def do_pause(self, pause):
        self.require_reachable()
        self.require_deployed()
        for l in self.fsq("pause" if pause else "resume"):
            say(l)
        return self.rc

    def do_tick(self, submit=True):
        self.require_reachable()
        self.require_deployed()
        spool = self.remote_status()
        if submit:
            submitted = False
            for j in self.load_jobs("pending"):
                if j["id"] in spool:
                    continue            # already accepted there; never again
                self.submit(j)
                submitted = True
            if submitted:
                spool = self.remote_status()
        self.reconcile(spool)
        if self.remote_paused:
            say("note: the remote spool is paused (env.py queue resume).")
        if self.remote_max is not None and str(self.remote_max) != str(self.max_jobs):
            say("note: remote max is %s, the profile says %s (redeploy, or fsq set-max on the "
                "host)." % (self.remote_max, self.max_jobs))
        return 0

    def do_preflight(self, deploy=False, cron=True):
        self.require_reachable()
        cron_flag = " --cron" if deploy and cron else ""
        pfx = " --prefix %s" % Q(self.prefix) if self.prefix else ""
        if self.conda_env:
            pfx += " --env %s" % Q(self.conda_env)
        self.remote("mkdir -p %s/bin" % self.fsq_home)
        if not self.t.copy_to(RUNNER, "%s/bin/fsq.new" % self.fsq_home):
            raise RemoteFailure("could not copy the runner to %s." % self.host)
        out = self.remote("chmod +x %s/bin/fsq.new && %s/bin/fsq.new preflight --repo %s%s%s"
                          % (self.fsq_home, self.fsq_home, self.remote_repo, pfx, cron_flag))
        pf_code = self.rc
        for l in out:
            say(l)
        if pf_code != 0 or not deploy:
            self.remote("rm -f %s/bin/fsq.new" % self.fsq_home)
            if pf_code != 0:
                say("preflight failed on %s; nothing deployed." % self.host)
                return 1
            return 0
        for l in self.remote("mv -f %s/bin/fsq.new %s && %s init --repo %s --max %d%s"
                             % (self.fsq_home, self.fsq_bin, self.fsq_bin, self.remote_repo,
                                self.max_jobs, pfx)):
            say(l)
        if self.rc != 0:
            raise RemoteFailure("fsq init failed on %s." % self.host)
        if cron:
            for l in self.fsq("cron-install"):
                say(l)
            if self.rc != 0:
                raise RemoteFailure("cron-install failed on %s." % self.host)
        v = self.fsq("version")
        say("deployed %s (%s)." % (self.fsq_bin, v[-1] if v else "?"))
        say("A fresh spool starts paused: env.py queue resume lets jobs start.")
        return 0


LEGACY_VALUE = {"-add": "add", "-label": "label", "-note": "note", "-log": "log"}
LEGACY_SWITCH = ("-list", "-check", "-tick", "-fetch", "-status", "-setup", "-preflight",
                 "-deploy", "-nocron", "-pause", "-resume")
LEGACY_ORDER = ("add", "list", "check", "log", "setup", "deploy", "preflight", "pause",
                "resume", "status", "tick", "fetch")


def parse_queue(argv):
    """(action, options) from the subcommand form or the legacy queue.ps1 flags."""
    opts = {"label": None, "note": None, "args": [], "profile": None, "dry_run": False,
            "cron": True, "script": None, "id": None}
    argv = list(argv)
    if argv[:1] == ["--profile"] and len(argv) > 1:
        opts["profile"] = argv[1]
        argv = argv[2:]
    if not argv:
        raise EnvError("queue needs a subcommand: add, list, check, tick, fetch, status, "
                       "log, preflight, deploy, pause, resume, setup")
    first = argv[0].lower()
    if first in LEGACY_VALUE or first in LEGACY_SWITCH or first == "-scriptargs":
        seen = set()
        i = 0
        in_args = False
        while i < len(argv):
            tok, low = argv[i], argv[i].lower()
            if low in LEGACY_VALUE:
                if i + 1 >= len(argv):
                    raise EnvError("%s needs a value" % tok)
                key = LEGACY_VALUE[low]
                val = argv[i + 1]
                if key == "add":
                    opts["script"] = val
                elif key == "log":
                    opts["id"] = val
                else:
                    opts[key] = val
                if key in ("add", "log"):
                    seen.add(key)
                i += 2
                in_args = False
                continue
            if low in LEGACY_SWITCH:
                if low == "-nocron":
                    opts["cron"] = False
                else:
                    seen.add(low[1:])
                i += 1
                in_args = False
                continue
            if low == "-scriptargs":
                in_args = True
                i += 1
                continue
            opts["args"].append(tok)       # ValueFromRemainingArguments
            i += 1
        for act in LEGACY_ORDER:
            if act in seen:
                return act, opts
        return "none", opts
    action = first
    rest = argv[1:]
    if "--" in rest:
        k = rest.index("--")
        opts["args"] = rest[k + 1:]
        rest = rest[:k]
    i = 0
    positional = []
    while i < len(rest):
        tok = rest[i]
        if tok in ("--label", "--note", "--args", "--profile") and i + 1 < len(rest):
            val = rest[i + 1]
            if tok == "--args":
                opts["args"] = [val] + opts["args"]
            else:
                opts[tok[2:]] = val
            i += 2
            continue
        if tok.startswith("--args="):
            opts["args"] = [tok[len("--args="):]] + opts["args"]
        elif tok == "--dry-run":
            opts["dry_run"] = True
        elif tok == "--no-cron":
            opts["cron"] = False
        else:
            positional.append(tok)
        i += 1
    if action == "add":
        if not positional:
            raise EnvError("queue add needs a script path")
        opts["script"] = positional[0]
        opts["args"] = positional[1:] + opts["args"]
    elif action == "log":
        if not positional:
            raise EnvError("queue log needs a job id (or a prefix)")
        opts["id"] = positional[0]
    return action, opts


def cmd_queue(lab, argv):
    action, o = parse_queue(argv)
    if action == "setup":
        return cmd_setup(lab, o["profile"] or "run", dry_run=o["dry_run"])
    q = Queue(lab, o["profile"])
    if action == "add":
        if not o["dry_run"]:
            q.ensure_dirs()
        return q.add(o["script"], o["args"], o["label"], o["note"], dry_run=o["dry_run"])
    q.ensure_dirs()
    if action == "list":
        return q.do_list()
    if action == "check":
        return q.do_check()
    if action == "log":
        return q.do_log(o["id"])
    if action == "status":
        return q.do_status()
    if action in ("pause", "resume"):
        return q.do_pause(action == "pause")
    if action in ("tick", "fetch"):
        return q.do_tick(submit=action == "tick")
    if action in ("preflight", "deploy"):
        return q.do_preflight(deploy=action == "deploy", cron=o["cron"])
    say("Nothing to do. See: py env.py --help")
    return 2


LEGACY_RUN_VALUE = {"-code": "-c", "-target": None, "-distro": None, "-prefix": "--prefix",
                    "-envname": "--conda", "-remoterepo": None}
LEGACY_RUN_SWITCH = {"-sage": "--sage", "-u": "-u", "-unbuffered": "-u"}


def _legacy_run(lab, rest):
    """True when ``run`` got run.ps1-style arguments (as ``lab.py cmd run`` passes)."""
    first = rest[0]
    low = first.lower()
    if low in LEGACY_RUN_VALUE or low in LEGACY_RUN_SWITCH:
        return True
    if first in lab.envs or first in lab.policy or re.match(r"^(wsl|ssh)(:|$)", first):
        return False
    return first.endswith(".py") or "/" in first or "\\" in first


def translate_legacy_run(rest):
    """run.ps1 arguments -> ``PROFILE [options] [--] [SCRIPT ARGS]`` (profile from -Target,
    default ``wsl``, or ``wsl:<distro>`` with -Distro)."""
    target, distro, opts, pos = "wsl", None, [], []
    i = 0
    while i < len(rest):
        tok, low = rest[i], rest[i].lower()
        if low in LEGACY_RUN_VALUE and i + 1 < len(rest):
            val = rest[i + 1]
            if low == "-target":
                target = val
            elif low == "-distro":
                distro = val
            elif LEGACY_RUN_VALUE[low]:
                opts += [LEGACY_RUN_VALUE[low], val]
            i += 2
            continue
        if low in LEGACY_RUN_SWITCH:
            opts.append(LEGACY_RUN_SWITCH[low])
        elif tok == "--dry-run" and not pos:
            # Only env.py's own --dry-run, before the script path, is an option here.
            # Once the script has been seen, a later "--dry-run" is the script's own
            # argument (run.ps1 passed script arguments after the script unchanged;
            # nothing here should reinterpret them as env.py's flags).
            opts.append(tok)
        elif tok != "--":
            pos.append(tok)
        i += 1
    if target == "wsl" and distro:
        target = "wsl:%s" % distro
    return [target] + opts + (["--"] + pos if pos else [])


# ----------------------------------------------------------------------------

USAGE = __doc__.split("Usage::")[1].split("Queue subcommands")[0]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    home = None
    while argv and argv[0] in ("--home",):
        if len(argv) < 2:
            print("error: --home needs a directory", file=sys.stderr)
            return 2
        home = argv[1]
        argv = argv[2:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0 if argv else 2
    sub, rest = argv[0], argv[1:]
    try:
        lab = load_lab(home)
        if sub == "list":
            return cmd_list(lab, as_json="--json" in rest)
        if sub == "check":
            names = [a for a in rest if not a.startswith("--")]
            return cmd_check(lab, names[0] if names else "run", live="--live" in rest)
        if sub in ("gateway", "vpn"):
            low = [a.lower() for a in rest]
            prof = rest[low.index("--profile") + 1] if "--profile" in low else None
            return cmd_gateway(lab, prof, probe="--probe" in low or "-probe" in low,
                               quiet="--quiet" in low or "-quiet" in low)
        if sub == "setup":
            names = [a for a in rest if not a.startswith("--")]
            return cmd_setup(lab, names[0] if names else "run", dry_run="--dry-run" in rest)
        if sub == "queue":
            return cmd_queue(lab, rest)
        if sub == "run":
            if not rest:
                raise EnvError("run needs a profile")
            if _legacy_run(lab, rest):
                rest = translate_legacy_run(rest)
            name, rest = rest[0], rest[1:]
            kw = {"sage": False, "unbuffered": False, "conda": None, "prefix": None}
            code, dry = None, False
            while rest and rest[0].startswith("-"):
                tok = rest.pop(0)
                if tok == "--sage":
                    kw["sage"] = True
                elif tok in ("-u", "--unbuffered"):
                    kw["unbuffered"] = True
                elif tok == "--dry-run":
                    dry = True
                elif tok in ("--conda", "--prefix") and rest:
                    kw[tok[2:]] = rest.pop(0)
                elif tok == "-c" and rest:
                    code = rest.pop(0)
                elif tok == "--":
                    break
                else:
                    raise EnvError("unknown run option %s" % tok)
            return cmd_run(lab, name, rest, code=code, dry_run=dry, **kw)
        raise EnvError("unknown command %r\n%s" % (sub, USAGE))
    except Exit as e:
        return e.code
    except RemoteFailure as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except EnvError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
