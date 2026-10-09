"""reviews.py -- where proof-review records live, and the statement hash.

    py reviews.py hash (--file F | --text T)          statement hash (decision_table.statement_hash)
    py reviews.py dir SUBJECT PASS [--home H]         the pass folder for a subject
    py reviews.py new-pass SUBJECT [--ticket T-NNNN]  open a pass: its name (date + ticket or time);
                                                      refused while another pass on SUBJECT is open
    py reviews.py abandon SUBJECT PASS --reason R     close an open pass with no decision
    py reviews.py list SUBJECT [--home H] [--json]    passes and their records

Layout (plan section 3.4): ``<expert home>/reviews/<ns>/<id-slug>/<pass>/`` holds
``A.md`` and ``B.md`` (verdicts landed by ``land_verdict.py``) and ``decision.md``
(the review-chair's record of the decision table's outcome), or ``abandoned.md`` for
a pass closed without one. ``new-pass`` notes the pass it opens as
``<subject dir>/.open/<pass>`` (outside the pass folder, which stays empty while a run
is in flight), and refuses a second pass on the same statement while one is open -- a
pass folder or note with neither ``decision.md`` nor ``abandoned.md`` -- since two
concurrent passes on one statement are forbidden (Roey, 2026-10-08). ``<id-slug>`` is the
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


OPEN_DIR = ".open"
CLOSERS = ("decision.md", "abandoned.md")


def _closed(subject_path, name):
    return any(os.path.isfile(os.path.join(subject_path, name, f)) for f in CLOSERS)


def open_passes(home, subject):
    """The names of the subject's open passes: noted by ``new-pass`` or holding landed
    runs, with neither decision.md nor abandoned.md. Folders starting with ``_`` or
    ``.`` (``_unfiled``) are not passes."""
    d = subject_dir(home, subject)
    names = set()
    if os.path.isdir(d):
        for n in os.listdir(d):
            if n[:1] not in ("_", ".") and os.path.isdir(os.path.join(d, n)):
                names.add(n)
        if os.path.isdir(os.path.join(d, OPEN_DIR)):
            names.update(os.listdir(os.path.join(d, OPEN_DIR)))
    return sorted(n for n in names if not _closed(d, n))


class Refused(Exception):
    pass


def open_pass(home, subject, ticket=None, now=None):
    """Open a pass on ``subject`` and return its name; the same name again if that pass
    is already open (a rerun of the same step). Raises Refused while another pass on
    the subject is open."""
    name = new_pass(ticket, now)
    others = [p for p in open_passes(home, subject) if p != name]
    if others:
        raise Refused("%s already has an open pass %s (no decision.md): conclude it, or "
                      "close it with `reviews.py abandon %s %s --reason ...`, before "
                      "opening another; two concurrent passes on one statement are "
                      "never run" % (subject, ", ".join(others), subject, others[0]))
    d = os.path.join(subject_dir(home, subject), OPEN_DIR)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("ticket: %s\nopened: %s\n" % (ticket or "none",
                                                (now or datetime.datetime.now())
                                                .strftime("%Y-%m-%d %H:%M")))
    return name


def abandon_pass(home, subject, pass_name, reason, now=None):
    if pass_name not in open_passes(home, subject):
        raise Refused("%s has no open pass %r" % (subject, pass_name))
    path = os.path.join(pass_dir(home, subject, pass_name), "abandoned.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("---\nsubject: %s\npass: %s\nabandoned: %s\n---\n\n%s\n"
                 % (subject, pass_name, (now or datetime.datetime.now())
                    .strftime("%Y-%m-%d"), reason.strip()))
    return path


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
    n.add_argument("--home")
    ab = sub.add_parser("abandon")
    ab.add_argument("subject")
    ab.add_argument("pass_name")
    ab.add_argument("--reason", required=True)
    ab.add_argument("--home")
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
    home = ex.expert_home(home=args.home)
    if not home:
        sys.stderr.write("reviews: no expert home (pass --home)\n")
        return 2
    if args.cmd == "new-pass":
        try:
            print(open_pass(home, args.subject, args.ticket))
        except Refused as exc:
            sys.stderr.write("reviews: refused: %s\n" % exc)
            return 1
        return 0
    if args.cmd == "abandon":
        try:
            print(abandon_pass(home, args.subject, args.pass_name, args.reason)
                  .replace("\\", "/"))
        except Refused as exc:
            sys.stderr.write("reviews: refused: %s\n" % exc)
            return 1
        return 0
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
