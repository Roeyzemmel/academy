---
id: CRIT-1
aliases: [R Prop 3.1]
title: "(Q1) fails for every rectangle unfolding except the unit square (parity)"
summary: "For the p×q rectangle (PA-7) the unfolding is a torus with Λ=2pZ⊕2qZ; a class lies in C iff it has a primitive vector, so parity makes (Q1) fail for all (p,q)≠(1,1)."
kind: prop
status: Proved
level: PA-7
topics: [q1, obstructions]
examples: [EX-2x1]
depends_on: []
source: notes/03-q2/q1-failure.md:17-31
added: 2026-09-24
---

## Statement

> **Proposition 3.1 (Proved).** Let $R_{p,q} = [0,p]\times[0,q]$, $p,q \in \mathbb{Z}_{>0}$,
> tiled by unit squares. Its unfolding is the torus $\mathbb{R}^2/\Lambda$,
> $\Lambda = 2p\mathbb{Z}\oplus 2q\mathbb{Z}$, an origami on $n = 4pq$ squares with
> $\Omega = \mathbb{Z}^2/\Lambda$, $G = \Omega$ regular, $\sigma = (1,0)$, $\tau = (0,1)$.
> A class $d+\Lambda$ lies in $C$ iff it contains a primitive vector, and it
> contains none iff some prime $\ell \mid \gcd(2p,2q)$ divides both $d_1$ and $d_2$.
> Taking $\ell = 2$ and noting $\Lambda \subseteq 2\mathbb{Z}^2$:
> **(Q1) fails for the unfolding of $R_{p,q}$ for every $(p,q)\ne(1,1)$.**

These satisfy (A6), and are exactly its $k=0$ members (Corollary 1.10). Smallest
case: the $2\times1$ rectangle, $G \cong \mathbb{Z}/4\times\mathbb{Z}/2$ on 8
squares; the class $(2,0)$ is unreachable since every representative $(2+4a,2b)$
is even in both coordinates. **This is precisely the
$\mathbb{Z}/2\times\mathbb{Z}/4$ counterexample of S1 §3.2 — it was a rectangle
unfolding all along.**

## History

- 2026-09-24: migrated verbatim from notes/03-q2/q1-failure.md:17-31 (relabel map).
