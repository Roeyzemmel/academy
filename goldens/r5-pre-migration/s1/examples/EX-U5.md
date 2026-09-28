---
id: EX-U5
aliases: ["U-pentomino", "U5"]
title: "U-pentomino, unfolded"
summary: "The unfolding of the U-pentomino (m = 5): |G| = 14400, centraliser Z/2 (mid-line), H = A_5, five orbitals, (2T) fails, K_min = 2."
construction: "R Prop. 1.5 (GEO-8) unfolding of the U-pentomino, every corner marked (regression row)"
r: "not recorded here"
u: "not recorded here"
n: "not recorded here"
G_order: "14400"
normal: "unknown"
stratum: "not recorded here"
genus: "not recorded here"
Lambda: "not recorded here"
level: PA-6
q2: "not refuted (computation only)"
q2_by: [regression]
K_min: "2"
claims: [STR-5]
runs: [regression]
source: "notes/04-examples/examples.md (R2 §8.2 table, hand-checked); computation/runs/regression.md"
added: 2026-09-24
---

## Facts

- "| U‑pentomino | 5 | $S_5$ | yes | $A_5$ | $\mathbb Z/2$, mid-line | 5 | no | 2 |" (columns P, m, H+, primitive, H, C(G), orbitals, (2T), K_min) — notes/04-examples/examples.md:24
- "Checked: U5 ($|Z|=2$): $4\cdot60^2=14400=|G|$" — claims/STR-5.md:53
- "All fifteen (Q2) verdicts TRUE from the bounded pass at K_min ≤ 3 — coverage certificates on the given labelling, not statements that (Q2) holds." (the regression's wording rule) — computation/verdicts/2026-09-22_regression-ff6e36f.md:25

## History

- 2026-09-24: created during the relabelling; facts copied, nothing recomputed.
- 2026-09-24: q2 changed from "holds" to "not refuted (computation only)": it rested only on runs regression, and computation refutes, it never proves.
