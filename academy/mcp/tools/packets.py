"""packets_* tools: review packets per docs/packet-template.md.

A packet lives at ``board/packets/<instance>/P-NNNN-<slug>.md``. Only the human
decides (``packets_decide``); the answer is written into ``## Decision`` and echoed
as one thread line into the packet's ticket.
"""

import os
import re

import academy_common as ac

from . import Tool, ToolError, obj, S, I, L
from .tickets import load_ticket

SECTION_ARGS = (("summary", "## Summary"), ("produced", "## Produced"),
                ("established_vs_assumed", "## Established vs assumed"),
                ("evidence", "## Evidence"))


def _write(path, meta, body):
    ordered = {k: meta.get(k) for k in ac.PACKET_KEY_ORDER if k in meta}
    ac.atomic_write(path, ac.write_frontmatter(ordered, body))


def compose_body(sections):
    """Build a packet body from a sections object (see packets_create)."""
    parts = []
    for key, head in SECTION_ARGS:
        parts.append("%s\n\n%s\n" % (head, str(sections.get(key) or "").strip()))
    for head, text in (sections.get("extra") or {}).items():
        head = head if head.startswith("## ") else "## " + head.lstrip("# ")
        parts.append("%s\n\n%s\n" % (head, str(text).strip()))
    parts.append("## Decisions needed\n\n%s\n"
                 % (str(sections.get("decisions_needed") or "None.").strip()))
    parts.append("## Machine notes\n\n%s\n"
                 % (str(sections.get("machine_notes") or "None.").strip()))
    parts.append("## Decision\n")
    return "\n" + "\n".join(parts)


def load_packet(ctx, pid):
    if not ac.RE_PACKET_ID.match(str(pid or "")):
        raise ToolError("a packet id looks like P-0012, got %r" % pid)
    path = ac.find_packet(ctx.board, pid)
    if not path:
        raise ToolError("no packet %s on the board" % pid)
    with open(path, "r", encoding="utf-8") as fh:
        meta, body = ac.read_frontmatter(fh.read())
    return path, meta, body


#: what packets_create needs, said in every refusal so one retry is enough
PACKET_SHAPE = (
    "packets_create needs: title (one line), kind (%s), and either body (the full "
    "Markdown) or sections {summary (<=3 lines), produced, established_vs_assumed, "
    "evidence, extra, decisions_needed, machine_notes}; optional instance (the human "
    "must give it; an agent's is its own), ticket (T-NNNN), agenda, subject [ids], "
    "status_before / status_proposed (registry statuses). decisions_needed is 'None.' "
    "or blocks '### D1. <question>' then 2-4 option lines '- (a) <text>' ... '- (d) "
    "<text>' and one '- Recommendation: <letter and why>'; numbered D1..Dn without gaps. "
    "## Decision stays empty (docs/packet-template.md)." % ", ".join(ac.PACKET_KINDS))


def create_packet(ctx, a):
    probs = []                  # every problem at once (fix 10, 2026-10-09)
    inst = None
    if ctx.is_human:
        inst = a.get("instance")
        if not inst or inst not in ctx.instances():
            probs.append("the human names the packet's instance (a workspace instance)")
    else:
        inst = ctx.instance
        if not inst:
            raise ToolError("agent %r runs outside every academy home and no instance "
                            "could be resolved; pass instance=<its instance>" % ctx.agent)
        if a.get("instance") and a["instance"] != inst:
            probs.append("a packet's instance is the caller's instance (%s)" % inst)
    if a.get("body") is not None and a.get("sections") is not None:
        probs.append("give body or sections, not both")
    body = a.get("body")
    if body is None:
        sections = a.get("sections") or {}
        if not isinstance(sections, dict):
            probs.append("sections must be an object")
            sections = {}
        body = compose_body(sections)
    body = str(body).replace("\r\n", "\n")
    if not body.startswith("\n"):
        body = "\n" + body
    if ac.packet_answers(body) or [ln for ln in ac._sections(body).get("## Decision", [])
                                   if ln.strip()]:
        probs.append("## Decision must be empty at creation")
    kind = a.get("kind") or "other"
    meta = {
        "packet": "P-0000",
        "title": (a.get("title") or "").strip(),
        "instance": inst or "unknown@x",
        "kind": kind,
        "by": ctx.speaker,
        "ticket": a.get("ticket") or None,
        "agenda": a.get("agenda") or None,
        "subject": list(a.get("subject") or []),
        "status_before": a.get("status_before") or None,
        "status_proposed": a.get("status_proposed") or None,
        "state": "open",
        "created": ac.today(),
        "decided": None,
    }
    if "\n" in meta["title"]:
        probs.append("title must be one line")
    probs += [p for p in ac.validate_packet(meta, body) if p not in probs]
    if probs:
        raise ToolError("invalid packet (%d problem%s): %s.\n%s"
                        % (len(probs), "" if len(probs) == 1 else "s", "; ".join(probs),
                           PACKET_SHAPE))
    tref = None
    if meta["ticket"]:
        tref, tmeta, tbody = load_ticket(ctx, meta["ticket"])
    pid = ac.allocate_id(ctx.board, "packet")
    meta["packet"] = pid
    path = os.path.join(ctx.board, "packets", inst, ac.packet_filename(pid, meta["title"]))
    _write(path, meta, body)
    linked = False
    if tref:
        pset = ac.parties(tmeta, ctx.instance)
        text = "packet %s: %s" % (pid, meta["title"])
        if ctx.is_human or "receiver" in pset:
            tmeta["packets"] = list(tmeta.get("packets") or []) + [pid]
            text = "set packets: [%s]; %s" % (", ".join(tmeta["packets"]), text)
            linked = True
        tbody = ac.append_thread(tbody, ctx.speaker, text)
        tmeta["updated"] = ac.today()
        ctx.store.save(tmeta, tbody, tref)
    return {"packet": pid, "path": path.replace("\\", "/"), "instance": inst,
            "ticket": meta["ticket"], "linked_to_ticket": linked}


def decide(ctx, a):
    if not ctx.is_human:
        raise ToolError("refused: only the human decides a packet")
    path, meta, body = load_packet(ctx, a.get("id"))
    k = int(a.get("decision", 0))
    choice = str(a.get("choice") or "").strip().lower().strip("()")
    note = a.get("note") or ""
    asked = ac.packet_decisions(body)
    if asked:
        if k not in asked:
            raise ToolError("%s asks D%s; there is no D%d"
                            % (meta["packet"], ",D".join(str(x) for x in sorted(asked)), k))
        if choice not in ("other",) and choice not in asked[k]["options"]:
            raise ToolError("D%d has options %s (or 'other' with a note)"
                            % (k, ", ".join(sorted(asked[k]["options"]))))
    else:
        if k != 0 or choice != "ack":
            raise ToolError("%s asks no decision: acknowledge it with decision 0, "
                            "choice 'ack'" % meta["packet"])
    try:
        body = ac.record_decision(body, k, choice, note)
    except ac.AcademyError as exc:
        raise ToolError(str(exc))
    if ac.packet_is_decided(body) and meta.get("state") != "decided":
        meta["state"] = "decided"
        meta["decided"] = ac.today()
    _write(path, meta, body)
    echoed = None
    if meta.get("ticket"):
        tref, tmeta, tbody = load_ticket(ctx, meta["ticket"])
        if choice == "ack":
            text = "acknowledged %s" % meta["packet"]
        elif choice == "other":
            text = "decision on %s D%d: %s" % (meta["packet"], k, " ".join(note.split()))
        else:
            text = "decision on %s D%d: (%s) %s" % (meta["packet"], k, choice,
                                                    asked[k]["options"][choice])
        tbody = ac.append_thread(tbody, ac.HUMAN, text)
        tmeta["updated"] = ac.today()
        ctx.store.save(tmeta, tbody, tref)
        echoed = meta["ticket"]
    return {"packet": meta["packet"], "state": meta["state"], "echoed_into": echoed}


def iter_packets(board):
    root = os.path.join(board, "packets")
    rx = re.compile(r"^P-\d{4,}-.*\.md$")
    if not os.path.isdir(root):
        return
    for d in sorted(os.listdir(root)):
        full = os.path.join(root, d)
        if not os.path.isdir(full):
            continue
        for f in sorted(os.listdir(full)):
            if rx.match(f):
                p = os.path.join(full, f)
                try:
                    with open(p, "r", encoding="utf-8") as fh:
                        meta, body = ac.read_frontmatter(fh.read())
                except ac.FrontmatterError:
                    continue
                yield p, meta, body


def _list(ctx, a):
    out = []
    for p, m, body in iter_packets(ctx.board):
        if a.get("instance") and m.get("instance") != a["instance"]:
            continue
        if a.get("state") and m.get("state") != a["state"]:
            continue
        if a.get("ticket") and m.get("ticket") != a["ticket"]:
            continue
        row = {k: m.get(k) for k in ("packet", "title", "instance", "kind", "ticket",
                                     "state", "status_before", "status_proposed",
                                     "created")}
        row["pending_decisions"] = sorted(set(ac.packet_decisions(body))
                                          - set(ac.packet_answers(body)))
        row["path"] = p.replace("\\", "/")
        out.append(row)
    return {"count": len(out), "packets": out}


def _get(ctx, a):
    path, meta, body = load_packet(ctx, a.get("id"))
    return {"path": path.replace("\\", "/"), "meta": meta, "body": body,
            "decisions": ac.packet_decisions(body),
            "answers": {k: list(v) for k, v in ac.packet_answers(body).items()},
            "problems": ac.validate_packet(meta, body)}


SECTIONS = {"type": "object", "description":
            "summary (<=3 lines), produced, established_vs_assumed, evidence, "
            "extra {heading: text} (between Evidence and Decisions needed), "
            "decisions_needed ('None.' or ### D1. blocks), machine_notes"}

TOOLS = [
    Tool("packets_list", "List review packets, filtered by instance / state / ticket, "
         "with their pending decisions.",
         obj({"instance": S, "state": {"type": "string", "enum": list(ac.PACKET_STATES)},
              "ticket": S}), _list),
    Tool("packets_get", "Read one packet with its parsed decisions and answers.",
         obj({"id": S}, ["id"]), _get),
    Tool("packets_create", "Create a review packet from the caller's instance, from a "
         "full Markdown body or from sections. Required: title, kind, and body or "
         "sections; decisions as '### D1. question' with 2-4 '- (a) option' lines and "
         "a '- Recommendation:' line (or 'None.'). ## Decision must be empty. With "
         "ticket, the receiver's packet is also listed in the ticket's packets. A "
         "refusal lists every problem at once.",
         obj({"title": S, "kind": {"type": "string", "enum": list(ac.PACKET_KINDS)},
              "instance": S, "ticket": S, "agenda": S, "subject": L,
              "status_before": {"type": "string", "enum": list(ac.CLAIM_STATUSES)},
              "status_proposed": {"type": "string", "enum": list(ac.CLAIM_STATUSES)},
              "body": S, "sections": SECTIONS}, ["title", "kind"]),
         create_packet, write=True),
    Tool("packets_decide", "Human only: record the answer to decision D<k> "
         "(choice a-d, 'other' with a note, or D0 'ack'), set state decided when all "
         "are answered, and echo it into the packet's ticket.",
         obj({"id": S, "decision": I, "choice": S, "note": S},
             ["id", "decision", "choice"]), decide, write=True),
]
