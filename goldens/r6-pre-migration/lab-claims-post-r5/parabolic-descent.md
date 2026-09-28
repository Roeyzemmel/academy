---
id: lab:parabolic-descent
kind: claim
title: Parabolic descent lemma — on every reduced origami, every VH state with J > 0 has a state with smaller J in its R-cycle or L-cycle
status: open
lifecycle: active
domain: translation-surfaces
tags: [vh, descent]
where: experiments/2026-09-23_parabolic_descent.py
open:
  - lab:parabolic-descent-n8 reports a counterexample (one H(4,2) orbit at n = 8); it is neither rechecked by an independent route nor audited, so the lemma stays open rather than refuted
  - supported below n = 8 (lab:parabolic-descent-n-le-7), not audited
  - "not a statement in the paper; if it goes in, it gets a paper: id and this claim bears on it"
evidence: []
history:
  - 2026-09-28 | open | schema v2 migration (R5), status unchanged
  - 2026-09-24 | open | created from the experiment header's "Claim tested"; it was the queue label paper:lem:parabolic-descent, which was never a \label in the paper
---
Stated in full in the header of `experiments/2026-09-23_parabolic_descent.py` (J as computed by
`fslab.vh_orbits.J`, B the coarse lattice, p a non-coarse point of the 2-subdivision, q a cone point).
