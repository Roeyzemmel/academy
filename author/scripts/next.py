"""next.py -- what /author:next runs, computed rather than chosen (plan section 4).

    py next.py plan [--json] [--items N]      the ordered ready set, the waiting and the parked
    py next.py file R-NNNN [--dry-run]        file the item's ticket (lead/verify/cite/...) and
                                              mark it ticketed
    py next.py mark R-NNNN --status S [--note TEXT] [--ticket T-NNNN]
    py next.py add --tag T --title TITLE [--attach ID] [--priority P] [--depends-on a,b]
                   [--route AGENT] [--source S] [--body TEXT]    prints the new id

Common options: ``--home DIR`` (default: the Author home holding the cwd), and for
tests ``--agenda FILE --roadmap FILE --board DIR --workspace FILE --instance NAME
--ns NS`` in place of the home's config.

The plan
--------
1. Candidates: the roadmap's items (``open``, or ``ticketed`` whose ticket came back),
   plus the board tickets addressed to this instance that are ``open``, ``accepted``
   or ``in-progress``.
2. Ready = every dependency met. A dependency is an item (met when ``done``), a ticket
   (met when ``delivered`` or ``closed``), or an agenda entry / claim id (met when its
   status reaches the entry's ``required``). A ``[verify]`` item also waits for the
   entries its agenda entry depends on (a verdict on top of unproved inputs is only
   a verdict modulo them).
3. Sort by the earliest agenda position the item unblocks -- its own entry or any
   entry that rests on it, transitively -- then priority (high, normal, low), then
   file order (items before tickets). ``global`` and unattached items sort last.
4. Take ``budget.itemsPerRun`` (at most 3).

Routing (references in skills/next/references/routing.md): ``apply`` -> math-editor,
``write`` -> math-writer (or the item's ``route``), ``figure`` -> figure-maker,
``build`` -> tex-engineer, ``notation`` -> notation-auditor, ``sweep`` -> note-sweeper;
``lead``/``verify``/``cite``/``experiment``/``referee`` -> a ticket to the Researcher,
Expert or Scientist instance sharing a domain; a ticketed item whose ticket came
back -> ``land`` (math-writer for a proof or experiment, math-editor for a verdict or
citation, /author:notes for a referee packet).

Exit codes: 0 ok; 1 nothing ready (plan) / nothing to do; 2 error (one line on stderr).
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import agenda_lib as al  # noqa: E402

AGENT_ROUTES = {"write": "math-writer", "apply": "math-editor", "figure": "figure-maker",
                "build": "tex-engineer", "notation": "notation-auditor",
                "sweep": "note-sweeper"}
ASK_ROUTES = {"lead": ("researcher", "prove"), "verify": ("expert", "verify"),
              "cite": ("expert", "cite"), "experiment": ("scientist", "experiment"),
              "referee": ("expert", "referee")}
LAND_ROUTES = {"lead": "math-writer", "verify": "math-editor", "cite": "math-editor",
               "experiment": "math-writer", "referee": "notes"}
TICKET_KIND_ROUTES = {"build": "tex-engineer", "figure": "figure-maker",
                      "notation": "notation-auditor"}
DELIVERABLES = {
    "prove": "A proof (or a refutation) of the statement, as a proof object with its "
             "status proposed; the ticket result names it.",
    "verify": "A verification packet with two verdicts; the ticket result names the "
              "verdict and whether a recolour is proposed.",
    "cite": "A bibliography entry and a card with the verbatim quote and version; the "
            "ticket result gives the key and pinpoint.",
    "experiment": "An experiment report packet with its ## Conclusion; the ticket result "
                  "names the lab claim.",
    "referee": "A referee packet on the built PDF.",
}
TICKET_MET = ("delivered", "closed")
TICKET_DEAD = ("rejected", "cancelled")
INBOX_ACTIVE = ("open", "accepted", "in-progress")
MAX_ITEMS = 3
INF = 10 ** 9
RE_HISTORY = re.compile(r"^- \d{4}-\d{2}-\d{2}: ")


class NextError(Exception):
    pass


# ----------------------------------------------------------------------------
# Context
# ----------------------------------------------------------------------------

def academy_scripts():
    return os.path.join(ac.repo_root(), "academy", "scripts")


def board_module():
    p = academy_scripts()
    if p not in sys.path:
        sys.path.insert(0, p)
    import board  # noqa: E402  (academy/scripts/board.py)
    return board


class Context(object):
    """Everything the plan needs, loaded once."""

    def __init__(self, agenda_path, roadmap_path, board, workspace, instance, ns,
                 items_per_run=MAX_ITEMS, domains=None, statuses=None):
        self.agenda_path = agenda_path
        self.roadmap_path = roadmap_path
        self.board = board
        self.workspace = workspace or {"instances": {}}
        self.instance = instance
        self.ns = ns or ""
        self.items_per_run = max(1, min(MAX_ITEMS, int(items_per_run or MAX_ITEMS)))
        self.domains = list(domains or [])
        self.statuses = dict(statuses or {})
        self.agenda = (al.parse_agenda(al.read_text(agenda_path))
                       if agenda_path and os.path.isfile(agenda_path) else al.Agenda())
        self.roadmap = (al.parse_roadmap(al.read_text(roadmap_path))
                        if roadmap_path and os.path.isfile(roadmap_path) else al.Roadmap())
        self.tickets = {}
        if board and os.path.isdir(board):
            for path, meta, body in board_module().iter_tickets(board):
                if meta and meta.get("id"):
                    m = dict(meta)
                    m["_path"] = path
                    m["_body"] = body
                    self.tickets[m["id"]] = m


def load_context(args):
    """A Context from --home's academy.json, overridden by explicit options."""
    home = args.home or ac.find_home(os.getcwd())
    cfg = None
    if home and os.path.isfile(os.path.join(home, ac.CONFIG_REL)):
        try:
            cfg = ac.load_config(home)
        except ac.AcademyError as exc:
            raise NextError(str(exc))
        if cfg.get("role") != "author":
            raise NextError("%s is a %s home, not an Author home" % (home, cfg.get("role")))
    if cfg is None and not (args.agenda and args.roadmap):
        raise NextError("no Author home here (no .claude/academy.json with role author); "
                        "give --home, or --agenda and --roadmap")
    paths = (cfg or {}).get("paths", {})

    def rel(key, default):
        v = paths.get(key, default)
        v = v[0] if isinstance(v, list) else v
        return os.path.join(home, *str(v).split("/")) if home else v

    ws = None
    try:
        ws = ac.load_workspace(args.workspace)
    except ac.ConfigError:
        if cfg is not None or args.board is None:
            ws = None
    board = args.board or (ws or {}).get("board")
    instance = args.instance or (cfg or {}).get("instance")
    if not instance:
        raise NextError("no instance name (give --instance)")
    ns = args.ns if args.ns is not None else (cfg or {}).get("ns", "")
    domains = (cfg or {}).get("domains") or ((ws or {}).get("instances", {})
                                             .get(instance, {}).get("domains")) or []
    items = args.items or ((cfg or {}).get("budget", {}).get("itemsPerRun")) or MAX_ITEMS
    statuses = {}
    if getattr(args, "statuses", None):
        with open(args.statuses, "r", encoding="utf-8") as fh:
            statuses = json.load(fh)
    return Context(args.agenda or rel("agenda", "Drafts/agenda.md"),
                   args.roadmap or rel("roadmap", "Drafts/roadmap.md"),
                   board, ws, instance, ns, items, domains, statuses)


# ----------------------------------------------------------------------------
# The plan
# ----------------------------------------------------------------------------

def entry_status(ctx, e):
    return ctx.statuses.get(e.claim) or ctx.statuses.get(e.label) or e.status


def entry_ok(ctx, e):
    return al.satisfied(entry_status(ctx, e), e.required)


def dep_state(ctx, dep):
    """(met, reason, dead) for one dependency."""
    dep = dep.strip().strip("`")
    if al.RE_ITEM_ID.match(dep):
        it = ctx.roadmap.get(dep)
        if it is None:
            return False, "unknown item %s" % dep, True
        if it.status == "done":
            return True, None, False
        if it.status == "dropped":
            return False, "dependency %s was dropped" % dep, True
        return False, "waits for %s (%s)" % (dep, it.status), False
    if al.RE_TICKET_ID.match(dep):
        t = ctx.tickets.get(dep)
        if t is None:
            return False, "unknown ticket %s" % dep, True
        st = t.get("status")
        if st in TICKET_MET:
            return True, None, False
        if st in TICKET_DEAD:
            return False, "ticket %s was %s" % (dep, st), True
        return False, "waits for ticket %s (%s)" % (dep, st), False
    e = ctx.agenda.lookup(dep, ctx.ns)
    if e is not None:
        if entry_ok(ctx, e):
            return True, None, False
        return False, "waits for %s to reach %s (now %s)" % (
            e.label, e.required, entry_status(ctx, e) or "unknown"), False
    st = ctx.statuses.get(dep)
    if st and al.satisfied(st, "proved"):
        return True, None, False
    return False, "waits for %s (%s)" % (dep, st or "status unknown"), False


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


def _one_line(text, limit=240):
    for para in (text or "").split("\n\n"):
        s = " ".join(para.split())
        if s and not s.startswith("<!--"):
            return s if len(s) <= limit else s[:limit - 3].rstrip() + "..."
    return ""


def _ask_line(it, limit=240):
    """``<title> -- <first paragraph>``, one line; the full body goes to ``## Ask``."""
    # a body that opens with a list item would give "<title> -- - <text>"
    first = re.sub(r"^(?:[-*+]|\d+\.)\s+", "", _one_line(it.body, limit))
    if not first or first == it.title:
        return it.title
    s = "%s -- %s" % (it.title, first)
    return s if len(s) <= limit else s[:limit - 3].rstrip() + "..."


def ticket_draft(ctx, it):
    """The ticket an ask item becomes (dict), or raise NextError."""
    if it.tag not in ASK_ROUTES:
        raise NextError("%s [%s] is not an ask item (tags: %s)"
                        % (it.id, it.tag, ", ".join(sorted(ASK_ROUTES))))
    role, kind = ASK_ROUTES[it.tag]
    to, note = target_instance(ctx, role)
    e = ctx.agenda.lookup(it.agenda, ctx.ns) if it.agenda and it.agenda != "global" else None
    claim = e.claim if e is not None and e.claim not in ("", "-") else None
    refs = [claim] if claim else []
    for d in it.depends_on:
        if ":" in d and d not in refs and not al.RE_ITEM_ID.match(d):
            refs.append(d)
    return {
        "to": to, "kind": kind, "title": it.title,
        "ask": _ask_line(it), "deliverable": DELIVERABLES[kind],
        "refs": refs, "agenda": claim or (it.agenda or "global"),
        "priority": it.priority, "domain": (ctx.domains or [None])[0],
        "detail": it.body.strip(), "note": note,
    }


def _position(ctx, ref):
    if not ref or ref == "global":
        return INF, None
    e = ctx.agenda.lookup(ref, ctx.ns)
    if e is None:
        return INF, "agenda entry %s not found; sorted with global" % ref
    return ctx.agenda.unblock_position(e.label), None


def _implicit_deps(ctx, it):
    """A verify waits for the inputs of its agenda entry.

    Only inputs whose status is known count: an input with no registry record
    (``missing``) or never read (``?``) is a gap for /author:agenda, not a reason
    to hold every verification that mentions it.
    """
    if it.tag != "verify" or not it.agenda:
        return []
    e = ctx.agenda.lookup(it.agenda, ctx.ns)
    if e is None:
        return []
    out = []
    for d in e.depends_on:
        de = ctx.agenda.lookup(d, ctx.ns)
        st = entry_status(ctx, de) if de is not None else ""
        if de is None or st in ("", "?", "missing"):
            continue
        out.append(d)
    return out


def plan(ctx):
    """The plan as a dict: ready (ordered), selected, waiting, parked, notes."""
    ready, waiting, parked, notes = [], [], [], []
    order = 0
    for it in ctx.roadmap.items:
        order += 1
        st = it.status
        if st in ("done", "dropped"):
            continue
        rec = {"source": "roadmap", "id": it.id, "tag": it.tag, "title": it.title,
               "agenda": it.agenda or "global", "priority": it.priority}
        if st in ("needs-human", "blocked"):
            rec["reason"] = st
            parked.append(rec)
            continue
        if st == "ticketed":
            t = ctx.tickets.get(it.ticket)
            if t is None:
                rec["reason"] = "ticketed, but ticket %s is not on the board" % it.ticket
                parked.append(rec)
                continue
            if t.get("status") in TICKET_DEAD:
                rec["reason"] = "ticket %s was %s; decide what next" % (it.ticket,
                                                                       t.get("status"))
                parked.append(rec)
                continue
            if t.get("status") not in TICKET_MET:
                rec["reason"] = "waits for ticket %s (%s)" % (it.ticket, t.get("status"))
                waiting.append(rec)
                continue
            rec.update(action="land", agent=LAND_ROUTES.get(it.tag, "math-editor"),
                       ticket=it.ticket, result=t.get("result"))
        elif st == "open":
            route = (it.fields.get("route") or "").strip()
            if it.tag in ASK_ROUTES and not route:
                draft = ticket_draft(ctx, it)
                rec.update(action="ticket", to=draft["to"], kind=draft["kind"])
                if draft["note"]:
                    rec["note"] = draft["note"]
                if not draft["to"]:
                    rec["reason"] = "no receiver: " + draft["note"]
                    parked.append(rec)
                    continue
            elif route or it.tag in AGENT_ROUTES:
                rec.update(action="agent", agent=route or AGENT_ROUTES[it.tag])
            else:
                rec.update(action="triage")
        else:
            rec["reason"] = "unknown status %r" % st
            parked.append(rec)
            continue
        unmet, dead = [], False
        for d in it.depends_on + _implicit_deps(ctx, it):
            met, why, is_dead = dep_state(ctx, d)
            if not met:
                unmet.append(why)
                dead = dead or is_dead
        if unmet:
            rec["reason"] = "; ".join(unmet)
            (parked if dead else waiting).append(rec)
            continue
        pos, note = _position(ctx, it.agenda)
        if note:
            notes.append("%s: %s" % (it.id, note))
        rec["position"] = None if pos == INF else pos
        rec["_key"] = (pos, al.PRIORITY_RANK[it.priority], 0, order)
        ready.append(rec)
    for tid in sorted(ctx.tickets, key=lambda x: int(x.split("-")[1])):
        t = ctx.tickets[tid]
        if t.get("to") != ctx.instance or t.get("status") not in INBOX_ACTIVE:
            continue
        kind = t.get("kind") or "other"
        prio = t.get("priority") if t.get("priority") in al.PRIORITIES else "normal"
        rec = {"source": "ticket", "id": tid, "tag": kind, "title": t.get("title"),
               "agenda": t.get("agenda") or "global", "priority": prio,
               "from": t.get("from"), "status": t.get("status")}
        agent = TICKET_KIND_ROUTES.get(kind)
        rec.update(action="agent", agent=agent) if agent else rec.update(action="triage")
        pos, note = _position(ctx, t.get("agenda"))
        if note:
            notes.append("%s: %s" % (tid, note))
        rec["position"] = None if pos == INF else pos
        rec["_key"] = (pos, al.PRIORITY_RANK[prio], 1, int(tid.split("-")[1]))
        ready.append(rec)
    ready.sort(key=lambda r: r["_key"])
    for r in ready:
        del r["_key"]
    take = ready[:ctx.items_per_run]
    return {"instance": ctx.instance, "items_per_run": ctx.items_per_run,
            "selected": take, "ready": ready, "remaining_ready": len(ready) - len(take),
            "waiting": waiting, "parked": parked, "notes": notes}


def render_plan(p):
    out = ["next for %s: %d ready, taking %d (itemsPerRun %d); %d waiting, %d parked"
           % (p["instance"], len(p["ready"]), len(p["selected"]), p["items_per_run"],
              len(p["waiting"]), len(p["parked"]))]
    out.append("")
    out.append("SELECTED (run serially, in this order)")
    for n, r in enumerate(p["selected"], 1):
        how = {"agent": "agent %s" % r.get("agent"),
               "ticket": "ticket %s -> %s" % (r.get("kind"), r.get("to")),
               "land": "land %s via %s" % (r.get("ticket"), r.get("agent")),
               "triage": "triage (ask Roey)"}[r["action"]]
        out.append("  %d. %s [%s] %s -- %s; agenda %s (position %s), %s"
                   % (n, r["id"], r["tag"], r["title"], how, r["agenda"],
                      r["position"] if r["position"] is not None else "-", r["priority"]))
    if not p["selected"]:
        out.append("  none")
    if p["remaining_ready"]:
        out.append("  (%d more ready; they wait for the next run)" % p["remaining_ready"])
    for name in ("waiting", "parked"):
        out.append("")
        out.append("%s (%d)" % (name.upper(), len(p[name])))
        for r in p[name]:
            out.append("  %s [%s] %s -- %s" % (r["id"], r["tag"], r["title"], r["reason"]))
    if p["notes"]:
        out.append("")
        out.append("NOTES")
        out.extend("  " + n for n in p["notes"])
    return "\n".join(out)


# ----------------------------------------------------------------------------
# Writes to the roadmap
# ----------------------------------------------------------------------------

def _save_roadmap(ctx):
    al.write_text(ctx.roadmap_path, al.write_roadmap(ctx.roadmap))


def mark(ctx, iid, status=None, note="", ticket=None, date=None):
    it = ctx.roadmap.get(iid)
    if it is None:
        raise NextError("no roadmap item %s" % iid)
    date = date or ac.today()
    if status:
        if status not in al.ITEM_STATUSES:
            raise NextError("status must be one of %s" % ", ".join(al.ITEM_STATUSES))
        it.fields["status"] = status
    if ticket:
        it.fields["ticket"] = ticket
    it.fields["updated"] = date
    if note or status:
        line = "- %s: %s%s" % (date, ("status %s" % status) if status else "",
                               ("; " if status and note else "") + (note or ""))
        last = it.body.rstrip("\n").split("\n")[-1] if it.body.strip() else ""
        if not it.body.strip():
            it.body = line
        elif RE_HISTORY.match(last):
            it.body = it.body.rstrip("\n") + "\n" + line
        else:
            it.body = it.body.rstrip("\n") + "\n\n" + line
    _save_roadmap(ctx)
    return it


def add(ctx, tag, title, agenda="", priority="normal", depends_on=None, route="",
        source="", body="", date=None):
    if tag not in al.TAGS:
        raise NextError("tag must be one of %s" % ", ".join(al.TAGS))
    if priority not in al.PRIORITIES:
        raise NextError("priority must be high, normal or low")
    date = date or ac.today()
    fields = {"status": "open", "agenda": agenda or "global", "priority": priority,
              "depends_on": al.fmt_list(list(depends_on or []))}
    if route:
        fields["route"] = route
    if source:
        fields["source"] = source
    fields["created"] = date
    it = al.Item(ctx.roadmap.next_id(), tag, " ".join(title.split()), fields, body or "")
    ctx.roadmap.blocks.append(it)
    _save_roadmap(ctx)
    return it


def file_ticket(ctx, iid, dry_run=False):
    it = ctx.roadmap.get(iid)
    if it is None:
        raise NextError("no roadmap item %s" % iid)
    if it.status != "open":
        raise NextError("%s is %s, not open" % (iid, it.status))
    draft = ticket_draft(ctx, it)
    if not draft["to"]:
        raise NextError(draft["note"])
    if dry_run:
        return draft, None
    if not ctx.board:
        raise NextError("no board (workspace.json 'board', or --board)")
    bd = board_module()
    path = bd.create_ticket(ctx.board, draft["to"], draft["title"], draft["ask"],
                            draft["deliverable"], kind=draft["kind"],
                            priority=draft["priority"], refs=draft["refs"],
                            agenda=draft["agenda"], domain=draft["domain"],
                            detail=draft["detail"], as_instance=ctx.instance,
                            workspace=ctx.workspace if ctx.workspace.get("instances") else None)
    tid = re.match(r"^(T-\d{4,})", os.path.basename(path)).group(1)
    mark(ctx, iid, "ticketed", "ticket %s filed to %s" % (tid, draft["to"]), ticket=tid)
    return draft, tid


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def build_parser():
    p = argparse.ArgumentParser(description="The /author:next plan and roadmap writes.")
    common = argparse.ArgumentParser(add_help=False)
    for opt in ("--home", "--agenda", "--roadmap", "--board", "--workspace", "--instance",
                "--ns", "--statuses"):
        common.add_argument(opt, default=None)
    common.add_argument("--items", type=int, default=None)
    sub = p.add_subparsers(dest="cmd")
    sp = sub.add_parser("plan", parents=[common])
    sp.add_argument("--json", action="store_true")
    sf = sub.add_parser("file", parents=[common])
    sf.add_argument("id")
    sf.add_argument("--dry-run", action="store_true")
    sm = sub.add_parser("mark", parents=[common])
    sm.add_argument("id")
    sm.add_argument("--status", default=None)
    sm.add_argument("--note", default="")
    sm.add_argument("--ticket", default=None)
    sa = sub.add_parser("add", parents=[common])
    sa.add_argument("--tag", required=True)
    sa.add_argument("--title", required=True)
    sa.add_argument("--attach", dest="item_agenda", default="",
                    help="the agenda entry (label or claim id) the item attaches to")
    sa.add_argument("--priority", default="normal")
    sa.add_argument("--depends-on", default="")
    sa.add_argument("--route", default="")
    sa.add_argument("--source", default="")
    sa.add_argument("--body", default="")
    return p


def main(argv=None):
    _utf8()
    args = build_parser().parse_args(argv)
    cmd = args.cmd or "plan"
    if not hasattr(args, "home"):
        args = build_parser().parse_args(["plan"] + list(argv or []))
    try:
        ctx = load_context(args)
        if cmd == "plan":
            p = plan(ctx)
            if getattr(args, "json", False):
                print(json.dumps(p, indent=2, ensure_ascii=False))
            else:
                print(render_plan(p))
            return 0 if p["selected"] else 1
        if cmd == "file":
            draft, tid = file_ticket(ctx, args.id, args.dry_run)
            print(json.dumps({"ticket": tid, "draft": draft}, indent=2, ensure_ascii=False))
            return 0
        if cmd == "mark":
            it = mark(ctx, args.id, args.status, args.note, args.ticket)
            print("%s: status %s" % (it.id, it.status))
            return 0
        if cmd == "add":
            it = add(ctx, args.tag, args.title, args.item_agenda, args.priority,
                     al.split_list(args.depends_on), args.route, args.source, args.body)
            print(it.id)
            return 0
    except (NextError, al.AgendaError, ac.AcademyError, OSError, ValueError) as exc:
        sys.stderr.write("next.py: %s\n" % exc)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
