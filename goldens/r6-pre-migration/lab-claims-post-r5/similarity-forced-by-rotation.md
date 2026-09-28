---
id: lab:similarity-forced-by-rotation
kind: claim
title: For K = C_n, D_n with 3 <= n <= 12, every g with g K g^{-1} in O_2(R) is a similarity (dim F(K) = 1); for n = 1, 2 non-similarity g exist
status: supported
bears_on: [paper:lem:flat-equivalence-props]
lifecycle: active
domain: translation-surfaces
tags: [flat-equivalence, structure-group]
where: experiments/2026-09-21_similarity_forced_by_rotation.py
open:
  - nothing about n > 12 (the class is otherwise exhaustive up to O_2-conjugacy)
  - "drop-one: infinite K and K not in O_2 recorded but not part of the claim"
  - no /verify-result audit
evidence:
  - "experiment | results/2026-09-21_similarity_forced_by_rotation.json | not audited | - | 96 rows (C_n, D_n, n = 1..12, 4 positions each), exact over AA: 80 rows with a rotation of order >= 3 all have dim F = 1; 16 sharpness rows have dim F = 2 or 3 with a verified witness; 0 counterexamples, 0 inconsistent; 40 random draws per family, none conjugating without being a similarity (commit 1cb3692)"
history:
  - 2026-09-28 | supported | schema v2 migration (R5), status unchanged
  - 2026-09-24 | supported | outcome read from the JSON, not from the header (its Result line says not yet run)
---
