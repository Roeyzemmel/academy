---
id: "2026-09-20_regression-8ceb09d"
date: "2026-09-20"
kind: "result"
subjects: ["regression"]
clears: []
decision: "not cleared"
source: "computation/verdicts.md:1592-1677 (HEAD 2026-09-24)"
---

## 2026-09-20 — 2026-09-20_christoffel_regression

Kind:            result
Claim it bears on: audited against its own header — the regression of `fslab/christoffel/`
against `computation/spec.md` §6.1 and `computation/spec-addendum-2.md` §4, and the
reproduction of item N6's coverage progression for the $2\times1$ rectangle.
Commit audited:  `8ceb09d` (JSON `provenance.git`, `dirty: false`; run on lingo
2026-09-20T12:55:16, Sage 10.7 / sage-flatsurf 0.8.0 / surface_dynamics 0.7.0, `--bound 8`)

Run A: GAP — the header's class cell says "every case in it is already settled, and a FALSE
verdict here would be a bug ... not a counterexample", but the Ornithorynque is an unsettled
member of spec §6.0's residual class, so its TRUE is a new datum and a FALSE would have been
a candidate refutation; and the `Result:` field is still the template placeholder, so the
script makes no statement in the repo's wording at all.   [Fable 5.1, primary]
Run B: GAP — every pinned value is right and was reproduced by an independent
implementation, but the six-field header claims checks the script does not perform, its
`Result:` line is still the template placeholder, and its search-class exclusions contradict
the class actually run.   [Fable 5.1, primary]

Decision: not cleared

The two runs agree on the verdict and, separately, on every number. Each wrote its own
implementation from scratch — no `fslab` import, its own unfolding from R Prop. 1.5, its own
Christoffel enumeration (A by tree descent, B by the lattice-path rule rather than the floor
formula), its own pair-orbit computation (B by BFS over ordered pairs rather than the
transversal recipe) — and both reproduced all fifteen rows: $|G|$, $|Z|$, the non-diagonal
orbital count, $K_{\min}$, genus and commutator cycle type, including plus-pentomino
$|G|=240$ and Ornithorynque $|G|=108$ with $|Z|=3$ and all six Forni–Matheus–Zorich cycle
types. Both reproduced N6 exactly: coverage 32 / 48 / 56 over the 56 ordered off-diagonal
pairs, the missing orbital $\{0,7\},\{1,6\},\{2,5\},\{3,4\}$, and $(2,1)$ as the only
closing direction, realised by $\sigma^2\tau$ / the word $xxy$.

**This is corroboration of the arithmetic, not a clearance.** The failure is in what the
script says it checked, which is the thing a later reader would rely on. Both runs are
recorded because a GAP found twice by independent routes is the informative case.

What the two runs found, merged (A and B overlap on 1, 2, 4, 5):

1. **The `Result:` field is unfilled** — line 44 is the literal
   `<fill in after running; copy the bound and class, never "true">`. Verified in the main
   session: `py scripts\check_experiments.py ... --strict` → `W3 ... Result field is
   unfilled`, exit 1.
2. **The class cell misdescribes the class.** "No non-normal origami outside the (A6) class"
   is false of the run — the Ornithorynque is one and is in it. "No surface whose group is
   too large for the bounded pass" is muddled: the bounded pass needs no group.
3. **Four rows hit `GroupTooLarge` at `GROUP_CAP = 20000`** — L4, P5, W5, L3x2blocks — and
   carry `group_order: null` with **no UNDECIDED marker**; on those rows `W_complete`,
   `raw_agrees`, `normal`, `normal_verdict` and `normal_agrees` are all null and the TRUE
   rests on the bounded pass alone.
4. **A pin was silently dropped**: addendum-2 §4 pins the L-tetromino at $|G| = 165888$; the
   script pins `None` because the cap cannot reach it, while the header lists $|G|$ among the
   compared fields. $|G|$ was therefore reproduced on 11 rows, not 15.
5. **The validation clause is overstated.** The header says three EW labellings give the same
   value set up to $G$-conjugacy; the code compares `w_ew` with **itself** plus a bare count
   comparison. The check with teeth is the brute-force relabelling search, which is genuine
   and would fail on a wrong $Q_8$ table — B notes it would also separate the EW from the
   $D_4$ regular origami, whose `_signature` is identical.
6. **The cross-checks were live on fewer rows than the header implies**: raw-vs-dedupe on 8
   of 15, the normal covering test on 5 (unit, 2×1, 2×3, EW, D4).
7. **`runs.md` overstates the run.** Its ORN paragraph credits the run with "no 12-cycle";
   that field is not in the stamped JSON and came from a laptop unit test. Its "every
   hand-verified value ... including all ten folding-group rows" excludes L4's $|G|$ and the
   (2T′) and primitivity columns.
8. **`NAMED_PINS["ORN"]["orb"] = 5` is a self-pin** (B): the FMZ side computation predicts
   $|G|$, $|Z|$, blocks and cycle types, not an orbital count.
9. **`n6.missing_orbital_pairs` is `cycles(winner)` with the winner hard-coded as the $(2,1)$
   value**, not derived from `missing`. The reported pairs are right and consistent with the
   computed `closing`, but the field's name overstates its provenance.

Allowed wording: **none.** Nothing from this result may be cited, including the two figures
that motivated it — plus-pentomino $|G| = 240$ and Ornithorynque $|G| = 108$ — even though
both auditors reproduced them independently. Under `.claude/rules/computation.md` a result is
citable only once cleared, and this one is not. The fixes are bookkeeping, not mathematics:
fill `Result:` in the repo's wording, correct the class cell and the two false exclusions,
mark the four capped rows UNDECIDED, qualify $|G|$ in the Claim field, rewrite Validation to
what the code does, state which rows had each cross-check live, and split the Ornithorynque
out as a new datum rather than a regression row. Since that changes the script, it must be
rerun — a one-second job — and re-settled.

Open: neither run could execute Sage or GAP, so the EW / CyclicCover / ORN permutation tuples
remain transcriptions that neither re-probed, and the ORN independence is only downstream of
those shared tuples. Neither could check the ORN's stratum **component** (the even one),
L4's $|G| = 165888$, or whether addendum-2 §4's "hand-verified" $|G|$ values (1152, 1152,
14400) were hand-verified or produced by the 2026-09-08 session's own code — if the latter,
that oracle is a prior code run and not independent. B notes `git_state()` ignores untracked
files, so `dirty: false` holds modulo those, and the result JSON is itself still untracked.
