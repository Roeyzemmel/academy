"""workers.py -- remote workers and the gateways in front of them (docs/config.md, "compute").

The academy implements the mechanism; a workspace supplies the machines. The
concrete values (which host, which user, where the conda env is, which VPN guards
it, whom to ask when it is down) live in the workspace's ``workspace.json`` under
``compute``, never in a plugin::

    "compute": {
      "workers":  {"<worker>":  {"transport": "ssh", "host": "...", "user": "...",
                                 "remoteRoot": "~", "maxJobs": 1,
                                 "conda": {"prefix": "...", "env": "..."},
                                 "gateway": "<gateway>"}},
      "gateways": {"<gateway>": {"kind": "vpn", "client": "globalprotect",
                                 "check": "globalprotect", "probeHost": "host:22",
                                 "owner": "...", "onDown": "..."}}
    }

A home's env profile refers to a worker by name: ``scientist.envs.<profile> =
{"worker": "<worker>"}`` (any other key there overrides the worker's value for that
home). ``expand_profile`` turns that into the ssh profile env.py speaks; an inline
ssh profile (``{"kind": "ssh", "host": ...}``) keeps working and may name a
``gateway`` too, or the older ``preflight: "vpn:<check>"``.

A gateway is checked locally before anything is sent to its worker (0 up, 1 down,
2 cannot tell): ``kind`` is ``vpn`` or ``none``; a vpn's ``check`` (default: its
``client``) is one of

    globalprotect  the GlobalProtect adapter's status (Windows: vpn.ps1; elsewhere the
                   ``globalprotect`` CLI when installed), no network round trip
    openconnect    an ``openconnect`` process is running
    tcp-reachable  a TCP connection to ``probeHost`` (host:port) opens within
                   ``timeoutMs`` (default 4000)
    command        ``command`` (a shell line) exits 0 (up) or 1 (down)

``probeHost`` is also what ``--probe`` connects to after a local check says up.
``onDown`` is what the agent tells the human when the gateway is down; ``{owner}``,
``{human}``, ``{gateway}`` and ``{worker}`` are filled in. ``owner`` defaults to the
workspace's ``human.name``.
"""

import os
import shutil
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402

TRANSPORTS = ("ssh",)
GATEWAY_KINDS = ("vpn", "none")
VPN_CHECKS = ("globalprotect", "openconnect", "tcp-reachable", "command")
WORDS = {0: "up", 1: "down", 2: "cannot tell"}
VPN_PS1 = os.path.join(HERE, "vpn.ps1")
DEFAULT_ON_DOWN = "ask {owner} to bring up {gateway}; jobs for {worker} wait in the queue"
HINT = ("a remote worker is defined once in the workspace's workspace.json under "
        "compute.workers (with its gateway under compute.gateways), and a home names it "
        "with scientist.envs.<profile> = {\"worker\": \"<name>\"} (docs/config.md, "
        "\"compute\")")


class WorkerError(Exception):
    """A worker or gateway is missing or malformed."""


class Compute(object):
    """The workspace's compute block, and whom to ask."""

    def __init__(self, block=None, human="the human", path=None):
        block = block if isinstance(block, dict) else {}
        self.workers = block.get("workers") if isinstance(block.get("workers"), dict) else {}
        self.gateways = block.get("gateways") if isinstance(block.get("gateways"), dict) \
            else {}
        self.human = human or "the human"
        self.path = path

    @property
    def where(self):
        return "%s compute" % (self.path or "workspace.json")


def load_compute(workspace=None):
    """The ``Compute`` of ``workspace`` (a loaded workspace dict), else of the
    workspace.json ``academy_common.load_workspace`` finds; empty when there is none."""
    ws = workspace
    if ws is None:
        try:
            ws = ac.load_workspace()
        except ac.AcademyError:
            ws = None
    if not isinstance(ws, dict):
        return Compute()
    human = (ws.get("human") or {}).get("name") or "the human"
    return Compute(ws.get("compute"), human, ws.get("_path"))


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------

def gateway_problems(name, gw):
    if not isinstance(gw, dict):
        return ["gateway %s is not an object" % name]
    kind = gw.get("kind")
    if kind not in GATEWAY_KINDS:
        return ["gateway %s: kind must be one of %s" % (name, ", ".join(GATEWAY_KINDS))]
    probs = []
    if kind == "vpn":
        check = gw.get("check") or gw.get("client")
        if check not in VPN_CHECKS:
            probs.append("gateway %s: check (or client) must be one of %s"
                         % (name, ", ".join(VPN_CHECKS)))
        elif check == "tcp-reachable" and not _split_hostport(gw.get("probeHost")):
            probs.append("gateway %s: check tcp-reachable needs probeHost host:port" % name)
        elif check == "command" and not gw.get("command"):
            probs.append("gateway %s: check command needs command" % name)
    if gw.get("probeHost") and not _split_hostport(gw.get("probeHost")):
        probs.append("gateway %s: probeHost must be host:port" % name)
    return probs


def worker_problems(name, w, compute):
    if not isinstance(w, dict):
        return ["worker %s is not an object" % name]
    probs = []
    if (w.get("transport") or "ssh") not in TRANSPORTS:
        probs.append("worker %s: transport must be one of %s" % (name, ", ".join(TRANSPORTS)))
    if not w.get("host"):
        probs.append("worker %s needs host" % name)
    conda = w.get("conda")
    if conda is not None and not isinstance(conda, dict):
        probs.append("worker %s: conda must be {prefix, env}" % name)
    mj = w.get("maxJobs")
    if mj is not None and not (isinstance(mj, int) and 1 <= mj <= 3):
        probs.append("worker %s: maxJobs must be an integer 1..3" % name)
    gw = w.get("gateway")
    if gw and gw not in compute.gateways:
        probs.append("worker %s: gateway %r is not in compute.gateways" % (name, gw))
    return probs


def compute_problems(compute):
    probs = []
    for name in sorted(compute.workers):
        probs += worker_problems(name, compute.workers[name], compute)
    for name in sorted(compute.gateways):
        probs += gateway_problems(name, compute.gateways[name])
    return probs


# ----------------------------------------------------------------------------
# Profiles
# ----------------------------------------------------------------------------

def _gateway(name, compute):
    gw = compute.gateways.get(name)
    if gw is None:
        raise WorkerError("gateway %r is not in %s.gateways; %s" % (name, compute.where, HINT))
    out = dict(gw)
    out["name"] = name
    return out


def expand_profile(name, prof, compute, home=None):
    """The ssh profile env.py runs for ``prof``: a worker reference resolved against
    ``compute``, an inline profile's ``gateway`` resolved, anything else unchanged.
    The resolved gateway is under ``_gateway``. Raises WorkerError."""
    if not isinstance(prof, dict):
        return prof
    if "worker" in prof:
        wname = prof.get("worker")
        w = compute.workers.get(wname) if isinstance(wname, str) else None
        if w is None:
            raise WorkerError("profile %s names worker %r, which %s.workers does not define; %s"
                              % (name, wname, compute.where, HINT))
        probs = worker_problems(wname, w, compute)
        if probs:
            raise WorkerError("; ".join(probs))
        conda = w.get("conda") or {}
        out = {"kind": "ssh", "worker": wname, "host": w["host"]}
        for src, dst in ((w.get("user"), "user"), (conda.get("prefix"), "prefix"),
                         (conda.get("env"), "env"), (w.get("maxJobs"), "maxJobs"),
                         (w.get("gateway"), "gateway"), (w.get("pushUrl"), "pushUrl"),
                         (w.get("remoteEnv"), "remoteEnv")):
            if src not in (None, ""):
                out[dst] = src
        if w.get("remoteRoot") and home:
            out["repo"] = "%s/%s" % (str(w["remoteRoot"]).rstrip("/"),
                                     os.path.basename(os.path.abspath(home)))
        for k, v in prof.items():
            if k != "worker":
                out[k] = v
    else:
        out = dict(prof)
    gw = out.get("gateway")
    if gw:
        out["_gateway"] = _gateway(gw, compute)
    elif out.get("preflight"):
        check = str(out["preflight"]).partition(":")[2]
        out["_gateway"] = {"name": str(out["preflight"]), "kind": "vpn", "check": check}
    return out


def gateway_label(prof):
    gw = prof.get("_gateway")
    return gw["name"] if gw else None


def on_down(prof, compute, profile_name=None):
    """The onDown message of ``prof``'s gateway, filled in."""
    gw = prof.get("_gateway") or {}
    owner = gw.get("owner") or compute.human
    text = gw.get("onDown") or DEFAULT_ON_DOWN
    for key, val in (("owner", owner), ("human", compute.human),
                     ("gateway", gw.get("name") or "the gateway"),
                     ("worker", prof.get("worker") or profile_name or prof.get("host") or "")):
        text = text.replace("{%s}" % key, str(val))
    return text


# ----------------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------------

def _split_hostport(s):
    if not isinstance(s, str) or ":" not in s:
        return None
    host, _, port = s.rpartition(":")
    if not host or not port.isdigit():
        return None
    return host.strip("[]"), int(port)


def tcp_reachable(hostport, timeout_ms=4000):
    hp = _split_hostport(hostport)
    if not hp:
        return 2, "cannot tell (probeHost %r is not host:port)" % hostport
    try:
        with socket.create_connection(hp, timeout=timeout_ms / 1000.0):
            return 0, "%s reachable" % hostport
    except socket.timeout:
        return 1, "%s did not answer in %dms" % (hostport, timeout_ms)
    except OSError as exc:
        return 1, "%s refused (%s)" % (hostport, exc)


def _run(argv, shell=False, timeout=60):
    try:
        p = subprocess.run(argv, shell=shell, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    return p.returncode, (p.stdout or p.stderr or "").strip()


def _check_globalprotect(gw):
    if os.name == "nt":
        argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", VPN_PS1]
        if gw.get("adapter"):
            argv += ["-AdapterPattern", gw["adapter"]]
        rc, out = _run(argv)
        if rc is None:
            return 2, "cannot tell (%s)" % out
        lines = out.splitlines()
        return (rc if rc in (0, 1, 2) else 2), (lines[-1] if lines else "exit %d" % rc)
    cli = shutil.which("globalprotect")
    if not cli:
        return 2, "cannot tell (no GlobalProtect adapter check on this OS and no " \
                  "globalprotect CLI)"
    rc, out = _run([cli, "show", "--status"])
    if rc is None:
        return 2, "cannot tell (%s)" % out
    if "disconnected" in out.lower():
        return 1, "GlobalProtect disconnected"
    if "connected" in out.lower():
        return 0, "GlobalProtect connected"
    return 2, "cannot tell (globalprotect show --status: %s)" % (out[:80] or rc)


def _check_openconnect(gw):
    if os.name == "nt":
        rc, out = _run(["tasklist", "/FI", "IMAGENAME eq openconnect.exe"])
        if rc is None:
            return 2, "cannot tell (%s)" % out
        return (0, "openconnect running") if "openconnect.exe" in out.lower() \
            else (1, "no openconnect process")
    if not shutil.which("pgrep"):
        return 2, "cannot tell (no pgrep)"
    rc, _out = _run(["pgrep", "-x", "openconnect"])
    if rc == 0:
        return 0, "openconnect running"
    if rc == 1:
        return 1, "no openconnect process"
    return 2, "cannot tell (pgrep exit %s)" % rc


def check_gateway(gw, probe=False):
    """(code, message) of a gateway: 0 up, 1 down, 2 cannot tell.

    ``ACADEMY_FAKE_PREFLIGHT`` (0/1/2) stands in for the check in tests."""
    if not gw:
        return 0, "no gateway"
    name = gw.get("name") or "gateway"
    fake = os.environ.get("ACADEMY_FAKE_PREFLIGHT")
    if fake in ("0", "1", "2"):
        code = int(fake)
        return code, "%s: %s (fake preflight)" % (name, WORDS[code])
    probs = gateway_problems(name, gw)
    if probs:
        return 2, "%s: cannot tell (%s)" % (name, "; ".join(probs))
    if gw.get("kind") == "none":
        return 0, "%s: up (kind none, nothing to bring up)" % name
    check = gw.get("check") or gw.get("client")
    timeout = int(gw.get("timeoutMs") or 4000)
    if check == "tcp-reachable":
        code, msg = tcp_reachable(gw["probeHost"], timeout)
        return code, "%s: %s (%s)" % (name, WORDS[code], msg)
    if check == "command":
        rc, out = _run(gw["command"], shell=True)
        code = rc if rc in (0, 1) else 2
        return code, "%s: %s (command exit %s%s)" % (name, WORDS[code], rc,
                                                    ": " + out.splitlines()[-1] if out else "")
    code, msg = (_check_globalprotect(gw) if check == "globalprotect"
                 else _check_openconnect(gw))
    if code == 0 and probe and gw.get("probeHost"):
        pc, pmsg = tcp_reachable(gw["probeHost"], timeout)
        if pc != 0:
            return 1, "%s: up but %s" % (name, pmsg)
        msg = "%s; %s" % (msg, pmsg)
    return code, "%s: %s (%s)" % (name, WORDS[code], msg)
