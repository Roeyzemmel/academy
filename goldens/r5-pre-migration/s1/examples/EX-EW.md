---
id: EX-EW
aliases: ["EW", "Eierlegende Wollmilchsau"]
title: "Eierlegende Wollmilchsau (EierlegendeWollmilchsau() labelling)"
summary: "The 8-square normal origami with monodromy Q₈, H(1,1,1,1), genus 3: OA-3 and GA-EP but not GA-RD, not PA-4; (Q2) holds with K = 2 (covering by ⟨i⟩,⟨j⟩,⟨k⟩). Primary validation case."
construction: "origamis.EierlegendeWollmilchsau() (surface_dynamics)"
r: "(1,2,3,0,5,6,7,4)"
u: "(4,7,6,5,2,1,0,3)"
n: "8"
G_order: "8"
normal: "yes"
stratum: "H(1,1,1,1)"
genus: "3"
Lambda: "2Z² (absolute periods (2,0,2))"
level: OA-3
q2: "holds"
q2_by: [CRIT-9, CRIT-3, E1, regression]
K_min: "2"
claims: [CRIT-9, CRIT-10, CRIT-3, STR-2, GEO-13, GEO-18, GEO-11, CEX-3, BOUND-3]
runs: [E1, regression, gap_reverify]
source: ".claude/rules/families.md §1; claims/CRIT-9.md; claims/STR-2.md; computation/runs/E1.md"
added: 2026-09-24
---

## Facts

- "8 squares, `r = (1,2,3,0,5,6,7,4)`, `u = (4,7,6,5,2,1,0,3)` 0-based, from" — .claude/rules/families.md:48
- "`origamis.EierlegendeWollmilchsau()`. Normal, monodromy the quaternion group of order 8," — .claude/rules/families.md:49
- "stratum H(1,1,1,1), genus 3, Veech group index 1, commutator cycle type 2^4. It satisfies" — .claude/rules/families.md:50
- "OA-3 ((A3)) and GA-EP ((EP)) but **not** GA-RD ((RD)) (R2 Prop. 3.1 prime, STR-2), and it" — .claude/rules/families.md:51
- "(Q2) is **known true** for it, with K = 2, by the covering test: the three shortest" — .claude/rules/families.md:57
- "absolute gives `(2,0,2)`. This database's Lambda is the absolute period lattice" — .claude/rules/families.md:188
- "| Eierlegende Wollmilchsau | $Q_8$, $n=8$, $\mathcal{H}(1,1,1,1)$ | $i,\ j,\ ij=k$ |" — claims/CRIT-9.md:31
- "So a commuting free $K_4$ exists, but one of" — claims/STR-2.md:38
- "- The Eierlegende Wollmilchsau (commutator $2^4$, no fixed points) is **not (A4)**" — claims/GEO-13.md:27
- "Every record closes at $K_{\min}=2$ — coverage certificates on the given labelling." — computation/runs/E1.md:14

## History

- 2026-09-24: created during the relabelling; facts copied, nothing recomputed.
