"""board_export.py -- file board -> GitHub issue manifest (docs/github-board.md).

    py board_export.py [--board DIR] [--repo OWNER/NAME] [--out manifest.json] [--summary]

Writes a deterministic manifest of everything a transport must create so that issue
number == ticket number: one entry per number 1..max (ids that were never used become
closed 'not planned' placeholders), the label set, and the relations to apply once every
issue exists: ``sub_issue`` (a ticket and its ``parent``) and ``dependency`` (a ticket and
each ticket in its ``waiting_on``). Nothing is sent anywhere; the migration
runbook (/academy:board-migrate) executes the manifest through the github MCP, or
``board_project.py``/a token does. Packets are not exported (they stay files).
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

#: label colour and description by prefix (``board_codec.LABEL_PREFIXES`` and the placeholder)
COLORS = dict(zip(bc.LABEL_PREFIXES + (bc.PLACEHOLDER,),
                  ("1d76db", "5319e7", "bfd4f2", "fbca04", "d93f0b", "0e8a16", "b60205",
                   "cccccc")))
DESCRIPTIONS = dict(zip(bc.LABEL_PREFIXES,
                        ("ticket status", "addressee instance", "sender instance", "ticket kind",
                         "ticket priority", "addressee role (derived from to)",
                         "dead-route block (derived from status blocked + blocked_by + "
                         "reopen_if)")))


def build(board, repo=""):
    tickets, unreadable = {}, []
    for path, meta, body in bd.iter_tickets(board):
        if meta is None:
            unreadable.append(path)
            continue
        tickets[bc.ticket_number(meta["id"])] = (meta, body)
    if not tickets:
        raise SystemExit("no tickets found under %s" % board)
    top = max(tickets)
    issues, gaps = [], []
    for n in range(1, top + 1):
        if n in tickets:
            issues.append(bc.encode(*tickets[n]))
        else:
            gaps.append(n)
            issues.append(bc.placeholder(n))
    labels = sorted({l for i in issues for l in i["labels"]})
    label_defs = [{"name": l, "color": COLORS.get(bc.label_prefix(l), "ededed"),
                   "description": DESCRIPTIONS.get(bc.label_prefix(l), "")} for l in labels]
    relations = bc.relations(issues)
    problems = []
    for i in issues:
        if len(i["body"]) > bc.MAX_BODY:
            problems.append("#%d body is %d characters" % (i["number"], len(i["body"])))
        for c in i["comments"]:
            if len(c) > bc.MAX_BODY:
                problems.append("#%d has an oversized thread comment" % i["number"])
    return {"schema": 1, "repo": repo, "labels": label_defs, "issues": issues,
            "relations": relations,
            "summary": {"tickets": len(tickets), "placeholders": len(gaps), "gaps": gaps,
                        "comments": sum(len(i["comments"]) for i in issues),
                        "closed": sum(1 for i in issues if i["state"] == "closed"),
                        "relations": len(relations), "labels": len(labels),
                        "unreadable": unreadable, "problems": problems}}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--board")
    ap.add_argument("--repo", default="")
    ap.add_argument("--out")
    ap.add_argument("--summary", action="store_true", help="print the counts only")
    a = ap.parse_args(argv)
    m = build(bd.resolve_board(a.board), a.repo)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(m, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    if a.summary or not a.out:
        json.dump(m["summary"], sys.stdout, indent=1)
        sys.stdout.write("\n")
    return 1 if m["summary"]["unreadable"] or m["summary"]["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
