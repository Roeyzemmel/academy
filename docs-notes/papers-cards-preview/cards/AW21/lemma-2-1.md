---
key: AW21
pinpoint: Lemma 2.1
version: arXiv v3 (27 Jan 2021)
read_from: source
verdict: match
used_by: [paper:defn:saturated-marking, paper:fact:forgetful-props]
source_label: L:FiberDim
checked: 2026-09-19
by: author@bi/source-checker
migrated: Drafts/sources.md (author@bi)
---

## Statement

_To fill (migrated): the statement relied on._

## Hypotheses

_To fill (migrated): the hypotheses, one per bullet._

## Quote

> Let $\cN$ be a point marking over $\cM$, and let $(X, \omega, S)\in \cN$. For each $s\in S$, fix a path $\gamma_s$ from a zero of $\omega$ to $s$. Then each branch of the fiber of $\cN$ over $(X,\omega)$ is locally defined by a collection of linear equations of the form $\sum_{s\in S} a_s \int_{\gamma_s}\omega = \int_\gamma \omega$ ... Moreover, these equations can be chosen to hold locally on $\cN$, and each fiber of $\cN$ over $\cM$ is either empty or has dimension $\dim \cN-\dim \cM$.

## Ledger text

- **Lemma 2.1** — source label `L:FiberDim`, first `\begin{lem}` in §2 ("Proof of
  Theorem \ref{T:main}"), hence Lemma 2.1. Verbatim: "Let $\cN$ be a point marking
  over $\cM$, and let $(X, \omega, S)\in \cN$. For each $s\in S$, fix a path
  $\gamma_s$ from a zero of $\omega$ to $s$. Then each branch of the fiber of $\cN$
  over $(X,\omega)$ is locally defined by a collection of linear equations of the
  form $\sum_{s\in S} a_s \int_{\gamma_s}\omega = \int_\gamma \omega$ ... Moreover,
  these equations can be chosen to hold locally on $\cN$, and each fiber of $\cN$
  over $\cM$ is either empty or has dimension $\dim \cN-\dim \cM$." Verdict:
  **match**, confirmed against `fact:forgetful-props` and the AW21 pointer after
  `defn:saturated-marking`. How read: **source** (v3, confirmed). 2026-09-19.

## Notes

Migrated by ledger_split.py; the ledger's own text is kept verbatim above.
