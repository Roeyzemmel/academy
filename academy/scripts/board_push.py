"""board_push.py -- execute a board_export manifest against a GitHub repo (bulk, resumable).

    py board_push.py --manifest M --repo OWNER/NAME --state STATE.json --assignee LOGIN
                     [--limit N] [--dry-run]

The bulk transport of /academy:board-migrate ``run``: it posts the manifest through the
REST API (``board_gh.GhTransport``, i.e. ``gh api``), so bodies and comments arrive byte for
byte. Order of work:

1. labels: every label of the manifest that the repo lacks is created with the manifest's
   colour and description (so no create ever meets a missing label);
2. issues, strictly in manifest order: create (title, body, labels, the assignee when
   ``assign_human``), each thread comment in order, the sub-issue link to ``parent`` (always
   an older issue), then close with ``state_reason`` when the ticket is closed;
3. dependencies (``waits_on``), once every issue exists (a blocker may be newer).

``STATE.json`` records ``{"labels": "done", "<n>": step, "dependencies": "done"}`` after
every write (step: ``created``, ``comments:<k>``, ``parent``, ``closed``, ``done``). A rerun
resumes from it; it is also safe when the state file lost the last write: before every
create, issue ``n`` is read -- absent (with ``n - 1`` present) means create, present with the
same title means the create already happened (its comments are counted on GitHub and the
rest posted), anything else stops with exit 2 (numbering broke: never "fix" it by creating more issues).
A first run (empty state) requires an empty repo: no issue and no pull request. Every
check reads issues by number: the "newest issue" listing lags behind fresh creates (seen in
the rehearsal), so it would stop a healthy run.

Exit 0 when everything is done, 2 on a stop or error (the message says where to resume).
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


class PushStop(Exception):
    pass


def _save(path, state):
    if path:
        ac.atomic_write(path, json.dumps(state, indent=0, sort_keys=True) + "\n")


def _count_comments(t, number):
    n, page = 0, 1
    while True:
        chunk = t.list_comments(number, page=page, per_page=100)
        if not chunk:
            return n
        n += len(chunk)
        page += 1


def push_labels(t, manifest, state, state_path, log):
    if state.get("labels") == "done":
        return
    have = {l["name"] for l in t.list_labels()}
    for d in manifest["labels"]:
        if d["name"] not in have:
            t.create_label(d["name"], d.get("color", "ededed"), d.get("description", ""))
            log("label %s" % d["name"])
    state["labels"] = "done"
    _save(state_path, state)


def push_issue(t, i, state, state_path, assignee, log):
    n = i["number"]
    key = str(n)
    step = state.get(key)
    if step == "done":
        return
    posted = 0
    if step is None:
        # by number, never by "newest issue": the REST list lags behind fresh creates
        got = t.get_issue(n)
        if got:
            if got.get("title") != i["title"] or "pull_request" in got:
                raise PushStop("#%d is already taken by %r, the manifest has %r"
                               % (n, got.get("title"), i["title"]))
            posted = _count_comments(t, n)
            log("#%d was already created (state lost); %d comment(s) found" % (n, posted))
        elif n > 1 and not t.get_issue(n - 1):
            raise PushStop("#%d does not exist, so #%d would not get its number" % (n - 1, n))
        else:
            got = t.create_issue(i["title"], i["body"], i["labels"],
                                 assignees=[assignee] if i.get("assign_human") else None)
            if got["number"] != n:
                raise PushStop("created #%d for %s, expected #%d" % (got["number"], i["title"], n))
            log("#%d created" % n)
        state[key] = "created"
        _save(state_path, state)
        step = "created"
    elif step.startswith("comments:"):
        posted = int(step.split(":", 1)[1])
    elif step == "created":
        posted = 0
    comments = i["comments"]
    if step in ("created",) or step.startswith("comments:"):
        for k in range(posted, len(comments)):
            t.add_comment(n, comments[k])
            state[key] = "comments:%d" % (k + 1)
            _save(state_path, state)
        if i.get("parent"):
            parent = bc.ticket_number(i["parent"])
            if t.get_parent(n) != parent:
                t.set_parent(n, parent)
        state[key] = "parent"
        _save(state_path, state)
        step = "parent"
    if step == "parent":
        if i["state"] == "closed":
            t.update_issue(n, state="closed", state_reason=i.get("state_reason"))
        state[key] = "closed"
        _save(state_path, state)
    state[key] = "done"
    _save(state_path, state)


def push_dependencies(t, manifest, state, state_path, log):
    if state.get("dependencies") == "done":
        return
    for r in manifest.get("relations", []):
        if r["type"] != "dependency":
            continue
        if r["blocker"] not in t.list_dependencies(r["issue"]):
            t.add_dependency(r["issue"], r["blocker"])
            log("#%d blocked by #%d" % (r["issue"], r["blocker"]))
    state["dependencies"] = "done"
    _save(state_path, state)


def _fresh(t, first):
    """The repo is empty, or holds only our own #1 (a first run whose state write was lost)."""
    got, second = t.get_issue(1), t.get_issue(2)
    if second:
        return False
    if got:
        return got.get("title") == first["title"] and "pull_request" not in got
    return t.last_number() == 0


def push(t, manifest, state=None, state_path=None, assignee=None, limit=None, log=print):
    """Execute ``manifest`` through transport ``t``; returns the state. Raises PushStop."""
    state = {} if state is None else state
    issues = manifest["issues"]
    if [i["number"] for i in issues] != list(range(1, len(issues) + 1)):
        raise PushStop("the manifest's numbers are not 1..%d" % len(issues))
    if any(i.get("assign_human") for i in issues) and not assignee:
        raise PushStop("some tickets are addressed to the human: pass --assignee LOGIN")
    if not any(k.isdigit() for k in state) and not _fresh(t, issues[0]):
        raise PushStop("the repo already has issues or pull requests: numbering would not "
                       "equal ticket ids (use an empty repo)")
    push_labels(t, manifest, state, state_path, log)
    done = 0
    for i in issues:
        if state.get(str(i["number"])) == "done":
            continue
        if limit is not None and done >= limit:
            return state
        push_issue(t, i, state, state_path, assignee, log)
        done += 1
    push_dependencies(t, manifest, state, state_path, log)
    return state


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--repo", required=True, help="OWNER/NAME")
    ap.add_argument("--state", required=True, help="the resumable state file")
    ap.add_argument("--assignee", help="the GitHub login of the human (tickets to human)")
    ap.add_argument("--limit", type=int, help="stop after this many issues (a partial run)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, send nothing")
    a = ap.parse_args(argv)
    with open(a.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)
    s = manifest.get("summary", {})
    if s.get("unreadable") or s.get("problems"):
        print("error: the manifest has unreadable tickets or problems; fix the board first",
              file=sys.stderr)
        return 2
    if manifest.get("repo") and manifest["repo"].lower() != a.repo.lower():
        print("error: the manifest was exported for %s, not %s" % (manifest["repo"], a.repo),
              file=sys.stderr)
        return 2
    state = {}
    if os.path.exists(a.state):
        with open(a.state, encoding="utf-8") as fh:
            state = json.load(fh)
    if a.dry_run:
        todo = [i["number"] for i in manifest["issues"] if state.get(str(i["number"])) != "done"]
        print("would push %d issue(s) (%s..%s), %d label(s), %d relation(s)"
              % (len(todo), todo[0] if todo else "-", todo[-1] if todo else "-",
                 len(manifest["labels"]), len(manifest.get("relations", []))))
        return 0
    import board_gh
    t = board_gh.GhTransport(a.repo)
    try:
        push(t, manifest, state, a.state, a.assignee, a.limit)
    except (PushStop, board_gh.GhError) as e:
        print("STOP: %s (state saved in %s; rerun the same command to resume)" % (e, a.state),
              file=sys.stderr)
        return 2
    left = [i["number"] for i in manifest["issues"] if state.get(str(i["number"])) != "done"]
    print("pushed: %d done, %d left%s" % (len(manifest["issues"]) - len(left), len(left),
                                         "" if left else ", dependencies done"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
