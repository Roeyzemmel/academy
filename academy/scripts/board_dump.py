"""board_dump.py -- the verify dump of a GitHub board, read through the REST API.

    py board_dump.py --repo OWNER/NAME --out dump.json

Writes ``[{"issue": {number, title, body, labels, state, state_reason, assignees},
"comments": [body, ...], "parent": <number or null>, "waits_on": [<number>, ...]}]`` for
every issue (pull requests skipped), the input of ``board_verify.py --issues`` and
``board_import.py --issues``. Read by script through ``gh api`` (``board_gh``), so the text
is byte-exact; never have a model retype a dump. The issue listing lags behind fresh creates,
so the dump reads on by number past the last listed issue. Parents and dependencies are both read, so
the verifier checks every relation.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))

import board_codec as bc  # noqa: E402
import board_store as bs  # noqa: E402


def _login(a):
    return a.get("login") if isinstance(a, dict) else a


def dump(t):
    """The dump records of every issue the transport holds, by number."""
    listed = bs.pages(t.list_issues, state="all")
    # the listing lags behind fresh creates: read on by number until the first gap
    n = max([i["number"] for i in listed], default=0) + 1
    while True:
        extra = t.get_issue(n)
        if not extra:
            break
        listed.append(extra)
        n += 1
    issues = [i for i in listed if "pull_request" not in i]
    out = []
    for i in sorted(issues, key=lambda i: i["number"]):
        n = i["number"]
        comments = [bs._body(c) for c in bs._ordered(bs.pages(t.list_comments, number=n))]
        out.append({"issue": {"number": n, "title": i["title"], "body": i.get("body") or "",
                              "labels": bc.label_names(i.get("labels")),
                              "state": i["state"], "state_reason": i.get("state_reason"),
                              "assignees": [_login(a) for a in i.get("assignees") or []]},
                    "comments": comments, "parent": t.get_parent(n),
                    "waits_on": t.list_dependencies(n)})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    import board_gh
    recs = dump(board_gh.GhTransport(a.repo))
    with open(a.out, "w", encoding="utf-8", newline="") as fh:
        json.dump(recs, fh, ensure_ascii=False, indent=1)
    print("%d issue(s), %d comment(s), %d sub-issue link(s), %d dependency link(s) -> %s"
          % (len(recs), sum(len(r["comments"]) for r in recs),
             sum(1 for r in recs if r["parent"]), sum(len(r["waits_on"]) for r in recs), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
