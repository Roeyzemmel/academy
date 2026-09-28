---
id: "2026-09-22_regression-c571b7d"
date: "2026-09-22"
kind: "result"
subjects: ["regression"]
clears: []
decision: "not cleared. Allowed wording: none."
source: "computation/verdicts.md:1335-1400 (HEAD 2026-09-24)"
---

## 2026-09-22 — 2026-09-20_christoffel_regression (rerun at c571b7d)

Kind:            result
Claim it bears on: audited against its own header — the regression of `fslab/christoffel/`
against `computation/spec.md` §6.1 and `computation/spec-addendum-2.md` §4, rerun after the
header fixes ordered by the 2026-09-21 `cadef3e` audit above.
Commit audited:  `c571b7d` (job `20260922-200400_2026-09-20_christoffel_regression`,
`dirty: false`, `--bound 8`)

Run A: GAP — "the header pins $\Lambda$, $|Z|$ and the non-diagonal orbital count on the
unit-square, 2×1-rectangle, EW and $D_4$ rows (and $K_{\min}$ on the unit square) as
reproductions of `computation/spec.md` §6.1, but §6.1's validation table has columns $n$,
$G$, (A3)–(A6), (Q1), (Q2) only (plus cycle types in prose and 'K=2 for the three 8-square
examples' in item 4), so on those rows the script reproduces hand facts it does not name
rather than the table it names — the same species of misattribution that made plus5's
$|G|=240$ a GAP at `cadef3e` — and the `Result:` line at `c571b7d` still says 'The corrected
script has NOT been run', so the committed script carries no statement of this run at all."
[Fable 5.1, primary]
Run B: not dispatched — run A was negative (sequential rule, 2026-09-22).

Decision: not cleared. Allowed wording: none.

Record also: the two fixes ordered by the 2026-09-21 `cadef3e` audit are verified in place
(`|G|` compared on ten rows, plus5 `G=None` as a new datum; ORN `orb=None`). Every number is
right: all 15 rows match their pins independently of `check()`; mismatches: `[]`; all 15
verdicts TRUE; n6 block 32/48/56 with missing orbital $\{7\}$; addendum-2 §4 matches column
for column on its ten rows. The four §6.1-row values are correct by hand ($\Lambda$ for
rectangles by R Prop. 3.1, $\Lambda=2\mathbb Z^2$ for $Q_8$ and $D_4$ by abelianisation, and
$|Z|=n$ / $n-1$ orbitals for regular origamis) but are not in §6.1. JSON diff vs committed:
only date, commit and eleven seconds fields; nothing numeric changed across the `8ceb09d`,
`cadef3e` and `c571b7d` runs. Library import chain unchanged `cadef3e`→`c571b7d`. Run A's
independent Sage/GAP spot check reproduced plus5 $|G|=240$ (automorphism group 4,
$H_5(2^4)^{\mathrm{odd}}$, 7 orbitals) and ORN $|G|=108$, $|\mathrm{Aut}|=3$,
$H_4(2^3)^{\mathrm{even}}$, 5 orbitals, and EW $\Lambda=(2,0,2)$. Side notes: the script
exits 0 regardless of mismatches (lines 311–329), so the evidence is `mismatches: []` in the
JSON, not the exit code; every TRUE comes from the bounded pass ($K_{\min} \le 3$).

Prospective wording (NOT licensed; carried forward unchanged from the 2026-09-21 entry
above, recorded for after the fix): "No disagreement with the pinned values over class $C$:
the fifteen named surfaces (unit square, 2×1 and 2×3 rectangles, L-tromino, L/T/S-
tetrominoes, P/U/W/plus-pentominoes, L of 2×2 blocks, EW, $D_4$ regular, Ornithorynque;
4–48 squares; directions $|p|+|q| \le 8$), at commit `c571b7d`. Pinned to addendum-2 §4:
$|H^+|$, $|H|$, $|Z|$, #orbitals, $K_{\min}$ on its ten polyomino rows and $|G|$ on its five
rows with a value. Pinned to spec §6.1: $|G|$ and the commutator cycle type on unit, 2×1,
EW, $D_4$, and $K=2$ on EW and $D_4$; $K=3$ on the 2×1 rectangle to R2 Prop. 7.1/N6. Pinned
to hand facts, not to any table: $\Lambda$ on those four rows (R Prop. 3.1 for the
rectangles; $2\mathbb Z^2$ for $Q_8$ and $D_4$ by abelianisation), $|Z|=n$ and $n-1$
orbitals on the four regular rows, $K=2$ on the unit square. Not pinned, new computed data
corroborated by independent Sage/GAP reimplementations: plus-pentomino $|G|=240$; the
Ornithorynque's $|G|=108$, $|Z|=3$, five orbitals, $K_{\min}=2$, verdict TRUE. $C$ excludes:
any surface not named; any hunt-family member beyond the EW and the Ornithorynque; any
non-polyomino parking garage; $|G|$ on L4, P5, W5, L3x2blocks (UNDECIDED above
`GROUP_CAP`=20000); the (2T′), primitivity and hypothesis-level columns; the Ornithorynque's
stratum component. It cannot refute (Q2) on the fourteen regression rows; only the
Ornithorynque row could have."

> 2026-09-22: "$|G|$ on its five rows" above should read "$|G|$ on five of its six rows that
> carry a value (the L-tetromino's 165888 is above GROUP_CAP and is not pinned)", per the
> ff6e36f entry above.

Next action: fix header lines 5 and 108 to name the real sources and rewrite the `Result:`
line to record this run; whether a header-only fix requires another rerun is Roey's decision
(pending).

Open: the remote log; whether addendum-2 §4's $|G|$ values were hand-verified or computed;
the (2T′)/primitivity columns and L4's 165888 not reproduced.
