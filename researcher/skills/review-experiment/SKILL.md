---
name: review-experiment
description: 'Review a computed result before it counts: two fresh experiment-reviewer runs (B only after a positive A), decision table by script. Use on review-experiment tickets and before a result is cited. Counterexample candidates: /researcher:settle.'
---

# Review an experiment

`$ARGUMENTS` is a ticket id (`T-NNNN`, kind `review-experiment`), a report packet
(`P-NNNN`) or a lab claim id. Run it from the Researcher home, in the main session.

A result that agrees with what you hoped is the dangerous kind, and a surprising result
is a bug until shown otherwise. One adversarial read is not a sign-off, so the result
gets two runs, and a disagreement is reported, never averaged.

## 1. Run the workflow

The sequencing is code (the human's decision, 2026-10-31). Call the **Workflow** tool:

    scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/review-experiment.js
    args: {subject: "lab:<id>", ticket: "T-NNNN", report: "P-NNNN", mode: "review"}

The script does the following:
- the `review-clerk` takes the ticket and reads `reviews.py decide`;
- it launches `experiment-reviewer` run A with `reviews.py brief`'s text, and nothing
  else, then run B only when `decide` says `need-B` (a fresh agent told nothing of A);
- it relaunches a run that did not land once, and stops on a lost run;
- it sends `claim-keeper` decide's grounds only on `cleared` / `cleared-modulo` with no
  `grounds_problems` (otherwise evidence rows only);
- it files a packet when the human must decide, and delivers the ticket.

The `land_review` hook lands each run. A hand-launched `experiment-reviewer` is refused
by the `review_launch_guard` hook. Pass no model override.

`outcome: needs-settle` means the report lists candidate counterexamples: run
`/researcher:settle` instead.

**By hand**, only when the Workflow tool cannot run: the human sets
`ACADEMY_ALLOW_MANUAL_REVIEW=1`. Then this seat loops `reviews.py decide` and
`reviews.py brief` itself (`$R` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`), and
the report says the pass ran by hand.

## 2. After it returns

- **`to_file`**: file each entry as this main session, which is the liaison. A
  reproduction request is a `test` ticket to the Scientist, `--parent` the review ticket.
  The pair waits on it.
- Put `notes` (a skipped B, a relaunch, a lost run) into the report verbatim.

## 3. Report

What is cleared and in which wording (the class, the bound, the exclusions), what is
not, and the single next action for each. A cleared result is quotable as "no
counterexample over class C", with the class's exclusions, never as "true". Computation
reaches `supported`, `refuted` or `refuted-as-stated`, never `proved`. The reviewers'
checklist is `${CLAUDE_PLUGIN_ROOT}/skills/review-experiment/checklist.md`.
