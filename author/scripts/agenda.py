"""agenda.py -- keep Drafts/agenda.md honest (plan section 4; /author:agenda, /author:status).

    py agenda.py check                     problems with agenda.md + roadmap.md (exit 1 if any)
    py agenda.py status [--statuses FILE]  refresh the generated status column
    py agenda.py gaps [--json]             entries below their required status with no
                                           open item or ticket working on them
    py agenda.py milestones [--json]       progress of each milestone
    py agenda.py show [--json]             the entries with their status

Common options: ``--home DIR`` (default: the Author home holding the cwd), or
``--agenda FILE --roadmap FILE --board DIR --instance NAME --ns NS`` for tests.

Where ``status`` gets the statuses, in this order:

1. ``--statuses FILE``: a JSON object ``{claim id or label: status}``. The skill
   writes it from the MCP tool ``claims_list`` when it has the server.
2. The home's registry command, ``registry.legacy.claims`` in academy.json (today
   ``py ../<lab>/scripts/claims.py --repo .``), run as
   ``<cmd> sql "select id, status from claims"`` in the home. Read-only.

A claim id the registry does not know is written as ``missing`` (a gap: the claim
record must be created, by claims_new or the claim-keeper).

Exit codes: 0 ok; 1 problems found (check) / nothing to report; 2 error.
"""

import argparse
import json
import os
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import agenda_lib as al  # noqa: E402
import next as nx  # noqa: E402

#: which ask a gap needs, by (current status, required status)
GAP_PROPOSALS = (
    # (current in ..., required in ..., tag, why)
    (("missing",), None, "apply", "no registry record for the claim: create it "
     "(claims_new, unsettled status) before anything else"),
    (("sketch", "supported"), ("proved-modulo", "proved"), "verify",
     "an argument exists; two agreeing verdicts are needed"),
    (("open", "conjectured", ""), ("sketch", "supported", "proved-modulo", "proved"), "lead",
     "no argument yet; a proof must come from the Researcher (the Author never "
     "invents one)"),
    (("proved-modulo",), ("proved",), "lead",
     "proved modulo inputs; the missing inputs need proofs"),
)


def load(args):
    ns_args = argparse.Namespace(home=args.home, agenda=args.agenda, roadmap=args.roadmap,
                                 board=args.board, workspace=args.workspace,
                                 instance=args.instance, ns=args.ns, items=None,
                                 statuses=None)
    return nx.load_context(ns_args)


def registry_statuses(home, config):
    """{claim id: status} from the home's registry command, or raise NextError."""
    cmd = ((config or {}).get("registry") or {}).get("legacy", {}).get("claims")
    if not cmd:
        raise nx.NextError("no registry command (registry.legacy.claims in academy.json); "
                           "pass --statuses FILE written from the MCP tool claims_list")
    argv = shlex.split(cmd, posix=False)
    if argv and argv[0].lower() in ("py", "python", "python3"):
        argv = [sys.executable] + argv[1:]
    argv += ["sql", "select id, status from claims"]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        p = subprocess.run(argv, cwd=home, capture_output=True, timeout=120, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise nx.NextError("registry command failed: %s" % exc)
    if p.returncode != 0:
        raise nx.NextError("registry command exited %d: %s" % (
            p.returncode, p.stderr.decode("utf-8", "replace").strip()[:300]))
    out = {}
    for ln in p.stdout.decode("utf-8", "replace").splitlines()[1:]:
        parts = [x.strip() for x in ln.split(" | ")]
        if len(parts) == 2 and parts[0]:
            out[parts[0]] = parts[1]
    return out


def refresh_status(ctx, statuses):
    """Write each entry's status from ``statuses``; returns the changed labels."""
    changed = []
    for e in ctx.agenda.entries:
        new = statuses.get(e.claim) or statuses.get(e.label)
        if new is None:
            new = "missing" if e.claim not in ("", "-") else "?"
        if new != e.status:
            changed.append((e.label, e.status, new))
            e.status = new
    al.write_text(ctx.agenda_path, al.write_agenda(ctx.agenda))
    return changed


def working_on(ctx):
    """Agenda labels that an open item or an active ticket is attached to."""
    busy = set()
    for it in ctx.roadmap.items:
        if it.status in ("open", "ticketed", "blocked", "needs-human") and it.agenda:
            e = ctx.agenda.lookup(it.agenda, ctx.ns)
            if e is not None:
                busy.add(e.label)
    for t in ctx.tickets.values():
        if t.get("status") in ("closed", "rejected", "cancelled"):
            continue
        if t.get("from") != ctx.instance and t.get("to") != ctx.instance:
            continue
        e = ctx.agenda.lookup(t.get("agenda") or "", ctx.ns)
        if e is not None:
            busy.add(e.label)
    return busy


def gaps(ctx):
    busy = working_on(ctx)
    out = []
    for e in ctx.agenda.entries:
        if e.done or e.label in busy:
            continue
        cur = e.status if e.status not in ("?",) else ""
        tag, why = None, None
        for curs, reqs, t, w in GAP_PROPOSALS:
            if cur in curs and (reqs is None or e.required in reqs):
                tag, why = t, w
                break
        if tag is None:
            tag, why = "verify", "status %s does not meet %s" % (cur or "unknown", e.required)
        out.append({"position": e.position, "label": e.label, "claim": e.claim,
                    "status": cur or "unknown", "required": e.required,
                    "owner": e.owner or ctx.instance, "proposed_tag": tag, "why": why})
    return out


def milestones(ctx):
    out = {}
    for name, goals in ctx.agenda.milestones.items():
        rows = []
        for lab, want in goals.items():
            e = ctx.agenda.lookup(lab, ctx.ns)
            st = e.status if e is not None else "unknown"
            rows.append({"label": lab, "target": want, "status": st,
                         "met": al.satisfied(st, want)})
        out[name] = {"met": sum(r["met"] for r in rows), "of": len(rows), "entries": rows}
    return out


def main(argv=None):
    nx._utf8()
    p = argparse.ArgumentParser(description="Keep the Author's agenda honest.")
    p.add_argument("cmd", choices=("check", "status", "gaps", "milestones", "show"))
    for opt in ("--home", "--agenda", "--roadmap", "--board", "--workspace", "--instance",
                "--ns", "--statuses"):
        p.add_argument(opt, default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    try:
        ctx = load(args)
        if args.cmd == "check":
            probs = al.check(ctx.agenda, ctx.roadmap, ctx.ns)
            for pr in probs:
                print(pr)
            print("%d problem(s); %d entries, %d items" % (
                len(probs), len(ctx.agenda.entries), len(ctx.roadmap.items)))
            return 1 if probs else 0
        if args.cmd == "status":
            if args.statuses:
                with open(args.statuses, "r", encoding="utf-8") as fh:
                    statuses = json.load(fh)
            else:
                home = args.home or ac.find_home(os.getcwd())
                statuses = registry_statuses(home, ac.load_config(home))
            changed = refresh_status(ctx, statuses)
            for lab, old, new in changed:
                print("%s: %s -> %s" % (lab, old or "?", new))
            print("%d status(es) changed in %s" % (len(changed), ctx.agenda_path))
            return 0
        if args.cmd == "gaps":
            g = gaps(ctx)
            if args.json:
                print(json.dumps(g, indent=2, ensure_ascii=False))
            else:
                for r in g:
                    print("%3d %s (%s, needs %s) -> [%s] %s" % (
                        r["position"], r["label"], r["status"], r["required"],
                        r["proposed_tag"], r["why"]))
                print("%d gap(s)" % len(g))
            return 0 if g else 1
        if args.cmd == "milestones":
            m = milestones(ctx)
            if args.json:
                print(json.dumps(m, indent=2, ensure_ascii=False))
            else:
                for name, v in m.items():
                    print("%s: %d of %d" % (name, v["met"], v["of"]))
                    for r in v["entries"]:
                        print("  [%s] %s: %s (target %s)" % (
                            "x" if r["met"] else " ", r["label"], r["status"], r["target"]))
                if not m:
                    print("no milestones in the agenda")
            return 0 if m else 1
        if args.cmd == "show":
            rows = [e.as_dict() for e in ctx.agenda.entries]
            if args.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            else:
                for e in ctx.agenda.entries:
                    print("%3d %-40s %-14s needs %-13s %s" % (
                        e.position, e.label, e.status or "?", e.required,
                        "ok" if e.done else ""))
            return 0
    except (nx.NextError, al.AgendaError, ac.AcademyError, OSError, ValueError) as exc:
        sys.stderr.write("agenda.py: %s\n" % exc)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
