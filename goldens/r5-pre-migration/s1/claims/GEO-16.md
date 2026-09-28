---
id: GEO-16
aliases: [R Prop 1.9]
title: "Polyomino unfoldings: commutator of type 3^k 1^{4m−3k}, genus k+1"
summary: "Under PA-6 with m squares and k reflex corners: [σ,τ] has k 3-cycles and 4m−3k fixed points, M ∈ H(2^k, 0^{4m−3k}), genus k+1, and k = 0 iff P is a rectangle"
kind: prop
status: Proved
level: PA-6
topics: [unfoldings]
examples: [EX-L3]
depends_on: [GEO-9]
source: notes/01-geometry/unfoldings.md:106-121
added: 2026-09-24
---

## Statement

> **Proposition 1.9 (necessary conditions under (A6); Proved).** Let $P$ be a
> polyomino with $m$ squares and $k$ reflex corners. Then $P$ has $k+4$ convex
> corners (exterior angles sum to $2\pi$), and:
> - $[\sigma,\tau]$ is a product of exactly **$k$ 3-cycles and $4m-3k$ fixed points**;
> - the genus is $g = k+1$, and $M$ lies in $\mathcal{H}(2^k,\,0^{\,4m-3k})$;
> - $k=0$ iff $P$ is a rectangle iff $M$ is a torus.
>
## Proof

> *Proof.* All angles are $\pi/2$ or $3\pi/2$, so only $m\in\{1,3\}$ occurs among
> corners in Proposition 1.6, together with $m=2$ edge-interior points and interior
> lattice points. Reflex corners give the 3-cycles; everything else is a fixed
> point, and the counts add to $4m$. Then $2g-2 = \sum(\ell_i-1) = 2k$. $\square$

*Check (L-tromino).* $m=3$, one reflex corner, five convex corners, two
edge-interior lattice points, no interior lattice points. Fixed points
$= 2\cdot2 + 5 = 9 = 4m-3k$; one 3-cycle; total $12 = 4m$ ✓. Genus 2,
$\mathcal{H}(2,0^9)$ ✓.

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/unfoldings.md:106-121 (relabel map).
