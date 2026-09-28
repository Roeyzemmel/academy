---
id: GEO-26
aliases: [R Prop 4.1]
title: "Dictionary: trajectories between fibre points ↔ powers of Christoffel rotations"
summary: "There is a trajectory from x_i to x_j in the fibre over z_0 avoiding the marked points iff π(w_r)^m(i) = j for a primitive (q,p), m ≥ 1, and the rotation w_r set by z_0"
kind: prop
status: Proved
topics: [dictionary]
depends_on: []
source: notes/01-geometry/dictionary.md:23-34
added: 2026-09-24
---

## Statement

> **Proposition 4.1 (dictionary; Proved).** For $x_i,x_j \in F_{z_0}$ there is a
> straight-line trajectory on $M$ from $x_i$ to $x_j$ avoiding $\pi^{-1}(0)$ iff
> there are a primitive $(q,p)$ and $m\ge1$ with $\pi(w_r)^m(i) = j$, where $w_r$
> is the cyclic rotation of $w_{p,q}$ determined by the intercept of the line
> through $z_0$ of direction $(q,p)$.
>
## Proof

> *Proof.* A trajectory from $x_i$ to $x_j$ projects to a straight path from $z_0$
> to $z_0$, so its holonomy is $v \in \mathbb{Z}^2$; write $v = m(q,p)$ with
> $(q,p)$ primitive, $m = \gcd(v)$. The path is the primitive closed geodesic
> through $z_0$ of direction $(q,p)$ traversed $m$ times; its class in $\pi_1$ is
> its cutting sequence, a cyclic rotation of $w_{p,q}$ fixed by the intercept.
> Lifting from $x_i$ lands in square $\pi(w_r)^m(i)$. The converse reverses this. $\square$

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/dictionary.md:23-34 (relabel map).
