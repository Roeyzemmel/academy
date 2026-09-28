---
id: lab:delaunay-ms91-standard-examples
title: The MS91 restatement of defn:delaunay (paths, not endpoints) gives a tiling by empty-disc concyclic cells on 11 standard examples; the old wording gives empty D(X) on 7 of them
status: supported
where: experiments/2026-09-21_delaunay_ms91_standard_examples.py
bears_on:
  - paper:defn:delaunay
evidence:
  - experiment | results/2026-09-21_delaunay_ms91_standard_examples.json | not audited | checks (a) tiling, (b) concyclic with empty circumdisc, (c) path count = vertex count pass on all 11 surfaces; 0 refuted, 0 hand-value mismatches, 0 errors (commit 1cb3692); old wording empty on the 7 members with at most 2 marked points
history:
  - 2026-09-24 | supported | outcome read from the JSON, not from the header (its Result line is unfilled)
open:
  - 11 named surfaces only; exact arithmetic, one route (sage-flatsurf delaunay_decompose plus fslab.delaunay)
  - class cannot drop "Sigma contains all cone points", "Sigma nonempty" or "compact without boundary"; the Sigma = cone points only variant was not run
  - no /verify-result audit
tags:
  - delaunay
---
