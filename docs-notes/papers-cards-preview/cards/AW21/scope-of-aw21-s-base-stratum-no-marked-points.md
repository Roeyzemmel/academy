---
key: AW21
pinpoint: "Scope of AW21's base stratum — no marked points"
version: arXiv v3 (27 Jan 2021)
read_from: source
verdict: see-notes
used_by: [paper:fact:forgetful-props, paper:lem:periodic-inheritence]
checked: 2026-09-21
by: author@bi/source-checker
migrated: Drafts/sources.md (author@bi)
---

## Statement

_To fill (migrated): the statement relied on._

## Hypotheses

_To fill (migrated): the hypotheses, one per bullet._

## Quote

> Affine invariant submanifolds

## Ledger text

- **Scope of AW21's base stratum — no marked points.** Verbatim from
  `AW21.src/main.tex:277,279` (§1, "Affine invariant submanifolds" / "Marked points on
  translation surfaces" paragraphs, immediately before `L:FiberDim`): "Given a
  partition of $2g-2$ as a sum of positive integers $2g-2=\sum_{i=1}^s k_i$, define the
  stratum $\cH(k_1, \ldots, k_s)$ to be the orbifold of all translation surfaces
  $(X,\omega)$ where $X$ has genus $g$ and $\omega$ has zeros of order
  $k_1, \ldots, k_{s}$." and "Let $\cH^{*n}$ denote the set of surfaces in $\cH$ with
  $n$ distinct marked points, none of which coincide with each other or with zeros of
  the Abelian differential." Verdict: **confirms the marked-base caveat** — AW21's
  base stratum $\cH(k_1,\ldots,k_s)$ is defined with no marked points at all; every
  marked point in the paper's framework lives one level up, in $\cH^{*n}$, forgotten by
  $\pi:\cH^{*n}\to\cH$. Consequently `L:FiberDim` (Lemma 2.1) is proved for a point
  marking $\cN$ over an affine invariant submanifold $\cM$ of an unmarked base
  $\cH$ — applying it (as `fact:forgetful-props` / `lem:periodic-inheritence` do) to a
  base that itself already carries marked points is an extension beyond what AW21
  states, and should be named as such in the text (e.g. a `\Claude` note or an explicit
  remark that the argument is run one marked-point-level up from where AW21 states it,
  or that the extension is routine because $\cH^{*n}$ with its own marked points is
  itself an unmarked-zero stratum of a bigger differential datum only after relabelling
  — whichever way the writer resolves it, the gap should not pass silently). How read:
  **source** (v3, `AW21.src/main.tex`). 2026-09-21.

## Notes

Migrated by ledger_split.py; the ledger's own text is kept verbatim above.
