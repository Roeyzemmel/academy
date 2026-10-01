"""board_verify.py -- compare GitHub issues (or a manifest) with the file board.

    py board_verify.py [--board DIR] --manifest manifest.json
    py board_verify.py [--board DIR] --issues dump.json

``dump.json`` is a list of ``{"issue": {number,title,body,labels,state,state_reason},
"comments": [body, ...]}`` collected from GitHub (the runbook fetches it with the github
MCP). Every ticket is decoded from its issue and rendered; the text must equal the file
on the board byte for byte, and the issue must be consistent (labels, role, state).
Exit 1 on any drift. Placeholders are checked to be closed.

Relations (sub-issue ``parent``, dependency ``waits_on``): a manifest is checked completely
(each issue's ``parent`` / ``waits_on`` and the manifest's ``relations`` list must equal what
the ticket files give). An issues dump is checked only when its records carry ``parent`` /
``waits_on`` (the runbook adds ``parent`` from the native links; the github MCP cannot read
dependencies, so its dumps leave ``waits_on`` out). Each key is checked only where a record
has it; without it that relation is **unverified** and ``main`` says so.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402

KEYS = ("number", "title", "body", "labels", "state", "state_reason")


def from_manifest(m):
    return [{"issue": {k: i[k] for k in KEYS}, "comments": i["comments"],
             "parent": i.get("parent"), "waits_on": i.get("waits_on", [])}
            for i in m["issues"]]


def unverified_relations(records, key=None):
    """Numbers of the records that carry no relation data (their links are not checked).

    With ``key`` (``parent`` or ``waits_on``), the records that lack that one key: a dump
    from the github MCP has ``parent`` but cannot read dependencies, so ``waits_on`` is
    checked only where the dump has it."""
    keys = (key,) if key else ("parent", "waits_on")
    return [r["issue"]["number"] for r in records
            if all(k not in r for k in keys)
            and "placeholder" not in bc.label_names(r["issue"].get("labels"))]


def _num(ref):
    """An issue number from a relation reference: a dump gives numbers (``get_parent``),
    a manifest gives ticket ids (``T-0055``)."""
    if not ref:
        return None
    return ref if isinstance(ref, int) else bc.ticket_number(ref)


def verify(board, records, relations=None):
    """List of drift messages (empty when the issues reproduce the board exactly).

    ``relations`` is the manifest's relation list, when there is one."""
    files = {}
    for path, meta, body in bd.iter_tickets(board):
        if meta is not None:
            files[bc.ticket_number(meta["id"])] = path
    seen, out = set(), []
    for r in records:
        iss = r["issue"]
        n = iss["number"]
        seen.add(n)
        if "placeholder" in bc.label_names(iss.get("labels")):
            if n in files:
                out.append("#%d is a placeholder but T-%04d exists on the board" % (n, n))
            elif iss.get("state") != "closed":
                out.append("#%d placeholder is not closed" % n)
            continue
        if n not in files:
            out.append("#%d has no ticket on the board" % n)
            continue
        probs = bc.validate_issue(iss, r["comments"])
        out.extend("#%d: %s" % (n, p) for p in probs)
        try:
            meta, body = bc.decode(iss, r["comments"])
        except (bc.CodecError, ValueError) as e:
            out.append("#%d: %s" % (n, e))
            continue
        with open(files[n], encoding="utf-8", newline="") as fh:
            if fh.read() != bc.render(meta, body):
                out.append("#%d: rendered ticket differs from %s" % (n, os.path.basename(files[n])))
        if "assignees" in iss and bool(iss["assignees"]) != (meta["to"] == ac.HUMAN):
            out.append("#%d: assignees are %s, the ticket is addressed to %s"
                       % (n, iss["assignees"], meta["to"]))
        if "parent" in r or "waits_on" in r:
            want = bc.encode(meta, body)
            if "parent" in r and _num(r.get("parent")) != _num(want["parent"]):
                out.append("#%d: parent is %s, the ticket says %s"
                           % (n, r.get("parent"), want["parent"]))
            if "waits_on" in r and (sorted(map(_num, r.get("waits_on") or []))
                                    != sorted(map(_num, want["waits_on"]))):
                out.append("#%d: waits_on is %s, the ticket says %s"
                           % (n, r.get("waits_on"), want["waits_on"]))
    for n in sorted(set(files) - seen):
        out.append("T-%04d is on the board but has no issue" % n)
    if relations is not None:
        issues = [bc.encode(m, b) for _p, m, b in bd.iter_tickets(board) if m is not None]
        key = lambda r: json.dumps(r, sort_keys=True)  # noqa: E731
        have, want = sorted(map(key, relations)), sorted(map(key, bc.relations(issues)))
        out.extend("relation %s is on the ticket files but not in the manifest" % w
                   for w in want if w not in have)
        out.extend("relation %s is in the manifest but not on the ticket files" % h
                   for h in have if h not in want)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--board")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--manifest")
    src.add_argument("--issues")
    a = ap.parse_args(argv)
    with open(a.manifest or a.issues, encoding="utf-8") as fh:
        data = json.load(fh)
    recs = from_manifest(data) if a.manifest else data
    drift = verify(bd.resolve_board(a.board), recs,
                   data.get("relations", []) if a.manifest else None)
    for d in drift:
        print(d)
    for key in ("parent", "waits_on"):
        skipped = unverified_relations(recs, key)
        if skipped:
            print("note: %s of %d issue(s) is unverified: the dump carries no %s data"
                  % (key, len(skipped), key))
    print("%d issue(s) checked, %d drift" % (len(recs), len(drift)))
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
