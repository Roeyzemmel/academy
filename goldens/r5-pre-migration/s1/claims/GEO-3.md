---
id: GEO-3
aliases: [R Lemma 1.2]
title: "Christoffel reversal: Christoffel values are strongly real under OA-1"
summary: "Under OA-1 every Christoffel value u satisfies u^{-1} = h^{-1}uh for some h in the coset Gι, using that a Christoffel word's reversal is a cyclic rotation of it"
kind: lemma
status: Proved modulo stated inputs
status_note: modulo BLRS fact
level: OA-1
topics: [symmetry]
depends_on: []
source: notes/01-geometry/symmetry-hypotheses.md:42-51
added: 2026-09-24
---

## Statement

> **Lemma 1.2 (Proved, modulo the standard fact that a lower Christoffel word and
> its reversal are cyclic rotations of one another — BLRS).** Under (A1), every
> $u \in W$ satisfies $u^{-1} = h^{-1}uh$ for some $h \in G\iota$: Christoffel
> values are strongly real in $G^+$, inverted by the non-identity coset.
>
## Proof

> *Proof.* $w^{\mathrm{low}} = xpy$ with $p$ a palindrome, so
> $\operatorname{rev}(w) = ypx = w^{\mathrm{up}}$, a cyclic rotation of
> $w^{\mathrm{low}}$; hence
> $\operatorname{rev}(w)(\sigma^{-1},\tau^{-1}) = g^{-1}w(\sigma^{-1},\tau^{-1})g$
> for the appropriate prefix value $g$, and $w(\sigma^{-1},\tau^{-1}) = \iota u \iota^{-1}$. $\square$

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/symmetry-hypotheses.md:42-51 (relabel map).
