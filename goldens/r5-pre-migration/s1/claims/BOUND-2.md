---
id: BOUND-2
aliases: [R2 Prop 7.1]
title: "K_min ≥ 2^r+1 for the 1×2^r rectangle; upper bounds on K"
summary: "Under PA-7 the 1×2^r rectangle needs K≥2^r+1, so no absolute K exists at any level; K≤p+q for a p×q rectangle, and K≤2 under GA-HA with trivial centraliser."
kind: prop
status: Proved
status_note: disproves BOUND-1
level: PA-7
topics: [bounds]
examples: [EX-2x1]
depends_on: [CRIT-15, GEO-21]
source: notes/03-q2/bounds-on-K.md:17-22
added: 2026-09-24
body_status_ack: "the body's 'Disproved' names what this item disproves (BOUND-1)"
---

## Statement

**Proposition 7.1 (Disproved: R Conj. 5.8).** Under (A7) with $\Lambda=2^{r+1}\mathbb Z\oplus2\mathbb Z$
(the $1\times2^r$ rectangle) the class $(2^r,1)$ forces $m$ odd, $p$ odd, $2^r\mid q$, so
$K\ge2^r+1$; no absolute $K$ exists even under (A7), hence under none of (A0)–(A6). Upper
bounds: $K\le p+q$ under (A7) for a $p\times q$ rectangle; $K\le2$ under (HA) with trivial centraliser (Thm 4.5(d)); $K\le2\,\mathrm{diam}(R)+1$
for same-rectangle pairs (Prop. 2.4(d)). The $K$ needed at a *fixed* base point is unbounded
even on one surface (§2.1 remark).

## History

- 2026-09-24: migrated verbatim from notes/03-q2/bounds-on-K.md:17-22 (relabel map).
