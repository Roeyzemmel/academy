"""board_sync.py -- the server-side half of the GitHub board (run by board-sync.yml).

Keeps one issue consistent with the ticket rules after any human or tool edit:

  * exactly one ``status:`` ``to:`` ``kind:`` ``prio:`` ``from:`` label (else: comment);
  * the ``role:`` label is derived from ``to:`` and is rewritten when it is wrong; so is
    ``route:dead`` (present exactly when the ticket is blocked with both ``blocked_by`` and
    ``reopen_if``: ``board_codec.is_dead_block``);
  * the issue is open/closed (and completed/not_planned) as the status says;
  * the ticket decodes and passes ``validate_ticket`` (else: one comment listing problems).

Status *transitions* (who may move what) are enforced by the client hook and skills before
a write; this backstop only checks the state a write leaves behind. With a *previous* state
(``plan(..., previous=...)``) it also enforces what the state can show of the reopen rule:
a dead-route block ends only by ``blocked -> accepted`` with a new ``reopened:`` thread
entry (``board_codec.check_reopen``). The workflow keeps that previous state in one hidden
comment (``<!-- academy:state {...} -->``, written by ``github-actions[bot]``, which is the
only author trusted; the last one counts and duplicates are deleted), validated strictly and
advanced only while the rule holds, so a hand edit stays reported until it is undone or the
``reopened:`` line is added. The state carries a digest of the thread, so an edited or replaced
entry is seen; a deleted state is reported when the thread shows an unreopened dead route.
Limits, honestly: GitHub identity is one account, so a forged ``reopened:`` thread comment
or ``**human**`` speaker passes (the server checks the state, not the person); the human's
own moves are exempt when the workflow knows the actor (``ACADEMY_HUMAN_LOGINS``) or the new
last thread entry is spoken by ``human``. Problems are posted in one comment that is edited
to a "resolved" line when they clear. Offline:

    py board_sync.py --issue issue.json [--comments c.json] [--previous prev.json]

prints the plan as JSON (exit 1 when there are problems). ``prev.json`` is the compact
state (``board_codec.ticket_state``) or a snapshot ``{"issue": ..., "comments": [...]}``.
``plan()`` is pure and never raises; ``main()`` reads the workflow event and talks REST with
``GITHUB_TOKEN`` (stdlib urllib).
"""

import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, HERE)

import board_codec as bc  # noqa: E402

PROBLEM_MARK = "<!-- academy:problems -->"
RESOLVED = PROBLEM_MARK + "\nResolved: this ticket passes the board rules."
STATE_MARK = "<!-- academy:state "
STATE_END = " -->"
#: the only author whose state comment is trusted (the workflow's GITHUB_TOKEN)
BOT_LOGIN = "github-actions[bot]"


def previous_state(previous):
    """The compact state of a ``previous`` given as a state dict or a snapshot
    ``{"issue": ..., "comments": [...]}``; None when there is none, it is malformed
    (``board_codec.parse_state``) or the snapshot does not decode."""
    if not previous or not isinstance(previous, dict):
        return None
    if "issue" in previous:
        try:
            return bc.state_of_issue(previous["issue"], previous.get("comments", []))
        except (bc.CodecError, ValueError, TypeError, AttributeError):
            return None
    return bc.parse_state(previous)


def plan(issue, comments, previous=None, human=False, assignee=None):
    """Actions for one issue: ``{"labels": [...]|None, "state": ..., "problems": [...]}``.

    ``labels`` is the corrected full label list when it must change, ``state`` a
    ``(state, reason)`` when the open/closed state must change, ``problems`` what a human
    must fix (unfixable here). ``previous`` (see ``previous_state``) adds the reopen-rule
    check of ``board_codec.check_reopen``; ``human`` says the editor is the human. With
    ``assignee`` (the human's login), ``assignees`` is the corrected assignee list when it
    must change (``board_codec.wants_human``), else None. Never
    raises: an unexpected failure is itself a problem, so one bad issue does not stop a run.
    """
    try:
        return _plan(issue, comments, previous, human, assignee)
    except Exception as e:  # noqa: BLE001 -- the backstop must report, not crash
        return {"labels": None, "state": None, "assignees": None,
                "problems": ["board-sync could not check this ticket: %s: %s"
                             % (type(e).__name__, e)]}


def _plan(issue, comments, previous, human, assignee=None):
    names = bc.label_names(issue.get("labels"))
    out = {"labels": None, "state": None, "assignees": None, "problems": []}
    if bc.PLACEHOLDER in names:
        return out
    try:
        meta, body = bc.decode(issue, comments)
    except (bc.CodecError, ValueError) as e:
        out["problems"].append(str(e))
        return out
    want = bc.corrected_labels(meta, names)
    if sorted(n for n in names if bc.is_derived_label(n)) != sorted(bc.derived_labels(meta)):
        out["labels"] = want
    state, reason = bc.state_of(meta["status"])
    if issue.get("state") != state or (state == "closed"
                                       and issue.get("state_reason") != reason):
        out["state"] = (state, reason)
    if assignee:
        out["assignees"] = bc.assignees_for(meta, issue.get("assignees"), assignee)
    fixed = dict(issue, labels=out["labels"] or names)
    out["problems"] = [p for p in bc.validate_issue(fixed, comments)
                       if not p.startswith("issue is ") and "state_reason" not in p]
    prev = previous_state(previous)
    if previous and prev is None:
        out["problems"].append("the remembered state of this ticket is malformed and was "
                               "ignored (it is rewritten on this run)")
    out["problems"] += bc.check_reopen(prev, bc.ticket_state(meta, body), body, human)
    return out


# ----------------------------------------------------------------------------
# REST (only what the workflow needs)
# ----------------------------------------------------------------------------

def _call(method, url, token, payload=None):
    req = urllib.request.Request(url, method=method, data=(
        json.dumps(payload).encode() if payload is not None else None), headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def _comments(api, token):
    out, page = [], 1
    while True:
        chunk = _call("GET", "%s/comments?per_page=100&page=%d" % (api, page), token)
        out += chunk
        if len(chunk) < 100:
            return out
        page += 1


def _login(c):
    u = c.get("user")
    return u.get("login") if isinstance(u, dict) else None


def _state_comments(comments, bot=BOT_LOGIN):
    """``(comment, state, dupes, notes)`` of the hidden state comments.

    Only a comment written by ``bot`` counts, and of those the **last**; ``comment`` is that
    one (None when there is none), ``state`` its strictly validated state (None when absent
    or malformed), ``dupes`` the earlier bot state comments (to delete), ``notes`` problems
    to report: a state comment by anyone else (ignored) or a malformed one.
    """
    marked = [c for c in comments if (c.get("body") or "").startswith(STATE_MARK)]
    mine = [c for c in marked if _login(c) == bot]
    notes = ["a state comment by %s is ignored (only %s's counts)" % (_login(c) or "?", bot)
             for c in marked if _login(c) != bot]
    if not mine:
        return None, None, [], notes
    c = mine[-1]
    text = c["body"][len(STATE_MARK):]
    try:
        state = bc.parse_state(json.loads(text[:text.rindex(STATE_END)]))
    except ValueError:
        state = None
    if state is None:
        notes.append("the remembered state comment is malformed; it is rewritten on this run")
    return c, state, mine[:-1], notes


def sync(iss, comments, call, api, previous=None, human=False, bot=BOT_LOGIN,
         assignee=None):
    """Plan and apply one issue with ``call(method, url, payload)``; returns the plan.

    ``comments`` are API comment objects (``body``, ``url``, ``user``). ``previous``
    overrides the stored state (the workflow passes nothing and the hidden state comment
    of ``bot`` is used). ``human`` is whether the editor is the human (see ``main``).
    """
    bodies = [c.get("body") or "" for c in comments]
    state_c, stored, dupes, notes = _state_comments(comments, bot)
    prev = previous if previous is not None else stored
    p = plan(iss, bodies, prev, human, assignee)
    p["problems"] += notes
    patch = {}
    if p["labels"] is not None:
        patch["labels"] = p["labels"]
    if p.get("assignees") is not None:
        patch["assignees"] = p["assignees"]
    if p["state"]:
        patch["state"], reason = p["state"]
        if reason:
            patch["state_reason"] = reason
    if patch:
        call("PATCH", api, patch)
    old = [c for c in comments if (c.get("body") or "").startswith(PROBLEM_MARK)]
    if p["problems"]:
        body = PROBLEM_MARK + "\nThis ticket does not pass the board rules:\n\n" + \
            "\n".join("- " + x for x in p["problems"])
    else:
        body = RESOLVED                          # a stale report must not outlive its cause
    if old:
        if (old[-1].get("body") or "") != body:
            call("PATCH", old[-1]["url"], {"body": body})
    elif p["problems"]:
        call("POST", api + "/comments", {"body": body})
    # advance the remembered state only while the reopen rule holds
    try:
        fixed = dict(iss, labels=p["labels"] or iss.get("labels"))
        meta, body_t = bc.decode(fixed, bodies)
        now = bc.ticket_state(meta, body_t)
        ok = not bc.check_reopen(previous_state(prev), now, body_t, human)
    except Exception:  # noqa: BLE001
        now, ok = None, False
    if now and ok:
        text = STATE_MARK + json.dumps(now, separators=(",", ":"), sort_keys=True) + STATE_END
        if state_c is None:
            call("POST", api + "/comments", {"body": text})
        elif (state_c.get("body") or "") != text:
            call("PATCH", state_c["url"], {"body": text})
    for d in dupes:                              # one state comment, however it got doubled
        call("DELETE", d["url"], None)
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--issue", help="offline: an issue JSON file (prints the plan)")
    ap.add_argument("--comments", help="offline: a JSON list of comment bodies")
    ap.add_argument("--previous", help="offline: the previous state or snapshot JSON")
    a = ap.parse_args(argv)
    if a.issue:
        def load(path):
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        p = plan(load(a.issue), load(a.comments) if a.comments else [],
                 load(a.previous) if a.previous else None)
        json.dump(p, sys.stdout, ensure_ascii=False, indent=1)
        sys.stdout.write("\n")
        return 1 if p["problems"] else 0
    token = os.environ["GITHUB_TOKEN"]
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as fh:
        event = json.load(fh)
    iss = event.get("issue")
    # pull requests and ordinary issues share the repository: only board issues are synced
    if not iss or "pull_request" in iss or not bc.is_board_issue(iss):
        return 0
    api = "%s/repos/%s/issues/%d" % (os.environ.get("GITHUB_API_URL", "https://api.github.com"),
                                     os.environ["GITHUB_REPOSITORY"], iss["number"])
    iss = _call("GET", api, token)
    comments = _comments(api, token)
    humans = [x.strip() for x in os.environ.get("ACADEMY_HUMAN_LOGINS", "").split(",")
              if x.strip()]
    actor = (event.get("sender") or {}).get("login") or os.environ.get("GITHUB_ACTOR")
    sync(iss, comments, lambda m, u, payload: _call(m, u, token, payload), api,
         human=bool(actor and actor in humans),
         bot=os.environ.get("ACADEMY_STATE_AUTHOR", BOT_LOGIN),
         assignee=humans[0] if humans else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
