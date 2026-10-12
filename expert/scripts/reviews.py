"""reviews.py -- where proof-review records live, and the statement hash.

    py reviews.py hash (--file F | --text T)          statement hash (decision_table.statement_hash)
    py reviews.py dir SUBJECT PASS [--home H]         the pass folder for a subject
    py reviews.py new-pass SUBJECT [--ticket T-NNNN]  open a pass: its name (date + ticket or time);
                                                      refused while another pass on SUBJECT is open
    py reviews.py new-pass SUBJECT --reword-of BASE [--ticket T-NNNN]
                                                      open a reword pass (T-0347) on a
                                                      statement reworded after BASE, a
                                                      CONFIRMED x2 pass; name ends -reword
    py reviews.py reword-brief SUBJECT PASS (--old-file F | --old-text T)
                  (--new-file F | --new-text T) [--findings F_OR_TEXT ...]
                  [--ticket T] [--out FILE]           the reword run's brief bundle
    py reviews.py abandon SUBJECT PASS --reason R     close an open pass with no decision
    py reviews.py list SUBJECT [--home H] [--json]    passes and their records

Layout (plan section 3.4): ``<expert home>/reviews/<ns>/<id-slug>/<pass>/`` holds
``A.md`` and ``B.md`` (verdicts landed by ``land_verdict.py``) and ``decision.md``
(the review-chair's record of the decision table's outcome), or ``abandoned.md`` for
a pass closed without one. ``new-pass`` notes the pass it opens as
``<subject dir>/.open/<pass>`` (outside the pass folder, which stays empty while a run
is in flight), and refuses a second pass on the same statement while one is open -- a
pass folder or note with neither ``decision.md`` nor ``abandoned.md`` -- since two
concurrent passes on one statement are forbidden (verify/references/conclude.md).
``<id-slug>`` is the id with every character outside ``[A-Za-z0-9._-]`` turned into ``-``
(``paper:lem:strip-bound`` -> ``paper/lem-strip-bound``).

**Reword passes** (T-0347, the human's decision of 2026-10-12). A statement whose wording changed after a
pass decided CONFIRMED x2 gets one informed run, not a new blind pair. ``new-pass
--reword-of BASE`` refuses unless BASE (a pass of the same subject) holds runs A and B
whose decision table gives ``confirmed`` / ``confirmed-modulo`` and is not abandoned; it
opens ``<date>-<ticket>-reword`` and notes ``reword_of`` and ``base_hash`` in its
``.open`` note. ``reword-brief`` checks the old statement against ``base_hash`` and the
new one against it (it must differ), and writes the bundle the reword run reads: the
brief's fields (``run: R``, ``mode: reword``, ``base_pass``, ``base_hash``, the new
``statement_hash``), both statements, a word diff, the base pass's ``decision.md`` and
its two run records inlined (the run cannot read ``reviews/``: the blind guard still
closes it), and the findings that prompted the rewording. Write it outside
``reviews/`` (the session scratchpad).
"""

import argparse
import datetime
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
import decision_table as dt  # noqa: E402
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


REWORD_SUFFIX = "-reword"


def base_decision(home, subject, base):
    """``(A, B, result)`` of the base pass ``base`` of ``subject``: its run records and
    its decision table. Raises Refused unless it is a CONFIRMED x2 pass (``confirmed`` /
    ``confirmed-modulo``), present and not abandoned."""
    d = pass_dir(home, subject, base)
    a, b, notes = dt.base_records(None, base, d)
    if a is None or b is None:
        raise Refused("the base pass %s of %s cannot carry a reword: %s"
                      % (base, subject, "; ".join(notes) or "its runs A and B are missing"))
    res = dt.decide(a, b)
    if res["outcome"] not in ("confirmed", "confirmed-modulo"):
        raise Refused("the base pass %s of %s is not CONFIRMED x2 (its table gives %s): a "
                      "reword needs a confirmed base; run a full blind pass instead"
                      % (base, subject, res["outcome"]))
    return a, b, res


def open_pass(home, subject, ticket=None, now=None, reword_of=None):
    """Open a pass on ``subject`` and return its name; the same name again if that pass
    is already open (a rerun of the same step). Raises Refused while another pass on
    the subject is open. ``reword_of`` opens a reword pass on that base pass (T-0347);
    refused unless the base is CONFIRMED x2 (``base_decision``)."""
    name = new_pass(ticket, now)
    base_hash = None
    if reword_of:
        a, _b, _res = base_decision(home, subject, reword_of)
        base_hash = a.get("statement_hash") or ""
        name += REWORD_SUFFIX
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
        if reword_of:
            fh.write("reword_of: %s\nbase_hash: %s\n" % (reword_of, base_hash))
    return name


def pass_note(home, subject, pass_name):
    """The ``key: value`` lines of the pass's ``.open`` note ({} when there is none)."""
    p = os.path.join(subject_dir(home, subject), OPEN_DIR, pass_name)
    out = {}
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            for ln in fh.read().splitlines():
                k, sep, v = ln.partition(":")
                if sep:
                    out[k.strip()] = v.strip()
    return out


def word_diff(old, new):
    """``old`` -> ``new`` word by word: ``[-removed-]`` and ``{+added+}``, as git's
    ``--word-diff=plain``."""
    a, b = str(old or "").split(), str(new or "").split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False) \
            .get_opcodes():
        if op == "equal":
            out.extend(a[i1:i2])
            continue
        if i2 > i1:
            out.append("[-%s-]" % " ".join(a[i1:i2]))
        if j2 > j1:
            out.append("{+%s+}" % " ".join(b[j1:j2]))
    return " ".join(out)


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def reword_brief(home, subject, pass_name, old_text, new_text, findings=(), ticket=None):
    """The reword run's brief bundle (Markdown). Raises Refused when ``pass_name`` is not
    a reword pass, its base is not CONFIRMED x2, the old statement's hash is not the base
    pass's, or the statement did not change."""
    note = pass_note(home, subject, pass_name)
    base = note.get("reword_of")
    if not base:
        raise Refused("%s of %s is not a reword pass (open one with `new-pass %s "
                      "--reword-of <base pass>`)" % (pass_name, subject, subject))
    a, b, res = base_decision(home, subject, base)
    base_hash = a.get("statement_hash") or ""
    old_h, new_h = statement_hash(old_text), statement_hash(new_text)
    if old_h != base_hash:
        raise Refused("the old statement hashes to %s, not the base pass's base_hash %s: "
                      "give the statement exactly as the base pass reviewed it"
                      % (old_h, base_hash))
    if new_h == base_hash:
        raise Refused("the statement did not change (its hash is base_hash %s): the base "
                      "pass's decision applies; no reword pass is needed" % base_hash)
    if ticket is None:
        t = note.get("ticket")
        ticket = t if t and t != "none" else None
    bdir = pass_dir(home, subject, base)
    dec = os.path.join(bdir, "decision.md")
    out = ["# Reword review bundle: %s" % subject, "",
           "You are run R of a reword pass (mode: reword). You are not blind to the base "
           "pass: it is inlined below. Judge whether the proof as reviewed still covers "
           "the new wording (rigor-reviewer, \"Reword mode\").", "",
           "Copy these into your VERDICT block unchanged:", "", "```",
           "subject: %s" % subject, "pass: %s" % pass_name, "run: R", "mode: reword",
           "base_pass: %s" % base, "base_hash: %s" % base_hash,
           "statement_hash: %s" % new_h, "ticket: %s" % (ticket or "none"), "```", "",
           "Base pass outcome (decision table): %s; modulo: %s"
           % (res["outcome"], ", ".join(res["modulo"]) or "none"), "",
           "## The statement as reviewed (base_hash %s)" % base_hash, "",
           str(old_text).strip(), "",
           "## The statement now (statement_hash %s)" % new_h, "", str(new_text).strip(), "",
           "## The change, word by word ([-removed-] {+added+})", "",
           word_diff(old_text, new_text), ""]
    sections = [("The base pass's decision", dec)] + \
        [("The base pass's run %s" % r.get("run"), r.get("file")) for r in (a, b)]
    for title, path in sections:
        shown = str(path or "").replace("\\", "/")
        out += ["## %s (`%s`)" % (title, shown), ""]
        out += [_read(path).strip() if path and os.path.isfile(path)
                else "(missing: %s)" % shown, ""]
    out += ["## The findings that prompted the rewording", ""]
    if not findings:
        out += ["(none given)", ""]
    for f in findings:
        if os.path.isfile(f):
            out += ["### `%s`" % f.replace("\\", "/"), "", _read(f).strip(), ""]
        else:
            out += ["- %s" % f, ""]
    return "\n".join(out).rstrip() + "\n"


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
    n.add_argument("--reword-of", default=None,
                   help="open a reword pass on this CONFIRMED x2 base pass (T-0347)")
    n.add_argument("--home")
    rb = sub.add_parser("reword-brief")
    rb.add_argument("subject")
    rb.add_argument("pass_name")
    go = rb.add_mutually_exclusive_group(required=True)
    go.add_argument("--old-file")
    go.add_argument("--old-text")
    gn = rb.add_mutually_exclusive_group(required=True)
    gn.add_argument("--new-file")
    gn.add_argument("--new-text")
    rb.add_argument("--findings", action="append", default=[],
                    help="a file (inlined) or a line of text; repeatable")
    rb.add_argument("--ticket")
    rb.add_argument("--out", help="write the bundle here (outside reviews/) instead of "
                                  "printing it")
    rb.add_argument("--home")
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
            print(open_pass(home, args.subject, args.ticket, reword_of=args.reword_of))
        except Refused as exc:
            sys.stderr.write("reviews: refused: %s\n" % exc)
            return 1
        return 0
    if args.cmd == "reword-brief":
        old = _read(args.old_file) if args.old_file else args.old_text
        new = _read(args.new_file) if args.new_file else args.new_text
        try:
            text = reword_brief(home, args.subject, args.pass_name, old, new,
                                args.findings, args.ticket)
        except Refused as exc:
            sys.stderr.write("reviews: refused: %s\n" % exc)
            return 1
        if args.out:
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
            with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            print(args.out.replace("\\", "/"))
        else:
            print(text, end="")
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
