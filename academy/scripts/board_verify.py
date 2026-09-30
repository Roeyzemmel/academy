"""board_verify.py -- compare GitHub issues (or a manifest) with the file board.

    py board_verify.py [--board DIR] --manifest manifest.json
    py board_verify.py [--board DIR] --issues dump.json

``dump.json`` is a list of ``{"issue": {number,title,body,labels,state,state_reason},
"comments": [body, ...]}`` collected from GitHub (the runbook fetches it with the github
MCP). Every ticket is decoded from its issue and rendered; the text must equal the file
on the board byte for byte, and the issue must be consistent (labels, role, state).
Exit 1 on any drift. Placeholders are checked to be closed.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, HERE)

import board as bd  # noqa: E402
import board_codec as bc  # noqa: E402

KEYS = ("number", "title", "body", "labels", "state", "state_reason")


def from_manifest(m):
    return [{"issue": {k: i[k] for k in KEYS}, "comments": i["comments"]} for i in m["issues"]]


def verify(board, records):
    """List of drift messages (empty when the issues reproduce the board exactly)."""
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
    for n in sorted(set(files) - seen):
        out.append("T-%04d is on the board but has no issue" % n)
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
    drift = verify(bd.resolve_board(a.board), recs)
    for d in drift:
        print(d)
    print("%d issue(s) checked, %d drift" % (len(recs), len(drift)))
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
