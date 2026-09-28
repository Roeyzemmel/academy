---
id: OBS-3
aliases: [N14, G3]
title: "Column form of the pillowcase-cover recipe"
summary: "The cyclic/abelian pillowcase recipe with data (A_p, a, χ) puts σ,τ in column form over A′ = ker χ, with c_{σ²}, c_{τ²}, c_{(στ)²} given by the pair sums a₀+a₃, a₂+a₃, a₀+a₂."
kind: prop
status: Proved
topics: [pillowcase-covers, obstructions]
depends_on: []
source: notes/03-q2/families-hunt.md:526-561
added: 2026-09-24
---

## Statement

### N14 (Proved) — column form of the pillowcase recipe

**N14.** Take the cyclic recipe (`fslab.christoffel.families.cyclic_cover`, the verbatim
transcription of `CyclicCover`) with $\mathbb Z/N$ replaced by a finite abelian group $A_p$ and
the parity by a character $\chi:A_p\to\mathbb Z/2$ with $\chi(a_j)=1$. Everything below
concerns the recipe's permutations, as its own worklist computes them: for cyclic $A_p$ this
is what `cyclic_cover` computes; for non-cyclic $A_p$, where there is no code
(`abelian_cover` raises `NotImplementedError`), the table **defines** the recipe. This
replaces a parenthetical that misdescribed N4's scope: N4 separately leaves open that the
recipe gives a translation surface covering the pillowcase with deck group $A$, the
`orientation_cover` cross-check, and the match with Wright's normalisation; N14 does not use
any of that.

Squares are $(i,\varepsilon)$, $i\in A_p$, $\varepsilon\in\{0,1\}$ (in the cyclic case,
$2i+\varepsilon$). Put $A':=\ker\chi$, base sheet $\eta\in\chi^{-1}(1)$. The type of a square
is $j=2\chi(i)+\varepsilon\in V$, its column coordinate $m=i$ ($\chi(i)=0$) or $m=i-\eta$
($\chi(i)=1$), $m\in A'$. Then
$$\sigma=[(0,\ a_0+a_3,\ a_1+a_2,\ 0),\ \pi_r],\qquad
\tau=[(-a_3-\eta,\ a_3-\eta,\ a_2+\eta,\ \eta-a_2),\ \pi_u]$$
over $A'$, and, using $\sum a_j=0$,
$$c_{\sigma^2}=s_1e_1,\quad c_{\tau^2}=s_2e_2,\quad c_{(\sigma\tau)^2}=\pm s_3e_3,\qquad
s_1=a_0+a_3,\ s_2=a_2+a_3,\ s_3=a_0+a_2\in A',$$
$$e_1=(1,1,-1,-1),\quad e_2=(-1,1,1,-1),\quad e_3=(1,-1,1,-1).$$
The sign is $+$ for $\sigma\tau$ composed right to left (N9/N12's convention: $\tau$ first),
and $-$ for families.md's `compose` convention ($\sigma$ first). In the cyclic case
$A'=2\mathbb Z/N$; halving identifies it with $\mathbb Z/(N/2)$, $\eta=1$, and in **halved**
coordinates this reproduces N8's two column forms exactly. N8's translation $T:i\mapsto i+4$
(sheet $\mapsto$ sheet $+2$) is $T_t$ with $t=2$ in **unhalved** $A'=2\mathbb Z/N$, i.e. $t=1$
in the halved $\mathbb Z/6$ of N8.

The hypothesis that the $a_j$ generate $A_p$ (H3) is **not used** in N14; it enters only
through transitivity (N15).

*Cleared by.* Two `claim-verifier` runs, both Proved, no inputs, sequential, both on
`claude-opus-5-5`; see `computation/verdicts.md`, entry "2026-09-24 — G3
(writing/n8-generalization.md) → N14". Source: `writing/n8-generalization.md` §2.1 (G3).

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:526-561 (relabel map).
