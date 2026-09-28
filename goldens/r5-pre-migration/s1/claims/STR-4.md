---
id: STR-4
aliases: [R2 Prop 3.3]
title: "Galois correspondence for reflection data; datum symmetries ↔ centraliser"
summary: "Intermediate Γ-sets ↔ foldings P → P′; a datum automorphism fixing the generators makes H^+ imprimitive, one swapping them gives a centralising T_θ with nonzero block shift"
kind: prop
status: Proved
topics: [structure, symmetry, quotients]
depends_on: [DEF-2]
source: notes/02-structure/reflection-data.md:132-146
added: 2026-09-24
---

## Statement

**Proposition 3.3.** (a) $H^+$ is imprimitive on $S$ iff there is a proper intermediate
transitive $\Gamma$-set $S\to S'\to\{\ast\}$; $S'$ is a reflection datum (possibly with
orbifold points and long corners) and geometrically $P$ *folds* onto $P'$.
(b) Let $\theta\in\mathrm{Sym}(S)$ be a datum automorphism with $\theta X_\bullet\theta^{-1}=X_{\lambda(\bullet)}$,
$\lambda\in K_4$ permuting $\{L,R\}$, $\{B,T\}$. If $\lambda=1$, $\theta$ centralises $H^+$ and
$H^+$ is imprimitive (blocks = $\langle\theta\rangle$-orbits; geometrically $P\to P/\theta$: reflection
in a grid line, half-turn about a lattice point). If $\lambda\ne1$, then
$T_\theta(s,e):=(\theta s,\,e+c_\lambda)$ lies in $C_{S_n}(G)$ with block shift
$\iota(T_\theta)=c_\lambda\ne0$ ($c_\lambda=(1,0)$ for $L\leftrightarrow R$, $(0,1)$ for $B\leftrightarrow T$,
$(1,1)$ for both; geometrically reflection in a mid-line, half-turn about a half-lattice point).

## Proof

*Proof.* (a) blocks of a transitive $\Gamma$-set ↔ subgroups between $\Gamma_s$ and $\Gamma$.
(b) $\lambda=1$: $\theta$ commutes with the generators. $\lambda\ne1$:
$T\sigma(s,e)=(\theta X_{e_1}s,\ e+c_\lambda+(1,0))=(X_{\lambda(e_1)}\theta s,\dots)=\sigma T(s,e)$ since
$\lambda$ swaps $L\leftrightarrow R$ exactly when $c_{\lambda,1}=1$. $\square$

## History

- 2026-09-24: migrated verbatim from notes/02-structure/reflection-data.md:132-146 (relabel map).
