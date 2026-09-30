"""agenda_migrate.py -- one-shot converter: an old Drafts/roadmap.md -> board tickets.

    py agenda_migrate.py --roadmap Drafts/roadmap.md [--home DIR] [--apply] [--json]
        [--board DIR --workspace FILE --instance NAME --ns NS --agenda FILE]

The roadmap was dropped (docs/superpowers/specs/2026-09-29-campaign-mode-design.md,
section 10): the board is the Author's only queue. This script turns the items of an
existing roadmap into tickets, once. It is the only code that still knows the roadmap
format, and it only *reads* the file: the human archives ``Drafts/roadmap.md`` (for
example ``git mv Drafts/roadmap.md Drafts/archive/``) after a run, and nothing writes it.

**Dry run by default.** Without ``--apply`` it prints the mapping and files nothing.
With ``--apply`` it files the tickets through ``board.create_ticket`` (from this Author
instance) and is idempotent: an item whose ticket carries its ``roadmap item R-NNNN``
provenance line, or that already names a ticket (``ticketed``), is never filed again, so
a second run files nothing new.

Mapping, by item status:

| roadmap item | ticket |
|---|---|
| ``done``, ``dropped`` | none (counted; the ticket history and the paper are the record) |
| ``ticketed`` | none: it already has a ticket (named in the report; a ticket missing from the board is reported as a problem) |
| ``open``, tag ``write apply figure build notation sweep`` (or a ``route:`` agent) | a self-ticket, kind ``write apply figure build notation sweep`` (the ``route`` agent's kind wins) |
| ``open``, tag ``lead verify cite experiment referee`` | an ask to the Expert instance sharing a domain (``lead`` and ``experiment`` as ``research`` with ``final_to``; ``verify``, ``cite``, ``referee`` as themselves) |
| ``needs-human``, ``blocked`` | a self-ticket (kind by tag; ``question`` for an ask tag), parked ``blocked`` on ``human`` |

``agenda`` is the item's entry as the claim id (else the label, else ``global``);
``refs`` the claim and any ``<ns>:<id>`` the item depends on; ``priority`` and the body
carry over, the body prefixed by a provenance line and any dependency text.

Dependencies: an item depending on another item or on a ticket becomes a ticket
``waiting_on`` the other's ticket (a self-ticket only; parked blocked, released by the
inbox when the ticket it waits on is delivered), or, for an ask that leaves the Author,
*held* (not filed; run again once the dependency is met). A dependency on an agenda
entry or a claim becomes a line in the ticket body, not a wait. A dropped or rejected
dependency holds the item. Everything held, and every judgement call, is in the report.

Exit codes: 0 ok; 1 nothing to convert; 2 error.
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
import agenda as ag  # noqa: E402
import agenda_lib as al  # noqa: E402
import inbox as nx  # noqa: E402
import routes as rt  # noqa: E402

TAGS = ("write", "apply", "lead", "verify", "cite", "experiment", "figure", "build",
        "notation", "sweep", "referee")
STATUSES = ("open", "ticketed", "blocked", "needs-human", "done", "dropped")
#: an item's ``route:`` agent -> the ticket kind that routes back to it
AGENT_KINDS = {"math-writer": "write", "math-editor": "apply", "figure-maker": "figure",
               "tex-engineer": "build", "notation-auditor": "notation",
               "note-sweeper": "sweep"}
SELF_TAG_KINDS = {"write": "write", "apply": "apply", "figure": "figure", "build": "build",
                  "notation": "notation", "sweep": "sweep"}

RE_ITEM_HEAD = re.compile(r"^## (R-\d{4,}) \[([a-z][a-z-]*)\] ?(.*)$")
RE_FIELD = re.compile(r"^- ([a-z_]+):(?: (.*))?$")
RE_ITEM_ID = re.compile(r"^R-\d{4,}$")
RE_PROVENANCE = re.compile(r"roadmap item (R-\d{4,})")


class Item(object):
    """One legacy roadmap item (read-only)."""

    def __init__(self, id, tag, title, fields, body):
        self.id, self.tag, self.title = id, tag, title
        self.fields, self.body = fields, body

    @property
    def status(self):
        return (self.fields.get("status") or "open").strip()

    @property
    def agenda(self):
        return (self.fields.get("agenda") or "").strip().strip("`")

    @property
    def priority(self):
        p = (self.fields.get("priority") or "normal").strip()
        return p if p in al.PRIORITIES else "normal"

    @property
    def depends_on(self):
        return al.split_list(self.fields.get("depends_on", ""))

    @property
    def ticket(self):
        return (self.fields.get("ticket") or "").strip()

    @property
    def route(self):
        return (self.fields.get("route") or "").strip()


def parse_items(text):
    """The ``## R-NNNN [tag] title`` items of a roadmap file's text, in order. Other
    ``##`` sections are ignored. Raises AgendaError on a duplicate id."""
    lines = text.replace("\r\n", "\n").split("\n")
    items, seen, i = [], set(), 0
    while i < len(lines):
        m = RE_ITEM_HEAD.match(lines[i])
        j = i + 1
        while j < len(lines) and not lines[j].startswith("## "):
            j += 1
        if m:
            if m.group(1) in seen:
                raise al.AgendaError("duplicate roadmap item %s" % m.group(1))
            seen.add(m.group(1))
            chunk, k, fields = lines[i + 1:j], 0, {}
            while k < len(chunk) and not chunk[k].strip():
                k += 1
            while k < len(chunk):
                fm = RE_FIELD.match(chunk[k])
                if not fm:
                    break
                fields[fm.group(1)] = (fm.group(2) or "").strip()
                k += 1
            items.append(Item(m.group(1), m.group(2), m.group(3).strip(), fields,
                              "\n".join(chunk[k:]).strip("\n")))
        i = j
    return items


def _one_line(text, limit=240):
    for para in (text or "").split("\n\n"):
        s = " ".join(para.split())
        if s and not s.startswith("<!--"):
            return s if len(s) <= limit else s[:limit - 3].rstrip() + "..."
    return ""


def _ask_line(it, limit=240):
    """``<title> -- <first paragraph>``, one line."""
    first = re.sub(r"^(?:[-*+]|\d+\.)\s+", "", _one_line(it.body, limit))
    if not first or first == it.title:
        return it.title
    s = "%s -- %s" % (it.title, first)
    return s if len(s) <= limit else s[:limit - 3].rstrip() + "..."


# ----------------------------------------------------------------------------
# The mapping
# ----------------------------------------------------------------------------

def local_kind(it):
    """The ticket kind of an item that stays in the Author, or None for an ask."""
    if it.route:
        return AGENT_KINDS.get(it.route) or SELF_TAG_KINDS.get(it.tag)
    return SELF_TAG_KINDS.get(it.tag)


def _claim_of(ctx, it):
    """(agenda field value, claim id or None) of an item's agenda attachment."""
    if not it.agenda or it.agenda == "global":
        return "global", None
    e = ctx.agenda.lookup(it.agenda, ctx.ns)
    if e is not None and e.claim not in ("", "-"):
        return e.claim, e.claim
    if e is not None:
        ref = "%s:%s" % (ctx.ns, e.label) if ctx.ns else e.label
        return ref, None
    return it.agenda, None


def _existing(ctx):
    """{item id: ticket id} of the tickets this instance already filed for an item."""
    out = {}
    for tid in sorted(ctx.tickets, key=nx._num):
        t = ctx.tickets[tid]
        if t.get("from") != ctx.instance or t.get("status") in nx.TICKET_DEAD:
            continue
        m = RE_PROVENANCE.search(t.get("_body") or "")
        if m:
            out.setdefault(m.group(1), tid)
    return out


def _dep_lines(deps):
    return "Depends on: " + ", ".join("`%s`" % d for d in deps) if deps else ""


def draft(ctx, it, waits, text_deps):
    """The ticket an open (or parked) item becomes, as a dict."""
    agenda, claim = _claim_of(ctx, it)
    refs = [claim] if claim else []
    for d in text_deps:
        if ":" in d and d not in refs:
            refs.append(d)
    parked = it.status in ("needs-human", "blocked")
    kind = local_kind(it)
    ask_tag = it.tag in rt.OUT_ROUTES and not it.route
    final_to, note = None, ""
    if ask_tag and not parked:
        role, kind, final_to, dkey = rt.OUT_ROUTES[it.tag]
        to, note = ag.target_instance(ctx, role)
        deliverable = rt.DELIVERABLES[dkey]
    else:
        to, deliverable = ctx.instance, rt.SELF_DELIVERABLE
        kind = kind or "question"
    prov = "Migrated from roadmap item %s (status %s) by agenda_migrate.py." % (it.id,
                                                                                it.status)
    body = "\n\n".join(x for x in (prov, _dep_lines(text_deps), it.body.strip()) if x)
    return {"item": it.id, "to": to, "kind": kind, "title": it.title, "ask": _ask_line(it),
            "deliverable": deliverable, "refs": refs, "agenda": agenda,
            "priority": it.priority, "domain": (ctx.domains or [None])[0],
            "detail": body, "final_to": final_to, "note": note, "waiting_on": waits,
            "parked": parked}


def plan(ctx, items):
    """The conversion as a dict: ``convert`` (drafts, dependency order), ``skipped``
    (already ticketed, done, dropped), ``held`` (reason each), ``problems``."""
    existing = _existing(ctx)
    by_id = {it.id: it for it in items}
    convert, skipped, held, problems = [], [], [], []
    counts = {"done": 0, "dropped": 0}
    ticket_of = {}                      # item id -> ticket id (real) or None (to be filed)
    state = {}                          # item id -> "filed" | "held" | "skipped" | "gone"
    pending = []
    for it in items:
        if it.tag not in TAGS:
            problems.append("%s: unknown tag [%s]; not converted" % (it.id, it.tag))
            state[it.id] = "held"
            held.append({"item": it.id, "why": "unknown tag [%s]" % it.tag})
            continue
        if it.status not in STATUSES:
            problems.append("%s: unknown status %r; not converted" % (it.id, it.status))
            state[it.id] = "held"
            held.append({"item": it.id, "why": "unknown status %r" % it.status})
            continue
        if it.status in ("done", "dropped"):
            counts[it.status] += 1
            state[it.id] = "gone" if it.status == "dropped" else "done"
            continue
        if it.id in existing:
            ticket_of[it.id] = existing[it.id]
            state[it.id] = "skipped"
            skipped.append({"item": it.id, "ticket": existing[it.id],
                            "why": "already converted"})
            continue
        if it.status == "ticketed":
            state[it.id] = "skipped"
            ticket_of[it.id] = it.ticket
            skipped.append({"item": it.id, "ticket": it.ticket, "why": "already ticketed"})
            if it.ticket not in ctx.tickets:
                problems.append("%s: ticketed as %s, which is not on the board" % (
                    it.id, it.ticket or "(no ticket named)"))
            continue
        pending.append(it)
    # dependency order: an item waits until the items it depends on are settled
    remaining, progress = list(pending), True
    while remaining and progress:
        progress = False
        for it in list(remaining):
            unmet, text_deps, dead = [], [], None
            for d in it.depends_on:
                if RE_ITEM_ID.match(d):
                    if d not in by_id:
                        dead = "depends on unknown item %s" % d
                    elif state.get(d) == "gone":
                        dead = "depends on %s, which was dropped" % d
                    elif state.get(d) == "done":
                        continue
                    elif state.get(d) == "held":
                        dead = "depends on %s, which is held" % d
                    elif d in ticket_of or state.get(d) == "filed":
                        unmet.append(("item", d))
                    else:
                        break                       # not decided yet: next pass
                elif al.RE_TICKET_ID.match(d):
                    t = ctx.tickets.get(d)
                    if t is None:
                        dead = "depends on unknown ticket %s" % d
                    elif t.get("status") in nx.TICKET_DEAD:
                        dead = "depends on ticket %s, which was %s" % (d, t.get("status"))
                    elif t.get("status") not in ("delivered", "closed"):
                        unmet.append(("ticket", d))
                else:
                    text_deps.append(d)
            else:
                remaining.remove(it)
                progress = True
                if dead:
                    state[it.id] = "held"
                    held.append({"item": it.id, "why": dead})
                    continue
                waits = []
                for kind, d in unmet:
                    real = ticket_of.get(d) if kind == "item" else d
                    t = ctx.tickets.get(real) if real else None
                    if kind == "item" and real and t is not None \
                            and t.get("status") in ("delivered", "closed"):
                        continue
                    waits.append(real or d)         # d: the item id, until it is filed
                dr = draft(ctx, it, waits, text_deps)
                if dr["parked"]:
                    dr["waits_human"] = True
                if waits and dr["to"] != ctx.instance:
                    state[it.id] = "held"
                    held.append({"item": it.id, "why": "an ask to %s that waits for %s: "
                                 "run again once it is delivered" % (dr["to"], ", ".join(
                                     waits))})
                    continue
                if not dr["to"]:
                    state[it.id] = "held"
                    held.append({"item": it.id, "why": "no receiver: " + dr["note"]})
                    continue
                state[it.id] = "filed"
                convert.append(dr)
    for it in remaining:                    # a cycle
        state[it.id] = "held"
        held.append({"item": it.id, "why": "dependency cycle or unresolved dependency"})
    return {"convert": convert, "skipped": skipped, "held": held, "problems": problems,
            "counts": counts}


def apply(ctx, pl):
    """File the planned tickets; returns ``{item id: ticket id}``. Never writes the
    roadmap file."""
    if not ctx.board:
        raise nx.InboxError("no board (workspace.json 'board', or --board)")
    bd = nx.board_module()
    made = {}
    for dr in pl["convert"]:
        path = bd.create_ticket(
            ctx.board, dr["to"], dr["title"], dr["ask"], dr["deliverable"],
            kind=dr["kind"], priority=dr["priority"], refs=dr["refs"],
            agenda=dr["agenda"], domain=dr["domain"], detail=dr["detail"],
            as_instance=ctx.instance, agent=ac.MAIN_AGENT, final_to=dr["final_to"],
            workspace=ctx.workspace if ctx.workspace.get("instances") else None)
        made[dr["item"]] = re.match(r"^(T-\d{4,})", os.path.basename(path)).group(1)
    for dr in pl["convert"]:
        waits = [made.get(w, w) for w in dr["waiting_on"]]
        waits = [w for w in waits if al.RE_TICKET_ID.match(w)]
        if dr["parked"]:
            waits = ["human"] + waits
        if not waits:
            continue
        reason = ("roadmap item %s was %s" % (dr["item"], "parked for Roey"
                                            if dr["parked"] else "waiting on %s"
                                            % ", ".join(waits)))
        bd.transition_ticket(ctx.board, made[dr["item"]], "blocked", waiting_on=waits,
                             reason=reason, as_instance=ctx.instance, agent=ac.MAIN_AGENT)
    return made


def render(pl, made, dry):
    out = ["%s: %d ticket(s) %s, %d skipped, %d held, done %d, dropped %d." % (
        "DRY RUN" if dry else "APPLIED", len(pl["convert"]),
        "to file" if dry else "filed", len(pl["skipped"]), len(pl["held"]),
        pl["counts"]["done"], pl["counts"]["dropped"]), ""]
    for dr in pl["convert"]:
        out.append("  %s -> %s %s (%s) agenda %s%s%s" % (
            dr["item"], made.get(dr["item"], "(new)"), dr["to"], dr["kind"], dr["agenda"],
            "  parked on human" if dr["parked"] else "",
            ("  waits for " + ", ".join(dr["waiting_on"])) if dr["waiting_on"] else ""))
    for s in pl["skipped"]:
        out.append("  %s: skipped, %s (%s)" % (s["item"], s["why"], s["ticket"] or "?"))
    for h in pl["held"]:
        out.append("  %s: HELD, %s" % (h["item"], h["why"]))
    for p in pl["problems"]:
        out.append("  problem: " + p)
    if dry:
        out += ["", "Nothing was written. Re-run with --apply to file the tickets; then "
                    "archive the roadmap file by hand."]
    return "\n".join(out)


def main(argv=None):
    nx._utf8()
    p = argparse.ArgumentParser(
        description="One-shot converter: an old Drafts/roadmap.md -> board tickets "
                    "(dry run unless --apply; never writes the roadmap).")
    p.add_argument("--roadmap", required=True, help="the old roadmap file (read only)")
    p.add_argument("--apply", action="store_true", help="file the tickets (default: dry run)")
    p.add_argument("--json", action="store_true")
    for opt in ("--home", "--agenda", "--board", "--workspace", "--instance", "--ns"):
        p.add_argument(opt, default=None)
    a = p.parse_args(argv)
    try:
        ns_args = argparse.Namespace(home=a.home, agenda=a.agenda, board=a.board,
                                     workspace=a.workspace, instance=a.instance, ns=a.ns,
                                     items=None)
        ctx = nx.load_context(ns_args)
        items = parse_items(al.read_text(a.roadmap))
        pl = plan(ctx, items)
        made = apply(ctx, pl) if a.apply and pl["convert"] else {}
        if a.json:
            print(json.dumps({"dry_run": not a.apply, "made": made, **{
                k: pl[k] for k in ("convert", "skipped", "held", "problems", "counts")}},
                indent=2, ensure_ascii=False))
        else:
            print(render(pl, made, not a.apply))
        return 0 if pl["convert"] else 1
    except (nx.InboxError, al.AgendaError, ac.AcademyError, OSError, ValueError) as exc:
        sys.stderr.write("agenda_migrate.py: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
