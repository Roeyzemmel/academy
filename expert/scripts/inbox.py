"""inbox.py -- the Expert's inbox: which tickets to take this run, and where each goes.

    py inbox.py [--instance expert@main] [--limit N] [--json]

Lists the tickets addressed to the Expert instance with status ``open`` or
``accepted`` (docs/protocol.md section 4, "Execution"), and the ``blocked`` relay
parents ready for their return leg (``final_to`` routes them to a relay, ``waiting_on``
holds only ticket ids, and every child is ``delivered`` or terminal; the route then
carries ``"return": true``), ordered by priority then id
(``board.list_tickets``; agenda positions are an Author notion and are not known
here), takes at most ``--limit`` (default: the home's ``budget.itemsPerRun``, never
more than 3) and gives each its route by ticket kind:

| kind | route |
|---|---|
| verify | skill ``expert:verify`` (review-chair; two rigor-reviewer runs) |
| cite | skill ``expert:cite`` (librarian) |
| lookup, question | agent ``clerk``; a miss escalates to ``librarian`` |
| referee | skill ``expert:referee`` |
| notation | skill ``expert:domain`` (librarian) |
| any kind with ``final_to`` beyond the Expert | agent ``research-intake`` (toward the Researcher or Scientist) or ``paper-liaison`` (toward an Author): a relay |
| research without ``final_to``, or with ``final_to`` the Expert | agent ``research-intake``, read as ``final_to: researcher`` |
| note | ``human``: a note is for the Author; block with ``waiting_on [human]`` |
| decision, other | ``human``: block the ticket with ``waiting_on: [human]`` |
| any other kind | ``reject``: not Expert work; the reason names the role it belongs to and, for Researcher or Scientist work, says to ask through a ``research`` ticket to the Expert with ``final_to`` |

The skill follows the route; this script decides nothing else and writes nothing.
Exit 0 with a plan (possibly empty), 2 on an error.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402

ROUTES = {
    "verify": ("skill", "expert:verify", "review-chair runs the pair and applies the table"),
    "cite": ("skill", "expert:cite", "librarian: bib entry, card, index row"),
    "lookup": ("agent", "clerk", "quick answer from hot.md and the library; a miss escalates"),
    "question": ("agent", "clerk", "the clerk first; a miss escalates to the librarian"),
    "referee": ("skill", "expert:referee", "cold whole-paper read, landed as a packet"),
    "notation": ("skill", "expert:domain", "librarian edits the domain pack"),
    "research": ("agent", "research-intake",
                 "relay toward the Researcher: no final_to (or final_to the Expert) is "
                 "read as final_to researcher"),
    "note": ("human", "human", "a note is for the Author; block with waiting_on [human]"),
    "decision": ("human", "human", "only the human decides: block with waiting_on [human]"),
    "other": ("human", "human", "no Expert route: block with waiting_on [human]"),
}
BELONGS = {
    "prove": "researcher", "review-experiment": "researcher", "generalize": "researcher",
    "experiment": "scientist", "test": "scientist", "code": "scientist",
    "build": "author", "figure": "author",
}
TAKE = ("open", "accepted")


#: relay tickets (final_to beyond the Expert) go to the relay of their crossing
RELAYS = {"researcher": "research-intake", "scientist": "research-intake",
          "author": "paper-liaison"}


def _final_role(meta):
    ft = meta.get("final_to")
    return ac.role_of(ft) if ft and ft not in ac.ROLES else ft


def route(meta):
    final = _final_role(meta)
    if final and final != "expert" and final in RELAYS:
        return {"how": "agent", "target": RELAYS[final],
                "why": "relay toward %s: check, sharpen, forward (final_to)" % final}
    kind = meta.get("kind") or "other"
    if kind in ROUTES:
        how, target, why = ROUTES[kind]
        return {"how": how, "target": target, "why": why}
    role = BELONGS.get(kind, "another role")
    why = "a %s ticket is %s work, not Expert work; reject it with that reason" % (kind, role)
    if role in ("researcher", "scientist"):
        why += ("; ask through a research ticket to the Expert with final_to %s" % role)
    return {"how": "reject", "target": None, "why": why}


def _status_of(board):
    def status(tid):
        path = ac.find_ticket(board, tid)
        if not path:
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return ac.read_frontmatter(fh.read())[0].get("status")
    return status


def is_return_leg(board, meta):
    """A blocked relay parent whose children are all delivered or terminal."""
    return (route(meta)["target"] in RELAYS.values()
            and ac.relay_return_ready(meta, _status_of(board)))


def plan(board, instance, limit):
    boardlib = ex.base_script("board")
    tickets = [t for t in boardlib.list_tickets(board, to=instance)
               if t.get("status") in TAKE
               or (t.get("status") == "blocked" and is_return_leg(board, t))]
    out = []
    for t in tickets[:limit]:
        r = route(t)
        if t.get("status") == "blocked":
            r["return"] = True
            r["why"] = ("return leg: the child is back; close it and deliver this "
                        "ticket with a result pointing at it")
        out.append({"id": t.get("id"), "kind": t.get("kind"), "status": t.get("status"),
                    "priority": t.get("priority"), "title": t.get("title"),
                    "from": t.get("from"), "budget": t.get("budget"),
                    "refs": t.get("refs") or [], "route": r,
                    "path": str(t.get("_path", "")).replace("\\", "/")})
    return {"instance": instance, "limit": limit, "waiting": len(tickets),
            "take": out, "left": max(0, len(tickets) - limit)}


def main(argv=None):
    ex.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--instance")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--board")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    ws = ex.load_workspace_or_none()
    if not ws:
        sys.stderr.write("inbox: workspace.json not found\n")
        return 2
    home = ac.find_home(os.getcwd())
    instance = args.instance
    if not instance and home:
        instance = ex.expert_instance_for_home(ws, home)
    if not instance:
        names = ex.expert_instances(ws)
        instance = names[0] if len(names) == 1 else None
    if not instance or instance not in ws["instances"]:
        sys.stderr.write("inbox: name the Expert instance (--instance)\n")
        return 2
    limit = args.limit
    if not limit:
        cfg = ex.expert_config(ws["instances"][instance]["home"])
        limit = ((cfg or {}).get("budget") or {}).get("itemsPerRun") or 3
    limit = max(1, min(int(limit), 3))
    res = plan(os.path.abspath(args.board or ws["board"]), instance, limit)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    print("%s: %d ticket(s) waiting; taking %d (limit %d)"
          % (instance, res["waiting"], len(res["take"]), limit))
    for t in res["take"]:
        r = t["route"]
        print("%s [%s, %s, %s] %s -> %s %s: %s" % (t["id"], t["kind"], t["status"],
                                                  t["priority"], t["title"], r["how"],
                                                  r["target"] or "", r["why"]))
    if res["left"]:
        print("%d more wait for the next run" % res["left"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
