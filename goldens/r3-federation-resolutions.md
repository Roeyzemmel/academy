# R3: new resolutions from federation through profiles

Generated 2026-09-28 (academy/registry, Group D). Old: FlatSurfLab's claims.py at 49c9072 (a regex, `kb_index`, over Slope1's claims/, assumptions/, examples/). New: the fsl-claims profile resolving `s1:` ids by loading Slope1 through the s1-kb profile (`registry/core/federation.py`).

## On the real registries

The lab and paper registries hold 25 distinct link targets, 2 of them into `s1:` (`s1:CEX-1` and `s1:Q2`, both Disproved, linked from the lab). Both resolve as before. The only change is the status word `foreign()` returns: Slope1's own (`Disproved`) instead of the old special case (`refuted`). It shows only in `claims.py show s1:<id>` run from the lab (`(ok: Disproved)` instead of `(ok: refuted)`). The depends_on warning uses the projection class and still reads "which is refuted". `check` output on all three registries is byte-identical to the goldens.

## Every s1 id and old label, old vs new (probe)

All 375 Slope1 ids (every entity type, the ledgers included) and old labels (`aliases`, and `old` of assumptions) were resolved as `s1:<name>` both ways. 72 differ in their resolution or in whether `check` lets the id through to resolution at all, in four groups: ledger ids (verdicts, runs, specs) now resolve; old labels the regex did not index (the `old` field of assumptions) now get the "old Slope1 label; the kb id is ..." hint instead of "no such id"; ids with non-ASCII characters (`GA-2T′`, `GA-CT′`, primed old labels) are no longer rejected by the lab's ASCII id rule before resolution (ids with spaces still are); and the Disproved word above. Nothing that resolved before stops resolving.

| name | old | new | reaches resolution in `check`: old / new |
|---|---|---|---|
| `(2T)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(2T)` is an old Slope1 label; the kb id is `s1:GA-2T` | no ("not a claim in the registry") / yes |
| `(2T′)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(2T′)` is an old Slope1 label; the kb id is `s1:GA-2T′` | no ("not a claim in the registry") / yes |
| `(A0)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(A0)` is an old Slope1 label; the kb id is `s1:OA-0` | no ("not a claim in the registry") / yes |
| `(A1)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(A1)` is an old Slope1 label; the kb id is `s1:OA-1` | no ("not a claim in the registry") / yes |
| `(A2)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(A2)` is an old Slope1 label; the kb id is `s1:OA-2` | no ("not a claim in the registry") / yes |
| `(A3)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(A3)` is an old Slope1 label; the kb id is `s1:OA-3` | no ("not a claim in the registry") / yes |
| `(A4)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(A4)` is an old Slope1 label; the kb id is `s1:PA-4` | no ("not a claim in the registry") / yes |
| `(A5)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(A5)` is an old Slope1 label; the kb id is `s1:PA-5w` | no ("not a claim in the registry") / yes |
| `(A6)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(A6)` is an old Slope1 label; the kb id is `s1:PA-6` | no ("not a claim in the registry") / yes |
| `(A7)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(A7)` is an old Slope1 label; the kb id is `s1:PA-7` | no ("not a claim in the registry") / yes |
| `(CT)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(CT)` is an old Slope1 label; the kb id is `s1:GA-CT` | no ("not a claim in the registry") / yes |
| `(CT′)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(CT′)` is an old Slope1 label; the kb id is `s1:GA-CT′` | no ("not a claim in the registry") / yes |
| `(D0)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(D0)` is an old Slope1 label; the kb id is `s1:GA-D0` | no ("not a claim in the registry") / yes |
| `(EP)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(EP)` is an old Slope1 label; the kb id is `s1:GA-EP` | no ("not a claim in the registry") / yes |
| `(HA)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(HA)` is an old Slope1 label; the kb id is `s1:GA-HA` | no ("not a claim in the registry") / yes |
| `(Q1)` | missing: `(Q1)` is an old Slope1 label; the kb id is `s1:Q1` | missing: `(Q1)` is an old Slope1 label; the kb id is `s1:Q1` | no ("not a claim in the registry") / yes |
| `(Q2)` | missing: `(Q2)` is an old Slope1 label; the kb id is `s1:Q2` | missing: `(Q2)` is an old Slope1 label; the kb id is `s1:Q2` | no ("not a claim in the registry") / yes |
| `(RD), (RD4), (RD5), (RD6), (RD7)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(RD), (RD4), (RD5), (RD6), (RD7)` is an old Slope1 label; the kb id is `s1:GA-RD` | no ("not a claim in the registry") / no ("not a claim in the registry") |
| `(SC)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `(SC)` is an old Slope1 label; the kb id is `s1:PA-SC` | no ("not a claim in the registry") / yes |
| `2026-09-20_N6` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-20_regression-8ceb09d` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-21_gap_reverify-cadef3e` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-21_regression-cadef3e` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-22_N1` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-22_gap_reverify-c571b7d` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-22_regression-c571b7d` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-22_regression-ff6e36f` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-23_E1-ew_ornithorynque_record` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-23_E2a-cyclic_covers_a` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-23_E2b-cyclic_covers_b` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-23_N8-certificate-N9` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-23_W1-W4-N10-N11` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-23_refutation-M12-1335` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-23_refutation-M12-15711` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_G1-N12-first` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_G1-N12-redecided` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_G10-N24` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_G2-G4-G5-N13-N15-N16` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_G3-N14` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_G7-N21` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_G8-N22` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_G9-N23` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_GEO-31` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_GEO-32` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_M2-M5-N17-N20` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_M2-M5-runA-not-cleared` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `2026-09-24_OPEN-10-attestation` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `BOUND-1` | ok: refuted | ok: Disproved | yes / yes |
| `CEX-1` | ok: refuted | ok: Disproved | yes / yes |
| `CyclicCover([1,1,1,1])` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `CyclicCover([1,1,1,1])` is an old Slope1 label; the kb id is `s1:EX-M4-1111` | no ("not a claim in the registry") / yes |
| `CyclicCover([1,3,3,5], M=12)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `CyclicCover([1,3,3,5], M=12)` is an old Slope1 label; the kb id is `s1:EX-M12-1335` | no ("not a claim in the registry") / no ("not a claim in the registry") |
| `CyclicCover([1,5,7,11], M=12)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `CyclicCover([1,5,7,11], M=12)` is an old Slope1 label; the kb id is `s1:EX-M12-15711` | no ("not a claim in the registry") / no ("not a claim in the registry") |
| `E1` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `E2a` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `E2b` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `GA-2T′` | ok: - | ok: - | no ("not a claim in the registry") / yes |
| `GA-CT′` | ok: - | ok: - | no ("not a claim in the registry") / yes |
| `M_12(1,3,3,5)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `M_12(1,3,3,5)` is an old Slope1 label; the kb id is `s1:EX-M12-1335` | no ("not a claim in the registry") / yes |
| `M_12(1,5,7,11)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `M_12(1,5,7,11)` is an old Slope1 label; the kb id is `s1:EX-M12-15711` | no ("not a claim in the registry") / yes |
| `M_4(1,1,1,1)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `M_4(1,1,1,1)` is an old Slope1 label; the kb id is `s1:EX-M4-1111` | no ("not a claim in the registry") / yes |
| `M_6(1,1,1,3)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `M_6(1,1,1,3)` is an old Slope1 label; the kb id is `s1:EX-ORN` | no ("not a claim in the registry") / yes |
| `O_16^a` | missing: `O_16^a` is an old Slope1 label; the kb id is `s1:EX-O16a` | missing: `O_16^a` is an old Slope1 label; the kb id is `s1:EX-O16a` | no ("not a claim in the registry") / yes |
| `O_16^b` | missing: `O_16^b` is an old Slope1 label; the kb id is `s1:EX-O16b` | missing: `O_16^b` is an old Slope1 label; the kb id is `s1:EX-O16b` | no ("not a claim in the registry") / yes |
| `O_16^c` | missing: `O_16^c` is an old Slope1 label; the kb id is `s1:EX-O16c` | missing: `O_16^c` is an old Slope1 label; the kb id is `s1:EX-O16c` | no ("not a claim in the registry") / yes |
| `Q1` | ok: refuted | ok: Disproved | yes / yes |
| `Q2` | ok: refuted | ok: Disproved | yes / yes |
| `W2′` | missing: `W2′` is an old Slope1 label; the kb id is `s1:GEO-23` | missing: `W2′` is an old Slope1 label; the kb id is `s1:GEO-23` | no ("not a claim in the registry") / yes |
| `gap_reverify` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `module-budget-conjtest` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `module-sage_record` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `regression` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | ok: - | yes / yes |
| `— (new 2026-09-24)` | missing: no such id in Slope1's kb (py tools/kb.py resolve <text>) | missing: `— (new 2026-09-24)` is an old Slope1 label; the kb id is `s1:PA-5` | no ("not a claim in the registry") / no ("not a claim in the registry") |
