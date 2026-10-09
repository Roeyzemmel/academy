---
name: review-experiment
description: 'Review a computed result before it counts: two fresh experiment-reviewer runs (B only after a positive A), decision table by script. Use on review-experiment tickets and before a result is cited. Counterexample candidates: /researcher:settle.'
---

# Review an experiment

`$ARGUMENTS` is a ticket id (`T-NNNN`, kind `review-experiment`), a report packet
(`P-NNNN`) or a lab claim id. Run it from the Researcher home, in the main session.
Scripts: `$R`, `$A` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Budget and
independence: `academy/references/budget.md` and `roster-rules.md` (base plugin).

A result that agrees with what you hoped is the dangerous kind, and a surprising
result is a bug until shown otherwise. Why two runs: one adversarial read is not a
sign-off; the same model on the same script gives a different verdict often enough to
matter. Disagreement is reported, never averaged.

1. **Gather.** From the ticket (`$A/board.py show T-NNNN`) or packet
   (`$A/packets.py show P-NNNN`): the subject lab claim, the report packet, the result.
   If the report lists candidate counterexamples, stop and run `/researcher:settle`
   instead. Move the ticket `accepted`, then `in-progress`
   (`$A/board.py transition T-NNNN accepted --as <instance>`).
2. **Where the pair stands.** `py $R/reviews.py decide <lab-id>`. `need-A` or `need-B`
   says which run to launch; any other state means the pair is already decided — go to
   step 5.
3. **Launch one run.** One `experiment-reviewer` agent, with the brief from
   `py $R/reviews.py brief <lab-id> --run <A|B> --report P-NNNN --ticket T-NNNN`, and
   nothing else pasted in. On its primary model; never pass a model override except
   the named fallback (`fallback:` in its frontmatter), and say so if you do. The
   grading primaries (`grading.primaryModels`) are equal, so a fallback that is one of
   them counts in full; a verdict on any other model is capped at GAP and cannot clear. When it stops, the
   `land_review` hook writes `audits/<lab-id>/<date>-<A|B>.md`.
4. **Decide.** `py $R/reviews.py decide <lab-id>` again. `need-B`: go back to step 3
   for run B, a fresh agent that is told nothing of A. Otherwise continue. If the run
   asked for **reproduction** on another environment profile, file that as a `test`
   ticket to the Scientist (`$A/board.py new --to <lab instance> --kind test --as
   <instance> ...`, `--parent` the review ticket) and say the pair waits on it.
5. **Record.**
   - `cleared` / `cleared-modulo` with no `grounds_problems`: dispatch `claim-keeper`
     with the claim id, the proposed status and the `grounds` object from
     `reviews.py decide --json`. It calls `claims_set_status`; the server re-checks.
   - cleared with grounds problems, `not-cleared` or `unresolved`: nothing changes
     status. Ask claim-keeper only to attach the verdicts as evidence rows.
   - A packet (`$A/packets.py new --instance <instance> --kind experiment-review
     --ticket T-NNNN --subject <lab-id> --body <file>`) only when the human must decide
     something (a disagreement, a reproduction request, an allowed wording to accept).
6. **Close the ticket**: result line = the state and both verdicts, then `delivered`
   (`$A/board.py transition T-NNNN delivered --result "..." --as <instance>`).
7. **Report**: what is cleared and in which wording (the class, the bound, the
   exclusions), what is not and the single next action for each.

A cleared result is quotable as "no counterexample over class C", with the class's
exclusions; never as "true". Computation reaches `supported`, `refuted` or
`refuted-as-stated`, never `proved`. The checklist the reviewers use is
`${CLAUDE_PLUGIN_ROOT}/skills/review-experiment/checklist.md`.
