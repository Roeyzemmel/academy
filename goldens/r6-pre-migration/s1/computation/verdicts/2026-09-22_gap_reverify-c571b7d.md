---
id: "2026-09-22_gap_reverify-c571b7d"
date: "2026-09-22"
kind: "result"
subjects: ["gap_reverify"]
clears: []
decision: "cleared. This discharges the working-tree assumption of the 2026-09-21 entry above"
source: "computation/verdicts.md:1226-1331 (HEAD 2026-09-24)"
---

## 2026-09-22 — 2026-09-20_gap_reverify_named (rerun at c571b7d)

Kind:            result
Claim it bears on: audited against its own header — the second, GAP-side, independent
implementation of the raw $|G|^2$ Christoffel BFS (`computation/spec.md` §5.1) and of orbital
coverage (§5.2) against the Python path, over eight named surfaces plus GAP-only pins on
three heavier rows.
Commit audited:  `c571b7d` (job `20260922-200400_2026-09-20_gap_reverify_named`,
`dirty: false`, `--group-limit 20000`, `heavy false`)

Run A: SOUND — "every number in results/2026-09-20_gap_reverify_named.json (all eight
comparison rows, the three heavy GAP pins at 864/1728/1728 raw states, the N6 progression
32/48/56 and the two drop-one rows) reproduces from a BFS/orbital implementation I wrote
from the spec without either fslab path, the JSON's commit c571b7d (dirty false) is the
commit of the script and modules I read, validate() ran and raises on any pin miss, and the
8 s runtime is the true cost of this workload."   [Fable 5.1, primary]
Run B: SOUND — "The working-tree JSON is a clean-tree (dirty: false) run of the unchanged
script at c571b7d whose content is byte-identical to the already-audited cadef3e result
outside provenance and the eight seconds timers, and an independent third implementation I
wrote from the spec reproduces every pinned and every compared number, including the three
heavy pins nobody had re-derived outside GAP — so the cadef3e clearance's working-tree
assumption is now discharged."   [Fable 5.1, primary]

Runs were sequential — run B was dispatched only after run A returned positive (the
sequential-verifier rule, 2026-09-22) — both on the primary model, Fable 5.1; neither on a
fallback.

Decision: cleared. This discharges the working-tree assumption of the 2026-09-21 entry above
(`## 2026-09-21 — 2026-09-20_gap_reverify_named (rerun at cadef3e)`). Runtime 8 s vs ~2 h
before: both runs confirm nothing was skipped; per-row compute is 0.119 s, the rest is Sage
start-up; the earlier ~2 h figure was the double launch under three competing Sage processes
already recorded in that entry. JSON diff against the committed `cadef3e` result: only date,
commit, `dirty` (`true`→`false`) and six seconds fields; no mathematical field differs.

Allowed wording (merge of both runs; A's extra exclusions are kept since the narrower
wording governs): "No disagreement, at commit `c571b7d` on a clean per-job worktree (job
`20260922-200400`, lingo, Sage 10.7, `--group-limit 20000`, `heavy false`), between the
GAP-side and the pure-Python implementations of the raw $|G|^2$ Christoffel BFS (spec §5.1)
and of orbital coverage (spec §5.2, in the defining form `Orbits(G, pairs, OnTuples)`) over
class $C$: the eight named tuples of `fslab.christoffel.families` / `polyomino` at that
commit — unit square, 2×1 rectangle, 2×3 rectangle, EW, $D_4$ regular,
`l3_tuples() = ((1,2,0),(2,1,0))` (labelled '3-square L'; the one-cylinder member of the L's
$\mathrm{SL}(2,\mathbb Z)$-orbit), `CyclicCover([1,1,1,1])`, Ornithorynque (3–24 squares,
$|G| \le 108$) — compared on $W$, the orbital partition, the covered ordered-pair set, the
verdict, $K_{\min}$, the per-$K$ coverage counts for $K \le K_{\min}$, and the raw state
count; plus GAP-only pins on the L-tromino, T- and S-tetromino against addendum-2 §4,
independently re-derived by both auditors. $C$ excludes: any member with $|G| > 20000$ or
raw states $> 10^6$ (never FALSE); any intransitive $G$; any hunt-family member beyond the
EW and the Ornithorynque; any non-polyomino parking garage; anything about (Q1),
illumination, strata or marked points; any error in the shared inputs — $(\sigma,\tau)$,
`gapinv`'s $\pm1$, the left-to-right word convention. Every member of $C$ is TRUE on both
paths with $K_{\min} \le 3$, so the FALSE/UNDECIDED branches, the
`complete_values(dedupe='conj')` fallback and both caps were not exercised. The 'direction
sizes' field is not an independent check (same state graph, same order) and is in both
implementations a traversal-dependent upper bound on the minimal direction size, exact on
$C$ but not in general. It says nothing about (Q2) and cannot refute it."

> 2026-09-22: describes the code at c571b7d/ff6e36f; the working-tree fix (runs.md,
> gap-reverify-size-and-undecided-fix) records exact least sizes via a separate bucket pass
> and reports incomplete searches as UNDECIDED — not yet run on lingo or settled.

Condition on citing: the script's `Result:` line
(`experiments/2026-09-20_gap_reverify_named.py:94-114`) still names job
`20260920-161100` at `cadef3e` with the modulo clause; it must be rewritten to name this job
before the JSON is committed or the wording quoted.

Open (neither run could check): the remote log of the job; untracked files in the remote
worktree (clean by construction, not observed); whether the EW/CyclicCover/Ornithorynque
tuples are the surfaces they are named for; the `--heavy` rows remain uncompared (pinned
only).

Findings to file as open follow-ups (not blocking this clearance):
(a) [Run A] Both BFS implementations dedupe on the evaluated pair, so the recorded direction
size is traversal-dependent, and they use different rules — Python records the first
dequeue (`values.py:156`, `setdefault`), GAP the minimum over dequeues
(`gap_reverify.py:278`). The `GapValue` docstring (`gap_reverify.py:478-485`) claims "first
(hence, by the FIFO order of the BFS, the least)", which is false. Run A's probe: on
L-tromino / T- / S-tetromino the two rules differ on 4/28/30 values and GAP's differs from
the exact size on 4/4/0 (e.g. recorded 17, exact 13). Consequence: a `--heavy` run is
predicted to report a spurious 'direction sizes' DISAGREE on all three heavy rows; GAP's
$K_{\min}$/`coverage_by_K` are exact only for small $K$ ($\le 5$) and otherwise an upper
bound / undercount. `tests`' `GapReverifyAgainstPython` covers only the eight light rows.

> Correction, 2026-09-22: the pinpoint `values.py:156` for Python's first-dequeue
> `setdefault` is wrong at commit `c571b7d`. Checked by the main session: `git show
> c571b7d:fslab/christoffel/values.py | grep -n setdefault` returns
> `164:        value_perms.setdefault(g, (w, p, q, a, b))` and
> `221:        value_perms.setdefault(v, (christoffel_word(*d), d[0], d[1], a, b))`. Line 164
> is the letters' `setdefault`, not the dequeue loop's; the dequeue-loop `setdefault` this
> finding means is line 221. The substance of finding (a) — that the recorded direction size
> is traversal-dependent and the docstring's "first (hence ... least)" claim is false — is
> unaffected; only the line number was wrong.

> 2026-09-22: describes the code at c571b7d/ff6e36f; the working-tree fix (runs.md,
> gap-reverify-size-and-undecided-fix) records exact least sizes via a separate bucket pass
> and reports incomplete searches as UNDECIDED — not yet run on lingo or settled.
(b) [Run B] An incomplete GAP search is recorded as a failed check and printed as
"DISAGREEMENT" (`gap_reverify.py:864-866`, script `:316-319`), not UNDECIDED as the header
says — matters only once a heavy member runs.
(c) [Run B] `coverage_by_K` compared on shared keys only (`:933-938`); the $|G|$ check
passes when Python's closure exceeds the limit (`:860-862`).
(d) [Run B] `l3_tuples()` is the one-cylinder member of the 3-square $H(2)$ orbit, not the
L-shaped presentation; the wording should carry the tuples.

Probes: session scratchpad `indep_probe.py` (A), `probe_indep_bfs.py` and
`probe_heavy_pins.py` (B).
