---
id: lab:q2-cyclic-covers-n-le-12
title: (Q2) holds on every square-tiled cyclic cover M_N(a) with N even, N <= 12, every corner marked
status: refuted
where: experiments/2026-09-23_cyclic_covers_a.py
bears_on:
  - s1:Q2
  - s1:CEX-1
evidence:
  - "experiment | results/2026-09-23_cyclic_covers_a.json | cleared (one representative per class, Slope1 /settle) | 12 members at N=12 fail: unit orbits of {1,3,3,5} (|G|=72, not normal) and {1,5,7,11} (|G|=24, normal); none fail at N <= 10"
  - "verdict | Slope1illuminationResearch:computation/verdicts/2026-09-23_refutation-M12-1335.md | cleared | M_12(1,3,3,5): two refutation-verifier and two result-auditor runs; recorded as s1:CEX-1 (formerly N8)"
  - "verdict | Slope1illuminationResearch:computation/verdicts/2026-09-23_refutation-M12-15711.md | cleared | M_12(1,5,7,11): same; s1:CEX-1"
history:
  - 2026-09-24 | refuted | Slope1's kb renamed N8 to s1:CEX-1; verdict refs point at its per-entry files
  - 2026-09-24 | refuted | seeded from the experiment header and result JSON (job 20260923-123801, commit 34552b0)
open:
  - the other ten failing members at N = 12 are not independently verified
  - the class excludes N > 12, non-cyclic abelian covers, and the exact (A4)-(A6) hypothesis levels
tags:
  - q2
  - cyclic-covers
---
Refuted at hypothesis level (A3), now Slope1's OA-3, in the every-corner-marked setting. N11
(Slope1) shows neither failing member is an (A4) unfolding, so this does not reach (A4).
