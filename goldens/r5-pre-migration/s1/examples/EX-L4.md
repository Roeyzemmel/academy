---
id: EX-L4
aliases: ["L-tetromino", "L4"]
title: "L-tetromino, unfolded"
summary: "The unfolding of the L-tetromino (m = 4): |G| = 165888, trivial centraliser, four orbitals, (2T) holds, K_min = 2. Above the regression's GROUP_CAP, so its group fields there are UNDECIDED."
construction: "R Prop. 1.5 (GEO-8) unfolding of the L-tetromino, every corner marked (regression row)"
r: "not recorded here"
u: "not recorded here"
n: "not recorded here"
G_order: "165888"
normal: "unknown"
stratum: "not recorded here"
genus: "not recorded here"
Lambda: "not recorded here"
level: PA-6
q2: "not refuted (computation only)"
q2_by: [regression]
K_min: "2"
claims: [STR-5, COMP-5]
runs: [regression]
source: "notes/04-examples/examples.md (R2 §8.2 table, hand-checked); computation/runs/regression.md"
added: 2026-09-24
---

## Facts

- "| L‑tetromino | 4 | $S_4$ | yes | $S_4$ | 1 | 4 | yes | 2 |" (columns P, m, H+, primitive, H, C(G), orbitals, (2T), K_min) — notes/04-examples/examples.md:20
- "$4\cdot12^4\le165888\le4\cdot24^4$." — claims/STR-5.md:54
- "L-tetromino |G| = 165888 reproduces in 0.6 s" — computation/verdicts/2026-09-22_regression-ff6e36f.md:23
- "All fifteen (Q2) verdicts TRUE from the bounded pass at K_min ≤ 3 — coverage certificates on the given labelling, not statements that (Q2) holds." (the regression's wording rule) — computation/verdicts/2026-09-22_regression-ff6e36f.md:25

## History

- 2026-09-24: created during the relabelling; facts copied, nothing recomputed.
- 2026-09-24: q2 changed from "holds" to "not refuted (computation only)": it rested only on runs regression, and computation refutes, it never proves.
