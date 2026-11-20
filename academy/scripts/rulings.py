"""rulings.py -- a ruling the human answers files its follow-up by code (#121 item 4).

A **ruling ticket** is a ``decision`` ticket from an Expert instance to the human about
the inputs of one review pass whose two blind runs are both CONFIRMED on one statement
hash (verify's ``disagreement`` on the modulo lists, expert ``conclude.md`` section 4.3).
It is recognised mechanically: the ticket's text (or its parent's pass, ``<date>-<parent>``)
names the pass folder ``reviews/<ns>/<slug>/<pass>/`` in the Expert's home, whose ``A.md``
and ``B.md`` are both CONFIRMED, about one subject, on one hash, with distinct run ids.

Its options (``options``): (a) the union of the two modulo lists, (b) their intersection,
(c) a re-run, (d) decline. ``decisions.py record`` calls :func:`record` for such a ticket,
and in the same step files the follow-up the answer needs, then delivers the ruling with
the follow-up named in its result and thread:

* (a) / (b): a ``decision`` ticket to the claim-keeper's instance (the rule of the MCP's
  ``claims_propose_status``: the Researcher owning the namespace, else one sharing the
  owner's domains), ``parent`` the ruling, asking to set ``proved-modulo`` the chosen list
  (``proved`` when it is empty), with the pass's two verdict files as ``grounds``
  (``Grounds (JSON):`` line; :func:`grounds_in` reads it back);
* (c): a ``verify`` ticket back to the Expert for a fresh blind pass;
* (d): nothing; the ruling is rejected (as for any ticket).

Idempotent: a ruling that already has a follow-up (a child ticket filed by the human, a
``keeper follow-up: T-NNNN`` thread line, or a claim-keeper's line on it) files nothing
and writes nothing. An
``accepted`` ruling without one (answered before this existed: the stall of #121) gets
it on its next record. ``stalled`` lists those.

A bare ``proceed`` names no modulo (T-1521's "proceed" was "repair first"), so a ruling
refuses it and asks for a letter.
"""

import glob
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

#: a pass folder named in the ticket's text or a ``file:`` ref (``reviews/<ns>/<slug>/<pass>``)
RE_PASS_PATH = re.compile(r"reviews/([a-z0-9][a-z0-9-]*)/([^/\s`'\"()\[\]]+)/"
                          r"(\d{4}-\d{2}-\d{2}-[A-Za-z0-9-]+)")
RE_ABOUT_INPUTS = re.compile(r"(?i)\bmodulo\b|\binputs?\b")
RE_FOLLOW_UP = re.compile(r"\bkeeper follow-up: (T-\d{4,})")
RE_GROUNDS = re.compile(r"^Grounds \(JSON\): (\{.*\})\s*$", re.M)
NONE_WORDS = ("", "none", "-", "n/a", "[]", "null")
#: paper-label prefixes an unqualified modulo input may carry (decision_table.LABEL_PREFIXES)
LABEL_PREFIXES = {"lem", "thm", "defn", "def", "cor", "prop", "fact", "rmk", "obs",
                  "ex", "claim", "conj", "eq", "sec", "nota", "assm", "hyp"}
CHOICES = {"a": "union", "union": "union",
           "b": "intersection", "intersection": "intersection",
           "c": "rerun", "rerun": "rerun", "re-run": "rerun",
           "d": "decline", "decline": "decline", "no": "decline", "n": "decline"}
LETTER = {"union": "a", "intersection": "b", "rerun": "c", "decline": "d"}
#: the kinds a ruling's follow-up has: the keeper's status decision, or a verify re-run
FOLLOW_UP_KINDS = ("decision", "verify")
#: how a human's answer line reads (decisions.py, before and after this change)
RE_ANSWER = re.compile(r"^human decision: (?!decline)")


# ----------------------------------------------------------------------------
# Reading a pass
# ----------------------------------------------------------------------------

def _fields(text):
    """The ``key: value`` fields of a review record: its frontmatter, else the last
    ``VERDICT`` block."""
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    block = []
    if lines and lines[0].strip() == "---":
        for ln in lines[1:]:
            if ln.strip() == "---":
                break
            block.append(ln)
    else:
        starts = [i for i, ln in enumerate(lines) if ln.strip() == "VERDICT"]
        if starts:
            for ln in lines[starts[-1] + 1:]:
                if ln.strip().startswith("```") or not ln.strip():
                    break
                block.append(ln)
    out = {}
    for ln in block:
        if ln[:1] in (" ", "\t", "-") or ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        out[k.strip()] = "" if v in ("null", "~") else v
    return out


def _split_top(s):
    """``s`` split on the commas and semicolons outside brackets (#103)."""
    out, depth, cur = [], 0, []
    for ch in str(s):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch in ",;" and depth == 0:
            out.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    out.append("".join(cur))
    return out


def modulo_list(value, subject="", author_ns=False):
    """A record's ``modulo`` as a list in one spelling: split at top-level commas, quotes
    and spaces collapsed, an unqualified paper label qualified with the subject's
    namespace when an Author owns it, duplicates dropped (registry aliases are not
    resolved: the keeper's ``claims_set_status`` checks the ids)."""
    s = str(value or "").strip()
    if s.lower() in NONE_WORDS:
        return []
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    ns = str(subject or "").partition(":")[0]
    out = []
    for it in _split_top(s):
        it = " ".join(it.split()).strip("`'\"")
        if not it or it.lower() in NONE_WORDS:
            continue
        head = it.partition("#")[0]
        if (author_ns and ns and " " not in head and not any(c in head for c in "()[]{}")
                and head.partition(":")[0].lower() in LABEL_PREFIXES and ":" in head):
            it = "%s:%s" % (ns, it)
        if it not in out:
            out.append(it)
    return out


def _owner(workspace, ns):
    for name, inst in (workspace or {}).get("instances", {}).items():
        if inst.get("ns") == ns:
            return name, inst
    return None, {}


def keeper_instance(workspace, ns):
    """The claim-keeper's instance for namespace ``ns``: the rule of the MCP tool
    ``claims_propose_status`` (``academy/mcp/tools/claims.py`` ``_keeper_instance``)."""
    insts = (workspace or {}).get("instances", {})
    owner, info = _owner(workspace, ns)
    if owner and info.get("role") == "researcher":
        return owner
    doms = set(info.get("domains") or [])
    cands = [n for n, i in insts.items() if i.get("role") == "researcher"
             and (not doms or doms & set(i.get("domains") or []))]
    cands = cands or [n for n, i in insts.items() if i.get("role") == "researcher"]
    if not cands:
        raise ac.AcademyError("no researcher instance (claim-keeper) in workspace.json")
    return cands[0]


def _read_run(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return _fields(fh.read())
    except OSError:
        return None


def _pass_dirs(home, text, parent, subjects):
    """Candidate pass folders: the paths the ticket's text names, then the parent's pass."""
    seen = []
    for ns, slug, p in RE_PASS_PATH.findall(text):
        d = os.path.join(home, "reviews", ns, slug, p)
        if d not in seen:
            seen.append(d)
    if not seen and parent:
        found = sorted(glob.glob(os.path.join(home, "reviews", "*", "*", "*-" + parent)),
                       reverse=True)
        seen = found
    if len(seen) > 1 and subjects:
        keep = [d for d in seen if (_read_run(os.path.join(d, "A.md")) or {}).get("subject")
                in subjects]
        seen = keep or seen
    return seen


def find_ruling(board, tid, workspace=None, ticket=None):
    """The ruling ``tid`` is, as a dict, or None when it is not one (module docstring).

    ``ticket``: ``(path, meta, body)`` when already read."""
    ws = workspace if workspace is not None else boardlib._workspace_or_none()
    if not ws:
        return None
    _path, meta, body = ticket or boardlib.get_ticket(board, tid)
    insts = ws.get("instances", {})
    frm = meta.get("from")
    if meta.get("kind") != "decision" or meta.get("to") != ac.HUMAN:
        return None
    if (insts.get(frm) or {}).get("role") != "expert":
        return None
    head = body.split(ac.THREAD_HEADING)[0] if ac.THREAD_HEADING in body else body
    text = " ".join(str(meta.get(k) or "") for k in ("title", "ask", "deliverable")) + "\n" + head
    if not RE_ABOUT_INPUTS.search(text):
        return None
    home = (insts.get(frm) or {}).get("home")
    if not home:
        return None
    refs = [str(r) for r in (meta.get("refs") or [])]
    subjects = [r for r in refs if ":" in r and not r.startswith(("file:", "bib:"))]
    for d in _pass_dirs(home, text + "\n" + " ".join(refs), meta.get("parent"), subjects):
        a, b = _read_run(os.path.join(d, "A.md")), _read_run(os.path.join(d, "B.md"))
        if not a or not b:
            continue
        if any(ac_norm(r.get("verdict")) != "CONFIRMED" for r in (a, b)):
            continue
        subject, h = a.get("subject") or "", a.get("statement_hash") or ""
        if not subject or b.get("subject") != subject or not h or b.get("statement_hash") != h:
            continue
        ids = [a.get("run_id") or "", b.get("run_id") or ""]
        if not all(ids) or ids[0] == ids[1]:
            continue
        ns = subject.partition(":")[0]
        _o, owner = _owner(ws, ns)
        author_ns = owner.get("role") == "author"
        la = modulo_list(a.get("modulo"), subject, author_ns)
        lb = modulo_list(b.get("modulo"), subject, author_ns)
        rel = os.path.relpath(d, home).replace("\\", "/")
        return {
            "id": meta["id"], "subject": subject, "pass": os.path.basename(d),
            "pass_dir": rel, "expert": frm, "statement_hash": h,
            "producer_role": owner.get("role") or "",
            "modulo_lists": {"A": la, "B": lb},
            "union": la + [x for x in lb if x not in la],
            "intersection": [x for x in la if x in lb],
            "verdicts": [{"verdict": "CONFIRMED", "run_id": r.get("run_id"),
                          "statement_hash": h, "grader_role": "expert",
                          "ref": "file:%s/%s/%s.md" % (frm, rel, run)}
                         for run, r in (("A", a), ("B", b))],
            "keeper": keeper_instance(ws, ns),
            "packets": [r for r in refs if ac.RE_PACKET_ID.match(r)],
            "priority": meta.get("priority") or "normal",
        }
    return None


def ac_norm(v):
    return " ".join(str(v or "").replace("_", " ").replace("-", " ").upper().split())


# ----------------------------------------------------------------------------
# Options and the follow-up
# ----------------------------------------------------------------------------

def _fmt(items):
    return "[" + ", ".join(items) + "]" if items else "no inputs"


def options(r):
    """The four options of a ruling, ``{label, description}`` as decisions.py shows them."""
    return [
        {"label": "(a) Union", "description": "%s %s modulo the union of both runs' lists %s; "
         "the keeper ticket is filed now" % (r["subject"], _target(r["union"]), _fmt(r["union"]))},
        {"label": "(b) Intersection", "description": "%s %s modulo what both runs list %s; "
         "the keeper ticket is filed now" % (r["subject"], _target(r["intersection"]),
                                              _fmt(r["intersection"]))},
        {"label": "(c) Re-run", "description": "No status now: a verify ticket for a fresh "
         "blind pass goes to %s" % r["expert"]},
        {"label": "(d) Decline", "description": "Reject the ruling; nothing is filed."},
    ]


def _target(modulo):
    return "proved-modulo" if modulo else "proved"


def parse_choice(choice):
    c = str(choice or "").strip().lower().strip("()")
    if c in CHOICES:
        return CHOICES[c]
    raise ac.AcademyError(
        "a ruling on the inputs takes a/union, b/intersection, c/re-run or d/decline, not %r "
        "(a bare proceed names no modulo)" % choice)


def grounds(r, which, quote=""):
    modulo = list(r[which])
    g = {"basis": "proof", "verdicts": [dict(v) for v in r["verdicts"]],
         "producer_role": r["producer_role"], "statement_hash": r["statement_hash"],
         "note": "the human's ruling %s: (%s) the %s of both runs' modulo lists%s"
                 % (r["id"], LETTER[which], which, (" -- " + quote) if quote else "")}
    if modulo:
        g["modulo"] = modulo
    return g


def grounds_in(body):
    """The grounds a follow-up ticket carries, parsed back (None when it has none)."""
    m = RE_GROUNDS.search(body or "")
    return json.loads(m.group(1)) if m else None


def follow_up_of(board, tid, body=None):
    """The follow-up a ruling already has, or None: a ``keeper follow-up:`` line in its
    thread (its ticket id), a line by a claim-keeper (the keeper acted on the ruling, as on
    T-0979: ``<instance>/claim-keeper``), else a child ticket (``parent`` = the ruling)
    filed by the human, or a ``decision`` / ``verify`` ticket to a role naming the ruling
    as parent or in its refs (T-0786, T-1769; its id)."""
    if body is None:
        body = boardlib.get_ticket(board, tid)[2]
    for _d, who, text in ac.thread_lines(body):
        m = RE_FOLLOW_UP.search(text)
        if m:
            return m.group(1)
        if str(who).endswith("/claim-keeper"):
            return who
    for m in boardlib.list_tickets(board, include_terminal=True):
        if m.get("parent") == tid and m.get("from") == ac.HUMAN:
            return m["id"]
        if m.get("kind") in FOLLOW_UP_KINDS and m.get("to") != ac.HUMAN and (
                m.get("parent") == tid or tid in [str(x) for x in (m.get("refs") or [])]):
            return m["id"]
    return None


def plan(r, which, comment=""):
    """The follow-up ticket's fields for answer ``which`` (no write), or None for decline."""
    quote = " ".join(str(comment or "").split())
    vrefs = [v["ref"] for v in r["verdicts"]]
    refs = [r["subject"], r["id"]] + [p for p in r["packets"] if p not in (r["subject"],)] + vrefs
    if which == "rerun":
        return {"to": r["expert"], "kind": "verify",
                "title": "Re-run the blind pass on %s (ruling %s)" % (r["subject"], r["id"]),
                "ask": "Verify %s in a fresh blind pass: the human ordered a re-run instead of "
                       "ruling on the inputs of pass %s (%s)." % (r["subject"], r["pass"], r["id"]),
                "deliverable": "A new pass with its decision record and packet.",
                "refs": refs,
                "detail": "The human's answer on %s: (c) re-run%s.\n\nThe earlier pass: `%s` "
                          "(A and B CONFIRMED on hash %s, modulo lists differing)."
                          % (r["id"], (" -- " + quote) if quote else "", r["pass_dir"],
                             r["statement_hash"])}
    if which not in ("union", "intersection"):
        return None
    g = grounds(r, which, quote)
    status = _target(g.get("modulo"))
    return {"to": r["keeper"], "kind": "decision",
            "title": "Status of %s -> %s (ruling %s)" % (r["subject"], status, r["id"]),
            "ask": "Set %s to %s%s (claims_set_status) on the human's ruling %s (%s), with "
                   "the grounds below." % (r["subject"], status,
                                            (" modulo " + _fmt(g["modulo"])) if g.get("modulo") else "",
                                            r["id"], which),
            "deliverable": "The status is set with grounds, or the ticket is rejected with "
                           "the reason.",
            "refs": refs,
            "detail": "\n\n".join([
                "The human's answer on %s: (%s) the %s of both runs' modulo lists%s."
                % (r["id"], LETTER[which], which, (" -- \"%s\"" % quote) if quote else ""),
                "Pass `%s` of the Expert %s: A and B CONFIRMED on statement hash %s. "
                "A lists %s; B lists %s." % (r["pass_dir"], r["expert"], r["statement_hash"],
                                            _fmt(r["modulo_lists"]["A"]),
                                            _fmt(r["modulo_lists"]["B"])),
                "If the claim's statement hash is no longer %s (the statement was edited), do "
                "not set it: reject this ticket with that reason, for a re-run. An input that "
                "is itself unsettled stays in the modulo list." % r["statement_hash"],
                "Grounds (JSON): " + json.dumps(g, ensure_ascii=False, separators=(", ", ": ")),
            ])}


def _deliver(board, tid, result, date):
    meta = boardlib.get_ticket(board, tid)[1]
    if meta.get("status") == "open":
        boardlib.transition_ticket(board, tid, "accepted", as_instance=ac.HUMAN, date=date)
        meta = boardlib.get_ticket(board, tid)[1]
    if meta.get("status") == "accepted":
        boardlib.transition_ticket(board, tid, "in-progress", as_instance=ac.HUMAN, date=date)
    boardlib.transition_ticket(board, tid, "delivered", result=result, as_instance=ac.HUMAN,
                               date=date)


def record(board, r, choice, comment="", workspace=None, date=None, ticket=None):
    """Record the human's answer to ruling ``r`` and file its follow-up in the same step.

    Returns ``{"ref", "status", "choice", "follow_up", "filed"}``. A ruling that already
    has a follow-up writes nothing (``filed`` False)."""
    date = date or ac.today()
    tid = r["id"]
    which = parse_choice(choice)
    _path, meta, body = ticket or boardlib.get_ticket(board, tid)
    status = meta.get("status")
    have = follow_up_of(board, tid, body)
    if have:
        return {"ref": tid, "status": status, "choice": LETTER.get(which), "follow_up": have,
                "filed": False}
    if status not in ("open", "accepted", "in-progress"):
        raise ac.AcademyError("%s is %s: a finished ruling is not answered again" % (tid, status))
    text = "human decision: (%s) %s" % (LETTER[which], which)
    if str(comment).strip():
        text += " -- " + " ".join(str(comment).split())
    if which == "decline":
        if status != "open":
            raise ac.AcademyError("%s is %s: decline it with board.py transition" % (tid, status))
        boardlib.append_to_ticket(board, tid, text, as_instance=ac.HUMAN, date=date)
        boardlib.transition_ticket(board, tid, "rejected", reason=" ".join(
            str(comment).split()) or "declined via /academy:decide", as_instance=ac.HUMAN,
            date=date)
        return {"ref": tid, "status": "rejected", "choice": "d", "follow_up": None,
                "filed": False}
    spec = plan(r, which, comment)
    boardlib.append_to_ticket(board, tid, text, as_instance=ac.HUMAN, date=date)
    path = boardlib.create_ticket(
        board, spec["to"], spec["title"], spec["ask"], spec["deliverable"], kind=spec["kind"],
        priority=r["priority"], refs=spec["refs"], parent=tid, budget={"runs": 1},
        detail=spec["detail"], as_instance=ac.HUMAN, workspace=workspace, date=date)
    new = (boardlib.read_ticket(path)[0]["id"] if os.path.isfile(str(path))
           else _id_of(board, path, tid))
    what = ("keeper follow-up: %s to %s (%s)" % (new, spec["to"], spec["title"])
            if which != "rerun" else
            "keeper follow-up: %s to %s (a re-run; no status now)" % (new, spec["to"]))
    boardlib.append_to_ticket(board, tid, what, as_instance=ac.HUMAN, date=date)
    result = ("Ruling (%s) %s: %s; %s filed to %s" % (
        LETTER[which], which, spec["title"], new, spec["to"]))
    _deliver(board, tid, result, date)
    return {"ref": tid, "status": "delivered", "choice": LETTER[which], "follow_up": new,
            "filed": True}


def _id_of(board, path, parent):
    """The id of the ticket just created at ``path`` on a non-file store."""
    for m in boardlib.list_tickets(board, include_terminal=True):
        if m.get("_path") == path or (m.get("parent") == parent and m.get("from") == ac.HUMAN):
            return m["id"]
    raise ac.AcademyError("the follow-up of %s was filed but its id is not found" % parent)


# ----------------------------------------------------------------------------
# Stalled rulings
# ----------------------------------------------------------------------------

def stalled(board, workspace=None):
    """Rulings the human answered (a ``human decision:`` line, not a decline) that are
    still ``accepted`` / ``in-progress`` with no follow-up: ``[{"id", "subject", "answer"}]``."""
    ws = workspace if workspace is not None else boardlib._workspace_or_none()
    roles = {n: i.get("role") for n, i in (ws or {}).get("instances", {}).items()}
    metas = boardlib.list_tickets(board, include_terminal=True)
    out = []
    for m in metas:
        if (m.get("kind") != "decision" or m.get("to") != ac.HUMAN
                or roles.get(m.get("from")) != "expert"
                or m.get("status") not in ("accepted", "in-progress")):
            continue
        t = boardlib.get_ticket(board, m["id"])
        answers = [x for _d, w, x in ac.thread_lines(t[2]) if w == ac.HUMAN and RE_ANSWER.match(x)]
        if not answers:
            continue
        r = find_ruling(board, m["id"], ws, ticket=t)
        if not r or follow_up_of(board, m["id"], t[2]):
            continue
        out.append({"id": m["id"], "subject": r["subject"], "answer": answers[-1]})
    return out
