"""board_sync.py -- the server-side half of the GitHub board (run by board-sync.yml).

Keeps one issue consistent with the ticket rules after any human or tool edit:

  * exactly one ``status:`` ``to:`` ``kind:`` ``prio:`` ``from:`` label (else: comment);
  * the ``role:`` label is derived from ``to:`` and is rewritten when it is wrong;
  * the issue is open/closed (and completed/not_planned) as the status says;
  * the ticket decodes and passes ``validate_ticket`` (else: one comment listing problems).

Status *transitions* (who may move what) are enforced by the client hook and skills before
a write; this backstop only checks the state a write leaves behind. ``plan()`` is pure;
``main()`` reads the workflow event and talks REST with ``GITHUB_TOKEN`` (stdlib urllib).
"""

import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, HERE)

import board_codec as bc  # noqa: E402

PROBLEM_MARK = "<!-- academy:problems -->"


def plan(issue, comments):
    """Actions for one issue: ``{"labels": [...]|None, "state": ..., "problems": [...]}``.

    ``labels`` is the corrected full label list when it must change, ``state`` a
    ``(state, reason)`` when the open/closed state must change, ``problems`` what a human
    must fix (unfixable here).
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
    if [n for n in names if n.startswith("role:")] != [want_role]:
        out["labels"] = [n for n in names if not n.startswith("role:")] + [want_role]
    state, reason = bc.state_of(meta["status"])
    if issue.get("state") != state or (state == "closed"
                                       and issue.get("state_reason") != reason):
        out["state"] = (state, reason)
    fixed = dict(issue, labels=out["labels"] or names)
    out["problems"] = [p for p in bc.validate_issue(fixed, comments)
                       if not p.startswith("issue is ") and "state_reason" not in p]
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


def main():
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
    p = plan(iss, [c["body"] for c in comments])
    patch = {}
    if p["labels"] is not None:
        patch["labels"] = p["labels"]
    if p["state"]:
        patch["state"], reason = p["state"]
        if reason:
            patch["state_reason"] = reason
    if patch:
        _call("PATCH", api, token, patch)
    if p["problems"]:
        body = PROBLEM_MARK + "\nThis ticket does not pass the board rules:\n\n" + \
            "\n".join("- " + x for x in p["problems"])
        old = [c for c in comments if (c["body"] or "").startswith(PROBLEM_MARK)]
        if old:
            _call("PATCH", old[-1]["url"], token, {"body": body})
        else:
            _call("POST", api + "/comments", token, {"body": body})
    return 0


if __name__ == "__main__":
    sys.exit(main())
