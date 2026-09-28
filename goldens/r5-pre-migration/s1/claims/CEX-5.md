---
id: CEX-5
aliases: [N24, G10]
title: "O_16^c fails (Q2) but is the transpose of O_16^a"
summary: "The abelian pillowcase datum A_p = Z/2×Z/4, χ = y mod 2 fails (Q2) on gr(T_(1,0)) at OA-3 by OBS-4, is not PA-4, and an explicit relabelling makes it the transpose of O_16^a: not new."
kind: prop
status: Proved
level: OA-3
topics: [counterexamples, pillowcase-covers]
examples: [EX-O16c, EX-O16a]
depends_on: [OBS-4, OBS-3, GEO-12, CEX-3]
source: notes/03-q2/families-hunt.md:998-1046
added: 2026-09-24
---

## Statement

### N24 (Proved) — $O_{16}^{c}$: in the abelian pillowcase family, but not a new example

**N24.** The datum is $A_p=\mathbb Z/2\times\mathbb Z/4$,
$a=((0,1),(0,1),(1,1),(1,1))$, $\chi(x,y)=y\bmod2$; squares are $2(x+2y)+\varepsilon$, tuples
`r = (1,10,3,8,15,4,13,6,9,2,11,0,7,12,5,14)`,
`u = (15,6,13,4,11,2,9,0,7,14,5,12,3,10,1,8)`. Here $s_1=s_3=(1,2)$, $s_2=(0,2)$.

**(Q2) fails for $O_{16}^{c}$**, on $\mathrm{gr}(T_{(1,0)})$ — an unmet orbital, not claimed to
be the only one — e.g. the pair $(0,2)$: $t=(1,0)\notin\bigcup\langle s_i\rangle=\{0,(0,2),(1,2)\}$,
by N15 (G4) applied to these $s_i$. **Level (A3)**, in sheet coordinates (square $(i,\varepsilon)$,
$i\in A_p$, label $2(x+2y)+\varepsilon$),
$$\mu(i,\varepsilon)=(-i,\ 1-\varepsilon),\qquad \nu(i,\varepsilon)=((1,0)-i,\ \varepsilon),$$
i.e. `mu = (1,0,3,2,13,12,15,14,9,8,11,10,5,4,7,6)`,
`nu = (2,3,0,1,14,15,12,13,10,11,8,9,6,7,4,5)`. In N14's column form over
$A'=\ker\chi=\{0,e,f,e+f\}$ (with $\eta=(0,1)$), $\sigma=[(0,e{+}f,e{+}f,0),\pi_r]$,
$\tau=[(e{+}f,e,e{+}f,e),\pi_u]$, $\mu=[(0,0,f,f),\pi_r]$, $\nu=[(e,e,e{+}f,e{+}f),\mathrm{id}]$;
every identity — $\mu\sigma=\sigma^{-1}\mu$, $\mu\tau=\tau\mu$, $\nu\sigma=\sigma\nu$,
$\nu\tau=\tau^{-1}\nu$, $\mu^2=\nu^2=1$, $\mu\nu=\nu\mu$ — is checked directly, and freeness
follows since $\mu,\mu\nu$ flip $\varepsilon$ and $\nu$ would need $2i=(1,0)$, impossible.
**Not (A4)**, by N10: $[\sigma,\tau]=\tau^2=T_{(0,2)}$ (type $2^8$) has no fixed point.

**Consequence: $O_{16}^{c}$ is in the $\mathrm{SL}(2,\mathbb Z)$-orbit of $O_{16}^{a}$**, so it
is **not a new counterexample**. By hand: $\sigma^4=\tau^4=1$, $\sigma\tau\sigma^{-1}=\tau^{-1}$,
$\langle\sigma\rangle\cap\langle\tau\rangle=1$, $|G|=16$, so $a\mapsto\tau$, $b\mapsto\sigma$ is
an isomorphism $G_{\mathrm{abs}}\to G$ (N22's group). Explicitly, the relabelling
$\varphi=$ `(0,15,8,7,1,14,9,6,10,5,2,13,11,4,3,12)` carries $(\tau_a,\sigma_a)$ (N22's pair,
transposed) to $(\sigma,\tau)$ here — so $O_{16}^{c}$ is the **transpose of $O_{16}^{a}$** —
with $\varphi(0)=0$, $\varphi(10)=2$, carrying N22's unmet pair $(0,10)$ to this one, $(0,2)$.
**So up to $\mathrm{SL}(2,\mathbb Z)$ the 16-square examples found so far are two,
$O_{16}^{a}$ and $O_{16}^{b}$ (N23), not three.** This settles the open line of N22's entry,
"whether $O_{16}^{a}\cong$ a transform of $O_{16}^{c}$": yes.

"Lies in family 4" is meant only in the sense that $O_{16}^{c}$'s permutations come from the
§2.1 recipe; the geometric reading of the recipe as a genuine pillowcase cover rests on N4,
**Not settled**, and is not claimed here.

*Cleared by.* Two `claim-verifier` runs, both Proved, CONFIRMED, sequential, both on
`claude-opus-5-5`: run A with inputs "none (N12–N15, N10 Proved; G6(b) not used)"; run B with
inputs "none (N15, N14, N13, N12, N10 and R Prop. 0.1 Proved; G6(b) not needed)". See
`computation/verdicts.md`, entry "2026-09-24 — G10 (writing/n8-generalization.md) → N24".
Source: `writing/n8-generalization.md` §4.3 (datum checks, the N15 argument, the G10 box with
$\mu,\nu$ and every identity, not (A4), and the paragraph showing $O_{16}^{c}$ is the transpose
of $O_{16}^{a}$ via the explicit $\varphi$).

**Update to N21–N22's "Not settled, explicitly" paragraph, above.** N23 and N24 settle both
$O_{16}^{b}$ and $O_{16}^{c}$: $O_{16}^{b}$ is a genuine second example, distinct up to
$\mathrm{SL}(2,\mathbb Z)$; $O_{16}^{c}$ lies in $O_{16}^{a}$'s $\mathrm{SL}(2,\mathbb Z)$-orbit
and is not a third. Spec S5 ($p=3$, $n=18$) and spec S2 (16 as the global minimum over all
(Q2) counterexamples, not only this mechanism) remain open, untouched by this pass.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:998-1046 (relabel map).
