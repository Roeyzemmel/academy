"""inbox.py -- which of the lab's tickets to take this run, and who takes each.

Usage::

    py inbox.py [--home DIR] [--board DIR] [--json] [--all]

Takes the tickets addressed to this Scientist instance whose status is ``open`` or
``accepted``, in the protocol's order (priority, then id; the agenda position
belongs to an Author's agenda and is not known here), and keeps the first
``budget.itemsPerRun`` (at most 3). ``--all`` lists them all without the cut.

Each row carries the route, decided here and not by the model:

==================  ============================================================
kind                route
==================  ============================================================
experiment          experimenter (a new experiment and its report)
test                experimenter, falsifier first (a conjectured generalization)
code                developer, then test-engineer reviews the diff; a title
                    beginning "Upstream:" goes to upstream-contributor (drafts only)
question            experimenter (answers from the lab's records; no new compute)
other               human (Roey says what it is)
anything else       reject: not the lab's work (names the usual receiver)
==================  ============================================================

The routed agent runs on its agent file's model. A ticket's ``budget.max_model``, if
present, is an advisory note from the sender and never blocks a route (T-0071); the
ticket's limit is ``budget.runs`` (academy references/budget.md rules 6 and 7). Exit 0
with rows, 1 with nothing to take, 2 on error.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _common as c  # noqa: E402
from _common import ac  # noqa: E402

TAKE = ("open", "accepted")
PRIORITY = {"high": 0, "normal": 1, "low": 2}
ROUTES = {
    "experiment": ("experimenter", "design, header approval, script, queue, report"),
    "test": ("experimenter", "test the falsifier first; the report goes back to the sender"),
    "code": ("developer", "test-first in a worktree; test-engineer reviews the diff"),
    "question": ("experimenter", "answer from the lab's records and results; no new compute"),
    "other": ("human", "Roey says what it is"),
}
ELSEWHERE = {"verify": "expert", "cite": "expert", "lookup": "expert", "referee": "expert",
             "prove": "researcher", "review-experiment": "researcher",
             "generalize": "researcher", "notation": "expert or author",
             "build": "author", "figure": "author", "decision": "human or claim-keeper"}


def route(meta):
    kind = meta.get("kind") or "other"
    if kind == "code" and str(meta.get("title") or "").lower().startswith("upstream:"):
        row = {"route": "upstream-contributor",
               "how": "draft the reproducer, issue text and patch branch; Roey files it"}
    elif kind in ROUTES:
        agent, how = ROUTES[kind]
        row = {"route": agent, "how": how}
    else:
        row = {"route": "reject", "how": "not the lab's work; usually for %s"
               % ELSEWHERE.get(kind, "another instance")}
    return row


def select(board, instance, limit=3, take_all=False):
    folder = os.path.join(board, instance)
    rows = []
    if os.path.isdir(folder):
        for f in sorted(os.listdir(folder)):
            if not (f.startswith("T-") and f.endswith(".md")):
                continue
            try:
                with open(os.path.join(folder, f), "r", encoding="utf-8") as fh:
                    meta = ac.read_frontmatter(fh.read())[0]
            except (OSError, ac.AcademyError, UnicodeDecodeError):
                continue
            if meta.get("to") != instance or meta.get("status") not in TAKE:
                continue
            row = {"id": meta.get("id"), "kind": meta.get("kind"), "title": meta.get("title"),
                   "status": meta.get("status"), "priority": meta.get("priority") or "normal",
                   "from": meta.get("from"), "budget": meta.get("budget")}
            row.update(route(meta))
            rows.append(row)
    rows.sort(key=lambda r: (PRIORITY.get(r["priority"], 1),
                             int(str(r["id"] or "T-0").split("-")[1] or 0)))
    total = len(rows)
    return (rows if take_all else rows[:max(1, min(int(limit), 3))]), total


def main(argv=None):
    ap = argparse.ArgumentParser(prog="inbox.py", description=__doc__.split("\n")[0])
    ap.add_argument("--home"); ap.add_argument("--board"); ap.add_argument("--workspace")
    ap.add_argument("--json", action="store_true"); ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    try:
        lab = c.resolve_lab(a.home, os.getcwd(), a.workspace)
        board = a.board or ac.load_workspace(a.workspace)["board"]
        limit = (lab["cfg"].get("budget") or {}).get("itemsPerRun", 3)
        rows, total = select(board, lab["instance"], limit, a.all)
    except ac.AcademyError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps({"instance": lab["instance"], "take": rows, "waiting": total,
                          "remaining": max(0, total - len(rows))}, indent=1,
                         ensure_ascii=False))
    else:
        for r in rows:
            print("%s  %-8s %-17s -> %-13s %s" % (
                r["id"], r["priority"], r["kind"], r["route"], r["title"]))
        print("%d taken, %d remaining" % (len(rows), max(0, total - len(rows))))
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
