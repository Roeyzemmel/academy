---
name: settle
description: 'Settle a returned result reporting candidate counterexamples: review the script, independently re-derive each candidate (at most three) via Scientist and Expert verify, apply the decision table. Use on every search result that reports a counterexample.'
---

# Settle a result with candidates

## Scope notes

- At most three candidates are filed per run, by likelihood `rank` (`settle.py plan --max`, capped by `budget.itemsPerRun`); the rest are deferred.

`$ARGUMENTS` is the lab claim id (or the report packet / ticket naming it). Scripts:
`$R`, `$A` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`; the decision table is
in `settle.py`'s docstring. Budget: `academy/references/budget.md`.

A result that hands you a counterexample to a question the notebook has been circling
is the most dangerous kind. Nothing is recorded until it clears.

1. **Candidates file.** From the report packet's raw outcome, write
   `<scratchpad>/settle-<lab-id>.json`: one entry per candidate with its `name`, `rank`
   (likelihood, 1 first), `ref`, and `detail` (parameters and certificate, verbatim from
   the report). No verdicts yet.
2. **Audit the script** exactly as `/researcher:review-experiment` steps 2–4: the
   experiment-review pair, landed by the hook. `py $R/settle.py plan <lab-id>
   --candidates <file>` shows where things stand.
3. **Candidates.** Only when the audit has cleared (the plan says so; a failed audit
   makes every candidate unrecordable, and filing their tickets would spend budget for
   nothing). For each candidate the plan lists under `file_now`, two tickets, both
   filed by this main session as the agent `main` (a liaison toward the Scientist and
   toward the Expert; `prover` may not file to the Scientist):
   - **Re-derivation (Scientist).** One `experiment` ticket to the Scientist instance
     (`py $A/board.py new --to <scientist> --kind experiment --title "Re-derive <name>
     independently" --ask ... --deliverable ... --refs <lab-id>,<claim> --detail
     "<detail>" --as <instance>`) for a `verify`-kind experiment: rebuild the candidate's decisive data
     from its defining input alone, by a route the pipeline did not use (a second
     implementation, another library), small cases only, and report whether it agrees.
     The reviewers cannot compute, so this run is the independent re-derivation.
   - **Review (Expert).** One `verify` ticket to the Expert instance (`py $A/board.py new
     --to <expert> --kind verify --title "Is <name> a counterexample to <claim>?" --ask
     ... --deliverable ... --refs <lab-id>,<claim>,<re-derivation ticket> --detail
     "<detail>" --as <instance>`), asking the review-chair for the rigor-reviewer pair in refutation
     mode: completeness of the enumeration first, then the re-derivation's report (it
     must exist, use another route and agree), then the witnesses. When this home has a
     verification checklist rule (`.claude/rules/verification-checklist.md`), the ticket
     names it: the reviewers work every item of it. File the review ticket only once the
     re-derivation report is back (a later run; nothing waits in a loop).

   Record both ticket ids in the candidates file. The rest are reported as deferred.
4. **Collect.** When the Expert's verification packets come back (a later run: nothing
   waits in a loop), copy each candidate's verdicts into the file (`run`, `verdict`,
   `model`, `run_id`, `packet`). Give `model` as the exact id each run reports
   (`claude-opus-5-5`, `claude-fable-…`): Fable and Opus 5.5 are equal primaries, and a
   run on any other model (Sonnet, Haiku, an older Opus) counts as not positive.
5. **Decide and record.** `py $R/settle.py decide <lab-id> --candidates <file>`, then
   `py $R/settle.py record <lab-id> --candidates <file>`, which writes the decision
   record `audits/<lab-id>/<date>-settle.md` (never rewritten; a new pass is a new file).
6. **Status.** Only the `recordable` candidates move anything: dispatch `claim-keeper`
   with the claim, the status (`refuted`, or `refuted-as-stated` with the repaired
   statement), and the proof grounds from the two CONFIRMED verdicts. The lab claim's
   own status follows the audit (`reviews.py decide`), as in review-experiment.
   A disagreement is recorded as unresolved and its weaker verdict's blocking step
   becomes the next ticket.
7. **Report** what is cleared for citation and what is not, and for anything not
   cleared the single next action.

A cleared refutation is quotable with the member, the certificate and the verdicts; a
cleared negative search only as "no counterexample over class C". Computation refutes;
it never proves.
