---
id: lab:parabolic-descent-n8
kind: claim
title: Parabolic descent holds on every reduced origami with 8 squares
status: refuted
bears_on: [lab:parabolic-descent]
lifecycle: active
domain: translation-surfaces
tags: [vh, descent]
where: experiments/2026-09-23_parabolic_descent.py
open:
  - recheck the two failing states by an independent route (J along the R- and L-cycles computed without fslab.vh_orbits.J); suspect J before believing the lemma false
  - "evidence to come: experiments/2026-09-24_parabolic_descent_n8_recheck.py (verify, two routes, route 2 written without fslab.vh / vh_orbits / sd_extras); written, not yet committed or queued"
  - illumination is not affected in this orbit (0 dark components, every component reaches J=0); only the descent route fails
  - no /verify-result audit
evidence:
  - "experiment | results/2026-09-23_parabolic_descent/n8-8.json | not audited | - | 2 parabolic failures among 1430352 states in 113 orbits: one orbit in H(4,2), r=[0,2,1,3,5,4,7,6], u=[1,2,3,4,6,0,7,5], two J=1 states whose whole R-cycle and L-cycle stay at J=1 (states and chains in the JSON's `failures`)"
history:
  - 2026-09-28 | refuted | schema v2 migration (R5), status unchanged
  - 2026-09-24 | refuted | bears_on repointed from paper:lem:parabolic-descent (never a \label) to lab:parabolic-descent
  - 2026-09-24 | refuted | read from the n=8 JSON (commit 556d98b, clean); the certificate has not been rechecked
---
