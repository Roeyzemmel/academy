#!/usr/bin/env python3
"""Full (Q2) records for the Eierlegende Wollmilchsau and the Ornithorynque, two constructions each.

Kind:           verify
Claims:         lab:q2-ew-ornithorynque, s1:Q2
Goal:           Does (Q2) [computation/spec.md §1] hold, with K_min = 2, on each of three
                labelled records of two named origamis, every square corner marked? (Q2):
                with W = {w(sigma^a, tau^b) : w Christoffel, a, b in {+-1}}, C = the union
                of u^G over u in W, C^pow = {c^k}, "is C^pow transitive off the diagonal?".
                The origamis: the Eierlegende Wollmilchsau (n = 8, G = Q_8, H(1,1,1,1),
                normal; families.md §1: "(Q2) is known true for it, with K = 2, by the
                covering test") and the Ornithorynque M_6(1,1,1,3) (n = 12, H_4(2^3)^even,
                not normal; families.md §2). Not covered: any other origami; any other
                point of either Teichmüller curve (N1 not used); fewer marked points;
                (Q1); illumination; parking-garage realisability ((A4)-(A6) are necessary
                flags only); the (2T')/(CT')/(D0) fields as verified facts.
Object:         Three labellings, one record each, no square index crossing between
                records (tuples 0-based r_tuple / u_tuple):
                - EW = surface_dynamics origamis.EierlegendeWollmilchsau(), r =
                  (1,2,3,0,5,6,7,4), u = (4,7,6,5,2,1,0,3); asserted equal to
                  families.ew_tuples().
                - M4_1111 = M_4(1,1,1,1) = origamis.CyclicCover([1,1,1,1]), r =
                  (1,4,7,2,5,0,3,6), u = (7,2,5,0,3,6,1,4); asserted equal to
                  families.cyclic_cover((1,1,1,1)) and cyclic_cover_1111_tuples(), and
                  isomorphic to the EW.
                - ORN = origamis.CyclicCover([1,1,1,3]), r = (1,8,7,2,5,0,11,6,9,4,3,10),
                  u = (7,6,5,0,11,10,9,4,3,2,1,8); asserted equal to
                  families.cyclic_cover((1,1,1,3)) and ornithorynque_tuples(). From the
                  library construction, not from FMZ's printed tuples.
Properties:     Per record (EW, M4_1111, ORN), each a named entry of the outcome block:
                - (Q2) TRUE with K_min = 2 (the E0 row, spec §6.1 table, families.md §1);
                - W complete (no direction-size bound; the BFS over at most |G|^2 <= 11664
                  states is exhaustive);
                - raw BFS agrees with the conjugacy-deduplicated BFS;
                - GAP compare_with_python AGREE (UNDECIDED does not count);
                - for EW and M4_1111 only (normal): R Prop. 5.7
                  [notes/03-q2/normal-case.md], "for a normal origami, (Q2) iff every
                  g in G \\ {1} is conjugate to a power of a Christoffel value", holds on
                  the complete W and normal_agrees is true;
                - pinned invariants: the pure-Python pins (EW / M4_1111: |G| = 8, |Z| = 8,
                  Lambda = (2,0,2), normal, commutator type 2^4, seven orbitals; ORN:
                  |G| = 108, |Z| = 3, not normal, five orbitals) and pure = Sage on |G|,
                  |Z|, Lambda (absolute), normality, genus.
                Plus one cross-record property: EW and M4_1111 agree on every
                relabelling-invariant field (|G|, |Z|, Lambda, orbital count, commutator
                cycle type, stratum, verdict, K_min) and on the Sage stratum.
                A (Q2) FALSE on any record is printed with its construction, (r, u), |G|,
                the uncovered G-orbital's representative pair (i, j) with d(i,j) and
                z(i,j), |W| and the GAP status (for the EW records also the uncovered
                g in G \\ {1} and its cycle type); it contradicts the cleared E0 row and
                is first read as a code fault.
Method:         Two routes. (1) Pure Python, fslab/christoffel: build_record / decide_q2
                (conjugacy-deduplicated orbital BFS, N2, cross-checked on every record by
                the raw BFS), invariants (period lattice, centraliser, z-map), and for the
                normal records covering_test (R Prop. 5.7) on the complete raw W as a
                second, independent decision. (2) Sage / libgap: the surface_dynamics
                generators and their invariants (monodromy, automorphism group,
                lattice_of_absolute_periods, is_normal, stratum_component, veech_group,
                Lyapunov sum), gapinv.all_blocks for block systems, and
                gap_reverify.compare_with_python, which re-decides the same pairs in GAP.
                The pure-Python core is the deliberate second implementation of every
                invariant, not a duplicate. N-items touched: N2; N5 ((CT')(i),(ii),
                (D0), orbital meeting -- recorded as data only); N3 only as "necessary
                conditions passed" for the hypothesis level; N7 (the EW's (A4)
                commutator pass is the vacuous kind, single even length 2^4, flagged).
                Not used: N1 (no SL(2,Z)-orbit reduction), N4. N6 not touched.
Validation:     validate() RAISES, before any record is written, unless: the five tuple
                equalities of Object hold; CyclicCover([1,1,1,1]).is_isomorphic(
                EierlegendeWollmilchsau()) (api-recipes §6.7.3); and every Sage pin holds
                (recipes §6.7, §6.7.3; ORN |G|, |Z| from E0, cleared at ff6e36f) --
                EW: 8 squares, H_3(1^4)^c, genus 3, veech index 1, Lyapunov sum 1,
                monodromy order 8, automorphism order 8, lattice_of_absolute_periods
                (2,0,2), is_normal True; M4_1111: the same except that stratum_component
                is not pinned; ORN: 12 squares, H_4(2^3)^even, genus 4, veech index 1,
                Lyapunov sum 1, monodromy order 108, automorphism order 3, is_normal
                False. Nothing else raises. RECORDED ONLY, never raised (a failure must
                reach the JSON): the pure-Python pins (incl. EW commutator type 2^4, ORN
                five orbitals), pure-vs-Sage disagreements, raw_agrees / normal_agrees
                false, Prop. 5.7 vs orbital verdict, compare_with_python DISAGREE, and
                EW-vs-M4_1111 invariant-field disagreements, in pipeline_failures; (Q2)
                TRUE with K_min = 2 per record, in e0_contradictions; families.md §2's U
                predictions for ORN (one block system of four blocks of size 3, three
                of two blocks of size 6, no 12-cycle, element cycle types {1^12, 1^6 3^2,
                1^3 3^3, 2^6, 3^4, 6^2}), reproduced not input, in orn_u_predictions.
                Every recorded check except the U predictions also enters the outcome
                block as a property.
Needs Sage:     yes -- the generators, stratum_component, veech_group, Lyapunov sum, and
                libgap through gapinv / gap_reverify.

Result:         Previous run (legacy format, before the verify header):
                No counterexample to (Q2) over class C at FlatSurfLab commit 34552b0
                (job 20260923-123800, lingo, clean per-job worktree, dirty false, exit
                0, Sage 10.7 / surface_dynamics 0.7.0, defaults). C: exactly three
                labelled records of two origamis, every square corner marked — EW =
                `EierlegendeWollmilchsau()` tuples (1,2,3,0,5,6,7,4)/(4,7,6,5,2,1,0,3);
                M_4(1,1,1,1) = `CyclicCover([1,1,1,1])` tuples
                (1,4,7,2,5,0,3,6)/(7,2,5,0,3,6,1,4), isomorphic to the EW; ORN =
                `CyclicCover([1,1,1,3])` tuples
                (1,8,7,2,5,0,11,6,9,4,3,10)/(7,6,5,0,11,10,9,4,3,2,1,8). W enumerated
                completely (raw BFS 24/24/648 states, |W| = 6/6/45). Every record closes
                at K_min = 2 — coverage certificates on the given labelling.
                `pipeline_failures`, `e0_contradictions`, `candidates` all empty; GAP
                `compare_with_python` AGREE on all three; R Prop. 5.7 covering on the
                complete W holds on both EW records. Ornithorynque data, reproduced from
                the library construction (not from FMZ's printed tuples): |G| = 108, |Z|
                = 3, five orbitals, block systems {3:1, 6:3}, element cycle types {1^12,
                1^6 3^2, 1^3 3^3, 2^6, 3^4, 6^2}, no 12-cycle, H_4(2^3)^even, genus 4, Λ
                = 2Z², level (A3) with (A4)–(A6) as necessary flags only. C excludes:
                any other origami; any other point of either Teichmüller curve (N1 not
                used); fewer marked points; (Q1); illumination; parking-garage
                realisability; the (2T′)/(CT′)/(D0) fields as verified facts. Its
                refuting power beyond the cleared E0 row was on the pipeline, and no
                pipeline check fired.
                Verify rerun (job 20260924-175705, commit a929eca, lingo, dirty false,
                exit 0): all 18 properties hold. Reproduces the numbers above: K_min = 2
                on all three, raw BFS 24/24/648, |W| = 6/6/45, |G| = 8/8/108, ORN
                block systems and cycle types match the predictions, empty
                pipeline_failures / e0_contradictions / candidates. Same class C, same
                exclusions.
"""

# Test fixture: the module docstring (header) of FlatSurfLab's
# experiments/2026-09-23_ew_ornithorynque_record.py, copied 2026-09-28; the body is omitted.
