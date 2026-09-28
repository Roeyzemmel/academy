# R2 requote: data-equality report

Generated 2026-09-28 by `py -m registry requote --write --report ...` (academy/registry/requote.py).

Each record of the lab and paper registries was read with the OLD claims.py reader, its frontmatter written again with the dialect's serializer (kb.py's; canonical field order, block lists, `[]`/`""` for empty values, quotes where needed; single quotes for values with a backslash), the body kept byte for byte, and the result read with the NEW parser. A file is written only when every field and the body are equal as data. Files are written LF.

"Was CRLF" below is the working-tree checkout under the system-wide `core.autocrlf=true`; the committed blobs were already LF, so a file whose frontmatter text did not change shows no diff in git. Both worktrees' `.gitattributes` gained `claims/** text eol=lf`.

**Post-write verification (independent of the requote run).** For all 140 records, the OLD reader on the committed blob (`git show HEAD:<file>`, branch `academy-migration` at FlatSurfLab 49c9072 and BilliardIllumination 220ac1b) equals the NEW parser (`fsl.parse_strict`) on the rewritten file, fields and body, and no rewritten file contains a CR: 140 of 140 equal.

## Summary

| files | equal as data | different | unreadable | rewritten | fields compared | list items compared |
|---|---|---|---|---|---|---|
| 140 | 140 | 0 | 0 | 140 | 957 | 515 |

## lab (FlatSurfLab worktree)

Repo `C:/Work/Math/FlatSurfLab-academy`; 25 records; 22 with a changed frontmatter text; 4 already read the same by both parsers before requoting.

| file | fields | list items | equal | frontmatter text changed | was CRLF |
|---|---|---|---|---|---|
| `claims/lab/arith-dark-pairs-pm1.md` | 8 | 11 | yes | yes | yes |
| `claims/lab/b0-slopes-small-origamis.md` | 8 | 10 | yes | yes | yes |
| `claims/lab/delaunay-ms91-standard-examples.md` | 9 | 7 | yes | no | yes |
| `claims/lab/descent-family-n-le-7.md` | 8 | 9 | yes | yes | yes |
| `claims/lab/fact-compatible-half-translation-genus2.md` | 8 | 8 | yes | yes | yes |
| `claims/lab/fact-compatible-half-translation-pillowcase.md` | 8 | 7 | yes | yes | yes |
| `claims/lab/fact-compatible-weak-condition-pillowcase.md` | 8 | 8 | yes | yes | yes |
| `claims/lab/fine-coarse-illumination-n-le-7.md` | 8 | 9 | yes | no | yes |
| `claims/lab/immersed-polygon-single-affine.md` | 9 | 7 | yes | no | yes |
| `claims/lab/k4-normalizer-self-maps.md` | 8 | 5 | yes | yes | yes |
| `claims/lab/null-holonomy-origami-examples.md` | 9 | 10 | yes | yes | yes |
| `claims/lab/parabolic-descent-n-le-7.md` | 9 | 10 | yes | yes | yes |
| `claims/lab/parabolic-descent-n8.md` | 9 | 10 | yes | yes | yes |
| `claims/lab/parabolic-descent.md` | 7 | 6 | yes | yes | yes |
| `claims/lab/periodicity-invariance-preimages.md` | 9 | 11 | yes | yes | yes |
| `claims/lab/plug-unfolding-lift-count.md` | 8 | 8 | yes | yes | yes |
| `claims/lab/q2-cyclic-covers-n-14-18.md` | 9 | 10 | yes | yes | yes |
| `claims/lab/q2-cyclic-covers-n-le-12.md` | 9 | 11 | yes | yes | yes |
| `claims/lab/q2-ew-ornithorynque.md` | 9 | 10 | yes | yes | yes |
| `claims/lab/relative-marking-compatibility.md` | 9 | 13 | yes | yes | yes |
| `claims/lab/relative-marking-genus2-partial.md` | 9 | 9 | yes | yes | yes |
| `claims/lab/relative-marking-standard-examples.md` | 9 | 8 | yes | yes | yes |
| `claims/lab/rhombus-kite-isosceles-unfoldings.md` | 9 | 11 | yes | yes | yes |
| `claims/lab/similarity-forced-by-rotation.md` | 9 | 8 | yes | yes | yes |
| `claims/lab/torus-periodic-growth-standard.md` | 9 | 10 | yes | yes | yes |

**Values the old reader kept with their quotes** (kept as data, so the quote characters are now part of the value; a human may want to drop them):

- none

## paper (BilliardIllumination worktree)

Repo `C:/Work/Math/BilliardIllumination-academy`; 115 records; 90 with a changed frontmatter text; 77 already read the same by both parsers before requoting.

| file | fields | list items | equal | frontmatter text changed | was CRLF |
|---|---|---|---|---|---|
| `claims/paper/conj__arith-relative-marking.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/conj__origami-slope.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/conj__slope-one-quotient.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/conj__torus-cover-tokarsky.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/conj__unfolding-characterization.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/cor__arith-billiard-finite.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/cor__arith-k-diff-finite.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/cor__arith-relative-position.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/cor__arith-slope-pm-one.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/cor__arithmetic-k-diff.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/cor__db-faith.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/cor__parking-garage-classification.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/cor__periodic-prim-relations.md` | 7 | 6 | yes | yes | yes |
| `claims/paper/cor__relative-marking-invariance-preimage.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/cor__short-path-geodesic.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/cor__slope-minus-one.md` | 7 | 3 | yes | no | yes |
| `claims/paper/cor__tokarsky-corners.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/cor__voronoi-permutation.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/defn__covering-moduli.md` | 6 | 4 | yes | yes | yes |
| `claims/paper/defn__delaunay.md` | 6 | 4 | yes | no | yes |
| `claims/paper/defn__flat-equivalence.md` | 6 | 4 | yes | no | yes |
| `claims/paper/defn__flat-structure.md` | 6 | 5 | yes | yes | yes |
| `claims/paper/defn__unfolding.md` | 6 | 4 | yes | no | yes |
| `claims/paper/ex__bary-delaunay.md` | 6 | 2 | yes | no | yes |
| `claims/paper/ex__branched-double-cover.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/ex__periodicity-coex.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/ex__platonic-boundary.md` | 6 | 3 | yes | no | yes |
| `claims/paper/ex__ppsg.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/ex__reduced-torus-16.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/ex__reduced-torus-32.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/ex__rhombus-same-unfolding.md` | 6 | 5 | yes | no | yes |
| `claims/paper/ex__torus-corners.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/ex__translation-orbit-marking.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/ex__two-square-tori.md` | 6 | 2 | yes | no | yes |
| `claims/paper/fact__aw-closed-markings.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/fact__aw-slope-pm-one.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/fact__barycentric-ds-properties.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/fact__compatible.md` | 6 | 2 | yes | no | yes |
| `claims/paper/fact__equivariant-is-zigzag.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/fact__flat-morphism-compose.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/fact__flat-structure-charts.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/fact__flat-structure-invariants.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/fact__forgetful-props.md` | 7 | 4 | yes | yes | yes |
| `claims/paper/fact__polygonal-ds-properties.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/fact__positive-systole.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/fact__S-normal-symmetric.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/lem__covering-moduli-proper.md` | 6 | 6 | yes | yes | yes |
| `claims/paper/lem__flat-equivalence-props.md` | 7 | 6 | yes | yes | yes |
| `claims/paper/lem__illumination-chase.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/lem__involution-blocking.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/lem__lift-to-unfoldings.md` | 7 | 3 | yes | no | yes |
| `claims/paper/lem__marking-full-preimage.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/lem__null-holonomy-tori.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/lem__periodic-coimage.md` | 7 | 5 | yes | yes | yes |
| `claims/paper/lem__periodic-inheritence.md` | 6 | 6 | yes | yes | yes |
| `claims/paper/lem__primitive-coset-existence.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/lem__primitive-purity.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/lem__relative-marking-invariance.md` | 7 | 7 | yes | no | yes |
| `claims/paper/lem__saddle-homotopy.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/lem__similarity-forced-by-rotation.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/lem__straightline-invariance.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/lem__structure-group-hierarchy.md` | 7 | 6 | yes | no | yes |
| `claims/paper/lem__thick-part-compact.md` | 7 | 8 | yes | yes | yes |
| `claims/paper/lem__tok.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/lem__tokarsky-descends.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/lem__tokarsky-target.md` | 6 | 2 | yes | no | yes |
| `claims/paper/lem__torus-corners-torsion.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/lem__trans-auth-effect.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/prop__blocking-monodromy.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/prop__cornered-arithmetic.md` | 7 | 4 | yes | yes | yes |
| `claims/paper/prop__corners-finite.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/prop__delaunay-invariance.md` | 7 | 5 | yes | yes | yes |
| `claims/paper/prop__delaunay-isometry-permutation.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/prop__fiber-disjoint-trajectory.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/prop__pathologies-inherited.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/prop__periodicity-invariance.md` | 6 | 5 | yes | yes | yes |
| `claims/paper/prop__polygon-sym.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/prop__reduced-torus-balanced.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/prop__reduced-torus-compatible.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/prop__reduced-torus-covering.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/prop__relative-marking-compatible.md` | 6 | 2 | yes | no | yes |
| `claims/paper/prop__saturated-markings-coverings.md` | 7 | 3 | yes | no | yes |
| `claims/paper/prop__tc-class.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/prop__unfolding-lift-general.md` | 7 | 6 | yes | yes | yes |
| `claims/paper/prop__vorobets-lift.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/prop__vorobets-veech-inclusion.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/prop__Voronoi-invariance.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/rmk__apisa-wright-reduction.md` | 6 | 2 | yes | no | yes |
| `claims/paper/rmk__aw-marked-periodic.md` | 6 | 2 | yes | no | yes |
| `claims/paper/rmk__best-converse.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/rmk__billiard-corners.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/rmk__cornered-arithmetic-ds.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/rmk__flat-morphism-flow.md` | 7 | 2 | yes | yes | yes |
| `claims/paper/rmk__flat-structure-orbifold.md` | 6 | 3 | yes | no | yes |
| `claims/paper/rmk__full-preimage-free.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/rmk__nonempty-marking.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/rmk__plug-unfolding.md` | 6 | 2 | yes | no | yes |
| `claims/paper/rmk__polygon-determined.md` | 7 | 4 | yes | no | yes |
| `claims/paper/rmk__saturation-vs-symmetry.md` | 6 | 2 | yes | no | yes |
| `claims/paper/rmk__slope-values-resolvable.md` | 6 | 2 | yes | no | yes |
| `claims/paper/rmk__slope-values-torus.md` | 6 | 2 | yes | no | yes |
| `claims/paper/rmk__slope-values.md` | 6 | 2 | yes | no | yes |
| `claims/paper/thm__arith-slope-constraint.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/thm__arithmetic-billiard-goal.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/thm__aw-finiteness.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/thm__barycentric-ds-bijection.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/thm__main-parking-garage.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/thm__main-resolvable-4k.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/thm__moeller-primitive.md` | 7 | 3 | yes | yes | yes |
| `claims/paper/thm__orthogonal-billiard-goal.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/thm__polygonal-ds-bijection.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/thm__primitive-construction.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/thm__primitive-G-structure.md` | 6 | 2 | yes | no | yes |
| `claims/paper/thm__schreier-lts-bijection.md` | 6 | 1 | yes | yes | yes |
| `claims/paper/thm__torus-periodic-points.md` | 7 | 6 | yes | yes | yes |

**Values the old reader kept with their quotes** (kept as data, so the quote characters are now part of the value; a human may want to drop them):

- none
