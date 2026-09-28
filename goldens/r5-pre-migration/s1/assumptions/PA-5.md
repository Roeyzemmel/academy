---
id: PA-5
title: "semi-corners only at relative marking points"
summary: "PA-4, and every semi-corner of P lifts to relative marking points of M (regular marked points); by GEO-9 this holds iff every semi-corner has angle π, i.e. every corner is an odd multiple of π/2"
kind: assumption
old: "— (new 2026-09-24)"
implies: [PA-5w]
incomparable_with: [PA-SC]
source: "new (Roey, 2026-09-24)"
added: 2026-09-24
---

## Definition

PA-4, and every **semi-corner** of $P$ — a vertex of angle $k\pi$, $k\ge1$, in the sense of
BilliardIllumination `defn:billiard-pathologies` — lies over **relative marking points** of
the unfolding: its lifts to $M$ are regular points (cone angle $2\pi$) that are marked, not
zeros. No other semi-corner is allowed.

*Equivalent form.* By GEO-9 (R Prop 1.6), a corner of angle $m\pi/2$ with $m=2k$ even gives
two $k$-cycles of $[\sigma,\tau]$, so each lift has cone angle $2k\pi$, a zero of order $k-1$
(this matches BilliardIllumination `rmk:plug-unfolding`). The lifts are relative marking
points iff $k=1$. So PA-5 holds iff every semi-corner has angle $\pi$, i.e. every corner of
$P$ (boundary point of angle $\ne\pi$) has angle an **odd** multiple of $\pi/2$, and no vertex
has angle $2\pi,3\pi,4\pi,\dots$. Stronger than PA-5w, which allows $3\pi,5\pi,\dots$.

## Relations

PA-5 ⇒ PA-5w: by definition. PA-6 ⇒ PA-5 is GEO-31, **Proved** (2026-09-24). PA-SC and PA-5 are incomparable: GEO-32, **Proved** (2026-09-24), garage level — the 8-square fan is PA-SC but not PA-5, the $3\times3$ square frame is PA-5 but not PA-SC. GEO-32's same witnesses also show PA-SC and PA-5w incomparable, previously resting on R §0.2 alone. The admitted class of garages is unchanged by the 2026-09-24 restatement, so GEO-31 and GEO-32 stand.

## History

- 2026-09-24: created during the relabelling. New text; the verbatim definition stays at the source.
- 2026-09-24: gloss restricted per `computation/verdicts/2026-09-24_GEO-31.md` findings 1 and
  "Definition" — "corner" reads "boundary point of angle $\ne\pi$", not "turning point", and
  the semi-corner sentence now states PA-5's own sense against BilliardIllumination's
  ($k\ge1$) sense, rather than claiming PA-5 excludes semi-corners outright. Relations line
  updated to Proved. Wording repair only; no change of meaning, since angle-$\pi$ points were
  already excluded from "corners" in the definition.
- 2026-09-24: frontmatter `summary` aligned with the corrected definition ("corner" = boundary
  point of angle $\ne\pi$, not "turning point"). `incomparable_with: [PA-SC]` added and the
  Relations line updated for GEO-32's clearance (`computation/verdicts/2026-09-24_GEO-32.md`,
  Proved).
- 2026-09-24: reworded per Roey, verbatim: "redefinining PA-5 - I agree, as we allow for
  relative markings. So let's allow in PA-5 relative markings that are at semi-corners."
  Title and Definition now name BilliardIllumination's `defn:billiard-pathologies` directly
  and describe the exemption as "relative markings" rather than leaving it implicit through
  the angle-$\pi$-is-not-a-corner convention. Wording only: the class of qualifying garages is
  unchanged (angle-$\pi$ points were already excluded from "corners"), so GEO-31 and GEO-32
  are unaffected.
- 2026-09-24: reworded per Roey, verbatim: "Pa-5 shoold not allow any semi-corner, rather only
  semi-corners that lie on relative marking points in the unfolding." Wording restated on the
  unfolding: a semi-corner qualifies by its lift to $M$ being a relative marking point, not by
  a garage-level angle description alone; class unchanged (equivalence via GEO-9).
