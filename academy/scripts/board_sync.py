"""board_sync.py -- the server-side half of the GitHub board (run by board-sync.yml).

Keeps one issue consistent with the ticket rules after any human or tool edit:

  * exactly one ``status:`` ``to:`` ``kind:`` ``prio:`` ``from:`` label (else: comment);
  * the ``role:`` label is derived from ``to:`` and is rewritten when it is wrong; so is
    ``route:dead`` (present exactly when ``blocked_by`` and ``reopen_if`` are both set);
  * the issue is open/closed (and completed/not_planned) as the status says;
  * the ticket decodes and passes ``validate_ticket`` (else: one comment listing problems).

Status *transitions* (who may move what) are enforced by the client hook and skills before
a write; this backstop only checks the state a write leaves behind. With a *previous* state
(``plan(..., previous=...)``) it also enforces what the state can show of the reopen rule:
a dead-route block ends only by ``blocked -> accepted`` with a new ``reopened:`` thread
entry (``board_codec.check_reopen``). The workflow keeps that previous state in one hidden
comment (``<!-- academy:state {...} -->``), advanced only while the rule holds, so a hand
edit stays reported until it is undone or the ``reopened:`` line is added. Offline:

    py board_sync.py --issue issue.json [--comments c.json] [--previous prev.json]

prints the plan as JSON (exit 1 when there are problems). ``prev.json`` is the compact
state (``board_codec.ticket_state``) or a snapshot ``{"issue": ..., "comments": [...]}``.
``plan()`` is pure; ``main()`` reads the workflow event and talks REST with
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
STATE_MARK = "<!-- academy:state "


def previous_state(previous):
    """The compact state of a ``previous`` given as a state dict or a snapshot
    ``{"issue": ..., "comments": [...]}`` (None when there is none or it does not decode)."""
    if not previous:
        return None
    if "issue" in previous:
        try:
            return bc.state_of_issue(previous["issue"], previous.get("comments", []))
        except (bc.CodecError, ValueError):
            return None
    return previous


def plan(issue, comments, previous=None):
    """Actions for one issue: ``{"labels": [...]|None, "state": ..., "problems": [...]}``.

    ``labels`` is the corrected full label list when it must change, ``state`` a
    ``(state, reason)`` when the open/closed state must change, ``problems`` what a human
    must fix (unfixable here). ``previous`` (see ``previous_state``) adds the reopen-rule
    check of ``board_codec.check_reopen``.
    """
    names = bc.label_names(issue.get("labels"))
    out = {"labels": None, "state": None, "problems": []}
    if "placeholder" in names:
        return out
    try:
        meta, _body = bc.decode(issue, comments)
    except (bc.CodecError, ValueError) as e:
        out["problems"].append(str(e))
        return out
    want_role = "role:" + bc.role_of(meta["to"])
    want_route = bc.route_labels(meta)
    if ([n for n in names if n.startswith("role:")] != [want_role]
            or [n for n in names if n.startswith("route:")] != want_route):
        out["labels"] = [n for n in names if not n.startswith(("role:", "route:"))] \
            + [want_role] + want_route
    state, reason = bc.state_of(meta["status"])
    if issue.get("state") != state or (state == "closed"
                                       and issue.get("state_reason") != reason):
        out["state"] = (state, reason)
    fixed = dict(issue, labels=out["labels"] or names)
    out["problems"] = [p for p in bc.validate_issue(fixed, comments)
                       if not p.startswith("issue is ") and "state_reason" not in p]
    prev = previous_state(previous)
    if prev:
        out["problems"] += bc.check_reopen(prev, bc.ticket_state(meta, _body))
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


def _state_comment(comments):
    """``(comment, state)`` of the hidden state comment, or ``(None, None)``."""
    for c in comments:
        text = c.get("body") or ""
        if text.startswith(STATE_MARK):
            try:
                return c, json.loads(text[len(STATE_MARK):].rsplit(" -->", 1)[0])
            except ValueError:
                return c, None
    return None, None


def sync(iss, comments, call, api, previous=None):
    """Plan and apply one issue with ``call(method, url, payload)``; returns the plan.

    ``comments`` are API comment objects (``body``, ``url``). ``previous`` overrides the
    stored state (the workflow passes nothing and the hidden state comment is used).
    """
    bodies = [c["body"] for c in comments]
    state_c, stored = _state_comment(comments)
    p = plan(iss, bodies, previous if previous is not None else stored)
    patch = {}
    if p["labels"] is not None:
        patch["labels"] = p["labels"]
    if p["state"]:
        patch["state"], reason = p["state"]
        if reason:
            patch["state_reason"] = reason
    if patch:
        call("PATCH", api, patch)
    if p["problems"]:
        body = PROBLEM_MARK + "\nThis ticket does not pass the board rules:\n\n" + \
            "\n".join("- " + x for x in p["problems"])
        old = [c for c in comments if (c["body"] or "").startswith(PROBLEM_MARK)]
        if old:
            call("PATCH", old[-1]["url"], {"body": body})
        else:
            call("POST", api + "/comments", {"body": body})
    # advance the remembered state only while the reopen rule holds
    try:
        now = bc.state_of_issue(dict(iss, labels=p["labels"] or iss.get("labels")), bodies)
    except (bc.CodecError, ValueError):
        now = None
    prev = previous_state(previous if previous is not None else stored)
    if now and not bc.check_reopen(prev, now):
        text = STATE_MARK + json.dumps(now, separators=(",", ":"), sort_keys=True) + " -->"
        if state_c is None:
            call("POST", api + "/comments", {"body": text})
        elif (state_c.get("body") or "") != text:
            call("PATCH", state_c["url"], {"body": text})
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
    if not iss or "pull_request" in iss:
        return 0
    api = "%s/repos/%s/issues/%d" % (os.environ.get("GITHUB_API_URL", "https://api.github.com"),
                                     os.environ["GITHUB_REPOSITORY"], iss["number"])
    iss = _call("GET", api, token)
    comments = _comments(api, token)
    sync(iss, comments, lambda m, u, payload: _call(m, u, token, payload), api)
    return 0


if __name__ == "__main__":
    sys.exit(main())
