---
id: OBS-8
aliases: [N17, M2]
title: "Affine symmetry, translations and Klein groups of the two M_12 members"
summary: "Neither M_12 member has a D₄ symmetry (Aff = Aff_K4, order 48 / 96); centraliser Dic₃ of order 12 / order 24; δ = ι₂ has order 12 with δ² = T; 12 / 36 OA-3 Klein groups."
kind: prop
status: Proved
topics: [symmetry, counterexamples]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: []
source: notes/03-q2/families-hunt.md:689-718
added: 2026-09-24
---

## Statement

### N17 (Proved) — the affine symmetry, computed

**N17.**
1. **No $D_4$.** No affine automorphism of either N8 member has derivative a quarter-turn or
   a diagonal reflection — $\sigma,\tau$ have cycle types $4^6,6^4$ (member 1) resp.
   $2^{12},4^6$ (member 2), which such a map would have to exchange. Hence
   $\mathrm{Aff}_{D_4}(M)=\mathrm{Aff}_{K_4}(M)$, of order 48 (member 1) and 96 (member 2).
2. **Translations.** For member 1, $Z=C_{S_{24}}(G)$ has order 12, is non-abelian
   ($1^12^13^24^66^2$), and is $\cong\mathrm{Dic}_3=\langle T,b\mid T^6=1,b^2=T^3,bTb^{-1}=T^{-1}\rangle$,
   with $b$ of order 4 satisfying $b^2=T^3$. For member 2, $|Z|=24$ ($M/Z$ is normal, deck
   group $\cong G$).
3. $\delta=\iota_2$ has derivative $-I$, order 12 in both members, and $\delta^2=T$.
4. **Conjugation of $T$**, restricted to the involutions occurring in the (A3) Klein groups
   used downstream (N20's witnesses): member 1's $\mu_{1,5,9,13,17,21}$ invert $T$ and
   $\nu_6,\nu_{18}$ centralise it; member 2's $\mu_{6,12,18}$ centralise $T$ and the
   $\nu_{\mathrm{odd}}$ invert it. (This does **not** hold over the whole reflection type —
   outside the Klein groups the pattern is different — but neither N19 nor N20 needs the
   unrestricted form.)
5. **Regular fixed points of the derivative-$(-I)$ involutions**, member 1: $\iota_{3,11,19}$
   fix 0 centres/8 top- or right-edge midpoints of $gT$, $\iota_{7,15,23}$ fix 8/0; member 2:
   $\iota_{0,12}$ fix 12/0 with $gT$ of order $>2$, $\iota_{1,9,17}$ fix 8/0, six of the
   remaining $\iota$'s fix 4/4, and $\iota_{5,13,21}$ fix 0/8.
6. **(A3) Klein groups.** There are 12 in member 1 and 36 in member 2, each
   $\{1,\mu_a,\nu_b,\mu_a\nu_b\}$ with the three non-identity elements free on squares.

*Cleared by.* Two `claim-verifier` runs, both Proved, no inputs, sequential, both on
`claude-opus-5-5`; see `computation/verdicts.md`, entry "2026-09-24 — M2–M5
(writing/n8-quotient-mechanism.md), after repair → N17–N20". An earlier pass on the
unrepaired draft returned Partial and did not clear (same entry file, superseded block).
Source: `writing/n8-quotient-mechanism.md` §2 (M2).

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:689-718 (relabel map).
