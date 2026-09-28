---
id: GEO-18
aliases: [R Rmk 1.11]
title: "Gauss–Bonnet, the EW and D_4 at level PA-4, and the realisation question"
summary: "EW and D_4 pass the PA-4 commutator test but fail PA-5w and PA-6 tests; a PA-4 realisation would be a genus-1 garage with two 2π corners; which (σ,τ) are unfoldings is open"
kind: remark
topics: [a4-realisation, unfoldings]
examples: [EX-EW, EX-D4]
depends_on: [GEO-10, GEO-14, GEO-16]
source: notes/01-geometry/unfoldings.md:130-152
added: 2026-09-24
---

## Statement

> **Remark 1.11 (Gauss–Bonnet, and the Eierlegende Wollmilchsau).** For a flat
> surface with geodesic boundary,
> $\sum_{\text{corners}}(\pi-\theta_i) = 2\pi\chi(P)$ — a rectangle gives
> $4\cdot\tfrac\pi2 = 2\pi\cdot1$ ✓, an L-shape $5\cdot\tfrac\pi2 - \tfrac\pi2 = 2\pi$ ✓.
>
> The EW and the $D_4$ origami have $[\sigma,\tau]$ of type $2^4$: they **pass**
> Corollary 1.7 (four is an even count) but **fail** Proposition 1.8, since cycles
> of even length force corners with $4\mid m$, and **fail** Proposition 1.9. So
> they can sit at level (A4) but no higher, and the chain separates them from both
> the (A5) class and the simple-table class. **Whether they satisfy (A4) at all is
> open, and the arithmetic is
> consistent**: $n=8$ forces $m=2$; four 2-cycles and no fixed points forbid convex
> corners, edge-interior lattice points and interior lattice points, so every
> lattice point of $P$ is a ramp corner of angle $2\pi$, and total angle
> $2\cdot2\pi = 4\pi$ forces exactly two of them. Gauss–Bonnet then gives
> $2(\pi-2\pi) = -2\pi$, i.e. $\chi(P) = -1$ — genus one with one boundary circle,
> matching $V-E+F = 2-5+2 = -1$ with three interior and two boundary edges. A
> compact orientable surface with non-empty boundary does immerse in $\mathbb{R}^2$,
> so nothing obstructs it on these grounds. Note that all corners of such a $P$ have
> $m=4$, so it would satisfy (A4) but **neither (A5) nor (SC)**. **The realisation problem — which
> $(\sigma,\tau)$ satisfying (A3) arise from some $P$ at each level — is Not
> settled**; Corollary 1.7 and Propositions 1.8–1.9 give conditions that are
> necessary, and in the case of 1.8 sufficient only relative to (A4).

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/unfoldings.md:130-152 (relabel map).
