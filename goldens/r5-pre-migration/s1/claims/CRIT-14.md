---
id: CRIT-14
aliases: [R2 Prop 4.4]
title: "Centralising elements: gr(T) is a single orbital; when it lies in R^pow"
summary: "For 1≠T centralising G, gr(T) is one orbital of size n; it lies in R^pow iff some ⟨u⟩-orbit is T-invariant (odd orbit count suffices for involutions); and GA-2T fails if n>|A|."
kind: prop
status: Proved
topics: [orbitals, q2-criteria]
depends_on: [CRIT-11]
source: notes/03-q2/orbitals.md:51-64
added: 2026-09-24
---

## Statement

**Proposition 4.4.** Let $1\ne T\in C_{S_n}(G)$. (a) $\mathrm{gr}(T):=\{(i,Ti)\}$ is a single
$G$-orbital of size $n$, inside $D_{\delta}$, $\delta=d(i,Ti)$ constant. (b)
$\mathrm{gr}(T)\subseteq R^{\mathrm{pow}}$ iff some $u\in W$ has a $\langle u\rangle$-orbit that is
$T$-invariant, iff $u^ki=Ti$ for some $u,k,i$; the direction of that $u$ then realises the
whole orbital, and under (EP) it must satisfy $(q,p)\equiv\iota(T)\pmod2$. (c) *(Counting
criterion.)* If $T$ is an involution and $u$ (of direction $\equiv\iota(T)$ under (EP)) has an
odd number of $\langle u\rangle$-orbits, one of them is $T$-invariant. (d) If $C_{S_n}(G)\ne1$
and $n>|A|$ then (2T) fails ($|\mathrm{gr}(T)|=n<|D_\delta|$).

## Proof

*Proof.* $T$ commutes with $G$ and with every $u$. (a) $G$ acts on $\mathrm{gr}(T)$ through the
first coordinate; $d(hi,Thi)=d(i,Ti)$. (b) $u^ki=Ti$ ⇒ $T\langle u\rangle i=\langle u\rangle i$;
conversely a $T$-invariant orbit contains $Ti$; conjugates: $hu^kh^{-1}i=Ti$ iff $u^k$ sends
$h^{-1}i$ to $Th^{-1}i$. (c) $T$ permutes the $\langle u\rangle$-orbits as an involution; an
involution on an odd set has a fixed point. (d) clear. $\square$

## History

- 2026-09-24: migrated verbatim from notes/03-q2/orbitals.md:51-64 (relabel map).
