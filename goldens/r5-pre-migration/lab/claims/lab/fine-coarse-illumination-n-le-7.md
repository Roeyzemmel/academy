---
id: lab:fine-coarse-illumination-n-le-7
title: Every non-coarse half-lattice point sees every cone point, the coarse grid blocking, on reduced origamis with 3..7 squares
status: supported
where: experiments/2026-09-23_fine_coarse_illumination_orbit.py
evidence:
  - experiment | results/2026-09-23_fine_coarse_illumination_orbit/n3-6.json | not audited | 0 of 945 start triples non-illuminated (1/3/7/25 orbits for n = 3..6), V1-V6 passed, BFS distance at most 4 (commit 8deb46c)
  - experiment | results/2026-09-23_fine_coarse_illumination_orbit/n7.json | not audited | 0 of 1323 start triples non-illuminated, 40 orbits, V1-V6 passed, BFS distance at most 5 (commit 8deb46c)
history:
  - 2026-09-24 | supported | seeded from the experiment header and result JSONs
open:
  - nothing about n > 7, regular coarse points as targets, fine grids 1/N with N >= 3, non-arithmetic surfaces, or blocking sets other than the full coarse grid
  - V1 orbit counts cite Hubert-Lelievre / McMullen 2005, not yet through source-checker
  - no paper label in the header; the queue label illum:fine-cone is not a \label
  - no /verify-result audit
tags:
  - vh
  - illumination
---
