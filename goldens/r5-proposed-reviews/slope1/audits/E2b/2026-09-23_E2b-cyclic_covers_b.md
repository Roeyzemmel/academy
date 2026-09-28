---
id: "2026-09-23_E2b-cyclic_covers_b"
date: "2026-09-23"
kind: "result"
subjects: ["E2b"]
clears: []
decision: "cleared, conditional on citing: the `Result:` field of `experiments/2026-09-23_cyclic_covers_b.py` is empty (checker W3) and must be filled with the wording below before it is quot"
source: "computation/verdicts.md:1180-1196 (HEAD 2026-09-24)"
---

## 2026-09-23 — 2026-09-23_cyclic_covers_b

Kind: result. Claim it bears on: audited against its own header — (Q2) over the square-tiled cyclic covers M_N(a), N ∈ {14, 16, 18} (E2b of the family hunt).
Commit audited: 34552b0 (job 20260923-123801_2026-09-23_cyclic_covers_b, dirty false, default arguments, exit 0, lingo, SageMath 10.7 / surface_dynamics 0.7.0, sweep 81 s). The work is in its parent 3bb691c; both runs confirmed the script and `fslab/` are unchanged between 3bb691c, 34552b0 and HEAD.

Run A: SOUND — "every one of the 238 TRUEs is a positive certificate — explicit Christoffel values of direction size ≤ 2 (σ^±1, τ^±1, σ^±1 τ^±1) whose cycles meet every G-orbital — re-derived in GAP for all 238 members inside the run and re-derived by me, stdlib-only and without `fslab.christoffel`, on eight named members including the largest groups; so the verdict does not rest on the completeness of any search, the enumeration is exactly one member per unit orbit (238, reproduced by an independent route), and the FALSE path is the same shared code that produced twelve FALSEs in E2a at the same commit."   [Fable 5.1, primary]
Run B: SOUND — "Every one of the 238 TRUE verdicts is a K = 2 coverage certificate that I re-derived from the recorded (r, u) alone by code sharing nothing with `fslab` (pair-orbit BFS for the G-orbitals, explicit cycles of the eight size-≤2 values), the same code says "not covered" on all twelve of E2a's N = 12 FALSE rows, and the enumeration independently comes out at 57 + 64 + 117 = 238 unit orbits with each orbit hit exactly once."   [Fable 5.1, primary]

Runs were sequential — B dispatched only after A returned positive (sequential-verifier rule, 2026-09-22); both on the primary model.

Findings both runs share: |G| computed on all 238 (range 28–2916; maxima 1372 / 512 / 2916 against the U bound 4(N/2)^4 = 9604 / 16384 / 26244); pure-vs-Sage crosscheck 0 mismatches, 0 unchecked on all 238; `gap_coverage_true_ok` true on all 238; raw/dedup cross-check on the 166 members with |G| ≤ 1000, **no BFS at all** on the 72 with |G| ∈ {1372, 2916}; every member closes at K = 2 exactly; 0 failed, 0 NOT RUN, 0 UNDECIDED, 0 structural violations; 18 normal members, all with the R Prop. 5.7 covering test agreeing. Run A: (2T′) fails on 112 of 238 members, all TRUE at K = 2.

Findings from one run: run B notes that in-run validation cannot catch an over-covering `coverage()`, since every pin expects TRUE and the (TRUE, K_min) pins go to `e0_contradictions`; the guard for an all-TRUE result is the per-member GAP re-check plus the independent re-derivations. Recommended: a negative pin (the 2×1 rectangle at K = 2, N6) in `validate_named` before E2c. Run B also notes that `matches_U: true` is not independent of the U count (a unit test pins the enumerator to it); both runs' own counts are.

Decision: **cleared**, conditional on citing: the `Result:` field of `experiments/2026-09-23_cyclic_covers_b.py` is empty (checker W3) and must be filled with the wording below before it is quoted; the result JSON is untracked and must be committed with it.
Allowed wording: "Job 20260923-123801_2026-09-23_cyclic_covers_b, commit 34552b0 (dirty false): no counterexample to (Q2) over class C. C = the 238 square-tiled cyclic covers M_N(a) with N ∈ {14, 16, 18} (57 / 64 / 117): every valid (N, a) up to multiplication of a by a unit of Z/N, S_4 class recorded and not quotiented, labelling `cyclic_cover == CyclicCover` on every member, every square corner marked, G-orbital labels. 238 run, 0 failed, 0 NOT RUN, 0 UNDECIDED; every member's bounded pass closed at K = 2 with the certificate re-checked in GAP; |G| ∈ [28, 2916], cross-checked against Sage on every member. C structurally cannot contain: N ∉ {14, 16, 18}; non-cyclic abelian covers (E3); non-abelian or non-pillowcase covers; primitive, 2-transitive or n-cycle-containing G (U; none arose); members with |G| > 50000 (none arose); (Q1); illumination; fewer marked points beyond the positive transfer; exact (A4)–(A6) levels. Blind spot: no enumeration of W decided any verdict (the 72 members with |G| > 1000 ran no search at all), so the run is silent on N2 beyond the 166 raw/dedup agreements, and on K_min > 2 in this range. The unit quotient rests on the FMZ duality lemma (settled per families.md §3; spot-checked by `is_isomorphic` on 10 members at N = 14)." Never "true", "holds" or "verified".
Open: neither run reran GAP or Sage themselves; FMZ duality on the other 228 members; the library-acceptance loop was run at N = 12 only (E2a), so "library accepts ⇒ enumerator includes" at N ∈ {14, 16, 18} rests on the four conditions being uniform in N; lingo's worktree beyond `dirty: false`, which ignores untracked files.
