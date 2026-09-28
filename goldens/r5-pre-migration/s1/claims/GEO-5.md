---
id: GEO-5
aliases: [R Lemma 2.1]
title: "Symmetry lemma: under OA-3 the Christoffel values are Φ-invariant"
summary: "Under OA-3, W is Φ-conjugation invariant, so C is a union of G^+-classes; (Q1)/(Q2) need only the non-diagonal G^+-orbitals, and the positive quadrant suffices"
kind: lemma
status: Proved
level: OA-3
topics: [symmetry, orbitals]
depends_on: []
source: notes/01-geometry/symmetry-hypotheses.md:92-108
added: 2026-09-24
---

## Statement

> **Lemma 2.1 (symmetry lemma; Proved).** Under (A3), $W$ is $\Phi$-conjugation
> invariant:
> $\phi(a,b)\,w(\sigma^{a'},\tau^{b'})\,\phi(a,b)^{-1} = w(\sigma^{aa'},\tau^{bb'}) \in W$.
> Hence $C = \bigcup_{u\in W} u^{G^+}$ and $R = \{(i,c(i)) : c \in C\}$ is a union
> of $G^+$-orbitals.

Three consequences, all **Proved**:

1. **Sharpened criterion.** $C$ (resp. $C^{\mathrm{pow}}$) is transitive off the
   diagonal iff the Christoffel digraph meets every non-diagonal orbital **of
   $G^+$**. The number of conditions drops from $\operatorname{rank}(G)-1$ to
   $\operatorname{rank}(G^+)-1$ (Wielandt rank; see S1 §2.3 for the terminology trap).
2. **The modelling choice of S1 §1.1 is settled.** Under (A3),
   $C = \bigcup_{w \text{ lower Christoffel}} \big(w(\sigma,\tau)\big)^{G^+}$: the
   positive quadrant suffices, at the price of conjugating by $G^+$ rather than $G$.
3. **Regular case.** The count drops from $|G|-1$ to the number of orbits of
   $A = \langle\alpha_\mu,\alpha_\nu\rangle \le \operatorname{Aut}(G)$ on $G\setminus\{1\}$.

## History

- 2026-09-24: migrated verbatim from notes/01-geometry/symmetry-hypotheses.md:92-108 (relabel map).
