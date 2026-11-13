"""tickets_* tools: the board protocol of docs/protocol.md, on academy_common.

Writes never commit (protocol section 2). The caller's party on a ticket is
decided by its instance against the ticket's ``from`` / ``to``; the human may do
anything, and is the only party on a ticket addressed to ``human``.
"""

import re

import academy_common as ac

from . import Tool, ToolError, obj, S, B, L

PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}
#: the ``instance`` argument of a write: the instance the caller acts for
ACTING = {"type": "string", "description":
          "The instance you act for (workspace.json), e.g. researcher@flat. Needed only "
          "when the server cannot tell (a cloud session, whose server runs outside the "
          "homes); default: the ticket's party of your role, the server's home, or the "
          "only instance of your role. A role agent can never act as 'human'."}
#: statuses ``deliver: true`` may start from
DELIVER_FROM = ("open", "accepted", "in-progress")
FROZEN = ("id", "created", "updated")
#: a status move that is not one transition is walked in one call when every status in
#: between is one of these (they need nothing of their own: no reason, no waiting_on,
#: no result) and the caller may make every hop. The ledger, 2026-10-31..11-13: 12
#: refusals of ``open -> in-progress`` after the refusal had learnt to name the route.
WALK_THROUGH = ("accepted", "in-progress")
#: arguments an agent puts inside ``fields`` although they are arguments of the call
FIELD_ARGS = ("result_detail", "ask_detail", "note", "reason", "reopen")
BLOCK_HINT = ("; pending: status 'blocked' with waiting_on: ['T-0123'] (the tickets, or "
              "'human', it waits for); a dead route: blocked_by: 'T-0123' (a ticket or "
              "registry id), reopen_if: '<what would reopen it>' and reason: '<what was "
              "tried>'")


def _who_moves(meta, pset, me, old, new, human):
    """The tail of a transition refusal: who this caller is on the ticket, the moves it
    may make from ``old``, and who makes the move asked for."""
    role = " and ".join(sorted(pset)) or "no party"
    moves = ac.allowed_moves(old, pset, human)
    out = "; %s is %s on %s (sender %s, receiver %s)" % (
        me, role, meta.get("id"), meta.get("from") or "?", meta.get("to") or "?")
    out += ("; from %s you may move it to: %s" % (old, ", ".join(moves)) if moves
            else "; from %s you may make no status move" % old)
    who = ac.TRANSITIONS.get((old, new))
    if who:
        names = [meta.get("from") if w == "sender" else meta.get("to") for w in who]
        out += "; %s -> %s is made by %s" % (old, new, " or ".join(
            "the %s (%s)" % (w, n or "?") for w, n in zip(who, names)))
    return out


def _one_line(name, value, required=True, tag=False):
    """``value`` as one line: runs of whitespace (line breaks included) become one space.
    A wrapped title or deliverable is still one sentence; ``ask`` and ``result``, whose
    extra lines are detail, go through ``_headline`` first. A ``tag`` (an instance, a
    role, a workplan's name) is refused when it spans lines: nothing sensible is meant."""
    if value is None or str(value).strip() == "":
        if required:
            raise ToolError("%s is required" % name)
        return None
    s = str(value).strip()
    if tag and ("\n" in s or "\r" in s):
        raise ToolError("%s must be one line" % name)
    return " ".join(s.split())


def _headline(value):
    """``(first line, whole text or None)`` of a field that must be one line. A caller
    that writes the detail into ``ask`` or ``result`` (18 and 1 refusals in the ledger,
    five weeks running) gets what it meant: the first line is the field, the whole text
    goes to the body section."""
    if value is None:
        return None, None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if "\n" not in text:
        return text, None
    first = next(ln.strip() for ln in text.split("\n") if ln.strip())
    return first.lstrip("#-* ").strip() or first, text


def _default_budget(ctx):
    """``{"runs": n}`` from the caller's home ``budget.ticketDefault`` (no max_model)."""
    try:
        home = ac.find_home(ctx.cwd)
        cfg = ac.load_config(home) if home else None
    except ac.ConfigError:
        cfg = None
    return ac.default_ticket_budget(cfg)


def load_ticket(ctx, tid):
    """``(ref, meta, body)`` of ticket ``tid`` on the caller's store (one fetch)."""
    if not ac.RE_TICKET_ID.match(str(tid or "")):
        hint = ""
        if re.match(r"^P-\d+$", str(tid or "")):
            hint = "; %s is a packet: read it with packets_get" % tid
        raise ToolError("a ticket id looks like T-0007, got %r%s" % (tid, hint))
    try:
        return ctx.store.get(tid)
    except ac.AcademyError:
        raise ToolError("no ticket %s on the board %s" % (tid, ctx.board))


def ticket_text(ctx, tid):
    """The ticket as a file would read (frontmatter and body), on either backend."""
    _ref, meta, body = load_ticket(ctx, tid)
    return ac.write_frontmatter({k: meta[k] for k in ac.TICKET_KEY_ORDER if k in meta}, body)


def replace_section(body, heading, text):
    """Replace the content under ``## heading`` (up to the next '## ') with ``text``."""
    lines = body.replace("\r\n", "\n").split("\n")
    h = "## " + heading
    if h not in lines:
        raise ToolError("the body has no %r section" % h)
    start = lines.index(h) + 1
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    block = [""] + (text.strip().split("\n") if text.strip() else []) + [""]
    if not text.strip():
        block = ["", ""]
    return "\n".join(lines[:start] + block + lines[end:])


def create_ticket(ctx, a, clerical=False):
    """Create a ticket from ``a`` (title, kind, to, ask, deliverable, ...)."""
    if a.get("parent") and ctx.ticket_hint is None and ctx.store.find(a["parent"]):
        try:            # an agent filing a child acts for its party on the parent
            ctx.ticket_hint = load_ticket(ctx, a["parent"])[1]
        except ToolError:
            pass
    a = dict(a)
    ask, ask_rest = _headline(a.get("ask"))
    if ask_rest:
        a["ask"] = ask
        a["ask_detail"] = "\n\n".join(x for x in (ask_rest, (a.get("ask_detail") or "").strip())
                                      if x)
    sender, agent = ctx.filer(bool(a.get("as_human")))
    if sender == ac.HUMAN and not ctx.is_human:
        raise ToolError("refused: only the main session files as 'human'")
    if sender == ac.HUMAN and not a.get("as_human") and a.get("on_behalf_of"):
        # a main session outside every home would stamp 'from: human' on work an instance
        # did (docs/protocol.md section 5); a caller that knows the instance says so
        if a["on_behalf_of"] not in ctx.instances():
            raise ToolError("on_behalf_of must be a workspace instance, got %r"
                            % a["on_behalf_of"])
        sender, agent = a["on_behalf_of"], ac.MAIN_AGENT
    if not sender:
        raise ToolError("agent %r runs outside every academy home; it cannot file tickets"
                        % ctx.agent)
    to = _one_line("to", a.get("to"), tag=True)
    if to != ac.HUMAN and to not in ctx.instances():
        raise ToolError("to must be a workspace instance or 'human', got %r" % to)
    final_to = _one_line("final_to", a.get("final_to"), required=False, tag=True)
    parent = a.get("parent") or None
    if parent and not ctx.store.find(parent):
        raise ToolError("parent %s is not on the board" % parent)
    depth = ac.relay_depth(ctx.store, parent) if final_to and parent else 0
    ok, why = ac.ticket_edge_allowed(sender, to, agent, ctx.perms, ctx.workspace,
                                     final_to, depth, clerical=clerical)
    if not ok:
        raise ToolError("refused: " + why)
    kind = a.get("kind") or "other"
    if kind not in ac.TICKET_KINDS:
        kind = "other"
    prio = a.get("priority") or "normal"
    if prio not in ac.PRIORITIES:
        raise ToolError("priority must be one of %s" % ", ".join(ac.PRIORITIES))
    budget = a.get("budget") or _default_budget(ctx)
    domain = a.get("domain")
    if not domain and to != ac.HUMAN:
        domain = (ctx.instances()[to].get("domains") or [None])[0]
    today = ac.today()
    meta = {
        "id": None,
        "title": _one_line("title", a.get("title")),
        "kind": kind,
        "from": sender,
        "to": to,
        "status": "open",
        "priority": prio,
        "ask": _one_line("ask", a.get("ask")),
        "deliverable": _one_line("deliverable", a.get("deliverable")),
        "refs": list(a.get("refs") or []),
        "agenda": a.get("agenda") or None,
        "domain": domain or None,
        "parent": parent,
        "final_to": final_to,
        "blocks": [],
        "waiting_on": [],
        "budget": budget,
        "result": None,
        "packets": [],
        "created": today,
        "updated": today,
    }
    campaign = _one_line("campaign", a.get("campaign"), required=False, tag=True)
    if campaign:
        meta["campaign"] = campaign     # the campaign's target id (inbox --campaign)
    cowork = _one_line("cowork", a.get("cowork"), required=False, tag=True)
    if cowork:
        meta["cowork"] = cowork         # the cowork's slug (inbox --cowork; /academy:cowork)
    meta["id"] = "T-0000"                           # placeholder for validation
    probs = ac.validate_ticket(meta)
    if probs:
        raise ToolError("invalid ticket: " + "; ".join(probs))
    speaker = ac.format_who(sender, agent)
    text = ac.new_ticket(meta, a.get("ask_detail") or "")
    fm, body = ac.read_frontmatter(text)
    note = (a.get("note") or "").strip()
    body = ac.append_thread(body, speaker, "opened" + (": " + note if note else ""))
    probs = ac.validate_ticket(fm, body)
    if probs:
        raise ToolError("invalid ticket: " + "; ".join(probs))
    path, fm = ctx.store.create(fm, body)
    tid = fm["id"]
    return {"id": tid, "path": path.replace("\\", "/"), "to": to, "from": sender,
            "status": "open"}


def _fmt_val(v):
    if isinstance(v, list):
        return "[%s]" % ", ".join(str(x) for x in v)
    if isinstance(v, dict):
        return "{%s}" % ", ".join("%s: %s" % kv for kv in v.items())
    return "" if v is None else str(v)


def update_ticket(ctx, a):
    path, meta, body = load_ticket(ctx, a.get("id"))
    old_meta = dict(meta)
    old_body = body
    human = ctx.is_human
    ctx.ticket_hint = old_meta          # an agent acts for its party on this ticket
    me = ctx.instance
    if not me:
        raise ToolError("agent %r runs outside every academy home and is no party of "
                        "%s; pass instance=<its instance>" % (ctx.agent, meta.get("id")))
    pset = ac.parties(meta, me)
    a = dict(a)
    fields = dict(a.get("fields") or {})
    if a.get("result") is not None and "result" not in fields:
        fields["result"] = a["result"]          # an alias of fields.result
    for k in ac.BLOCK_FIELDS:                   # likewise waiting_on, blocked_by, reopen_if
        if a.get(k) is not None and k not in fields:
            fields[k] = a[k]
    for k in FIELD_ARGS:                        # and an argument put inside fields
        if k in fields:
            v = fields.pop(k)
            if a.get(k) is None:
                a[k] = v
    if isinstance(fields.get("waiting_on"), str):
        fields["waiting_on"] = [w for w in re.split(r"[,\s]+", fields["waiting_on"]) if w]
    new_status = a.get("status")
    deliver = a.get("deliver") is True
    # the result's extra lines are its detail; a result given only as detail has its
    # first line as the field (12 refusals "delivered needs result" after 2026-10-31)
    result, result_rest = _headline(fields.get("result"))
    if result_rest:
        fields["result"] = result
        if a.get("result_detail") is None:
            a["result_detail"] = result_rest
    elif (not fields.get("result") and not meta.get("result") and a.get("result_detail")
          and (deliver or new_status in ("delivered", "closed"))):
        fields["result"] = _headline(a["result_detail"])[0]
    if (deliver or new_status == "delivered") and meta.get("status") == "delivered" \
            and (human or "receiver" in pset):
        # delivering a delivered ticket again is the receiver amending its result, not a
        # status move (4 refusals, 2026-11-07..12)
        deliver, new_status = False, None
    if deliver:
        if new_status not in (None, "delivered"):
            raise ToolError("deliver: true walks the ticket to delivered; it cannot be "
                            "combined with status %s" % new_status)
        new_status = "delivered"
        # the human may make every hop, so may deliver in one call too (ledger: 7 refusals
        # of the human-side session, 2026-10-26..31)
        if (not human and "receiver" not in pset) or meta.get("status") not in DELIVER_FROM:
            hint = ""
            if not human and "receiver" not in pset:
                hint = ("; only the receiver %s delivers it: work it from that instance "
                        "(instance=%s, as its own agent)%s"
                        % (meta.get("to"), meta.get("to"),
                           ", or the human moves it" if meta.get("to") != ac.HUMAN
                           else "; a ticket to human is moved by the human"))
            raise ToolError(
                "deliver: true is for the receiver (or the human) of an open, accepted or "
                "in-progress ticket; %s is %s and %s is %s%s"
                % (meta["id"], meta.get("status"), me,
                   " and ".join(sorted(pset)) or "no party", hint))
        if not (fields.get("result") or meta.get("result")):
            raise ToolError("delivered needs result: pass fields.result (one line, the "
                            "answer) in the same call as deliver: true; detail goes in "
                            "the ## Result body (result_detail)")
    reason = (a.get("reason") or "").strip()
    note = (a.get("note") or "").strip()
    speaker = ctx.speaker
    lines = []
    old_status = old_meta.get("status")
    status_change = bool(new_status and new_status != old_status)
    staged = {}          # blocking fields of a status move: apply_blocking writes them

    # -- fields -----------------------------------------------------------
    allowed = ac.editable_fields(pset, human)
    for k, v in fields.items():
        if k == "status":
            raise ToolError("change status with the 'status' argument, not fields")
        if k not in ac.TICKET_KEY_ORDER:
            raise ToolError("unknown ticket field %r" % k)
        if k in FROZEN:
            raise ToolError("%s is written by the server only" % k)
        if k == "to" and not human:
            raise ToolError("only the human re-routes a ticket (to)")
        if k == "from" and not human:
            raise ToolError("from is a system field")
        if k not in allowed:
            owner = next((o for o, fs in ac.TICKET_FIELDS.items() if k in fs), "?")
            raise ToolError("%s is a %s field; %s is %s on %s" % (
                k, owner, me, " and ".join(sorted(pset)) or "no party", meta["id"]))
        if k in ("title", "ask", "deliverable", "result"):
            v = _one_line(k, v, required=(k != "result"))
        if k in ac.BLOCK_FIELDS and status_change:
            staged[k] = v
            continue
        if meta.get(k) != v:
            meta[k] = v
            lines.append("set %s: %s" % (k, _fmt_val(v)))

    # -- sections ---------------------------------------------------------
    if a.get("ask_detail") is not None:
        if not (human or "sender" in pset):
            raise ToolError("## Ask belongs to the sender")
        body = replace_section(body, "Ask", a["ask_detail"])
        lines.append("set ## Ask")
    if a.get("result_detail") is not None:
        if not (human or "receiver" in pset):
            raise ToolError("## Result belongs to the receiver")
        body = replace_section(body, "Result", a["result_detail"])
        lines.append("set ## Result")

    # -- status -----------------------------------------------------------
    if status_change:
        if meta.get("to") == ac.HUMAN and not human:
            raise ToolError("refused: a ticket addressed to human changes status only "
                            "by the human")
        chain = None
        if deliver:
            chain = ac.transition_route(old_status, new_status)
        elif not human and (old_status, new_status) not in ac.TRANSITIONS:
            route = ac.transition_route(old_status, new_status)
            if route and all(s in WALK_THROUGH for s in route[1:-1]):
                chain = route
        steps = list(zip(chain, chain[1:])) if chain else [(old_status, new_status)]
        for hop_old, hop_new in steps:
            ok, why = ac.can_transition(hop_old, hop_new, pset, human)
            if not ok:
                raise ToolError("refused: %s%s" % (
                    why, _who_moves(meta, pset, me, hop_old, hop_new, human)))
        for n, (hop_old, hop_new) in enumerate(steps):
            # the first hop sees the ticket as it was before this call, as a single step did
            hop_meta = old_meta if n == 0 else dict(meta, status=hop_old)
            try:
                blines = ac.apply_blocking(
                    hop_meta, meta, hop_new, reason, staged.get("waiting_on"),
                    staged.get("blocked_by"), staged.get("reopen_if"), a.get("reopen"), human)
            except ac.AcademyError as exc:
                raise ToolError(str(exc) + (BLOCK_HINT if hop_new == "blocked" else ""))
            lines.extend(blines)
            meta["status"] = hop_new
            dead_block = hop_new == "blocked" and ac.is_dead_route(meta)
            lines.append("status %s -> %s%s" % (hop_old, hop_new,
                                                (": " + " ".join(reason.split()))
                                                if reason and not dead_block else ""))
        if new_status in ("delivered", "closed") and not meta.get("result"):
            raise ToolError("%s needs result: pass fields.result (one line, the answer) in the same call as status; "
                            "detail goes in the ## Result body (result_detail)" % new_status)
    elif a.get("reopen"):
        raise ToolError(ac.REOPEN_ONLY)
    elif reason and not note:
        note = reason
    if note:
        lines.append(note)
    if not lines:
        # not an error: the ticket already reads as asked (8 ledger entries, five weeks)
        return {"id": meta["id"], "path": path.replace("\\", "/"), "status": meta.get("status"),
                "changed": False, "thread": [], "mirrored_blocks_into": [],
                "note": "nothing to change: the ticket already reads so"}

    for ln in lines:
        body = ac.append_thread(body, speaker, ln)
    meta["updated"] = ac.today()
    probs = ac.validate_ticket(meta, body)
    if probs:
        raise ToolError("the update would leave an invalid ticket: " + "; ".join(probs))
    if not ac.thread_is_append_only(old_body, body):
        raise ToolError("internal: thread is not append-only")

    relocate = meta.get("to") != old_meta.get("to")
    if relocate:
        to = meta["to"]
        if to != ac.HUMAN and to not in ctx.instances():
            raise ToolError("to must be a workspace instance or 'human'")
    new_path = ctx.store.save(meta, body, path, relocate=relocate)

    # blocking bookkeeping: mirror into the awaited tickets' blocks
    freed = []
    if meta.get("status") == "blocked":
        freed = ac.mirror_blocks(ctx.store, meta["id"], meta.get("waiting_on"), ac.today())
    return {"id": meta["id"], "path": new_path.replace("\\", "/"),
            "status": meta["status"], "thread": lines, "mirrored_blocks_into": freed}


def _summary(path, meta):
    return {k: meta.get(k) for k in ("id", "title", "kind", "from", "to", "status",
                                     "priority", "agenda", "updated")} | {
        "path": path.replace("\\", "/")}


def _list(ctx, a):
    out = []
    statuses = a.get("status")
    if isinstance(statuses, str):
        statuses = [statuses]
    for p, m in ctx.store.iter_meta():
        if a.get("to") and m.get("to") != a["to"]:
            continue
        if a.get("from") and m.get("from") != a["from"]:
            continue
        if a.get("instance") and a["instance"] not in (m.get("to"), m.get("from")):
            continue
        if statuses and m.get("status") not in statuses:
            continue
        if not a.get("include_terminal", True) and m.get("status") in ac.TERMINAL:
            continue
        out.append(_summary(p, m))
    out.sort(key=lambda t: (PRIORITY_ORDER.get(t.get("priority"), 1), t["id"]))
    return {"board": ctx.board, "count": len(out), "tickets": out}


def _get(ctx, a):
    path, meta, body = load_ticket(ctx, a.get("id"))
    return {"path": path.replace("\\", "/"), "meta": meta, "body": body,
            "problems": ac.validate_ticket(meta, body)}


TOOLS = [
    Tool("tickets_list", "List board tickets, filtered by to / from / instance (either "
         "side) / status.",
         obj({"to": S, "from": S, "instance": S,
              "status": {"type": ["string", "array"], "items": {"type": "string"}},
              "include_terminal": B}), _list),
    Tool("tickets_get", "Read one ticket (frontmatter, body, validation problems).",
         obj({"id": S, "instance": ACTING}, ["id"]), _get),
    Tool("tickets_create", "File a ticket from the caller's instance (the human files "
         "as 'human'). The server allocates the id and dates; status is open. ask is one line: a "
         "longer ask keeps its first line and goes whole to the ## Ask body. A ticket must pass the chain "
         "(docs/protocol.md section 5): to a neighbouring role, by a liaison; final_to "
         "names the role a relay forwards it to. campaign / cowork tag the ticket for a "
         "workplan (academy/lib/workplan.py): a campaign's target id or a cowork's slug.",
         obj({"title": S, "kind": {"type": "string", "enum": list(ac.TICKET_KINDS)},
              "to": S, "ask": S, "deliverable": S, "ask_detail": S,
              "priority": {"type": "string", "enum": list(ac.PRIORITIES)},
              "refs": L, "agenda": S, "domain": S, "parent": S,
              "budget": {"type": "object", "description":
                         "{runs: int >= 1} (default: the home's budget.ticketDefault "
                         "runs); an optional max_model is an advisory note only, never "
                         "a gate: an agent runs on its agent file's model"},
              "note": S, "final_to": S, "campaign": S, "cowork": S, "as_human": B,
              "instance": ACTING},
             ["title", "kind", "to", "ask", "deliverable"]),
         lambda ctx, a: create_ticket(ctx, a), write=True),
    Tool("tickets_update", "Change a ticket: a status transition (with reason where the "
         "protocol needs one), owned fields, ## Ask / ## Result detail, and/or a thread "
         "note. Field ownership and transitions per docs/protocol.md. deliver: true (the "
         "receiver or the human, ticket open/accepted/in-progress, fields.result required) walks "
         "open -> accepted -> in-progress -> delivered in one call, writing the usual "
         "thread line per step; every hop must be allowed; not with another status. "
         "status in-progress from open likewise passes through accepted. result, "
         "waiting_on, blocked_by and reopen_if are aliases of the fields of that name; a "
         "multi-line result keeps its first line and goes whole to ## Result. blocked "
         "needs waiting_on (pending), or blocked_by + reopen_if + reason (a dead route). "
         "A call that changes nothing answers changed: false.",
         obj({"id": S, "status": {"type": "string", "enum": list(ac.TICKET_STATUSES)},
              "reason": S, "reopen": S, "fields": {"type": "object"}, "ask_detail": S,
              "result_detail": S, "note": S, "deliver": B, "result": S,
              "waiting_on": {"type": ["array", "string"], "items": {"type": "string"}},
              "blocked_by": S, "reopen_if": S, "instance": ACTING}, ["id"]),
         update_ticket, write=True),
]
