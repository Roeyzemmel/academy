---
id: GEO-12
aliases: [N10, W1]
title: "Every PA-4 garage has at least four convex corners"
summary: "A PA-4 garage has ≥ 4 convex corners of four distinct orientations (extremal lattice points), so [σ,τ] has at least four fixed points; uses only hol(P) = 0"
kind: prop
status: Proved
level: PA-4
topics: [unfoldings, a4-realisation]
depends_on: [GEO-9]
source: notes/03-q2/families-hunt.md:356-380
added: 2026-09-24
---

## Statement

## [2026-09-23] N10 (Proved) — every (A4) garage has at least four convex corners

**N10.** Every (A4) garage $P$ (a rectangle-tiled parking garage, immersion
$\mathrm{hol}(P)=0$, no interior cone points) has at least four convex corners, of four
distinct orientations. Consequently $[\sigma,\tau]$ has at least four fixed points, by
R Prop. 1.6.

*Argument.* Let $y_0$ be the minimal height of $h(P)$ and $x_0$ the minimal abscissa at that
height, so $p=(x_0,y_0)$ is a lattice point; let $v$ be a vertex of $P$ over $p$. Of the four
cells meeting $p$, only the NE cell can receive a square corner at $v$ (the SW and SE cells
lie below $y_0$; the NW cell has points left of $x_0$ at height $y_0$). Since $h$ is a local
homeomorphism on edge interiors, consecutive square corners at $v$ lie on opposite sides of a
shared edge's image and so cannot both map to the NE cell; hence $v$ has exactly one square
corner and angle $\pi/2$ — a single square cannot close a link on itself, since translation
gluings never pair a left edge with a bottom edge. The same argument at the other three
extremal lattice points gives four convex corners of four distinct orientations.

*What is actually used.* $\mathrm{hol}(P)=0$ (the immersion condition) alone; **not** the
absence of interior cone points as such — the argument only needs the local-homeomorphism
property on edge interiors and the extremal-point construction, which is a statement about
(A4), not about (RD4).

*Cleared by.* Two `claim-verifier` runs on the primary model (Fable 5.1), sequential, both
Proved/CONFIRMED on 2026-09-23; see `computation/verdicts.md`, entry "W1 and W4
(writing/a4-candidate-generation.md)". Source: `writing/a4-candidate-generation.md`, item W1.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:356-380 (relabel map).
