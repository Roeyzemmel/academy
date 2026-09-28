---
id: "2026-09-21_gap_reverify-cadef3e"
date: "2026-09-21"
kind: "result"
subjects: ["gap_reverify"]
clears: []
decision: "cleared modulo the assumption above (quoted verbatim), against commit cadef3e's"
source: "computation/verdicts.md:1524-1588 (HEAD 2026-09-24)"
---

## 2026-09-21 — 2026-09-20_gap_reverify_named (rerun at cadef3e)

Kind:            result
Claim it bears on: audited against its own header — the second, GAP-side, independent
implementation of the raw $|G|^2$ Christoffel BFS (`computation/spec.md` §5.1) and of orbital
coverage (§5.2) against the Python path, over eight named surfaces plus GAP-only pins on
three heavier rows.
Commit audited:  `cadef3e` (job `20260920-161100_2026-09-20_gap_reverify_named`,
**`dirty: true`**, `--group-limit 20000`, `heavy false`)

Run A: SOUND MODULO "lingo's tree at 22:05:50 differed from cadef3e only by
`results/2026-09-20_christoffel_regression.json`." The JSON's validation keys
(`pins`/`n6_progression`/`n6_missing_pairs`/`drop_one`) are the committed `validate()`'s
return shape, not the working tree's. The dirty flag is explained by the sibling regression
job rewriting that tracked results file at 20:13:52, and `env.py`'s dirty check is
`git diff --quiet HEAD`. Reproduced all 8 comparison rows, the L3/T4/S4 pins (raw states
864/1728/1728), N6 and drop-one with zero diffs. Header defects at `cadef3e`: the `Result:`
line still reads "not yet run", and it says "four heavy rows" when there are three (the 2×3
rectangle is a compared light row).   [Fable 5.1, primary]
Run B: SOUND. Verified the same assumption from the remote side: remote reflog checkout to
`cadef3e` at 19:47:36 with nothing later; the first launch's banner at 20:07:15 was clean;
the regression JSON was saved at 20:13:52; the second launch's banner at 21:54:52 read
"`cadef3e` (dirty)"; the remote tree is clean after `-Fetch`. Direct libgap confirms
Group/Size/Orbits on R2x1 8/7, EW 8/7, ORN 108/5, L3 648/4, T4 1152/5, S4 1152/5,
R2x3 24/23; a hand check of the 2×1 progression 32/48/56 agrees. Found the same two header
defects.
**New process finding**: the job was launched twice at `cadef3e` (logs `20260920-195053` and
`20260920-195837`). `queue.ps1:177-181` treats a nonzero return from `-Push -Detach` as a
failed start, but the `nohup` had already fired, so the next tick relaunched it. Three Sage
processes ran on the 4-core box, explaining the roughly 2-hour runtime. The two checkpoint
sequences are identical — a free second reproduction.   [Fable 5.1, primary]

Both auditors report that the **uncommitted working-tree edit** to
`experiments/2026-09-20_gap_reverify_named.py` is broken: an early `return` at lines 252–253
comes before the N6 block, the drop-one block and the only `raise`, so `validate()` can never
fail; its header claims "1327104 states" for the 1152 pins when the actual count is 1728; and
it mentions a `skipped` key that does not exist in the JSON. **That file must not be
committed as it stands, and this JSON must not be attributed to it.**

Decision: cleared modulo the assumption above (quoted verbatim), **against commit cadef3e's
script only**, and conditional on the header's `Result:` line being filled and "four heavy
rows" → "three".

Allowed wording (from Run B, consistent with Run A):

> No disagreement between the GAP-side and the pure-Python implementations of the raw
> $|G|^2$ Christoffel BFS (spec §5.1) and of orbital coverage (spec §5.2, in the defining
> form `Orbits(G, pairs, OnTuples)`) over class $C$: the eight named origamis unit square,
> 2×1 rectangle, 2×3 rectangle, EW, D4 regular, 3-square L, `CyclicCover([1,1,1,1])` and
> Ornithorynque (3–24 squares), compared field by field on $W$, direction sizes, the orbital
> partition, the covered ordered-pair set, the verdict, $K_{\min}$, the per-$K$ coverage
> counts and the raw state count; plus GAP-only pins on the L-tromino, T- and S-tetromino
> against addendum-2 §4. $C$ excludes any member with $|G| > 20000$ or raw states $>10^6$
> (UNDECIDED, never FALSE), any intransitive $G$, any hunt-family member beyond the EW and
> the Ornithorynque, any non-polyomino parking garage, anything about (Q1), illumination,
> strata or marked points, and any error in the shared inputs — $(\sigma,\tau)$, `gapinv`'s
> $\pm1$, the left-to-right word convention. It says nothing about (Q2) and cannot refute it.

This licenses `gap_reverify` as `refutation-verifier`'s second implementation within those
caps. Promoting the module's UNCONFIRMED GAP calls to CONFIRMED is now supported by this
evidence, but that edit lives in FlatSurfLab code and is not this repo's to make; it is
recorded here as pending.

Open: whether the broken uncommitted script, once corrected and committed, reproduces the
same result; the two named header fixes are not yet applied to any committed script.
