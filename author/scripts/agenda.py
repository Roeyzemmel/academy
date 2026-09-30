"""agenda.py -- keep Drafts/agenda.md honest (plan section 4; /author:agenda, /author:status).

    py agenda.py check                     problems with agenda.md (exit 1 if any)
    py agenda.py status [--statuses FILE]  refresh the generated status column
    py agenda.py gaps [--json]             entries below their required status with no
                                           ticket working on them
    py agenda.py gaps --file [--dry-run]   file one ticket per gap (idempotent)
    py agenda.py milestones [--json]       progress of each milestone
    py agenda.py show [--json]             the entries with their status and tickets

Common options: ``--home DIR`` (default: the Author home holding the cwd), or
``--agenda FILE --board DIR --instance NAME --ns NS`` for tests.

The board is the Author's only queue (there is no roadmap): a gap becomes a ticket whose
``agenda`` field is the entry's claim id and whose ``refs`` carry the claim, filed
through ``board.create_ticket``. An entry is a gap only while no non-terminal ticket to
or from this instance carries its ``agenda``, so filing the same gap twice files one
ticket. Milestones and the status column are computed from the registry statuses and
the tickets attached to each entry.

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
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import agenda_lib as al  # noqa: E402
import inbox as nx  # noqa: E402
import routes as rt  # noqa: E402

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
    ns_args = argparse.Namespace(home=args.home, agenda=args.agenda, board=args.board,
                                 workspace=args.workspace, instance=args.instance,
                                 ns=args.ns, items=None)
    return nx.load_context(ns_args)


def registry_statuses(home, config):
    """{claim id: status} from the home's registry command, or raise InboxError."""
    cmd = ((config or {}).get("registry") or {}).get("legacy", {}).get("claims")
    if not cmd:
        raise nx.InboxError("no registry command (registry.legacy.claims in academy.json); "
                           "pass --statuses FILE written from the MCP tool claims_list")
    argv = shlex.split(cmd, posix=False)
    if argv and argv[0].lower() in ("py", "python", "python3"):
        argv = [sys.executable] + argv[1:]
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


def entry_tickets(ctx):
    """{agenda label: [ids of the non-terminal tickets to or from this instance]}."""
    out = {}
    for tid in sorted(ctx.tickets, key=nx._num):
        t = ctx.tickets[tid]
        if t.get("status") in ac.TERMINAL:
            continue
        if t.get("from") != ctx.instance and t.get("to") != ctx.instance:
            continue
        e = ctx.agenda.lookup(t.get("agenda") or "", ctx.ns)
        if e is not None:
            out.setdefault(e.label, []).append(tid)
    return out


def working_on(ctx):
    """Agenda labels that an active ticket is attached to."""
    return set(entry_tickets(ctx))


def _claim_ref(ctx, e):
    """The id a ticket's ``agenda`` field carries for entry ``e``: its claim, else the label."""
    if e.claim not in ("", "-"):
        return e.claim
    return "%s:%s" % (ctx.ns, e.label) if ctx.ns else e.label


def _waits_for(ctx, e):
    """Inputs of ``e`` (agenda entries with a known status) not yet at their required
    status: a verification on top of unproved inputs is only a verdict modulo them."""
    out = []
    for d in e.depends_on:
        de = ctx.agenda.lookup(d, ctx.ns)
        if de is None or de.status in ("", "?", "missing"):
            continue
        if not de.done:
            out.append(de.label)
    return out


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
                    "owner": e.owner or ctx.instance, "proposed_tag": tag, "why": why,
                    "waits_for": _waits_for(ctx, e) if tag == "verify" else []})
    return out


def ticket_draft(ctx, gap):
    """The ticket a gap becomes: ``{to, kind, title, ask, deliverable, refs, agenda,
    final_to, note}``. ``apply`` stays in the Author (a self-ticket); the asks go to the
    Expert instance sharing a domain (``research`` with ``final_to`` for ``lead``)."""
    e = ctx.agenda.lookup(gap["label"], ctx.ns)
    ref = _claim_ref(ctx, e)
    refs = [ref] if e.claim not in ("", "-") else []
    tag = gap["proposed_tag"]
    if tag in rt.OUT_ROUTES:
        role, kind, final_to, dkey = rt.OUT_ROUTES[tag]
        to, note = target_instance(ctx, role)
        deliverable = rt.DELIVERABLES[dkey]
    else:
        kind, final_to, note = "apply", None, ""
        to, deliverable = ctx.instance, rt.SELF_DELIVERABLE
    verb = {"verify": "Verify", "lead": "Prove", "apply": "Create the record of"}.get(tag,
                                                                                 "Work on")
    return {"to": to, "kind": kind, "title": "%s %s" % (verb, e.label),
            "ask": "%s %s (status %s, needs %s): %s" % (verb, e.label, gap["status"],
                                                       gap["required"], gap["why"]),
            "deliverable": deliverable, "refs": refs, "agenda": ref,
            "final_to": final_to, "note": note, "priority": "normal",
            "domain": (ctx.domains or [None])[0]}


def target_instance(ctx, role):
    """(instance, note) of the ``role`` instance sharing a domain with this one."""
    cands = sorted(n for n, i in ctx.workspace.get("instances", {}).items()
                   if i.get("role") == role
                   and (not ctx.domains or set(i.get("domains") or []) & set(ctx.domains)))
    if not cands:
        return None, "no %s instance shares a domain with %s" % (role, ctx.instance)
    note = ""
    if len(cands) > 1:
        note = "several %s instances (%s); took %s" % (role, ", ".join(cands), cands[0])
    return cands[0], note


def file_gaps(ctx, dry_run=False):
    """File one ticket per gap; returns ``{"filed": [...], "held": [...]}``.

    Idempotent: a gap is an entry with no non-terminal ticket attached, so once filed
    the entry is busy and a second run files nothing. A verification whose inputs are
    not yet at their required status is held (reported, not filed).
    """
    if not ctx.board:
        raise nx.InboxError("no board (workspace.json 'board', or --board)")
    bd = nx.board_module()
    filed, held = [], []
    for g in gaps(ctx):
        if g["waits_for"]:
            held.append({"label": g["label"], "why": "inputs not yet at their required "
                         "status: %s" % ", ".join(g["waits_for"])})
            continue
        d = ticket_draft(ctx, g)
        if not d["to"]:
            held.append({"label": g["label"], "why": d["note"]})
            continue
        row = {"label": g["label"], "ticket": None, "to": d["to"], "kind": d["kind"],
               "agenda": d["agenda"]}
        if not dry_run:
            path = bd.create_ticket(
                ctx.board, d["to"], d["title"], d["ask"], d["deliverable"], kind=d["kind"],
                priority=d["priority"], refs=d["refs"], agenda=d["agenda"],
                domain=d["domain"], as_instance=ctx.instance, agent=ac.MAIN_AGENT,
                final_to=d["final_to"],
                workspace=ctx.workspace if ctx.workspace.get("instances") else None)
            tid = re.match(r"^(T-\d{4,})", os.path.basename(path)).group(1)
            row["ticket"] = tid
            with open(path, "r", encoding="utf-8") as fh:
                ctx.tickets[tid] = dict(ac.read_frontmatter(fh.read())[0], _path=path)
        filed.append(row)
    return {"filed": filed, "held": held}


def milestones(ctx):
    tix = entry_tickets(ctx)
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
            res = file_gaps(ctx, args.dry_run)
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
            g = gaps(ctx)
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
            tix = entry_tickets(ctx)
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
