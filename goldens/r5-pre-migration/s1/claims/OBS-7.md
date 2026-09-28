---
id: OBS-7
aliases: [M1]
title: "Quotient illumination: definition and lifting lemma"
summary: "Draft: for finite H ≤ Aff(M), x̄ illuminates ȳ in M/H iff x illuminates some hy in M; non-illumination in the quotient lifts, the converse needs every hy unlit; pairs identified by H collapse."
kind: draft
status: Not settled
status_note: "draft; not yet through /verify-claim"
topics: [drafts, quotients]
depends_on: []
source: "writing/n8-quotient-mechanism.md §1 (M1)"
added: 2026-09-24
---

## Statement

<!-- copied from writing/n8-quotient-mechanism.md §1, item M1; the draft stays the working copy -->

> **M1 (definition and elementary lemma; Not settled).** Let $H\le\mathrm{Aff}_{D_4}(M)$ be
> finite, $Q=M/H$, and let $q:M\to Q$ be the projection. Call $q(S)$ a *$Q$-trajectory* when $S$ is a
> straight segment of $M$ whose interior avoids $\Sigma^*$. Say that $\bar x$ *illuminates* $\bar y$
> in $Q$ if some $Q$-trajectory joins them. Then:
> 1. $\bar x$ illuminates $\bar y$ in $Q$ iff $x$ illuminates $hy$ in $M$ for some $h\in H$.
> 2. **Lifting direction (always valid).** If $\bar x$ does not illuminate $\bar y$ in $Q$, then
>    $x$ illuminates no point of $Hy$, and in particular not $y$.
> 3. **Converse (needs care).** Non-illumination of $(x,y)$ in $M$ descends to $Q$ iff $x$ also
>    fails to illuminate every other $hy$, $h\in H\setminus\{1\}$.
> 4. If $T\in H$ then $q(x)=q(Tx)$. The pair collapses, and nothing about illumination between
>    two distinct points of $Q$ can express it.

## Proof

The argument is in [writing/n8-quotient-mechanism.md](../writing/n8-quotient-mechanism.md) §1, item M1, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/n8-quotient-mechanism.md §1 (M1) during the relabelling.
