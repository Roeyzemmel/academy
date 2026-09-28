---
id: OBS-17
aliases: [W9a]
title: "Squares criterion: a sufficient condition for (Q2) failure"
summary: "Draft, under GA-EP: if an orbital inside {ι=0} has a pair whose coset holds no square of a C^pow element, (Q2) fails; normal form: some 1 ≠ E ∈ G₀ is not a square in G."
kind: draft
status: Not settled
status_note: "draft; not yet through /verify-claim"
level: GA-EP
topics: [drafts, obstructions, normal-case]
examples: [EX-M12-15711]
depends_on: [CRIT-11, CRIT-9, OBS-19]
source: "writing/a4-candidate-generation.md §1.1 (W9a)"
added: 2026-09-24
---

## Statement

<!-- copied from writing/a4-candidate-generation.md §1.1, item W9a; the draft stays the working copy -->

> **W9a (sufficient condition for (Q2) failure; argument given; Not settled).** Assume (EP).
> If $u\in W$ has direction $(q,p)$ and $u^k i=j$ with $\iota(i,j)=0$, then $k(q,p)\equiv0
> \pmod 2$. Since $(q,p)$ is primitive, $k$ is even, so $j=(u^{k/2})^2 i$ (R2 Prop. 4.1(d)).
> Hence:
> - **Non-normal form.** If some $G$-orbital inside $\{\iota=0\}\setminus\mathrm{diag}$ contains
>   a pair $(i,j)$ such that the coset $\{g:gi=j\}$ contains no square $c^2$ with
>   $c\in C^{\mathrm{pow}}$ (a fortiori, no square of any element of $G$), then (Q2) fails.
> - **Normal form** (R Prop. 5.7). If some $1\ne E\in G_0$ is not a square in $G$ (for
>   example, $E\in G_0$ generating a maximal cyclic subgroup), then (Q2) fails.
>
> *Rests on:* R2 Prop. 4.1(d) (Proved), R Prop. 5.7 (Proved), and for the normal form the
> elementary equivalence "(Q2) ⇔ every maximal cyclic subgroup of $G$ is conjugate to
> $\langle u\rangle$ for some $u\in W$", which follows from Prop. 5.7 by maximality.
> The N8 member 2 certificate is the normal form with $E=E_1$.

A general "quotient" version is also true and elementary. Let $f:G\to Q$ be a homomorphism
with $G_i\le\ker f$, so that $\Omega\to Q$ is a normal quotient origami $M'$. If (Q2) fails on
$M'$, it fails on $M$. This is the lifting lemma W5 in §2.3.

## Proof

The argument is in [writing/a4-candidate-generation.md](../writing/a4-candidate-generation.md) §1.1, item W9a, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/a4-candidate-generation.md §1.1 (W9a) during the relabelling.
