---
id: lab:q2-cyclic-covers-n-14-18
kind: claim
title: (Q2) holds on all 238 square-tiled cyclic covers M_N(a), N in {14, 16, 18}, up to units, every corner marked
status: supported
bears_on: [s1:Q2]
lifecycle: active
domain: translation-surfaces
tags: [q2, cyclic-covers]
where: experiments/2026-09-23_cyclic_covers_b.py
open:
  - the clearing is recorded in Slope1's verdicts, not in results/audits.md here
  - class excludes N outside {14, 16, 18}, non-cyclic abelian covers, non-abelian or non-pillowcase covers, and the exact (A4)-(A6) levels
  - "blind spot: the 72 members with |G| > 1000 ran no W search, so the run is silent on N2 there and on K_min > 2"
  - the unit quotient rests on the FMZ duality lemma, spot-checked on 10 members at N = 14 only
evidence:
  - experiment | results/2026-09-23_cyclic_covers_b.json | cleared (Slope1 verdict, two SOUND) | - | 238 run (57/64/117), all TRUE at K = 2, certificates re-checked in GAP, 0 failed, 0 not run, 0 undecided; |G| in [28, 2916] (job 20260923-123801, commit 34552b0)
  - "verdict | Slope1illuminationResearch:computation/verdicts/2026-09-23_E2b-cyclic_covers_b.md | cleared | - | two independent result-auditor runs SOUND; conditional on filling Result: and committing the JSON"
history:
  - 2026-09-28 | supported | schema v2 migration (R5), status unchanged
  - 2026-09-24 | supported | seeded from the experiment header and result JSON
---
