"""board_project.py -- the GitHub Project (v2) fields of the board, as a declarative spec.

    py board_project.py [--workspace FILE] [--out spec.json]   the spec (JSON)
    py board_project.py --check                                the spec covers every kind,
                                                               status, priority, role (exit 1 if not)
    py board_project.py --live fields.json                     compare with the live Project

Offline: nothing is sent anywhere. The spec is derived from the codec and the academy
constants (``ac.TICKET_KINDS``, ``ac.TICKET_STATUSES`` ...), so a new kind or status reaches
the Project by regenerating, never by editing options by hand. The runbook (or a token with
the ``project`` scope) creates the fields and options from ``fields`` and sets each item's
values from ``fields_for(meta)``. ``fields.json`` for ``--live`` is what the Project reports:
``{"fields": [{"name": "Kind", "options": ["verify", ...]}, ...]}`` (options as names or
``{"name": ...}``); missing fields and options are reported, extra ones are only noted.

Fields (docs/github-board.md): **Status** (Todo = open, In Progress, Done = closed / rejected
/ cancelled, plus Accepted, Blocked, Delivered), **Instance** (the ``to`` of the ticket, one
option per workspace instance and ``human``), **Role**, **Kind**, **Priority** (P0/P1/P2 =
high/normal/low), **Agenda** (text) and **Block** (``pending`` or ``dead-route``, set on a
blocked ticket only, the Project twin of the label ``route:dead``).
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board_codec as bc  # noqa: E402

#: ticket status -> option of the Project's Status field
STATUS_OPTIONS = {"open": "Todo", "accepted": "Accepted", "in-progress": "In Progress",
                  "delivered": "Delivered", "blocked": "Blocked", "closed": "Done",
                  "rejected": "Done", "cancelled": "Done"}
#: ticket priority -> option of the Priority field
PRIORITY_OPTIONS = {"high": "P0", "normal": "P1", "low": "P2"}
BLOCK_OPTIONS = ("pending", "dead-route")


def _opts(names):
    seen = []
    for n in names:
        if n not in seen:
            seen.append(n)
    return [{"name": n} for n in seen]


def build(instances=None):
    """The spec: ``{"schema", "fields": [{name, type, options?}], "mappings": {...}}``.

    ``instances`` are the workspace's instance names (``human`` is always added); without
    them the Instance field lists ``human`` only and says its options come from the workspace.
    """
    inst = list(instances or []) + [ac.HUMAN]
    fields = [
        {"name": "Status", "type": "single_select",
         "options": _opts(STATUS_OPTIONS[s] for s in ac.TICKET_STATUSES)},
        {"name": "Instance", "type": "single_select", "options": _opts(inst),
         "options_from": "workspace.instances + human"},
        {"name": "Role", "type": "single_select", "options": _opts(bc.ROLES)},
        {"name": "Kind", "type": "single_select", "options": _opts(ac.TICKET_KINDS)},
        {"name": "Priority", "type": "single_select",
         "options": _opts(PRIORITY_OPTIONS[p] for p in ac.PRIORITIES)},
        {"name": "Agenda", "type": "text"},
        {"name": "Block", "type": "single_select", "options": _opts(BLOCK_OPTIONS)},
    ]
    return {"schema": 1, "fields": fields,
            "mappings": {"status": dict(STATUS_OPTIONS), "priority": dict(PRIORITY_OPTIONS),
                         "block": {"pending": "pending", "dead-route": "dead-route"}}}


def fields_for(meta):
    """The Project field values of a ticket (None where the field stays empty)."""
    blocked = meta.get("status") == "blocked"
    return {"Status": STATUS_OPTIONS.get(meta.get("status")),
            "Instance": meta.get("to"),
            "Role": bc.role_of(meta["to"]) if meta.get("to") else None,
            "Kind": meta.get("kind"),
            "Priority": PRIORITY_OPTIONS.get(meta.get("priority")),
            "Agenda": meta.get("agenda") or None,
            "Block": (("dead-route" if bc.is_dead_route(meta) else "pending")
                      if blocked else None)}


def _field(spec, name):
    return next((f for f in spec["fields"] if f["name"] == name), None)


def _names(field):
    return [o["name"] for o in (field or {}).get("options", [])]


def check(spec):
    """Problems: what the spec fails to cover (empty when it covers every kind, status,
    priority and role, and every mapping lands on an option that exists)."""
    probs = []
    for fname, wanted in (("Kind", ac.TICKET_KINDS), ("Role", bc.ROLES)):
        have = _names(_field(spec, fname))
        probs += ["%s has no option %r" % (fname, w) for w in wanted if w not in have]
        probs += ["%s option %r is not a %s" % (fname, h, fname.lower())
                  for h in have if h not in wanted]
    for fname, table, keys in (("Status", "status", ac.TICKET_STATUSES),
                               ("Priority", "priority", ac.PRIORITIES)):
        have = _names(_field(spec, fname))
        m = spec["mappings"][table]
        for k in keys:
            if k not in m:
                probs.append("no %s option for %s %r" % (fname, table, k))
            elif m[k] not in have:
                probs.append("%s %r maps to %r, which is not a %s option" % (table, k, m[k],
                                                                              fname))
    if _names(_field(spec, "Block")) != list(BLOCK_OPTIONS):
        probs.append("Block options must be %s" % ", ".join(BLOCK_OPTIONS))
    if ac.HUMAN not in _names(_field(spec, "Instance")):
        probs.append("Instance has no option 'human'")
    for name in ("Status", "Instance", "Role", "Kind", "Priority", "Agenda", "Block"):
        if _field(spec, name) is None:
            probs.append("no field %s" % name)
    return probs


def compare_live(spec, live):
    """``(problems, notes)`` of the live Project's fields against the spec: a field or an
    option the spec wants and the Project lacks is a problem; extra ones are notes."""
    got = {}
    for f in live.get("fields", []):
        got[f["name"]] = [o["name"] if isinstance(o, dict) else str(o)
                          for o in f.get("options") or []]
    probs, notes = [], []
    for f in spec["fields"]:
        if f["name"] not in got:
            probs.append("Project has no field %s" % f["name"])
            continue
        want = _names(f)
        probs += ["Project field %s lacks option %r" % (f["name"], w)
                  for w in want if w not in got[f["name"]]]
        notes += ["Project field %s has an extra option %r" % (f["name"], x)
                  for x in got[f["name"]] if want and x not in want]
    return probs, notes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--workspace", help="workspace.json (the Instance options)")
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--live", help="the live Project's fields (JSON): report what is missing")
    a = ap.parse_args(argv)
    try:
        ws = ac.load_workspace(a.workspace)
        instances = sorted(ws["instances"])
    except ac.ConfigError:
        instances = []
    spec = build(instances)
    rc = 0
    if a.check:
        probs = check(spec)
        for p in probs:
            print(p)
        print("spec covers %d kinds, %d statuses: %s" % (
            len(ac.TICKET_KINDS), len(ac.TICKET_STATUSES), "ok" if not probs else "NOT ok"))
        rc = 1 if probs else 0
    if a.live:
        with open(a.live, encoding="utf-8") as fh:
            probs, notes = compare_live(spec, json.load(fh))
        for p in probs:
            print("missing: " + p)
        for n in notes:
            print("note: " + n)
        print("%d missing" % len(probs))
        rc = rc or (1 if probs else 0)
    if a.out or not (a.check or a.live):
        text = json.dumps(spec, ensure_ascii=False, indent=1) + "\n"
        if a.out:
            with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
        else:
            sys.stdout.write(text)
    return rc


if __name__ == "__main__":
    sys.exit(main())
