---
id: GEO-2
aliases: [R Prop 1.1]
title: "OA-1 / OA-2 ⇔ an affine automorphism / involution with derivative −I"
summary: "M has an affine automorphism with derivative −I iff OA-1 holds, and an affine involution with derivative −I iff OA-2 holds; ι inverts exactly the palindromic words"
kind: prop
status: Proved
topics: [symmetry, geometry, assumptions]
depends_on: []
source: notes/01-geometry/symmetry-hypotheses.md:22-40
added: 2026-09-24
---

## Statement

> **Proposition 1.1 (Proved).** $M$ admits an affine automorphism with derivative
> $-I$ iff (A1) holds; it admits an affine **involution** with derivative $-I$ iff
> (A2) holds.
>
## Proof

> *Proof.* $-I$ acts on $\pi_1(\mathbb{T}^2\setminus\{0\}) = F_2$ through
> $\mathrm{SL}(2,\mathbb{Z}) \cong \mathrm{Out}^+(F_2)$ by
> $\alpha : x\mapsto x^{-1},\, y\mapsto y^{-1}$, which is orientation-preserving in
> the required sense since it fixes the puncture class up to conjugacy:
> $\alpha([x,y]) = [x^{-1},y^{-1}] = (xy)^{-1}[x,y](xy)$. The automorphism is
> realised iff $\pi\circ\alpha \sim \pi$, i.e. iff (A1). Affine automorphisms with
> derivative $-I$ correspond to the coset $\iota\,C_{S_n}(G)$, and $\psi^2$ is the
> translation automorphism given by $\iota^2$; so $\psi^2=\mathrm{id}$ iff
> $\iota^2=1$. $\square$

**What $\iota$ does to a general word.** For any word $w$,
$$\iota\,w(\sigma,\tau)\,\iota^{-1} = w(\sigma^{-1},\tau^{-1}),\qquad
w(\sigma,\tau)^{-1} = \operatorname{rev}(w)(\sigma^{-1},\tau^{-1}),$$
so $\iota$ inverts exactly the palindromic words. For Christoffel words more is
true.

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/symmetry-hypotheses.md:22-40 (relabel map).
