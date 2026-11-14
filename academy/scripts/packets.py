"""packets.py -- review packets on the board (docs/packet-template.md).

Usage:

    py packets.py new --instance X --title T [--kind K] [--by SPEAKER] [--ticket T-NNNN]
                      [--agenda ID] [--subject a,b] [--status-before S]
                      [--status-proposed S] [--body FILE]
    py packets.py list [--open] [--instance X] [--json]
    py packets.py show P-NNNN
    py packets.py decide P-NNNN --choice N [--decision K] [--comment TEXT]

``new`` fills ``academy/templates/packet.md`` (or takes the body of ``--body``,
which must carry the seven sections) and writes
``board/packets/<instance>/P-NNNN-<slug>.md``. With ``--ticket`` the packet id is
added to that ticket's ``packets`` list and a thread line records it.

``decide`` is the human's write-back. ``--choice`` is an option letter ``a``-``d``,
its number ``1``-``4``, ``other`` (``--comment`` then carries the answer) or ``ack``
(an informational packet, decision 0). ``--decision`` defaults to the first
unanswered decision. The line goes into ``## Decision``; ``state`` becomes
``decided`` once every decision has a line; and the answer is echoed into the
linked ticket's thread as ``decision on P-NNNN D<k>: (<letter>) <option>``, with the
comment as a continuation line. Only the human decides, so there is no ``--as``.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board as boardlib  # noqa: E402

TEMPLATE = os.path.join(PLUGIN, "templates", "packet.md")


def read_packet(path):
    with open(path, "r", encoding="utf-8") as fh:
        return ac.read_frontmatter(fh.read())


def write_packet(path, meta, body):
    ordered = {k: meta[k] for k in ac.PACKET_KEY_ORDER if k in meta}
    ac.atomic_write(path, ac.write_frontmatter(ordered, body))


def iter_packets(board):
    """Yield ``(path, meta, body)`` for every packet under ``board/packets/`` (``board``: a
    directory or a store; packets are files on every backend)."""
    root = os.path.join(ac.board_dir(board), "packets")
    rx = re.compile(r"^P-\d{4,}(?:-.*)?\.md$")
    if not os.path.isdir(root):
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for f in sorted(filenames):
            if not rx.match(f):
                continue
            p = os.path.join(dirpath, f)
            try:
                meta, body = read_packet(p)
            except (ac.FrontmatterError, OSError, UnicodeDecodeError):
                meta, body = None, ""
            yield p, meta, body


def list_packets(board, only_open=False, instance=None):
    out = []
    for path, meta, body in iter_packets(board):
        if meta is None:
            continue
        if only_open and meta.get("state") != "open":
            continue
        if instance and meta.get("instance") != instance:
            continue
        asked, answers = ac.packet_decisions(body), ac.packet_answers(body)
        m = dict(meta)
        m["_path"] = path
        m["_pending"] = sorted(k for k in asked if k not in answers)
        m["_problems"] = ac.validate_packet(meta, body)
        out.append(m)
    out.sort(key=lambda m: int(str(m.get("packet", "P-0")).split("-")[1] or 0))
    return out


#: rows of the text listing when no --limit is given
LIST_ROWS = 50


def brief(rows):
    """What a review reads from a listing, and no more (2026-11-13: 273 open packets were
    189 000 characters of JSON, mostly paths, nulls and the titles of packets that only
    want an acknowledgement).

    ``decide``: a row (packet, title, instance, kind, ticket, pending) per valid packet
    with a decision to make; ``problems``: packet, instance and the problems of each
    invalid one (shown on the dashboard, not asked); ``acknowledge``: the ids of the valid
    packets with nothing to decide. ``packets.py show P-NNNN`` prints any one in full."""
    out = {"count": len(rows), "decide": [], "problems": [], "acknowledge": []}
    for m in rows:
        if m.get("_problems"):
            out["problems"].append({"packet": m.get("packet"), "instance": m.get("instance"),
                                    "pending": m["_pending"], "problems": m["_problems"]})
        elif m["_pending"]:
            out["decide"].append({k: v for k, v in (
                ("packet", m.get("packet")), ("title", m.get("title")),
                ("instance", m.get("instance")), ("kind", m.get("kind")),
                ("ticket", m.get("ticket")), ("pending", m["_pending"])) if v})
        else:
            out["acknowledge"].append(m.get("packet"))
    return out


def get_packet(board, pid):
    path = ac.find_packet(ac.board_dir(board), pid)
    if not path:
        raise ac.AcademyError("no packet %s on %s" % (pid, ac.board_dir(board)))
    meta, body = read_packet(path)
    return path, meta, body


def create_packet(board, instance, title, kind="other", by=None, ticket=None,
                  agenda=None, subject=None, status_before=None, status_proposed=None,
                  body=None, template=TEMPLATE, workspace=None, date=None):
    """Allocate an id and write a new open packet. Returns its path."""
    ws = workspace
    if not ac.RE_INSTANCE.match(str(instance)):
        raise ac.AcademyError("instance must be an instance name, not %r" % instance)
    if ws is not None and instance not in ws["instances"]:
        raise ac.AcademyError("instance %r is not in workspace.json" % instance)
    date = date or ac.today()
    if body is None:
        with open(template, "r", encoding="utf-8") as fh:
            _tmeta, body = ac.read_frontmatter(fh.read())
    meta = {
        "packet": "P-0000", "title": title, "instance": instance,
        "kind": kind if kind in ac.PACKET_KINDS else "other", "by": by or instance,
        "ticket": ticket, "agenda": agenda, "subject": list(subject or []),
        "status_before": status_before, "status_proposed": status_proposed,
        "state": "open", "created": date, "decided": None,
    }
    probs = ac.validate_packet(meta, body)
    if ac.packet_answers(body):
        probs.append("## Decision must be empty at creation")
    if probs:
        raise ac.AcademyError("invalid packet: " + "; ".join(probs))
    store = ac.as_store(board)
    tref = None
    if ticket:
        tref = store.find(ticket)
        if not tref:
            raise ac.AcademyError("no ticket %s on the board" % ticket)
    pid = ac.allocate_id(ac.board_dir(board), "packet")
    meta["packet"] = pid
    path = os.path.join(ac.board_dir(board), "packets", instance,
                        ac.packet_filename(pid, title))
    write_packet(path, meta, body)
    if tref:
        _r, tm, tb = store.get(ticket)
        pk = list(tm.get("packets") or [])
        if pid not in pk:
            pk.append(pid)
        tm["packets"] = pk
        tm["updated"] = date
        tb = ac.append_thread(tb, meta["by"], "packet %s filed: %s" % (pid, title), date)
        store.save(tm, tb, tref)
    return path


def _choice_letter(choice):
    c = str(choice).strip().lower()
    if c in ("other", "ack"):
        return c
    if re.match(r"^[1-4]$", c):
        return "abcd"[int(c) - 1]
    if re.match(r"^\(?[a-d]\)?$", c):
        return c.strip("()")
    raise ac.AcademyError("choice must be a-d, 1-4, 'other' or 'ack', not %r" % choice)


#: the note a packet carries while work goes on under a recommendation that the human has
#: not decided yet (a note line of '## Decision': it answers nothing, docs/packet-template.md)
RE_PROVISIONAL = re.compile(r"^_Provisional (\d{4}-\d{2}-\d{2}): proceeding on D(\d+) "
                            r"\(([a-d])\), the recommendation; not decided\._$")


def provisional_choices(body):
    """``{k: letter}`` of the decisions a packet is being worked on provisionally."""
    out = {}
    for ln in body.replace("\r\n", "\n").split("\n"):
        m = RE_PROVISIONAL.match(ln.strip())
        if m:
            out[int(m.group(2))] = m.group(3)
    return out


def note_provisional(board, pid, k, letter, date=None):
    """Add the provisional note for decision ``k`` to the packet (once). Returns True when
    it was added. The packet stays open and the decision stays pending."""
    path, meta, body = get_packet(board, pid)
    if k in provisional_choices(body) or k in ac.packet_answers(body):
        return False
    lines = body.replace("\r\n", "\n").rstrip("\n").split("\n")
    if "## Decision" not in lines:
        raise ac.AcademyError("%s has no '## Decision' section" % pid)
    start = lines.index("## Decision") + 1
    end = next((j for j in range(start, len(lines)) if lines[j].startswith("## ")), len(lines))
    while end > start and not lines[end - 1].strip():
        end -= 1
    note = "_Provisional %s: proceeding on D%d (%s), the recommendation; not decided._" % (
        date or ac.today(), k, letter)
    lines[end:end] = ([""] if end == start else []) + [note]
    write_packet(path, meta, "\n".join(lines) + "\n")
    return True


def decide_packet(board, pid, choice, decision=None, comment="", date=None):
    """Write the human's answer into a packet and echo it into its ticket.

    Returns ``(packet_path, k, decided)``.
    """
    path, meta, body = get_packet(board, pid)
    date = date or ac.today()
    if meta.get("state") == "withdrawn":
        raise ac.AcademyError("%s is withdrawn" % pid)
    letter = _choice_letter(choice)
    asked, answers = ac.packet_decisions(body), ac.packet_answers(body)
    if letter == "ack":
        k = 0
        if asked:
            raise ac.AcademyError("%s asks decisions; 'ack' is only for informational "
                                  "packets" % pid)
    else:
        if not asked:
            raise ac.AcademyError("%s asks no decision; answer it with --choice ack" % pid)
        if decision is None:
            pending = sorted(x for x in asked if x not in answers)
            k = pending[0] if pending else max(asked)
        else:
            k = int(decision)
        if k not in asked:
            raise ac.AcademyError("%s has no decision D%d" % (pid, k))
        if letter != "other" and letter not in asked[k]["options"]:
            raise ac.AcademyError("D%d has no option (%s)" % (k, letter))
    was = provisional_choices(body).get(k)
    overturned = bool(was) and letter not in (was, "ack")
    body = ac.record_decision(body, k, letter, comment or "", ac.HUMAN, date)
    decided = ac.packet_is_decided(body)
    if decided:
        meta["state"] = "decided"
        meta["decided"] = date
    write_packet(path, meta, body)
    tid = meta.get("ticket")
    if tid:
        store = ac.as_store(board)
        tref = store.find(tid)
        if tref:
            if letter == "other":
                text = "decision on %s D%d: %s" % (pid, k, " ".join(comment.split()))
            elif letter == "ack":
                text = "decision on %s D0: ack" % pid
            else:
                text = "decision on %s D%d: (%s) %s" % (pid, k, letter,
                                                        asked[k]["options"][letter])
            if comment.strip() and letter != "other":
                text += "\n" + " ".join(comment.split())
            if overturned:
                text += ("\nthis overturns the provisional (%s) the work went on under: what "
                         "was done on it is to be revisited" % was)
            _r, tm, tb = store.get(tid)
            tb = ac.append_thread(tb, ac.HUMAN, text, date)
            tm["updated"] = date
            store.save(tm, tb, tref)
            if overturned and tm.get("status") == "delivered":
                # the human chose otherwise: the ticket goes back to its receiver
                try:
                    boardlib.transition_ticket(board, tid, "in-progress", date=date, reason=(
                        "returned: the decision on %s D%d overturns the provisional (%s)"
                        % (pid, k, was)))
                except ac.AcademyError:
                    pass
    return path, k, decided


def main(argv=None):
    ap = argparse.ArgumentParser(prog="packets.py", description=__doc__.split("\n")[0])
    ap.add_argument("--board"); ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="create a packet from the template")
    p.add_argument("--instance", required=True); p.add_argument("--title", required=True)
    p.add_argument("--kind", default="other", choices=ac.PACKET_KINDS)
    p.add_argument("--by"); p.add_argument("--ticket"); p.add_argument("--agenda")
    p.add_argument("--subject"); p.add_argument("--status-before", choices=ac.CLAIM_STATUSES)
    p.add_argument("--status-proposed", choices=ac.CLAIM_STATUSES)
    p.add_argument("--body", help="file whose body (after any frontmatter) is used")

    p = sub.add_parser("list", help="list packets")
    p.add_argument("--open", action="store_true"); p.add_argument("--instance")
    p.add_argument("--pending", action="store_true",
                   help="only packets with a decision still to make")
    p.add_argument("--json", action="store_true")
    p.add_argument("--brief", action="store_true",
                   help="with --json: what a review needs and no more (see brief())")
    p.add_argument("--limit", type=int, default=LIST_ROWS,
                   help="rows of the text listing, newest first (default %d, 0 = all)"
                        % LIST_ROWS)

    p = sub.add_parser("show", help="print one packet")
    p.add_argument("id")

    p = sub.add_parser("decide", help="record the human's answer to one decision")
    p.add_argument("id"); p.add_argument("--choice", required=True)
    p.add_argument("--decision", type=int); p.add_argument("--comment", default="")

    a = ap.parse_args(argv)
    boardlib._utf8_stdout()
    try:
        ws = boardlib._workspace_or_none(a.workspace)
        board = boardlib.resolve_store(a.board, a.workspace)
        if a.cmd == "new":
            body = None
            if a.body:
                with open(a.body, "r", encoding="utf-8") as fh:
                    _m, body = ac.read_frontmatter(fh.read())
            print(create_packet(board, a.instance, a.title, a.kind, a.by, a.ticket,
                                a.agenda, boardlib._split(a.subject), a.status_before,
                                a.status_proposed, body, workspace=ws))
        elif a.cmd == "list":
            rows = list_packets(board, a.open, a.instance)
            if a.pending:
                rows = [m for m in rows if m["_pending"]]
            if a.json and a.brief:
                print(json.dumps(brief(rows), ensure_ascii=False))
            elif a.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            else:
                total = len(rows)
                if a.limit > 0 and total > a.limit:
                    rows = rows[-a.limit:]
                    print("(the newest %d of %d; --limit 0 lists all, --pending only those "
                          "with a decision to make)" % (a.limit, total))
                for m in rows:
                    pend = ",".join("D%d" % k for k in m["_pending"]) or "-"
                    print("%-8s %-8s %-18s %-18s pending:%-8s %s" % (
                        m.get("packet"), m.get("state"), m.get("instance"), m.get("kind"),
                        pend, m.get("title")))
                print("%d packet(s)" % total)
        elif a.cmd == "show":
            path, meta, body = get_packet(board, a.id)
            with open(path, "r", encoding="utf-8") as fh:
                sys.stdout.write(fh.read())
            probs = ac.validate_packet(meta, body)
            if probs:
                print("\n# problems: " + "; ".join(probs))
        elif a.cmd == "decide":
            path, k, decided = decide_packet(board, a.id, a.choice, a.decision, a.comment)
            print("%s D%d recorded%s" % (path, k, "; packet decided" if decided else ""))
    except ac.AcademyError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
