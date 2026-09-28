---
key: AW21
pinpoint: Published-version check and marked-base scope, 2026-09-21 (Tier 3d, issue A1)
version: arXiv v3 (27 Jan 2021)
read_from: abstract
used_by: []
checked: 2026-09-21
by: author@bi/source-checker
migrated: Drafts/sources.md (author@bi)
---

## Statement

_To fill (migrated): the statement relied on._

## Hypotheses

_To fill (migrated): the hypotheses, one per bullet._

## Quote

_No verbatim quote._

## Ledger text

- **Published-version check and marked-base scope, 2026-09-21 (Tier 3d, issue A1).**
Attempted to reach the published Geometry & Topology PDF for Theorem 1.3 (`T:main`)
and Lemma 2.1 (`L:FiberDim`) the same way as for LMW16 above:
`https://msp.org/gt/2021/25-6/gt-v25-n6-p03-s.pdf` and the `-p.pdf` variant (found via
`https://msp.org/gt/2021/25-6/index.xhtml`, article `p03.xhtml`, pages 2913–2961,
doi:10.2140/gt.2021.25.2913, matching `references.bib`) both return HTTP 200 but serve
an HTML "Access Denied" / subscription page, not the PDF (`curl` on the same host with
the same method worked for LMW16's 2016 volume but not this 2021 one — MSP's own
subscriptions page confirms Geometry & Topology is not fully open-access, only
individual older volumes/articles are). The abstract page
(`https://msp.org/gt/2021/25-6/p03.xhtml`) is reachable and gives only the abstract.
**Published Theorem 1.3 and Lemma 2.1 could not be checked**; the arXiv v3 numbering
already recorded above (`T:main` = Theorem 1.3, `L:FiberDim` = Lemma 2.1, both
resolved by counting the shared `thm` counter within each `\section`) is the only
numbering confirmed by this agent. Recommended pinpoints stay
`\cite[Theorem~1.3]{AW21}` and `\cite[Lemma~2.1]{AW21}`, understood as **arXiv v3
numbering, published numbering unverified** — flag this if a coauthor has
institutional access to Geometry & Topology and can confirm the two numbers carry
over (Apisa–Wright's own papers rarely renumber between arXiv and GT, but this was not
independently checked here). How read: abstract page only (published); **not read**
(published body).

## Notes

Migrated by ledger_split.py; the ledger's own text is kept verbatim above.
