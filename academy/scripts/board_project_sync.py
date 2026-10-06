"""board_project_sync.py -- keep the board's GitHub Project (v2) in step with the issues.

Every ticket issue becomes an item of the Project, with its fields set to
``board_project.fields_for`` of the decoded ticket (Status, Instance, Role, Kind, Priority,
Agenda, Block; a field with no value is cleared, and a single-select value the Project has
no option for yet -- a new instance -- is appended as an option first). An issue that does
not decode as a ticket still joins, with Status from its state only. Only the Project is
written; the issue is never touched. Items already right are left alone.

It runs on the human's machine, through ``gh`` logged in with the ``project`` scope
(``gh auth login -s project``): a user-owned Project cannot be reached by a workflow's
``GITHUB_TOKEN`` nor by a fine-grained token, and no long-lived token is stored in the repo.
New issues join the Project through its built-in "Auto-add to project" workflow; this script
fills their fields when it next runs:

    py board_project_sync.py [--repo OWNER/NAME] [--project users/<login>/<n>] [--issue N]...
    py board_project_sync.py --decode issue.json     # offline: the values, as JSON

``--repo`` and ``--project`` default to ``board.repo`` and ``board.project`` in
workspace.json. Exit 0 when clean, 1 with problems listed, 2 on an error. ``values_for()`` is
pure; ``sync_issue()`` takes an injected ``gql(query, variables) -> data`` so the tests need
no network.
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))
sys.path.insert(0, HERE)

import academy_common as ac  # noqa: E402
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


def sync_issue(gql, project, issue, current=None):
    """Add ``issue`` to the Project and set its fields; ``current`` is its item as
    ``(item id, {field: value})`` when it is already there. Returns ``(problems, written)``:
    the problems (a field the Project lacks, a non-ticket issue) and whether anything was
    written (nothing when the item already holds every value). Never edits the issue."""
    values, problem = values_for(issue)
    problems = ["#%s: %s" % (issue["number"], problem)] if problem else []
    if current and all(current[1].get(k) == v for k, v in values.items()):
        return problems, False
    item = current[0] if current else gql(ADD_ITEM, {"p": project["id"], "c": issue["node_id"]}
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
    return problems, True


# ----------------------------------------------------------------------------
# gh (the human's login)
# ----------------------------------------------------------------------------

GH = os.environ.get("GH", "gh")

ITEMS_QUERY = """
query($p:ID!,$a:String){ node(id:$p){ ... on ProjectV2 { items(first:100,after:$a){
  pageInfo{ hasNextPage endCursor }
  nodes{ id content{ ... on Issue{ number repository{ nameWithOwner } } }
    fieldValues(first:30){ nodes{
      ... on ProjectV2ItemFieldSingleSelectValue{ name
        field{ ... on ProjectV2FieldCommon{ name } } }
      ... on ProjectV2ItemFieldTextValue{ text
        field{ ... on ProjectV2FieldCommon{ name } } } } } } } } } }"""


def _gh(args, stdin=None):
    p = subprocess.run([GH] + args, input=stdin, capture_output=True, text=True,
                       encoding="utf-8")
    if p.returncode:
        raise RuntimeError("gh %s: %s" % (" ".join(args[:2]), (p.stderr or p.stdout).strip()))
    return p.stdout


def gh_gql(query, variables):
    out = json.loads(_gh(["api", "graphql", "--input", "-"],
                         json.dumps({"query": query, "variables": variables})))
    if out.get("errors"):
        raise RuntimeError("GraphQL: %s" % json.dumps(out["errors"])[:500])
    return out["data"]


def gh_issues(repo, numbers=None):
    if numbers:
        return [json.loads(_gh(["api", "repos/%s/issues/%d" % (repo, n)])) for n in numbers]
    pages = json.loads(_gh(["api", "--paginate", "--slurp",
                            "repos/%s/issues?state=all&per_page=100" % repo]))
    return [i for page in pages for i in page if "pull_request" not in i]


def project_items(gql, project, repo):
    """``{issue number: (item id, {field: value})}`` of the Project's items from ``repo``."""
    out, after = {}, None
    while True:
        page = gql(ITEMS_QUERY, {"p": project["id"], "a": after})["node"]["items"]
        for n in page["nodes"]:
            c = n.get("content") or {}
            if (c.get("repository") or {}).get("nameWithOwner") != repo:
                continue
            vals = {}
            for v in n["fieldValues"]["nodes"]:
                if v and v.get("field"):
                    vals[v["field"]["name"]] = v["name"] if "name" in v else v.get("text")
            out[c["number"]] = (n["id"], vals)
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", help="OWNER/NAME (default: board.repo in workspace.json)")
    ap.add_argument("--project", help="users/<login>/<n>, orgs/<login>/<n> or the Project URL "
                                      "(default: board.project in workspace.json)")
    ap.add_argument("--issue", type=int, action="append", help="only this issue (repeatable)")
    ap.add_argument("--workspace", help="workspace.json (default: the one academy_common finds)")
    ap.add_argument("--decode", help="offline: an issue JSON file (prints the field values)")
    a = ap.parse_args(argv)
    if a.decode:
        with open(a.decode, encoding="utf-8") as fh:
            values, problem = values_for(json.load(fh))
        json.dump({"values": values, "problem": problem}, sys.stdout, ensure_ascii=False,
                  indent=1)
        sys.stdout.write("\n")
        return 0
    cfg = {}
    if not (a.repo and a.project):
        try:
            cfg = ac.load_workspace(a.workspace).get("board_config") or {}
        except ac.ConfigError:   # no workspace: the flags must say it all
            cfg = {}
    repo, ref = a.repo or cfg.get("repo"), a.project or cfg.get("project")
    if not repo or not ref:
        sys.stderr.write("board_project_sync: give --repo and --project (or board.repo and "
                         "board.project in workspace.json)\n")
        return 2
    try:
        project = load_project(gh_gql, ref)
        items = project_items(gh_gql, project, repo)
        issues = gh_issues(repo, a.issue)
        problems, written = [], 0
        for i in sorted(issues, key=lambda i: i["number"]):
            p, w = sync_issue(gh_gql, project, i, items.get(i["number"]))
            problems += p
            written += w
    except (RuntimeError, LookupError, ValueError) as e:
        sys.stderr.write("board_project_sync: %s\n" % e)
        return 2
    print("board_project_sync: %d issue(s) checked, %d updated" % (len(issues), written))
    for p in problems:
        print("  " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
