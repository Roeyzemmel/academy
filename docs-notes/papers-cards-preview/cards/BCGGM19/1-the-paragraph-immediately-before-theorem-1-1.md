---
key: BCGGM19
pinpoint: §1, the paragraph immediately before Theorem 1.1
version: arXiv v2 (16 Nov 2017)
read_from: extraction
verdict: see-notes
used_by: [paper:lem:thick-part-compact]
checked: 2026-09-24
by: author@bi/source-checker
migrated: Drafts/sources.md (author@bi)
---

## Statement

_To fill (migrated): the statement relied on._

## Hypotheses

_To fill (migrated): the hypotheses, one per bullet._

## Quote

> Recall that period coordinates provide local coordinates for the strata of abelian and quadratic differentials \cite{HubbardMasur}. In particular, the existence of period coordinates implies the smoothness of the strata in these cases, and gives the dimension of the strata.

## Ledger text

- **§1, the paragraph immediately before Theorem 1.1** — verbatim (arXiv v2,
  `kdiff_arxiv_final.tex` line 312): "Recall that period coordinates provide local
  coordinates for the strata of abelian and quadratic differentials
  \cite{HubbardMasur}. In particular, the existence of period coordinates implies the
  smoothness of the strata in these cases, and gives the dimension of the strata."
  `\cite{HubbardMasur}` resolves, in `kdiff_arxiv_final.bbl` line 226, to Hubbard, J.
  and Masur, H. (HM79). Checked against the published version too
  (`BCGGM19-published.txt`, *Algebraic Geometry* 6 (2019), no. 2): the same sentence
  appears verbatim immediately before the identically-numbered Theorem 1.1, so arXiv
  and published numbering agree here; either `\cite[\S 1]{BCGGM19}` or `\cite[the
  paragraph preceding Theorem 1.1]{BCGGM19}` works as a pinpoint. Verdict: **found
  with caveat** — BCGGM19's marked points $z_1,\dots,z_n$ in this theorem are all
  zeros or poles of $\xi$, so the statement as read does not on its face cover a
  marked point that is a regular point of the flat structure (the same marked-vs-
  singular gap already flagged for KMS86 in the `## SW08` block); not circular the way
  MW17 is, since BCGGM19 does not define its topology by period coordinates but states
  the fact as an already-established input before proving its own Theorem 1.1.
  Recommended for the zeros-only case of the period-coordinates-are-local-charts step
  in `lem:thick-part-compact`'s proof (not yet applied to the `.tex`, since this is a
  new supporting citation rather than a pinpoint correction). How read: extraction
  (arXiv v2 source and published PDF). (moved from the Job 2 / Tier 3d issue C log,
  2026-09-24)

## Notes

Migrated by ledger_split.py; the ledger's own text is kept verbatim above.
