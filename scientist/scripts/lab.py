"""lab.py -- where the lab is, which command runs an action, and what state it is in.

Usage::

    py lab.py home   [--home DIR] [--json]
    py lab.py cmd    [--home DIR] ACTION [ARGS ...]     ACTION: queue | run | vpn | check
    py lab.py status [--home DIR] [--board DIR] [--json]

``home`` prints the Scientist instance the session acts for (from --home, the cwd,
or workspace.json), its home, whether the home is switched over (has
``.claude/academy.json``), its domains and their pack folders, the env profiles and
the policy.

``cmd`` prints the one command line that performs ACTION today. With the plugin's
runner (``scripts/env.py``, Group C): ``py "<plugin>/scripts/env.py" --home "<home>"
ACTION ARGS`` for queue, run and vpn. ``env.py queue`` also takes the legacy
``queue.ps1`` flags, so ``cmd queue -List`` works unchanged; ``env.py run`` takes
``PROFILE SCRIPT [ARGS]``; ``env.py vpn`` takes ``-Quiet`` / ``-Probe``. check is
``py "<plugin>/scripts/check_experiments.py" --home "<home>" ARGS``. A plugin copy
without them falls back to the home's own ``scripts\\queue.ps1`` / ``run.ps1`` /
``vpn.ps1`` / ``check_experiments.py``, run from the home.

``status`` counts the local queue by state, the tickets addressed to the instance,
its open packets, and lists the result JSONs that no experiment-report packet on the
board refers to yet (newest first, at most ten).

Exit codes: 0 ok, 2 error (one line on stderr). Never contacts a remote host.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _common as c  # noqa: E402
from _common import ac  # noqa: E402

PLUGIN = os.path.dirname(HERE)
QUEUE_STATES = ("pending", "running", "done", "parked")
LEGACY = {"queue": ("powershell", "scripts/queue.ps1"),
          "run": ("powershell", "scripts/run.ps1"),
          "vpn": ("powershell", "scripts/vpn.ps1"),
          "check": ("py", "scripts/check_experiments.py")}


SAFE = re.compile(r"^[A-Za-z0-9_./:=@,+\-]+$")


def _q(s, shell="powershell"):
    """Quote one argument for the shell the command line is meant for."""
    if SAFE.match(s or ""):
        return s
    if shell == "powershell":
        return "'%s'" % s.replace("'", "''")
    return '"%s"' % s.replace('"', '\\"')


def command_for(lab, action, args=(), plugin=PLUGIN):
    """(runner, command line) for ``action`` in this lab."""
    if action not in LEGACY:
        raise ac.AcademyError("action must be one of %s" % ", ".join(sorted(LEGACY)))
    envpy = os.path.join(plugin, "scripts", "env.py")
    checker = os.path.join(plugin, "scripts", "check_experiments.py")
    extra = " ".join(_q(a, "powershell" if action != "check" else "py") for a in args)
    home_ = lab["home"].replace("\\", "/")
    if os.path.isfile(envpy) and action != "check":
        cmd = 'py "%s" --home "%s" %s %s' % (envpy.replace("\\", "/"), home_, action, extra)
        return "env.py", cmd.strip()
    if action == "check" and os.path.isfile(checker):
        cmd = 'py "%s" --home "%s" %s' % (checker.replace("\\", "/"), home_, extra)
        return "plugin", cmd.strip()
    kind, rel = LEGACY[action]
    home = lab["home"].replace("\\", "/")
    if not os.path.isfile(os.path.join(home, rel)):
        raise ac.AcademyError("%s has no %s and the plugin has no env.py yet" % (home, rel))
    if kind == "powershell":
        cmd = 'cd "%s"; %s %s' % (home, rel.replace("/", "\\"), extra)
    else:
        cmd = 'cd "%s"; py %s %s' % (home, rel.replace("/", "\\"), extra)
    return "legacy", cmd.strip()


def describe(lab):
    cfg = lab["cfg"]
    sci = cfg.get("scientist") or {}
    root = ac.repo_root()
    packs = {d: os.path.join(root, "domains", d).replace("\\", "/")
             for d in cfg.get("domains") or []}
    return {"instance": lab["instance"], "home": lab["home"].replace("\\", "/"),
            "switched": lab["switched"], "domains": cfg.get("domains") or [],
            "packs": packs, "envs": sci.get("envs") or {}, "policy": sci.get("policy") or {},
            "queue": ((sci.get("queue") or {}).get("dir")
                      or (cfg.get("paths") or {}).get("queue") or "queue"),
            "experiments": c.experiments_dir(cfg), "results": c.results_dir(cfg),
            "note": lab.get("note") or ""}


def queue_counts(home, qdir):
    out = {}
    for st in QUEUE_STATES:
        d = os.path.join(home, qdir, st)
        out[st] = len([f for f in os.listdir(d) if f.endswith(".json")]) \
            if os.path.isdir(d) else 0
    return out


def result_stems(home, rdir):
    """(stem, relative path, mtime) for every result JSON, newest first."""
    root = os.path.join(home, rdir)
    rows = []
    if not os.path.isdir(root):
        return rows
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for f in filenames:
            if not f.endswith(".json"):
                continue
            full = os.path.join(dirpath, f)
            rel = c.relative(home, full)
            parts = c.relative(root, full).split("/")
            stem = parts[0] if len(parts) > 1 else f[:-5]
            rows.append((stem, rel, os.path.getmtime(full)))
    rows.sort(key=lambda r: (-r[2], r[1]))
    return rows


def reported(board, instance):
    """The result paths that experiment-report packets of ``instance`` refer to."""
    root = os.path.join(board, "packets", instance)
    seen = set()
    if not os.path.isdir(root):
        return seen
    rx = re.compile(r"file:%s/([^\s`]+\.json)" % re.escape(instance))
    for f in os.listdir(root):
        if not f.endswith(".md"):
            continue
        try:
            with open(os.path.join(root, f), "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        if "kind: experiment-report" not in text:
            continue
        seen.update(m.group(1) for m in rx.finditer(text))
    return seen


def status(lab, board=None):
    d = describe(lab)
    out = {"instance": d["instance"], "home": d["home"], "switched": d["switched"],
           "queue": queue_counts(lab["home"], d["queue"])}
    try:
        bdir = board or ac.load_workspace()["board"]
    except ac.AcademyError:
        bdir = None
    tickets, packets, unreported = {}, 0, []
    if bdir and os.path.isdir(bdir):
        folder = os.path.join(bdir, d["instance"])
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if re.match(r"^T-\d{4,}-.*\.md$", f):
                    try:
                        with open(os.path.join(folder, f), "r", encoding="utf-8") as fh:
                            meta = ac.read_frontmatter(fh.read())[0]
                    except (OSError, ac.AcademyError):
                        continue
                    st = meta.get("status")
                    if st not in ac.TERMINAL:
                        tickets[st] = tickets.get(st, 0) + 1
        proot = os.path.join(bdir, "packets", d["instance"])
        if os.path.isdir(proot):
            for f in os.listdir(proot):
                if f.endswith(".md"):
                    try:
                        with open(os.path.join(proot, f), "r", encoding="utf-8") as fh:
                            if ac.read_frontmatter(fh.read())[0].get("state") == "open":
                                packets += 1
                    except (OSError, ac.AcademyError):
                        continue
        done = reported(bdir, d["instance"])
        for stem, rel, _mt in result_stems(lab["home"], d["results"]):
            if rel not in done:
                unreported.append(rel)
    out.update({"board": (bdir or "").replace("\\", "/"), "tickets": tickets,
                "open_packets": packets, "unreported_results": unreported[:10],
                "unreported_total": len(unreported)})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="lab.py", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("home"); p.add_argument("--home"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("cmd"); p.add_argument("--home")
    p.add_argument("action"); p.add_argument("args", nargs=argparse.REMAINDER)
    p = sub.add_parser("status"); p.add_argument("--home"); p.add_argument("--board")
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        lab = c.resolve_lab(a.home, os.getcwd())
        if a.cmd == "home":
            d = describe(lab)
            if a.json:
                print(json.dumps(d, indent=1, ensure_ascii=False))
            else:
                print("%s at %s (%s)" % (d["instance"], d["home"],
                                        "switched over" if d["switched"]
                                        else "no academy.json yet: layout defaults"))
                print("domains: %s" % ", ".join("%s -> %s" % kv for kv in d["packs"].items()))
                print("envs: %s" % (", ".join("%s (%s)" % (k, v.get("kind"))
                                              for k, v in d["envs"].items()) or "none"))
                print("policy: %s" % (", ".join("%s=%s" % kv for kv in d["policy"].items())
                                      or "none"))
                if d["note"]:
                    print("note: " + d["note"])
        elif a.cmd == "cmd":
            runner, cmd = command_for(lab, a.action, list(a.args))
            print(cmd)
        else:
            s = status(lab, a.board)
            if a.json:
                print(json.dumps(s, indent=1, ensure_ascii=False))
            else:
                q = s["queue"]
                print("%s: queue %s" % (s["instance"], ", ".join("%d %s" % (q[k], k)
                                                                  for k in QUEUE_STATES)))
                print("tickets to it: %s; open packets from it: %d"
                      % (", ".join("%d %s" % (v, k) for k, v in sorted(s["tickets"].items()))
                         or "none", s["open_packets"]))
                print("results with no report packet: %d%s" % (
                    s["unreported_total"], (" (newest: %s)" % ", ".join(
                        s["unreported_results"][:5])) if s["unreported_results"] else ""))
    except ac.AcademyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
