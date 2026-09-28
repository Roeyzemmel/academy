---
id: lab:relative-marking-standard-examples
kind: claim
title: Lambda(X), [Lambda:L] and |R(X)| on 11 standard surfaces (5 origamis, 3 billiard unfoldings, 2 slit double covers, double pentagon control)
status: open
bears_on: [paper:defn:relative-marking, paper:prop:relative-marking-compatible]
lifecycle: active
domain: translation-surfaces
tags: [relative-marking]
where: experiments/2026-09-18_relative_marking_standard_examples.py
open:
  - not yet run in the new format; the only queue run (09-19, commit 029e329) ended exited-without-result, and its log (scratch/remote_logs/20260919-104107_... on lingo) has not been fetched; likely the 09-19..22 cling segfault, unconfirmed
  - is the measured table of Lambda(X) / R(X) on the unfoldings wanted for the paper, or is this only a check that relative_marking computes correctly (then the tests in tests/test_relative_marking.py are enough)?
  - the old header counted 12 surfaces, the code builds 11 (two separating square-tiled surfaces, not three); is one missing?
  - class excludes large [Lambda:L], Sigma_X other than the full vertex set of the presentation, and non-torus-covers other than the double pentagon
evidence: []
history:
  - 2026-09-28 | open | schema v2 migration (R5), status unchanged
  - 2026-09-24 | open | created; header rewritten in place as a measure (Roey's approval), not yet run
---
