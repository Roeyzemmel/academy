---
name: settle
description: 'Settle a returned result reporting candidate counterexamples: review the script, independently re-derive each candidate (at most three) via Scientist and Expert verify, apply the decision table. Use on every search result that reports a counterexample.'
---

# Settle a result with candidates

`$ARGUMENTS` is the lab claim id (or the report packet or ticket naming it). The decision
table is in `settle.py`'s docstring. A result that hands you a counterexample to a question
the notebook has been circling is the most dangerous kind: nothing is recorded until it
clears.

Three calls of `${CLAUDE_PLUGIN_ROOT}/workflows/review-experiment.js` (the Workflow tool, `args: {subject: "lab:<id>", ticket, report, candidates: "<home>/.academy/settle-<id>.json", mode}`),
each a later run than the one before; nothing waits in a loop. The inbox runs the first
itself when a review finds candidates. The order is code (2026-10-31; docs/workflows.md):

1. **`settle-audit`**: the script audit, the experiment-review pair. The clerk writes the
   candidates file (`name`, `rank` by likelihood with 1 first, `ref`, `detail` verbatim)
   and runs `settle.py plan`. Only if the audit cleared, `lead-researcher` (the researcher
   -> scientist liaison) files one re-derivation ticket per candidate, at most three. Each
   is a `verify`-kind experiment that rebuilds the decisive data by a route the pipeline
   did not use, on small cases. The reviewers cannot compute, so this is the independent
   re-derivation. The script reads each ticket back and records it in the file.
2. **`settle-review`**: for each candidate whose re-derivation came back, and only those,
   `lead-researcher` files a `verify` ticket to the Expert in refutation mode. The order of
   the review: the completeness of the enumeration first, then the re-derivation report
   (it must exist, use another route and agree), then the witnesses. Pass
   `checklist: "<paths.verifyChecklist>"` when the home has one; the ticket names it.
3. **`settle-conclude`**, with `verdicts`: per candidate, `run`, `verdict`, the exact
   `model`, `run_id` and `packet`. `settle.py decide` and `record` run; only the
   `recordable` candidates reach `claim-keeper`.

**Report** what is cleared for citation and what is not, and for anything not cleared the
single next action. A cleared refutation is quotable with the member, the certificate and
the verdicts. A cleared negative search is quotable only as "no counterexample over class
C". Computation refutes; it never proves.
