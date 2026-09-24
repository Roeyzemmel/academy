---
name: verify-result
description: Audit a computed result before it becomes a claim — two independent flatsurf:result-auditor runs over the script and its result JSON, asking whether the check is a shadow of the claim, whether the stratum and the bound are what they should be, and what the search class structurally could not have contained. Records both verdicts in FlatSurfLab's results/audits.md and has claim-keeper update the lab claim. Use on any result about to be cited, on a surprising result, and before a result is handed to the paper repo.
---

# Audit a result before it becomes a claim

`$ARGUMENTS` names the result: a `results/*.json` stem, an experiment script, or the
claim it is about to support.

Read `.claude/flatsurf.json` first. If its `settle` names a repo pass other than this
one (Slope1: `/settle`, which adds refutation verifiers), run that instead and stop.
Paths below are in `lab` (FlatSurfLab).

A result that agrees with what you hoped is the dangerous kind. Do not silence a
surprising result either: **a surprising result is a bug until shown otherwise** —
stratum mismatch, squared-versus-linear bound, libflatsurf's doubled cylinder area.
This pass is where that suspicion gets spent.

## Why two runs

One adversarial read is not a sign-off. The same model, the same script, a different
run, a different verdict — self-inconsistency in this kind of checking is measured in
the tens of percent. So this pass dispatches **two independent
`flatsurf:result-auditor` agents** that do not see each other's findings, and the
result is cleared only if both clear it. Disagreement is not averaged; it is reported
as unresolved, and the result stays uncited until it is settled.

## The pass

1. **Gather.** The result JSON, the script, its header, and the claim it supports —
   the lab claim (`<registry.cmd> show lab:<name>`) and what it `bears_on` (a `paper:`
   label in BilliardIllumination, an `s1:` id in Slope1). An auditor that cannot find
   the claim audits the script against its own header and says so.
2. **Dispatch two `flatsurf:result-auditor` agents**, in one message so they run
   concurrently, each with the same brief and no knowledge of the other. Both on a
   primary model (Fable 5.1 or Opus 5.5).
3. **Compare verdicts.**

   | Verdict | Meaning |
   |---|---|
   | `SOUND` | the computation checks what the header says, within the class it names |
   | `SOUND MODULO` | sound given a stated assumption the auditor could not check |
   | `GAP` | the check does not establish what it claims, and here is what it misses |
   | `BROKEN` | a concrete defect: wrong stratum, wrong bound, wrong object |

   Both `SOUND` → cleared. Anything else, or any disagreement → not cleared.
4. **Record both verdicts** in FlatSurfLab's `results/audits.md`, dated, naming the
   result, both verdicts verbatim, and the decision.
5. **Update the claim** through `flatsurf:claim-keeper`: the audit state on the
   experiment's evidence line, and a status change only on a clearance.
6. **Report** what is cleared for citation and what is not, and for anything not
   cleared, the single next action.

The questions the auditors ask are in `agents/result-auditor.md` and
`references/sage-review.md`.

## Closing

A cleared result is quotable as "no counterexample below bound *B* over class *C*",
with the class's exclusions stated. It is never quotable as "true". Nothing here
proves anything; it establishes that a search did what it said it did.
