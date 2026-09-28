---
id: OBS-19
aliases: [W5]
title: "Lifting lemma: (Q2) failure lifts from quotient origamis"
summary: "Draft: if M → M′ → T² and a pair of distinct squares of M′ is not in R^pow(M′), no pair over it is in R^pow(M). Also: at PA-4 the normal/quotient parity obstruction is always absent."
kind: draft
status: Not settled
status_note: "draft; not yet through /verify-claim"
topics: [drafts, quotients, a4-realisation]
depends_on: [STR-5, GEO-22, GEO-23]
source: "writing/a4-candidate-generation.md §2.3 (W5)"
added: 2026-09-24
---

## Statement

<!-- copied from writing/a4-candidate-generation.md §2.3, item W5; the draft stays the working copy -->

> **W5 (lifting lemma; elementary; Not settled, expected to clear).** Suppose
> $M\to M'\to\mathbb T^2$, and $(B,B')$ with $B\ne B'$ is not in $R^{\mathrm{pow}}(M')$. Then
> no pair in $B\times B'$ lies in $R^{\mathrm{pow}}(M)$, because $c=\gamma u^k\gamma^{-1}$ maps
> to $\bar\gamma\bar u^k\bar\gamma^{-1}$, which uses the same word. So (Q2) failure lifts from
> quotients.

**Verdict on (i) at (A4).**
- The (EP) parity map is **always present**, by R2 Thm 3.4(a).
- The D₄/parity obstruction **in normal or quotient form is always absent**. Normal (A4)
  unfoldings are rectangles (W2). A rectangle's $G_0=2\mathbb Z^2/\Lambda=2G$ consists
  entirely of squares, so W9a's normal form cannot bite. Every normal quotient is a torus
  (W2′).
- **(RD4) does not force a $D_4$ quotient.** The only forced quotient is
  $(\mathbb Z/2)^2=G^+/G_0^+$-shifts. The $D_4$ in N8 was incidental.
- What remains of (i) is the **non-normal, pairwise** form of W9a, a coset $g_0G_i$ with no
  square in it. That form must see point stabilisers. For $\mathrm{gr}(T)$ with $\iota(T)=0$
  it adds nothing beyond (CT′)(i), since the power is automatically even.
- *Heuristic, not proved:* at (A4) point stabilisers are large ($|G|\gg n$), squares are
  abundant, and this form is unlikely to be the one that bites. Treat it as a cheap
  relaxation filter only where $|G|$ is small enough to enumerate.

## Proof

The argument is in [writing/a4-candidate-generation.md](../writing/a4-candidate-generation.md) §2.3, item W5, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/a4-candidate-generation.md §2.3 (W5) during the relabelling.
