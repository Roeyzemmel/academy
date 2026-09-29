#!/usr/bin/env python3
"""Periodic-point growth on the maximal torus of four square-tiled torus covers.

Kind:           measure
Claims:         lab:torus-periodic-growth-standard
Goal:           on the maximal torus T(X) = R^2/L(X) (defn:maximal-torus,
                sections/appendix_null_holonomy.tex) marked at F = tau_X(Sigma_X),
                measure (1) |S_v| against the formula (sum_k v_k)^2 of
                thm:torus-periodic-points item 1 (sections/markings.tex), for every v
                in the box, and (2) the truncated periodic set |union S_v| as the box
                grows, to see growth rather than a plateau on torus covers. Context:
                PaperHome Tier 4 issue 5 (Drafts/comment_roadmap.md), Roey's
                question at sections/slope_blocking.tex:27 on AW21 Lemma 2.13 (bears on
                paper:thm:torus-periodic-points and paper:rmk:slope-values).
Class:          four square-tiled torus covers, built in fslab.pslit_covers:
                - the square torus R^2/Z^2 (1 square), marked at one basepoint (0,0)
                  (no cone point; rmk:nonempty-marking's single-point case), n = |F| = 1;
                - the unfolding of the square billiard table, the 2x2 torus
                  R^2/(2Z)^2 (4 squares), marked at its 4 corner images (the lattice
                  points of the 4 squares), n = 4; any rectangle's unfolding is this
                  one up to a diagonal linear map, which the L(X)-coordinates absorb;
                - the 3-square L in H(2), marked at its one zero, n = 1;
                - the Eierlegende Wollmilchsau, marked at its 4 zeros.
                v runs over Z^n with sum_k v_k > 0 and |v_k| <= R, R = 1..6 (--bound).
                NOT covered: the double pentagon (its coordinates are irrational and
                fslab.ptranslation takes Fraction scalars only, so it is not built at
                all; its finiteness is thm:aw-finiteness, cited to AW21, not
                recomputed); P(X) itself, as opposed to P(T(X), F); irrational marks
                (s_v_points refuses them); torus covers that are not square-tiled;
                R > 6.
Quantity:       per X, exactly (Fraction arithmetic): stratum; L(X); area of T(X);
                |Trans(T(X))|; F in L(X)-coordinates; for every v in the R = --bound
                box, |S_v| from fslab.torus_periodic.s_v_points, checked here to be
                (sum v_k)^2 DISTINCT points of [0,1)^2 each solving
                sum_k v_k p = sum_k v_k x_k mod Z^2 (the right side recomputed here, not
                taken from the module); for |v_k| <= --brute-bound, also that S_v is ALL
                the solutions, by brute force over the grid (1/D)Z^2, D = N * den(rhs).
                Any mismatch aborts the run. Recorded per N = sum v_k: the formula N^2,
                the sizes observed, the number of v. Then the cumulative count
                |union S_v, |v_k| <= R| for R = 1..--bound, computed twice (an
                incremental union here and fslab.torus_periodic.periodic_points_growth;
                a disagreement aborts), and whether it is strictly increasing.
Validation:     R^2/Z^2 marked at (0,0), through the same pipeline (pslit_covers.torus,
                null_holonomy.maximal_torus, ptranslation.solve_basis): the growth at
                R = 1, 2, 3 must be [1, 4, 12] (hand count: S_1 = {0}; S_2 = (1/2)Z^2,
                4 points; S_3 adds (1/3)Z^2, meeting the rest only at 0, 4 + 9 - 1 = 12),
                and every S_v there must pass the per-v check. The old refuting outcome
                "maximal_torus must refuse a non-torus-cover" is a code check, now
                tests/test_null_holonomy.py (NotATorusCoverRefused, pure Python, with a
                stub surface: every closed surface with Fraction coordinates is a torus
                cover, so the module cannot build a real one).
Needs Sage:     no (fslab.ptranslation / pslit_covers / null_holonomy / torus_periodic
                are pure Python, exact Fractions; runs through the queue like any
                experiment). These modules are due to be retired in C3
                (docs/code-audit.md); this script runs once at the current commit
                before that, and its JSON is the C3 regression target.

Result:         Measured at commit a929eca (job 20260924-175705, lingo, dirty false,
                exit 0; pure Python). Validation passed. |S_v| = (sum v_k)^2 on every v
                checked (13546 per 4-mark example, 6 per 1-mark example), and S_v is all
                solutions on every v with |v_k| <= 2 (270 / 2 by brute force); no
                mismatch. Growth |union S_v| for R = 1..6: square torus and 3-square L
                1, 4, 12, 24, 48, 72; 2x2 torus and EW 48, 480, 1728, 4128, 8352, 14592;
                strictly increasing on all four. The pairs agree because the quantity
                lives on (T(X), F): square torus and L both give (R^2/Z^2, {0}), 2x2
                torus and EW both give (R^2/2Z^2, the 2-torsion points in L-coords), so
                the class holds 2 distinct marked tori, not 4. No plateau below R = 6
                over these 2; nothing about P(X) itself, irrational marks, or
                non-square-tiled covers.
"""

# Test fixture: the module docstring (header) of SciLab's
# experiments/2026-09-24_torus_cover_periodic_growth.py, copied 2026-09-28; the body is omitted.
