---
id: GEO-20
aliases: [R2 Thm 2.3]
title: "Garage unfoldings are twisted diagonals (PA-4 ⇒ RD4, …, PA-7 ⇒ RD7)"
summary: "A garage with hol(P) ⊆ 2Z² gives a reflection datum whose twisted diagonal is its unfolding, with corner angles read from dihedral orbits; converses fail only by immersion/embedding"
kind: thm
status: Proved
level: PA-4
topics: [unfoldings, structure]
depends_on: [DEF-2, GEO-8, GEO-9]
source: notes/01-geometry/unfoldings.md:168-183
added: 2026-09-24
---

## Statement

**Theorem 2.3.** (a) If $\mathrm{hol}(P)\subseteq2\mathbb Z^2$ then $(S;X_L,X_R,Y_B,Y_T)$ is a
reflection datum and $(s,g)\mapsto(s,\,p(s)+c_g)$, $c_g=\big(\tfrac{1-\alpha}2,\tfrac{1-\beta}2\big)$,
is an isomorphism of R's $(\sigma,\tau)$ with the twisted diagonal; so **(A4) ⇒ (RD)**.
(b) The $\langle X,Y\rangle$-orbit of $s$ is the set of squares around one vertex of $P$ over the
corner $XY$ of $Q$: a path of length $\ell$ is a boundary corner of angle $\ell\pi/2$, a
cycle of length $2\ell$ an interior vertex of angle $\ell\pi$. Hence **(A4) ⇒ (RD4)**,
**(A5) ⇒ (RD5)**, **(A6) ⇒ (RD6)**, **(A7) ⇒ (RD7)** (a rectangle has only corners of angle
$\pi/2$, $\pi$ and interior vertices).
(c) The converses fail only by conditions $G$ cannot see: $\mathrm{hol}(P)=0$ (immersion)
and injectivity (embedding). Example: the closed staircase
$s_1\overset r\to s_2\overset u\to s_3\to\cdots\to s_{2k}\to s_1$ satisfies (RD6) for $k$ even
with $\mathrm{hol}=\langle(k,k)\rangle$.

## Proof

*Proof.* (a) $\sigma(s,g)=(r^{\alpha}s,g)$ if defined, else $(s,\rho_1g)$; with $e=p(s)+c_g$,
$\alpha=(-1)^{e_1+p_1(s)}$, so $r^\alpha=X_R$ if $e_1=0$, $X_L$ if $e_1=1$, and $e$ changes by
$(1,0)$ in both cases. (b) R Prop. 1.6. $\square$

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/unfoldings.md:168-183 (relabel map).
