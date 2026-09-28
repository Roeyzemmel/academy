---
id: CRIT-18
aliases: [R2 Lemma 4.8]
title: "Block reduction: (Q2) lifts from a block quotient under fibre conditions"
summary: "For a G-invariant block system: if block-pair stabilisers are transitive on B×B′, (Q2) holds on the quotient origami, and each in-block orbital is met, then (Q2) holds for G."
kind: lemma
status: Proved
topics: [q2-criteria, quotients, orbitals]
depends_on: []
source: notes/03-q2/orbitals.md:140-157
added: 2026-09-24
---

## Statement

**Lemma 4.8.** Let $\mathfrak B$ be a $G$-invariant block system, $\bar G$ the induced group
on $\Omega/\mathfrak B$ (the origami $\bar M$ covered by $M$), $\bar u$ the image of $u\in W$.
Suppose: (i) for any two blocks $B\ne B'$ in a common $\bar G$-orbital, the ordered-pair
stabiliser $G_{B,B'}$ is transitive on $B\times B'$; (ii) (Q2) holds for $\bar G$; (iii) for
each block $B$ and each orbital of the setwise stabiliser $G_B$ on $B^{(2)}$ there is $u^m$
with $\bar u^m(B)=B$ meeting it. Then (Q2) holds for $G$. If (i) fails only for pairs
$(B,B')$ on which $G_{B,B'}$ has exactly two orbits, the graph of a bijection $t$ and its
complement, then (i)–(iii) still give (Q2) provided each such graph is met.

## Proof

*Proof.* Orbitals of $G$ on pairs in different blocks are, under (i), in bijection with
$\bar G$-orbitals, met by (ii) (lift $\bar u^m\bar B=\bar B'$ to $u^m$; the pair $(i,u^mi)$ lies in
$B\times B'$); pairs in one block are handled by (iii). $\square$

Theorem 4.5 is the case $\mathfrak B=\{B_e\}$: (i) holds except on linked pairs, where the
graphs are the $\mathrm{gr}(T)$; (ii) is (Q2) for the $2\times2$ torus; (iii) is the
2‑transitivity of $H$ met by $\sigma^2$ or $\tau^2$. For a general block system (S1 §3.5's
induction) the lemma isolates the two things to prove: (i) "fibre 2‑transitivity" and
(iii) "fibre (Q2)".

## History

- 2026-09-24: migrated verbatim from notes/03-q2/orbitals.md:140-157 (relabel map).
