# Agenda: author@bi

<!-- academy agenda v1 (author plugin, references/formats.md). Row order is the
precedence: paper order by default. Edit label, claim, required, depends_on and owner
by hand or with /author:agenda; the status column is refreshed by
`agenda.py status` from the registry and is never edited by hand. -->

The paper's results in paper order. `/author:next` works on the items that unblock
the earliest entry first. `required` is the status an entry must reach; `status` is
what the registry says now (vocabulary: the academy `status-vocabulary` skill).

## Milestones

None yet. A milestone is a line `- `name`: label=status, ...` (a coauthor round, a submission).

## Entries

| # | label | claim | required | depends_on | owner | status |
|---|---|---|---|---|---|---|
| 1 | defn:resolvable | paper:defn:resolvable | proved | defn:unfolding | author@bi | missing |
| 2 | thm:main-resolvable-4k | paper:thm:main-resolvable-4k | conjectured | - | author@bi | conjectured |
| 3 | thm:main-parking-garage | paper:thm:main-parking-garage | conjectured | - | author@bi | conjectured |
| 4 | conj:origami-slope | paper:conj:origami-slope | conjectured | - | author@bi | conjectured |
| 5 | conj:slope-one-quotient | paper:conj:slope-one-quotient | conjectured | - | author@bi | conjectured |
| 6 | thm:arithmetic-billiard-goal | paper:thm:arithmetic-billiard-goal | conjectured | - | author@bi | conjectured |
| 7 | thm:orthogonal-billiard-goal | paper:thm:orthogonal-billiard-goal | conjectured | - | author@bi | conjectured |
| 8 | defn:blocking | paper:defn:blocking | proved | - | author@bi | missing |
| 9 | defn:flat-structure | paper:defn:flat-structure | proved | defn:corners | author@bi | proved |
| 10 | fact:flat-structure-invariants | paper:fact:flat-structure-invariants | proved | - | author@bi | proved |
| 11 | fact:flat-structure-charts | paper:fact:flat-structure-charts | proved | defn:flat-structure | author@bi | proved |
| 12 | defn:unfolding | paper:defn:unfolding | proved | defn:flat-structure, fact:flat-structure-charts, defn:flat-morphism | author@bi | proved |
| 13 | rmk:flat-structure-orbifold | paper:rmk:flat-structure-orbifold | proved | - | author@bi | sketch |
| 14 | defn:flat-morphism | paper:defn:flat-morphism | proved | fact:flat-structure-charts, defn:flat-equivalence | author@bi | missing |
| 15 | defn:flat-equivalence | paper:defn:flat-equivalence | proved | fact:flat-structure-charts | author@bi | proved |
| 16 | lem:similarity-forced-by-rotation | paper:lem:similarity-forced-by-rotation | proved | defn:flat-structure, defn:flat-equivalence | author@bi | sketch |
| 17 | lem:lift-to-unfoldings | paper:lem:lift-to-unfoldings | proved | defn:unfolding, defn:flat-morphism, defn:flat-equivalence, defn:flat-structure, fact:flat-structure-charts | author@bi | sketch |
| 18 | lem:structure-group-hierarchy | paper:lem:structure-group-hierarchy | proved | lem:lift-to-unfoldings | author@bi | sketch |
| 19 | fact:flat-morphism-compose | paper:fact:flat-morphism-compose | proved | fact:flat-structure-charts, lem:structure-group-hierarchy | author@bi | sketch |
| 20 | lem:flat-equivalence-props | paper:lem:flat-equivalence-props | proved | defn:flat-equivalence, defn:flat-morphism, defn:flat-structure, ex:two-square-tori, lem:lift-to-unfoldings, fact:flat-structure-invariants | author@bi | sketch |
| 21 | ex:two-square-tori | paper:ex:two-square-tori | proved | - | author@bi | proved |
| 22 | rmk:polygon-determined | paper:rmk:polygon-determined | proved | - | author@bi | sketch |
| 23 | rmk:flat-morphism-flow | paper:rmk:flat-morphism-flow | proved | - | author@bi | sketch |
| 24 | defn:double-cover | paper:defn:double-cover | proved | - | author@bi | missing |
| 25 | ex:platonic-boundary | paper:ex:platonic-boundary | proved | - | author@bi | proved |
| 26 | defn:billiard-table | paper:defn:billiard-table | proved | defn:billiard-pathologies | author@bi | missing |
| 27 | prop:polygon-sym | paper:prop:polygon-sym | proved | - | author@bi | sketch |
| 28 | defn:billiard-pathologies | paper:defn:billiard-pathologies | proved | defn:flat-structure, rmk:plug-unfolding, prop:pathologies-inherited, thm:main-parking-garage | author@bi | missing |
| 29 | rmk:plug-unfolding | paper:rmk:plug-unfolding | proved | - | author@bi | proved |
| 30 | prop:pathologies-inherited | paper:prop:pathologies-inherited | proved | - | author@bi | sketch |
| 31 | prop:vorobets-lift | paper:prop:vorobets-lift | proved | - | author@bi | proved |
| 32 | prop:unfolding-lift-general | paper:prop:unfolding-lift-general | proved | lem:lift-to-unfoldings | author@bi | sketch |
| 33 | ex:rhombus-same-unfolding | paper:ex:rhombus-same-unfolding | proved | - | author@bi | sketch |
| 34 | defn:compatible | paper:defn:compatible | proved | - | author@bi | missing |
| 35 | fact:compatible | paper:fact:compatible | proved | defn:compatible, defn:flat-morphism | author@bi | proved |
| 36 | defn:periodic-points | paper:defn:periodic-points | proved | - | author@bi | missing |
| 37 | thm:aw-finiteness | paper:thm:aw-finiteness | proved | - | author@bi | proved |
| 38 | rmk:nonempty-marking | paper:rmk:nonempty-marking | proved | - | author@bi | proved |
| 39 | defn:forgetful-map | paper:defn:forgetful-map | proved | - | author@bi | missing |
| 40 | fact:forgetful-props | paper:fact:forgetful-props | proved | defn:forgetful-map | author@bi | sketch |
| 41 | lem:periodic-inheritence | paper:lem:periodic-inheritence | proved | defn:periodic-points, fact:forgetful-props, rmk:nonempty-marking | author@bi | sketch |
| 42 | defn:covering-moduli | paper:defn:covering-moduli | proved | - | author@bi | sketch |
| 43 | lem:covering-moduli-proper | paper:lem:covering-moduli-proper | proved | defn:covering-moduli, rmk:nonempty-marking, defn:systole, lem:thick-part-compact | author@bi | sketch |
| 44 | lem:marking-full-preimage | paper:lem:marking-full-preimage | proved | defn:compatible, defn:covering-moduli, rmk:nonempty-marking, prop:relative-marking-compatible, lem:covering-moduli-proper, defn:forgetful-map, fact:forgetful-props, lem:periodic-inheritence | author@bi | sketch |
| 45 | lem:periodic-coimage | paper:lem:periodic-coimage | proved | defn:compatible, lem:marking-full-preimage, defn:covering-moduli, fact:forgetful-props | author@bi | sketch |
| 46 | prop:periodicity-invariance | paper:prop:periodicity-invariance | proved | lem:periodic-coimage, lem:periodic-inheritence, defn:covering-moduli, lem:covering-moduli-proper | author@bi | sketch |
| 47 | rmk:full-preimage-free | paper:rmk:full-preimage-free | proved | - | author@bi | sketch |
| 48 | rmk:aw-marked-periodic | paper:rmk:aw-marked-periodic | proved | - | author@bi | sketch |
| 49 | thm:torus-periodic-points | paper:thm:torus-periodic-points | proved | rmk:nonempty-marking, fact:forgetful-props | author@bi | sketch |
| 50 | ex:periodicity-coex | paper:ex:periodicity-coex | proved | - | author@bi | proved |
| 51 | cor:periodic-prim-relations | paper:cor:periodic-prim-relations | proved | - | author@bi | open |
| 52 | defn:relative-marking | paper:defn:relative-marking | proved | - | author@bi | missing |
| 53 | prop:relative-marking-compatible | paper:prop:relative-marking-compatible | proved | defn:relative-marking | author@bi | proved |
| 54 | lem:relative-marking-invariance | paper:lem:relative-marking-invariance | proved | prop:relative-marking-compatible, rmk:nonempty-marking, defn:flat-morphism, defn:relative-marking | author@bi | sketch |
| 55 | cor:relative-marking-invariance-preimage | paper:cor:relative-marking-invariance-preimage | proved | defn:flat-morphism, prop:relative-marking-compatible, defn:relative-marking | author@bi | proved |
| 56 | defn:corners | paper:defn:corners | proved | - | author@bi | missing |
| 57 | rmk:billiard-corners | paper:rmk:billiard-corners | proved | - | author@bi | sketch |
| 58 | lem:trans-auth-effect | paper:lem:trans-auth-effect | proved | - | author@bi | proved |
| 59 | prop:corners-finite | paper:prop:corners-finite | proved | defn:corners | author@bi | proved |
| 60 | lem:torus-corners-torsion | paper:lem:torus-corners-torsion | proved | defn:corners, defn:relative-marking, lem:relative-marking-invariance | author@bi | sketch |
| 61 | ex:torus-corners | paper:ex:torus-corners | proved | lem:torus-corners-torsion | author@bi | sketch |
| 62 | defn:entangled | paper:defn:entangled | proved | - | author@bi | missing |
| 63 | defn:saturated-marking | paper:defn:saturated-marking | proved | defn:periodic-points | author@bi | missing |
| 64 | rmk:saturation-vs-symmetry | paper:rmk:saturation-vs-symmetry | proved | - | author@bi | sketch |
| 65 | defn:slope | paper:defn:slope | proved | - | author@bi | missing |
| 66 | rmk:slope-values | paper:rmk:slope-values | proved | - | author@bi | proved |
| 67 | fact:aw-slope-pm-one | paper:fact:aw-slope-pm-one | proved | - | author@bi | proved |
| 68 | rmk:slope-values-resolvable | paper:rmk:slope-values-resolvable | proved | - | author@bi | proved |
| 69 | rmk:slope-values-torus | paper:rmk:slope-values-torus | proved | - | author@bi | sketch |
| 70 | ex:translation-orbit-marking | paper:ex:translation-orbit-marking | proved | - | author@bi | sketch |
| 71 | fact:aw-closed-markings | paper:fact:aw-closed-markings | proved | - | author@bi | proved |
| 72 | prop:saturated-markings-coverings | paper:prop:saturated-markings-coverings | proved | defn:saturated-marking, fact:aw-slope-pm-one | author@bi | sketch |
| 73 | defn:cylinder-monodromy | paper:defn:cylinder-monodromy | proved | - | author@bi | missing |
| 74 | fact:S-normal-symmetric | paper:fact:S-normal-symmetric | proved | - | author@bi | sketch |
| 75 | prop:blocking-monodromy | paper:prop:blocking-monodromy | proved | - | author@bi | sketch |
| 76 | defn:primitive-holonomy | paper:defn:primitive-holonomy | proved | - | author@bi | missing |
| 77 | lem:primitive-coset-existence | paper:lem:primitive-coset-existence | proved | - | author@bi | sketch |
| 78 | lem:primitive-purity | paper:lem:primitive-purity | proved | - | author@bi | sketch |
| 79 | prop:fiber-disjoint-trajectory | paper:prop:fiber-disjoint-trajectory | proved | lem:primitive-coset-existence, lem:primitive-purity | author@bi | sketch |
| 80 | rmk:apisa-wright-reduction | paper:rmk:apisa-wright-reduction | proved | - | author@bi | sketch |
| 81 | cor:slope-minus-one | paper:cor:slope-minus-one | proved | rmk:apisa-wright-reduction, prop:fiber-disjoint-trajectory, fact:aw-slope-pm-one | author@bi | sketch |
| 82 | prop:tc-class | paper:prop:tc-class | proved | - | author@bi | proved |
| 83 | defn:arithmetic | paper:defn:arithmetic | proved | - | author@bi | missing |
| 84 | prop:cornered-arithmetic | paper:prop:cornered-arithmetic | proved | rmk:nonempty-marking, defn:relative-marking, lem:torus-corners-torsion, defn:corners, defn:arithmetic | author@bi | sketch |
| 85 | rmk:cornered-arithmetic-ds | paper:rmk:cornered-arithmetic-ds | proved | - | author@bi | sketch |
| 86 | ex:branched-double-cover | paper:ex:branched-double-cover | proved | defn:corners, prop:cornered-arithmetic, lem:torus-corners-torsion | author@bi | sketch |
| 87 | cor:arithmetic-k-diff | paper:cor:arithmetic-k-diff | proved | - | author@bi | sketch |
| 88 | cor:parking-garage-classification | paper:cor:parking-garage-classification | proved | defn:billiard-pathologies | author@bi | sketch |
| 89 | conj:arith-relative-marking | paper:conj:arith-relative-marking | conjectured | - | author@bi | conjectured |
| 90 | cor:arith-slope-pm-one | paper:cor:arith-slope-pm-one | conjectured | - | author@bi | conjectured |
| 91 | cor:arith-relative-position | paper:cor:arith-relative-position | conjectured | defn:relative-marking | author@bi | conjectured |
| 92 | thm:arith-slope-constraint | paper:thm:arith-slope-constraint | conjectured | - | author@bi | conjectured |
| 93 | cor:arith-billiard-finite | paper:cor:arith-billiard-finite | conjectured | - | author@bi | conjectured |
| 94 | cor:arith-k-diff-finite | paper:cor:arith-k-diff-finite | conjectured | - | author@bi | conjectured |
| 95 | lem:illumination-chase | paper:lem:illumination-chase | proved | - | author@bi | proved |
| 96 | lem:tokarsky-target | paper:lem:tokarsky-target | conjectured | - | author@bi | conjectured |
| 97 | conj:torus-cover-tokarsky | paper:conj:torus-cover-tokarsky | conjectured | - | author@bi | conjectured |
| 98 | conj:unfolding-characterization | paper:conj:unfolding-characterization | conjectured | - | author@bi | conjectured |
| 99 | prop:prim-polygon | paper:prop:prim-polygon | proved | thm:primitive-construction | author@bi | missing |
| 100 | rmk:best-converse | paper:rmk:best-converse | proved | - | author@bi | proved |
| 101 | defn:lts | paper:defn:lts | proved | - | author@bi | missing |
| 102 | defn:lts-properties | paper:defn:lts-properties | proved | - | author@bi | missing |
| 103 | defn:bisimulation | paper:defn:bisimulation | proved | - | author@bi | missing |
| 104 | defn:zigzag | paper:defn:zigzag | proved | - | author@bi | missing |
| 105 | defn:schreier-graph | paper:defn:schreier-graph | proved | - | author@bi | missing |
| 106 | thm:schreier-lts-bijection | paper:thm:schreier-lts-bijection | proved | - | author@bi | sketch |
| 107 | defn:equivariant-covering | paper:defn:equivariant-covering | proved | - | author@bi | missing |
| 108 | fact:equivariant-is-zigzag | paper:fact:equivariant-is-zigzag | proved | - | author@bi | sketch |
| 109 | fact:polygonal-ds-properties | paper:fact:polygonal-ds-properties | proved | - | author@bi | sketch |
| 110 | ex:ppsg | paper:ex:ppsg | proved | defn:delaunay | author@bi | proved |
| 111 | thm:polygonal-ds-bijection | paper:thm:polygonal-ds-bijection | proved | - | author@bi | sketch |
| 112 | fact:barycentric-ds-properties | paper:fact:barycentric-ds-properties | proved | - | author@bi | sketch |
| 113 | ex:bary-delaunay | paper:ex:bary-delaunay | proved | - | author@bi | proved |
| 114 | thm:barycentric-ds-bijection | paper:thm:barycentric-ds-bijection | proved | defn:flat-morphism | author@bi | sketch |
| 115 | thm:moeller-primitive | paper:thm:moeller-primitive | proved | - | author@bi | proved |
| 116 | thm:primitive-construction | paper:thm:primitive-construction | proved | - | author@bi | sketch |
| 117 | thm:primitive-G-structure | paper:thm:primitive-G-structure | proved | - | author@bi | sketch |
| 118 | lem:tok | paper:lem:tok | proved | - | author@bi | proved |
| 119 | lem:involution-blocking | paper:lem:involution-blocking | proved | - | author@bi | sketch |
| 120 | cor:tokarsky-corners | paper:cor:tokarsky-corners | proved | - | author@bi | sketch |
| 121 | lem:tokarsky-descends | paper:lem:tokarsky-descends | proved | - | author@bi | sketch |
| 122 | prop:vorobets-veech-inclusion | paper:prop:vorobets-veech-inclusion | proved | - | author@bi | proved |
| 123 | fact:positive-systole | paper:fact:positive-systole | proved | - | author@bi | proved |
| 124 | lem:saddle-homotopy | paper:lem:saddle-homotopy | proved | - | author@bi | proved |
| 125 | cor:short-path-geodesic | paper:cor:short-path-geodesic | proved | lem:saddle-homotopy | author@bi | proved |
| 126 | lem:straightline-invariance | paper:lem:straightline-invariance | proved | cor:short-path-geodesic | author@bi | proved |
| 127 | prop:Voronoi-invariance | paper:prop:Voronoi-invariance | proved | lem:straightline-invariance | author@bi | proved |
| 128 | cor:voronoi-permutation | paper:cor:voronoi-permutation | proved | - | author@bi | sketch |
| 129 | defn:delaunay | paper:defn:delaunay | proved | - | author@bi | sketch |
| 130 | prop:delaunay-isometry-permutation | paper:prop:delaunay-isometry-permutation | proved | - | author@bi | proved |
| 131 | cor:db-faith | paper:cor:db-faith | proved | - | author@bi | sketch |
| 132 | prop:delaunay-invariance | paper:prop:delaunay-invariance | proved | defn:delaunay, defn:flat-morphism | author@bi | sketch |
| 133 | defn:systole | paper:defn:systole | proved | - | author@bi | missing |
| 134 | lem:thick-part-compact | paper:lem:thick-part-compact | proved | defn:covering-moduli, rmk:nonempty-marking, defn:delaunay, lem:saddle-homotopy | author@bi | sketch |
| 135 | defn:null-holonomy | paper:defn:null-holonomy | proved | - | author@bi | missing |
| 136 | defn:maximal-torus | paper:defn:maximal-torus | proved | - | author@bi | missing |
| 137 | lem:null-holonomy-tori | paper:lem:null-holonomy-tori | proved | defn:compatible, defn:relative-marking, defn:maximal-torus | author@bi | sketch |
| 138 | prop:reduced-torus-covering | paper:prop:reduced-torus-covering | proved | - | author@bi | sketch |
| 139 | prop:reduced-torus-compatible | paper:prop:reduced-torus-compatible | proved | prop:reduced-torus-covering, defn:compatible, prop:relative-marking-compatible | author@bi | sketch |
| 140 | prop:reduced-torus-balanced | paper:prop:reduced-torus-balanced | proved | prop:reduced-torus-covering, lem:null-holonomy-tori, prop:reduced-torus-compatible | author@bi | sketch |
| 141 | ex:reduced-torus-32 | paper:ex:reduced-torus-32 | proved | prop:reduced-torus-covering | author@bi | sketch |
| 142 | ex:reduced-torus-16 | paper:ex:reduced-torus-16 | proved | ex:reduced-torus-32, lem:null-holonomy-tori, prop:reduced-torus-balanced | author@bi | sketch |
