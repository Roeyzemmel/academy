---
id: OBS-18
aliases: [W9b]
title: "Trap: test (CT′)(i), not the literal (CT), on shift-0 elements"
summary: "Draft remark: for T with ι(T) = 0 no primitive direction is ≡ ι(T) mod 2, so the literal GA-CT clause is false; this happens at PA-4 but not under GA-HA; pipelines must test (CT′)(i)."
kind: remark
topics: [drafts, q2-criteria, computation]
depends_on: [CRIT-15]
source: "writing/a4-candidate-generation.md §1.2 (W9b)"
added: 2026-09-24
---

## Statement

<!-- copied from writing/a4-candidate-generation.md §1.2, item W9b; the draft stays the working copy -->

> **W9b (a trap, not an error in the database).** (CT) in R2 §4.4 asks for a value "of
> direction $\equiv\iota(T)\pmod2$". For a $T$ with $\iota(T)=0$, no primitive direction
> qualifies, so the literal clause is false. Under (HA) this cannot happen, because
> $\iota(T)\ne0$ (Thm 4.5(b)). At (A4) it does happen: see W7. The correct condition is
> (CT′)(i), with an even power. The hand-check in §5 is exactly such a case. **A pipeline
> must test (CT′)(i), never the literal (CT), on shift-0 elements.**

## Proof

The argument is in [writing/a4-candidate-generation.md](../writing/a4-candidate-generation.md) §1.2, item W9b, which remains the working copy until the item passes `/verify-claim`.

## History

- 2026-09-24: registered from writing/a4-candidate-generation.md §1.2 (W9b) during the relabelling.
