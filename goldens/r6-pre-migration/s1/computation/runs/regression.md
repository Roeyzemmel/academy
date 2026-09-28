---
id: "regression"
status: "recorded"
family: "named surfaces (validation, not a hunt family)"
script: "experiments/2026-09-20_christoffel_regression.py"
class_short: "the 15 named surfaces only: unit square, 2×1 and 2×3 rectangles, L‑tromino, L/T/S‑tetrominoes, P/U/W/plus‑pentominoes, L of 2×2 blocks, EW, D_4 regular, Ornitho"
source: "computation/runs.md:18, 221-346 (HEAD 2026-09-24)"
---

## Row (verbatim)

| Item | Family | Script (FlatSurfLab) | Job id | Class / bound | Status | Outcome |
|---|---|---|---|---|---|---|
| regression of `fslab/christoffel/` against spec §6.1 and addendum-2 §4 | named surfaces (validation, not a hunt family) | `experiments/2026-09-20_christoffel_regression.py` | `20260920-122209_2026-09-20_christoffel_regression` (lingo, commit `8ceb09d`, not cleared — see notes); rerun `20260920-161100_2026-09-20_christoffel_regression` (lingo, commit `cadef3e`, `dirty: false`, `--bound 8`); rerun `20260922-200400_2026-09-20_christoffel_regression` (lingo, commit `c571b7d`, `dirty: false`, `--bound 8`); rerun `20260922-210229_2026-09-20_christoffel_regression` (lingo, commit `ff6e36f`, `dirty: false`, `--bound 8`, exit 0, 10 s) | the 15 named surfaces only: unit square, 2×1 and 2×3 rectangles, L‑tromino, L/T/S‑tetrominoes, P/U/W/plus‑pentominoes, L of 2×2 blocks, EW, $D_4$ regular, Ornithorynque; 4–48 squares; direction size $\le 8$. **Structurally cannot contain** any cyclic or abelian pillowcase cover beyond the EW and the Ornithorynque, or any parking garage that is not a polyomino. The `GROUP_CAP` of 20000 left four rows — L4, P5, W5, L3x2blocks — with `group_order: null`, and on those rows the TRUE rests on the bounded pass alone, not on the group-order check — so it **cannot refute (Q2)** | recorded | **Cleared at `ff6e36f`** on a clean per-job worktree (`computation/verdicts.md`, entry `## 2026-09-22 — 2026-09-20_christoffel_regression (rerun at ff6e36f)`), by two `result-auditor` runs, both SOUND, run sequentially (B after A returned positive), both on the primary model. mismatches: `[]`; all 15 verdicts TRUE from the bounded pass; the N6 block (32/48/56, missing orbital $\{7\}$, closing direction $(2,1)$) and the three new data (plus5 $|G|=240$; ORN $|G|=108$, $|Z|=3$, five orbitals, $K_{\min}=2$) reproduced independently by both auditors. Conditional on citing (both header sentences, no number or logic affected): (1) the `Result:` field still names job `20260922-200400` at `c571b7d` and must be rewritten to name job `20260922-210229` at `ff6e36f`; (2) the Claim-tested field's "$|G|$ on its five rows that carry a value" must read "five of its six rows" (addendum-2 §4 carries six $|G|$ values; the L-tetromino's 165888 is above `GROUP_CAP` and is not pinned). Allowed wording quoted in full in the verdicts entry, with class $C$'s exclusions. Open: the two header edits, then Roey's commit. |

## Notes (verbatim)

**Regression row.** Filed 2026-09-20 by `family-experimenter`. Every pinned value in the
script's `PINS` table already reproduces on the laptop under `py tests\run_all.py`
(45 new tests in `tests/test_christoffel.py`, all passing), including the corrected
$K_{\min}=3$ for the $2\times1$ rectangle and its coverage progression 32 / 48 / 56 over
the 56 ordered off-diagonal pairs. The queued run is the provenance-stamped record of
that, not a search. Queue command line:

```
scripts\queue.ps1 -Add experiments\2026-09-20_christoffel_regression.py -Label regression:christoffel-core -Note "reproduce spec 6.1 and addendum-2 4 on the named surfaces; validation is three labellings of the EW" -ScriptArgs "--bound 8"
```

**Update, 2026-09-20: the queued job ran, and the result is audited but not cleared.** It ran
on lingo at commit `8ceb09d` as `20260920-122209_2026-09-20_christoffel_regression` and wrote
`results/2026-09-20_christoffel_regression.json`. Two `result-auditor` runs both returned
**GAP** against the script's own header, not against its arithmetic (`computation/verdicts.md`,
entry `## 2026-09-20 — 2026-09-20_christoffel_regression`): the class cell misdescribes the
class it searched, the `Result:` line is unfilled, and the header claims checks the script
does not perform. Every number both auditors independently reproduced was correct. The
decision is **not cleared**, and the allowed wording is **none** — nothing here may be cited,
including the plus-pentomino and Ornithorynque figures below, until the header is fixed and
the script is rerun and re-settled.

**Pending, not yet citable.** The local unit-test run (`py tests\run_all.py`, laptop, no
commit hash, no provenance stamp, no audit) reproduced every hand-verified value in
`computation/spec.md` §6.1 and `computation/spec-addendum-2.md` §4 that the bounded pass
could reach, with no disagreement — **except** the L-tetromino's $\|G\| = 165888$, which the
`GROUP_CAP` of 20000 cannot reach and which the script pins as `None` rather than compares,
and **except** the (2T′) and primitivity columns, which this run does not check at all. It
additionally produced one value that table leaves blank: the plus-pentomino's monodromy order as **240**,
which is exactly the lower bound $4\,(m!/2)^{4/|Z|}$ of R2 Thm 3.4(h) at $m=5$, $|Z|=4$,
attained. Under `.claude/rules/computation.md` a laptop unit-test run with no commit hash, no
provenance stamp and no audit is not evidence, so this figure is **not yet citable**. It
becomes citable only when the queued run above produces it with a stamped result and two
`result-auditor` runs clear it; it would then fill in the `$|G|$` cell of the plus-pentomino
row of the addendum-2 §4 table, currently an em dash.

Separately, and with the same pending marker: the Ornithorynque oracle reproduced monodromy
of order 108, centraliser of order 3, genus 4 and not normal — matching four of the
predictions taken from Forni–Matheus–Zorich's printed permutations
(`.claude/rules/families.md`, family 2), computed here instead from the library's own
`CyclicCover([1,1,1,3])` construction. **"No 12-cycle" is not among the reproduced fields**:
it is not in the stamped JSON and came from a separate laptop unit test, not from this
oracle. These are two independent routes to the same surface, but the reproduction is again
a laptop run with no commit hash, no provenance stamp and no audit, so it is likewise
**not yet citable** pending a queued, stamped, audited run.

**Update, 2026-09-21: header fixes filed, working tree only** (drained from
`computation/inbox.md` entry "[2026-09-21] settle-fixes-cadef3e" by `status-keeper`,
2026-09-22). `family-experimenter` rewrote `experiments/2026-09-20_christoffel_regression.py`'s
header per the two-defect fix ordered by the `cadef3e` audit above: $|G|$ now stated as
COMPUTED on eleven rows, COMPARED on ten; plus5 $|G|=240$ stated as a new computed datum, not
a table reproduction; the `NAMED_PINS["ORN"]["orb"]=5` self-pin removed (`orb=None`), the
Ornithorynque's five orbitals stated as a new datum; "no 12-cycle" attributed to
`tests/test_christoffel.py::test_ornithorynque_oracle`; the stale "every case here is settled
TRUE" message reworded for ORN; `Result:` now records the `cadef3e` audit (GAP, not cleared)
and notes the corrected script awaits a rerun on hold. Evidence at filing time (local only,
FlatSurfLab working tree over HEAD `cadef3e`): `py -m py_compile`, exit 0;
`py scripts\check_experiments.py ... --strict` → "0 error(s), 0 warning(s) over 1 script(s)
-- strict"; `py tests\run_all.py` → "Ran 196 tests … OK (skipped=85)". Pinpoints checked in
this drain: `computation/verdicts.md` entries at lines 36–87 and 91–155 (confirmed present,
matching the entry's citation, read in this dispatch); `.claude/rules/computation.md`
"Environment facts" correction block (confirmed present, read in this dispatch). **None of
this is committed, and no rerun has happened**: still no allowed wording beyond the
prospective text already recorded in `computation/verdicts.md`.

**Update, 2026-09-22 (working tree only, `family-experimenter`).** Local checks repeated and
still green: `py -m py_compile` exit 0; `py scripts\check_experiments.py ... --strict` → 0
error(s), 0 warning(s); `py tests\run_all.py` → 196 tests, OK (skipped=85). **The regression
script's corrected header has not been run.** Its rerun and re-settle wait on the lingo
scheduler being deployed (see "Process notes" below). This row stays `done`, not `recorded`
— nothing here clears it.

**Update, 2026-09-22 (later same day, working tree only, `family-experimenter`): header
wording fixes ordered by the 2026-09-22 /settle pass on the c571b7d rerun** (drained from
`computation/inbox.md` entry "[2026-09-22] header-wording-fixes-c571b7d" by `status-keeper`,
2026-09-22). Wording-only header fixes; no computed logic, pin value or result JSON changed.
In `experiments/2026-09-20_christoffel_regression.py`, the `Claim tested` and `Result:`
fields are rewritten per the "Next action" of `computation/verdicts.md`, entry `## 2026-09-22
— 2026-09-20_christoffel_regression (rerun at c571b7d)` ("fix header lines 5 and 108 to name
the real sources and rewrite the `Result:` line to record this run"): `Claim tested` now
splits each pin by its actual source — `computation/spec-addendum-2.md` §4 for $|H^+|$,
$|H|$, $|Z|$, the orbital count and $K_{\min}$ on its ten polyomino rows and $|G|$ on its
five rows with a value; `computation/spec.md` §6.1, named as carrying only the columns $n$,
$G$, (A3), (A4)–(A6) tests, (Q1), (Q2), with cycle types in prose and "K=2 for the three
8-square examples" in item 4, for $|G|$ and the commutator cycle type on the unit square, the
2×1 rectangle, EW and $D_4$; everything else named as a hand fact or a new computed datum, not
a table. `Result:` is filled: "no disagreement with the pinned values over the class above;
NOT cleared, no wording from it may be cited", naming job
`20260922-200400_2026-09-20_christoffel_regression` at commit `c571b7d` and the GAP verdict
(header misattribution, `Result:` line unfilled at audit time), with the per-row numbers
(all 15 rows match their pins, mismatches `[]`, all 15 verdicts TRUE from the bounded pass,
the 2×1 coverage 32/48/56 with the size-2 gap `{7}` closed only by direction (2,1), plus5
$|G|=240$ and ORN as new data). Evidence at filing time (local only, FlatSurfLab working
tree): `py -m py_compile` on the three files (this script plus the two named in the
gap_reverify update above), exit 0; `py scripts\check_experiments.py <script> --strict` →
"0 error(s), 0 warning(s) over 1 script(s) -- strict"; `py tests\run_all.py` → "Ran 214 tests
in 8.294s" / "OK (skipped=93)", "ALL PASS", "ALL PASS", exit 0. Pinpoint checked in this
drain: `computation/spec.md` §6.1's table columns and item 4's sentence, confirmed exact
(same check as recorded in the gap_reverify update above); the rewritten `Claim tested` and
`Result:` fields, read directly in FlatSurfLab at their current working-tree state (confirmed
present as described, lines 4–20 and 118–126). **None of this is committed, and the header fix
does not by itself change the decision: the row stays `done`, not `recorded`, and the
allowed wording stays "none" until a rerun is re-settled.** Whether the header-only fix
requires a rerun is still Roey's decision, per the paragraph above.

**Update, 2026-09-22 (later same day): the header-attribution rerun ran and is cleared.**
Filed as job `20260922-210229_2026-09-20_christoffel_regression` at commit `ff6e36f`,
`dirty: false`, `--bound 8`, exit 0, lingo, 10 s. Two `result-auditor` runs, both SOUND, run
sequentially (B after A returned positive, per the sequential-verifier rule), both on the
primary model, cleared it against its own corrected header
(`computation/verdicts.md`, entry `## 2026-09-22 — 2026-09-20_christoffel_regression (rerun
at ff6e36f)`). All 15 rows match their pins, mismatches `[]`, all 15 verdicts TRUE from the
bounded pass; the N6 block and the three new data (plus5 $|G|=240$; ORN $|G|=108$, $|Z|=3$,
five orbitals, $K_{\min}=2$) reproduced independently by both auditors. This row is now
**citable**, once two remaining header sentences are fixed (wording only, no number, pin or
logic affected): the `Result:` field's job/commit naming, and the Claim-tested field's
$|G|$-row count ("five of its six rows", not "five rows"). Status moves to `recorded`.
Whether the header-only edit forces a further rerun: no — both auditors concur, by the
precedent of the `gap_reverify` `c571b7d` clearance.

> 2026-09-22: both citing conditions are now applied in FlatSurfLab's working tree
> (`experiments/2026-09-20_christoffel_regression.py`: `Result:` names job
> `20260922-210229_2026-09-20_christoffel_regression` at commit `ff6e36f`; Claim-tested (a)
> reads "five of its six rows that carry a value"), uncommitted. The wording above becomes
> quotable once Roey commits that header.
