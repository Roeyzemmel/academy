"""R5: the schema-v2 migration of every registry record (plan section 6, "One schema").

    py -m registry.migrate_v2 [--math C:/Work/Math] [--date YYYY-MM-DD]
                              [--report FILE] [--mapping-json FILE] [--packet-body FILE]
                              [--proposed-reviews DIR] [--snapshot DIR] [--apply]

It rewrites every claim, assumption and example record of the three migration worktrees
(``<math>/FlatSurfLab-academy`` for ``lab:``, ``<math>/BilliardIllumination-academy``
for ``paper:``, ``<math>/Slope1illuminationResearch-academy`` for ``s1:``) into the
academy object schema (``core/schema.py``). Without ``--apply`` it only computes and
writes the reports; with it, it also writes the records (LF) and the Partial splits.
It refuses a home whose directory does not end in ``-academy`` (the main checkouts are
never touched).

What it decides mechanically, and what it leaves for Roey (every one of these is listed
in the mapping report and in the review packet body):

* **Statuses.** lab/paper keep their word; ``superseded``/``dropped`` move to the
  lifecycle, and the status under it is the last status the history recorded before
  the move (else ``open``). Slope1: ``Proved`` -> proved; ``Proved modulo stated
  inputs`` -> proved-modulo with ``modulo`` from the ``status_note`` ("modulo X, Y");
  ``Reduced`` -> proved-modulo with ``modulo`` the reduction target when an id names
  it, else a plain-text item marked ``UNRESOLVED-TARGET`` for Roey; ``Partial`` -> the
  parent becomes ``open`` and each proved case a new claim with status ``sketch`` (the
  case texts are proposals: :data:`PARTIAL_SPLITS`); ``Disproved`` -> refuted;
  ``Not settled`` -> by kind and proof state: an open problem or question -> open, a
  conjecture -> conjectured, a statement whose body has a ``## Proof`` -> sketch,
  one without -> open.
* **Fields.** Every old field is carried, renamed or mapped by :data:`FSL_MAP` /
  :data:`S1_MAP`; a field in neither table stops the migration. The statement is not
  copied into a ``statement`` field: it stays where it is (the body's ``## Statement``,
  the paper's LaTeX, the lab title), so no statement hash changes through it.
* **Evidence.** lab/paper rows gain the ``run_id`` cell (``-``); Slope1 ``cleared_by``
  and the verdicts that name a record become ``verdict`` rows, and an example's ``runs``
  become ``experiment`` rows. The verdict and run files stay where they are (evidence
  targets); their move into Expert's ``reviews/s1/<id>/`` is only proposed, as copies
  under ``--proposed-reviews``.
* **History.** Slope1's body ``## History`` becomes frontmatter rows, newest first; every
  record gains one row for this migration.

Checks (machine-checked, in the report): every old field mapped; every carried value
equal after a round trip through the dialect; every record's projection class
unchanged (the new split cases are additions); every statement hash unchanged or
listed; every old evidence and history row present in the new file.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

from .core import fm, projection, schema
from .core.model import statement_hash_of
from .profiles import fsl, s1kb

DOMAIN = "translation-surfaces"
HOMES = {"lab": "FlatSurfLab-academy", "paper": "BilliardIllumination-academy",
         "s1": "Slope1illuminationResearch-academy"}
FSL_DIRS = {"lab": "claims/lab", "paper": "claims/paper"}
S1_DIRS = (("claims", "claim"), ("assumptions", "assumption"), ("examples", "example"))

# --------------------------------------------------------------------- the field maps
#: old field -> (disposition, new field, how). Dispositions: carried (same name, same
#: value), renamed (same value, new name), mapped (value transformed), moved (into
#: evidence or history rows), derived (not stored: recomputed from other records).
FSL_MAP = {
    "id": ("carried", "id", ""),
    "title": ("carried", "title", "the lab title is also the statement"),
    "status": ("mapped", "status / lifecycle",
               "same word; superseded/dropped -> lifecycle, status = the last one before"),
    "where": ("carried", "where", "the file holding the statement or the experiment"),
    "bears_on": ("carried", "bears_on", ""),
    "depends_on": ("carried", "depends_on", ""),
    "supersedes": ("mapped", "supersedes", "scalar -> one-item list (one-way)"),
    "superseded_by": ("derived", "(derived)", "recomputed from the other side's supersedes"),
    "evidence": ("mapped", "evidence",
                 "`kind | ref | verdict | note` -> `type | ref | verdict | run_id | note`, "
                 "run_id `-`, an empty verdict `-`"),
    "history": ("mapped", "history", "rows kept verbatim; one migration row added on top"),
    "open": ("carried", "open", "lab/paper profile field (caveats and next steps); it becomes "
             "`modulo` only on a proved-modulo record, and no lab/paper record is one"),
    "tags": ("carried", "tags", ""),
}
FSL_NEW = {"kind": "lab: claim; paper: from the label prefix (PAPER_KINDS)",
           "lifecycle": "active, or the old superseded/dropped status",
           "domain": DOMAIN}

S1_MAP = {
    "id": ("carried", "id", ""),
    "aliases": ("carried", "aliases", ""),
    "title": ("carried", "title", ""),
    "summary": ("carried", "summary", "s1 profile field"),
    "kind": ("mapped", "kind + form",
             "kind = the v2 statement type (KIND_V2), form = the old kind"),
    "status": ("mapped", "status", "Slope1 label -> v2 word (see the status table)"),
    "status_note": ("carried", "status_note",
                    "s1 profile field; for proved-modulo also the source of `modulo`"),
    "level": ("carried", "level", "s1 profile field"),
    "status_by_level": ("mapped", "status_by_level", "values -> v2 words"),
    "topics": ("renamed", "tags", ""),
    "examples": ("carried", "examples", "s1 profile field"),
    "depends_on": ("carried", "depends_on", ""),
    "supersedes": ("mapped", "supersedes", "one-way list"),
    "superseded_by": ("derived", "(derived)", "recomputed from the other side's supersedes"),
    "cleared_by": ("moved", "evidence", "`verdict | <file> | <decision> | <verdict id> | "
                   "cleared_by` rows"),
    "source": ("carried", "source", "s1 profile field (provenance)"),
    "added": ("carried", "added", "s1 profile field"),
    "body_status_ack": ("carried", "body_status_ack", "s1 profile field"),
    "cites": ("carried", "cites", "s1 profile field (checked against the library)"),
    "old": ("carried", "old", "s1 profile field (the assumption's old label)"),
    "implies": ("carried", "implies", "s1 profile field (assumption graph)"),
    "implies_pending": ("carried", "implies_pending", "s1 profile field"),
    "incomparable_with": ("carried", "incomparable_with", "s1 profile field"),
    "runs": ("moved", "evidence", "`experiment | computation/runs/<id>.md | <run status> | "
             "<job id or -> | run` rows"),
    "claims": ("carried", "claims", "s1 profile field (example -> claims)"),
}
for _k in ("construction", "r", "u", "n", "G_order", "normal", "stratum", "genus",
           "Lambda", "q2", "q2_by", "K_min"):
    S1_MAP[_k] = ("carried", _k, "s1 profile field (example data)")
S1_NEW = {"lifecycle": "active", "domain": DOMAIN,
          "modulo": "proved-modulo only: the stated inputs / the reduction target",
          "evidence": "verdict rows (cleared_by, verdict subjects/clears), run rows",
          "history": "the body's ## History items, newest first, plus the migration row"}
S1_BODY = {"## History": ("moved", "history", "items -> rows `date |  | text`, newest first; "
                          "continuation lines joined with one space")}

#: Slope1 label -> v2 status, for status_by_level values and the plain cases
S1_WORD = {"Proved": "proved", "Proved modulo stated inputs": "proved-modulo",
           "Reduced": "proved-modulo", "Disproved": "refuted", "Not settled": "open",
           "Partial": "open"}

#: the Partial splits: parent -> the proposed cases. The texts are the parent's own
#: words (R2 section 5.3, verbatim in the parent's body), cut at its semicolons; they are
#: proposals for Roey, written as `sketch` claims, never as proved ones.
PARTIAL_SPLITS = {
    "OPEN-4": {
        "prefix": "STR",
        "cases": [
            {"key": "a",
             "title": "A grid-line reflection or lattice-point half-turn of P makes H^+ imprimitive (OPEN-4 case)",
             "summary": "Case of R2 §5.3's obstructions: a grid-line reflection or a lattice-point half-turn symmetry of P makes H^+ imprimitive (Prop. 3.3(b)).",
             "depends_on": ["STR-4"],
             "statement": "If $P$ has a grid-line reflection or a lattice-point half-turn symmetry, then $H^+$ is imprimitive.",
             "verbatim": "Obstructions: grid-line reflections and lattice-point half-turns (Prop. 3.3(b))",
             "note": "This case is the λ = 1 clause of STR-4(b) (R2 Prop 3.3(b)), which is recorded Proved: the case may be a duplicate of STR-4 rather than a new claim."},
            {"key": "b",
             "title": "Λ ≠ 2Z² makes H^+ imprimitive (OPEN-4 case)",
             "summary": "Case of R2 §5.3's obstructions: if Λ≠2Z², the fibres of β refined by Ω→A are H-blocks, so H^+ is imprimitive.",
             "depends_on": [],
             "statement": "If $\\Lambda\\ne2\\mathbb Z^2$, then $H^+$ is imprimitive: the fibres of $\\beta$ refined by $\\Omega\\to A$ are $H$-blocks.",
             "verbatim": "$\\Lambda\\ne2\\mathbb Z^2$ (the fibres of\n$\\beta$ refined by $\\Omega\\to A$ are $H$-blocks)",
             "note": "The parenthesis is the whole argument in the source; no proof is written out."},
            {"key": "c",
             "title": "For a rectangle, H^+ = D_p × D_q on rows × columns (OPEN-4 case)",
             "summary": "Case of R2 §5.3's obstructions: for a rectangle P, H^+ = D_p×D_q acting on rows×columns, an imprimitive action.",
             "depends_on": [],
             "statement": "If $P$ is a rectangle, then $H^+=D_p\\times D_q$ acting on rows$\\times$columns; in particular $H^+$ is imprimitive.",
             "verbatim": "rectangles ($H^+=D_p\\times D_q$ on rows$\\times$columns)",
             "note": "The source gives only the parenthesis. Imprimitivity of a product action needs both factors non-trivial (p, q ≥ 2); the source does not say how thin rectangles are treated."},
        ],
    },
}

# --------------------------------------------------------------------------- helpers


def today():
    return datetime.date.today().isoformat()


def _ser_fsl(fields):
    return fm.serialize_frontmatter(fields, fsl.V2_ORDER, fsl.V2_BLOCK,
                                    fm.format_scalar_single)


def _ser_s1(fields):
    return s1kb.serialize_v2(fields)


def _decision_word(decision):
    d = str(decision or "").strip()
    d = re.split(r"[.;:(,]", d, maxsplit=1)[0].strip() or d
    d = d.replace("|", "/")
    return (d[:60] + "…") if len(d) > 61 else d


JOB_RE = re.compile(r"\b(\d{8}-\d{6}_[A-Za-z0-9_.\-]+)")


def _job_id(body):
    jobs = []
    for m in JOB_RE.finditer(body):
        j = m.group(1).rstrip(".")
        if j not in jobs:
            jobs.append(j)
    return jobs[0] if len(jobs) == 1 else ""


def _history_items(body):
    """(items oldest first, body without the ## History section). Items are the dated
    bullets; an indented continuation line joins its item with one space."""
    lines = body.split("\n")
    idx = next((i for i, l in enumerate(lines) if l.strip().lower() == "## history"), None)
    if idx is None:
        return [], body, False
    end = next((j for j in range(idx + 1, len(lines)) if re.match(r"^#{1,2} ", lines[j])),
               len(lines))
    items = []
    for l in lines[idx + 1:end]:
        if not l.strip():
            continue
        m = s1kb.HISTORY_LINE.match(l)
        if m and re.match(r"^\s*[-*]\s*\d{4}-\d{2}-\d{2}", l):
            items.append([m.group(1), m.group(2).strip()])
        elif items:
            items[-1][1] += " " + l.strip()
        else:
            raise ValueError(f"history line before any item: {l!r}")
    rest = lines[:idx] + lines[end:]
    while rest and not rest[-1].strip():
        rest.pop()
    return items, "\n".join(rest) + "\n", True


def _has_proof(body):
    return any(re.match(r"^#{2,3}\s+proof\b", l.strip(), re.I) for l in body.split("\n"))


# ------------------------------------------------------------------------- fsl records

def migrate_fsl(ns, home, date, log):
    root = home / FSL_DIRS[ns]
    out = []
    for p in sorted(root.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        old, body = fsl.parse_strict(text, p)       # dialect only: R2 requoted them
        rec = {"ns": ns, "file": str(p), "rel": p.relative_to(home).as_posix(),
               "id": old["id"], "old": old, "old_text": text, "fields": [],
               "judgement": []}
        unmapped = [k for k in old if k not in FSL_MAP]
        if unmapped:
            raise SystemExit(f"{p}: unmapped field(s) {unmapped}; add them to FSL_MAP")
        new = {"id": old["id"]}
        label = old["id"].split(":", 1)[1]
        new["kind"] = fsl.kind_of(old["id"], "paper" if ns == "paper" else "lab")
        new["title"] = old["title"]
        st = old["status"]
        lifecycle = "active"
        rule = "same word"
        if st in ("superseded", "dropped"):
            lifecycle = st
            prev = next((schema.history_cells(h)[1] for h in old.get("history", [])
                         if schema.history_cells(h)[1] in schema.STATUSES), None)
            st = prev or "open"
            rule = (f"lifecycle {lifecycle}; status = last recorded status `{prev}`"
                    if prev else f"lifecycle {lifecycle}; no earlier status recorded -> open")
            rec["judgement"].append(("lifecycle", rule))
        new["status"] = st
        if old.get("open") and st == "proved-modulo":
            new["modulo"] = list(old["open"])
            rec["judgement"].append(("modulo", "open: -> modulo (proved-modulo)"))
        if "depends_on" in old:
            new["depends_on"] = list(old["depends_on"])
        if old.get("bears_on"):
            new["bears_on"] = list(old["bears_on"])
        if old.get("supersedes"):
            sup = old["supersedes"]
            new["supersedes"] = list(sup) if isinstance(sup, list) else [sup]
        new["lifecycle"] = lifecycle
        new["domain"] = DOMAIN
        if old.get("tags"):
            new["tags"] = list(old["tags"])
        if old.get("where"):
            new["where"] = old["where"]
        if old.get("open") and st != "proved-modulo":
            new["open"] = list(old["open"])
        ev = []
        for row in old.get("evidence", []):
            k, ref, verdict, note = fsl.split_row(row, 4)
            ev.append(schema.evidence_row(k, ref, verdict, "", note))
        new["evidence"] = ev
        state_now = lifecycle if lifecycle != "active" else st
        mig = schema.history_row(
            date, state_now,
            "schema v2 migration (R5)" + (f": {rule}" if rule != "same word" else
                                           ", status unchanged"))
        new["history"] = [mig] + list(old.get("history", []))
        rec.update(new=new, body=body, new_text="---\n" + _ser_fsl(new) + "---\n"
                   + _fsl_body_text(text),
                   status_old=old["status"], status_new=st, lifecycle=lifecycle, rule=rule,
                   cls_old=projection.project(old["status"], projection.FSL))
        for k in old:
            rec["fields"].append((k,) + FSL_MAP[k])
        out.append(rec)
    return out


def _fsl_body_text(text):
    """The body exactly as the file has it (after the closing fence)."""
    lines, close = fm.fence_lines(text)
    return "\n".join(lines[close + 1:])


# -------------------------------------------------------------------------- s1 records

def load_s1_ledgers(home):
    verdicts, runs = {}, {}
    for d, store in (("computation/verdicts", verdicts), ("computation/runs", runs)):
        for p in sorted((home / d).glob("*.md")):
            if p.name.lower() == "readme.md":
                continue
            meta, body = fm.split_document(p.read_text(encoding="utf-8"), str(p))
            rid = str(meta.get("id") or p.stem)
            store[rid] = {"rel": p.relative_to(home).as_posix(), "meta": meta, "body": body,
                          "path": p}
    return verdicts, runs


def _reduction_target(meta, body, known):
    """Ids named as the target of the reduction -- "Reduced ... to <ID>" in the
    status_note, the summary or the body (its History section excluded: a history line
    quotes old notes, not the target) -- in order; [] if none."""
    texts = [str(meta.get("status_note") or ""), str(meta.get("summary") or "")]
    texts += [l for l in body.split("\n") if "reduced" in l.lower()]
    out = []
    for t in texts:
        for m in re.finditer(r"[Rr]educed\b[^.;]*?\bto\b([^.;]*)", t):
            for tok in re.findall(r"\b([A-Z]+-[A-Za-z0-9′']+|Q\d+)\b", m.group(1)):
                if tok in known and tok not in out:
                    out.append(tok)
    return out


def _modulo_inputs(note):
    m = re.search(r"modulo\s+(.+)$", str(note or ""), re.I)
    if not m:
        return []
    return [x.strip() for x in re.split(r",\s*|\s+and\s+", m.group(1)) if x.strip()]


def migrate_s1(home, date, log):
    kb = s1kb.load_kb(home)
    known = set(kb.entities)
    verdicts, runs = load_s1_ledgers(home)
    # which verdicts name each entity
    named = {}
    for vid, v in verdicts.items():
        subs = v["meta"].get("subjects") or []
        clears = v["meta"].get("clears") or []
        for role, lst in (("subject", subs), ("clears", clears)):
            for ref in lst if isinstance(lst, list) else []:
                eid = s1kb.lookup(kb, ref)[0]
                if eid:
                    named.setdefault(eid, {}).setdefault(vid, []).append(role)
    out, splits = [], []
    for d, etype in S1_DIRS:
        for p in sorted((home / d).glob("*.md")):
            if p.name.lower() == "readme.md":
                continue
            text = p.read_text(encoding="utf-8")
            old, body = fm.split_document(text, str(p))
            eid = old["id"]
            rec = {"ns": "s1", "file": str(p), "rel": p.relative_to(home).as_posix(),
                   "id": eid, "old": old, "old_text": text, "fields": [], "judgement": [],
                   "etype": etype}
            unmapped = [k for k in old if k not in S1_MAP]
            if unmapped:
                raise SystemExit(f"{p}: unmapped field(s) {unmapped}; add them to S1_MAP")
            items, new_body, had_hist = _history_items(body)
            oldkind = old.get("kind")
            st_old = old.get("status")
            new = {"id": eid}
            if etype == "example":
                new["kind"] = "example"
            elif etype == "assumption":
                new["kind"] = "assumption"
            else:
                new["kind"] = s1kb.KIND_V2[oldkind]
                new["form"] = oldkind
            new["title"] = old["title"]
            status, rule, modulo = None, "", []
            if etype == "claim" and st_old:
                if st_old == "Proved":
                    status, rule = "proved", "Proved -> proved"
                elif st_old == "Disproved":
                    status, rule = "refuted", "Disproved -> refuted"
                elif st_old == "Proved modulo stated inputs":
                    status = "proved-modulo"
                    modulo = _modulo_inputs(old.get("status_note"))
                    rule = "Proved modulo stated inputs -> proved-modulo; modulo from status_note"
                    if not modulo:
                        modulo = ["UNRESOLVED-TARGET: the stated inputs are not named in "
                                  "status_note (Roey to name them)"]
                        rec["judgement"].append(("modulo", "stated inputs not found"))
                    else:
                        rec["judgement"].append(("modulo", "inputs read from status_note: "
                                                 + "; ".join(modulo)))
                elif st_old == "Reduced":
                    status = "proved-modulo"
                    tg = _reduction_target(old, new_body, known - {eid})
                    if tg:
                        modulo = tg
                        rule = "Reduced -> proved-modulo; modulo = the reduction target(s) named by id"
                        rec["judgement"].append(("reduced", "target by id: " + ", ".join(tg)))
                    else:
                        note = str(old.get("status_note") or "")
                        m = re.search(r"\(to ([^)]*)\)", note)
                        what = m.group(1) if m else note
                        modulo = [f"UNRESOLVED-TARGET: {what} (no record carries this "
                                  "input; Roey to name the target)"]
                        rule = "Reduced -> proved-modulo; target not an id: marked for Roey"
                        rec["judgement"].append(("reduced", "target not determinable "
                                                 "mechanically: " + what))
                elif st_old == "Partial":
                    status, rule = "open", "Partial -> open parent + sketch cases (split)"
                    rec["judgement"].append(("partial", "split"))
                elif st_old == "Not settled":
                    if oldkind in ("open", "question"):
                        status, rule = "open", "Not settled, open problem/question -> open"
                    elif oldkind == "conj":
                        status, rule = "conjectured", "Not settled, conjecture -> conjectured"
                    elif _has_proof(body):
                        status, rule = "sketch", "Not settled, statement with a ## Proof -> sketch"
                        rec["judgement"].append(("not-settled", "sketch (has a proof section)"))
                    else:
                        status, rule = "open", "Not settled, statement without a proof -> open"
                        rec["judgement"].append(("not-settled", "open (no proof section)"))
                else:
                    raise SystemExit(f"{p}: unknown status {st_old!r}")
                new["status"] = status
            elif etype == "claim":
                rule = f"no status ({oldkind})"
            if modulo:
                new["modulo"] = modulo
            if "depends_on" in old:
                new["depends_on"] = list(old["depends_on"])
            if old.get("supersedes"):
                sup = old["supersedes"]
                new["supersedes"] = list(sup) if isinstance(sup, list) else [sup]
            new["lifecycle"] = "active"
            if old.get("aliases") is not None:
                new["aliases"] = list(old["aliases"])
            new["domain"] = DOMAIN
            if old.get("topics") is not None:
                new["tags"] = list(old["topics"])
            for k in s1kb.S1_EXTENSION:
                if k in old:
                    v = old[k]
                    if k == "status_by_level" and isinstance(v, dict):
                        v = {lvl: (S1_WORD.get(x, x) if isinstance(x, str) else x)
                             for lvl, x in v.items()}
                        rec["judgement"].append(("status_by_level", "values -> v2 words; "
                                                 "per-level modulo targets stay in the body"))
                    new[k] = v
            ev = []
            for vrel in old.get("cleared_by") or []:
                vid = next((i for i, v in verdicts.items() if v["rel"] == vrel), Path(vrel).stem)
                dec = _decision_word(verdicts.get(vid, {}).get("meta", {}).get("decision"))
                ev.append(schema.evidence_row("verdict", vrel, dec, vid, s1kb.CLEARED_NOTE))
            for vid, roles in sorted((named.get(eid) or {}).items()):
                v = verdicts[vid]
                if any(schema.evidence_cells(r)[1] == v["rel"] for r in ev):
                    continue
                ev.append(schema.evidence_row(
                    "verdict", v["rel"], _decision_word(v["meta"].get("decision")), vid,
                    "names this record as " + " and ".join(sorted(set(roles)))))
            for rid in old.get("runs") or []:
                r = runs.get(rid)
                if r is None:
                    ev.append(schema.evidence_row("experiment", f"computation/runs/{rid}.md",
                                                  "", "", s1kb.RUN_NOTE + "; no run file"))
                    continue
                ev.append(schema.evidence_row(
                    "experiment", r["rel"], _decision_word(r["meta"].get("status")),
                    _job_id(r["body"]), s1kb.RUN_NOTE))
            new["evidence"] = ev
            hist = [schema.history_row(d_, "", t_) for d_, t_ in reversed(items)]
            # newest first: a stable sort by date, descending (same-day items keep the
            # reversed order: later in the body = newer)
            hist.sort(key=lambda h: schema.history_cells(h)[0], reverse=True)
            if st_old or status:
                mig_note = f"schema v2 migration (R5): {rule}"
            else:
                mig_note = "schema v2 migration (R5)"
            new["history"] = [schema.history_row(date, status or "", mig_note)] + hist
            rec.update(new=new, body=new_body, had_history=had_hist, history_items=items,
                       new_text="---\n" + _ser_s1(new) + "---\n" + new_body,
                       status_old=st_old or "", status_new=status or "", lifecycle="active",
                       rule=rule,
                       cls_old=projection.project(st_old if etype in ("claim", "assumption")
                                                  and st_old else "", projection.S1))
            for k in old:
                rec["fields"].append((k,) + S1_MAP[k])
            if had_hist:
                rec["fields"].append(("## History (body)",) + S1_BODY["## History"])
            out.append(rec)
    # the Partial splits
    for rec in out:
        if rec["status_old"] != "Partial":
            continue
        spec = PARTIAL_SPLITS.get(rec["id"])
        if spec is None:
            rec["judgement"].append(("partial", "NO SPLIT PROPOSED: parent set open only"))
            continue
        used = s1kb.used_numbers(kb, spec["prefix"])
        n = max(used, default=0)
        case_ids = []
        for case in spec["cases"]:
            n += 1
            cid = f"{spec['prefix']}-{n}"
            case_ids.append(cid)
            parent = rec["id"]
            meta = {"id": cid, "kind": "claim", "form": "prop", "title": case["title"],
                    "status": "sketch", "depends_on": list(case["depends_on"]),
                    "lifecycle": "active", "aliases": [], "domain": DOMAIN,
                    "tags": list(rec["new"].get("tags") or []),
                    "summary": case["summary"],
                    "status_note": "proposed Partial split of %s, case (%s); sketch until "
                                   "Roey confirms" % (parent, case["key"]),
                    "level": rec["old"].get("level"),
                    "source": f"split of claims/{parent}.md (R5, {date}): "
                              + str(rec["old"].get("source") or ""),
                    "added": date, "evidence": [],
                    "history": [schema.history_row(
                        date, "sketch", f"created by the schema v2 migration (R5): proposed "
                        f"case ({case['key']}) of the Partial {parent}; not proved until "
                        "Roey confirms the split")]}
            if not meta["level"]:
                del meta["level"]
            body = ("\n## Statement\n\n" + case["statement"] + "\n\n"
                    "*Proposed split case (" + case["key"] + ") of [" + parent + "](" + parent
                    + ".md), R5 schema v2 migration. The parent's verbatim words (R2 §5.3):* "
                    + case["verbatim"] + ".\n\n## Notes\n\n- " + case["note"] + "\n")
            splits.append({"id": cid, "parent": parent, "case": case, "new": meta,
                           "body": body, "rel": f"claims/{cid}.md",
                           "new_text": "---\n" + _ser_s1(meta) + "---\n" + body})
        rec["new"]["depends_on"] = list(rec["new"].get("depends_on") or []) + case_ids
        rec["judgement"].append(("partial", "split into " + ", ".join(case_ids)
                                 + " (sketch); parent open, depends_on the cases"))
        rec["new"]["history"][0] = schema.history_row(
            date, rec["new"]["status"], "schema v2 migration (R5): status Partial -> open; "
            "proposed split into " + ", ".join(case_ids) + " (sketch, for Roey's review)")
        rec["new_text"] = "---\n" + _ser_s1(rec["new"]) + "---\n" + rec["body"]
    return out, splits, verdicts, runs, kb


# ------------------------------------------------------------------------ verification

def _reparse(rec):
    if rec["ns"] == "s1":
        meta, body = fm.split_document(rec["new_text"], rec["rel"])
    else:
        meta, body = fsl.parse_strict(rec["new_text"], rec["rel"])
    return meta, body


def verify(recs, splits):
    """Machine checks; returns {check: [problems]} (all empty when green)."""
    probs = {"unmapped": [], "carried": [], "projection": [], "evidence": [],
             "history": [], "roundtrip": [], "schema": [], "hash": []}
    hashes = []
    for r in recs:
        meta, body = _reparse(r)
        if meta != r["new"]:
            probs["roundtrip"].append(f"{r['rel']}: re-read frontmatter != intended")
        for k in r["old"]:
            disp = (FSL_MAP if r["ns"] != "s1" else S1_MAP).get(k)
            if disp is None:
                probs["unmapped"].append(f"{r['rel']}: {k}")
                continue
            if k == "depends_on" and r["status_old"] == "Partial" \
                    and (meta.get(k) or [])[:len(r["old"][k])] == r["old"][k]:
                continue    # the Partial parent: its old inputs, then the split cases
            if disp[0] == "carried" and meta.get(disp[1]) != r["old"][k]:
                probs["carried"].append(f"{r['rel']}: {k} {r['old'][k]!r} != {meta.get(disp[1])!r}")
            if disp[0] == "renamed" and meta.get(disp[1]) != r["old"][k] \
                    and not (r["old"][k] == [] and disp[1] not in meta):
                probs["carried"].append(f"{r['rel']}: {k} -> {disp[1]} differs")
        new_cls = schema.project(meta)
        if r["ns"] == "s1" and not meta.get("status") and meta.get("lifecycle") == "active":
            new_cls = projection.NA
        if r["cls_old"] != new_cls:
            probs["projection"].append(f"{_qid(r)}: {r['cls_old']} -> {new_cls}")
        # evidence and history rows kept
        if r["ns"] != "s1":
            olds = r["old"].get("evidence") or []
            news = meta.get("evidence") or []
            if len(olds) != len(news):
                probs["evidence"].append(f"{r['rel']}: {len(olds)} rows -> {len(news)}")
            for o, n in zip(olds, news):
                ok = fsl.split_row(o, 4)
                nk = schema.evidence_cells(n)
                if (ok[0], ok[1], ok[2] or "-", ok[3]) != (nk[0], nk[1], nk[2], nk[4]):
                    probs["evidence"].append(f"{r['rel']}: `{o}` -> `{n}`")
            if (meta.get("history") or [])[1:] != (r["old"].get("history") or []):
                probs["history"].append(f"{r['rel']}: old history rows not kept verbatim")
            if r["ns"] == "lab":
                h_old = statement_hash_of(r["old"]["title"] + "\n" + _fsl_body_text(r["old_text"]).strip())
                h_new = statement_hash_of(meta["title"] + "\n" + body)
                hashes.append((f"lab:{r['id'].split(':', 1)[1]}", h_old, h_new))
        else:
            for vrel in r["old"].get("cleared_by") or []:
                if not any(schema.evidence_cells(x)[1] == vrel and
                           schema.evidence_cells(x)[4] == s1kb.CLEARED_NOTE
                           for x in meta.get("evidence") or []):
                    probs["evidence"].append(f"{r['rel']}: cleared_by {vrel} lost")
            for rid in r["old"].get("runs") or []:
                if not any(schema.evidence_cells(x)[1].endswith(f"/{rid}.md")
                           for x in meta.get("evidence") or []):
                    probs["evidence"].append(f"{r['rel']}: run {rid} lost")
            rows = meta.get("history") or []
            notes = [schema.history_cells(x)[2] for x in rows]
            for d_, t_ in r.get("history_items") or []:
                if schema.history_row(d_, "", t_) not in rows:
                    probs["history"].append(f"{r['rel']}: history item {d_} lost")
            if len(rows) != len(r.get("history_items") or []) + 1:
                probs["history"].append(f"{r['rel']}: {len(rows)} rows for "
                                        f"{len(r.get('history_items') or [])} items + 1")
            old_e = s1kb.Entity(r["id"], r["etype"], r["rel"], r["old"],
                                fm.split_document(r["old_text"], r["rel"])[1])
            new_e = s1kb.Entity(r["id"], r["etype"], r["rel"], meta, body)
            hashes.append((f"s1:{r['id']}", statement_hash_of(s1kb.statement_text(old_e)),
                           statement_hash_of(s1kb.statement_text(new_e))))
        for level, msg in schema.check_record(
                meta, extra_fields=s1kb.S1_EXTENSION if r["ns"] == "s1" else fsl.V2_EXTRA,
                status_kinds=fsl.V2_STATUS_KINDS.get(r["ns"], schema.STATUS_KINDS)
                if r["ns"] != "s1" else schema.STATUS_KINDS):
            if level == "error":
                probs["schema"].append(f"{r['rel']}: {msg}")
    for s in splits:
        meta, _ = fm.split_document(s["new_text"], s["rel"])
        if meta != s["new"]:
            probs["roundtrip"].append(f"{s['rel']}: re-read frontmatter != intended")
        if meta.get("status") != "sketch":
            probs["projection"].append(f"{s['rel']}: a split case must be sketch")
        for level, msg in schema.check_record(meta, extra_fields=s1kb.S1_EXTENSION):
            if level == "error":
                probs["schema"].append(f"{s['rel']}: {msg}")
    changed = [h for h in hashes if h[1] != h[2]]
    return probs, hashes, changed


# ----------------------------------------------------------------------------- reports

def _qid(r):
    return r["id"] if r["ns"] != "s1" else f"s1:{r['id']}"


def _md(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def write_report(path, recs, splits, probs, hashes, changed, date, proposals, applied):
    by_ns = {}
    for r in recs:
        by_ns.setdefault(r["ns"], []).append(r)
    L = [f"# R5 mapping report: schema v2 migration ({date})", "",
         "Generated by `py -m registry.migrate_v2` (academy/academy/registry/migrate_v2.py). "
         "Machine-checked; every row below comes from the script, not by hand.", "",
         f"Applied to the worktrees: **{'yes' if applied else 'no (dry run)'}**. Homes: "
         + ", ".join(f"`{ns}:` {HOMES[ns]}" for ns in ("lab", "paper", "s1")) + ".", "",
         "## Machine checks", "",
         "| check | result |", "|---|---|"]
    names = {"unmapped": "every old field of every file has a disposition (FSL_MAP / S1_MAP)",
             "carried": "every carried or renamed field equal after the dialect round trip",
             "roundtrip": "every new file re-reads to exactly the intended frontmatter",
             "projection": "projection class unchanged for every record (split cases are additions, all sketch)",
             "evidence": "every old evidence row / cleared_by / run kept as an evidence row",
             "history": "every old history row / body History item kept as a row, plus one migration row",
             "schema": "every new record passes the core schema rules (core/schema.check_record)"}
    for k, label in names.items():
        L.append(f"| {label} | {'PASS' if not probs[k] else 'FAIL: ' + str(len(probs[k]))} |")
    L.append(f"| statement hashes (`py -m registry statement`) unchanged | "
             f"{len(hashes) - len(changed)}/{len(hashes)} unchanged; "
             f"{len(changed)} changed (listed below) |")
    L += ["", "Counts: " + ", ".join(f"`{ns}:` {len(v)} records" for ns, v in sorted(by_ns.items()))
          + f"; {len(splits)} new split cases.", ""]
    for k, v in probs.items():
        if v:
            L += [f"### Problems: {k}", ""] + [f"- {_md(x)}" for x in v] + [""]
    # field tables
    L += ["## Field mapping", "",
          "Every field that occurs in an old file, with its disposition. *carried*: same name, "
          "same value; *renamed*: same value, new name; *mapped*: value transformed; *moved*: "
          "into evidence or history rows; *derived*: not stored, recomputed.", ""]
    for title, table, new, nss in (("lab / paper (fsl-claims v1)", FSL_MAP, FSL_NEW, ("lab", "paper")),
                                   ("s1 (s1-kb v1)", dict(S1_MAP, **S1_BODY), S1_NEW, ("s1",))):
        occ = {}
        for r in recs:
            if r["ns"] in nss:
                for f in r["fields"]:
                    occ[f[0]] = occ.get(f[0], 0) + 1
        L += [f"### {title}", "", "| old field | files | disposition | new field | how |",
              "|---|---|---|---|---|"]
        for k, (disp, nf, how) in table.items():
            if k in occ:
                L.append(f"| `{k}` | {occ[k]} | {disp} | `{nf}` | {_md(how)} |")
        unused = [k for k in table if k not in occ]
        if unused:
            L.append("")
            L.append("Mapped but absent from every file: " + ", ".join(f"`{k}`" for k in unused) + ".")
        L += ["", "New fields: " + "; ".join(f"`{k}`: {_md(v)}" for k, v in new.items()) + ".", ""]
    # status tables
    L += ["## Status, per file", "",
          "Old status -> new status (and lifecycle), with the projection class before and "
          "after. Every class is unchanged.", ""]
    for ns in ("lab", "paper", "s1"):
        rs = by_ns.get(ns, [])
        L += [f"### `{ns}:` ({len(rs)} records)", "",
              "| id | file | old status | new status | lifecycle | class old -> new | rule |",
              "|---|---|---|---|---|---|---|"]
        for r in sorted(rs, key=lambda r: r["rel"]):
            meta, _ = _reparse(r)
            nc = schema.project(meta)
            if ns == "s1" and not meta.get("status"):
                nc = projection.NA
            L.append(f"| `{r['id']}` | `{r['rel']}` | {r['status_old'] or '-'} | "
                     f"{r['status_new'] or '-'} | {r['lifecycle']} | {r['cls_old']} -> {nc} | "
                     f"{_md(r['rule'])} |")
        L.append("")
    L += ["## Partial splits (new records, proposals)", ""]
    if not splits:
        L.append("None.")
    for s in splits:
        L.append(f"- `s1:{s['id']}` (sketch), case ({s['case']['key']}) of `s1:{s['parent']}`: "
                 f"{_md(s['case']['statement'])}")
    L += ["", "## Judgement calls, per record", ""]
    for r in recs:
        for kind, what in r["judgement"]:
            L.append(f"- `{_qid(r)}` [{kind}] {_md(what)}")
    L += ["", "## Statement hashes that changed", "",
          "The hash is of the text a proof review is given on (`py -m registry statement`). "
          "A Slope1 record without a `## Statement` section is hashed on its whole body, so "
          "moving its `## History` into the frontmatter changes its hash; nothing else does.", ""]
    L += [f"- `{q}`: {a} -> {b}" for q, a, b in changed] or ["None."]
    L += ["", "## Verdict and run records (proposed moves, not applied)", "",
          f"Copies under `goldens/r5-proposed-reviews/`; see its `MANIFEST.md`. "
          f"{len(proposals)} proposed files. The originals stay in "
          "`Slope1illuminationResearch-academy/computation/{verdicts,runs}/`, and the evidence "
          "rows point at them there.", ""]
    Path(path).write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def propose_reviews(outdir, verdicts, runs, kb):
    """Copy each verdict file to its proposed home: a verdict on claims/examples to
    Expert's ``reviews/s1/<first subject>/``; a verdict on a run (an experiment audit)
    to the Researcher's ``audits/<run>/`` (plan section 3.3). Verbatim copies."""
    outdir = Path(outdir)
    if outdir.exists():
        shutil.rmtree(outdir)
    rows = []
    for vid, v in sorted(verdicts.items()):
        subs = [s for s in (v["meta"].get("subjects") or []) if isinstance(s, str)]
        resolved = [(s, s1kb.lookup(kb, s)[0]) for s in subs]
        targets = [(s, e) for s, e in resolved if e]
        if not targets:
            dest = Path("papers/reviews/s1/_unassigned") / Path(v["rel"]).name
            why = "no subject resolves"
        else:
            first = kb.entities[targets[0][1]]
            if first.etype == "run":
                dest = Path("slope1/audits") / first.id / Path(v["rel"]).name
                why = "experiment audit (subject is a run)"
            else:
                dest = Path("papers/reviews/s1") / first.id / Path(v["rel"]).name
                why = "proof/claim verdict"
        p = outdir / dest
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(v["path"], p)
        rows.append((vid, v["rel"], dest.as_posix(), ", ".join(e for _, e in targets) or "-", why))
    L = ["# Proposed moves of Slope1's verdict records (R5; not applied)", "",
         "Each file here is a verbatim copy of a verdict file in "
         "`Slope1illuminationResearch-academy/computation/verdicts/`, placed where it would live "
         "after the move: `papers/…` is Expert's home (`C:\\Work\\Math\\papers`), `slope1/…` the "
         "Researcher's. Nothing was written into either home. A verdict naming several records "
         "is placed under the first; the others are listed. Runs (`computation/runs/`) stay "
         "where they are, as references to the lab's results.", "",
         "| verdict | now | proposed | subjects (resolved) | why |", "|---|---|---|---|---|"]
    L += [f"| `{a}` | `{b}` | `{c}` | {d} | {e} |" for a, b, c, d, e in rows]
    (outdir / "MANIFEST.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    return rows


def snapshot(outdir, recs):
    outdir = Path(outdir)
    if outdir.exists():
        shutil.rmtree(outdir)
    for r in recs:
        p = outdir / r["ns"] / r["rel"]
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(r["old_text"])


def apply(recs, splits, math):
    for r in recs:
        with open(r["file"], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(r["new_text"])
    for s in splits:
        p = math / HOMES["s1"] / s["rel"]
        if p.exists():
            raise SystemExit(f"{p} exists; refusing to overwrite with a split case")
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(s["new_text"])


def mapping_json(path, recs, splits, hashes):
    data = {"records": [{"qid": f"{r['ns']}:{r['id'].split(':', 1)[-1]}", "file": r["rel"],
                         "status_old": r["status_old"], "status_new": r["status_new"],
                         "lifecycle": r["lifecycle"], "class_old": r["cls_old"],
                         "rule": r["rule"], "fields": [list(f) for f in r["fields"]],
                         "judgement": [list(j) for j in r["judgement"]]} for r in recs],
            "splits": [{"id": s["id"], "parent": s["parent"], "case": s["case"]["key"],
                        "file": s["rel"]} for s in splits],
            "hashes": [list(h) for h in hashes]}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8", newline="\n")


def run(math, date=None, apply_=False, report=None, mapping=None, proposed=None,
        snap=None):
    math = Path(math)
    date = date or today()
    homes = {ns: math / d for ns, d in HOMES.items()}
    for ns, h in homes.items():
        if not h.name.endswith("-academy") or not h.is_dir():
            raise SystemExit(f"{h}: not a migration worktree (*-academy); refusing")
    log = []
    recs = migrate_fsl("lab", homes["lab"], date, log) + migrate_fsl("paper", homes["paper"], date, log)
    s1recs, splits, verdicts, runs, kb = migrate_s1(homes["s1"], date, log)
    recs += s1recs
    probs, hashes, changed = verify(recs, splits)
    bad = {k: v for k, v in probs.items() if v}
    proposals = propose_reviews(proposed, verdicts, runs, kb) if proposed else []
    if snap:
        snapshot(snap, recs)
    if report:
        write_report(report, recs, splits, probs, hashes, changed, date, proposals,
                     apply_ and not bad)
    if mapping:
        mapping_json(mapping, recs, splits, hashes)
    if bad:
        print("migrate_v2: checks FAILED, nothing applied:\n" + "\n".join(
            f"  {k}: {len(v)} ({v[0]})" for k, v in bad.items()), file=sys.stderr)
        return 1, recs, splits
    if apply_:
        apply(recs, splits, math)
    print(f"migrate_v2: {len(recs)} records, {len(splits)} split cases, "
          f"{len(changed)} statement hashes changed; {'applied' if apply_ else 'dry run'}")
    return 0, recs, splits


def main(argv=None):
    ap = argparse.ArgumentParser(prog="registry.migrate_v2", description=__doc__.split("\n")[0])
    ap.add_argument("--math", default=os.environ.get("ACADEMY_MATH", "C:/Work/Math"))
    ap.add_argument("--date")
    ap.add_argument("--report")
    ap.add_argument("--mapping-json")
    ap.add_argument("--proposed-reviews")
    ap.add_argument("--snapshot")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    rc, _, _ = run(a.math, a.date, a.apply, a.report, a.mapping_json, a.proposed_reviews,
                   a.snapshot)
    return rc


if __name__ == "__main__":
    sys.exit(main())
