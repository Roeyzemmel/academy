"""inbox.py -- the Researcher instance's inbox: which tickets to take, and where each goes.

docs/protocol.md section 4 (execution) and references/budget.md: the receiver's
``open`` and ``accepted`` tickets, ordered by priority, then agenda position, then id;
at most ``budget.itemsPerRun`` (never more than 3), run serially. This script only
reads the board; the skill moves the tickets (``board.py transition``) and runs them.

Usage:

    py inbox.py [--instance researcher@x] [--n N] [--all] [--json]

``--all`` lists every open/accepted/in-progress/blocked ticket without taking any.
Without ``--instance`` the instance is the Researcher home containing the cwd.

Routing by ticket kind (the skill or agent that handles it):

    prove               /researcher:prove
    review-experiment   /researcher:review-experiment  (or /researcher:settle when the
                        report lists candidate counterexamples)
    generalize          /researcher:generalize
    decision            claim-keeper (a status proposal from claims_propose_status)
    question            /researcher:explore (as a question) or lead-researcher
    research            lead-researcher
    final_to beyond the Researcher (whatever the kind): experiment-spec (toward the
                        Scientist) or lit-request (toward the Expert or the Author)
    everything else     lead-researcher, which may reject with a reason

Agenda position: a ticket's ``agenda`` field names an Author agenda entry; tickets with
one come before tickets without, in id order (the Author's own ordering is not visible
from here).
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import _researcher as rs  # noqa: E402

ROUTES = {
    "prove": "/researcher:prove",
    "review-experiment": "/researcher:review-experiment",
    "generalize": "/researcher:generalize",
    "decision": "claim-keeper",
    "question": "/researcher:explore",
    "research": "lead-researcher",
}
#: a ticket whose final_to lies beyond the Researcher goes to the relay of its direction
RELAYS = {"scientist": "experiment-spec", "expert": "lit-request", "author": "lit-request"}
DEFAULT_ROUTE = "lead-researcher"
TAKE = ("open", "accepted")
SHOW = ("open", "accepted", "in-progress", "blocked")
PRIORITY = {"high": 0, "normal": 1, "low": 2}
RE_FILE = re.compile(r"^T-\d{4,}-.*\.md$")


def tickets_for(board, instance, statuses):
    folder = os.path.join(board, instance)
    out = []
    if not os.path.isdir(folder):
        return out
    for f in sorted(os.listdir(folder)):
        if not RE_FILE.match(f):
            continue
        path = os.path.join(folder, f)
        try:
            meta, _ = ac.read_frontmatter(rs.read_text(path) or "")
        except ac.AcademyError:
            continue
        if meta.get("status") in statuses:
            meta = dict(meta)
            meta["path"] = path.replace("\\", "/")
            out.append(meta)
    return out


def order_key(t):
    num = int(str(t.get("id", "T-0")).split("-")[1] or 0)
    return (PRIORITY.get(t.get("priority"), 1), 0 if t.get("agenda") else 1, num)


def route(t):
    ft = t.get("final_to")
    final = ac.role_of(ft) if ft and ft not in ac.ROLES else ft
    if final and final != "researcher" and final in RELAYS:
        return RELAYS[final]
    return ROUTES.get(t.get("kind"), DEFAULT_ROUTE)


def take(tickets, n):
    return sorted(tickets, key=order_key)[:n]


def resolve_instance(instance=None, cwd=None):
    if instance:
        return instance, None
    home, cfg, inst = rs.researcher_home(cwd or os.getcwd())
    if not inst:
        raise ac.AcademyError("not in a Researcher home; give --instance")
    return inst, cfg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--instance")
    ap.add_argument("--board")
    ap.add_argument("--n", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        inst, cfg = resolve_instance(args.instance)
        board = args.board or ac.load_workspace()["board"]
        limit = min(int(((cfg or {}).get("budget") or {}).get("itemsPerRun", 3)), 3)
        n = max(1, min(args.n or limit, limit))
        pool = tickets_for(board, inst, SHOW if args.all else TAKE)
        chosen = sorted(pool, key=order_key) if args.all else take(pool, n)
        rows = [{"id": t["id"], "kind": t.get("kind"), "status": t.get("status"),
                 "priority": t.get("priority"), "from": t.get("from"),
                 "title": t.get("title"), "route": route(t),
                 "budget": t.get("budget"), "path": t["path"]} for t in chosen]
        left = max(0, len(pool) - len(rows)) if not args.all else 0
        if args.json:
            print(json.dumps({"instance": inst, "take": rows, "remaining": left},
                             ensure_ascii=False, indent=1))
        else:
            for r in rows:
                print("%s  %-17s %-11s %-6s from %-18s -> %-30s %s"
                      % (r["id"], r["kind"], r["status"], r["priority"], r["from"],
                         r["route"], r["title"]))
            if not rows:
                print("(inbox of %s is empty)" % inst)
            elif left:
                print("%d more ticket(s) wait for the next run" % left)
        return 0 if rows else 1
    except (ac.AcademyError, OSError) as exc:
        sys.stderr.write("inbox.py: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
