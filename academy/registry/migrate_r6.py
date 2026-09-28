"""migrate_r6 -- R6: Slope1's notebook layout (plan sections 3.3 and 6, phase R6).

Run after R5 (``migrate_v2``), on the migration worktree of ``s1:``
(``<math>/Slope1illuminationResearch-academy``) and, for the two cross-repo evidence
refs, the lab's (``<math>/FlatSurfLab-academy``). Without ``--apply`` it only plans and
checks; with it, it writes. It refuses a home not named ``*-academy`` and an s1 home
that already has ``objects/``.

What it does, mechanically:

1. **Records.** Every ``claims/*.md``, ``assumptions/*.md`` and ``examples/*.md`` moves,
   byte for byte, to ``objects/<kind>/`` by its schema-v2 ``kind``. The generated
   ``assumptions/README.md`` is deleted (``build`` writes ``views/assumptions.md``).
2. **Audits.** A verdict file whose every subject is a run (a file in
   ``computation/runs/``) is an experiment audit and moves, byte for byte, to
   ``audits/<first subject>/`` (P-0004 D9 (a), the Researcher half). The claim
   verdicts stay in ``computation/verdicts/`` until the Expert's librarian moves them
   (phase 7). Evidence refs to a moved audit are rewritten: in s1 records, and in lab
   records (``Slope1illuminationResearch:computation/verdicts/...``), where a history
   row records the move.
3. **Notes.** Each ``notes/<area>/<name>.md`` becomes the journal entry
   ``journal/<last-changed date>-<area>-<name>.md``, verbatim below a one-line
   provenance comment; only the relative links to moved files are retargeted. The
   ``notes/`` pages are topic pages, not dated working notes and not research
   programs, so none is turned into a direction (the conservative rule: when unsure,
   keep it verbatim in the journal).
4. **Directions.** Two research programs are written as direction objects
   (``objects/direction/DIR-1.md``, ``DIR-2.md``), drafted from the open-problem pages
   (``06-open/open-history.md``, ``03-q2/families-hunt.md``) and naming only existing
   ids; their history says lead-researcher is to review them.
5. **The (Q2) search record** (``docs-notes/extracted-q2-record.md`` in the academy
   repo, cut from the old libgap recipe file in Group B) becomes a journal entry,
   verbatim below a provenance comment.
6. ``proofs/README.md`` and the path map ``kb/r6-path-map.md`` (every old path and its
   new one, like ``kb/relabel-map.md`` for labels) are written.

Machine checks (all must pass, or nothing is written): every record lands in the folder
of its kind, no two files land on one path, every retargeted link resolves after the
move, every id a direction names exists, and every rewritten evidence ref exists after
the move. The views are not written here: run ``py tools/kb.py build`` in the s1 home
and ``py scripts/claims.py render`` in the lab afterwards.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

from .core import fm as _fm
from .core import schema as _schema
from .migrate_v2 import HOMES

DATE = "2026-09-28"
ACADEMY_REPO = Path(__file__).resolve().parents[2]
Q2_RECORD = ACADEMY_REPO / "docs-notes" / "extracted-q2-record.md"
Q2_RECORD_DEST = "journal/2026-09-20-q2-search-libgap-record.md"
S1_REPO_NAME = "Slope1illuminationResearch"
#: what the last plan() noticed but did not refuse (printed by run(); for the report)
INFO = []

#: the date each notes/ page last changed (git log -1 on the migration branch's base,
#: 9cbe45b), which dates its journal entry
NOTE_DATES = {
    "00-setting/hypotheses.md": "2026-09-24", "00-setting/invariants.md": "2026-09-24",
    "00-setting/questions.md": "2026-09-19", "00-setting/terminology.md": "2026-09-19",
    "01-geometry/dictionary.md": "2026-09-24",
    "01-geometry/symmetry-hypotheses.md": "2026-09-24",
    "01-geometry/unfoldings.md": "2026-09-24",
    "02-structure/constraints-on-G.md": "2026-09-24",
    "02-structure/reflection-data.md": "2026-09-24",
    "03-q2/bounds-on-K.md": "2026-09-24", "03-q2/establishing-HA-CT.md": "2026-09-24",
    "03-q2/families-hunt.md": "2026-09-24", "03-q2/normal-case.md": "2026-09-24",
    "03-q2/orbitals.md": "2026-09-24", "03-q2/q1-failure.md": "2026-09-24",
    "03-q2/settled-cases.md": "2026-09-24", "04-examples/examples.md": "2026-09-19",
    "05-related/periodic-points-origami-orbits.md": "2026-09-19",
    "06-open/open-history.md": "2026-09-24",
}


def journal_name(note_rel):
    area, name = note_rel.split("/", 1)
    area = re.sub(r"^\d+-", "", area)
    slug = name if name.startswith(area) else f"{area}-{name}"
    return f"journal/{NOTE_DATES[note_rel]}-{slug}"


DIR_1 = """---
id: DIR-1
kind: direction
title: (Q2) for parking-garage unfoldings, PA-4 and above
lifecycle: active
domain: translation-surfaces
tags: [q2-criteria, open-problems]
summary: (Q2) is refuted at OA-3 but open for unfoldings of rectangle-tiled parking garages; at PA-6 minus PA-7 it is reduced to 5.A, 5.B, 6.A and the imprimitive case.
source: journal/2026-09-24-open-history.md (R2 §10 "Open, by leverage" and the experiments for the computation spec)
added: 2026-09-28
evidence: []
history:
  - "2026-09-28 | | drafted by the R6 migration from the open-problem page (notes/06-open/open-history.md); lead-researcher to review the program, the order and the falsifiers"
---

## Program

Decide (Q2) ([Q2](../question/Q2.md)) at the geometric levels. It fails at OA-3 (CEX-1,
CEX-3, CEX-4), and no known counterexample is a parking-garage unfolding (GEO-13). Under
PA-6 without PA-7 it is reduced to Open 5.A (OPEN-3), Open 5.B (OPEN-4), Open 6.A
(OPEN-5) and the imprimitive case; if Conjecture 10.1 (OPEN-2) holds, (Q2) at PA-6 is
equivalent to GA-CT′ alone (CRIT-17). The source's order "by leverage" is kept below.

## Questions

- s1:OPEN-2 — Conjecture 10.1: under PA-6 the G-orbitals are the level sets of inv = (d, z)
- s1:OPEN-3 — Open 5.A: a 3-cycle in H^+ without a unique reflex vertex
- s1:OPEN-4 — Open 5.B: which polyominoes are fold-imprimitive
- s1:OPEN-5 — Open 6.A: a direction with a T_θ-invariant orbit for half-turn symmetries
- s1:OPEN-11 — the grid-line-symmetric case: block reduction (CRIT-18) as an induction
- s1:OPEN-6 — the replacement bound K ≤ max(width, height) + 1 for polyominoes
- s1:OPEN-12 — (Q1) for PA-6 unfoldings that are not rectangles (secondary)

## Candidate claims

- s1:STR-6 — a grid-line reflection or lattice-point half-turn makes H^+ imprimitive (split from OPEN-4; P-0004 D1)
- s1:STR-7 — Λ ≠ 2Z² makes H^+ imprimitive (split from OPEN-4)
- s1:STR-8 — rectangles: H^+ = D_p × D_q is imprimitive (split from OPEN-4)
- s1:CRIT-20 — mid-line reflections satisfy GA-CT; its reduction target is unresolved (P-0004 D2)

## Falsifiers

- s1:OPEN-2 — H^+ and the G-orbitals against the level sets of inv for all polyominoes with at most 10 cells (spec experiment (i)); a counterexample can only live among polyominoes with H^+ imprimitive, Λ = 2Z² and no grid-line symmetry (experiment (iv))
- s1:OPEN-5 — for symmetric shapes, the smallest direction with a T-invariant orbit and the parity of the number of u-orbits (experiment (ii))
- s1:OPEN-6 — K_min against max(width, height) + 1 (experiment (iii))

## Next steps

1. Roey's decisions D1 and D2 of packet P-0004 fix STR-6..8 and CRIT-20's target.
2. The spec experiments (i)–(iv) above go to the Scientist as tickets, with these falsifiers.
3. OPEN-2 first: by the source's leverage order it would reduce PA-6 to GA-CT′.
"""

DIR_2 = """---
id: DIR-2
kind: direction
title: The family hunt for a (Q2) counterexample at PA-4
lifecycle: active
domain: translation-surfaces
tags: [counterexamples, families, computation]
summary: Search named families of origamis for a (Q2) counterexample that is a parking-garage unfolding (PA-4); the OA-3 counterexamples found so far are not.
source: journal/2026-09-24-q2-families-hunt.md; journal/2026-09-24-open-history.md (the four families, what gates a refutation, what a counterexample must look like); .claude/rules/families.md
added: 2026-09-28
evidence: []
history:
  - "2026-09-28 | | drafted by the R6 migration from the family-hunt pages (notes/03-q2/families-hunt.md, notes/06-open/open-history.md); lead-researcher to review the program, the order and the falsifiers"
---

## Program

The hunt of 2026-09-20..24 found (Q2) counterexamples at OA-3 (CEX-1, CEX-3, CEX-4), with
16 squares the minimum for their mechanism (BOUND-4); none is a PA-4 unfolding (GEO-13).
The live question is OPEN-1: a counterexample that is the unfolding of a rectangle-tiled
parking garage. The families and their parametrisations are `.claude/rules/families.md`
(§5 adds the PA-4 garages). Computation refutes; it never proves.

What gates a refutation: COMP-1 (the SL(2,Z)-orbit reduction and the value-set
enumeration), GEO-19 (every hypothesis level beyond "necessary conditions passed") and
COMP-3 (the construction of the abelian family). Until each is verified, a member found
through those paths is a candidate only, and its level is flagged experimental.

## Questions

- s1:OPEN-1 — a (Q2) counterexample at PA-4
- s1:OPEN-9 — n = 18 for the mechanism, and whether any counterexample has fewer than 16 squares
- s1:OPEN-8 — necessity of the gcd criterion (OBS-5) beyond N ≤ 18
- s1:OPEN-7 — the quotient mechanism for other M_N(a)

## Candidate claims

- s1:GEO-19 — the realisation test: M/Φ is a rectangle-tiled garage iff the vertex angles are right (gates PA-4, PA-5w, PA-6)
- s1:COMP-1 — the SL(2,Z)-orbit reduction of the enumeration
- s1:COMP-2 — the conjugation dedupe of the value-set BFS
- s1:COMP-3 — the abelian pillowcase covers as a family
- s1:COMP-4 — the pipeline's necessary conditions
- s1:COMP-5 — GA-CT′(i) for T of prime order from cusp representatives
- s1:GEO-11 — the GEO-10 commutator test needs n ≥ 6

## Falsifiers

- s1:OPEN-1 — a member with (Q2) failing: for a normal member, a non-identity element of G conjugate to no power of any Christoffel value, named with its class and a completeness certificate; for a non-normal member, a G-orbital (a pair (i, j) with d(i, j) and z(i, j)) met by no power of any value, with a completeness certificate. A record whose value set is not complete is UNDECIDED, never a counterexample.
- s1:GEO-19 — a garage unfolding the test rejects, or an accepted member that is not an unfolding

## Next steps

1. Verify the gates COMP-1, GEO-19 and COMP-3 (proof reviews through the Expert) before any refutation through them is believed.
2. Rank members on the two axes of `.claude/rules/families.md` (likelihood of failure, hypothesis level), a Pareto front, never a scalar.
3. The (Q2) search's libgap record is journal/2026-09-20-q2-search-libgap-record.md.
"""

DIRECTIONS = {"objects/direction/DIR-1.md": DIR_1, "objects/direction/DIR-2.md": DIR_2}

PROOFS_README = """# Proof attempts

`proofs/<id>/attempt-<n>.md`, one versioned attempt per file (the Researcher plugin's
`templates/notebook/_templates/attempt.md`; `py notebook.py attempt <id> --create`). A
failed attempt is kept: why it fails is knowledge. The object's `proof:` field points at
the current attempt.

The proofs written before the notebook layout (R6, 2026-09-28) stay where they were, in
the `## Proof` section of each object under `objects/`: they are verbatim, and several
are cleared as written. Only new attempts come here.
"""


def _kind_of(path):
    meta, _ = _fm.split_document(path.read_text(encoding="utf-8"), str(path))
    return meta.get("kind"), meta


def _link_fix(text, rec_dst, note_dst, here):
    """Retarget the relative links of a moved notes page (now at ``here``)."""
    def claim(m):
        dst = rec_dst.get(f"claims/{m.group(1)}.md")
        return f"]({os.path.relpath(dst, os.path.dirname(here)).replace(os.sep, '/')})" \
            if dst else m.group(0)

    def sibling(m):
        dst = note_dst.get(m.group(1))
        return f"]({os.path.relpath(dst, os.path.dirname(here)).replace(os.sep, '/')})" \
            if dst else m.group(0)
    text = re.sub(r"\]\(\.\./\.\./claims/([^)/]+)\.md\)", claim, text)
    return re.sub(r"\]\(([a-z0-9-]+\.md)\)", sibling, text)


def plan(math, date=DATE):
    """``(ops, problems)``. ``ops`` are ``(op, home, rel, payload)`` with op one of
    ``move`` (payload: new rel), ``write`` (payload: text), ``delete``."""
    math = Path(math)
    s1, lab = math / HOMES["s1"], math / HOMES["lab"]
    ops, problems = [], []
    INFO.clear()
    for h in (s1, lab):
        if not h.name.endswith("-academy") or not h.is_dir():
            raise SystemExit(f"{h}: not a migration worktree (*-academy); refusing")
    if (s1 / "objects").exists():
        raise SystemExit(f"{s1 / 'objects'} exists: R6 is already applied; refusing")
    # 1. records
    rec_dst = {}
    for folder in ("claims", "assumptions", "examples"):
        for p in sorted((s1 / folder).glob("*.md")):
            rel = f"{folder}/{p.name}"
            if p.name.lower() == "readme.md":
                ops.append(("delete", s1, rel, None))
                continue
            kind, meta = _kind_of(p)
            if not _schema.is_v2(meta):
                problems.append(f"{rel}: not a schema-v2 record (run R5 first)")
                continue
            if kind not in _schema.KINDS:
                problems.append(f"{rel}: kind {kind!r} is not an object kind")
                continue
            rec_dst[rel] = f"objects/{kind}/{p.name}"
            ops.append(("move", s1, rel, rec_dst[rel]))
    # 2. audits
    runs = {p.stem for p in (s1 / "computation" / "runs").glob("*.md")}
    audit_dst = {}
    for p in sorted((s1 / "computation" / "verdicts").glob("*.md")):
        meta, _ = _fm.split_document(p.read_text(encoding="utf-8"), p.name)
        subj = meta.get("subjects") if isinstance(meta.get("subjects"), list) else []
        if subj and all(s in runs for s in subj):
            rel = f"computation/verdicts/{p.name}"
            audit_dst[rel] = f"audits/{subj[0]}/{p.name}"
            ops.append(("move", s1, rel, audit_dst[rel]))
    for rel, dst in rec_dst.items():
        meta = _kind_of(s1 / rel)[1]
        for row in meta.get("evidence") or []:
            if _schema.evidence_cells(row)[1] in audit_dst:
                problems.append(f"{rel}: an evidence row names a moved audit; rewriting "
                                "s1 evidence rows is not implemented (none existed at R6)")
        text = (s1 / rel).read_text(encoding="utf-8")
        if any(a in text for a in audit_dst):
            INFO.append(f"{rel}: names a moved audit in its text (a `source:` field or a "
                        "quoted pointer); left verbatim, resolved by kb/r6-path-map.md")
    lab_fixes = []
    for p in sorted((lab / "claims" / "lab").glob("*.md")):
        text = p.read_bytes().decode("utf-8")
        new, moved = text, []
        for a, dst in audit_dst.items():
            old_ref, new_ref = f"{S1_REPO_NAME}:{a}", f"{S1_REPO_NAME}:{dst}"
            if old_ref in new:
                new = new.replace(old_ref, new_ref)
                moved.append(dst)
        if moved:
            row = _schema.history_row(date, "", "R6: the Slope1 verdict ref moved to "
                                      + ", ".join(sorted({d.rsplit('/', 1)[0] + '/'
                                                          for d in moved}))
                                      + " (layout move; the file is unchanged)")
            new = new.replace("\nhistory:\n", "\nhistory:\n  - "
                              + _fm.format_scalar_single(row) + "\n", 1)
            rel = f"claims/lab/{p.name}"
            lab_fixes.append(rel)
            ops.append(("write", lab, rel, new))
    # 3. notes -> journal
    note_dst = {}
    notes = sorted((s1 / "notes").rglob("*.md")) if (s1 / "notes").is_dir() else []
    for p in notes:
        nrel = p.relative_to(s1 / "notes").as_posix()
        if nrel not in NOTE_DATES:
            problems.append(f"notes/{nrel}: no date in NOTE_DATES; add it")
            continue
        note_dst[p.name] = journal_name(nrel)
    for p in notes:
        nrel = p.relative_to(s1 / "notes").as_posix()
        if nrel not in NOTE_DATES:
            continue
        here = journal_name(nrel)
        text = p.read_bytes().decode("utf-8")
        body = _link_fix(text, rec_dst, note_dst, here)
        head = (f"<!-- R6 {date}: moved from notes/{nrel} (last changed {NOTE_DATES[nrel]}), "
                "verbatim except that the relative links to moved files are retargeted. "
                "A topic page kept as a journal entry; old paths: kb/r6-path-map.md -->\n\n")
        ops.append(("write", s1, here, head + body))
        ops.append(("delete", s1, f"notes/{nrel}", None))
        for m in re.finditer(r"\]\((\.\./[^)]+\.md)\)", body):
            target = os.path.normpath(os.path.join(os.path.dirname(here), m.group(1)))
            target = target.replace(os.sep, "/")
            if target not in rec_dst.values() and target not in note_dst.values():
                problems.append(f"{here}: link {m.group(1)} does not resolve after R6")
    # 4. directions
    known = {Path(v).stem for v in rec_dst.values()}
    from .profiles import s1kb
    for rel, text in DIRECTIONS.items():
        try:    # the canonical form of the dialect (quotes only where it needs them)
            meta, body = _fm.split_document(text, rel)
            text = "---\n" + s1kb.serialize_v2(meta) + "---\n" + body
        except _fm.FrontmatterError as exc:
            problems.append(str(exc))
        for m in re.finditer(r"\]\((\.\./[^)]+\.md)\)", text):
            target = os.path.normpath(os.path.join(os.path.dirname(rel), m.group(1)))
            if target.replace(os.sep, "/") not in rec_dst.values():
                problems.append(f"{rel}: link {m.group(1)} does not resolve after R6")
        for m in re.finditer(r"(?m)^- s1:([^\s]+) —", text):
            if m.group(1) not in known:
                problems.append(f"{rel}: names s1:{m.group(1)}, which is no record")
        ops.append(("write", s1, rel, text))
    # 5. the (Q2) search record
    if Q2_RECORD.is_file():
        q2 = Q2_RECORD.read_bytes().decode("utf-8").replace("\r\n", "\n")
        head = (f"<!-- R6 {date}: the (Q2) search's libgap record, verbatim from the academy "
                "repo's docs-notes/extracted-q2-record.md (cut from the old flatsurf-computation "
                "libgap recipe file in Group B, destined for this notebook) -->\n\n")
        ops.append(("write", s1, Q2_RECORD_DEST, head + q2))
    else:
        problems.append(f"{Q2_RECORD}: missing")
    # 6. proofs/README.md and the path map
    ops.append(("write", s1, "proofs/README.md", PROOFS_README))
    rows = ([(a, b) for a, b in rec_dst.items()] + [(a, b) for a, b in audit_dst.items()]
            + [(f"notes/{p.relative_to(s1 / 'notes').as_posix()}",
                journal_name(p.relative_to(s1 / "notes").as_posix())) for p in notes
               if p.relative_to(s1 / "notes").as_posix() in NOTE_DATES]
            + [("assumptions/README.md", "views/assumptions.md (generated)")])
    pm = ["# R6 path map (frozen)", "",
          f"The notebook layout move of {date} (academy plan section 3.3, phase R6), by "
          "`py -m registry.migrate_r6`. Every moved file with its new path. Ids did not "
          "change; old paths in verbatim text, `source:` fields and quoted pointers "
          "(\"— claims/CRIT-9.md:31\") are resolved here. Line numbers in old pointers "
          "refer to the files before R5 and R6. Never edit this file.", "",
          "| old path | new path |", "|---|---|"]
    pm += [f"| `{a}` | `{b}` |" for a, b in sorted(rows)]
    ops.append(("write", s1, "kb/r6-path-map.md", "\n".join(pm) + "\n"))
    # checks
    dsts = [(o[1], o[3] if o[0] == "move" else o[2]) for o in ops if o[0] != "delete"]
    seen = set()
    for d in dsts:
        if d in seen:
            problems.append(f"{d[1]}: two files land here")
        seen.add(d)
    for rel, dst in rec_dst.items():
        kind = dst.split("/")[1]
        if _kind_of(s1 / rel)[0] != kind:
            problems.append(f"{rel}: kind does not match {dst}")
    for rel in lab_fixes:
        text = next(o[3] for o in ops if o[0] == "write" and o[1] == lab and o[2] == rel)
        for m in re.finditer(re.escape(S1_REPO_NAME) + r":(audits/[^\s|\"]+)", text):
            if m.group(1) not in audit_dst.values():
                problems.append(f"{rel}: evidence ref {m.group(1)} does not exist after R6")
    return ops, problems


def apply(ops):
    for op, home, rel, payload in ops:
        if op == "move":
            dst = home / payload
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(home / rel), str(dst))
    for op, home, rel, payload in ops:
        if op == "write":
            p = home / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(payload)
    for op, home, rel, payload in ops:
        if op == "delete" and (home / rel).exists():
            (home / rel).unlink()
    for home in {o[1] for o in ops}:
        for d in ("claims", "assumptions", "examples", "notes"):
            root = home / d
            if root.is_dir() and home.name == HOMES["s1"]:
                for sub in sorted(root.rglob("*"), reverse=True):
                    if sub.is_dir() and not any(sub.iterdir()):
                        sub.rmdir()
                if not any(root.iterdir()):
                    root.rmdir()


def run(math, date=DATE, apply_=False):
    ops, problems = plan(math, date)
    counts = {}
    for o in ops:
        key = (o[0], o[1].name)
        counts[key] = counts.get(key, 0) + 1
    for (op, home), n in sorted(counts.items()):
        print(f"{op:6} {n:4}  {home}")
    for i in INFO:
        print(f"INFO {i}")
    for p in problems:
        print(f"PROBLEM {p}", file=sys.stderr)
    if problems:
        print(f"migrate_r6: {len(problems)} problem(s); nothing written", file=sys.stderr)
        return 1, ops
    if apply_:
        apply(ops)
        print("migrate_r6: applied; now run `py tools/kb.py build` in the s1 home and "
              "`py scripts/claims.py render` in the lab")
    else:
        print("migrate_r6: plan only (give --apply to write)")
    return 0, ops


def main(argv=None):
    ap = argparse.ArgumentParser(prog="registry.migrate_r6", description=__doc__.split("\n")[0])
    ap.add_argument("--math", default=os.environ.get("ACADEMY_MATH", "C:/Work/Math"))
    ap.add_argument("--date", default=DATE)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    rc, _ = run(a.math, a.date, a.apply)
    return rc


if __name__ == "__main__":
    sys.exit(main())
