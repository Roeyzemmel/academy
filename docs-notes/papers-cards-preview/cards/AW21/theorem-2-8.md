---
key: AW21
pinpoint: Theorem 2.8
version: arXiv v3 (27 Jan 2021)
read_from: source
verdict: match
used_by: [paper:fact:aw-closed-markings, paper:rmk:slope-values]
source_label: T:Slope1
checked: 2026-09-23
by: author@bi/source-checker
migrated: Drafts/sources.md (author@bi)
---

## Statement

_To fill (migrated): the statement relied on._

## Hypotheses

_To fill (migrated): the hypotheses, one per bullet._

## Quote

> Suppose that $\cM$ has only finitely many $\cM$-periodic points. Then any irreducible $2$-point marking $\cN$ over $\cM$ has slope $1$ or $-1$.

## Ledger text

- **Theorem 2.8** — source label `T:Slope1`, the eighth environment sharing the
  `thm` counter in §2 ("Proof of Theorem \ref{T:main}") — counted as: Lemma 2.1
  `L:FiberDim`, an unlabeled Example (2.2), Definition 2.3 `D:slope`, Remark 2.4
  `R:MorePoints`, three further unlabeled Examples (2.5–2.7), then `T:Slope1` —
  hence Theorem 2.8. Verbatim (`AW21.src/main.tex:453-455`): "Suppose that $\cM$ has
  only finitely many $\cM$-periodic points. Then any irreducible $2$-point marking
  $\cN$ over $\cM$ has slope $1$ or $-1$." Combined with Theorem 1.2 (`T:periodic`,
  Eskin–Filip–Wright, `AW21.src/main.tex:283-285`: "An affine invariant submanifold
  has infinitely many periodic points if and only if it consists entirely of
  branched covers of tori"), this is the source of the "resolvable $\Rightarrow$
  slope $\pm1$" constraint: on an $\cM$ not consisting entirely of torus covers,
  $\cM$ has finitely many periodic points by Theorem 1.2, so Theorem 2.8 applies and
  forces slope $\pm1$ on every irreducible 2-point marking. Verdict: **match** for
  the "only slope $\pm1$ point markings occur outside the torus-cover case" claim
  intended for `rmk:slope-values` — note Theorem 2.8 itself is stated for an
  irreducible 2-point marking directly (via the periodic-points hypothesis), not
  phrased in terms of finite blocking; the finite-blocking route to the same
  hypothesis on $x_1,x_2$ (that they are not both $\cM$-periodic) is **Theorem 3.6**
  (`T:cor`, `AW21.src/main.tex:743-745`: "If $x_1$ and $x_2$ are finitely blocked on
  $(X,\omega)$, then either they are both $\cM$-periodic points or zeros ... or
  $\piQ(x_1)=\piQ(x_2)$", proved by invoking the slope-$\pm1$ movement of Theorem
  2.8). [**Correction, 2026-09-24**: this environment was previously mislabelled
  "Theorem 2.15" in this file — an error from extending §2's `thm`-counter count
  across the section break. `T:cor` sits in §3 ("The finite blocking problem"), whose
  counter resets per AW21's `[section]` numbering scheme (see the Definition 2.3 note
  below); confirmed against the printed number in `AW21.txt` line 792, "Theorem 3.6.
  If x1 and x2 are finitely blocked...". See the "AW21 numbering conflict, Tier 4
  issue 3a, 2026-09-24" block near the end of this file for the full resolution and
  every other pinpoint checked in that pass.] Recommended pinpoint for the slope-$\pm1$ constraint itself: `\cite[Theorem
  2.8]{AW21}` (optionally with `\cite[Theorem 1.2]{AW21}` for the torus-cover
  equivalence). This is **distinct from** `\cite[Lemma 2.10]{AW21}`
  (`fact:aw-closed-markings`, source label `L:producecover`), which gives the
  covering construction, not the slope value. How read: **source** (v3, confirmed
  against `AW21.src/main.tex`). 2026-09-23.

## Notes

Migrated by ledger_split.py; the ledger's own text is kept verbatim above.
