---
id: "module-budget-conjtest"
status: "written"
family: "none — search machinery for the cyclic-cover sweeps E2a/b/c"
script: "fslab/christoffel/{values,decide,sweep,record,gapinv}.py, tests/test_christoffel.py (class BudgetAndConjTestPlumbing)"
class_short: "not a search. The tests use only EW, the 2×1 rectangle and the Ornithorynque. Structurally cannot show: how the budget behaves at |G|sim10^4, or that conj_test_"
source: "computation/runs.md:22, 368-391 (HEAD 2026-09-24)"
---

## Row (verbatim)

| Item | Family | Script (FlatSurfLab) | Job id | Class / bound | Status | Outcome |
|---|---|---|---|---|---|---|
| module work, no experiment: a wall-clock budget (`time_budget_s`) and an exact conjugacy test (`conj_test`) threaded through `values.complete_values` → `decide.decide_q2` → `sweep.build_record` → `sweep.run_members`; new `Record` fields `n_states`, `n_states_raw`, `W_size`, `stopped_by`, `decide_wall_s`, `structural_violations`, `s4_class`; `gapinv.representative_action_tuples`, `simultaneous_conjugator_gap` and `conj_test_factory` docstrings moved from UNCONFIRMED to "CONFIRMED (WSL; lingo pending)" against api-recipes.md §12.7.6 | none — search machinery for the cyclic-cover sweeps E2a/b/c | `fslab/christoffel/{values,decide,sweep,record,gapinv}.py`, `tests/test_christoffel.py` (class `BudgetAndConjTestPlumbing`) | — | not a search. The tests use only EW, the 2×1 rectangle and the Ornithorynque. **Structurally cannot show**: how the budget behaves at $\|G\|\sim10^4$, or that `conj_test_factory` is correct on lingo | written | — |

## Notes (verbatim)

**`christoffel_budget_conjtest_plumbing` and `christoffel_sage_record` rows.** Filed
2026-09-23 by `family-experimenter`, drained the same day. Neither has a queueable
`experiments/` wrapper, so — as with the `gap_reverify` module before its own wrapper was
written — each is filed as a table row with `Job id` "—" and elaborated here rather than in
the JSON-carrying half of the ledger. Evidence at filing time (local plus WSL Sage; **not
run on lingo**): for the plumbing entry, `py -m py_compile` on the five touched modules gave
`ok values`, `ok decide`, `ok sweep`, `ok record`, `ok gapinv`; `py -m unittest
tests.test_christoffel.BudgetAndConjTestPlumbing -v` → `Ran 9 tests in 0.251s` / `OK`; `py
tests\run_all.py` → `Ran 238 tests in 7.613s` / `OK (skipped=99)`; WSL Sage → `Ran 238 tests
in 11.412s` / `OK (skipped=1)`. For the `sage_record` entry, `py -m py_compile` on the three
touched files → `COMPILED`; `py -m unittest tests.test_christoffel.SageRecordPure -v` → `Ran
7 tests in 0.037s` / `OK`; `py tests\run_all.py` → `Ran 252 tests in 6.656s` / `OK
(skipped=106)`; WSL Sage → `Ran 252 tests in 10.242s` / `OK (skipped=1)`, every `SageRecord*`
test `... ok`. Pinpoint checked in this drain: the canonical `api-recipes.md` §12.7.6
"Addition: `conj_test_factory` / `simultaneous_conjugator_gap` (`fslab/christoffel/gapinv.py`)
— Confirmed against 12.6/12.7.2, WSL only, probed 2026-09-23 (api-check)" (line 2240,
confirmed present, read in this dispatch) — its own header already says "WSL only", which
matches the entry's "CONFIRMED (WSL; lingo pending)" wording exactly. **This is not yet a
lingo-cleared CONFIRMED under this project's stricter convention** (`.claude/rules/computation.md`:
CONFIRMED means executed in the target environment); nothing here promotes it further. The
U-prediction data quoted in the `sage_record` entry (element cycle types, block systems,
structural checks reproduced for the Ornithorynque and M_4(1,1,1,1)/M_6(1,1,1,3)) stay U —
they are WSL reproductions, not a lingo-cleared, stamped result, and carry no `Outcome` here.
