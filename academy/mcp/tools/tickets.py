"""tickets_* tools: the board protocol of docs/protocol.md, on academy_common.

Writes never commit (protocol section 2). The caller's party on a ticket is
decided by its instance against the ticket's ``from`` / ``to``; the human may do
anything, and is the only party on a ticket addressed to ``human``.
"""

import os

import academy_common as ac

from . import Tool, ToolError, obj, S, B, L

REASON_NEEDED = {("delivered", "in-progress")}
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
    try:
        home = ac.find_home(ctx.cwd)
        cfg = ac.load_config(home) if home else ac.CONFIG_DEFAULTS
    except ac.ConfigError:
        cfg = ac.CONFIG_DEFAULTS
    b = (cfg.get("budget") or {}).get("ticketDefault") or {"runs": 1, "max_model": "sonnet"}
    return {"runs": int(b.get("runs", 1)), "max_model": b.get("max_model", "sonnet")}


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def load_ticket(ctx, tid):
    if not ac.RE_TICKET_ID.match(str(tid or "")):
        raise ToolError("a ticket id looks like T-0007, got %r" % tid)
    path = ac.find_ticket(ctx.board, tid)
    if not path:
        raise ToolError("no ticket %s on the board %s" % (tid, ctx.board))
    meta, body = ac.read_frontmatter(_read(path))
    return path, meta, body


def _write(path, meta, body):
    ordered = {k: meta[k] for k in ac.TICKET_KEY_ORDER if k in meta}
    ac.atomic_write(path, ac.write_frontmatter(ordered, body))


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
    if not sender:
        raise ToolError("agent %r runs outside every academy home; it cannot file tickets"
                        % ctx.agent)
    to = _one_line("to", a.get("to"))
    if to != ac.HUMAN and to not in ctx.instances():
        raise ToolError("to must be a workspace instance or 'human', got %r" % to)
    final_to = _one_line("final_to", a.get("final_to"), required=False)
    parent = a.get("parent") or None
    if parent and not ac.find_ticket(ctx.board, parent):
        raise ToolError("parent %s is not on the board" % parent)
    depth = ac.relay_depth(ctx.board, parent) if final_to and parent else 0
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
    meta["id"] = "T-0000"                           # placeholder for validation
    probs = ac.validate_ticket(meta)
    if probs:
        raise ToolError("invalid ticket: " + "; ".join(probs))
    speaker = ac.format_who(sender, agent)
    tid = ac.allocate_id(ctx.board, "ticket")
    meta["id"] = tid
    text = ac.new_ticket(meta, a.get("ask_detail") or "")
    fm, body = ac.read_frontmatter(text)
    note = (a.get("note") or "").strip()
    body = ac.append_thread(body, speaker, "opened" + (": " + note if note else ""))
    probs = ac.validate_ticket(fm, body)
    if probs:
        raise ToolError("invalid ticket: " + "; ".join(probs))
    path = os.path.join(ctx.board, to, ac.ticket_filename(tid, meta["title"]))
    _write(path, fm, body)
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
    old_status = old_meta.get("status")
    if new_status and new_status != old_status:
        if meta.get("to") == ac.HUMAN and not human:
            raise ToolError("refused: a ticket addressed to human changes status only "
                            "by the human")
        ok, why = ac.can_transition(old_status, new_status, pset, human)
        if not ok:
            raise ToolError("refused: %s" % why)
        if (new_status in ("rejected", "cancelled")
                or (old_status, new_status) in REASON_NEEDED) and not reason:
            raise ToolError("%s -> %s needs a reason in the same write"
                            % (old_status, new_status))
        was_dead = old_status == "blocked" and bool(old_meta.get("blocked_by")
                                                     and old_meta.get("reopen_if"))
        reopen = " ".join(str(a.get("reopen") or "").split())
        if new_status == "blocked":
            dead = bool(meta.get("blocked_by") and meta.get("reopen_if"))
            if meta.get("waiting_on") and (meta.get("blocked_by") or meta.get("reopen_if")):
                raise ToolError("blocked is pending (waiting_on) or a dead route "
                                "(blocked_by and reopen_if), not both")
            if not meta.get("waiting_on") and not dead:
                raise ToolError("blocked needs fields.waiting_on, or both "
                                "fields.blocked_by and fields.reopen_if")
            if dead:
                if not reason:
                    raise ToolError("a dead-route block needs a reason naming what was tried")
                lines.append("tried: %s" % " ".join(reason.split()))
                reason = ""
        elif was_dead:
            if new_status == "accepted":
                if not reopen:
                    raise ToolError("a dead-route ticket reopens with reopen "
                                    "(the new mechanism)")
                lines.append("reopened: %s" % reopen)
            elif new_status != "cancelled":
                raise ToolError("a dead-route ticket reopens only blocked -> accepted "
                                "with reopen; the sender may cancel with a reason")
        if old_status == "blocked" and new_status != "blocked":
            if meta.get("waiting_on"):
                meta["waiting_on"] = []
                lines.append("set waiting_on: []")
            for f in ("blocked_by", "reopen_if"):
                meta.pop(f, None)
        if new_status in ("delivered", "closed") and not meta.get("result"):
            raise ToolError("%s needs result (fields.result)" % new_status)
        meta["status"] = new_status
        lines.append("status %s -> %s%s" % (old_status, new_status,
                                            (": " + reason) if reason else ""))
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
    if not ac.thread_is_append_only(ac.read_frontmatter(_read(path))[1], body):
        raise ToolError("internal: thread is not append-only")

    new_path = path
    if meta.get("to") != old_meta.get("to"):
        to = meta["to"]
        if to != ac.HUMAN and to not in ctx.instances():
            raise ToolError("to must be a workspace instance or 'human'")
        new_path = os.path.join(ctx.board, to, os.path.basename(path))
    _write(new_path, meta, body)
    if new_path != path:
        os.remove(path)

    # blocking bookkeeping: mirror into the awaited tickets' blocks
    freed = []
    if meta.get("status") == "blocked":
        for w in meta.get("waiting_on") or []:
            if ac.RE_TICKET_ID.match(str(w)):
                wp = ac.find_ticket(ctx.board, w)
                if not wp:
                    continue
                wm, wb = ac.read_frontmatter(_read(wp))
                if meta["id"] not in (wm.get("blocks") or []):
                    wm["blocks"] = list(wm.get("blocks") or []) + [meta["id"]]
                    wm["updated"] = ac.today()
                    _write(wp, wm, wb)
                    freed.append(w)
    return {"id": meta["id"], "path": new_path.replace("\\", "/"),
            "status": meta["status"], "thread": lines, "mirrored_blocks_into": freed}


def _summary(path, meta):
    return {k: meta.get(k) for k in ("id", "title", "kind", "from", "to", "status",
                                     "priority", "agenda", "updated")} | {
        "path": path.replace("\\", "/")}


def iter_tickets(board):
    import re
    rx = re.compile(r"^T-\d{4,}-.*\.md$")
    if not os.path.isdir(board):
        return
    for d in sorted(os.listdir(board)):
        full = os.path.join(board, d)
        if d in ("packets", "deep-dives", ".ids", ".git") or not os.path.isdir(full):
            continue
        for f in sorted(os.listdir(full)):
            if rx.match(f):
                p = os.path.join(full, f)
                try:
                    meta, _ = ac.read_frontmatter(_read(p))
                except ac.FrontmatterError:
                    continue
                yield p, meta


def _list(ctx, a):
    out = []
    statuses = a.get("status")
    if isinstance(statuses, str):
        statuses = [statuses]
    for p, m in iter_tickets(ctx.board):
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
         "names the role a relay forwards it to.",
         obj({"title": S, "kind": {"type": "string", "enum": list(ac.TICKET_KINDS)},
              "to": S, "ask": S, "deliverable": S, "ask_detail": S,
              "priority": {"type": "string", "enum": list(ac.PRIORITIES)},
              "refs": L, "agenda": S, "domain": S, "parent": S,
              "budget": {"type": "object"}, "note": S, "final_to": S, "campaign": S,
              "as_human": B},
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
