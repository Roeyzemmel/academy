---
id: EX-ORN
aliases: ["Ornithorynque", "ORN", "M_6(1,1,1,3)"]
title: "Ornithorynque, CyclicCover([1,1,1,3])"
summary: "The 12-square non-normal origami M_6(1,1,1,3) in H_4(2³)^even: |G| = 108, |Z| = 3, five orbitals, Λ = 2Z², not PA-4. E1 and the regression record it with K_min = 2."
construction: "origamis.CyclicCover([1,1,1,3]), repr M_6(1,1,1,3); no dedicated generator"
r: "(1,8,7,2,5,0,11,6,9,4,3,10)"
u: "(7,6,5,0,11,10,9,4,3,2,1,8)"
n: "12"
G_order: "108"
normal: "no"
stratum: "H_4(2^3), even component"
genus: "4"
Lambda: "2Z²"
level: OA-3
q2: "not refuted (computation only)"
q2_by: [E1, regression]
K_min: "2"
claims: [GEO-13]
runs: [E1, regression, gap_reverify]
source: ".claude/rules/families.md §2; computation/runs/E1.md; claims/GEO-13.md"
added: 2026-09-24
---

## Facts

- "nb_squares 12   stratum H_4(2^3), component ^even   genus 4   veech_group().index() 1" — .claude/rules/families.md:68
- "r_tuple (1, 8, 7, 2, 5, 0, 11, 6, 9, 4, 3, 10)" — .claude/rules/families.md:69
- "u_tuple (7, 6, 5, 0, 11, 10, 9, 4, 3, 2, 1, 8)" — .claude/rules/families.md:70
- "**It is NOT a normal origami** — settled against Matheus-Yoccoz (arXiv:0912.1425), who give" — .claude/rules/families.md:73
- "Ornithorynque data, reproduced from the library construction (not from FMZ's printed tuples): $|G|=108$, $|Z|=3$, five orbitals" (level (A3) there is a computed record field, stated 'with (A4)–(A6) as necessary flags only') — computation/runs/E1.md:14
- "no 12-cycle, $H_4(2^3)^{\mathrm{even}}$, genus 4, $\Lambda=2\mathbb Z^2$, level (A3) with (A4)–(A6) as necessary flags only" — computation/runs/E1.md:14
- "It cannot refute (Q2) beyond what the cleared E0 row already decided (ORN and EW both TRUE, $K_{\min}=2$)" — computation/runs/E1.md:14
- "- The $D_4$ regular origami (commutator $2^4$) and the Ornithorynque (commutator $3^3\,1^3$," — claims/GEO-13.md:30
- "Never "(Q2) true"." (E1's wording rule) — computation/verdicts/2026-09-23_E1-ew_ornithorynque_record.md:24

## History

- 2026-09-24: created during the relabelling; facts copied, nothing recomputed.
- 2026-09-24: q2 changed from "holds" to "not refuted (computation only)": it rested only on runs E1, regression, and computation refutes, it never proves.
