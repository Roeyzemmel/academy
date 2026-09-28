---
id: lab:plug-unfolding-lift-count
kind: claim
title: "A point x of a rational table lifts to |K_P|/|Gamma_x| points of the unfolding, each of angle |Gamma_x| angle(x): on seven small tables by coset count plus Gauss-Bonnet genus, and on the 3x2 rectangle in coordinates"
status: open
bears_on: [paper:rmk:plug-unfolding]
lifecycle: active
domain: translation-surfaces
where: experiments/2026-09-19_plug_unfolding_lift_count.py
open:
  - not yet run (queue it; the script is standard library only)
  - route 2 is a coset count, true by construction once K_P and the side reflections are right; the only independent checks are route 1 (3x2 rectangle only) and the genus comparison with the closed genus formula (polygonal tables only)
  - route 3 (flatsurf billiard(P).minimal_cover("translation"), vertices over each corner and their angles) is a TODO; the calls that attribute cover vertices to corners and read their angles are not confirmed in api-recipes.md, so run /api-check first
  - the old docstring promised "a triangle with a pi/3 and a 2pi/3 corner"; the code runs an equilateral triangle with a marked edge point and a (pi/3, 2pi/3, pi/3, 2pi/3) parallelogram. The header now describes the code; Roey to say which was intended
  - the slit table (ii) and the interior-cone-point table (iii) have no independent genus value and cannot be built as flatsurf polygons; is route 2 plus integrality of the Gauss-Bonnet genus enough for them, or should they be built with slit_covers?
  - no /verify-result audit yet
evidence: []
history:
  - 2026-09-28 | open | schema v2 migration (R5), status unchanged
  - "2026-09-24 | open | created; script rewritten in place to Kind: verify, never run"
---
