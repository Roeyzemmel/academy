---
id: "module-sage_record"
status: "written"
family: "none — record machinery for the cyclic-cover sweeps E2a/b/c"
script: "fslab/christoffel/sage_record.py (new); tests/test_christoffel.py, tests/test_christoffel_sage.py"
class_short: "not a search. The tests use only the EW (two labellings), the 2×1 rectangle, the Ornithorynque and M_4(1,1,1,1). Structurally cannot show: sage_invariants' cost"
source: "computation/runs.md:23 (HEAD 2026-09-24)"
---

## Row (verbatim)

| Item | Family | Script (FlatSurfLab) | Job id | Class / bound | Status | Outcome |
|---|---|---|---|---|---|---|
| new module `fslab/christoffel/sage_record.py`, the Sage-facing half of a record: `sage_invariants`, `crosscheck`, `block_systems` (via `gapinv.all_blocks`), `element_cycle_types` (pure), `structural_checks` (families.md's U structural expectations), `cyclic_group_order_bound` (pure); 7 pure tests (`SageRecordPure`) and 7 Sage tests (`SageRecordAgainstSurfaceDynamics`, `SageRecordBlockSystems`) | none — record machinery for the cyclic-cover sweeps E2a/b/c | `fslab/christoffel/sage_record.py` (new); `tests/test_christoffel.py`, `tests/test_christoffel_sage.py` | — | not a search. The tests use only the EW (two labellings), the 2×1 rectangle, the Ornithorynque and M_4(1,1,1,1). **Structurally cannot show**: `sage_invariants`' cost at 40 squares, or that the structural expectations hold beyond $N=6$ | written | — |

The shared notes for this row are in [module-budget-conjtest](module-budget-conjtest.md).
