"""board_project_sync.py -- keep the board's GitHub Project (v2) in step with the issues.

Run by board-sync.yml after ``board_sync.py``: the issue of the event is added to the
Project (idempotent: ``addProjectV2ItemById`` returns the existing item) and its fields are
set to ``board_project.fields_for`` of the decoded ticket (Status, Instance, Role, Kind,
Priority, Agenda, Block; a field with no value is cleared, and a single-select value the
Project has no option for yet -- a new instance -- is added as an option first). An issue that does not decode as
a ticket (a stray issue, a placeholder) still joins the Project, with Status from its state
only. With no issue in the event (``workflow_dispatch``) every issue of the repository is
synced: that is the backfill and the repair.

Only the Project is written; the issue is never touched. A user-owned Project cannot be
reached with the workflow's ``GITHUB_TOKEN`` nor with a fine-grained token, so the step needs
``ACADEMY_PROJECT_TOKEN`` (a classic token with the ``project`` scope, or an App token) and
``ACADEMY_PROJECT`` (``users/<login>/<number>``, ``orgs/<login>/<number>`` or the Project's
URL). Without either it prints why and exits 0, and the board works from labels alone.

Offline:

    py board_project_sync.py --issue issue.json

prints the field values as JSON. ``values_for()`` is pure; ``sync_issue()`` takes an
injected ``gql(query, variables) -> data`` so the tests need no network.
"""

import argparse
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, HERE)

import board_codec as bc  # noqa: E402
import board_project as bp  # noqa: E402

RE_PROJECT = re.compile(r"(?:https://github\.com/)?(users|orgs)/([^/]+)/(?:projects/)?(\d+)/?$")

FIELDS_QUERY = """
query($login:String!,$number:Int!){ %s(login:$login){ projectV2(number:$number){ id
  fields(first:50){ nodes{ ... on ProjectV2FieldCommon{ id name dataType }
    ... on ProjectV2SingleSelectField{ options{ id name color } } } } } } }"""

ADD_OPTION = """
mutation($f:ID!,$o:[ProjectV2SingleSelectFieldOptionInput!]){ updateProjectV2Field(input:{
  fieldId:$f,singleSelectOptions:$o}){ projectV2Field{ ... on ProjectV2SingleSelectField{
  options{ id name color } } } } }"""

ADD_ITEM = """
mutation($p:ID!,$c:ID!){ addProjectV2ItemById(input:{projectId:$p,contentId:$c}){ item{ id } } }"""


def parse_project(ref):
    """``(owner_kind, login, number)`` of ``users/<login>/<n>``, ``orgs/<login>/<n>`` or a
    Project URL; owner_kind is the GraphQL root field (``user`` or ``organization``)."""
    m = RE_PROJECT.match((ref or "").strip())
    if not m:
        raise ValueError("ACADEMY_PROJECT must be users/<login>/<n>, orgs/<login>/<n> or the "
                         "Project URL, not %r" % ref)
    return ("user" if m.group(1) == "users" else "organization"), m.group(2), int(m.group(3))


def values_for(issue):
    """``(values, problem)``: the Project field values of an issue, and why it did not decode
    as a ticket (None when it did). A non-ticket gets Status from its state, nothing else."""
    try:
        meta, _ = bc.decode(issue)
    except bc.CodecError as e:
        return {"Status": "Done" if issue.get("state") == "closed" else "Todo"}, str(e)
    return bp.fields_for(meta), None


def load_project(gql, ref):
    """``{"id": ..., "fields": {name: field}}`` of the Project ``ref``."""
    kind, login, number = parse_project(ref)
    data = gql(FIELDS_QUERY % kind, {"login": login, "number": number})
    proj = (data.get(kind) or {}).get("projectV2")
    if not proj:
        raise LookupError("no Project %s (or the token cannot see it)" % ref)
    return {"id": proj["id"],
            "fields": {f["name"]: f for f in proj["fields"]["nodes"] if f.get("name")}}


def add_option(gql, field, name):
    """Append option ``name`` to a single-select field, keeping the existing options (and so
    every item's value): a new instance, or a kind the Project predates."""
    keep = [{"id": o["id"], "name": o["name"], "color": o.get("color") or "GRAY",
             "description": ""}
            for o in field.get("options", [])]
    data = gql(ADD_OPTION, {"f": field["id"], "o": keep + [
        {"name": name, "color": "GRAY", "description": ""}]})
    field["options"] = data["updateProjectV2Field"]["projectV2Field"]["options"]


def _value(gql, field, v):
    if field["dataType"] == "TEXT":
        return "{text:%s}" % json.dumps(v)
    find = lambda: next((o["id"] for o in field.get("options", []) if o["name"] == v), None)
    if not find():
        add_option(gql, field, v)
    oid = find()
    return '{singleSelectOptionId:"%s"}' % oid if oid else None


def sync_issue(gql, project, issue):
    """Add ``issue`` to the Project and set its fields. Returns the problems (a field the
    Project lacks, a non-ticket issue); never edits the issue."""
    values, problem = values_for(issue)
    problems = ["#%s: %s" % (issue["number"], problem)] if problem else []
    item = gql(ADD_ITEM, {"p": project["id"], "c": issue["node_id"]}
               )["addProjectV2ItemById"]["item"]["id"]
    parts = []
    for k, (name, v) in enumerate(sorted(values.items())):
        field = project["fields"].get(name)
        if not field:
            problems.append("#%s: the Project has no field %r" % (issue["number"], name))
            continue
        where = 'projectId:"%s",itemId:"%s",fieldId:"%s"' % (project["id"], item, field["id"])
        if v is None:
            parts.append("c%d: clearProjectV2ItemFieldValue(input:{%s}){ clientMutationId }"
                         % (k, where))
            continue
        value = _value(gql, field, v)
        if value is None:
            problems.append("#%s: %s has no option %r" % (issue["number"], name, v))
            continue
        parts.append("u%d: updateProjectV2ItemFieldValue(input:{%s,value:%s}){ clientMutationId }"
                     % (k, where, value))
    if parts:
        gql("mutation{ %s }" % " ".join(parts), {})
    return problems


# ----------------------------------------------------------------------------
# HTTP (only what the workflow needs)
# ----------------------------------------------------------------------------

def _request(url, token, payload=None):
    req = urllib.request.Request(url, method="POST" if payload is not None else "GET", data=(
        json.dumps(payload).encode() if payload is not None else None), headers={
        "Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
        "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"null")


def make_gql(api, token):
    def gql(query, variables):
        out = _request(api + "/graphql", token, {"query": query, "variables": variables})
        if out.get("errors"):
            raise RuntimeError("GraphQL: %s" % json.dumps(out["errors"])[:500])
        return out["data"]
    return gql


def _all_issues(api, repo, token):
    out, page = [], 1
    while True:
        batch = _request("%s/repos/%s/issues?state=all&per_page=100&page=%d"
                         % (api, repo, page), token)
        if not batch:
            return [i for i in out if "pull_request" not in i]
        out += batch
        page += 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--issue", help="offline: an issue JSON file (prints the field values)")
    a = ap.parse_args(argv)
    if a.issue:
        with open(a.issue, encoding="utf-8") as fh:
            values, problem = values_for(json.load(fh))
        json.dump({"values": values, "problem": problem}, sys.stdout, ensure_ascii=False,
                  indent=1)
        sys.stdout.write("\n")
        return 0
    token, ref = os.environ.get("ACADEMY_PROJECT_TOKEN"), os.environ.get("ACADEMY_PROJECT")
    if not token or not ref:
        print("board_project_sync: ACADEMY_PROJECT_TOKEN or ACADEMY_PROJECT not set; "
              "the Project is not synced (labels still are)")
        return 0
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    repo = os.environ["GITHUB_REPOSITORY"]
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as fh:
        event = json.load(fh)
    gql = make_gql(api, token)
    project = load_project(gql, ref)
    iss = event.get("issue")
    if iss and "pull_request" in iss:
        return 0
    # issues are read with the workflow's token: a project-only token cannot read a private repo
    rest = os.environ.get("GITHUB_TOKEN") or token
    if iss:   # fresh: board_sync.py may just have corrected its labels
        issues = [_request("%s/repos/%s/issues/%d" % (api, repo, iss["number"]), rest)]
    else:
        issues = _all_issues(api, repo, rest)
    problems = []
    for i in issues:
        problems += sync_issue(gql, project, i)
    print("board_project_sync: %d issue(s) synced" % len(issues))
    for p in problems:
        print("  " + p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
