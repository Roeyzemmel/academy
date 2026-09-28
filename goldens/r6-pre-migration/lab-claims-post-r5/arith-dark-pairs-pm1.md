---
id: lab:arith-dark-pairs-pm1
kind: claim
title: "Search: a non-illuminable pair (x,y) on an arithmetic surface with pi(y) != +-pi(x) in R^2/Lambda_0 (five named surfaces, denominator <= 6, bound 2B = 24)"
status: open
bears_on: [paper:lem:illumination-chase, paper:cor:arith-relative-position, paper:cor:arith-slope-pm-one]
lifecycle: active
domain: translation-surfaces
where: experiments/2026-09-18_illumination_chase.py
open:
  - "NEXT (Roey 2026-09-24: non-periodic points unless stated): the class is rational grids on torus covers, i.e. periodic points only. Redesign for non-periodic x, y (coordinates in a number field) once the Sage origami core (C2) exists; not queued until then"
  - not yet run (queue job 20260919-102332 parked since 09-19, reason unrecorded)
  - the old header's second refuting outcome ("a non-illuminable pair on a surface where the paper's conjectures predict none") named no surface and was dropped; restore it only with a named surface
  - paper:lem:illumination-chase (closures of loci) is deliberately not in bears_on; the search tests only a pointwise necessary condition
  - no known example of the full property exists; only the dark branch (marked 2x2 torus, y = -x) and the +-1 classifier (synthetic pi-values) are validated
  - depends on fslab.origami_illumination (scheduled for replacement) and private helpers of fslab.relative_marking
evidence: []
history:
  - 2026-09-28 | open | schema v2 migration (R5), status unchanged
  - "2026-09-24 | open | bears_on paper:lem:illumination-chase added: BI's experiments.md row named it"
  - 2026-09-24 | open | created; header rewritten in place into the search format (Roey's approval)
---
