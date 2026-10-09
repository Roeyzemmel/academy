"""tickets_* tools: the board protocol of docs/protocol.md, on academy_common.

Writes never commit (protocol section 2). The caller's party on a ticket is
decided by its instance against the ticket's ``from`` / ``to``; the human may do
anything, and is the only party on a ticket addressed to ``human``.
"""

import academy_common as ac

from . import Tool, ToolError, obj, S, B, L

PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}
FROZEN = ("id", "created", "updated")


def _one_line(name, value, required=True):
    if value is None or str(value).strip() == "":
        if required:
            raise ToolError("%s is required" % name)
        return None
    s = str(value).strip()
    if "\n" in s or "\r" in s:
        raise ToolError("%s must be one line (detail goes in the body)" % name)
    return s


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
        raise ToolError("a ticket id looks like T-0007, got %r" % tid)
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
    sender, agent = ctx.filer(bool(a.get("as_human")))
    if sender == ac.HUMAN and not a.get("as_human") and a.get("on_behalf_of"):
        # a main session outside every home would stamp 'from: human' on work an instance
        # did (T-0065/T-0066); a caller that knows the instance says so
        if a["on_behalf_of"] not in ctx.instances():
            raise ToolError("on_behalf_of must be a workspace instance, got %r"
                            % a["on_behalf_of"])
        sender, agent = a["on_behalf_of"], ac.MAIN_AGENT
    if not sender:
        raise ToolError("agent %r runs outside every academy home; it cannot file tickets"
                        % ctx.agent)
    to = _one_line("to", a.get("to"))
    if to != ac.HUMAN and to not in ctx.instances():
        raise ToolError("to must be a workspace instance or 'human', got %r" % to)
    final_to = _one_line("final_to", a.get("final_to"), required=False)
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
    campaign = _one_line("campaign", a.get("campaign"), required=False)
    if campaign:
        meta["campaign"] = campaign     # the campaign's target id (inbox --campaign)
    cowork = _one_line("cowork", a.get("cowork"), required=False)
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
    me = ctx.instance
    if not me:
        raise ToolError("agent %r runs outside every academy home" % ctx.agent)
    pset = ac.parties(meta, me)
    fields = dict(a.get("fields") or {})
    new_status = a.get("status")
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
        ok, why = ac.can_transition(old_status, new_status, pset, human)
        if not ok:
            raise ToolError("refused: %s" % why)
        try:
            blines = ac.apply_blocking(
                old_meta, meta, new_status, reason, staged.get("waiting_on"),
                staged.get("blocked_by"), staged.get("reopen_if"), a.get("reopen"), human)
        except ac.AcademyError as exc:
            raise ToolError(str(exc))
        lines.extend(blines)
        if new_status in ("delivered", "closed") and not meta.get("result"):
            raise ToolError("%s needs result (fields.result)" % new_status)
        meta["status"] = new_status
        dead_block = new_status == "blocked" and ac.is_dead_route(meta)
        lines.append("status %s -> %s%s" % (old_status, new_status,
                                            (": " + " ".join(reason.split()))
                                            if reason and not dead_block else ""))
    elif a.get("reopen"):
        raise ToolError(ac.REOPEN_ONLY)
    elif reason and not note:
        note = reason
    if note:
        lines.append(note)
    if not lines:
        raise ToolError("nothing to change")

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
         obj({"id": S}, ["id"]), _get),
    Tool("tickets_create", "File a ticket from the caller's instance (the human files "
         "as 'human'). The server allocates the id and dates; status is open. A ticket must pass the chain "
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
              "note": S, "final_to": S, "campaign": S, "cowork": S, "as_human": B},
             ["title", "kind", "to", "ask", "deliverable"]),
         lambda ctx, a: create_ticket(ctx, a), write=True),
    Tool("tickets_update", "Change a ticket: a status transition (with reason where the "
         "protocol needs one), owned fields, ## Ask / ## Result detail, and/or a thread "
         "note. Field ownership and transitions per docs/protocol.md.",
         obj({"id": S, "status": {"type": "string", "enum": list(ac.TICKET_STATUSES)},
              "reason": S, "reopen": S, "fields": {"type": "object"}, "ask_detail": S,
              "result_detail": S, "note": S}, ["id"]),
         update_ticket, write=True),
]
