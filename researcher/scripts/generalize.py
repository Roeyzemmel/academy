"""generalize.py -- from a reviewed experiment's conclusion to conjectures with falsifiers.

Plan section 3.3 (``generalize``) and docs/protocol.md section 6.2. The model work
(proposing the generalizations) is ``prover``'s; this script does the bookkeeping around
it and enforces the rules:

* the input is an ``experiment-report`` packet whose experiment review has **cleared**
  (``reviews.py decide`` on its lab claim: cleared or cleared-modulo);
* at most ``researcher.generalize.maxPerRun`` (default 3) proposals per run;
* every proposal is an object of kind ``conjecture`` with status ``conjectured`` --
  never higher (``researcher.generalize.raiseAbove``) -- with ``bears_on`` naming the lab
  claim and a non-empty **falsifier** (the smallest case where it could fail);
* one ``test`` ticket per proposal goes to the Scientist, ``parent`` the generalize
  ticket, ``refs`` the new id and the lab claim, the ask "test the falsifier first".

Usage (from a Researcher home, or with --home):

    py generalize.py source P-NNNN|<ns>:<lab-id> [--json]
    py generalize.py validate FILE --lab-claim <ns>:<id> [--json]
    py generalize.py create FILE --lab-claim <ns>:<id> [--apply]     the conjectured objects
    py generalize.py tickets FILE --lab-claim <ns>:<id> --parent T-NNNN [--to scientist@x]
                              [--as researcher@x] [--apply]
    py generalize.py packet-body FILE --lab-claim <ns>:<id> --report P-NNNN --out PATH

The proposals FILE is JSON, a list (or {"proposals": [...]}) of

    {"id": "nb:GEN-3", "title": "...", "statement": "...", "kind": "conjecture",
     "status": "conjectured", "bears_on": ["lab:x"], "falsifier": "...",
     "pattern": "wider class | relaxed hypothesis | pattern | invariant",
     "rationale": "why the data suggests it"}

``tickets`` prints the board.py command lines it would run; ``--apply`` runs them (as
the instance, through the base plugin's board.py). Exit codes: 0 ok, 1 nothing, 2 error.
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402
import _researcher as rs  # noqa: E402
import reviews  # noqa: E402

PATTERNS = ("wider class", "relaxed hypothesis", "pattern", "invariant")
CLEARED = ("cleared", "cleared-modulo")
RE_ID = re.compile(r"^[a-z0-9]+:[A-Za-z0-9][A-Za-z0-9._:-]*$")


def _board():
    return ac.load_workspace()["board"]


def _section(body, heading):
    lines, cur, out = body.replace("\r\n", "\n").split("\n"), False, []
    for ln in lines:
        if ln.startswith("## "):
            cur = ln[3:].strip().lower() == heading.lower()
            continue
        if cur:
            out.append(ln)
    return "\n".join(out).strip()


def _read_packet(path):
    meta, body = ac.read_frontmatter(rs.read_text(path) or "")
    return meta, body


def find_report(board, ref):
    """The experiment-report packet for ``ref`` (a packet id, or a lab claim id)."""
    if ac.RE_PACKET_ID.match(ref):
        path = ac.find_packet(board, ref)
        if not path:
            raise ac.AcademyError("no packet %s on the board" % ref)
        return path
    best = None
    root = os.path.join(board, "packets")
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if not re.match(r"^P-\d{4,}-.*\.md$", f):
                continue
            path = os.path.join(dirpath, f)
            try:
                meta, _ = _read_packet(path)
            except ac.AcademyError:
                continue
            if meta.get("kind") == "experiment-report" and ref in (meta.get("subject") or []):
                num = int(str(meta.get("packet", "P-0")).split("-")[1])
                if best is None or num > best[0]:
                    best = (num, path)
    if not best:
        raise ac.AcademyError("no experiment-report packet has %s in its subject" % ref)
    return best[1]


def lab_ids(meta, lab_namespaces):
    return [s for s in (meta.get("subject") or [])
            if isinstance(s, str) and s.split(":", 1)[0] in lab_namespaces]


def _lab_namespaces():
    ws = rs.workspace_or_none() or {}
    ns = [i.get("ns") for i in ws.get("instances", {}).values()
          if i.get("role") == "scientist" and i.get("ns")]
    return ns or ["lab"]


def source(home, ref):
    """The conclusion to generalize from, and the review state of its lab claim(s)."""
    path = find_report(_board(), ref)
    meta, body = _read_packet(path)
    if meta.get("kind") != "experiment-report":
        raise ac.AcademyError("%s is a %s packet, not an experiment-report"
                              % (meta.get("packet"), meta.get("kind")))
    conclusion = _section(body, "Conclusion")
    if not conclusion:
        raise ac.AcademyError("%s has no ## Conclusion" % meta.get("packet"))
    labs = lab_ids(meta, _lab_namespaces())
    if not labs and not ac.RE_PACKET_ID.match(ref):
        labs = [ref]
    if not labs:
        raise ac.AcademyError("%s names no lab claim in its subject" % meta.get("packet"))
    audits = reviews.audits_dir(home)
    states = {lab: reviews.decide(reviews.load_runs(audits, lab))["state"] for lab in labs}
    return {"packet": meta.get("packet"), "path": path.replace("\\", "/"),
            "title": meta.get("title"), "lab_claims": labs, "review": states,
            "reviewed": all(s in CLEARED for s in states.values()),
            "conclusion": conclusion, "ticket": meta.get("ticket")}


def load_proposals(path):
    with open(path, "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("proposals", [])
    if not isinstance(data, list) or not all(isinstance(p, dict) for p in data):
        raise ac.AcademyError("proposals must be a list of objects")
    return data


def settings(home):
    _, cfg, inst = rs.researcher_home(home)
    gen = ((cfg or {}).get("researcher") or {}).get("generalize") or {}
    ws = rs.workspace_or_none() or {}
    winst = ws.get("instances", {}).get(inst or "", {})
    ns = (cfg or {}).get("ns") or winst.get("ns")
    lab = ((cfg or {}).get("researcher") or {}).get("lab")
    if not lab:
        doms = set(winst.get("domains") or [])
        lab = next((n for n, i in ws.get("instances", {}).items()
                    if i.get("role") == "scientist" and doms & set(i.get("domains") or [])),
                   None)
    return {"instance": inst, "ns": ns, "lab": lab,
            "max": min(int(gen.get("maxPerRun", 3)), 3),
            "ceiling": gen.get("raiseAbove", "conjectured")}


def validate(proposals, lab_claim, st):
    """List of problems (empty when every proposal may be filed)."""
    probs = []
    if not proposals:
        probs.append("no proposals")
    if len(proposals) > st["max"]:
        probs.append("%d proposals; at most %d per run" % (len(proposals), st["max"]))
    seen = set()
    for i, p in enumerate(proposals, 1):
        tag = p.get("id") or "#%d" % i
        pid = p.get("id") or ""
        if not RE_ID.match(pid):
            probs.append("%s: id must be '<ns>:<id>'" % tag)
        elif st["ns"] and pid.split(":", 1)[0] != st["ns"]:
            probs.append("%s: id must be in this instance's namespace %r" % (tag, st["ns"]))
        if pid in seen:
            probs.append("%s: duplicate id" % tag)
        seen.add(pid)
        for f in ("title", "statement", "falsifier"):
            if not str(p.get(f) or "").strip():
                probs.append("%s: %s is required" % (tag, f))
        if (p.get("kind") or "conjecture") != "conjecture":
            probs.append("%s: kind must be conjecture" % tag)
        status = p.get("status") or "conjectured"
        if status != st["ceiling"]:
            probs.append("%s: status must be %s (generalize never raises above it), not %r"
                         % (tag, st["ceiling"], status))
        if lab_claim not in (p.get("bears_on") or []):
            probs.append("%s: bears_on must include %s" % (tag, lab_claim))
        pat = str(p.get("pattern") or "").lower()
        if pat and pat not in PATTERNS:
            probs.append("%s: pattern must be one of %s" % (tag, ", ".join(PATTERNS)))
    return probs


def create_objects(home, proposals, lab_claim, apply=False):
    """Write one conjectured object per proposal (objects/conjecture/<id>.md)."""
    import notebook
    nb = notebook.Notebook(home)
    out = []
    for p in proposals:
        oid = nb.bare(p["id"])
        path = os.path.join(nb.paths["objects"], "conjecture", oid + ".md")
        if apply:
            bears = list(p.get("bears_on") or [])
            path = nb.new_object("conjecture", oid, p["title"], p["statement"],
                                 "conjectured", bears, p.get("depends_on") or [],
                                 p["falsifier"], ["generalization"],
                                 by="researcher/generalize from %s" % lab_claim)
        out.append(path.replace("\\", "/"))
    return out


def board_script():
    return os.path.join(ac.repo_root(), "academy", "scripts", "board.py")


def ticket_commands(proposals, lab_claim, parent, to, as_instance):
    cmds = []
    for p in proposals:
        detail = ("Generalization %s (%s), proposed from %s.\n\nStatement: %s\n\n"
                  "Falsifier (test this first): %s\n\nRationale: %s"
                  % (p["id"], p.get("pattern") or "generalization", lab_claim,
                     p["statement"], p["falsifier"], p.get("rationale") or "-"))
        cmds.append([sys.executable, board_script(), "new", "--to", to,
                     "--title", "Test generalization %s" % p["id"],
                     "--kind", "test",
                     "--ask", "Test %s, starting from its falsifier." % p["id"],
                     "--deliverable", "An experiment-report packet whose ## Conclusion "
                     "says whether the falsifier (and then the class) refutes %s." % p["id"],
                     "--refs", "%s,%s" % (p["id"], lab_claim),
                     "--parent", parent, "--detail", detail, "--as", as_instance,
                     "--agent", "main"])
    return cmds


def packet_body(proposals, lab_claim, report, src_state=""):
    lines = ["", "## Summary", "",
             "%d generalization(s) of %s proposed from report %s, each conjectured with a "
             "falsifier." % (len(proposals), lab_claim, report),
             "Each goes to the Scientist as one test ticket; none is raised above "
             "conjectured here.", "", "## Produced", ""]
    for p in proposals:
        lines.append("- `%s` (conjectured): %s" % (p["id"], p["title"]))
    lines += ["", "## Established vs assumed", ""]
    lines.append("- **Established:** %s is reviewed (%s) as reported in %s."
                 % (lab_claim, src_state or "cleared", report))
    for p in proposals:
        lines.append("- **Not established:** %s (conjectured); falsifier: %s"
                     % (p["id"], p["falsifier"]))
    lines += ["", "## Evidence", "", "- Report %s, its `## Conclusion`." % report,
              "- Experiment review of %s: `reviews.py decide %s`." % (lab_claim, lab_claim),
              "", "## Decisions needed", "", "None.", "", "## Machine notes", ""]
    notes = [p.get("rationale") for p in proposals if p.get("rationale")]
    if notes:
        for p in proposals:
            if p.get("rationale"):
                lines.append("- prover: %s: %s" % (p["id"], p["rationale"]))
    else:
        lines.append("None.")
    lines += ["", "## Decision", ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("source"); p.add_argument("ref"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("validate"); p.add_argument("file"); p.add_argument("--lab-claim", required=True)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("create"); p.add_argument("file"); p.add_argument("--lab-claim", required=True)
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("tickets"); p.add_argument("file"); p.add_argument("--lab-claim", required=True)
    p.add_argument("--parent", required=True); p.add_argument("--to"); p.add_argument("--as", dest="as_instance")
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("packet-body"); p.add_argument("file"); p.add_argument("--lab-claim", required=True)
    p.add_argument("--report", required=True); p.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    home = args.home or os.getcwd()
    try:
        if args.cmd == "source":
            s = source(home, args.ref)
            if args.json:
                print(json.dumps(s, ensure_ascii=False, indent=1))
            else:
                print("%s  %s" % (s["packet"], s["title"]))
                print("lab claims: %s" % ", ".join("%s (%s)" % kv for kv in s["review"].items()))
                print("reviewed: %s" % ("yes" if s["reviewed"] else "NO"))
                print("\n## Conclusion\n\n" + s["conclusion"])
            if not s["reviewed"]:
                sys.stderr.write("generalize.py: the experiment review has not cleared; "
                                 "generalize only from a reviewed report\n")
                return 2
            return 0
        st = settings(home)
        proposals = load_proposals(args.file)
        probs = validate(proposals, args.lab_claim, st)
        if args.cmd == "validate":
            if args.json:
                print(json.dumps({"ok": not probs, "problems": probs}, indent=1))
            else:
                print("ok" if not probs else "\n".join("- " + x for x in probs))
            return 0 if not probs else 2
        if probs:
            raise ac.AcademyError("proposals invalid: " + "; ".join(probs))
        if args.cmd == "create":
            for path in create_objects(home, proposals, args.lab_claim, args.apply):
                print(("created " if args.apply else "would create ") + path)
            return 0
        if args.cmd == "packet-body":
            ac.atomic_write(args.out, packet_body(proposals, args.lab_claim, args.report))
            print(os.path.abspath(args.out).replace("\\", "/"))
            return 0
        to = args.to or st["lab"]
        inst = args.as_instance or st["instance"]
        if not to or not inst:
            raise ac.AcademyError("cannot tell the Scientist instance or this instance; "
                                  "give --to and --as")
        cmds = ticket_commands(proposals, args.lab_claim, args.parent, to, inst)
        for c in cmds:
            if args.apply:
                res = subprocess.run(c, capture_output=True, timeout=60)
                out = (res.stdout + res.stderr).decode("utf-8", "replace").strip()
                print(out)
                if res.returncode != 0:
                    raise ac.AcademyError("board.py failed; the remaining tickets were not filed")
            else:
                print(" ".join(json.dumps(x) if " " in x else x for x in c))
        return 0
    except (ac.AcademyError, OSError, ValueError) as exc:
        sys.stderr.write("generalize.py: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
