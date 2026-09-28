---
id: lab:torus-periodic-growth-standard
title: "|S_v| = (sum v_k)^2 per v and the growth of |union S_v, |v_k| <= R|, R = 1..6, on the maximal torus of 4 square-tiled torus covers"
status: open
where: experiments/2026-09-24_torus_cover_periodic_growth.py
bears_on:
  - paper:thm:torus-periodic-points
  - paper:rmk:slope-values
evidence: []
history:
  - 2026-09-24 | open | created; header rewritten in place as a measure (Roey's approval), not yet run
open:
  - not yet run; it must run once at the current commit before C3 retires ptranslation / pslit_covers / null_holonomy / torus_periodic, and its JSON is then the C3 regression target (docs/code-audit.md)
  - "question for Roey: does the growth count add anything beyond thm:torus-periodic-points plus Eskin-Filip-Wright (F rational, so P(T(X), F) is infinite and no plateau is possible), or is the per-S_v formula check the real content? Kept as a measure of both until he decides"
  - class excludes the double pentagon (fslab.ptranslation is Fraction-only), P(X) itself as opposed to P(T(X), F), irrational marks, non-square-tiled torus covers, and R > 6
  - the brute-force upper bound on S_v (all solutions found) is checked only for |v_k| <= 2; beyond it only the lower bound (N^2 distinct solutions) is computed, the rest being the kernel-of-N count
  - paper's slope_blocking.tex:62 cites the script as "written, not run"
tags:
  - periodic-points
  - torus-covers
---
