---
id: STR-2
aliases: [R2 Prop 3.1′]
title: "GA-RD ⇔ GA-EP plus OA-3 with standard shifts; the EW is not a twisted diagonal"
summary: "(σ,τ) is a twisted diagonal iff GA-EP holds and OA-3's K_4 shifts the blocks by (1,0), (0,1); the EW satisfies OA-3 and GA-EP but not GA-RD"
kind: prop
status: Proved
topics: [structure, symmetry]
examples: [EX-EW]
depends_on: [STR-1]
source: notes/02-structure/reflection-data.md:90-112
added: 2026-09-24
---

## Statement

**Proposition 3.1′ ((RD) recognised; Proved).** Say (A3) holds *with standard shifts*,
(A3$^{\rm std}$), if the $K_4$ of (A3) can be chosen so that $\mu$ shifts the (EP)-blocks by
$(1,0)$ and $\nu$ by $(0,1)$ (under (A4) this is the deck group, so (A4) ⇒ (A3$^{\rm std}$)).
Then
$$\text{(RD)}\iff\text{(EP)}\wedge\text{(A3}^{\rm std}\text{)}.$$
## Proof

*Proof.* ⇒ by Theorem 3.1(a). ⇐: put $S=B_{(0,0)}$, $X_0=\mu\sigma|_S$, $X_1=\sigma\mu|_S$,
$Y_0=\nu\tau|_S$, $Y_1=\tau\nu|_S$ — involutions of $S$ since $(\mu\sigma)^2=\mu\sigma\mu\sigma=\sigma^{-1}\sigma=1$
and the shifts cancel — and identify $\Omega\cong S\times(\mathbb Z/2)^2$ by $(s,e)\mapsto\mu^{e_1}\nu^{e_2}s$
(a bijection because $\Phi$ permutes the blocks regularly). Then
$\sigma\,\mu^{e_1}\nu^{e_2}s=\mu^{e_1+1}\nu^{e_2}X_{e_1}s$ in all four cases, using $\nu\sigma=\sigma\nu$
and $\mu\nu=\nu\mu$; likewise for $\tau$. Transitivity of $G$ gives transitivity of the datum
and the required fixed points. $\square$

*Remark.* (A3)∧(EP) does **not** imply (RD): for the Eierlegende Wollmilchsau ($G=Q_8$
regular, (EP) holds since $Q_8/\{\pm1\}\cong(\mathbb Z/2)^2$) every solution of (A3) has the
form $\mu=\mathrm{conj}_j\circ R_h$, $\nu=\mathrm{conj}_i\circ R_{h'}$ with $h\in\{\pm i,\pm k\}$,
$h'\in\{\pm j,\pm k\}$ (right multiplications $R$ commute with $G$; involutivity forces $h$
to be inverted by $\mathrm{conj}_j$), and $\mu\nu=\nu\mu$ forces $jh'j^{-1}h=ihi^{-1}h'$, which
fails for $h=\pm i$, $h'=\pm j$ (it reads $-\varepsilon\delta k=\varepsilon\delta k$) and holds for
$(h,h')=(\pm i,\pm k)$ or $(\pm k,\pm j)$. So a commuting free $K_4$ exists, but one of
$\mu,\nu$ always has block shift $(1,1)$: (A3$^{\rm std}$) fails and the EW is not a twisted
diagonal. (A hand computation with the wrong, non-commuting pair had suggested otherwise;
the twisted-diagonal formula genuinely needs the standard shifts.)

## History

- 2026-09-24: migrated verbatim from notes/02-structure/reflection-data.md:90-112 (relabel map).
