---
id: "gap_reverify"
status: "recorded"
family: "none — a verification module, not a family"
script: "fslab/christoffel/gap_reverify.py + the GapReverify block of tests/test_christoffel_sage.py"
class_short: "one named origami per call; the raw |G|^2 BFS with no conjugacy dedupe, under group_limit 20000 elements and max_states 10^6, plus the exact G-orbit partition o"
source: "computation/runs.md:17, 27-220 (HEAD 2026-09-24)"
---

## Row (verbatim)

| Item | Family | Script (FlatSurfLab) | Job id | Class / bound | Status | Outcome |
|---|---|---|---|---|---|---|
| second implementation of the raw Christoffel BFS and of orbital coverage, in GAP, for `refutation-verifier` | none — a verification module, not a family | `fslab/christoffel/gap_reverify.py` + the `GapReverify*` block of `tests/test_christoffel_sage.py` | `20260920-123729_2026-09-20_gap_reverify_named` (lingo, commit `de0c1c5`, failed — see notes); superseded by rerun `20260920-161100_2026-09-20_gap_reverify_named` (lingo, commit `cadef3e`, **dirty**, `--group-limit 20000`, `heavy false`; launched twice, see notes); superseded by rerun `20260922-200400_2026-09-20_gap_reverify_named` (lingo, commit `c571b7d`, `dirty: false`, `--group-limit 20000`, `heavy false`) | one named origami per call; the **raw** $\|G\|^2$ BFS with no conjugacy dedupe, under `group_limit` 20000 elements and `max_states` $10^6$, plus the exact $G$-orbit partition of the $n(n-1)$ ordered off-diagonal pairs. **Structurally cannot contain** any member with $\|G\|>20000$ (the L-tetromino at 165888) or whose raw state count passes $10^6$ — both reported `UNDECIDED`, never `FALSE`; any intransitive $G$; anything about (Q1), illumination, strata or marked points; and any disagreement caused by a shared upstream input, since both paths are handed the *same* $(\sigma,\tau)$. It **cannot refute (Q2) on its own**: it can only agree or disagree with the Python path | recorded | **Cleared without the working-tree assumption**, at commit `c571b7d` on a clean per-job worktree (`computation/verdicts.md`, entry `## 2026-09-22 — 2026-09-20_gap_reverify_named (rerun at c571b7d)`), by two `result-auditor` runs, both SOUND, run sequentially (B after A returned positive), both on the primary model. This discharges the `cadef3e` entry's working-tree assumption below. Conditional on citing: the script's `Result:` line still names the `cadef3e` job and must be rewritten to name job `20260922-200400` before the JSON is committed or the wording quoted. Allowed wording: "no disagreement, at commit `c571b7d` on a clean per-job worktree, between the GAP-side and the pure-Python implementations of the raw $\|G\|^2$ Christoffel BFS (spec §5.1) and of orbital coverage (spec §5.2, defining form) over class $C$" — quoted in full in the verdicts entry, with $C$'s exclusions. **The uncommitted working-tree edit to `experiments/2026-09-20_gap_reverify_named.py` is broken** (an early `return` skips the N6/drop-one blocks and the only `raise`; a false "1327104 states" header; a nonexistent `skipped` JSON key) and must not be committed as-is or credited with this JSON. |

## Notes (verbatim)

**`gap_reverify` row.** Filed 2026-09-20 by `family-experimenter`. The module is the GAP-side
half of the two-implementations rule of `.claude/rules/computation.md`: the breadth-first
search of `computation/spec.md` §5.1 and the orbital coverage of §5.2 are written a second
time, in the GAP language, and run inside libgap. It shares with the Python path only the
input pair, the left-to-right word convention and the single `+1` of
`fslab/christoffel/gapinv.py`; it does not share the tree, the queue, the deduplication, the
orbital labelling or the coverage loop. Where §5.2 gives the efficient transversal recipe,
this route takes the defining one, `Orbits(G, pairs, OnTuples)`, so a wrong transversal in
`orbitals.py` cannot be reproduced by it.

**Wrapper filed, 2026-09-20** (drained from `computation/inbox.md` by `status-keeper`,
2026-09-21). `family-experimenter` filed a thin experiment wrapper,
`experiments/2026-09-20_gap_reverify_named.py`, that makes this row queueable: it calls
`gap_reverify.compare_with_python` on eight named surfaces, pins the GAP path alone against
the four heavy rows, runs one drop-one variant, and writes exactly one
`results/<stem>.json` at the end through `fslab.env.save_result`; the module and its
unittest block are unchanged. Class/bound as stated in the table row above. Evidence at
filing time (laptop only, no Sage or GAP run): `py -m py_compile
experiments\2026-09-20_gap_reverify_named.py` silent, exit 0;
`py scripts\check_experiments.py experiments\2026-09-20_gap_reverify_named.py --strict` →
`0 error(s), 0 warning(s) over 1 script(s) -- strict`; `py tests\run_all.py` → `Ran 176 tests
in 9.738s` / `OK (skipped=74)`, the 74 skips being the Sage/GAP classes including the whole
`GapReverify*` block; `scripts\queue.ps1 -Add …` → `queued
20260920-123729_2026-09-20_gap_reverify_named`, with a warning that the script was
uncommitted and `-Tick` would skip it until committed.

> Correction, 2026-09-22: this paragraph said the wrapper "pins the GAP path alone against
> the four heavy rows". **There are three heavy rows** — the L-tromino and the T- and
> S-tetromino; the 2×3 rectangle is a compared **light** row, not a heavy one. Independently
> confirmed by both `result-auditor` runs on the `cadef3e` rerun
> (`computation/verdicts.md`, entry `## 2026-09-21 — 2026-09-20_gap_reverify_named (rerun at
> cadef3e)`, Run A: "it says 'four heavy rows' when there are three"). The class/bound cell of
> this row already says "three" correctly; only this prose paragraph carried the slip.

The libgap import form was verified
by `grep` at filing time, not assumed: the direct form
`from sage.libs.gap.libgap import libgap` occurs only inside the documented post-`sage.all`
fallback in `gapinv.py:111` and in a docstring naming it as wrong; every live import site
uses `from sage.all import libgap`. Pinpoints checked in this drain: `computation/runs.md`
"Notes on the rows above" (this section, read in this dispatch); `.claude/rules/computation.md`
"The cross-repo contract" and "Environment facts, probed 2026-09-19 and 2026-09-20" (both
headers confirmed present, read in this dispatch); `computation/spec.md` §5.1, §5.2, §6.1, §7
and `computation/spec-addendum-2.md` §4 (all five section headers confirmed present, read in
this dispatch — the filing entry had marked these `uncited` pending this check, and they now
check out as real sections; their content was not re-verified against the script's specific
quotations, only their existence). This filing's job id, `20260920-123729_…`, is the same job
already recorded above as `failed` at `de0c1c5`; the fix (the trailing-`;` bug) and the
subsequent successful rerun as `20260920-161100_…` at `cadef3e` are recorded in the "Update"
paragraphs below and in `computation/verdicts.md`, entry
`## 2026-09-21 — 2026-09-20_gap_reverify_named (rerun at cadef3e)`.

**Not yet evidence, and not yet even executed.** No GAP call in the module has been run: the
laptop has no Sage and this project forbids a WSL Sage run for anything but unit tests.
Every call is marked `UNCONFIRMED` in its docstring. The promotion path is a run of
`py tests/run_all.py` under Sage on lingo, where the `GapReverifyValidation`,
`GapReverifyAgainstPython` and `GapReverifyDropOneVariants` classes stop skipping. **Until
that run is green, a `refutation-verifier` that calls this module is not a second
independent re-derivation**, and a candidate counterexample may not rest on it. The row
cannot go through `queue.ps1` as it stands, because the queue marks a job done when
`results/<stem>.json` appears and a unittest run writes none; filing it needs either a thin
`experiments/` wrapper that calls `compare_with_python` on the named surfaces and saves one
result, or a direct `scripts\run.ps1 tests\run_all.py -Target ssh:lingo -Push`.

**A refuted call form found on the way, and repaired.** `fslab/christoffel/gapinv.py`
documented `from sage.libs.gap.libgap import libgap` as CONFIRMED.
`.claude/rules/computation.md` ("Environment facts") **refutes** exactly that form as a
first Sage import under a plain `python` interpreter (circular `ImportError` on
`is_MPolynomial`, Sage 10.7), and both of FlatSurfLab's own probes,
`scratch/probe_libgap.py` and `scratch/probe_libgap_c8.py`, use `from sage.all import
libgap`.

> Correction, 2026-09-20: the entry as first filed attributed this refutation to the
> `flatsurf-computation` skill's `api-recipes.md` "§12.2". **That section does not exist** —
> the file ends at section 11 and contains no mention of `libgap` or `sage.all`. The
> substance above is correct and was re-verified against the two sources now named; the
> pinpoint was not. Three GAP calls in `gap_reverify.py` had been marked CONFIRMED on the
> same non-existent section and have been downgraded to UNCONFIRMED.
>
> Correction to the correction, 2026-09-20 (later same day): the paragraph directly above is
> itself wrong, and is left in place rather than deleted, per this file's supersession rule —
> the mistake is worth keeping visible since the same trap can recur. There are **two
> divergent copies** of `api-recipes.md` on this machine. The canonical one, which Roey has
> now designated as such, is reached through the `~/.claude/skills/flatsurf-computation`
> symlink (`C:\Users\Galit\.claude\skills\flatsurf-computation\references\api-recipes.md`,
> a symlink to the local-agent-mode-sessions skills-plugin copy): 2084 lines, 100597 bytes,
> mtime 2026-09-19 23:43, sha256 prefix `7ded754e`, sections 1–12, 43 `libgap` hits,
> containing `### 12.2 \`from sage.libs.gap.libgap import libgap\` as the *first* Sage
> import — **Refuted**` at line 1759, with exactly the ImportError text originally cited. The
> stale copy that the "correction" above was actually read against is
> `C:\Users\Galit\.claude\skills\synced\9966c44f-fba7-4bf1-bf39-f0161ffdb25c_5d44e6b0-c2a7-4ada-966a-d3697a222675\flatsurf-computation\references\api-recipes.md`:
> 1538 lines, 68825 bytes, mtime 2026-09-19 17:17, sha256 prefix `8343e646`, sections 1–11,
> zero `libgap` hits. Both copies were independently confirmed by direct read on 2026-09-20:
> the canonical copy's line 2084/2085 and the stale copy's line 1538/1539 match the counts
> above exactly, and a search for `libgap` in the stale copy returns nothing. **The original
> `§12.2` pinpoint was correct all along**, against the copy Roey has designated canonical; a
> backup of that canonical file is kept at
> `C:\Work\Math\FlatSurfLab\scratch\api-recipes.backup-2026-09-20.md`. This is a **bookkeeping**
> failure, not a mathematical one — no result or status label in this project ever rested on
> which copy was read. The three GAP calls in `gap_reverify.py` **stay UNCONFIRMED for now**
> regardless: `CONFIRMED` in this project means executed in the target environment, and none
> of the three have run on lingo. Five `api-prober` runs did independently re-derive them in
> WSL Sage on 2026-09-20, and all five confirmed them — corroboration, not clearance. The
> queued job whose green return would promote them to CONFIRMED is
> `20260920-123729_2026-09-20_gap_reverify_named`.

The failure mode was not a crash: the `ImportError` made `_have_libgap()` in
`tests/test_christoffel_sage.py` return `False`, so **every** `NEED_GAP` test would have
skipped on lingo and the run would have reported green with no GAP coverage at all. Both
sites now use `from sage.all import libgap`. This was unverified until the lingo run.

**Update, 2026-09-20: the queued job ran and failed.** `20260920-123729_2026-09-20_gap_reverify_named`
ran on lingo at commit `de0c1c5` and did not return green: `GAPError: can only evaluate a
single statement`, raised inside `validate()` at `fslab/christoffel/gap_reverify.py:419`
before any sweep executed, so no `results/<stem>.json` was written. The three GAP calls
above are therefore still not promoted to CONFIRMED. The cause is settled: a trailing `;`
after the closing `end` of a GAP function definition passed to `libgap.eval`; the fix is to
strip it, and this is now recorded as §12.8 of the canonical `api-recipes.md`. This failure
is itself confirmation of the UNCONFIRMED marking the call form carried — its docstring said
no probe had run it, and none had. The row's status is `failed`; a `failed` row answers no
question and nothing may rest on it.

**Update, 2026-09-21: header fixes filed, working tree only** (drained from
`computation/inbox.md` entry "[2026-09-21] settle-fixes-cadef3e" by `status-keeper`,
2026-09-22). `family-experimenter` restored the broken uncommitted edit to
`experiments/2026-09-20_gap_reverify_named.py` from `cadef3e` (backup at
`scratch/gap_reverify_named.dirty-2026-09-20.py` in FlatSurfLab) and rewrote its header:
`Result:` filled with the cleared wording and the run named; "four heavy rows" corrected to
three (the 2×3 rectangle is a compared light row); the "up to 1327104 states" bound
annotated with the actual 864/1728/1728; the "every GAP call is UNCONFIRMED" sentence
updated to match. GAP call markings in `fslab/christoffel/gap_reverify.py` and `gapinv.py`
were promoted from UNCONFIRMED to CONFIRMED for the forms the cleared `cadef3e` run
exercised: in `_BFS_GAP` the GAP-level `Group`, `Size`, `AsSSortedList`, `PositionSorted`,
`BlistList`; in `_COVER_GAP` `Orbits(G, pairs, OnTuples)`, `SizeBlist`, `Maximum`, `Minimum`,
`j^u`, `Group`/`IsTransitive`; the `libgap.eval` function form (already CONFIRMED in WSL, now
also on lingo); `gapinv.from_gap_perm` (`libgap.ListPerm(g, n)`); `gapinv.to_gap_perm`'s round
trip. Stay UNCONFIRMED / not exercised: the capped branches of the BFS (`m > maxGroup`,
`nStates > maxStates`), the intransitive `Error` branch, the two-argument `libgap.Orbits(H,
dom)` (not called by the module), and every other `gapinv` function (`gap_group`,
`group_order`, primitivity, transitivity, `Centralizer`, stabiliser invariants,
`RepresentativeAction`). Evidence at filing time (local only, FlatSurfLab working tree over
HEAD `cadef3e`): `py -m py_compile` on all four touched files, exit 0;
`py scripts\check_experiments.py <each script> --strict` → "0 error(s), 0 warning(s) over
1 script(s) -- strict" for both; `py tests\run_all.py` → "Ran 196 tests … OK (skipped=85)",
"ALL PASS", exit 0. Pinpoints checked in this drain: `computation/verdicts.md` entries at
lines 36–87 and 91–155 (both confirmed present, matching the entry's citation, read in this
dispatch); `.claude/rules/computation.md` "Environment facts" correction block (confirmed
present, read in this dispatch). **None of this is committed**, and at filing time
`tests/test_christoffel_sage.py` lines 87–88 still called `ListPerm` UNCONFIRMED (see the
2026-09-22 update below).

**Update, 2026-09-22 (working tree only, `family-experimenter`).** In
`experiments/2026-09-20_gap_reverify_named.py` the PINS comment now says three heavy rows,
matching the fix above; the `heavy_cases` comment describes 419904 and 1327104 as the
$|G|^2$ *completeness bound* for the raw BFS, not a cost, and notes that the `cadef3e` pins
actually reached 864/1728/1728 states. In `tests/test_christoffel_sage.py` the
`from_gap_perm` test docstring now says `ListPerm` is CONFIRMED on lingo by job
`20260920-161100` at `cadef3e`; the `OnPoints` route stays UNCONFIRMED. Local checks: `py
-m py_compile` exit 0; `py scripts\check_experiments.py ... --strict` → 0 error(s), 0
warning(s); `py tests\run_all.py` → 196 tests, OK (skipped=85). **None of this is
committed.**

**Update, 2026-09-22 (later same day, working tree only, `family-experimenter`): header
wording fixes ordered by the 2026-09-22 /settle pass on the c571b7d rerun** (drained from
`computation/inbox.md` entry "[2026-09-22] header-wording-fixes-c571b7d" by `status-keeper`,
2026-09-22). Wording-only header/docstring fixes; no computed logic, pin value or result JSON
changed. In `experiments/2026-09-20_gap_reverify_named.py`, the `Search class`, `Needs Sage`
and `Result:` fields are rewritten: `Result:` now names job
`20260922-200400_2026-09-20_gap_reverify_named` at commit `c571b7d` with the allowed wording
of the cleared verdicts entry, discharging the condition on citing recorded in
`computation/verdicts.md`, entry `## 2026-09-22 — 2026-09-20_gap_reverify_named (rerun at
c571b7d)` ("the script's `Result:` line ... still names job `20260920-161100` at `cadef3e`
... it must be rewritten to name this job before the JSON is committed or the wording
quoted"). In `fslab/christoffel/gap_reverify.py`, the module header's "Structurally cannot
contain" clause and the `GapValue` docstring are corrected per that same verdicts entry's
finding (a): the docstring no longer claims the recorded direction size is "first (hence, by
the FIFO order of the BFS, the least)" — it now says size is not in general the least
direction size, both BFS implementations dedupe on the evaluated pair and record it by
different rules (Python the first dequeue, GAP the minimum over dequeues), citing Python's
rule by code text (`values.py`, `complete_values`, `value_perms.setdefault(v, ...)` in the
dequeue loop) rather than by line number. Evidence at filing time (local only, FlatSurfLab
working tree): `py -m py_compile` on the three touched files, exit 0; `py
scripts\check_experiments.py <script> --strict` on each script → "0 error(s), 0 warning(s)
over 1 script(s) -- strict"; `py tests\run_all.py` → "Ran 214 tests in 8.294s" / "OK
(skipped=93)", "ALL PASS", "ALL PASS", exit 0. Pinpoints checked in this drain:
`computation/spec.md` §6.1 (table columns confirmed exactly `n`, `G`, `(A3)`, `(A4) test`,
`(A5) test`, `(A6) test`, `(Q1)`, `(Q2)`, cycle types in the prose beneath, and item 4's
sentence "All three 8-square examples give $K=2$", read in this dispatch); the rewritten
`Result:` lines and the `GapValue` docstring in both files, read directly in FlatSurfLab at
their current working-tree state (confirmed present as described). **None of this is
committed.** No status in either row's table cell changes: the `gap_reverify_named` row stays
`recorded`, the regression row stays `done`. **The regression script's corrected header still
awaits a rerun; whether a header-only fix requires one is Roey's decision, unchanged from the
paragraph above.**
