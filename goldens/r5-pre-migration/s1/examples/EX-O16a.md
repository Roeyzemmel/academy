---
id: EX-O16a
aliases: ["O16a", "O_16^a"]
title: "O_16^a, Cayley origami of Z/4 ⋊ Z/4"
summary: "16-square normal origami, G = ⟨a,b | a⁴=b⁴=1, bab⁻¹=a⁻¹⟩, H(1⁸), genus 5, Λ = 2Z×4Z: (Q2) fails at OA-3 exactly on gr(T_E), E = a²b² (CEX-3); smallest possible for the mechanism (BOUND-4)."
construction: "squares (i,j) in (Z/4)², label i+4j; σ(i,j) = (i+(−1)^j, j), τ(i,j) = (i, j+1): a 4×4 grid whose odd rows run backwards"
r: "(1,2,3,0,7,4,5,6,9,10,11,8,15,12,13,14)"
u: "(4,5,6,7,8,9,10,11,12,13,14,15,0,1,2,3)"
n: "16"
G_order: "16"
normal: "yes"
stratum: "H(1^8)"
genus: "5"
Lambda: "2Z×4Z"
level: OA-3
q2: "fails"
q2_by: [CEX-3]
K_min: "3 (on the met part only)"
claims: [CEX-3, CEX-4, CEX-5, BOUND-4, OPEN-9]
runs: []
source: "claims/CEX-3.md; writing/n8-generalization.md §4, §4.1"
added: 2026-09-24
---

## Facts

- "$r=(1,2,3,0,7,4,5,6,9,10,11,8,15,12,13,14)$, $u=(4,5,6,7,8,9,10,11,12,13,14,15,0,1,2,3)$." — claims/CEX-3.md:23
- "**Uniqueness of the unmet orbital**" — claims/CEX-3.md:40
- "other than $\{E\}$, so $\mathrm{gr}(T_E)$ is the **only** unmet orbital, with $K_{\min}=3$ on" — claims/CEX-3.md:44
- "All three have commutator type $2^8$, stratum $\mathcal H(1^8)$, genus 5, and are normal" — writing/n8-generalization.md:436
- "with $a\mapsto(1,0)$, $b\mapsto(0,1)$. Hence **$\Lambda=2\mathbb Z\times4\mathbb Z$**, not its transpose." — writing/n8-generalization.md:448
- "O_{16}^{a}/\langle T_E\rangle$ is a translation double cover of the Eierlegende" — claims/CEX-3.md:53
- "**(ii) Sharpness.** The bound is attained at level (A3), by $O_{16}^{a}$ = N22 (Proved)." — claims/BOUND-4.md:27

## History

- 2026-09-24: created during the relabelling; facts copied, nothing recomputed.
