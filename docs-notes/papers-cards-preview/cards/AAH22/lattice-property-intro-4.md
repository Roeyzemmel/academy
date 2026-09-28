---
key: AAH22
pinpoint: Lattice property, intro + §4
version: arXiv v2 (20 Dec 2019)
read_from: extraction
verdict: match
used_by: [paper:ex:platonic-boundary]
checked: 2026-09-19
by: author@bi/source-checker
migrated: Drafts/sources.md (author@bi)
---

## Statement

_To fill (migrated): the statement relied on._

## Hypotheses

_To fill (migrated): the hypotheses, one per bullet._

## Quote

> the unfolding of every Platonic solid is a lattice surface (that is, a surface whose stabilizer in SL(2,R), known as the Veech group, is a lattice) (see Proposition 4.4).

## Ledger text

- **Lattice property, intro + §4** - the paper states the "first key observation" as
  verbatim: "the unfolding of every Platonic solid is a lattice surface (that is, a
  surface whose stabilizer in SL(2,R), known as the Veech group, is a lattice) (see
  Proposition 4.4)." There is no single numbered theorem asserting this for all five
  solids; the mechanism is **Proposition 4.4** ("If S is a translation surface with a
  regular n-gon decomposition P, then there is a translation covering φ: S → Πₙ ...")
  together with **Corollary 2.11** ("Let φ: S → P is a translation covering, where P is
  a primitive lattice surface with genus greater than 1 ... Then S is a lattice
  surface"), applied with $P = \Pi_n$ (Veech's regular n-gon / double n-gon table, a
  known lattice surface) for the dodecahedron (n=5, via **Theorem 4.5**, degree-60 cover
  of the double pentagon) and the elementary square-tiled/arithmetic argument of
  **§7** ("all of these Platonic solids have either square faces, in which case the
  unfolding is square-tiled and covers Π₄, or ... triangle faces ... cover the double
  triangle Π₃") for the tetrahedron, cube, octahedron and icosahedron. Verdict: **match**
  with `ex:platonic-boundary`'s "who show in particular that all five unfoldings are
  lattice surfaces" — supported, though attributed in the paper to a combination of
  results rather than one theorem; no single pinpoint captures the claim. How read:
  extraction (v2 PDF). 2026-09-19.

## Notes

Migrated by ledger_split.py; the ledger's own text is kept verbatim above.
