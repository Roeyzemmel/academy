---
id: EX-T4
aliases: ["T-tetromino", "T4"]
title: "T-tetromino, unfolded"
summary: "The unfolding of the T-tetromino (m = 4): |G| = 1152, centraliser Z/2 (mid-line symmetry), five orbitals, (2T) fails, K_min = 2."
construction: "R Prop. 1.5 (GEO-8) unfolding of the T-tetromino, every corner marked (regression row)"
r: "not recorded here"
u: "not recorded here"
n: "not recorded here"
G_order: "1152"
normal: "unknown"
stratum: "not recorded here"
genus: "not recorded here"
Lambda: "not recorded here"
level: PA-6
q2: "not refuted (computation only)"
q2_by: [regression]
K_min: "2"
claims: []
runs: [regression, gap_reverify]
source: "notes/04-examples/examples.md (R2 §8.2 table, hand-checked); computation/runs/regression.md"
added: 2026-09-24
---

## Facts

- "| T‑tetromino | 4 | $S_4$ | yes | $S_4$ | $\mathbb Z/2$, mid-line, $\iota=(1,0)$ | 5 | no | 2 |" (columns P, m, H+, primitive, H, C(G), orbitals, (2T), K_min) — notes/04-examples/examples.md:21
- "T4 1152/5" (Group/Size/Orbits, run B's direct libgap check) — computation/verdicts/2026-09-21_gap_reverify-cadef3e.md:34
- "All fifteen (Q2) verdicts TRUE from the bounded pass at K_min ≤ 3 — coverage certificates on the given labelling, not statements that (Q2) holds." (the regression's wording rule) — computation/verdicts/2026-09-22_regression-ff6e36f.md:25

## History

- 2026-09-24: created during the relabelling; facts copied, nothing recomputed.
- 2026-09-24: q2 changed from "holds" to "not refuted (computation only)": it rested only on runs regression, and computation refutes, it never proves.
