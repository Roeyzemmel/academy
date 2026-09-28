---
key: AW21
pinpoint: Definition 2.3
version: arXiv v3 (27 Jan 2021)
read_from: source
verdict: match
used_by: [paper:defn:slope, paper:rmk:slope-values-resolvable]
source_label: D:slope
checked: 2026-09-23
by: author@bi/source-checker
migrated: Drafts/sources.md (author@bi)
---

## Statement

_To fill (migrated): the statement relied on._

## Hypotheses

_To fill (migrated): the hypotheses, one per bullet._

## Quote

> Let $\cN$ be an irreducible 2-point marking over $\cM$. As above, consider any $(X,\omega, \{p_1,p_2\})\in \cN$, and rewrite the linear equation locally defining the fiber in the form $\int_{\gamma_1} \omega = a\int_{\gamma_2} \omega + \int_\gamma \omega$, with $a\neq 0$. We define the slope of $\cN$ to be $a$ or $1/a$, whichever is larger in absolute value.

## Ledger text

- **Definition 2.3** (source label `D:slope`, `AW21.src/main.tex:425-430`) — resolved
  by counting the shared `thm` counter (reset `[section]`) within §2 ("Proof of
  Theorem \ref{T:main}", starting `AW21.src/main.tex:375`): `L:FiberDim`=Lemma 2.1,
  the unlabelled Example after it=Example 2.2, `D:slope`=**Definition 2.3**,
  `R:MorePoints`=Remark 2.4, three more Examples=2.5-2.7, `T:Slope1`=Theorem 2.8
  (consistent with the "hence Theorem 2.8" count already recorded above). Verbatim:
  "Let $\cN$ be an irreducible 2-point marking over $\cM$. As above, consider any
  $(X,\omega, \{p_1,p_2\})\in \cN$, and rewrite the linear equation locally defining
  the fiber in the form $\int_{\gamma_1} \omega = a\int_{\gamma_2} \omega +
  \int_\gamma \omega$, with $a\neq 0$. We define the slope of $\cN$ to be $a$ or
  $1/a$, whichever is larger in absolute value." Immediately after (line 432): "Note
  that if the role of $p_1$ and $p_2$ are interchanged, $1/a$ will play the role of
  $a$." Compared against the draft's `defn:slope` (`sections/slope_blocking.tex`
  lines 100-118, quoted in full in the LMW16 re-check entry above): **AW21's $a$ is
  the same ratio as the draft's/LMW16's $\lambda$** (both come from the single linear
  relation between the two relative periods on the 1-dimension-larger fibre — AW21's
  $\{p_1,p_2\}$ unordered with $\gamma_1,\gamma_2$ playing the role of the draft's
  $\alpha,\beta$), **but AW21 then canonicalises**: since $\cN$ is a marking by an
  *unordered pair* $\{p_1,p_2\}$, swapping which point is $p_1$ replaces $a$ by
  $1/a$, and AW21 fixes a single number for $\cN$ by taking whichever of $a,1/a$ is
  $\ge 1$ in absolute value. The draft's $\lambda$, by contrast, is defined for an
  **ordered** pair $(x,y)$ (`sections/slope_blocking.tex:101-102`, "a marking over
  $\cM$ by an ordered pair $(x,y)$") and takes no absolute-value normalisation, so it
  ranges freely over $\R\cup\{\infty\}$ and flips to $1/\lambda$ under $(x,y)
  \mapsto (y,x)$ exactly as AW21's $a$ does before the max-normalisation is applied.
  **Verdict: the underlying linear-relation constructions match** (same fibre, same
  pair of relative periods, same "which one is larger" ambiguity under reordering the
  two points); **the normalisations differ** as the existing `\Claude` note at
  `sections/slope_blocking.tex:156-163` already states — AW21's slope is an
  order-independent invariant of the unordered marking $\cN$ (always $|a|\ge 1$),
  while `defn:slope`'s $\lambda$ is an order-dependent invariant of the ordered pair
  $(x,y)$ (any value in $\R\cup\{\infty\}$). They coincide exactly where $|\lambda|=1$
  (since $1/1=1$ and $1/(-1)=-1$, the two conventions agree at $\pm1$ regardless of
  order), which is precisely the range Theorem 2.8 asserts — so citing
  `\cite[Theorem~2.8]{AW21}` for "every irreducible 2-point marking has slope $1$ or
  $-1$" in `rmk:slope-values-resolvable` is **safe under either normalisation**, but
  the two `\lambda`/`a` symbols should not be treated as identical in general (e.g.
  LMW16 §6 Example 1's slope $-a/b$, $a\ne b$, would be reported by AW21's convention
  as $-b/a$ when $b>a$, a different number from the draft's/LMW16's $\lambda=-a/b$).
  This confirms and closes the existing `\Claude` note's "open Tier 4 item": the
  attribution split is real but harmless for every value the draft currently cites
  from AW21 Theorem 2.8. How read: **source** (v3, `AW21.src/main.tex`). 2026-09-23.

## Notes

Migrated by ledger_split.py; the ledger's own text is kept verbatim above.
