---
name: settle
description: 'Settle a returned result reporting candidate counterexamples: review the script, independently re-derive each candidate (at most three) via Scientist and Expert verify, apply the decision table. Use on every search result that reports a counterexample.'
---

# Settle a result with candidates

`$ARGUMENTS` is the lab claim id (or the report packet or ticket naming it). The
decision table is in `settle.py`'s docstring.

A result that hands you a counterexample to a question the notebook has been circling
is the most dangerous kind. Nothing is recorded until it clears.

## Run 1: the audit and the plan

Call the **Workflow** tool:

    scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/review-experiment.js
    args: {subject: "lab:<id>", ticket: "T-NNNN", report: "P-NNNN", mode: "settle-audit",
           candidates: "<scratchpad>/settle-<lab-id>.json"}

The script runs the experiment-review pair as `/researcher:review-experiment` does. Then
the clerk writes the candidates file (one entry per candidate: `name`, `rank` by
likelihood with 1 first, `ref`, and `detail` verbatim from the report) and runs
`settle.py plan`. Only if the audit cleared does the result carry `to_file`: at most
three candidates (capped by `budget.itemsPerRun`), the rest deferred.

File each entry as this main session, as the agent `main`, the liaison toward the
Scientist and the Expert (`prover` may not file to the Scientist):

- **Re-derivation (Scientist).** A `verify`-kind `experiment` ticket. It rebuilds the
  candidate's decisive data from its defining input alone, by a route the pipeline did
  not use, on small cases only. The reviewers cannot compute, so this run is the
  independent re-derivation.
- **Review (Expert)**, filed in a later run, once the re-derivation report is back. A
  `verify` ticket asking for the rigor-reviewer pair in refutation mode, in this order:
  the completeness of the enumeration, the re-derivation report (it must exist, use
  another route and agree), then the witnesses. When this home has a verification
  checklist (`paths.verifyChecklist`, default `.claude/rules/verification-checklist.md`),
  the ticket names that file.

Record the ticket ids in the candidates file. Nothing waits in a loop.

## Run 2: the decision

When the Expert's verification packets are back, run the same script with
`mode: "settle-conclude"`, the same `candidates` file, and `verdicts`: per candidate,
`run`, `verdict`, `model` (the exact id), `run_id` and `packet`. The clerk copies them in
and runs `settle.py decide` and `settle.py record` (`audits/<lab-id>/<date>-settle.md`,
never rewritten). Only the `recordable` candidates reach `claim-keeper`. A disagreement
is recorded as unresolved, and its weaker verdict's blocking step becomes the next
ticket.

## Report

What is cleared for citation and what is not, and for anything not cleared the single
next action. A cleared refutation is quotable with the member, the certificate and the
verdicts. A cleared negative search is quotable only as "no counterexample over class
C". Computation refutes; it never proves.
