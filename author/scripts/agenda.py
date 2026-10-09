"""agenda.py -- keep Drafts/agenda.md honest (plan section 4; /author:agenda, /author:status).

    py agenda.py check                     problems with agenda.md (exit 1 if any)
    py agenda.py status [--statuses FILE]  refresh the generated status column
    py agenda.py gaps [--json]             entries below their required status with no
                                           ticket working on them
    py agenda.py gaps --file [--dry-run] [--campaign TARGET]
                                           file one ticket per gap (idempotent)
    py agenda.py milestones [--json]       progress of each milestone
    py agenda.py show [--json]             the entries with their status and tickets

Common options: ``--home DIR`` (default: the Author home holding the cwd), or
``--agenda FILE --board DIR --instance NAME --ns NS`` for tests.

The board is the Author's only queue (there is no roadmap): a gap becomes a ticket whose
``agenda`` field is the entry's qualified label (``<ns>:<label>``: unique in the agenda,
where a claim id may be shared by two entries) and whose ``refs`` carry the claim, filed
through ``board.create_ticket`` (``--campaign TARGET`` tags it for a campaign). An entry
is a gap only while no non-terminal ticket to or from this instance carries its
``agenda``, so filing the same gap twice files one ticket. A gap no ticket can close (a
refuted claim, a claim with no registry record) is *held* and reported: it waits for
the human. The gap logic itself is ``gaps.py``, shared with ``inbox.py`` and the converter.
The agenda file must exist (a missing one is an error, not an empty agenda). Milestones and the status column are computed from the registry statuses and
the tickets attached to each entry.

Where ``status`` gets the statuses, in this order:

1. ``--statuses FILE``: a JSON object ``{claim id or label: status}``. The skill
   writes it from the MCP tool ``claims_list`` when it has the server.
2. The home's registry command, ``registry.legacy.claims`` in academy.json (today
   ``py ../<lab>/scripts/claims.py --repo .``), run as
   ``<cmd> sql "select id, status from claims"`` in the home. Read-only.

A claim id the registry does not know is written as ``missing`` (a held gap: the human
creates the record with claims_new; the claim-keeper sets statuses).

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
import gaps as gp  # noqa: E402
import inbox as nx  # noqa: E402

def load(args):
    ns_args = argparse.Namespace(home=args.home, agenda=args.agenda, board=args.board,
                                 workspace=args.workspace, instance=args.instance,
                                 ns=args.ns, items=None)
    return nx.load_context(ns_args)


def registry_argv(cmd):
    """The argv of the registry command ``cmd`` (a command line as academy.json holds it).

    Windows-safe: the line is split without POSIX rules (backslashes stay), the literal
    quotes the split keeps are stripped, and a ``py``/``python``/``python3`` launcher
    (with or without ``.exe``, any directory) becomes this interpreter.
    """
    argv = [a[1:-1] if len(a) >= 2 and a[0] == a[-1] and a[0] in "\"'" else a
            for a in shlex.split(cmd, posix=False)]
    if argv:
        base = os.path.basename(argv[0].replace("\\", "/")).lower()
        if base.endswith(".exe"):
            base = base[:-4]
        if base in ("py", "python", "python3"):
            argv[0] = sys.executable
    return argv


def registry_statuses(home, config):
    """{claim id: status} from the home's registry command, or raise InboxError."""
    cmd = ((config or {}).get("registry") or {}).get("legacy", {}).get("claims")
    if not cmd:
        raise nx.InboxError("no registry command (registry.legacy.claims in academy.json); "
                           "pass --statuses FILE written from the MCP tool claims_list")
    argv = registry_argv(cmd)
    argv += ["sql", "select id, status from claims"]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        p = subprocess.run(argv, cwd=home, capture_output=True, timeout=120, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise nx.InboxError("registry command failed: %s" % exc)
    if p.returncode != 0:
        raise nx.InboxError("registry command exited %d: %s" % (
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


def milestones(ctx):
    tix = gp.entry_tickets(ctx)
    out = {}
    for name, goals in ctx.agenda.milestones.items():
        rows = []
        for lab, want in goals.items():
            e = ctx.agenda.lookup(lab, ctx.ns)
            st = e.status if e is not None else "unknown"
            rows.append({"label": lab, "target": want, "status": st,
                         "met": al.satisfied(st, want),
                         "tickets": tix.get(e.label, []) if e is not None else []})
        out[name] = {"met": sum(r["met"] for r in rows), "of": len(rows), "entries": rows}
    return out


def main(argv=None):
    nx._utf8()
    p = argparse.ArgumentParser(description="Keep the Author's agenda honest.")
    p.add_argument("cmd", choices=("check", "status", "gaps", "milestones", "show"))
    for opt in ("--home", "--agenda", "--board", "--workspace", "--instance", "--ns",
                "--statuses"):
        p.add_argument(opt, default=None)
    p.add_argument("--json", action="store_true")
    p.add_argument("--file", action="store_true",
                   help="gaps: file one ticket per gap (idempotent)")
    p.add_argument("--dry-run", action="store_true", help="gaps --file: show, file nothing")
    p.add_argument("--campaign", metavar="TARGET", default=None,
                   help="gaps --file: tag each filed ticket `campaign: TARGET`")
    args = p.parse_args(argv)
    try:
        ctx = load(args)
        if args.cmd == "check":
            probs = al.check(ctx.agenda, ctx.ns)
            for pr in probs:
                print(pr)
            print("%d problem(s); %d entries" % (len(probs), len(ctx.agenda.entries)))
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
        if args.cmd == "gaps" and args.file:
            res = gp.file_gaps(ctx, args.dry_run, args.campaign)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                for r in res["filed"]:
                    print("%s %s -> %s (%s)" % (r["ticket"] or "(dry run)", r["label"],
                                                r["to"], r["kind"]))
                for r in res["held"]:
                    print("held %s: %s" % (r["label"], r["why"]))
                print("%d ticket(s) %s, %d held" % (
                    len(res["filed"]), "to file" if args.dry_run else "filed",
                    len(res["held"])))
            return 0 if res["filed"] else 1
        if args.cmd == "gaps":
            g = gp.gaps(ctx)
            if args.json:
                print(json.dumps(g, indent=2, ensure_ascii=False))
            else:
                for r in g:
                    print("%3d %s (%s, needs %s) -> [%s] %s%s" % (
                        r["position"], r["label"], r["status"], r["required"],
                        r["proposed_tag"], r["why"],
                        ("; waits for " + ", ".join(r["waits_for"])) if r["waits_for"]
                        else ""))
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
                        print("  [%s] %s: %s (target %s)%s" % (
                            "x" if r["met"] else " ", r["label"], r["status"], r["target"],
                            ("  tickets: " + ", ".join(r["tickets"])) if r["tickets"]
                            else ""))
                if not m:
                    print("no milestones in the agenda")
            return 0 if m else 1
        if args.cmd == "show":
            tix = gp.entry_tickets(ctx)
            rows = [dict(e.as_dict(), tickets=tix.get(e.label, []))
                    for e in ctx.agenda.entries]
            if args.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            else:
                for e in ctx.agenda.entries:
                    print("%3d %-40s %-14s needs %-13s %s%s" % (
                        e.position, e.label, e.status or "?", e.required,
                        "ok" if e.done else "",
                        ("  tickets: " + ", ".join(tix.get(e.label, [])))
                        if tix.get(e.label) else ""))
            return 0
    except (nx.InboxError, al.AgendaError, ac.AcademyError, OSError, ValueError) as exc:
        sys.stderr.write("agenda.py: %s\n" % exc)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
