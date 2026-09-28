"""reviews.py -- where proof-review records live, and the statement hash.

    py reviews.py hash (--file F | --text T)          statement hash (decision_table.statement_hash)
    py reviews.py dir SUBJECT PASS [--home H]         the pass folder for a subject
    py reviews.py new-pass SUBJECT [--ticket T-NNNN]  a fresh pass name (date + ticket or time)
    py reviews.py list SUBJECT [--home H] [--json]    passes and their records

Layout (plan section 3.4): ``<expert home>/reviews/<ns>/<id-slug>/<pass>/`` holds
``A.md`` and ``B.md`` (verdicts landed by ``land_verdict.py``) and ``decision.md``
(the review-chair's record of the decision table's outcome). ``<id-slug>`` is the
id with every character outside ``[A-Za-z0-9._-]`` turned into ``-``
(``paper:lem:strip-bound`` -> ``paper/lem-strip-bound``).
"""

import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from decision_table import statement_hash  # noqa: E402

RE_SUBJECT = re.compile(r"^([a-z0-9][a-z0-9-]*):(.+)$")
RE_PASS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def split_subject(subject):
    m = RE_SUBJECT.match(str(subject or "").strip())
    if not m:
        return None, None
    return m.group(1), m.group(2)


def reviews_root(home):
    return ex.home_path(home, ex.expert_config(home), "reviews", "reviews")


def subject_dir(home, subject):
    ns, cid = split_subject(subject)
    if not ns:
        return os.path.join(reviews_root(home), "_unsorted", ex.slug_id(subject or "unknown"))
    return os.path.join(reviews_root(home), ns, ex.slug_id(cid))


def pass_dir(home, subject, pass_name):
    p = pass_name if pass_name and RE_PASS.match(pass_name) else ex.slug_id(pass_name or "")
    return os.path.join(subject_dir(home, subject), p or "unpaired")


def new_pass(ticket=None, now=None):
    now = now or datetime.datetime.now()
    if ticket:
        return "%s-%s" % (now.strftime("%Y-%m-%d"), ticket)
    return now.strftime("%Y-%m-%d-%H%M")


def list_passes(home, subject):
    d = subject_dir(home, subject)
    out = []
    if not os.path.isdir(d):
        return out
    for p in sorted(os.listdir(d)):
        full = os.path.join(d, p)
        if os.path.isdir(full):
            out.append({"pass": p, "dir": full.replace("\\", "/"),
                        "files": sorted(os.listdir(full))})
    return out


def main(argv=None):
    ex.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hash")
    g = h.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--text")
    d = sub.add_parser("dir")
    d.add_argument("subject")
    d.add_argument("pass_name")
    d.add_argument("--home")
    n = sub.add_parser("new-pass")
    n.add_argument("subject")
    n.add_argument("--ticket")
    ls = sub.add_parser("list")
    ls.add_argument("subject")
    ls.add_argument("--home")
    ls.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "hash":
        if args.file:
            with open(args.file, "r", encoding="utf-8") as fh:
                text = fh.read()
        else:
            text = args.text
        print(statement_hash(text))
        return 0
    if args.cmd == "new-pass":
        print(new_pass(args.ticket))
        return 0
    home = ex.expert_home(home=args.home)
    if not home:
        sys.stderr.write("reviews: no expert home (pass --home)\n")
        return 2
    if args.cmd == "dir":
        print(pass_dir(home, args.subject, args.pass_name).replace("\\", "/"))
        return 0
    rows = list_passes(home, args.subject)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            print("%s\t%s" % (r["pass"], ", ".join(r["files"])))
        if not rows:
            print("no review passes for %s" % args.subject)
    return 0


if __name__ == "__main__":
    sys.exit(main())
