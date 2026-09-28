---
id: GEO-1
aliases: [R Prop 0.1]
title: "The symmetry chain OA-3 ⇒ OA-2 ⇒ OA-1, with OA-2 strictly stronger than OA-1"
summary: "A free K_4 action gives an involution inverting σ and τ; valid ι form a coset of the centraliser, so asking for an involution (OA-2) is a genuine extra condition over OA-1"
kind: prop
status: Proved
topics: [assumptions, symmetry]
depends_on: []
source: notes/00-setting/hypotheses.md:53-70
added: 2026-09-24
---

## Statement

> **Proposition 0.1 (Proved).** (A3) $\Rightarrow$ (A2) $\Rightarrow$ (A1), and
> (A2) is in general strictly stronger than (A1).
>
## Proof

> *Proof.* (A3) $\Rightarrow$ (A2): take $\iota=\phi(-1,-1)$, so
> $\iota^2=\phi\big((-1,-1)^2\big)=\phi(1,1)=1$. (A2) $\Rightarrow$ (A1) is trivial.
> For the gap: conjugation by $\iota^2$ fixes $\sigma$ and $\tau$, so
> $\iota^2\in C_{S_n}(G)$ always, and the set of valid $\iota$ is a coset
> $\iota\,C_{S_n}(G)$. (A2) asks that some member of that coset — i.e. some affine
> automorphism with derivative $-I$, modified by a translation automorphism — be
> an involution, a genuine extra condition. $\square$

(A3) is the weakest *algebraic* level and is what the structural results of §2
actually use, so those apply to any origami carrying the symmetry, whether or not
it is an unfolding (Remark 1.11).

*(A1)–(A3) are conditions on the generators, not on $G$: since inversion is an
anti-automorphism, a conjugation of $S_n$ inverting every element of $G$ would
force $G$ abelian.*

## History

- 2026-09-24: migrated verbatim from notes/00-setting/hypotheses.md:53-70 (relabel map).
