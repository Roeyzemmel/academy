"""board.py -- the ticket CLI over the board repo (docs/protocol.md sections 2-4).

Usage (from anywhere; the board comes from workspace.json unless --board is given):

    py board.py list [--to X] [--from X] [--status S] [--all] [--json]
    py board.py new --to X --title T --ask A --deliverable D [--kind K] [--priority P]
                    [--refs a,b] [--agenda ID] [--domain D] [--parent T-NNNN]
                    [--runs N] [--max-model M] [--detail TEXT] --as INSTANCE [--agent NAME]
                    [--final-to ROLE]
    py board.py show T-NNNN [--json]
    py board.py transition T-NNNN STATUS [--reason R] [--result R] [--waiting-on a,b]
                    [--as INSTANCE] [--agent NAME]
    py board.py append T-NNNN --text TEXT [--as INSTANCE] [--agent NAME]

``--as`` names the caller's instance; ``new`` requires it (``--as human`` only from
/academy:board, desk and decide); for ``transition`` and ``append``, without it the
caller is the human. The functions below are the implementation
and may be imported (the MCP server and the tests do); the CLI is a thin wrapper.
Nothing here commits: board commits are made by session_start / board sync.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))

import academy_common as ac  # noqa: E402

RESERVED = ("packets", "deep-dives", ".ids", ".render", ".git")
PRIORITY_ORDER = {"high": 0, "normal": 1, "low": 2}


# ----------------------------------------------------------------------------
# Locating the board and the workspace
# ----------------------------------------------------------------------------

def resolve_board(board=None, workspace=None):
    """The board directory: ``board`` if given, else workspace.json's ``board``."""
    if board:
        return os.path.abspath(board)
    return os.path.abspath(ac.load_workspace(workspace)["board"])


def _workspace_or_none(workspace=None):
    try:
        return ac.load_workspace(workspace)
    except ac.ConfigError:
        return None


def _default_budget(cwd=None):
    """``{"runs": n}`` from ``budget.ticketDefault`` of the caller's home config, or the
    library default (``ac.default_ticket_budget``; no ``max_model``, T-0071)."""
    home = ac.find_home(cwd or os.getcwd())
    cfg = None
    if home:
        try:
            cfg = ac.load_config(home)
        except ac.AcademyError:
            pass
    return ac.default_ticket_budget(cfg)


def _split(s):
    if s is None:
        return None
    return [x.strip() for x in str(s).split(",") if x.strip()]


# ----------------------------------------------------------------------------
# Reading tickets
# ----------------------------------------------------------------------------

def read_ticket(path):
    with open(path, "r", encoding="utf-8") as fh:
        meta, body = ac.read_frontmatter(fh.read())
    return meta, body


def write_ticket(path, meta, body):
    ordered = {k: meta[k] for k in ac.TICKET_KEY_ORDER if k in meta}
    ac.atomic_write(path, ac.write_frontmatter(ordered, body))


def iter_tickets(board):
    """Yield ``(path, meta, body)`` for every ticket file on the board.

    Only files named ``T-NNNN-*.md`` inside instance folders and ``human/`` count
    (protocol.md section 2). An unreadable file is yielded with ``meta = None``.
    """
    import re
    rx = re.compile(r"^T-\d{4,}(?:-.*)?\.md$")
    if not os.path.isdir(board):
        return
    for folder in sorted(os.listdir(board)):
        full = os.path.join(board, folder)
        if folder in RESERVED or folder.startswith(".") or not os.path.isdir(full):
            continue
        for f in sorted(os.listdir(full)):
            if not rx.match(f):
                continue
            p = os.path.join(full, f)
            try:
                meta, body = read_ticket(p)
            except (ac.FrontmatterError, OSError, UnicodeDecodeError):
                meta, body = None, ""
            yield p, meta, body


def list_tickets(board, to=None, frm=None, status=None, include_terminal=False):
    """Tickets matching the filters, ordered by priority then id.

    Without ``status`` and ``include_terminal`` the terminal tickets (closed,
    rejected, cancelled) are left out.
    """
    out = []
    for path, meta, _body in iter_tickets(board):
        if meta is None:
            continue
        if to and meta.get("to") != to:
            continue
        if frm and meta.get("from") != frm:
            continue
        if status:
            if meta.get("status") != status:
                continue
        elif not include_terminal and meta.get("status") in ac.TERMINAL:
            continue
        m = dict(meta)
        m["_path"] = path
        out.append(m)
    out.sort(key=lambda m: (PRIORITY_ORDER.get(m.get("priority"), 1),
                            int(str(m.get("id", "T-0")).split("-")[1] or 0)))
    return out


def get_ticket(board, tid):
    path = ac.find_ticket(board, tid)
    if not path:
        raise ac.AcademyError("no ticket %s on %s" % (tid, board))
    meta, body = read_ticket(path)
    return path, meta, body


# ----------------------------------------------------------------------------
# Writing tickets
# ----------------------------------------------------------------------------

def bare_agent(agent):
    """An agent named as a speaker is its bare name: ``expert:librarian`` (the name an
    agent carries, plugin-namespaced) is written ``librarian`` (docs/protocol.md 1)."""
    return str(agent or "").strip().rsplit(":", 1)[-1].strip()


def _check_party(name, workspace, what):
    if not ac.is_party(name):
        raise ac.AcademyError("%s must be an instance name or 'human', not %r" % (what, name))
    if name != ac.HUMAN and workspace is not None and name not in workspace["instances"]:
        raise ac.AcademyError("%s %r is not an instance of workspace.json" % (what, name))


def create_ticket(board, to, title, ask, deliverable, kind="other", priority="normal",
                  refs=None, agenda=None, domain=None, parent=None, budget=None,
                  detail="", as_instance=None, agent="", workspace=None, date=None,
                  final_to=None, perms=None):
    """Allocate an id and write a new ``open`` ticket in ``board/<to>/``. Returns its path."""
    ws = workspace if workspace is not None else _workspace_or_none()
    if not as_instance:
        raise ac.AcademyError("--as is required: the filing instance ('human' only from "
                              "/academy:board, desk or decide, after Roey confirms)")
    _check_party(to, ws, "to")
    _check_party(as_instance, ws, "from")
    who = bare_agent(agent) or (ac.MAIN_AGENT if as_instance != ac.HUMAN else "")
    depth = ac.relay_depth(board, parent) if final_to and parent else 0
    ok, why = ac.ticket_edge_allowed(as_instance, to, who,
                                     perms if perms is not None else ac.load_permissions(),
                                     ws, final_to, depth)
    if not ok:
        raise ac.AcademyError("refused: " + why)
    if kind not in ac.TICKET_KINDS:
        kind = "other"
    if domain is None and ws is not None and to in ws["instances"]:
        domain = (ws["instances"][to].get("domains") or [None])[0]
    date = date or ac.today()
    meta = {
        "id": "T-0000", "title": title, "kind": kind, "from": as_instance, "to": to,
        "status": "open", "priority": priority, "ask": ask, "deliverable": deliverable,
        "refs": list(refs or []), "agenda": agenda, "domain": domain, "parent": parent,
        "final_to": final_to,
        "blocks": [], "waiting_on": [], "budget": dict(budget or _default_budget()),
        "result": None, "packets": [], "created": date, "updated": date,
    }
    probs = ac.validate_ticket(meta)
    if probs:
        raise ac.AcademyError("invalid ticket: " + "; ".join(probs))
    tid = ac.allocate_id(board, "ticket")
    meta["id"] = tid
    text = ac.new_ticket(meta, detail)
    fm, body = ac.read_frontmatter(text)
    body = ac.append_thread(body, ac.format_who(as_instance, who), "opened", date)
    path = os.path.join(board, to, ac.ticket_filename(tid, title))
    write_ticket(path, fm, body)
    return path


def append_to_ticket(board, tid, text, as_instance=ac.HUMAN, agent="", date=None):
    """Append one entry to the ticket's thread. Returns the path."""
    path, meta, body = get_ticket(board, tid)
    date = date or ac.today()
    body = ac.append_thread(body, ac.format_who(as_instance, bare_agent(agent)), text, date)
    meta["updated"] = date
    write_ticket(path, meta, body)
    return path


def _mirror_blocks(board, tid, waiting_on, date):
    """Add ``tid`` to the ``blocks`` list of every ticket it now waits on."""
    for w in waiting_on or []:
        if not ac.RE_TICKET_ID.match(str(w)):
            continue
        p = ac.find_ticket(board, w)
        if not p:
            continue
        m, b = read_ticket(p)
        blocks = list(m.get("blocks") or [])
        if tid not in blocks:
            blocks.append(tid)
            m["blocks"] = blocks
            m["updated"] = date
            write_ticket(p, m, b)


def transition_ticket(board, tid, new, reason="", result=None, waiting_on=None,
                      as_instance=ac.HUMAN, agent="", date=None):
    """Move a ticket to ``new`` under the lifecycle rules. Returns the path.

    Raises AcademyError when the caller may not make the move or a requirement
    (reason, result, waiting_on) is missing. The thread gets one line per field set
    and one ``status <old> -> <new>[: reason]`` line.
    """
    path, meta, body = get_ticket(board, tid)
    date = date or ac.today()
    as_instance = as_instance or ac.HUMAN
    human = as_instance == ac.HUMAN
    old = meta.get("status")
    ok, why = ac.can_transition(old, new, ac.parties(meta, as_instance), human=human)
    if not ok:
        raise ac.AcademyError("%s: %s" % (tid, why))
    if old == new:
        return path
    needs_reason = new in ("rejected", "cancelled") or (old, new) == ("delivered",
                                                                      "in-progress")
    if needs_reason and not (reason or "").strip():
        raise ac.AcademyError("%s: %s -> %s needs a reason" % (tid, old, new))
    who = ac.format_who(as_instance, bare_agent(agent))
    if result is not None and str(result).strip():
        meta["result"] = " ".join(str(result).split())
        body = ac.append_thread(body, who, "set result: %s" % meta["result"], date)
    if new == "blocked":
        wo = list(waiting_on or meta.get("waiting_on") or [])
        if not wo:
            raise ac.AcademyError("%s: a blocked ticket needs --waiting-on" % tid)
        meta["waiting_on"] = wo
        body = ac.append_thread(body, who, "set waiting_on: [%s]" % ", ".join(wo), date)
    elif meta.get("waiting_on"):
        meta["waiting_on"] = []
    if new in ("delivered", "closed") and not meta.get("result"):
        raise ac.AcademyError("%s: %s needs a result (--result)" % (tid, new))
    meta["status"] = new
    meta["updated"] = date
    line = "status %s -> %s" % (old, new)
    if (reason or "").strip():
        line += ": " + reason.strip()
    body = ac.append_thread(body, who, line, date)
    probs = ac.validate_ticket(meta, body)
    if probs:
        raise ac.AcademyError("%s would be invalid: %s" % (tid, "; ".join(probs)))
    write_ticket(path, meta, body)
    if new == "blocked":
        _mirror_blocks(board, tid, meta["waiting_on"], date)
    return path


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _fmt_row(m):
    return "%-8s %-11s %-6s %-18s -> %-18s %s" % (
        m.get("id"), m.get("status"), m.get("priority"), m.get("from"), m.get("to"),
        m.get("title"))


def _utf8_stdout():
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="board.py", description=__doc__.split("\n")[0])
    ap.add_argument("--board", help="board directory (default: workspace.json 'board')")
    ap.add_argument("--workspace", help="workspace.json to use")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="list tickets")
    p.add_argument("--to"); p.add_argument("--from", dest="frm"); p.add_argument("--status")
    p.add_argument("--all", action="store_true", help="include closed/rejected/cancelled")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("new", help="file a new ticket")
    p.add_argument("--to", required=True); p.add_argument("--title", required=True)
    p.add_argument("--ask", required=True); p.add_argument("--deliverable", required=True)
    p.add_argument("--kind", default="other"); p.add_argument("--priority", default="normal",
                                                               choices=ac.PRIORITIES)
    p.add_argument("--refs"); p.add_argument("--agenda"); p.add_argument("--domain")
    p.add_argument("--parent"); p.add_argument("--runs", type=int)
    p.add_argument("--max-model", choices=ac.MODELS,
                   help="optional advisory note for budget.max_model; never a gate: the "
                        "agent file sets the model (T-0071)")
    p.add_argument("--detail", default="")
    p.add_argument("--as", dest="as_instance", required=True)
    p.add_argument("--final-to", dest="final_to")
    p.add_argument("--agent", default="")

    p = sub.add_parser("show", help="print one ticket")
    p.add_argument("id"); p.add_argument("--json", action="store_true")

    p = sub.add_parser("transition", help="change a ticket's status")
    p.add_argument("id"); p.add_argument("status", choices=ac.TICKET_STATUSES)
    p.add_argument("--reason", default=""); p.add_argument("--result")
    p.add_argument("--waiting-on")
    p.add_argument("--as", dest="as_instance", default=ac.HUMAN)
    p.add_argument("--agent", default="")

    p = sub.add_parser("append", help="append a line to a ticket's thread")
    p.add_argument("id"); p.add_argument("--text", required=True)
    p.add_argument("--as", dest="as_instance", default=ac.HUMAN)
    p.add_argument("--agent", default="")

    a = ap.parse_args(argv)
    _utf8_stdout()
    try:
        ws = _workspace_or_none(a.workspace)
        board = resolve_board(a.board, a.workspace)
        if a.cmd == "list":
            rows = list_tickets(board, a.to, a.frm, a.status, a.all)
            if a.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            else:
                for m in rows:
                    print(_fmt_row(m))
                print("%d ticket(s)" % len(rows))
        elif a.cmd == "new":
            budget = _default_budget()
            if a.runs:
                budget["runs"] = a.runs
            if a.max_model:
                budget["max_model"] = a.max_model
            path = create_ticket(board, a.to, a.title, a.ask, a.deliverable, a.kind,
                                 a.priority, _split(a.refs), a.agenda, a.domain, a.parent,
                                 budget, a.detail, a.as_instance, a.agent, ws,
                                 final_to=a.final_to)
            print(path)
        elif a.cmd == "show":
            path, meta, body = get_ticket(board, a.id)
            if a.json:
                print(json.dumps({"path": path, "meta": meta, "body": body,
                                  "thread": ac.thread_lines(body),
                                  "problems": ac.validate_ticket(meta, body)},
                                 indent=2, ensure_ascii=False))
            else:
                with open(path, "r", encoding="utf-8") as fh:
                    sys.stdout.write(fh.read())
                probs = ac.validate_ticket(meta, body)
                if probs:
                    print("\n# problems: " + "; ".join(probs))
        elif a.cmd == "transition":
            print(transition_ticket(board, a.id, a.status, a.reason, a.result,
                                    _split(a.waiting_on), a.as_instance, a.agent))
        elif a.cmd == "append":
            print(append_to_ticket(board, a.id, a.text, a.as_instance, a.agent))
    except ac.AcademyError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
