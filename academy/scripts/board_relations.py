"""board_relations.py -- mirror the tickets' links into GitHub's native relations.

    py board_relations.py plan  [--workspace F] [--repo OWNER/NAME] [--ids T-0001,T-0002] [--json]
    py board_relations.py apply [--workspace F] [--repo OWNER/NAME] [--ids ...] [--dry-run] [--json]

The ticket's meta line is the source of truth; the native relations follow it (docs/github-board.md,
"Native relations"):

* ``parent: T-a`` on T-b          -> issue b is a sub-issue of issue a;
* ``waiting_on`` of T-b holds T-a -> issue b is blocked by issue a (``blocks`` is the
  bookkeeping mirror of ``waiting_on`` and is not read: it is never pruned).

Not mirrored: ``waiting_on`` tokens that are not ticket ids (``human``, an instance) and the
dead-route ``blocked_by`` (a ticket or registry id the route *ended at*, not something whose
closing frees the ticket; it stays in the meta line, the ``route:dead`` label and the Project's
Block field). A link whose target is not a ticket on the board (a missing id, a placeholder) is
reported as unresolved and skipped; a native link to an issue that is not a board ticket (an
ordinary issue, another repository) is kept, never removed.

``plan`` reads the issues (the listing's ``parent_issue_url`` and ``issue_dependencies_summary``
spare a read per issue where GitHub gives them) and the native links, and prints the diff;
it only reads. ``apply`` writes the diff through the transport, removals first; a failed write
is reported and the rest go on, and a rerun recomputes the diff, so it resumes where it stopped
and a second run is a no-op. A repository without sub-issues or dependencies (404/410 on the
probe) is reported as "not available" and that kind is left alone. ``--ids`` limits the tickets
whose links are synced. ``--repo`` uses ``gh`` directly; otherwise the board of workspace.json
(``board.backend`` github, through ``board.transport``).

Exit 0: in step, everything applied, or the relations are not available; 1: ``apply`` had
failures; 2: an error. This is a sync, run by hand; ticket writes never depend on it.
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
import board_store as bs  # noqa: E402

KINDS = ("sub_issues", "dependencies")
#: apply order: removals first (a moved link never doubles up), then additions
ORDER = ("remove_blocked_by", "remove_sub_issue", "add_sub_issue", "add_blocked_by")


def tid(n):
    return ac.format_id("T", n)


def _is_tid(x):
    return bool(ac.RE_TICKET_ID.match(str(x or "")))


def _url_ref(url):
    """``{"number", "repo"}`` of an API issue URL (``.../repos/O/N/issues/7``)."""
    if not url or "/repos/" not in url or "/issues/" not in url:
        return None
    repo, _, num = url.split("/repos/", 1)[1].rpartition("/issues/")
    return {"number": int(num), "repo": repo} if num.isdigit() else None


class Board(object):
    """The issues of the repository and the tickets among them."""

    def __init__(self, t, repo=""):
        self.t = t
        self.repo = repo or getattr(t, "repo", "") or ""
        self.issues = {i["number"]: i for i in bs.pages(t.list_issues, state="all")}
        self.tickets = {}
        self.undecodable = []
        for n, issue in sorted(self.issues.items()):
            if not bs.GithubBoardStore._is_ticket(issue) or not bc.is_board_issue(issue):
                continue
            try:
                self.tickets[n] = bc.decode(issue, ())[0]
            except (bc.CodecError, ValueError):
                self.undecodable.append(n)

    def local(self, ref):
        """The issue number of ``ref`` when it is a ticket of this board, else None."""
        if not ref:
            return None
        if ref.get("repo") and self.repo and ref["repo"].lower() != self.repo.lower():
            return None
        return ref["number"] if ref["number"] in self.tickets else None


def wanted(board, n):
    """``(parent, blockers, unresolved, tokens)`` the meta line of ticket ``n`` asks for."""
    meta, unresolved = board.tickets[n], []

    def target(field, x):
        if not _is_tid(x):
            return None
        m = bc.ticket_number(x)
        if m == n:
            unresolved.append({"issue": n, "field": field, "target": str(x),
                               "why": "the ticket itself"})
            return None
        if m not in board.tickets:
            unresolved.append({"issue": n, "field": field, "target": str(x),
                               "why": "not a ticket on the board"})
            return None
        return m

    p = meta.get("parent")
    parent = target("parent", p) if p else None
    if p and not _is_tid(p):
        unresolved.append({"issue": n, "field": "parent", "target": str(p),
                           "why": "not a ticket id"})
    blockers, tokens = [], 0
    for w in meta.get("waiting_on") or []:
        if not _is_tid(w):
            tokens += 1                     # human, an instance: no native form
            continue
        b = target("waiting_on", w)
        if b is not None and b not in blockers:
            blockers.append(b)
    return parent, sorted(blockers), unresolved, tokens


def _reader(t, *names):
    for name in names:
        if hasattr(t, name):
            return name
    return None


def availability(t, board, scope):
    """``{kind: True | "why not"}``: probed on the first ticket in scope."""
    out = {}
    for kind, names in (("sub_issues", ("parent_ref", "get_parent")),
                        ("dependencies", ("blocker_refs", "list_dependencies"))):
        out[kind] = True if _reader(t, *names) else "the transport cannot read them"
    if scope and hasattr(t, "relations_available"):
        got = t.relations_available(scope[0])
        for kind in KINDS:
            if out[kind] is True and not got.get(kind, True):
                out[kind] = "not available on this repository"
    return out


def native_parent(t, board, n):
    issue = board.issues.get(n) or {}
    # the REST listing says it, with no read: it carries ``sub_issues_summary`` on every
    # issue and ``parent_issue_url`` only on one that has a parent
    if "parent_issue_url" in issue or "sub_issues_summary" in issue:
        return _url_ref(issue.get("parent_issue_url"))
    if hasattr(t, "parent_ref"):
        return t.parent_ref(n)
    p = t.get_parent(n)
    return {"number": p, "repo": None} if p else None


def native_blockers(t, board, n):
    summary = (board.issues.get(n) or {}).get("issue_dependencies_summary")
    if isinstance(summary, dict):
        k = summary.get("total_blocked_by", summary.get("blocked_by"))
        if k == 0:
            return []
    if hasattr(t, "blocker_refs"):
        return t.blocker_refs(n)
    return [{"number": b, "repo": None} for b in t.list_dependencies(n)]


def _show(board, ref):
    if ref.get("repo") and board.repo and ref["repo"].lower() != board.repo.lower():
        return "%s#%d" % (ref["repo"], ref["number"])
    return tid(ref["number"]) if ref["number"] in board.tickets else "#%d" % ref["number"]


def plan(t, repo="", ids=None, board=None):
    """The diff between the tickets' links and the native ones. Reads only."""
    board = board or Board(t, repo)
    scope = sorted(board.tickets)
    missing = []
    if ids:
        want = [bc.ticket_number(i) for i in ids]
        missing = [tid(m) for m in want if m not in board.tickets]
        scope = [m for m in scope if m in want]
    avail = availability(t, board, scope)
    out = {"repo": board.repo, "tickets": len(scope), "available": avail, "ops": [],
           "unresolved": [], "kept": [], "tokens": 0, "missing": missing,
           "undecodable": board.undecodable}
    for n in scope:
        parent, blockers, unresolved, tokens = wanted(board, n)
        out["tokens"] += tokens
        for u in unresolved:
            if (u["field"] == "parent" and avail["sub_issues"] is True) or \
                    (u["field"] == "waiting_on" and avail["dependencies"] is True):
                out["unresolved"].append(u)
        if avail["sub_issues"] is True:
            have = native_parent(t, board, n)
            mine = board.local(have)
            if parent is not None and mine != parent:
                out["ops"].append({"op": "add_sub_issue", "issue": n, "parent": parent,
                                   "replaces": _show(board, have) if have else None})
            elif parent is None and have and mine is None:
                out["kept"].append({"issue": n, "link": "sub-issue of",
                                    "target": _show(board, have)})
            elif parent is None and mine is not None and \
                    not any(u["field"] == "parent" for u in unresolved):
                out["ops"].append({"op": "remove_sub_issue", "issue": n, "parent": mine})
        if avail["dependencies"] is True:
            have = native_blockers(t, board, n)
            mine = []
            for ref in have:
                m = board.local(ref)
                if m is None:
                    out["kept"].append({"issue": n, "link": "blocked by",
                                        "target": _show(board, ref)})
                else:
                    mine.append(m)
            for b in blockers:
                if b not in mine:
                    out["ops"].append({"op": "add_blocked_by", "issue": n, "blocker": b})
            for b in sorted(set(mine)):
                if b not in blockers:
                    out["ops"].append({"op": "remove_blocked_by", "issue": n, "blocker": b})
    out["ops"].sort(key=lambda o: (ORDER.index(o["op"]), o["issue"]))
    return out


def describe(op):
    n = tid(op["issue"])
    if op["op"] == "add_sub_issue":
        return "+ %s sub-issue of %s%s" % (n, tid(op["parent"]), (
            " (now under %s)" % op["replaces"]) if op.get("replaces") else "")
    if op["op"] == "remove_sub_issue":
        return "- %s no longer a sub-issue of %s" % (n, tid(op["parent"]))
    if op["op"] == "add_blocked_by":
        return "+ %s blocked by %s" % (n, tid(op["blocker"]))
    return "- %s no longer blocked by %s" % (n, tid(op["blocker"]))


def apply_op(t, op):
    if op["op"] == "add_sub_issue":
        t.set_parent(op["issue"], op["parent"])          # replaces a parent it had
    elif op["op"] == "remove_sub_issue":
        t.remove_parent(op["issue"], op["parent"])
    elif op["op"] == "add_blocked_by":
        t.add_dependency(op["issue"], op["blocker"])
    else:
        t.remove_dependency(op["issue"], op["blocker"])


def apply(t, p, log=None, issues=()):
    """Write the ops of plan ``p``; ``(done, failed)``, failed as ``(op, message)``. A failed
    write does not stop the others; a rerun of ``plan`` + ``apply`` picks up what is left.
    ``issues`` (the listed issues) lend their ids to a transport that needs them."""
    if issues and hasattr(t, "note_ids"):
        t.note_ids(list(issues))
    done, failed = [], []
    for op in p["ops"]:
        try:
            apply_op(t, op)
        except Exception as e:                       # report it, go on with the rest
            failed.append((op, str(e)))
            if log:
                log("! %s: %s" % (describe(op), e))
            continue
        done.append(op)
        if log:
            log(describe(op))
    return done, failed


def report(p, write=print):
    a = p["available"]
    write("board_relations: %s, %d ticket(s); sub-issues %s, dependencies %s"
          % (p["repo"] or "board", p["tickets"],
             "available" if a["sub_issues"] is True else a["sub_issues"],
             "available" if a["dependencies"] is True else a["dependencies"]))
    for m in p["missing"]:
        write("? %s: not a ticket on the board (--ids)" % m)
    for u in p["unresolved"]:
        write("? %s %s %s: %s (skipped)" % (tid(u["issue"]), u["field"], u["target"], u["why"]))
    for k in p["kept"]:
        write("= %s %s %s: not a board ticket, kept" % (tid(k["issue"]), k["link"], k["target"]))


def summary(p):
    c = {o: sum(1 for x in p["ops"] if x["op"] == o) for o in ORDER}
    return ("%d change(s): %d sub-issue link(s) to add or move, %d to remove; %d dependency "
            "link(s) to add, %d to remove; %d unresolved, %d kept, %d non-ticket token(s) "
            "skipped" % (len(p["ops"]), c["add_sub_issue"], c["remove_sub_issue"],
                          c["add_blocked_by"], c["remove_blocked_by"], len(p["unresolved"]),
                          len(p["kept"]), p["tokens"]))


def open_transport(a):
    """``(transport, repo)`` from ``--repo`` (gh) or the workspace's github board."""
    if a.repo:
        import board_gh
        return board_gh.GhTransport(a.repo), a.repo
    ws = ac.load_workspace(a.workspace)
    if (ws.get("board_config") or {}).get("backend", "files") != "github":
        raise ac.ConfigError("the board is not on GitHub (board.backend is not github): "
                             "there are no native relations to mirror")
    store = ac.open_store(ws)
    return store.t, store.repo


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("plan", "apply"))
    ap.add_argument("--workspace", help="workspace.json (default: the one academy_common finds)")
    ap.add_argument("--repo", help="OWNER/NAME, read and written through gh (default: the "
                                   "workspace's board)")
    ap.add_argument("--ids", help="only these tickets' links, comma-separated T-NNNN")
    ap.add_argument("--dry-run", action="store_true", help="apply: print, write nothing")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    ids = [x.strip() for x in (a.ids or "").split(",") if x.strip()]
    bad = [x for x in ids if not _is_tid(x)]
    if bad:
        sys.stderr.write("board_relations: not a ticket id: %s\n" % ", ".join(bad))
        return 2
    try:
        t, repo = open_transport(a)
        board = Board(t, repo)
        p = plan(t, repo, ids, board=board)
    except Exception as e:                           # gh missing, config, an API error
        sys.stderr.write("board_relations: %s\n" % e)
        return 2
    writing = a.cmd == "apply" and not a.dry_run
    lines = []
    out = lines.append if a.json else print
    report(p, out)
    done, failed = [], []
    if writing:
        done, failed = apply(t, p, log=out, issues=board.issues.values())
    else:
        for op in p["ops"]:
            out(describe(op))
    if a.json:
        doc = dict(p, applied=len(done) if writing else 0,
                   failed=[{"op": o, "error": e} for o, e in failed], lines=lines)
        json.dump(doc, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
    else:
        unavailable = [k for k in KINDS if p["available"][k] is not True]
        print(summary(p) + ("" if writing else "; nothing written"))
        if writing:
            print("applied %d, failed %d%s" % (len(done), len(failed),
                                                "; rerun apply to resume" if failed else ""))
        if len(unavailable) == len(KINDS):
            print("native relations not available: nothing to do")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
