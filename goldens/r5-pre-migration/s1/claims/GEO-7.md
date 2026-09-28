---
id: GEO-7
aliases: [R Prop 1.4]
title: "A garage unfolding carries a free K_4 action on squares, so PA-4 ⇒ OA-3"
summary: "Under PA-4, Φ ≅ K_4 acts freely on the squares, Ω ≅ S(P)×K_4 and n = 4m with m the number of squares of P; hence PA-4 ⇒ OA-3"
kind: prop
status: Proved
level: PA-4
topics: [unfoldings, assumptions]
depends_on: []
source: notes/01-geometry/unfoldings.md:20-34
added: 2026-09-24
---

## Statement

> **Proposition 1.4 (Proved).** Under (A4), $\Phi \cong K_4$ acts **freely** on
> $\Omega$, and $\Omega \cong S(P)\times K_4$ where $S(P)$ is the set of unit
> squares of $P$; in particular $n = 4m$ with $m = |S(P)|$. Hence (A4) $\Rightarrow$ (A3).
>
## Proof

> *Proof.* The relation $\sim$ identifies only boundary points, so the four copies
> have pairwise disjoint interiors. Because $P$ is tiled by unit squares,
> $\partial P$ lies inside the square grid, so no unit square of $M$ is cut by a
> copy boundary; each therefore lies in exactly one copy. $\Phi$ permutes the
> copies simply transitively. $\square$

Freeness is on the **set of squares of $M$**, not on $M$ itself — $\Phi$ has fixed
points over the corners. The proof uses only the tiling: not the marking
convention, not embeddedness, not simple connectivity. It does need $M$ connected,
i.e. $P$ must have at least one horizontal and one vertical boundary edge, else
the edge-reflections do not generate $K_4$ and $G$ is not transitive.

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/unfoldings.md:20-34 (relabel map).
