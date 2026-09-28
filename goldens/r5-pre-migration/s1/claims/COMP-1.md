---
id: COMP-1
aliases: [N1]
title: "Christoffel words represent each primitive conjugacy class of F_2 once"
summary: "Lower Christoffel words in the four sign quadrants represent each primitive class of F_2 once (cited); still open: (Q2) is GL(2,Z)-invariant, hence constant on a Teichmüller curve."
kind: prop
status: Not settled
topics: [computation, dictionary]
depends_on: []
source: notes/03-q2/families-hunt.md:46-75
added: 2026-09-24
---

## Statement

### N1 (Not settled) — Christoffel words and primitive conjugacy classes of $F_2$

**N1.** The lower Christoffel words, evaluated in all four sign quadrants at
$(\sigma^{\pm1},\tau^{\pm1})$, represent every conjugacy class of primitive elements of the
free group $F_2$ exactly once — the classical correspondence between primitive conjugacy
classes and primitive vectors of $\mathbb Z^2$. Consequently the set $C$ of
`computation/spec.md` §1 equals the $G$-conjugation closure of the values of all primitive
elements, and (Q2) is invariant under the $\mathrm{GL}(2,\mathbb Z)$-action on origamis,
hence constant on a Teichmüller curve.

*What it buys.* The search may take one representative per $\mathrm{SL}(2,\mathbb Z)$-orbit,
and the value set may be enumerated a second, independent way by a labelled Nielsen-move
breadth-first search on pairs $(g_1,g_2)$, which must agree with the spec's Christoffel-tree
enumeration.

*Citation for the group-theoretic half.* Kassel–Reutenauer, arXiv:math/0507219, Cor. 3.3(b)
(v1): "The primitive elements of $F_2$ are exactly the conjugates of Christoffel words." A
weaker form (a bijection between conjugacy classes of primitives up to inverse and the
primitive words $E_{p/q}$) is in Gilman–Keen, arXiv:0802.2731. Recorded in
`literature/families.md`, Block E. This settles the correspondence between Christoffel words
and primitive conjugacy classes of $F_2$ that the first sentence of N1 asserts.

*What would settle it, narrowed.* The group-theoretic half is now cited; what remains is
**only** that (Q2) is invariant under the $\mathrm{GL}(2,\mathbb Z)$-action on origamis and
hence constant on a Teichmüller curve — for which the Block E search found nothing — plus the
check that the orbit-invariance argument survives the marked-point convention (every square
corner is marked).

*Related, already in this database.* R Lemma 1.2 and R Prop. 4.1–4.3 touch the
Christoffel/rotation dictionary and should be cited alongside.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:46-75 (relabel map).
