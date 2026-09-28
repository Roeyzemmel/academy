"""reviews.py -- the experiment-review pair: landed runs, the decision table, the grounds.

Plan section 8 (experiment review) and references/budget.md. The reviews are the files
``land_review.py`` writes under ``<home>/<paths.audits>/<subject slug>/``. This script
never writes: it reads them and says what happens next.

Usage (from a Researcher home, or with --home):

    py reviews.py list SUBJECT [--json]          the landed runs for a claim id
    py reviews.py decide SUBJECT [--json]        state, next step, proposed status, grounds
    py reviews.py pending [--json]               subjects waiting for run B
    py reviews.py brief SUBJECT --run A|B [--result R] [--ticket T-NNNN] [--report P-NNNN]

The decision table (run B only after a positive run A; neither run sees the other):

    no run A                                   need-A
    run A GAP / BROKEN (or capped)             not-cleared       (B is never launched)
    run A positive, no later run B             need-B
    B not positive                             not-cleared
    both SOUND                                 cleared
    both SOUND MODULO                          cleared-modulo    (assumptions quoted)
    SOUND with SOUND MODULO                    unresolved        (disagreement is not averaged)
    different commits, or different outcomes   unresolved

A cleared pair proposes ``supported`` (outcome supports) or ``refuted`` (outcome refutes);
never ``proved``. The grounds object is the shape the MCP ``claims_set_status`` checks
(``check_grounds``, basis computation); ``grounds_problems`` lists what it would refuse
(no commit, validation not passed, inconclusive outcome).

Exit codes: 0 success, 1 nothing found (list / decide with no runs is still 0), 2 error.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import _researcher as rs  # noqa: E402


def audits_dir(home):
    home, cfg, _ = rs.researcher_home(home) if home else (None, None, None)
    if not home:
        raise ac.AcademyError("not in a Researcher home (give --home)")
    return rs.notebook_paths(home, cfg)["audits"]


def load_runs(audits, subject):
    """The landed runs for ``subject``, oldest first: list of dicts (meta + 'path')."""
    folder = os.path.join(audits, rs.subject_slug(subject))
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(folder, name)
        try:
            meta, _ = ac.read_frontmatter(rs.read_text(path) or "")
        except ac.AcademyError:
            continue
        if meta.get("run") not in ("A", "B"):
            continue
        meta = dict(meta)
        meta["path"] = path.replace("\\", "/")
        meta["_key"] = (str(meta.get("landed") or ""), name)
        out.append(meta)
    out.sort(key=lambda m: m["_key"])
    return out


def current_pair(runs):
    """``(a, b)``: the latest run A and the run B landed after it (or None)."""
    a_idx = None
    for i, r in enumerate(runs):
        if r["run"] == "A":
            a_idx = i
    if a_idx is None:
        return None, None
    b = None
    for r in runs[a_idx + 1:]:
        if r["run"] == "B":
            b = r
    return runs[a_idx], b


def _v(run):
    return rs.norm_verdict(run.get("verdict"))[0]


def _ref(path):
    """A landed review file as an evidence ref: ``<home directory name>:<relative path>``
    (the registry's cross-repo ref form), else the path as it is."""
    home, _, _ = rs.researcher_home(path)
    rel = ac._rel_to(home, path) if home else None
    return "%s:%s" % (os.path.basename(home.rstrip("/")), rel) if rel else path


def decide(runs):
    """Apply the decision table to the landed runs of one subject."""
    a, b = current_pair(runs)
    out = {"state": None, "next": "", "a": a and a["path"], "b": b and b["path"],
           "verdicts": [x and _v(x) for x in (a, b) if x], "proposed_status": None,
           "assumptions": [], "grounds": None, "grounds_problems": [], "reasons": []}
    if a is None:
        out.update(state="need-A", next="launch experiment-reviewer run A")
        return out
    if _v(a) not in rs.POSITIVE:
        why = "run A: %s%s" % (_v(a) or a.get("verdict"),
                               " (capped: %s on %s)" % (a.get("verdict_given"), a.get("model"))
                               if a.get("capped") else "")
        out.update(state="not-cleared", next="report; run B is not launched",
                   reasons=[why])
        return out
    if b is None:
        out.update(state="need-B", next="launch experiment-reviewer run B (fresh, blind to A)")
        return out
    vb = _v(b)
    if vb not in rs.POSITIVE:
        out.update(state="not-cleared", next="report both runs; file the blocking step",
                   reasons=["run B: %s" % (vb or b.get("verdict"))])
        return out
    va = _v(a)
    reasons = []
    if va != vb:
        reasons.append("the runs disagree: A %s, B %s" % (va, vb))
    ca, cb = str(a.get("commit") or ""), str(b.get("commit") or "")
    if ca and cb and ca != cb:
        reasons.append("the runs reviewed different commits (%s, %s)" % (ca, cb))
    oa, ob = a.get("outcome"), b.get("outcome")
    if oa != ob:
        reasons.append("the runs read the outcome differently (%s, %s)" % (oa, ob))
    if reasons:
        out.update(state="unresolved", reasons=reasons,
                   next="report both runs; the weaker run's blocking step is the next item")
        return out
    modulo = va == "SOUND MODULO"
    out["state"] = "cleared-modulo" if modulo else "cleared"
    if modulo:
        out["assumptions"] = [x.get("assumption") for x in (a, b) if x.get("assumption")]
    out["proposed_status"] = {"supports": "supported", "refutes": "refuted"}.get(oa)
    gp = []
    if not ca:
        gp.append("no commit hash in the review record")
    if not (a.get("validation") == "passed" and b.get("validation") == "passed"):
        gp.append("the validation case is not recorded as passed by both runs")
    if out["proposed_status"] is None:
        gp.append("outcome %s proposes no status" % oa)
    out["grounds_problems"] = gp
    out["grounds"] = {
        "basis": "computation",
        # the landed runs are experiment-reviewer's (land_review.py lands no other agent);
        # what they graded is an experiment, the Scientist experimenter's work
        "producer_role": "experimenter",
        "verdicts": [{"verdict": _v(x), "run_id": str(x.get("run_id") or x["path"]),
                      "commit": str(x.get("commit") or ""),
                      "grader_role": "experiment-reviewer", "ref": _ref(x["path"])}
                     for x in (a, b)],
        "commit": ca,
        "validation_passed": not any("validation" in p for p in gp),
        "outcome": oa,
        "note": "experiment review pair: %s; %s" % (a["path"], b["path"]),
    }
    if modulo:
        out["grounds"]["modulo"] = out["assumptions"]
    out["next"] = ("claim-keeper: claims_set_status %s with these grounds" %
                   out["proposed_status"] if not gp else
                   "report: cleared, but the grounds are incomplete (%s)" % "; ".join(gp))
    return out


def pending(audits):
    """Subjects whose current pair has a positive A and no B yet."""
    out = []
    if not os.path.isdir(audits):
        return out
    for slug in sorted(os.listdir(audits)):
        folder = os.path.join(audits, slug)
        if slug.startswith("_") or not os.path.isdir(folder):
            continue
        runs = load_runs(audits, slug)
        if runs and decide(runs)["state"] == "need-B":
            out.append(runs[-1].get("subject") or slug)
    return out


def brief(subject, run, result=None, ticket=None, report=None):
    lines = [
        "Review one computed result. You are run %s of an experiment-review pair; another "
        "run may exist, and you must not look for it or account for it." % run,
        "Subject: %s." % subject,
    ]
    if result:
        lines.append("Result: %s." % result)
    if report:
        lines.append("Experiment report packet: %s (read it with packets_get)." % report)
    if ticket:
        lines.append("Ticket: %s." % ticket)
    lines.append("Follow your agent definition and the checklist "
                 "skills/review-experiment/checklist.md. End with the '## Review record' "
                 "block, Run: %s." % run)
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home", help="the Researcher home (default: from the cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "decide"):
        p = sub.add_parser(name)
        p.add_argument("subject")
        p.add_argument("--json", action="store_true")
    p = sub.add_parser("pending")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("brief")
    p.add_argument("subject")
    p.add_argument("--run", required=True, choices=("A", "B"))
    p.add_argument("--result")
    p.add_argument("--ticket")
    p.add_argument("--report")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "brief":
            print(brief(args.subject, args.run, args.result, args.ticket, args.report))
            return 0
        audits = audits_dir(args.home or os.getcwd())
        if args.cmd == "pending":
            subs = pending(audits)
            print(json.dumps(subs) if args.json else ("\n".join(subs) or "(none)"))
            return 0
        runs = load_runs(audits, args.subject)
        if args.cmd == "list":
            rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in runs]
            if args.json:
                print(json.dumps(rows, ensure_ascii=False, indent=1))
            else:
                for r in rows:
                    print("%s  run %s  %-12s %s%s" % (r.get("landed"), r["run"],
                                                     r.get("verdict"), r["path"],
                                                     "  (capped)" if r.get("capped") else ""))
                if not rows:
                    print("(no landed runs for %s)" % args.subject)
            return 0 if rows else 1
        d = decide(runs)
        if args.json:
            print(json.dumps(d, ensure_ascii=False, indent=1))
        else:
            print("%s: %s -- next: %s" % (args.subject, d["state"], d["next"]))
            for r in d["reasons"] + d["grounds_problems"]:
                print("  - %s" % r)
            if d["proposed_status"]:
                print("  proposed status: %s" % d["proposed_status"])
        return 0
    except ac.AcademyError as exc:
        sys.stderr.write("reviews.py: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
