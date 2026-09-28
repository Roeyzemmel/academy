---
id: GEO-25
aliases: [W6]
title: "The cyclic-cover family M_N(a) at level PA-4"
summary: "Draft: GEO-12 and GEO-24 exclude from PA-4 every M_N(a) with N ≢ 2 mod 4 (whenever some a_j is a unit), including all N = 12 members"
kind: draft
status: Not settled
status_note: "draft; not yet through /verify-claim"
topics: [drafts, a4-realisation, pillowcase-covers]
examples: [EX-M12-1335, EX-M12-15711]
depends_on: [GEO-12, GEO-24]
source: "writing/a4-candidate-generation.md §2.2 (W6)"
added: 2026-09-24
---

## Statement

<!-- copied from writing/a4-candidate-generation.md §2.2, item W6; the draft stays the working copy -->

> **W6 (the cyclic-cover family at (A4); argument given; Not settled).** In $M_N(a)$, with
> $n=2N$, every vertex lies over a pillowcase corner. The vertices over corner $j$ have
> commutator cycle length $N/(2\gcd(N,a_j))$. Two consequences:
> - W1 needs fixed points, hence some $a_j\equiv N/2\pmod N$. Since $a_j$ is odd, this forces
>   $N\equiv2\pmod4$, and the fixed-point count $\sum_{a_j\equiv N/2}N/2$ must be at least 4.
> - W3 excludes $N\equiv0\pmod4$ whenever some $a_j$ is a unit: a cycle of even length
>   $N/2=m$ would fill a whole block.
>
> **So every $N=12$ member, including all twelve FALSE ones, fails W1.** The part of the
> family compatible with (A4) lies in $N\equiv2\pmod4$. There the cleared runs E2a ($N\le10$)
> and E2b ($N\in\{14,18\}$ within $\{14,16,18\}$) report no counterexample, over their stated
> classes. Passing W1 and W3 is still only necessary.

## Proof

The argument is in [writing/a4-candidate-generation.md](../writing/a4-candidate-generation.md) §2.2, item W6, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/a4-candidate-generation.md §2.2 (W6) during the relabelling.
