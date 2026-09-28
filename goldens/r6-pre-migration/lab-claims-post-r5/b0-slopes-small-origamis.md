---
id: lab:b0-slopes-small-origamis
kind: claim
title: "Search: a B_0 pair on a branched 3- or 4-square origami whose admissible slopes (Reading A) omit both 1 and -1"
status: open
bears_on: [paper:rmk:slope-values, paper:cor:slope-minus-one]
lifecycle: active
domain: translation-surfaces
where: experiments/2026-09-23_b0_slope_values_torus_covers.py
open:
  - "NEXT (Roey 2026-09-24: non-periodic points unless stated): the class is rational grids on torus covers, i.e. periodic points only. Redesign for non-periodic x, y (coordinates in a number field) once the Sage origami core (C2) exists; not queued until then"
  - not yet run
  - should regular (unmarked) lattice points be allowed as x or y? They are not in Sigma_X under the script's convention, and v = (0,0) would admit lambda = 0; kept excluded (tagged [excludes ...]) because fslab.relative_marking.marking_slope_candidates refuses (0,0) as if it were in Sigma_X
  - no known B_0 pair inside the class; the B_0 detector is validated on the marked 2x2 torus midpoint pair, which lies outside the class's marking convention (its marked points are regular)
  - the old header's (a)/(b) (lambda in {0, inf}, lambda irrational) cannot occur in this class by construction; the class says nothing about them
  - Reading (B) (y a periodic unmarked anchor) is not searched
  - depends on fslab.origami_illumination (scheduled for replacement)
evidence: []
history:
  - 2026-09-28 | open | schema v2 migration (R5), status unchanged
  - 2026-09-24 | open | created; header rewritten in place into the search format (Roey's approval)
---
