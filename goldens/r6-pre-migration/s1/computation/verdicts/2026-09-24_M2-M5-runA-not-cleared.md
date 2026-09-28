---
id: "2026-09-24_M2-M5-runA-not-cleared"
date: "2026-09-24"
kind: "claim"
subjects: ["OBS-8", "OBS-9", "OBS-10", "OBS-11"]
clears: []
decision: "Run A returned Partial on all four items and on the unit. Under the"
source: "computation/verdicts.md:680-775 (HEAD 2026-09-24)"
---

## 2026-09-24 — M2–M5 (writing/n8-quotient-mechanism.md), run A only — not cleared

> Superseded by N17–N20 (Proved), 2026-09-24 — see the entry
> "M2–M5 (writing/n8-quotient-mechanism.md), after repair → N17–N20" above. The draft was
> repaired to fix findings F1–F6 below, and a fresh run A and run B on the repaired text both
> returned Proved.

Kind: claim. Claim it bears on: M2, M3, M4, M5 of `writing/n8-quotient-mechanism.md`, and
the four items as one unit. M2–M5 have no N-number; no status label moves on this pass.
Commit audited: n/a (claim verification, not a result JSON)

Run A: one `claim-verifier` on `claude-opus-5-5`, an equal primary per the amended rule
(Roey, 2026-09-24).

Decision: Run A returned Partial on all four items and on the unit. Under the
sequential-run rule (run B only after a positive A), no run B was dispatched.
**Not cleared.** No allowed wording.

Deciding sentence, verbatim: "The main result holds and is fully argued: for both members,
no $x\in M\setminus\Sigma^*$ illuminates $Tx$ or $T^{-1}x$. It follows from M4's forward
implication, with corner monodromies computed from the stored permutations, so the
Forni–Matheus–Zorich (FMZ) identification is genuinely not needed. However, each of the
four items contains one clause that is false or unargued as written."

Run A, verbatim:

```
VERDICT
item:       M2 (writing/n8-quotient-mechanism.md)
label:      Partial
confidence: CONFIRMED
model:      claude-opus-5-5
inputs:     none (Dic_3 via standard order-12 classification, uncited)
blocking:   M2(4) mu/nu clauses false as stated; true only for the (A3) Klein-group involutions
```
```
VERDICT
item:       M3 (writing/n8-quotient-mechanism.md)
label:      Partial
confidence: CONFIRMED
model:      claude-opus-5-5
inputs:     none ([N8p] Lemmas 1.1, 1.2 = N9, Proved)
blocking:   M3(2) as stated (u depending only on direction) is false pointwise; (1),(3) Proved; (2) holds with u = traversal-order lift of the loop through q(x)
```
```
VERDICT
item:       M4 (writing/n8-quotient-mechanism.md)
label:      Partial
confidence: CONFIRMED
model:      claude-opus-5-5
inputs:     none
blocking:   converse: existence of a corner-free leaf for x outside the stated set is not derived (true; exceptional set finite)
```
```
VERDICT
item:       M5 (writing/n8-quotient-mechanism.md)
label:      Partial
confidence: CONFIRMED
model:      claude-opus-5-5
inputs:     none (FMZ identification not needed: delta, Q_0, d_a re-derived from the stored permutations)
blocking:   "T^{±2}x and T^3x are reached" false at edge midpoints/centres; freeness and pillowcase pointers (M2, §3) do not support the step
```
```
VERDICT
item:       M2–M5 as one unit
label:      Partial
confidence: CONFIRMED
model:      claude-opus-5-5
inputs:     none
blocking:   F1 (M2(4)), F2 (M3(2)), F3 (M4 converse), F4 (M5 reachability); the core "no x in M\Σ* illuminates T^{±1}x" is established
```

Findings:
- **F1** M2(4) INVALID: the μ/ν centralise-or-invert claims are false for some involutions.
  Member 1: μ_0 and μ_12 centralise T, and ν_{3,7,11,15,19,23} invert it. Member 2:
  μ_{1,5,9,13,17,21} invert T, and ν_0, ν_12 centralise it. The claims are true only for
  involutions lying in (A3) Klein groups. Check M8/M9 for use of the unrestricted form.
- **F2** M3(2) INVALID as stated: φ is not determined by direction and column (direction
  (1,1), column 0 gives 2 and 4). It holds 128/128 with u the traversal-order lift of the
  loop through q(x).
- **F3** M4 converse UNJUSTIFIED: the corner-free leaf is not derived. Fix: two directions of
  one class leave a finite exceptional set, which is stronger than claimed.
- **F4** M5 OVERSTATED: "T^{±2}x and T^3x are reached" is false at explicit points (edge
  midpoints, square centres). Correct form: "outside a finite set".
- **F5** M5 pointers: "powers fix only vertices (M2)" and "Q_0 the pillowcase (§3)" do not
  support the step. Both facts are true and were re-derived.
- **F6** minor: "agrees exactly" should read "consistent with"; parity classes are relative
  to the pillowcase lattice; "δ² a translation" is redundant.
- **Checks:** exact rational tracing, 232 directions, about 34,600 traces per member; M4
  matched on the EW and the Ornithorynque; consistent with G4 (s = 6,8,4 and 0,6,8). Scripts
  are in the session scratchpad (m2check.py … m4gen.py).
- **Open:** re-verify after repair; both runs fresh.

Allowed wording: none.
Open: as recorded above (F1–F6); a run B, and a rerun of run A itself, after M2(4), M3(2),
M4's converse and M5's reachability sentence are repaired.
