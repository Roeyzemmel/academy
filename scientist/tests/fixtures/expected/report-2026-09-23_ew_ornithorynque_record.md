## Summary

Verify experiment `2026-09-23_ew_ornithorynque_record` on lab:q2-ew-ornithorynque, s1:Q2: holds.
Conclusion: supports -- (Q2) holds with K_min = 2 on the three labelled records (EW, M_4(1,1,1,1), Ornithorynque), each decided by two routes (pure Python and GAP) that agree.
Proposed status: lab:q2-ew-ornithorynque -> supported, pending two experiment reviews.

## Produced

- Script `file:scientist@main/experiments/2026-09-23_ew_ornithorynque_record.py` (header `Kind: verify`).
- Result `file:scientist@main/results/2026-09-23_ew_ornithorynque_record.json`.
- Claims concerned: lab:q2-ew-ornithorynque, s1:Q2.

## Established vs assumed

- **Established:** (computation, not yet reviewed; proposed supported for lab:q2-ew-ornithorynque) supports -- (Q2) holds with K_min = 2 on the three labelled records (EW, M_4(1,1,1,1), Ornithorynque), each decided by two routes (pure Python and GAP) that agree.
- **Assumed:** the run on profile `lingo` at commit `a929eca` executed the script as written, and the validation case certifies the pipeline on this class.
- **Not established:** (Q2) at any other point of either Teichmüller curve, for any other origami, with fewer marked points, or anything about (Q1) or illumination.

## Evidence

- Result `file:scientist@main/results/2026-09-23_ew_ornithorynque_record.json`: outcome `holds`, commit `a929eca` (clean tree), run 2026-09-24T18:36:51.
- Validation case: reproduced (from the draft).
- The script's own Result field: Previous run (legacy format, before the verify header): No counterexample to (Q2) over class C at SciLab commit 34552b0 (job 20260923-123800, lingo, clean per-job worktree, dirty false, exit 0, Sage 10.7 / surface_dynamics 0.7.0, defaults). C: exactly three labelled records of two origamis, every square corner marked — EW = `EierlegendeWollmilchsau()` tuples (1,2,3,0,5,6,7,4)/(4,7,6,5,2,1,0,3); M_4(1,1,1,1) = `CyclicCover([1,1,1,1])` tuples (1,4,7,2,5,0,3,6)/(7,2,5,0,3,6,1,4), isomorphic to the EW; ORN = `CyclicCover([1,1,1,3])` tuples (1,8,7,2,5,0,11,6,9,4,3,10)/(7,6,5,0,11,10,9,4,3,2,1,8). W enumerated completely (raw BFS 24/24/648 states, |W| = 6/6/45). Every record closes at K_min = 2...

## Question

Does (Q2) [computation/spec.md §1] hold, with K_min = 2, on each of three labelled records of two named origamis, every square corner marked? (Q2): with W = {w(sigma^a, tau^b) : w Christoffel, a, b in {+-1}}, C = the union of u^G over u in W, C^pow = {c^k}, "is C^pow transitive off the diagonal?". The origamis: the Eierlegende Wollmilchsau (n = 8, G = Q_8, H(1,1,1,1), normal; families.md §1: "(Q2) is known true for it, with K = 2, by the covering test") and the Ornithorynque M_6(1,1,1,3) (n = 12, H_4(2^3)^even, not normal; families.md §2). Not covered: any other origami; any other point of either Teichmüller curve (N1 not used); fewer marked points; (Q1); illumination; parking-garage realisability ((A4)-(A6) are necessary flags only); the (2T')/(CT')/(D0) fields as verified facts.

Claims: lab:q2-ew-ornithorynque, s1:Q2.

## Class

One named object (see ## Object).

**Cannot contain:** any other origami; any other point of either Teichmüller curve (N1 not used); fewer marked points; (Q1); illumination; parking-garage realisability ((A4)-(A6) are necessary flags only); the (2T')/(CT')/(D0) fields as verified facts

## Method

Two routes. (1) Pure Python, fslab/christoffel: build_record / decide_q2 (conjugacy-deduplicated orbital BFS, N2, cross-checked on every record by the raw BFS), invariants (period lattice, centraliser, z-map), and for the normal records covering_test (R Prop. 5.7) on the complete raw W as a second, independent decision. (2) Sage / libgap: the surface_dynamics generators and their invariants (monodromy, automorphism group, lattice_of_absolute_periods, is_normal, stratum_component, veech_group, Lyapunov sum), gapinv.all_blocks for block systems, and gap_reverify.compare_with_python, which re-decides the same pairs in GAP. The pure-Python core is the deliberate second implementation of every invariant, not a duplicate. N-items touched: N2; N5 ((CT')(i),(ii), (D0), orbital meeting -- recorded as data only); N3 only as "necessary conditions passed" for the hypothesis level; N7 (the EW's (A4) commutator pass is the vacuous kind, single even length 2^4, flagged). Not used: N1 (no SL(2,Z)-orbit reduction), N4. N6 not touched.

Needs Sage: yes -- the generators, stratum_component, veech_group, Lyapunov sum, and libgap through gapinv / gap_reverify.

## Environment

- Profile: `lingo` (kind ssh, host lingo)
- Commit: `a929eca`
- Versions: python 3.12.14, sage 10.7, sage_flatsurf 0.8.0, surface_dynamics 0.7.0
- Platform: Linux-5.14.0-570.26.1.el9_6.x86_64-x86_64-with-glibc2.34
- Arguments: `[]`

## Validation

validate() RAISES, before any record is written, unless: the five tuple equalities of Object hold; CyclicCover([1,1,1,1]).is_isomorphic( EierlegendeWollmilchsau()) (api-recipes §6.7.3); and every Sage pin holds (recipes §6.7, §6.7.3; ORN |G|, |Z| from E0, cleared at ff6e36f) -- EW: 8 squares, H_3(1^4)^c, genus 3, veech index 1, Lyapunov sum 1, monodromy order 8, automorphism order 8, lattice_of_absolute_periods (2,0,2), is_normal True; M4_1111: the same except that stratum_component is not pinned; ORN: 12 squares, H_4(2^3)^even, genus 4, veech index 1, Lyapunov sum 1, monodromy order 108, automorphism order 3, is_normal False. Nothing else raises. RECORDED ONLY, never raised (a failure must reach the JSON): the pure-Python pins (incl. EW commutator type 2^4, ORN five orbitals), pure-vs-Sage disagreements, raw_agrees / normal_agrees false, Prop. 5.7 vs orbital verdict, compare_with_python DISAGREE, and EW-vs-M4_1111 invariant-field disagreements, in pipeline_failures; (Q2) TRUE with K_min = 2 per record, in e0_contradictions; families.md §2's U predictions for ORN (one block system of four blocks of size 3, three of two blocks of size 6, no 12-cycle, element cycle types {1^12, 1^6 3^2, 1^3 3^3, 2^6, 3^4, 6^2}), reproduced not input, in orn_u_predictions. Every recorded check except the U predictions also enters the outcome block as a property.

**Reproduced:** yes (from the draft).

## Object

Three labellings, one record each, no square index crossing between records (tuples 0-based r_tuple / u_tuple): - EW = surface_dynamics origamis.EierlegendeWollmilchsau(), r = (1,2,3,0,5,6,7,4), u = (4,7,6,5,2,1,0,3); asserted equal to families.ew_tuples(). - M4_1111 = M_4(1,1,1,1) = origamis.CyclicCover([1,1,1,1]), r = (1,4,7,2,5,0,3,6), u = (7,2,5,0,3,6,1,4); asserted equal to families.cyclic_cover((1,1,1,1)) and cyclic_cover_1111_tuples(), and isomorphic to the EW. - ORN = origamis.CyclicCover([1,1,1,3]), r = (1,8,7,2,5,0,11,6,9,4,3,10), u = (7,6,5,0,11,10,9,4,3,2,1,8); asserted equal to families.cyclic_cover((1,1,1,3)) and ornithorynque_tuples(). From the library construction, not from FMZ's printed tuples.

Objects in the outcome: `EW`, `M4_1111`, `ORN`.

## Check

Properties: Per record (EW, M4_1111, ORN), each a named entry of the outcome block: - (Q2) TRUE with K_min = 2 (the E0 row, spec §6.1 table, families.md §1); - W complete (no direction-size bound; the BFS over at most |G|^2 <= 11664 states is exhaustive); - raw BFS agrees with the conjugacy-deduplicated BFS; - GAP compare_with_python AGREE (UNDECIDED does not count); - for EW and M4_1111 only (normal): R Prop. 5.7 [notes/03-q2/normal-case.md], "for a normal origami, (Q2) iff every g in G \ {1} is conjugate to a power of a Christoffel value", holds on the complete W and normal_agrees is true; - pinned invariants: the pure-Python pins (EW / M4_1111: |G| = 8, |Z| = 8, Lambda = (2,0,2), normal, commutator type 2^4, seven orbitals; ORN: |G| = 108, |Z| = 3, not normal, five orbitals) and pure = Sage on |G|, |Z|, Lambda (absolute), normality, genus. Plus one cross-record property: EW and M4_1111 agree on every relabelling-invariant field (|G|, |Z|, Lambda, orbital count, commutator cycle type, stratum, verdict, K_min) and on the Sage stratum. A (Q2) FALSE on any record is printed with its construction, (r, u), |G|, the uncovered G-orbital's representative pair (i, j) with d(i,j) and z(i,j), |W| and the GAP status (for the EW records also the uncovered g in G \ {1} and its cycle type); it contradicts the cleared E0 row and is first read as a code fault.

| Property | Outcome |
|---|---|
| EW: (Q2) TRUE with K_min = 2 | holds |
| EW: W complete | holds |
| EW: raw BFS agrees | holds |
| EW: GAP compare_with_python AGREE | holds |
| EW: R Prop. 5.7 holds on the complete W, normal_agrees | holds |
| EW: pinned invariants (pure pins, pure = Sage) | holds |
| M4_1111: (Q2) TRUE with K_min = 2 | holds |
| M4_1111: W complete | holds |
| M4_1111: raw BFS agrees | holds |
| M4_1111: GAP compare_with_python AGREE | holds |
| M4_1111: R Prop. 5.7 holds on the complete W, normal_agrees | holds |
| M4_1111: pinned invariants (pure pins, pure = Sage) | holds |
| ORN: (Q2) TRUE with K_min = 2 | holds |
| ORN: W complete | holds |
| ORN: raw BFS agrees | holds |
| ORN: GAP compare_with_python AGREE | holds |
| ORN: pinned invariants (pure pins, pure = Sage) | holds |
| EW vs M4_1111: relabelling-invariant fields agree | holds |

Overall: `holds`, by 2 independent route(s).

## Raw outcome

- `kind`: `"verify"`
- `status`: `"holds"`
- `object`: `{"EW": {"construction": "surface_dynamics origamis.EierlegendeWollmilchsau() == families.ew_tuples()", "r": [1, 2, 3, 0, 5, 6, 7, 4], "u": [4, 7, 6, 5, 2, 1, 0, 3]}, "M4_1111": {"construction": "surface_dynamics origamis.CyclicCover([1,1,1,1]) == families.cyclic_cover((1,1,1,1))", "r": [1, 4, 7, ...`
- `properties`: `{"EW: (Q2) TRUE with K_min = 2": "holds", "EW: W complete": "holds", "EW: raw BFS agrees": "holds", "EW: GAP compare_with_python AGREE": "holds", "EW: R Prop. 5.7 holds on the complete W, normal_agrees": "holds", "EW: pinned invariants (pure pins, pure = Sage)": "holds", "M4_1111: (Q2) TRUE with ...`
- `routes`: `2`

Full block: `outcome` in `file:scientist@main/results/2026-09-23_ew_ornithorynque_record.json`.

## Conclusion

- **Establishes:** supports -- (Q2) holds with K_min = 2 on the three labelled records (EW, M_4(1,1,1,1), Ornithorynque), each decided by two routes (pure Python and GAP) that agree.
- **Does not establish:** (Q2) at any other point of either Teichmüller curve, for any other origami, with fewer marked points, or anything about (Q1) or illumination.
- **Proposed status:** lab:q2-ew-ornithorynque -> supported
- **Next step:** two experiment-reviewer runs; then consider an s1 generalization to the whole FMZ cyclic-cover family, falsifier first.

## Decisions needed

None.

## Machine notes

- experimenter: took the verify rerun of job 20260924-175705 as the run reported here; the earlier legacy-format run is mentioned only in the script's Result field.

## Decision
