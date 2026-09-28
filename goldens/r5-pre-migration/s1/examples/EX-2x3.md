---
id: EX-2x3
aliases: ["2x3 rectangle", "R2x3"]
title: "2×3 rectangle, unfolded"
summary: "The unfolding of the 2×3 rectangle: |G| = 24, centraliser all of G, 23 orbitals; (Q2) holds (rectangle) with K_min = 3, by the same odd-multiplier obstruction as the 2×1 rectangle."
construction: "R Prop. 1.5 (GEO-8) unfolding of the 2×3 rectangle, every corner marked (regression row R2x3, '2 wide')"
r: "not recorded here"
u: "not recorded here"
n: "not recorded here"
G_order: "24"
normal: "unknown"
stratum: "not recorded here"
genus: "not recorded here"
Lambda: "not recorded here"
level: PA-7
q2: "holds"
q2_by: [CRIT-3, CRIT-13, regression]
K_min: "3"
claims: []
runs: [regression, gap_reverify]
source: "notes/04-examples/examples.md (R2 §8.2 table); computation/verdicts/2026-09-21_gap_reverify-cadef3e.md; computation/verdicts/2026-09-21_regression-cadef3e.md; .claude/rules/families.md"
added: 2026-09-24
---

## Facts

- "| $2\times3$ rectangle | 6 | $D_2\times D_3$ | no | order 6 | $G$ | 23 $=D_\delta$'s | yes | 3 |" (columns P, m, H+, primitive, H, C(G), orbitals, (2T), K_min) — notes/04-examples/examples.md:27
- "R2x3 24/23;" (Group/Size/Orbits, run B's direct libgap check) — computation/verdicts/2026-09-21_gap_reverify-cadef3e.md:35
- "R2's own regression table gives `K_min = 3` for the 2x3" — .claude/rules/families.md:319
- "All fifteen (Q2) verdicts TRUE from the bounded pass at K_min ≤ 3 — coverage certificates on the given labelling, not statements that (Q2) holds." (the regression's wording rule) — computation/verdicts/2026-09-22_regression-ff6e36f.md:25

## History

- 2026-09-24: created during the relabelling; facts copied, nothing recomputed.
