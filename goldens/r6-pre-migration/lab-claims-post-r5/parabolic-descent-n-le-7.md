---
id: lab:parabolic-descent-n-le-7
kind: claim
title: Parabolic descent — every state with J > 0 has a state with smaller J in its R-cycle or L-cycle — on reduced origamis with 3..7 squares
status: supported
bears_on: [lab:parabolic-descent]
lifecycle: active
domain: translation-surfaces
tags: [vh, descent]
where: experiments/2026-09-23_parabolic_descent.py
open:
  - nothing about n > 7; at n = 8 the lemma fails on 2 states (lab:parabolic-descent-n8)
  - no /verify-result audit
  - the "shear along p's cylinder" rule is not discriminated (right 10, wrong 54 where only one family descends)
evidence:
  - "experiment | results/2026-09-23_parabolic_descent/n3-6.json | not audited | - | 0 failures among 17616 states (n=3..6); weak: J > 0 at only 348 states"
  - experiment | results/2026-09-23_parabolic_descent/n7-7.json | not audited | - | 0 failures among 137445 states in 40 orbits (n=7); J > 0 at 4136 states
history:
  - 2026-09-28 | supported | schema v2 migration (R5), status unchanged
  - 2026-09-24 | supported | bears_on repointed from paper:lem:parabolic-descent (never a \label) to lab:parabolic-descent
  - 2026-09-24 | supported | seeded from the experiment header (runs at 1b50d63 and 34552b0)
---
