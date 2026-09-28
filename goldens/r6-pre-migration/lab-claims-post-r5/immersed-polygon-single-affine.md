---
id: lab:immersed-polygon-single-affine
kind: claim
title: A flat equivalence between connected immersed rational polygons is one global affine map (m=8 immersed star)
status: supported
bears_on: [paper:rmk:polygon-determined]
lifecycle: active
domain: translation-surfaces
tags: [parking-garage, flat-equivalence]
where: experiments/2026-09-22_parking_garage_single_affine.py
open:
  - one immersed example only; no search class beyond the m=8 star
  - no /verify-result audit
evidence:
  - experiment | results/2026-09-22_parking_garage_single_affine.json | not audited | - | the same affine map on all 8 charts of the m=8 immersed star, for every g tested; fails as expected when connectedness is dropped
history:
  - 2026-09-28 | supported | schema v2 migration (R5), status unchanged
  - 2026-09-24 | supported | seeded from the experiment header
---
Suggests connectedness, not embeddedness, is what the embedded proof uses; this matches
Roey's claim in Tier 9 issue 5.
