---
id: lab:descent-family-n-le-7
title: At every J > 0 state where p is interior to cylinders of one direction d only, a power of the shear not preserving d lowers J, on reduced origamis with 3..7 squares
status: supported
where: experiments/2026-09-23_descent_family.py
evidence:
  - "experiment | results/2026-09-23_descent_family/n3-7.json | not audited | 0 refutations; pure-type J > 0 states: 0/0/24/300/3760 for n = 3..7; V3 census match against parabolic_descent n3-6 and n7-7 (commit 556d98b)"
history:
  - 2026-09-24 | supported | outcome read from the JSON, not from the header (its Result line says pending)
open:
  - "NEXT (rescheduled 2026-09-24): n = 8 queued (job 20260924-173753) for more discriminating states"
  - "weakly discriminating: at n = 7 both shears descend at 3716 of the 3760 pure-type states; only 44 (h:L 22, v:R 22) separate the predicted shear from the other"
  - nothing about n > 7, regular coarse targets, fine grids 1/N with N >= 3, or words mixing R and L
  - no paper label in the header; the queue label lem:descent-family is not a \label; related to lab:parabolic-descent-n-le-7
  - no /verify-result audit
tags:
  - vh
  - descent
---
