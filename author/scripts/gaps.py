"""gaps -- the agenda entries with no ticket working on them, and filing a ticket.

The one module that ``inbox.py`` (the header), ``agenda.py`` (``gaps``, ``gaps --file``,
``show``, ``milestones``) and ``agenda_migrate.py`` (the converter) all import, so that
none of them imports another (``agenda.py`` used to import ``inbox.py`` while ``inbox.py``
lazily imported ``agenda.py``). It knows a *context* only by its attributes (``agenda``,
``tickets``, ``board``, ``instance``, ``ns``, ``domains``, ``workspace``), never by class.

A ticket is attached to an agenda entry by its ``agenda`` field, which a filed ticket
sets to the entry's **qualified label** (``<ns>:<label>``): the label is unique in an
agenda, a claim id is not (two entries may rest on one claim), so the attachment is exact.
``refs`` carries the claim.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import agenda_lib as al  # noqa: E402
import routes as rt  # noqa: E402

#: a ticket in one of these will never be delivered (``closed`` is terminal, but it was)
DEAD = tuple(s for s in ac.TERMINAL if s != "closed")

#: a gap no ticket can close: the entry waits for Roey, and ``--file`` reports it held
HOLD = "hold"

#: which ask a gap needs: (current in ..., required in ... or None, tag, why). First match
#: wins; ``hold`` is reported, never filed.
GAP_PROPOSALS = (
    (("missing",), None, HOLD,
     "no registry record for the claim: Roey creates it (claims_new, unsettled status; "
     "the claim-keeper sets statuses), then the gap is seen again"),
    (("refuted", "refuted-as-stated"), None, HOLD,
     "the claim is refuted: nobody verifies or proves it; Roey decides (change what the "
     "entry requires, repair the statement, or drop the entry)"),
    (("superseded", "dropped"), None, HOLD,
     "the claim's record is no longer active: Roey decides what the entry should point at"),
    (("sketch", "supported"), ("proved-modulo", "proved"), "verify",
     "an argument exists; two agreeing verdicts are needed"),
    (("open", "conjectured", ""), ("sketch", "supported", "proved-modulo", "proved"), "lead",
     "no argument yet; a proof must come from the Researcher (the Author never "
     "invents one)"),
    (("proved-modulo",), ("proved",), "lead",
     "proved modulo inputs; the missing inputs need proofs"),
)


def board_module():
    """``academy/scripts/board.py``: the one place a ticket is written."""
    p = os.path.join(ac.repo_root(), "academy", "scripts")
    if p not in sys.path:
        sys.path.insert(0, p)
    import board  # noqa: E402
    return board


# ----------------------------------------------------------------------------
# Which ticket works on which entry
# ----------------------------------------------------------------------------

def entry_ref(ctx, e):
    """The ``agenda`` value of a ticket for entry ``e``: its qualified label."""
    return "%s:%s" % (ctx.ns, e.label) if ctx.ns else e.label


def claim_refs(e):
    return [e.claim] if e.claim not in ("", "-") else []


def entry_tickets(ctx):
    """{agenda label: [ids of the non-terminal tickets to or from this instance]}."""
    out = {}
    for tid in sorted(ctx.tickets, key=ac.inbox_core.num):
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
    """The entries below their required status with no non-terminal ticket attached."""
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


# ----------------------------------------------------------------------------
# Drafting and filing
# ----------------------------------------------------------------------------

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


def ticket_draft(ctx, gap):
    """The ticket a (non-hold) gap becomes: ``{to, kind, title, ask, deliverable, refs,
    agenda, final_to, note}``. The asks go to the Expert instance sharing a domain
    (``research`` with ``final_to`` for ``lead``)."""
    e = ctx.agenda.lookup(gap["label"], ctx.ns)
    tag = gap["proposed_tag"]
    if tag not in rt.OUT_ROUTES:
        raise al.AgendaError("gap %s: %r is not something a ticket can be filed for"
                             % (gap["label"], tag))
    role, kind, final_to, dkey = rt.OUT_ROUTES[tag]
    to, note = target_instance(ctx, role)
    verb = {"verify": "Verify", "lead": "Prove"}.get(tag, "Work on")
    return {"to": to, "kind": kind, "title": "%s %s" % (verb, e.label),
            "ask": "%s %s (status %s, needs %s): %s" % (verb, e.label, gap["status"],
                                                       gap["required"], gap["why"]),
            "deliverable": rt.DELIVERABLES[dkey], "refs": claim_refs(e),
            "agenda": entry_ref(ctx, e), "final_to": final_to, "note": note,
            "priority": "normal", "domain": (ctx.domains or [None])[0]}


_RE_TID = re.compile(r"(T-\d{4,})")
_RE_ISSUE = re.compile(r"#(\d+)$")


def ticket_id_of(ref):
    """The ticket id behind the ref ``create_ticket`` returns: a file name
    ``T-NNNN-...md``, or a github ref ``github#N``."""
    base = os.path.basename(str(ref))
    m = _RE_TID.match(base)
    if m:
        return m.group(1)
    m = _RE_ISSUE.search(str(ref))
    if m:
        return ac.format_id("T", int(m.group(1)))
    raise al.AgendaError("cannot tell the ticket id of %r" % (ref,))


def file_ticket(ctx, draft, detail="", campaign=None):
    """File ``draft`` (the keys of ``ticket_draft``) from this instance through
    ``board.create_ticket``; record it in ``ctx.tickets``; return its id. The one place
    the gap filer and the roadmap converter create a ticket."""
    if not ctx.board:
        raise al.AgendaError("no board (workspace.json 'board', or --board)")
    path = board_module().create_ticket(
        ctx.board, draft["to"], draft["title"], draft["ask"], draft["deliverable"],
        kind=draft["kind"], priority=draft["priority"], refs=draft["refs"],
        agenda=draft["agenda"], domain=draft["domain"], detail=detail,
        as_instance=ctx.instance, agent=ac.MAIN_AGENT, final_to=draft["final_to"],
        campaign=campaign or None,
        workspace=ctx.workspace if ctx.workspace.get("instances") else None)
    tid = ticket_id_of(path)
    meta = ctx.board.get(tid)[1]
    ctx.tickets[tid] = dict(meta, _path=path)
    return tid


def file_gaps(ctx, dry_run=False, campaign=None):
    """File one ticket per gap; returns ``{"filed": [...], "held": [...]}``.

    Idempotent: a gap is an entry with no non-terminal ticket attached, so once filed
    the entry is busy and a second run files nothing. Held (reported, not filed): a
    verification whose inputs are not yet at their required status, a gap only Roey can
    close (``hold``: a refuted or missing claim), an ask with no receiver.
    """
    if not ctx.board:
        raise al.AgendaError("no board (workspace.json 'board', or --board)")
    filed, held = [], []
    for g in gaps(ctx):
        if g["proposed_tag"] == HOLD:
            held.append({"label": g["label"], "why": g["why"]})
            continue
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
            row["ticket"] = file_ticket(ctx, d, campaign=campaign)
        filed.append(row)
    return {"filed": filed, "held": held}
