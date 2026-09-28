---
id: EX-X5
aliases: ["plus-pentomino", "X5", "plus5"]
title: "plus-pentomino, unfolded"
summary: "The unfolding of the plus-pentomino (m = 5): |G| = 240, centraliser K₄, seven orbitals, (2T) fails, K_min = 2; the half-turn datum of OPEN-5 (met at K = 2)."
construction: "R Prop. 1.5 (GEO-8) unfolding of the plus-pentomino, every corner marked (regression row)"
r: "not recorded here"
u: "not recorded here"
n: "not recorded here"
G_order: "240"
normal: "unknown"
stratum: "not recorded here"
genus: "not recorded here"
Lambda: "not recorded here"
level: PA-6
q2: "not refuted (computation only)"
q2_by: [regression]
K_min: "2"
claims: [OPEN-5]
runs: [regression]
source: "notes/04-examples/examples.md (R2 §8.2 table, hand-checked); computation/runs/regression.md"
added: 2026-09-24
---

## Facts

- "| plus‑pentomino | 5 | $S_5$ | yes | $A_5$ | $K_4$ | $4+3=7$ | no | 2 |" (columns P, m, H+, primitive, H, C(G), orbitals, (2T), K_min) — notes/04-examples/examples.md:26
- "New computed data, not pins, corroborated by independent reimplementations: plus-pentomino |G| = 240, |Z| = 4, 7 orbitals" — computation/verdicts/2026-09-22_regression-ff6e36f.md:25
- "$H_5(2^4)^{\mathrm{odd}}$, 7 orbitals)" (run A's Sage/GAP spot check, in a not-cleared entry; stratum not filled in the field for that reason) — computation/verdicts/2026-09-22_regression-c571b7d.md:43
- "All fifteen (Q2) verdicts TRUE from the bounded pass at K_min ≤ 3 — coverage certificates on the given labelling, not statements that (Q2) holds." (the regression's wording rule) — computation/verdicts/2026-09-22_regression-ff6e36f.md:25

## History

- 2026-09-24: created during the relabelling; facts copied, nothing recomputed.
- 2026-09-24: q2 changed from "holds" to "not refuted (computation only)": it rested only on runs regression, and computation refutes, it never proves.
