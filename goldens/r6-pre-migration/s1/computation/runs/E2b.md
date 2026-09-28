---
id: "E2b"
status: "recorded"
family: "cyclic covers of the pillowcase, $M_N(a_1,\\dots,a_4)$ (families.md §3)"
script: "experiments/2026-09-23_cyclic_covers_b.py (new), on fslab/christoffel/cyclic_sweep.py"
class_short: "every valid (N,a) with Nin{14,16,18}, one per unit orbit (238 if families.md's U count holds); W complete or bounded pass closed; G-orbital labels; group-limit "
source: "computation/runs.md:21, 416-426 (HEAD 2026-09-24)"
---

## Row (verbatim)

| Item | Family | Script (FlatSurfLab) | Job id | Class / bound | Status | Outcome |
|---|---|---|---|---|---|---|
| E2b — (Q2) over $M_N(a)$ with $N\in\{14,16,18\}$, one member per unit orbit, $S_4$ class recorded and not quotiented; no probe | cyclic covers of the pillowcase, $M_N(a_1,\dots,a_4)$ (families.md §3) | `experiments/2026-09-23_cyclic_covers_b.py` (new), on `fslab/christoffel/cyclic_sweep.py` | `20260923-123801_2026-09-23_cyclic_covers_b` (label `hunt:E2b`; `queue.ps1 -Tick` reported "submitted 20260923-123801_2026-09-23_cyclic_covers_b 34552b0"; lingo, commit `34552b0`; pending in lingo's FIFO behind `20260923-123615_2026-09-23_parabolic_descent`) | every valid $(N,a)$ with $N\in\{14,16,18\}$, one per unit orbit (238 if families.md's U count holds); $W$ complete or bounded pass closed; $G$-orbital labels; group-limit 50000, member budget 300 s, total budget 18000 s (all default). **Structurally cannot contain**: $N$ outside $\{14,16,18\}$; non-cyclic abelian covers (E3); non-abelian or non-pillowcase covers; primitive, 2-transitive or $n$-cycle-containing $G$ (U); members with $\|G\|>50000$ (failure rows); anything hiding in an UNDECIDED member; members not run under the total budget; (Q1); illumination; exact (A4)–(A6) levels. Every FALSE with $\|G\|>1000$ rests on N2 (conj-only) and is labelled so | recorded | **Cleared**, by two `result-auditor` runs, both SOUND, run sequentially (B after A returned positive), both on the primary model (`computation/verdicts.md`, entry `## 2026-09-23 — 2026-09-23_cyclic_covers_b`). Allowed wording: "Job `20260923-123801_2026-09-23_cyclic_covers_b`, commit `34552b0` (dirty false): no counterexample to (Q2) over class $C$. $C$ = the 238 square-tiled cyclic covers $M_N(a)$ with $N\in\{14,16,18\}$ (57 / 64 / 117): every valid $(N,a)$ up to multiplication of $a$ by a unit of $\mathbb Z/N$, $S_4$ class recorded and not quotiented, labelling `cyclic_cover == CyclicCover` on every member, every square corner marked, $G$-orbital labels. 238 run, 0 failed, 0 NOT RUN, 0 UNDECIDED; every member's bounded pass closed at $K=2$ with the certificate re-checked in GAP; $\|G\|\in[28,2916]$, cross-checked against Sage on every member. $C$ structurally cannot contain: $N\notin\{14,16,18\}$; non-cyclic abelian covers (E3); non-abelian or non-pillowcase covers; primitive, 2-transitive or $n$-cycle-containing $G$ (U; none arose); members with $\|G\|>50000$ (none arose); (Q1); illumination; fewer marked points beyond the positive transfer; exact (A4)–(A6) levels. Blind spot: no enumeration of $W$ decided any verdict (the 72 members with $\|G\|>1000$ ran no search at all), so the run is silent on N2 beyond the 166 raw/dedup agreements, and on $K_{\min}>2$ in this range. The unit quotient rests on the FMZ duality lemma (settled per families.md §3; spot-checked by `is_isomorphic` on 10 members at $N=14$)." Never "true", "holds" or "verified". Conditional on citing: the `Result:` field is empty and must be filled with the wording above before it is quoted; the result JSON is untracked and must be committed with it. Open: neither run reran GAP or Sage themselves; FMZ duality on the other 228 members; the library-acceptance loop was run at $N=12$ only (E2a); lingo's worktree beyond `dirty: false`. |

## Notes (verbatim)

**`cyclic_covers_b` row (E2b).** Filed 2026-09-23 by `family-experimenter`, drained the same
day. Evidence at filing time (local plus the same WSL Sage run as the E2a amendment above,
since both share `cyclic_sweep.py`): `py -m py_compile experiments/2026-09-23_cyclic_covers_b.py`
→ `COMPILED`; `py scripts\check_experiments.py experiments\2026-09-23_cyclic_covers_b.py
--strict` → `0 error(s), 0 warning(s) over 1 script(s) -- strict`; `py tests\run_all.py` →
`Ran 265 tests in 7.522s` / `OK (skipped=114)` locally, `Ran 265 tests in 14.367s` / `OK
(skipped=1)` in WSL Sage. The script itself was not executed (experiments run only on
lingo). Queued by the main session as job `20260923-123801_2026-09-23_cyclic_covers_b` (label
`hunt:E2b`); `-Tick` reported `submitted 20260923-123801_2026-09-23_cyclic_covers_b 34552b0`.
Pending in lingo's FIFO behind `20260923-123615_2026-09-23_parabolic_descent`, not yet run.
