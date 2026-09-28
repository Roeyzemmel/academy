---
id: GEO-31
aliases: []
title: "PA-6 ⇒ PA-5: every corner of an embedded rectangle-tiled polygon is π/2 or 3π/2"
summary: "Every corner (boundary point of angle ≠ π) of an embedded rectangle-tiled polygon has angle π/2 or 3π/2, so PA-6 ⇒ PA-5; marked angle-π points are semi-corners in BilliardIllumination's sense"
kind: prop
status: Proved
status_note: ""
level: PA-6
topics: [assumptions, unfoldings]
depends_on: []
source: "new (Roey's redefinition of PA-5, 2026-09-24)"
added: 2026-09-24
cleared_by: [computation/verdicts/2026-09-24_GEO-31.md]
---

## Statement

Let $P$ be a rectangle-tiled polygon **embedded** in the plane (in particular any PA-6
witness). Every corner of $P$ — every boundary point of angle $\ne\pi$ — has angle $\pi/2$ or
$3\pi/2$. Hence PA-6 ⇒ PA-5 (the PA-4 conjunct: an embedded $P$ has flat interior and $h$ is
the inclusion; equivalently PA-6 ⇒ PA-5w ⇒ PA-4). The proof uses only embeddedness and
axis-parallel sides, not simple connectivity, so it also covers embedded regions with holes.

## Proof

$P$ is embedded, so a small disc about a boundary point meets $P$ in one sector: by
injectivity of $h$, an angle $>2\pi$ would force the sector to overlap itself, and angle
$2\pi$ is a slit tip whose two sides coincide, so every corner's angle is below $2\pi$. The
sides are axis-parallel, so a corner's angle is $\pi/2$, $\pi$ or $3\pi/2$; angle $\pi$ is not
a corner (it is a boundary point on a straight side), so every corner has angle $\pi/2$ or
$3\pi/2$. This gives PA-5's turning-point condition. The PA-4 conjunct of PA-5 holds by
definition: an embedded $P$ has a flat interior, with $h$ the inclusion — equivalently,
PA-6 ⇒ PA-5w ⇒ PA-4. Hence PA-6 ⇒ PA-5.

## History

- 2026-09-24: created with the new PA-5. The edge PA-6 ⇒ PA-5 is stored as `implies_pending` until this clears.
- 2026-09-24: status Not settled → Proved (verdict computation/verdicts/2026-09-24_GEO-31.md)
- 2026-09-24: Statement and Proof transcribed from the Allowed wording of
  `computation/verdicts/2026-09-24_GEO-31.md` (two `claim-verifier` runs on claude-opus-5-5,
  both Proved/CONFIRMED).
- 2026-09-24: PA-5 restated on the unfolding (semi-corners only at relative marking points);
  the class is unchanged (GEO-9), so this item stands as cleared.
