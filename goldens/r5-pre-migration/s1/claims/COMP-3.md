---
id: COMP-3
aliases: [N4]
title: "Abelian pillowcase covers by transcribing the CyclicCover recipe"
summary: "Replacing Z/M by a finite abelian A and parity by a character χ with χ(a_j)=1 should give the abelian square-tiled surfaces; unproved, and the match with Wright's normalisation is open."
kind: prop
status: Not settled
topics: [computation, pillowcase-covers]
depends_on: []
source: notes/03-q2/families-hunt.md:111-129
added: 2026-09-24
---

## Statement

### N4 (Not settled) — abelian square-tiled covers by transcribing the cyclic recipe

**N4.** `surface_dynamics`' `origamis.CyclicCover` builds $r$ and $u$ on sheets indexed by
$\mathbb Z/M$, two squares $2i$ and $2i+1$ per sheet, by the shifts $i\mapsto i\pm a_j$, with
the sign determined by a parity split of the sheets. Replacing $\mathbb Z/M$ by a finite
abelian group $A$ and the parity by a character $\chi:A\to\mathbb Z/2$ with $\chi(a_j)=1$ for
every $j$ yields the abelian square-tiled surfaces (four elements $a_0,\dots,a_3$ generating
$A$ and summing to zero).

*What would settle it.* A proof that the transcription gives a translation surface covering
the pillowcase with deck group $A$, plus the two validation checks the pipeline will run:
cyclic $A$ must reproduce `CyclicCover` tuple for tuple, and the independent
`PillowcaseCover(...).orientation_cover()` route must give isomorphic components. **An
explicit added obligation**: Wright (arXiv:1203.2683) gives the translation-surface condition
for an abelian square-tiled surface in a *different normalisation* of the character than the
one N4 writes — his datum is a $4\times m$ matrix $A$ over $\mathbb Z/N$ and his condition is
that $(N/2,N/2,N/2,N/2)$ lies in the row span of $A$, against N4's $\chi:A\to\mathbb Z/2$
with $\chi(a_j)=1$ for each generator. Whether the two parametrisations biject is not settled
by that source and is not settled here; recorded in `literature/families.md`, Block D.

## History

- 2026-09-24: migrated verbatim from notes/03-q2/families-hunt.md:111-129 (relabel map).
