---
id: lab:relative-marking-genus2-partial
title: With g(Y) = 2 and pi(Sigma_X) = Sigma_Y, Lambda(X) = Lambda(Y), pi^{-1}(R(Y)) = R(X) and pi(R(X)) = R(Y) on 876 partially marked rational slit covers (denominator <= 4)
status: supported
where: experiments/2026-09-19_relative_marking_genus2_partial.py
bears_on:
  - paper:lem:relative-marking-invariance
evidence:
  - experiment | results/2026-09-19_relative_marking_genus2_partial.json | not audited | 0 refuted among 876 configurations in 42 families (--den 4, --extra-limit 6, commit 1b97839); drop-one D1 (genus 1), D2 and D3 each fail as expected; D4 vacuous
history:
  - 2026-09-24 | supported | outcome read from the JSON, not from the header (its Result line is unfilled)
open:
  - "NEXT (rescheduled 2026-09-24): irrational cases, blocked until C3 rebuilds the stack on flatsurf (ptranslation is Fraction-only)"
  - every surface is rational, so the intersection with Q.L(X) in eq:relative-lattice is vacuous; no irrational case was run (the Sage path did not start on 2026-09-19)
  - class excludes targets of genus >= 3, targets that are not slit double covers of the square torus, and other ramification patterns
  - pure-Python fallback (fslab.ptranslation), not the Sage implementation
  - no /verify-result audit
tags:
  - relative-marking
---
