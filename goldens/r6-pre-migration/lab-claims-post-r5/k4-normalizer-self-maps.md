---
id: lab:k4-normalizer-self-maps
kind: claim
title: Which elements of N(K_4) are linear parts of affine self-maps of a rectangle unfolding
status: open
bears_on: [paper:defn:flat-equivalence, paper:defn:flat-structure]
lifecycle: dropped
domain: translation-surfaces
where: paper:sections/flat_structures.tex
open:
  - the self-map case waits on generalising N(M, Delta) to non-isometric affine automorphisms (roadmap, Tier 9 issue 3); that definition, not a computation, is what is missing
evidence:
  - hand | BilliardIllumination:sections/flat_structures.tex | - | - | N(K_4) is the invertible monomial matrices (proved in the paper); diag(p,1/p) maps aZ+bZ to paZ+(b/p)Z, which equals the lattice only for p = +-1, for every rectangle
history:
  - "2026-09-28 | dropped | schema v2 migration (R5): lifecycle dropped; no earlier status recorded -> open"
  - "2026-09-24 | dropped | Roey: retired in favour of the two-line argument; the script (experiments/2026-09-22_flat_equivalence_K4_normalizer.py, never run) is deleted and stays in git history"
---
