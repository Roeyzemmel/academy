---
id: CRIT-15
aliases: [R2 Thm 4.5]
title: "GA-EP ∧ GA-HA ⇒ [(Q2) ⇔ GA-CT]; K≤2 if the centraliser is trivial"
summary: "Under GA-EP and GA-HA: Λ=2Z², the orbitals are the ι-classes split only by graphs of centralising involutions, (Q2) ⇔ GA-CT, and (Q2) holds with K≤2 if C(G)=1."
kind: thm
status: Proved
topics: [q2-criteria, orbitals]
depends_on: [STR-3, CRIT-11, CRIT-12, CRIT-13, CRIT-14]
source: notes/03-q2/orbitals.md:72-93
added: 2026-09-24
---

## Statement

**Theorem 4.5.** Assume (EP) and (HA). Then:
(a) $\Lambda=2\mathbb Z^2$ and $\{\iota=0\}$ is a single $G$-orbital.
(b) The block-shift map $C_{S_n}(G)\to(\mathbb Z/2)^2$ is injective; every nontrivial $T$ is an
involution with $\iota(T)\ne0$.
(c) For $\epsilon\ne0$, $\{\iota=\epsilon\}$ is a single $G$-orbital unless some $T\in C_{S_n}(G)$ has
$\iota(T)=\epsilon$, in which case it is exactly $\mathrm{gr}(T)$ and its complement.
(d) **(Q2) ⇔ (CT).** In particular, if $C_{S_n}(G)=1$ then (Q2) holds with $K\le2$ (Cor. 4.3(b)).

## Proof

*Proof.* (a) $H$ is 2‑transitive on $B_e$ (Lemma 3.2(a)); $d$ is constant on the resulting
orbital while onto $\{\delta\equiv0\}$; so that subgroup of $A$ is trivial. (b) A $T$ preserving
blocks commutes with $G_0|_{B_e}\supseteq A_m$, whose centraliser in $\mathrm{Sym}(B_e)$ is trivial
($m\ge4$); $T^2$ has shift 0. (c) Let $K\le\mathrm{Sym}(B_e)\times\mathrm{Sym}(B_{e'})$ be the image
of $G_0$, subdirect in $H\times H'$, $H\cong H'\in\{A_m,S_m\}$. Goursat: $N=K\cap(H\times1)$ is $1$
or $\supseteq A_m$. If $\supseteq A_m$, $K\supseteq A_m\times A_m$ is transitive on $B_e\times B_{e'}$.
If $N=1$, $K$ is the graph of an isomorphism $\theta:H\to H'$; if $\theta$ is induced by a
bijection $t:B_e\to B_{e'}$ the orbits are $\mathrm{gr}(t)$ and its complement (2‑transitivity);
if not ($m=6$, $\theta$ outer) the point stabiliser maps to a transitive subgroup ($A_5$,
$S_5\cong PGL_2(5)$ on 6 points) and $K$ is transitive. A $G_0$-equivariant $t$ extends to
$T\in C_{S_n}(G)$ by $T|_{B_{ge}}=gtg^{-1}$ (well defined as $G_0$ stabilises $B_e$ and $t$ is
equivariant; commutes with $G$), and $\mathrm{gr}(T)$ is the orbital by Prop. 4.4(a);
conversely each $T$ with $\iota(T)=\epsilon$ gives such a $t$. (d) Prop. 4.1, Thm 4.2, Prop. 4.4(b).
$\square$

## History

- 2026-09-24: migrated verbatim from notes/03-q2/orbitals.md:72-93 (relabel map).
