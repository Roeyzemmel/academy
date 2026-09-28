---
id: lab:relative-marking-compatibility
kind: claim
title: pi^{-1}(pi(R(X))) = R(X) on 133 two-slit (Z/2)^2 torus covers X -> Y (Y genus 2), slit data of denominator <= 4, 8 of them in Q(sqrt 2)
status: supported
bears_on: [paper:lem:relative-marking-invariance, paper:prop:relative-marking-compatible]
lifecycle: active
domain: translation-surfaces
tags: [relative-marking]
where: experiments/2026-09-18_relative_marking_compatibility.py
open:
  - "NEXT (rescheduled 2026-09-24): widen the Q(sqrt 2) part beyond 8 members; a code change, so it comes with the Sage migration and a verify/search header for Roey to approve"
  - only the 8 members with data in Q(sqrt 2) have content; by the header, the purely rational members are covers where compatibility holds for trivial reasons
  - class excludes non-parallel slits, coverings of degree > 2, non-normal coverings, and slit data of denominator > 4
  - the lifted_slit_cover validation case is not recorded in the JSON
  - legacy JSON, no outcome block
  - no /verify-result audit
evidence:
  - experiment | results/2026-09-18_relative_marking_compatibility.json | not audited | - | 0 refutations of (1) among 133 configurations (X in H(1^8), Y in H(1^2,0^4), --bound 4, commit 029e329); pi(R(X)) = R(Y) also held on all 133, though not claimed
history:
  - 2026-09-28 | supported | schema v2 migration (R5), status unchanged
  - "2026-09-24 | supported | bears_on paper:lem:relative-marking-invariance added: BI's experiments.md row named it"
  - 2026-09-24 | supported | outcome read from the JSON, not from the header (its Result line is unfilled); 0 of 133 configurations refute (1)
  - 2026-09-24 | open | seeded; a result JSON exists but the header's Result line was never filled
---
