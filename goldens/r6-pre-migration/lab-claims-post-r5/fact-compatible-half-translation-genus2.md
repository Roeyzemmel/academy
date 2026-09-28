---
id: lab:fact-compatible-half-translation-genus2
kind: claim
title: "3-square L tower X' -> X'/iota -> T2/+-1 (half-translation maps, not translation): with Sigma_Y != pi1(Sigma_X), compat(pi2 o pi1) <=> compat(pi1) and compat(pi2) fails for three Sigma_X; with the hypothesis it holds for three"
status: open
bears_on: [paper:fact:compatible]
lifecycle: dropped
domain: translation-surfaces
where: experiments/2026-09-19_fact_compatible_L_counterexample.py
open:
  - not yet run (queue it; the script is standard library only)
  - pi1 and pi2 are half-translation in charts, while paper:fact:compatible item 2 is stated for translation-in-charts maps; this does NOT refute the fact as stated. Roey to decide whether the fact should be read for any surjective flat morphism (its proof is set-theoretic plus surjectivity), in which case the example transfers
  - is the example meant to be cited next to the fact, as the reason the hypothesis is there?
  - one route only (exact grid enumeration); a second route (e.g. surface_dynamics Origami with the library's own hyperelliptic involution instead of the formula for iota) is needed before citing
  - no /verify-result audit yet
evidence: []
history:
  - "2026-09-28 | dropped | schema v2 migration (R5): lifecycle dropped; status = last recorded status `open`"
  - "2026-09-24 | dropped | Roey: translation surfaces only for now; this example uses half-translation maps, so it is out of scope. The script stays in the repo, not queued"
  - "2026-09-24 | open | created; script rewritten in place to Kind: verify, never run"
---
