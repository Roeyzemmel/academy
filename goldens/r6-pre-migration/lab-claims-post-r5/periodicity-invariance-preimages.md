---
id: lab:periodicity-invariance-preimages
kind: claim
title: Every other preimage of a marked point is periodic (PR reading) on marked tori with at most 3 points over Q(sqrt 2), quotient lattices of order <= 4
status: supported
bears_on: [paper:prop:periodicity-invariance, paper:lem:periodic-coimage]
lifecycle: active
domain: translation-surfaces
tags: [periodic-points]
where: experiments/2026-09-19_periodicity_invariance_preimages.py
open:
  - fslab/torus_periodic.py's Z2 reading still encodes the old primitive-only statement; update it to the current one (all v in Z^n_+) when C3 rebuilds the module, and rerun then
  - the header calls the statement a one-line theorem in this class, so the run tests the readings of P, not the claim
  - class excludes X not a torus cover, square-tiled X with a proper sub-lattice marking, data outside Q(sqrt 2); Z2/Q2 "not periodic" is bounded by vbound 5
  - drop-one E3 (X not a torus cover) not runnable
  - no /verify-result audit
evidence:
  - "experiment | results/2026-09-19_periodicity_invariance_preimages.json | not audited | - | part B: 0 refutations and 0 nesting failures over 532 (F, p, g) triples (--order 4, vbound 5, commit 1b97839); the literal Z2 wording of eq:torus-average disagrees with PR on 490 of the 532; part A (5 origamis, 40 checks) vacuous by design"
history:
  - 2026-09-28 | supported | schema v2 migration (R5), status unchanged
  - 2026-09-24 | supported | the Z2-vs-PR disagreement (490/532) was this run's finding against the then-printed eq:torus-average (union over PRIMITIVE v); the paper was corrected in Tier 10 (BilliardIllumination 74dcd44, 2026-09-23) to all v in Z^n_+ with v(p) not necessarily primitive, which matches PR
  - 2026-09-24 | supported | outcome read from the JSON, not from the header (its Result line is unfilled)
---
