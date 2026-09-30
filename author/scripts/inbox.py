"""inbox.py -- the Author's inbox: roadmap items become self-tickets, tickets are routed.

    py inbox.py [--sync] [--n N] [--all] [--json] [--campaign TARGET]
    py inbox.py --check T-NNNN                the serial checkpoint of a ticket just handled
    py inbox.py sync [--dry-run]              file the ready roadmap items; settle delivered ones
    py inbox.py file R-NNNN [--dry-run]       file one item's ticket and mark it ticketed
    py inbox.py mark R-NNNN --status S [--note TEXT] [--ticket T-NNNN]
    py inbox.py add --tag T --title TITLE [--attach ID] [--priority P] [--depends-on a,b]
                    [--route AGENT] [--source S] [--body TEXT]    prints the new id

Common options: ``--home DIR`` (default: the Author home holding the cwd), and for
tests ``--agenda FILE --roadmap FILE --board DIR --workspace FILE --instance NAME
--ns NS`` in place of the home's config.

A thin wrapper over the academy's ``inbox_core`` (``_academy.py``): the board is the
single queue and the roadmap stays the place the human edits. The Author's routing
table is ``routes.py``. What is Author-specific lives here:

1. **Sweep first.** Every run starts with the machine-note sweep (``note-sweeper``, as
   ``/author:sweep`` does); the output says so first and it counts against no item cap.
2. **Filing (``sync``, or ``--sync`` before the selection).** Each ``open`` roadmap item
   whose dependencies are met is filed once: an item that stays in the Author
   (``write`` ``apply`` ``figure`` ``build`` ``notation`` ``sweep``, or with a ``route:``)
   as a ticket from this instance to itself (kind = the item kind, ``refs`` = the item id
   and its claim, ``agenda`` = its entry); an ask (``lead`` ``verify`` ``cite``
   ``experiment`` ``referee``) as a ticket to the Expert instance sharing a domain
   (``lead`` and ``experiment`` as ``research`` with ``final_to``). Filing is idempotent:
   an item already ticketed, or whose ticket is already on the board, is never filed
   again. A delivered self-ticket is closed and its item marked ``done``.
3. **Selection.** The core's, in the Author's precedence: in-progress tickets first,
   then returned tickets to land (an item whose ticket to another role came back;
   ``"return": true``), then ``open``/``accepted`` tickets ordered by the earliest agenda
   position they unblock (their own entry, or any entry resting on it, transitively),
   then priority, then id. At most ``budget.itemsPerRun`` (never more than 3).

Readiness: an item is ready when every dependency is met. A dependency is an item (met
when ``done``), a ticket (met when ``delivered`` or ``closed``), or an agenda entry / claim
id (met when its status reaches the entry's ``required``). A ``[verify]`` item also
waits for the entries its agenda entry depends on (a verdict on top of unproved inputs
is only a verdict modulo them). ``--all`` also lists the waiting and the parked items.

Exit codes: 0 ok; 1 nothing to take / nothing to do; 2 error (one line on stderr); 3 for
``--check`` on an unfinished ticket.
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
from routes import AGENT_KINDS, ITEM_KINDS, LAND_ROUTES, land_route, route  # noqa: E402

core = ac.inbox_core

#: an item that stays in the Author is served by this agent (its ``route:`` overrides)
AGENT_ROUTES = {"write": "math-writer", "apply": "math-editor", "figure": "figure-maker",
                "build": "tex-engineer", "notation": "notation-auditor",
                "sweep": "note-sweeper"}
ASK_ROUTES = {"lead": ("expert", "research"), "verify": ("expert", "verify"),
              "cite": ("expert", "cite"), "experiment": ("expert", "research"),
              "referee": ("expert", "referee")}
#: the role a relayed ask is really for (docs/protocol.md section 5)
FINAL_TO = {"lead": "researcher", "experiment": "scientist"}
#: the deliverable of a relayed ask is the final receiver's
DELIVERABLE_OF = {"lead": "prove", "experiment": "experiment"}
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
SELF_DELIVERABLE = ("The item's work done in the paper and recorded (`inbox.py mark R-NNNN "
                    "--status done`); this ticket delivered with a one-line result.")
TICKET_MET = ("delivered", "closed")
TICKET_DEAD = ("rejected", "cancelled")
INBOX_ACTIVE = ("open", "accepted", "in-progress")
MAX_ITEMS = 3
INF = 10 ** 9
RE_HISTORY = re.compile(r"^- \d{4}-\d{2}-\d{2}: ")


class InboxError(Exception):
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
    home = args.home
    if not home and args.instance:
        # /academy:inbox runs from anywhere: the instance names its home in workspace.json
        try:
            inst = ac.load_workspace(args.workspace)["instances"].get(args.instance) or {}
        except ac.AcademyError:
            inst = {}
        if inst.get("role") == "author":
            home = inst.get("home")
    home = home or ac.find_home(os.getcwd())
    cfg = None
    if home and os.path.isfile(os.path.join(home, ac.CONFIG_REL)):
        try:
            cfg = ac.load_config(home)
        except ac.AcademyError as exc:
            raise InboxError(str(exc))
        if cfg.get("role") != "author":
            raise InboxError("%s is a %s home, not an Author home" % (home, cfg.get("role")))
    if cfg is None and not (args.agenda and args.roadmap):
        raise InboxError("no Author home here (no .claude/academy.json with role author); "
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
        raise InboxError("no instance name (give --instance)")
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
    """The ticket an ask item becomes (dict), or raise InboxError."""
    if it.tag not in ASK_ROUTES:
        raise InboxError("%s [%s] is not an ask item (tags: %s)"
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
        "ask": _ask_line(it), "deliverable": DELIVERABLES[DELIVERABLE_OF.get(it.tag, kind)],
        "refs": refs, "agenda": claim or (it.agenda or "global"),
        "priority": it.priority, "domain": (ctx.domains or [None])[0],
        "detail": it.body.strip(), "note": note,
        "final_to": FINAL_TO.get(it.tag),
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


def _is_self(ctx, t):
    return t.get("from") == ctx.instance and t.get("to") == ctx.instance


def _local_agent(it):
    """The agent serving an item that stays in the Author, or None for an ask item."""
    route_field = (it.fields.get("route") or "").strip()
    if it.tag in ASK_ROUTES and not route_field:
        return None
    return route_field or AGENT_ROUTES.get(it.tag)


def local_kind(it):
    """The ticket kind of an item's self-ticket: routes back to the item's agent."""
    agent = _local_agent(it)
    return AGENT_KINDS.get(agent) or ITEM_KINDS.get(it.tag) if agent else None


def self_draft(ctx, it):
    """The self-ticket a local item becomes (dict)."""
    e = ctx.agenda.lookup(it.agenda, ctx.ns) if it.agenda and it.agenda != "global" else None
    claim = e.claim if e is not None and e.claim not in ("", "-") else None
    kind = local_kind(it) or "other"
    refs = [it.id] + ([claim] if claim else [])
    for d in it.depends_on:
        if ":" in d and d not in refs and not al.RE_ITEM_ID.match(d):
            refs.append(d)
    return {"to": ctx.instance, "kind": kind, "title": it.title, "ask": _ask_line(it),
            "deliverable": SELF_DELIVERABLE, "refs": refs,
            "agenda": claim or (it.agenda or "global"), "priority": it.priority,
            "domain": (ctx.domains or [None])[0], "detail": it.body.strip(), "note": "",
            "final_to": None}


def draft_for(ctx, it):
    return ticket_draft(ctx, it) if it.tag in ASK_ROUTES and not _local_agent(it) \
        else self_draft(ctx, it)


def plan(ctx):
    """The items as a dict: ``to_file`` (ready, ordered), ``land`` (returned tickets to
    land, ordered), ``settle`` (delivered self-tickets), ``waiting``, ``parked``, ``notes``."""
    to_file, land, settle, waiting, parked, notes = [], [], [], [], [], []
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
            if _is_self(ctx, t):
                if t.get("status") in TICKET_MET:
                    rec.update(ticket=it.ticket, result=t.get("result"))
                    settle.append(rec)
                elif t.get("status") not in INBOX_ACTIVE:
                    rec["reason"] = "waits for ticket %s (%s)" % (it.ticket, t.get("status"))
                    waiting.append(rec)
                continue                      # open / accepted / in-progress: in the inbox
            if t.get("status") not in TICKET_MET:
                rec["reason"] = "waits for ticket %s (%s)" % (it.ticket, t.get("status"))
                waiting.append(rec)
                continue
            rec.update(action="land", ticket=it.ticket, result=t.get("result"),
                       kind=t.get("kind"), path=str(t.get("_path", "")).replace("\\", "/"))
        elif st == "open":
            if it.tag in ASK_ROUTES and not _local_agent(it):
                draft = ticket_draft(ctx, it)
                rec.update(action="ticket", to=draft["to"], kind=draft["kind"])
                if draft["note"]:
                    rec["note"] = draft["note"]
                if not draft["to"]:
                    rec["reason"] = "no receiver: " + draft["note"]
                    parked.append(rec)
                    continue
            elif _local_agent(it):
                rec.update(action="self", to=ctx.instance, kind=local_kind(it) or "other",
                           agent=_local_agent(it))
            else:
                rec["reason"] = "no agent for [%s]" % it.tag
                parked.append(rec)
                continue
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
        rec["_key"] = (pos, al.PRIORITY_RANK[it.priority], order)
        (land if rec["action"] == "land" else to_file).append(rec)
    for lst in (to_file, land):
        lst.sort(key=lambda r: r["_key"])
        for r in lst:
            del r["_key"]
    return {"instance": ctx.instance, "to_file": to_file, "land": land, "settle": settle,
            "waiting": waiting, "parked": parked, "notes": notes}


def land_rows(ctx, p):
    """The returned tickets to land, as inbox rows (``return: true``), in plan order."""
    rows = []
    for r in p["land"]:
        t = ctx.tickets.get(r["ticket"]) or {}
        rt = land_route(r["tag"])
        rt["why"] += " (item %s; ticket %s came back: %s)" % (r["id"], r["ticket"],
                                                              r.get("result") or "no result")
        rows.append({"id": r["ticket"], "kind": t.get("kind"), "status": t.get("status"),
                     "priority": r["priority"], "from": ctx.instance, "title": r["title"],
                     "agenda": t.get("agenda"), "budget": t.get("budget"),
                     "refs": t.get("refs") or [r["id"]], "campaign": t.get("campaign"),
                     "route": rt, "return": True, "over_budget": None, "blocked": None,
                     "path": r.get("path"), "item": r["id"]})
    return rows


def render_lists(p):
    out = []
    for name in ("waiting", "parked"):
        out.append("")
        out.append("%s (%d)" % (name.upper(), len(p[name])))
        for r in p[name]:
            out.append("  %s [%s] %s -- %s" % (r["id"], r["tag"], r["title"], r["reason"]))
    if p["notes"]:
        out.append("")
        out.append("NOTES")
        out.extend("  " + n for n in p["notes"])
    return out


# ----------------------------------------------------------------------------
# Writes to the roadmap
# ----------------------------------------------------------------------------

def _save_roadmap(ctx):
    al.write_text(ctx.roadmap_path, al.write_roadmap(ctx.roadmap))


def _sync_self_ticket(ctx, it, status, note=""):
    """Keep an item's self-ticket in step when the item is marked (this instance is both ends).

    ``done`` walks the ticket to ``delivered`` (result: the note) and ``closed``;
    ``blocked`` or ``needs-human`` parks it ``blocked`` on ``human``, so the inbox does
    not offer it again while the item waits.
    """
    t = ctx.tickets.get(it.ticket) if it.ticket else None
    if t is None or not _is_self(ctx, t) or not ctx.board or status not in (
            "done", "blocked", "needs-human"):
        return
    bd = board_module()
    path = ac.find_ticket(ctx.board, it.ticket)
    if not path:
        return
    with open(path, "r", encoding="utf-8") as fh:
        st = ac.read_frontmatter(fh.read())[0].get("status")
    kw = dict(as_instance=ctx.instance, agent=ac.MAIN_AGENT)
    if status == "done":
        result = " ".join((note or "item done").split())
        steps = {"open": ("accepted", "in-progress", "delivered", "closed"),
                 "accepted": ("in-progress", "delivered", "closed"),
                 "in-progress": ("delivered", "closed"),
                 "blocked": ("in-progress", "delivered", "closed"),
                 "delivered": ("closed",)}.get(st, ())
        for new in steps:
            bd.transition_ticket(ctx.board, it.ticket, new,
                                 result=result if new == "delivered" else None, **kw)
        if steps:
            t["status"] = "closed"
    elif st in ("open", "accepted", "in-progress"):
        if st == "open":
            bd.transition_ticket(ctx.board, it.ticket, "accepted", **kw)
        bd.transition_ticket(ctx.board, it.ticket, "blocked", waiting_on=["human"],
                             reason="item %s marked %s" % (it.id, status), **kw)
        t["status"] = "blocked"


def mark(ctx, iid, status=None, note="", ticket=None, date=None):
    it = ctx.roadmap.get(iid)
    if it is None:
        raise InboxError("no roadmap item %s" % iid)
    date = date or ac.today()
    if status:
        if status not in al.ITEM_STATUSES:
            raise InboxError("status must be one of %s" % ", ".join(al.ITEM_STATUSES))
        it.fields["status"] = status
    if ticket:
        it.fields["ticket"] = ticket
    it.fields["updated"] = date
    _sync_self_ticket(ctx, it, status, note)
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
        raise InboxError("tag must be one of %s" % ", ".join(al.TAGS))
    if priority not in al.PRIORITIES:
        raise InboxError("priority must be high, normal or low")
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


def _existing_self_ticket(ctx, it):
    """A ticket from this instance already on the board for item ``it`` (its id is in
    ``refs``): a filing whose roadmap write was lost. Filing is idempotent."""
    for tid in sorted(ctx.tickets, key=lambda x: int(x.split("-")[1])):
        t = ctx.tickets[tid]
        if t.get("from") == ctx.instance and it.id in (t.get("refs") or []) \
                and t.get("status") not in TICKET_DEAD:
            return tid
    return None


def file_ticket(ctx, iid, dry_run=False):
    """File the ticket of item ``iid``; returns ``(draft, ticket id or None)``.

    Idempotent: an item that is not ``open`` is refused, and one whose ticket is already
    on the board is marked ticketed with that ticket instead of filing a second.
    """
    it = ctx.roadmap.get(iid)
    if it is None:
        raise InboxError("no roadmap item %s" % iid)
    if it.status != "open":
        raise InboxError("%s is %s, not open" % (iid, it.status))
    draft = draft_for(ctx, it)
    if not draft["to"]:
        raise InboxError(draft["note"])
    if dry_run:
        return draft, None
    if not ctx.board:
        raise InboxError("no board (workspace.json 'board', or --board)")
    tid = _existing_self_ticket(ctx, it)
    if tid:
        mark(ctx, iid, "ticketed", "ticket %s was already on the board" % tid, ticket=tid)
        return draft, tid
    bd = board_module()
    path = bd.create_ticket(ctx.board, draft["to"], draft["title"], draft["ask"],
                            draft["deliverable"], kind=draft["kind"],
                            priority=draft["priority"], refs=draft["refs"],
                            agenda=draft["agenda"], domain=draft["domain"],
                            detail=draft["detail"], as_instance=ctx.instance,
                            agent=ac.MAIN_AGENT, final_to=draft.get("final_to"),
                            workspace=ctx.workspace if ctx.workspace.get("instances") else None)
    tid = re.match(r"^(T-\d{4,})", os.path.basename(path)).group(1)
    with open(path, "r", encoding="utf-8") as fh:
        ctx.tickets[tid] = dict(ac.read_frontmatter(fh.read())[0], _path=path)
    mark(ctx, iid, "ticketed", "ticket %s filed to %s" % (tid, draft["to"]), ticket=tid)
    return draft, tid


def settle_self(ctx, rec, dry_run=False):
    """Close a delivered self-ticket and mark its item ``done``."""
    tid = rec["ticket"]
    if dry_run:
        return
    mark(ctx, rec["id"], "done", "ticket %s delivered: %s" % (tid, rec.get("result") or ""))


def sync(ctx, dry_run=False):
    """File every ready open item once, and settle delivered self-tickets.

    Returns ``{"filed": [...], "settled": [...]}``. Running it twice files nothing new.
    """
    p = plan(ctx)
    settled = []
    for rec in p["settle"]:
        settle_self(ctx, rec, dry_run)
        settled.append({"item": rec["id"], "ticket": rec["ticket"]})
    filed = []
    for rec in p["to_file"]:
        draft, tid = file_ticket(ctx, rec["id"], dry_run)
        filed.append({"item": rec["id"], "ticket": tid, "to": draft["to"],
                      "kind": draft["kind"]})
    return {"filed": filed, "settled": settled}


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


SUBCOMMANDS = ("sync", "file", "mark", "add")


def _common(p):
    for opt in ("--home", "--agenda", "--roadmap", "--board", "--workspace", "--instance",
                "--ns", "--statuses"):
        p.add_argument(opt, default=None)
    p.add_argument("--items", "--n", dest="items", type=int, default=None)


def build_parser():
    p = argparse.ArgumentParser(description="The Author's inbox and roadmap writes.")
    common = argparse.ArgumentParser(add_help=False)
    _common(common)
    sub = p.add_subparsers(dest="cmd")
    ss = sub.add_parser("sync", parents=[common])
    ss.add_argument("--dry-run", action="store_true")
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


def inbox_parser():
    ap = core.parser(__doc__.split("\n")[0], prog="inbox.py")
    for opt in ("--agenda", "--roadmap", "--ns", "--statuses"):
        ap.add_argument(opt, default=None)
    ap.add_argument("--sync", action="store_true",
                    help="file the ready roadmap items first (idempotent)")
    return ap


def sweep_step():
    return {"how": "agent", "target": "note-sweeper",
            "why": "the machine-note sweep runs before any ticket is taken; it counts "
                   "against no item cap (/author:sweep is the standalone entry)"}


def run_inbox(args):
    """The selection: sync first when asked, then the core with the Author's extras."""
    if args.check:
        board = args.board or ac.load_workspace(args.workspace)["board"]
        return core.run(args, "", board, 3, route)
    args.items = args.n
    ctx = load_context(args)
    header_text, header_json = [], {}
    if args.sync:
        res = sync(ctx)
        header_json["synced"] = res
        header_text += ["filed %s -> %s (%s)" % (f["item"], f["ticket"], f["kind"])
                        for f in res["filed"]]
        header_text += ["settled %s (ticket %s delivered)" % (s["item"], s["ticket"])
                        for s in res["settled"]]
        ctx = load_context(args)
    if not ctx.board:
        raise InboxError("no board (workspace.json 'board', or --board)")
    p = plan(ctx)
    lands = land_rows(ctx, p)
    header_json.update(land=len(lands), unfiled=len(p["to_file"]))
    if p["to_file"] and not args.sync:
        header_text.append("%d ready item(s) not filed yet: run `inbox.py sync`"
                           % len(p["to_file"]))
    if not args.all:
        header_json["sweep"] = sweep_step()
        header_text.insert(0, "SWEEP FIRST: note-sweeper, before any ticket below "
                              "(counts against no item cap)")
    after = []
    if args.all:
        header_json.update(waiting_items=p["waiting"], parked=p["parked"], notes=p["notes"])
        after = render_lists(p)
    pos = lambda m: _position(ctx, m.get("agenda"))[0]  # noqa: E731
    return core.run(args, ctx.instance, ctx.board, ctx.items_per_run, route, position=pos,
                    return_legs=False, position_first=True, extra=lands,
                    header={"json": header_json, "text": header_text, "text_after": after})


def main(argv=None):
    _utf8()
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if not argv or argv[0] not in SUBCOMMANDS:
            return run_inbox(inbox_parser().parse_args(argv))
        args = build_parser().parse_args(argv)
        cmd = args.cmd
        ctx = load_context(args)
        if cmd == "sync":
            res = sync(ctx, args.dry_run)
            print(json.dumps(res, indent=2, ensure_ascii=False))
            return 0 if res["filed"] or res["settled"] else 1
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
    except (InboxError, al.AgendaError, ac.AcademyError, OSError, ValueError) as exc:
        sys.stderr.write("inbox.py: %s\n" % exc)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
