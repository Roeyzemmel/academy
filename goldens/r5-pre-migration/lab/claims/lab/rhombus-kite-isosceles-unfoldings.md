---
id: lab:rhombus-kite-isosceles-unfoldings
title: The bare unfoldings of the kite Q1, rhombus Q2 and isosceles triangle Q3 built from T = (pi/10, pi/2, 2pi/5) are pairwise translation-isomorphic, in H(3,3)
status: supported
where: experiments/2026-09-22_rhombus_kite_isosceles_double_pentagon.py
bears_on:
  - paper:prop:polygon-sym
  - paper:ex:rhombus-same-unfolding
evidence:
  - "experiment | results/2026-09-22_rhombus_kite_isosceles_double_pentagon.json | not audited | canonicalize(): bare Q1-Q2, Q1-Q3, Q2-Q3 isomorphic; with marked points only Q2-Q3 isomorphic (Q1 carries 12 marked regular points, Q2 and Q3 carry 2); all three genus 4, equal area (commit c571b7d)"
history:
  - "2026-09-24 | supported | bears_on paper:prop:polygon-sym added: BI's experiments.md row named it"
  - 2026-09-24 | supported | outcome read from the JSON, not from the header (its Result line says not yet run)
open:
  - "NEXT (rescheduled 2026-09-24): the covering question needs a new design: the area sieve is scale-dependent (the root cause of the false REFUTED); only Riemann-Hurwitz survives, bounding the degree by 3. A search for an explicit covering, header for Roey to approve"
  - covering of the double pentagon undecided. The JSON says REFUTED because area(M_Qi)/area(DP) = 1.8885..., not an integer, but DP is veech_double_n_gon(5) at its own scale, never normalised against T, so this rules out only that one scaled copy, not a cover of a rescaled or rotated double pentagon
  - one route only (canonicalize); a verify with one route stays supported
  - no /verify-result audit
tags:
  - unfolding
  - double-pentagon
---
