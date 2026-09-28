---
id: lab:null-holonomy-origami-examples
kind: claim
title: The 8/16/32-square origamis of ex:reduced-torus-32 and ex:reduced-torus-16 have the lattices, cone orders, T(X), T_0(X), Z(X) and compatibility verdicts the appendix states
status: supported
bears_on: [paper:ex:reduced-torus-32, paper:ex:reduced-torus-16]
lifecycle: active
domain: translation-surfaces
tags: [null-holonomy, reduced-torus]
where: experiments/2026-09-23_null_holonomy_origami_examples.py
open:
  - one route only (pure-Python fslab.null_holonomy); surfaces reconstructed from the appendix prose, no surviving permutations to compare against
  - "resolved 2026-09-24: the 0^14 in stratum_X are the 14 unmarked regular corners of the tiling (22 vertex classes = 8 cone + 14 regular, from genus 6); fslab.ptranslation.stratum() lists every vertex class. A labelling defect of the retiring pure stack, not a marked-point question"
  - Sigma_T(X) is reported with representatives (-2,0), (-1,0), equal to the claimed (2,0), (3,0) mod L(X); the JSON flag says they match
  - no /verify-result audit
evidence:
  - "experiment | results/2026-09-23_null_holonomy_origami_examples.json | not audited | - | every *_matches_claim flag true: L(X) = <(4,0),(0,2)> proper in (2Z)^2, cone orders {3, 1x7}, Sigma_T sets, trivial Trans, T_0 areas 8 and 4; ex-32: Z(X) not a union of pi-fibres; ex-16: Z(X) = Sigma_X, pi(Sigma_X) = Sigma_Y, X not compatible with pi (commit e62b554)"
history:
  - 2026-09-28 | supported | schema v2 migration (R5), status unchanged
  - 2026-09-24 | supported | outcome read from the JSON, not from the header (its Result line is unfilled)
---
