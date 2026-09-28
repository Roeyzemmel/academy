---
key: AAH22
pinpoint: Definition of the unfolding, §2.2
version: arXiv v2 (20 Dec 2019)
read_from: extraction
verdict: match
used_by: [paper:defn:unfolding, paper:ex:platonic-boundary]
checked: 2026-09-19
by: author@bi/source-checker
migrated: Drafts/sources.md (author@bi)
---

## Statement

_To fill (migrated): the statement relied on._

## Hypotheses

_To fill (migrated): the hypotheses, one per bullet._

## Quote

> The unfolding of a cone surface S is the smallest cover of S branched over Σ for which the parallel transport homomorphism PT has trivial image. This unfolding S̃ is the completion of the cover of S associated to ker PT.

## Ledger text

- **Definition of the unfolding, §2.2** - verbatim (pdftotext of arXiv v2 PDF): "The
  unfolding of a cone surface S is the smallest cover of S branched over Σ for which the
  parallel transport homomorphism PT has trivial image. This unfolding S̃ is the
  completion of the cover of S associated to ker PT." And **Proposition 2.3**: "The
  covering S̃ → S is regular with deck group isomorphic to PT(H₁(S;Z)). In particular,
  the cover is finite if and only if PT(H₁(S;Z)) = Z/kZ for some integer k ≥ 1." Verdict:
  **match** — this is exactly the $K_S$-cover of `defn:unfolding`: PT is the linear
  holonomy $\mathrm{lin}\circ\rho$, its image is the structure group $K_S$, and the
  unfolding is the completion of the cover associated to its kernel, deck group
  isomorphic to $K_S$ via the same construction. Resolves the open item in the
  `\Claude` note after `ex:platonic-boundary`: their unfolding of a Platonic-solid
  boundary surface is the $K_S$-cover, not a further cover. How read: extraction (v2
  PDF via arxiv.org/pdf/1811.04131). 2026-09-19.

## Notes

Migrated by ledger_split.py; the ledger's own text is kept verbatim above.
