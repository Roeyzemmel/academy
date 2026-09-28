"""decision_table.py -- the proof-review decision table, applied mechanically.

    py decision_table.py A.md [B.md|-] [--established id1,id2] [--primary fable,opus-5.5] [--json]

Takes the verdict records of run A and (optionally) run B -- files landed by
``land_verdict.py`` under ``<expert home>/reviews/<ns>/<id>/<pass>/`` or any text
ending in a ``VERDICT`` block -- and prints the outcome. The review-chair runs it
and follows it; it never substitutes its own reading (roster-rules.md, rule 3).

The table (from the old /paper:verify, in the academy's verdict words):

| Run A | Run B | Outcome |
|---|---|---|
| CONFIRMED | not yet run | ``awaiting-b``: launch B with the identical brief |
| CONFIRMED | CONFIRMED, no inputs on either | ``confirmed``: propose ``proved``; recolour earned |
| CONFIRMED modulo X | CONFIRMED modulo X (same set) | ``confirmed-modulo``: propose ``proved-modulo``; recolour only if every input in X is established |
| CONFIRMED (modulo X) | CONFIRMED modulo Y, Y != X | ``disagreement`` |
| CONFIRMED | GAP | ``disagreement``: no status; file the weaker run's blocking step |
| DISPROVED (either run) | any | ``disproved``: no status; the counterexample goes to Roey at once |
| GAP | not run | ``single-negative``: no status; A's blocking step is the repair item; B skipped by design |
| PLAUSIBLE (either run) | any non-DISPROVED | ``degraded``: a fallback verdict never counts; re-run that run on a primary |
| two CONFIRMED with a shared run id, differing statement hashes or subjects | | ``invalid-pair``: no status; the pair is not two independent reviews of one statement |
| anything else | | ``no-change``: report the union of the findings (a fallback: with the four verdict words and the sequencing rule no input reaches it) |
| run A missing or unreadable | | ``incomplete`` |

Mechanical rules applied before the table:

* The primaries are ``PRIMARY_MODELS`` = Fable and Opus 5.5, equal in authority
  (Roey, 2026-09-24, reconfirmed 2026-09-28); ``--primary`` takes a comma-separated
  list and defaults to both. A CONFIRMED given on any other model (Sonnet, Haiku, an
  older Opus, a bare ``opus`` that names no version, or no model at all) is read as
  PLAUSIBLE (roster-rules.md, "Graders degrade"). Every run's recorded model is kept
  in ``runs[].model``.
* B present after a non-CONFIRMED A is a process anomaly (B should not have run);
  it is reported, and the outcome is taken from A alone.

Exit code: 0 on an outcome, 2 on a usage error. The JSON carries ``grounds`` in the
shape ``claims_propose_status`` / ``check_grounds`` expect.
"""

import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _academy as ac  # noqa: E402

VERDICTS = ("CONFIRMED", "PLAUSIBLE", "GAP", "DISPROVED")
FIELDS = ("subject", "pass", "run", "run_id", "verdict", "modulo", "model",
          "statement_hash", "blocking", "ticket")
NONE_WORDS = ("", "none", "-", "n/a", "[]", "null")

OUTCOMES = ("awaiting-b", "confirmed", "confirmed-modulo", "disagreement", "disproved",
            "single-negative", "degraded", "invalid-pair", "no-change", "incomplete")


# ----------------------------------------------------------------------------
# Statement hash
# ----------------------------------------------------------------------------

_CACHE = {}


def _engine_statement_hash_of():
    """``registry.core.model.statement_hash_of``, imported so this hash is always the
    engine's own -- the text ``py -m registry statement <ns:id>`` hashes -- rather than
    a reimplementation that could silently drift from it. Falls back to an identical
    local copy if the registry package cannot be found on this machine."""
    if "fn" not in _CACHE:
        try:
            plugin = os.path.join(ac.repo_root(), "academy")
            if plugin not in sys.path:
                sys.path.insert(0, plugin)
            from registry.core.model import statement_hash_of as fn
        except ImportError:
            def fn(text):
                norm = " ".join(str(text or "").split())
                return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
        _CACHE["fn"] = fn
    return _CACHE["fn"]


def statement_hash(text):
    """sha256 of the statement with all whitespace collapsed, first 16 hex digits --
    the same computation as ``py -m registry statement <ns:id>``, imported from the
    registry engine when it can be found (see ``_engine_statement_hash_of``)."""
    return _engine_statement_hash_of()(text)


# ----------------------------------------------------------------------------
# Parsing a verdict
# ----------------------------------------------------------------------------

RE_FIELD = re.compile(r"^\s*([A-Za-z_]+)\s*:\s*(.*?)\s*$")


def _split_list(v):
    if isinstance(v, list):
        items = v
    else:
        s = str(v or "").strip()
        if s.lower() in NONE_WORDS:
            return []
        s = s.strip("[]")
        items = re.split(r"[,;]", s)
    out = []
    for it in items:
        it = str(it).strip().strip("`'\"")
        if it and it.lower() not in NONE_WORDS:
            out.append(it)
    return out


def norm_verdict(v):
    """One of VERDICTS, or '' if ``v`` is not a verdict word.

    Accepts the word alone or followed by commentary (``CONFIRMED (on fable)``);
    the old six statuses are *not* accepted: a reviewer must use the four words.
    """
    s = " ".join(str(v or "").upper().replace("_", " ").split())
    for w in VERDICTS:
        if s == w or s.startswith(w + " ") or s.startswith(w + "(") or s.startswith(w + ","):
            return w
    return ""


def parse_verdict_block(text):
    """The fields of the last ``VERDICT`` block in ``text`` (a dict), or None.

    The block is a line reading ``VERDICT`` followed by ``key: value`` lines, up
    to a blank line, a code fence or the end. Keys are lower-cased.
    """
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().strip("`*#: ").upper() == "VERDICT":
            start = i
    if start is None:
        return None
    out = {}
    for ln in lines[start + 1:]:
        if not ln.strip() or ln.strip().startswith("```"):
            if out:
                break
            continue
        m = RE_FIELD.match(ln)
        if not m:
            break
        out[m.group(1).lower()] = m.group(2)
    return out or None


def parse_record(text):
    """A verdict record from a landed file (frontmatter) or a raw report (VERDICT block).

    Returns a dict with the FIELDS (``modulo`` a list, ``verdict`` normalised, ''
    when missing) plus ``problems`` (list of strings) and ``raw_verdict``.
    """
    fields = None
    if str(text or "").lstrip().startswith("---"):
        try:
            meta, _body = ac.read_frontmatter(text)
            fields = {k: meta.get(k) for k in FIELDS if k in meta}
        except ac.AcademyError:
            fields = None
    if fields is None or not fields.get("verdict"):
        block = parse_verdict_block(text)
        if block is not None:
            fields = dict(fields or {})
            fields.update(block)
    rec = {k: "" for k in FIELDS}
    rec["modulo"] = []
    rec["problems"] = []
    if not fields:
        rec["problems"].append("no VERDICT block or verdict record found")
        rec["raw_verdict"] = ""
        return rec
    for k in FIELDS:
        v = fields.get(k)
        if k == "modulo":
            rec[k] = _split_list(v)
        else:
            rec[k] = "" if v is None else str(v).strip()
    rec["raw_verdict"] = rec["verdict"]
    rec["verdict"] = norm_verdict(rec["verdict"])
    if not rec["verdict"]:
        rec["problems"].append("verdict %r is not one of %s"
                               % (rec["raw_verdict"], ", ".join(VERDICTS)))
    if rec["blocking"].lower() in NONE_WORDS:
        rec["blocking"] = ""
    return rec


def read_record(path):
    if path in (None, "", "-"):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        rec = parse_record(fh.read())
    rec["file"] = path
    return rec


# ----------------------------------------------------------------------------
# The table
# ----------------------------------------------------------------------------

PRIMARY_MODELS = ("fable", "opus-5.5")

RE_OPUS_55 = re.compile(r"opus-?5-5(?![0-9])")


def model_label(name):
    """A model name reduced to the label the roster rules use: ``fable``, ``opus-5.5``,
    or the family (``opus``, ``sonnet``, ``haiku``) of any other model; the name itself
    (lower-cased) when it names no known family, '' when empty.

    ``claude-opus-5-5``, ``claude-opus-5-5[1m]``, ``Opus 5.5`` and ``opus-5.5`` all
    read as ``opus-5.5``; a bare ``opus`` names no version and reads as ``opus``."""
    n = str(name or "").strip().lower()
    if not n:
        return ""
    k = re.sub(r"[\s_.]+", "-", n)
    if "fable" in k:
        return "fable"
    if RE_OPUS_55.search(k):
        return "opus-5.5"
    for fam in ("opus", "sonnet", "haiku"):
        if fam in k:
            return fam
    return n


def _primaries(primary=None):
    if primary is None:
        primary = PRIMARY_MODELS
    if isinstance(primary, str):
        primary = [p for p in re.split(r"[,;]", primary) if p.strip()]
    return tuple(sorted({model_label(p) for p in primary if model_label(p)}))


def is_primary(model, primary=None):
    """True when ``model`` is one of the primaries (default ``PRIMARY_MODELS``)."""
    lab = model_label(model)
    return bool(lab) and lab in _primaries(primary)


def effective(rec, primary=None):
    """(verdict, note): CONFIRMED on a non-primary model reads as PLAUSIBLE."""
    v = rec["verdict"]
    if v == "CONFIRMED" and not is_primary(rec.get("model"), primary):
        return "PLAUSIBLE", ("run %s: CONFIRMED on %r, not a primary (%s): read as "
                             "PLAUSIBLE" % (rec.get("run") or "?", rec.get("model") or "an "
                                            "unnamed model", ", ".join(_primaries(primary))))
    return v, ""


def should_launch_b(rec_a, primary=None):
    """Run B is launched only after a positive run A (CONFIRMED on a primary)."""
    if not rec_a or rec_a["problems"]:
        return False
    return effective(rec_a, primary)[0] == "CONFIRMED"


GRADER_ROLE = "expert"    # every proof review here is run by an Expert instance


def producer_role_for(subject, override=None, workspace=None):
    """The role of the instance that produced the reviewed proof: the role that owns
    ``subject``'s namespace in workspace.json (``paper:`` -> ``author``, ``s1:`` ->
    ``researcher``, ``lab:`` -> ``scientist``). ``override`` (a CLI flag) always wins;
    '' when the namespace has no owning instance or workspace.json cannot be read."""
    if override:
        return override
    ns = str(subject or "").split(":", 1)[0].strip()
    if not ns:
        return ""
    try:
        ws = workspace if workspace is not None else ac.load_workspace()
    except ac.AcademyError:
        return ""
    for inst in ws.get("instances", {}).values():
        if inst.get("ns") == ns:
            return inst.get("role") or ""
    return ""


def _grounds(recs, modulo, note, producer_role=""):
    rows = [{"verdict": r["_eff"], "run_id": r.get("run_id") or "",
             "statement_hash": r.get("statement_hash") or "",
             "grader_role": GRADER_ROLE,
             "ref": r.get("file") or ""} for r in recs]
    g = {"basis": "proof", "verdicts": rows, "note": note}
    if producer_role:
        g["producer_role"] = producer_role
    hashes = {r.get("statement_hash") for r in recs if r.get("statement_hash")}
    if len(hashes) == 1:
        g["statement_hash"] = hashes.pop()
    if modulo:
        g["modulo"] = list(modulo)
    return g


def decide(rec_a, rec_b=None, established=(), primary=None, producer_role=None):
    """Apply the table. ``rec_a`` / ``rec_b`` come from ``parse_record``; ``rec_b``
    may be None (not launched). ``established`` lists the modulo inputs known to be
    established (registry ``proved`` or a verified citation card). ``producer_role``
    overrides the namespace-owner lookup (``producer_role_for``) when given."""
    res = {"outcome": "", "launch_b": False, "proposed_status": None, "recolour": False,
           "needs_human": False, "modulo": [], "pending_inputs": [], "file_items": [],
           "anomalies": [], "grounds": None, "summary": "", "runs": []}
    established = set(established or ())

    if rec_a is None or rec_a["problems"]:
        res["outcome"] = "incomplete"
        res["summary"] = "run A has no readable verdict: nothing to conclude"
        if rec_a:
            res["anomalies"].extend("run A: " + p for p in rec_a["problems"])
        return res

    prod_role = producer_role_for(rec_a.get("subject"), producer_role)

    recs = [rec_a] + ([rec_b] if rec_b is not None else [])
    for r in recs:
        eff, note = effective(r, primary)
        r["_eff"] = eff
        if note:
            res["anomalies"].append(note)
    if rec_b is not None and rec_b["problems"]:
        res["anomalies"].extend("run B: " + p for p in rec_b["problems"])
    for r in recs:
        res["runs"].append({k: r.get(k) for k in ("run", "run_id", "verdict", "model",
                                                   "modulo", "statement_hash", "blocking",
                                                   "file")})
        res["runs"][-1]["effective"] = r["_eff"]

    a = rec_a["_eff"]
    b = rec_b["_eff"] if rec_b is not None and not rec_b["problems"] else None

    if rec_b is not None and a != "CONFIRMED":
        res["anomalies"].append("run B was launched after a non-positive run A (%s); "
                                "the outcome is taken from A alone" % a)
        b = None
        recs = [rec_a]

    # DISPROVED dominates.
    if a == "DISPROVED" or b == "DISPROVED":
        res["outcome"] = "disproved"
        res["needs_human"] = True
        who = [r for r in recs if r["_eff"] == "DISPROVED"]
        res["file_items"] = [{"run": r.get("run"), "kind": "counterexample",
                              "text": r.get("blocking") or "see the run's report"}
                             for r in who]
        if len(recs) == 2 and a == b == "DISPROVED" and _pair_ok(rec_a, rec_b, res):
            res["proposed_status"] = "refuted"
            res["grounds"] = _grounds(recs, [], "two DISPROVED verdicts", prod_role)
            res["summary"] = "both runs DISPROVED: propose refuted"
        else:
            res["summary"] = ("DISPROVED by run %s: no status change; the counterexample "
                              "goes to Roey at once" % ", ".join(r.get("run") or "?"
                                                                 for r in who))
        return res

    if b is None:
        if a == "CONFIRMED":
            if rec_b is not None:        # B present but unreadable
                res["outcome"] = "incomplete"
                res["summary"] = "run B has no readable verdict: conclude nothing yet"
                return res
            res["outcome"] = "awaiting-b"
            res["launch_b"] = True
            res["summary"] = "A is CONFIRMED: launch run B with the identical brief"
            return res
        if a == "PLAUSIBLE":
            res["outcome"] = "degraded"
            res["summary"] = ("A is PLAUSIBLE (fallback or reduced strength): it never "
                              "counts; re-run A on a primary model (%s)"
                              % ", ".join(_primaries(primary)))
            return res
        res["outcome"] = "single-negative"
        res["file_items"] = [{"run": rec_a.get("run") or "A", "kind": "repair",
                              "text": rec_a.get("blocking") or "see run A's report"}]
        res["summary"] = "A is GAP: no status change; file A's blocking step; B skipped by design"
        return res

    if "PLAUSIBLE" in (a, b):
        res["outcome"] = "degraded"
        res["summary"] = ("a PLAUSIBLE verdict never counts toward two agreeing verdicts: "
                          "re-run the PLAUSIBLE run on a primary model (%s)"
                          % ", ".join(_primaries(primary)))
        return res

    if a == b == "CONFIRMED":
        if not _pair_ok(rec_a, rec_b, res):
            res["outcome"] = "invalid-pair"
            res["summary"] = "the two runs are not independent reviews of one statement"
            return res
        ma, mb = set(rec_a["modulo"]), set(rec_b["modulo"])
        if ma != mb:
            res["outcome"] = "disagreement"
            res["modulo"] = sorted(ma | mb)
            res["file_items"] = [{"run": "A+B", "kind": "inputs",
                                  "text": "the runs name different inputs: A %s, B %s"
                                          % (sorted(ma) or "none", sorted(mb) or "none")}]
            res["summary"] = "both CONFIRMED but on different inputs: no status change"
            return res
        if not ma:
            res["outcome"] = "confirmed"
            res["proposed_status"] = "proved"
            res["recolour"] = True
            res["grounds"] = _grounds(recs, [], "two CONFIRMED verdicts, no open inputs",
                                      prod_role)
            res["summary"] = "CONFIRMED x2: propose proved; recolour earned"
            return res
        res["outcome"] = "confirmed-modulo"
        res["modulo"] = sorted(ma)
        res["pending_inputs"] = sorted(ma - established)
        res["proposed_status"] = "proved-modulo"
        res["recolour"] = not res["pending_inputs"]
        res["grounds"] = _grounds(recs, sorted(ma), "two CONFIRMED verdicts modulo %s"
                                  % ", ".join(sorted(ma)), prod_role)
        res["file_items"] = [{"run": "A+B", "kind": "verify-input", "text": i}
                             for i in res["pending_inputs"]]
        res["summary"] = ("CONFIRMED x2 modulo %s: propose proved-modulo; %s"
                          % (", ".join(sorted(ma)),
                             "recolour earned (every input established)" if res["recolour"]
                             else "stays sketch until %s are established"
                             % ", ".join(res["pending_inputs"])))
        return res

    if a == "CONFIRMED" and b == "GAP":
        res["outcome"] = "disagreement"
        res["file_items"] = [{"run": rec_b.get("run") or "B", "kind": "repair",
                              "text": rec_b.get("blocking") or "see run B's report"}]
        res["summary"] = ("A CONFIRMED, B GAP: no status change; relay both reports and "
                          "file B's blocking step")
        return res

    res["outcome"] = "no-change"
    res["file_items"] = [{"run": r.get("run"), "kind": "repair", "text": r.get("blocking")}
                         for r in recs if r.get("blocking")]
    res["summary"] = "no status change; report the union of the findings"
    return res


def _pair_ok(ra, rb, res):
    ok = True
    ia, ib = ra.get("run_id"), rb.get("run_id")
    if not ia or not ib:
        res["anomalies"].append("a run has no run_id")
        ok = False
    elif ia == ib:
        res["anomalies"].append("runs A and B share the run id %s" % ia)
        ok = False
    ha, hb = ra.get("statement_hash"), rb.get("statement_hash")
    if not ha or not hb:
        res["anomalies"].append("a run has no statement_hash")
        ok = False
    elif ha != hb:
        res["anomalies"].append("statement hashes differ (A %s, B %s): the statement "
                                "changed between the runs" % (ha, hb))
        ok = False
    sa, sb = ra.get("subject"), rb.get("subject")
    if sa and sb and sa != sb:
        res["anomalies"].append("subjects differ (A %s, B %s)" % (sa, sb))
        ok = False
    return ok


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _text(res):
    out = ["outcome: %s" % res["outcome"], "summary: %s" % res["summary"]]
    if res["launch_b"]:
        out.append("next: launch run B")
    if res["proposed_status"]:
        out.append("propose: %s" % res["proposed_status"])
    out.append("recolour: %s" % ("yes" if res["recolour"] else "no"))
    if res["modulo"]:
        out.append("modulo: %s" % ", ".join(res["modulo"]))
    if res["pending_inputs"]:
        out.append("pending inputs: %s" % ", ".join(res["pending_inputs"]))
    for it in res["file_items"]:
        out.append("file (%s, run %s): %s" % (it["kind"], it["run"], it["text"]))
    for an in res["anomalies"]:
        out.append("anomaly: %s" % an)
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("a", help="run A's verdict file")
    ap.add_argument("b", nargs="?", default=None, help="run B's verdict file, or - / omitted")
    ap.add_argument("--established", default="",
                    help="comma-separated modulo inputs known to be established")
    ap.add_argument("--primary", default=",".join(PRIMARY_MODELS),
                    help="comma-separated primary models (default: fable,opus-5.5)")
    ap.add_argument("--producer-role", default=None,
                    help="override the namespace-owner lookup for grounds.producer_role")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        ra = read_record(args.a)
        rb = read_record(args.b)
    except OSError as exc:
        sys.stderr.write("decision_table: %s\n" % exc)
        return 2
    res = decide(ra, rb, _split_list(args.established), args.primary, args.producer_role)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(json.dumps(res, indent=2, ensure_ascii=False) if args.json else _text(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
