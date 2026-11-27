#!/usr/bin/env python3
"""prove_inputs.py -- what the prove workflow does about an attempt's falsifier and inputs (#126).

    py prove_inputs.py waiver --claim NS:ID [--ticket T-NNNN] [--cowork SLUG] [--home DIR] [--json]
    py prove_inputs.py inputs --claim NS:ID --ids ID [ID ...] [--instance researcher@x] [--json]

``waiver`` (#126, point 4): whether the human waived falsifiers for this claim by a ruling
scoped wider than one ticket, so a failed attempt files none. Two places hold such a ruling,
each as the human's own dated thread line (``- YYYY-MM-DD human: ...``, the form a ticket
waiver takes):

* the plan of the ticket's cowork (``<board>/cowork/<slug>.md``; the slug is ``--cowork``,
  else the ticket's ``cowork`` field): a line saying there are to be no falsifiers ("none of
  the flat-structure falsifiers for now", "no falsifiers", "falsifiers waived"). A later
  line of the human that asks for them again ("run the falsifiers again", "resume
  falsifiers") lifts it;
* the Researcher home's ``.claude/academy.json``, ``researcher.falsifierWaivers``: a list of
  ``{"scope": "<id or id prefix>", "line": "- YYYY-MM-DD human: ..."}``, the scope matched
  against the claim id with and without its namespace (``flat:FND-`` covers ``flat:FND-38``).

Prints ``{waived, source, scope, line}``; ``waived`` is false with ``why`` when none applies.

``inputs`` (#126, point 2): for each unreviewed input an attempt rests on, what settles it,
as ``[{id, status, action, ticket, to, why}]``:

* ``none`` -- proved or proved-modulo already, or no role of the workspace proves it here;
* ``link`` -- a verify or prove ticket naming it is open: ``ticket`` is that ticket;
* ``verify`` -- a sketch (a proof exists, unreviewed): a verify ticket to the Expert ``to``;
* ``prove`` -- open, conjectured or unknown: a prove ticket to the Researcher instance that
  owns its namespace (``to``).

Both read only (the board, the registry, the plan); the workflow files what ``inputs`` names.
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

#: the human's dated thread line, the one form a waiver counts in (prove.js, #117)
RE_HUMAN_LINE = re.compile(r"^\s*-?\s*(\d{4}-\d{2}-\d{2}) human:\s*(.+?)\s*$")
#: a ruling that there are to be no falsifiers
RE_WAIVE = re.compile(
    r"(?i)\bno falsifiers?\b|\bnone of the [\w./:-]+(?: [\w./:-]+)? falsifiers\b"
    r"|\bfalsifiers? (?:are |is )?waived\b|\bwaive[sd]? (?:the |all )?falsifiers?\b"
    r"|\bskip (?:the |all )?falsifiers?\b|\bwithout falsifiers\b")
#: a later ruling that asks for them again
RE_LIFT = re.compile(
    r"(?i)\b(?:resume|run|file|restart) (?:the |all )?falsifiers?(?: again)?\b"
    r"|\bfalsifiers? again\b|\bfalsifiers? (?:are )?back\b")
FINISHED = ("delivered", "closed", "rejected", "cancelled")
SETTLED = ("proved", "proved-modulo")
ARGUMENT_KINDS = ("verify", "prove")


def _bare(x):
    return re.sub(r"^[a-z][a-z0-9]*:", "", str(x or "").strip())


def _ns(x):
    m = re.match(r"^([a-z][a-z0-9]*):", str(x or "").strip())
    return m.group(1) if m else ""


def same_ref(a, b):
    """Two ids name one statement: equal, or equal without the namespace when one has
    none (prove.js's sameRef)."""
    a, b = str(a or "").strip(), str(b or "").strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if _ns(a) and _ns(b):
        return False
    return _bare(a) == _bare(b)


# ----------------------------------------------------------------------------
# waiver
# ----------------------------------------------------------------------------

def plan_waiver(text):
    """The human's line in a cowork plan that waives falsifiers and is not lifted by a
    later one of theirs, or ''."""
    found = ""
    for line in (text or "").splitlines():
        m = RE_HUMAN_LINE.match(line)
        if not m:
            continue
        words = m.group(2)
        if RE_LIFT.search(words) and not RE_WAIVE.search(words):
            found = ""
        elif RE_WAIVE.search(words):
            found = line.strip()
    return found


def config_waiver(cfg, claim):
    """The ``researcher.falsifierWaivers`` entry of a home's config covering ``claim``:
    ``(scope, line)``, or ``("", "")``. An entry without the human's dated line is skipped."""
    rows = ((cfg or {}).get("researcher") or {}).get("falsifierWaivers") or []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        scope, line = str(row.get("scope") or "").strip(), str(row.get("line") or "").strip()
        if not scope or not RE_HUMAN_LINE.match(line):
            continue
        for c in (str(claim), _bare(claim)):
            if c == scope or (scope.endswith(("-", "_", "/", ":")) and c.startswith(scope)):
                return scope, line
    return "", ""


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def waiver(claim, ticket_meta=None, cowork=None, home=None, board_path=None):
    """``{waived, source, scope, line}`` or ``{waived: False, why}`` (module docstring)."""
    if home:
        cfg = None
        try:
            cfg = json.loads(_read(os.path.join(home, ".claude", "academy.json")) or "null")
        except ValueError:
            cfg = None
        scope, line = config_waiver(cfg, claim)
        if line:
            return {"waived": True, "source": "config", "scope": scope, "line": line}
    slug = (cowork or (ticket_meta or {}).get("cowork") or "").strip()
    if not slug:
        return {"waived": False, "why": "no cowork on the ticket and no config waiver covers %s"
                % claim}
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", slug) or not board_path:
        return {"waived": False, "why": "cowork %r: its plan cannot be found" % slug}
    cands = [os.path.join(board_path, "cowork", slug + ".md")]
    try:
        cands += sorted(os.path.join(board_path, "cowork", f)
                        for f in os.listdir(os.path.join(board_path, "cowork"))
                        if re.match(r"^\d{4}-\d{2}-\d{2}-%s\.md$" % re.escape(slug), f))
    except OSError:
        pass
    for path in cands:
        text = _read(path)
        if text is None:
            continue
        line = plan_waiver(text)
        if line:
            return {"waived": True, "source": "cowork", "scope": slug, "line": line}
        return {"waived": False, "why": "the plan of cowork %s holds no standing waiver of the "
                "human's" % slug}
    return {"waived": False, "why": "cowork %s has no plan under the board's cowork/" % slug}


# ----------------------------------------------------------------------------
# inputs
# ----------------------------------------------------------------------------

def plan_inputs(claim, ids, metas, status_of, instances, instance=None):
    """The rows of ``inputs`` (module docstring). ``metas`` are the board's tickets,
    ``status_of`` maps a qualified id to its registry status (None when unknown),
    ``instances`` is workspace.json's ``instances``."""
    own_ns = _ns(claim)
    expert = next((n for n, i in sorted(instances.items()) if i.get("role") == "expert"), "")
    owner = {i.get("ns"): n for n, i in sorted(instances.items())
             if i.get("role") == "researcher" and i.get("ns")}
    rows, seen = [], set()
    for raw in ids:
        qid = str(raw).strip()
        if not qid:
            continue
        if not _ns(qid) and own_ns:
            qid = "%s:%s" % (own_ns, qid)
        if qid in seen or same_ref(qid, claim):
            continue
        seen.add(qid)
        try:
            st = status_of(qid)
        except Exception:    # an unreadable registry: the input is unknown, not settled
            st = None
        st = str(st or "").strip().lower()
        row = {"id": qid, "status": st or "unknown", "action": "none", "ticket": "", "to": "",
               "why": ""}
        if st in SETTLED:
            row["why"] = "%s already" % st
            rows.append(row)
            continue
        open_ = [m for m in metas if m and m.get("kind") in ARGUMENT_KINDS
                 and m.get("status") not in FINISHED
                 and any(same_ref(r, qid) for r in (m.get("refs") or []))]
        if open_:
            t = min(open_, key=lambda m: int(re.sub(r"\D", "", str(m.get("id"))) or 0))
            row.update(action="link", ticket=str(t.get("id")),
                       why="%s %s is %s" % (t.get("kind"), t.get("id"), t.get("status")))
        elif st == "sketch":
            if expert:
                row.update(action="verify", to=expert, why="a sketch: its proof is unreviewed")
            else:
                row["why"] = "a sketch, but the workspace has no Expert to verify it"
        elif _ns(qid) in owner:
            row.update(action="prove", to=owner[_ns(qid)],
                       why="%s: no proof to review yet" % (st or "status unknown"))
        else:
            row["why"] = "no Researcher instance owns namespace %r" % _ns(qid)
        rows.append(row)
    return rows


def _registry_status(qid):
    plugin = os.path.join(ac.repo_root(), "academy")
    if plugin not in sys.path:
        sys.path.insert(0, plugin)
    from registry.core import federation, workspace as rws
    ns, _, name = qid.partition(":")
    info = rws.namespaces().get(ns)
    home = info and info.get("home")
    if not home or not os.path.isdir(str(home)):
        return None
    rec = federation.store(ns, home).get(name)
    return rec.status if rec is not None else None


def _board(ws):
    store = ac.open_store(ws)
    return [m for _ref, m in store.iter_meta() if m]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("waiver")
    w.add_argument("--claim", required=True)
    w.add_argument("--ticket")
    w.add_argument("--cowork")
    w.add_argument("--home")
    w.add_argument("--json", action="store_true")
    i = sub.add_parser("inputs")
    i.add_argument("--claim", required=True)
    i.add_argument("--ids", nargs="+", required=True)
    i.add_argument("--instance")
    i.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    ws = ac.load_workspace()
    if a.cmd == "waiver":
        meta = None
        if a.ticket:
            meta = next((m for m in _board(ws) if str(m.get("id")) == a.ticket), None)
        board = (ws or {}).get("board")
        board_path = board.get("path") if isinstance(board, dict) else board
        res = waiver(a.claim, meta, a.cowork, a.home, board_path)
    else:
        res = plan_inputs(a.claim, a.ids, _board(ws), _registry_status,
                          (ws or {}).get("instances") or {}, a.instance)
    print(json.dumps(res, indent=1) if a.json else json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
