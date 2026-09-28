---
id: EX-L3
aliases: ["L-tromino", "L3"]
title: "L-tromino, unfolded"
summary: "The unfolding of the L-tromino (m = 3): |G| = 648, trivial centraliser, four orbitals (the ι-classes), (2T) holds, K_min = 2; genus 2, H(2,0^9)."
construction: "R Prop. 1.5 (GEO-8) unfolding of the L-tromino, every corner marked (regression row)"
r: "not recorded here"
u: "not recorded here"
n: "12"
G_order: "648"
normal: "unknown"
stratum: "H(2,0^9)"
genus: "2"
Lambda: "not recorded here"
level: PA-6
q2: "not refuted (computation only)"
q2_by: [regression]
K_min: "2"
claims: [GEO-16]
runs: [regression, gap_reverify]
source: "notes/04-examples/examples.md (R2 §8.2 table, hand-checked); computation/runs/regression.md"
added: 2026-09-24
---

## Facts

- "| L‑tromino | 3 | $S_3$ | yes | $S_3$ | 1 | 4 $=\iota$-classes | yes | 2 |" (columns P, m, H+, primitive, H, C(G), orbitals, (2T), K_min) — notes/04-examples/examples.md:19
- "L3 648/4" (Group/Size/Orbits, run B's direct libgap check) — computation/verdicts/2026-09-21_gap_reverify-cadef3e.md:34
- "$= 2\cdot2 + 5 = 9 = 4m-3k$; one 3-cycle; total $12 = 4m$ ✓. Genus 2," — claims/GEO-16.md:34
- "$\mathcal{H}(2,0^9)$ ✓." — claims/GEO-16.md:35
- "(d) [Run B] `l3_tuples()` is the one-cylinder member of the 3-square $H(2)$ orbit, not the" (gap_reverify's '3-square L' is a different surface from this one) — computation/verdicts/2026-09-22_gap_reverify-c571b7d.md:112
- "All fifteen (Q2) verdicts TRUE from the bounded pass at K_min ≤ 3 — coverage certificates on the given labelling, not statements that (Q2) holds." (the regression's wording rule) — computation/verdicts/2026-09-22_regression-ff6e36f.md:25

## History

- 2026-09-24: created during the relabelling; facts copied, nothing recomputed.
- 2026-09-24: q2 changed from "holds" to "not refuted (computation only)": it rested only on runs regression, and computation refutes, it never proves.
