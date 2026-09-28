---
id: OBS-20
aliases: [W7]
title: "Deck translations of garage covers and the covering criterion at PA-4"
summary: "Draft: translation automorphisms of a PA-4 garage exist only when PA-SC fails; for a regular garage cover with group D, (CT′)(i) holds for all deck elements iff folded-core monodromies cover D."
kind: draft
status: Not settled
status_note: "draft; not yet through /verify-claim"
level: PA-4
topics: [drafts, a4-realisation, orbitals]
depends_on: [STR-4]
source: "writing/a4-candidate-generation.md §2.4 (W7)"
added: 2026-09-24
---

## Statement

<!-- copied from writing/a4-candidate-generation.md §2.4, item W7; the draft stays the working copy -->

> **W7 (deck translations; argument sketch; Not settled).**
> - Let $\theta$ be a datum automorphism with $\lambda(\theta)=1$. Then $h\circ\theta=h+v$ with
>   $v\in\mathbb Z^2$. Because $\theta$ has finite order, $v=0$. So $\theta$ permutes sheets
>   over each cell.
> - Such a $\theta$ fixing a cell fixes its neighbours, hence everything. It also fixes no
>   boundary vertex, since a path link has no nontrivial translation automorphism. So
>   $\langle\theta\rangle$ acts freely and $P\to P/\langle\theta\rangle$ is a genuine covering.
>   A free finite action on a disc is impossible, so **such $T$ exist only when (SC) fails.**
> - For a regular garage cover $P\to P'$ with group $D$, each $d\in D$ gives
>   $T_d(s,g)=(ds,g)\in Z$ (R2 Prop. 3.3(b)) with $\iota=0$ and $d(i,T_di)=0\in A$.
> - The $u$-cycle of $i$ in $M_P$ lies over the $\bar u$-cycle of $\bar i$ in $M_{P'}$, of
>   length $L$. We have $u^L i=T_{\gamma}i$, where $\gamma$ is the $D$-monodromy of the loop
>   in $P'$ obtained by folding that cylinder level. So the cycle is $T_d$-invariant if and
>   only if $d\in\langle\gamma\rangle$, up to the conjugacy coming from the choice of base
>   point.
>
> **Hence (CT′)(i) for all deck elements holds if and only if the cyclic subgroups generated
> by the $D$-monodromies of folded cylinder cores of $M_{P'}$ cover $D$ up to conjugacy.**
> This is the garage-level analogue of R Prop. 5.7, with two substitutions:
> - $F_2$ becomes $\pi_1(P')$, a free group of rank $1-\chi(P')$;
> - Christoffel (primitive) classes become the classes of periodic billiard loops in $P'$.
>
> N8's member 2 was a finite quotient of $F_2$ that the primitive classes fail to cover. The
> (A4) analogue is a finite quotient of $\pi_1(P')$ that the billiard classes fail to cover.

## Proof

The argument is in [writing/a4-candidate-generation.md](../writing/a4-candidate-generation.md) §2.4, item W7, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/a4-candidate-generation.md §2.4 (W7) during the relabelling.
