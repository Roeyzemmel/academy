---
id: GEO-21
aliases: [R2 Prop 2.4]
title: "What PA-6 adds: cycle types, symmetries, GA-D0, rectangle witnesses"
summary: "Under PA-6: cycle types of σ, τ, [σ,τ]; plane symmetries act on the datum; GA-D0 holds unless PA-7; pairs within a rectangle touching two walls lie in R^pow"
kind: prop
status: Proved
level: PA-6
topics: [unfoldings, symmetry, orbitals]
depends_on: [DEF-2, GEO-16, DEF-1]
source: notes/01-geometry/unfoldings.md:189-209
added: 2026-09-24
---

## Statement

**Proposition 2.4.** Under (A6) (embedded polyomino):
(a) *Cycle types.* $\sigma$-orbits are $\rho\times\{\beta\}$ over row segments $\rho$, of length
$2L_\rho$; $\tau$ likewise over column segments; $\sigma,\tau,\sigma\tau$ are fixed-point-free.
$[\sigma,\tau]$ has one $3$-cycle per reflex corner and fixed points otherwise
(R Prop. 1.9); $M\in\mathcal H(2^k,0^{n-3k})$.
(b) *Symmetries.* An isometry $\theta$ of the plane with linear part $L_\theta\in K_4$ preserving
$P$ is an automorphism of the datum permuting the generators by $\lambda(\theta)\in K_4$
($L\leftrightarrow R$ iff $L_\theta$ reverses $x$, etc.); $\lambda(\theta)=1$ iff the axis/centre
is on the integer grid.
(c) *(D0).* If (A7) fails then (D0) holds with $u=\sigma$ or $\tau$; under (A7), $G$ is abelian
regular, $n=|A|$ and $D_0=\emptyset$. *(Order of $(1,0)$ in $A$ is the generator $\lambda_1$ of
$\Lambda\cap\mathbb Ze_1$, dividing all $2L_\rho$; failure in both directions forces all row
segments of one length $L$, all column segments of one length $L'$, and then a bottom-most
row segment with the column segments through it is an $L\times L'$ rectangle with nothing
adjacent, so $P$ is that rectangle.)*
(d) *Rectangle witnesses.* If $R\subseteq P$ is a rectangle of cells with a vertical side and a
horizontal side on $\partial P$, then all pairs $((s,g),(s',g'))$ with $s,s'\in R$ lie in
$R^{\mathrm{pow}}$, each realised by one Christoffel power (unfold $R$ across the wall sides;
the union of copies is convex), with $|p|+|q|\le2\,\mathrm{diam}(R)+1$.
(e) *Sanity.* Directions $(1,N)$ with $\tau^N=1$ give nothing new: $xy^N\mapsto\sigma$,
rotations $\mapsto\tau^k\sigma\tau^{-k}$.

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/unfoldings.md:189-209 (relabel map).
