"""cowork.py -- the plan files and state of /academy:cowork (and the campaigns' state).

    py cowork.py new SLUG --goal "..." [--agents N] [--board DIR]   open the plan file
    py cowork.py status SLUG [--board DIR] [--json]                 its state, from tickets
    py cowork.py list [--kind cowork|campaign|all] [--board DIR] [--json]
                                                                    active workplans

A cowork's plan is ``<board>/cowork/<slug>.md`` (template ``templates/cowork-plan.md``):
the goal, the seeding, the task table with ticket ids, the decisions log and a running
log. Its tickets carry ``cowork: <slug>`` (``board.py new --cowork``, ``tickets_create``
field ``cowork``). The state (``ACTIVE``, ``WAITING``, ``PAUSE``, ``DONE``) is computed
from those tickets by ``academy/lib/workplan.py``, never kept by hand; a cowork has no
leading instance, so every open ticket waits for its role's next actor.

``list`` shows every active workplan: a cowork whose plan file is not ``status: closed``
or that has an open tagged ticket, and every campaign with an open tagged ticket. The
desk shows it (``/academy:desk``).

Exit codes: 0 success, 1 nothing found, 2 error.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PLUGIN, "lib"))
sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import workplan as wp  # noqa: E402

TEMPLATE = os.path.join(PLUGIN, "templates", "cowork-plan.md")


def _store(board=None, workspace=None):
    if board:
        return ac.FileBoardStore(board)
    return ac.open_store(ac.load_workspace(workspace))


def _metas(store):
    return [m for _r, m in ac.as_store(store).iter_meta()]


def new_plan(board_dir, slug, goal, agents=1, date=None):
    """Write the plan file from the template; returns its path. Refuses an existing one."""
    prob = wp.check_tag("cowork", slug)
    if prob:
        raise ac.AcademyError(prob)
    path = wp.plan_path(board_dir, slug)
    if os.path.exists(path):
        raise ac.AcademyError("%s exists: resume it (/academy:cowork %s --resume)"
                              % (path, slug))
    with open(TEMPLATE, encoding="utf-8") as fh:
        text = fh.read()
    for k, v in (("slug", slug), ("goal", " ".join((goal or "").split()) or "(to state)"),
                 ("date", date or ac.today()), ("agents", str(agents))):
        text = text.replace("{{%s}}" % k, v)
    ac.atomic_write(path, text)
    return path


def status(store, slug):
    bd = ac.board_dir(store)
    st = wp.state(_metas(store), "cowork", slug)
    path = wp.plan_path(bd, slug)
    st["plan"] = path.replace("\\", "/") if os.path.isfile(path) else None
    if st["plan"]:
        with open(path, encoding="utf-8") as fh:
            st["plan_status"] = wp.plan_status(fh.read())
    return st


def active(store, kind="all"):
    """``[{kind, value, state, open, plan}]`` of the active workplans."""
    metas = _metas(store)
    rows = []
    kinds = wp.KINDS if kind == "all" else (kind,)
    if "cowork" in kinds:
        bd = ac.board_dir(store)
        slugs = set(wp.active(metas, "cowork"))
        for slug in wp.plans(bd):
            with open(wp.plan_path(bd, slug), encoding="utf-8") as fh:
                if wp.plan_status(fh.read()) != "closed":
                    slugs.add(slug)
        for slug in sorted(slugs):
            st = status(store, slug)
            rows.append({"kind": "cowork", "value": slug, "state": st["state"],
                         "open": st["decision"] + st["out"] + st["own"] + st["dead"],
                         "plan": st["plan"]})
    if "campaign" in kinds:
        for target, ids in wp.active(metas, "campaign").items():
            st = wp.state(metas, "campaign", target)
            rows.append({"kind": "campaign", "value": target, "state": st["state"],
                         "open": ids, "plan": None})
    return rows


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--board")
    ap.add_argument("--workspace")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new")
    p.add_argument("slug")
    p.add_argument("--goal", default="")
    p.add_argument("--agents", type=int, default=1)
    p = sub.add_parser("status")
    p.add_argument("slug")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("list")
    p.add_argument("--kind", choices=("cowork", "campaign", "all"), default="all")
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        store = _store(a.board, a.workspace)
        if a.cmd == "new":
            wp.caps("cowork", agents=a.agents)
            print(new_plan(ac.board_dir(store), a.slug, a.goal, a.agents).replace("\\", "/"))
            return 0
        if a.cmd == "status":
            st = status(store, a.slug)
            if a.json:
                print(json.dumps(st, indent=1, ensure_ascii=False))
            else:
                print("cowork %s: %s  (plan %s)" % (a.slug, st["state"], st["plan"] or "none"))
                for k in ("decision", "out", "own", "dead", "done"):
                    if st[k]:
                        print("  %-8s %s" % (k, ", ".join(st[k])))
            return 0 if (st["plan"] or sum(st["counts"].values())) else 1
        rows = active(store, a.kind)
        if a.json:
            print(json.dumps(rows, indent=1, ensure_ascii=False))
        else:
            for r in rows:
                print("%-8s %-32s %-8s open: %s" % (r["kind"], r["value"], r["state"],
                                                    ", ".join(r["open"]) or "-"))
            if not rows:
                print("(no active campaign or cowork)")
        return 0 if rows else 1
    except (ac.AcademyError, wp.WorkplanError, OSError) as exc:
        sys.stderr.write("cowork: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
