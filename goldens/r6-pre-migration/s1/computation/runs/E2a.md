---
id: "E2a"
status: "recorded"
family: "cyclic covers of the pillowcase, $M_N(a_1,\\dots,a_4)$ (families.md §3)"
script: "experiments/2026-09-23_cyclic_covers_a.py (new), on fslab/christoffel/cyclic_sweep.py (new; shared with E2b)"
class_short: "every valid (N,a) with N even, 2le Nle12, one per unit orbit (116 if families.md's U count holds); W complete or bounded pass closed; G-orbital labels; group-li"
source: "computation/runs.md:20, 392-415 (HEAD 2026-09-24)"
---

## Row (verbatim)

| Item | Family | Script (FlatSurfLab) | Job id | Class / bound | Status | Outcome |
|---|---|---|---|---|---|---|
| E2a — (Q2) over the square-tiled cyclic covers $M_N(a)$, $N$ even, $2\le N\le12$, one member per unit orbit, $S_4$ class recorded and not quotiented; the states-vs-$\|G\|$ and wall-time-vs-$\|G\|$ probe that sets E2c's defaults; amended before its first run to add a `--total-budget-s` (default 18000) measured from process start and to move the sweep machinery into the shared module `fslab/christoffel/cyclic_sweep.py` so E2a/b/c cannot drift apart | cyclic covers of the pillowcase, $M_N(a_1,\dots,a_4)$ (families.md §3) | `experiments/2026-09-23_cyclic_covers_a.py` (new), on `fslab/christoffel/cyclic_sweep.py` (new; shared with E2b) | `20260923-123801_2026-09-23_cyclic_covers_a` (label `hunt:E2a`; `queue.ps1 -Tick` reported "submitted 20260923-123801_2026-09-23_cyclic_covers_a 34552b0"; lingo, commit `34552b0`; pending in lingo's FIFO behind `20260923-123615_2026-09-23_parabolic_descent`) | every valid $(N,a)$ with $N$ even, $2\le N\le12$, one per unit orbit (116 if families.md's U count holds); $W$ complete or bounded pass closed; $G$-orbital labels; group-limit 50000, member budget 300 s, total budget 18000 s (all default). **Structurally cannot contain**: $N>12$; non-cyclic abelian covers (E3); non-abelian or non-pillowcase covers; primitive, 2-transitive or $n$-cycle-containing $G$ (U: none in the family); members with $\|G\|>50000$ (failure rows); anything hiding in an UNDECIDED member (300 s member budget or $2\times10^6$-state cap); members **not run** when the 18000 s total budget runs out — listed under `not_run`, no verdict, excluded from the class searched; (Q1); illumination; exact (A4)–(A6) levels | recorded | **Cleared**, by two `result-auditor` runs, both SOUND, run sequentially (B after A returned positive), both on the primary model (`computation/verdicts.md`, entry `## 2026-09-23 — 2026-09-23_cyclic_covers_a`). Allowed wording: "Job `20260923-123801_2026-09-23_cyclic_covers_a`, lingo, commit `34552b0` (dirty false), all defaults, 28 s. Class $C$: every valid $(N,a)$ with $N$ even, $2\le N\le12$, one representative per unit orbit of $\mathbb Z/N$ — 117 members (116 for $4\le N\le12$, matching families.md's U count, plus the $N=2$ torus), $S_4$ class recorded and not quotiented, every corner marked, $G$-orbital labels, $W$ complete on every member (max $|G|$ 500; no cap or budget reached; 0 failed, 0 NOT RUN, 0 UNDECIDED). No counterexample over $C$ at $N\le10$, nor on 40 of the 52 members at $N=12$. Twelve members at N = 12 are recorded in the JSON's `candidates` — the six unit-orbit representatives of each of the S_4 classes {1,3,3,5} (|G| = 72, not normal) and {1,5,7,11} (|G| = 24, normal), each with W complete and compare_with_python AGREE; one representative of each is cleared as a refutation (entries above), the other ten are not independently verified. $C$ structurally excludes: $N>12$; non-cyclic abelian and non-pillowcase covers; (Q1); illumination; exact (A4)–(A6) levels. The identification of unit multiples as isomorphic at $N\in\{10,12\}$ rests on Forni–Matheus–Zorich duality (checked by `is_isomorphic` in-run for $N\le8$, and by run A for the twelve FALSE orbits). The states-vs-$|G|$ probe branch did not execute; state and wall-time counts come from the deciding searches." Conditional on citing: `Result:` is empty and must be filled; header line 2's "states-vs-$|G|$ probe" must say it did not run in this range; the result JSON must be committed with it. Never "true", "counterexample" or "(Q2) fails" in the `Result:` line itself — per-case verdicts stay in the JSON. Open: FMZ duality at $N\in\{10,12\}$ beyond the FALSE orbits; that `CyclicCover` is FMZ's $M_N(a)$; lingo's worktree beyond `dirty: false`. |

## Notes (verbatim)

**`cyclic_covers_a` row (E2a), amended before its first run.** The amendment entry
("cyclic_covers_a — total budget and shared module") is folded into the row above rather than
filed as a second row, since it changes the script before any run of it exists to distinguish.
Two changes, both named in the table's Item cell: (1) `--total-budget-s`, default 18000 s,
measured from process start, covering validation and the probe; members not started when it
runs out are listed under `not_run` and `counts.not_run`, carry no verdict, and are excluded
from the class searched; `--resume` picks them up from
`scratch/checkpoints/<stem>/members.jsonl`. (2) the sweep machinery (`member_name`, `members`,
`budgeted`, `ConjTimer`, `Extras`, `pipeline_failures`, `probe_row`, `summarise`, `run_sweep`,
`validate_named`, `acceptance_check`, `unit_orbit_check`) moved out of the script into the new
shared module `fslab/christoffel/cyclic_sweep.py`, so E2a and E2b cannot drift apart; new tests
`CyclicSweepPure` (5) and `CyclicSweepOnSmallMembers` (3). Evidence at filing time (local plus
WSL Sage, before the amendment): `py -m py_compile tests/test_christoffel_sage.py
tests/test_christoffel.py fslab/christoffel/cyclic_sweep.py` → `COMPILED`; `py -m unittest
tests.test_christoffel.CyclicSweepPure -v` → `Ran 5 tests in 0.068s` / `OK`; `py
tests\run_all.py` → `Ran 265 tests in 7.522s` / `OK (skipped=114)`; WSL Sage → `Ran 265 tests
in 14.367s` / `OK (skipped=1)`, all 8 `CyclicSweep*` tests `... ok`. This is unit-test scale,
not a result. Queued by the main session as job
`20260923-123801_2026-09-23_cyclic_covers_a` (label `hunt:E2a`); `-Tick` reported `submitted
20260923-123801_2026-09-23_cyclic_covers_a 34552b0`. Pending in lingo's FIFO behind
`20260923-123615_2026-09-23_parabolic_descent`, not yet run. **E2c is not filed.** Per the
coordinating session's instruction, nothing is recorded for it except: E2c ($N=20$) is held
until E2a's `probe_table` returns.
