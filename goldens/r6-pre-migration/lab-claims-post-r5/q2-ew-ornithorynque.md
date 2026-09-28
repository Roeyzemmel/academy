---
id: lab:q2-ew-ornithorynque
kind: claim
title: (Q2) holds with K_min = 2 on the Eierlegende Wollmilchsau (two labellings) and the Ornithorynque M_6(1,1,1,3), every corner marked
status: proved
bears_on: [s1:Q2]
lifecycle: active
domain: translation-surfaces
tags: [q2, named-origamis]
where: experiments/2026-09-23_ew_ornithorynque_record.py
open:
  - "the Slope1 clearing was conditional on header fixes to Result: and Validation; the rerun in the verify format (outcome block) is queued to carry them"
  - two origamis only; nothing about other points of either Teichmueller curve, fewer marked points, (Q1) or illumination
  - the Ornithorynque is CyclicCover([1,1,1,3]) from the library, not checked against FMZ's printed tuples
evidence:
  - experiment | results/2026-09-23_ew_ornithorynque_record.json | cleared (Slope1 verdict, two SOUND) | - | 3 records TRUE at K_min = 2, W complete (|W| = 6/6/45), raw BFS agrees, GAP compare_with_python AGREE; R Prop. 5.7 agrees on both EW records; no pipeline failures (job 20260923-123800, commit 34552b0)
  - "verdict | Slope1illuminationResearch:computation/verdicts/2026-09-23_E1-ew_ornithorynque_record.md | cleared | - | two independent result-auditor runs SOUND; conditional on header fixes to Result: and Validation"
history:
  - 2026-09-28 | proved | schema v2 migration (R5), status unchanged
  - "2026-09-24 | proved | Roey: a verify on three named objects, cross-checked with GAP and cleared by two SOUND auditor runs (Slope1); the script's header is now Kind: verify"
  - 2026-09-24 | supported | seeded from the experiment header and result JSON
---
