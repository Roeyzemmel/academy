---
id: OPEN-13
aliases: []
title: "EMM orbit-closure theorem with marked points: which reference?"
summary: "GEO-29(c) and GEO-30 use EMM15 Thm 2.1 in strata with marked points; EMM as written has none. Parked (Roey, 2026-09-24): many papers assume the extension; find the reference later"
kind: open
status: Not settled
status_note: "parked by Roey, 2026-09-24"
topics: [base-point, marked-points, open]
depends_on: [GEO-29, GEO-30]
cites: [EMM15, AW21]
source: "../papers/EMM15.meta scope note; GEO-30 input (A) in notes/01-geometry/dictionary.md (R2 §2.1)"
added: 2026-09-24
---
## Statement

GEO-29(c) and GEO-30 (R2 Lemma 2.1(c), Thm 2.2) cite input (A), "Eskin–Mirzakhani–Mohammadi
Thm 2.1: orbit closures in strata (marked points allowed) are affine invariant submanifolds".
The scope note in `../papers/EMM15.meta` says the paper as written covers strata of abelian
differentials **with no marked points** (its $\alpha$ is a partition of $2g-2$). **Which
reference justifies the marked-point version used in $\mathcal H^*_1$ and $\mathcal H^*_2$?**

## Notes

- Roey, 2026-09-24: many papers assume that EMM applies to strata with marked points. Leave this
  aside for now and check it later. **No status changes until then.** GEO-29 and GEO-30 stay
  "Proved modulo EMM Thm 2.1, Smillie–Weiss".
- Places to look first: AW21 (Apisa–Wright, "Marked points on translation surfaces", cached in
  `../papers/AW21.src/`), and the BilliardIllumination paper's own use of EMM15 in
  `lem:covering-moduli-proper` (`../papers/index.md`, row EMM15).
- If a reference is found: add its key to `cites` of GEO-29 and GEO-30 and name it in their
  inputs. The label "Proved modulo stated inputs" may then need the extension listed as an input.

## History

- 2026-09-24: created to park the question raised by the relabelling's semantic pass (Roey: check later).
