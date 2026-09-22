---
name: verify
description: Verify one labelled statement — by default the head of the roadmap's verification queue — with two independent adversarial runs (the second only if the first is positive) and recolour it only if both agree — the sanctioned route from a blue (sketched) statement to an established one. Dispatches one master-verifier, which launches the pair, adjudicates it and records both verdicts in Drafts/verdicts.md. Use on any [verify] roadmap item about an argument, and before any recolouring.
---

# Verify one statement

`$ARGUMENTS` is the label to verify, optionally followed by the question asked. If it is
empty, take the **head of the `## Verification queue`** section at the end of
`Drafts/comment_roadmap.md` (tiers fill it; they no longer verify anything themselves),
or, if the queue is empty, an open `[verify]` item — and **say which one and why** before
dispatching. One label per invocation: verification is the most expensive pass in the
roster, and the author decides how much of the queue to spend on.

A single adversarial read is not a sign-off. Published measurements of LLM proof
verification put self-inconsistency across repeated runs of the same proof in the tens
of percent: the same model, the same proof, a different verdict. So this pass runs the
check **twice, independently**, and treats disagreement as a finding in itself. The two
runs go **in sequence**: run B is launched only if run A comes back positive, since a
negative A already rules out recolouring and its findings are enough to file the repair.

## 1. Dispatch one master-verifier

Dispatch **one** `master-verifier` subagent with the label, the file, and the question if
one was given. It launches the blind `proof-verifier` runs itself, adjudicates them
with the table below, and lands the result in the ledgers through
`paper:verify-conclude`. **You do not launch `proof-verifier` directly** — the pair and
its concluder belong in one agent, which is what keeps the adjudication's context whole.

Pass no `model` override. `master-verifier` applies the fallback rule to the pair itself
when the primary is genuinely unavailable, and names the substitution. A fallback
verdict is PLAUSIBLE and never recolours.

**Running it by hand.** If `master-verifier` cannot be launched, the main session may run
the runs itself — `proof-verifier` run A, then run B only if A is positive, same brief,
neither told of the other:

> Verify `<label>` in `<file>`. The question is whether it may go black. Work through
> your obligation ledger before reading the proof.

— and then load `paper:verify-conclude` and conclude in the same seat. Say in the report
that the pass ran by hand.

## 2. The decision table

`master-verifier` applies this; it is stated here because it is the pass's contract.

| Run A | Run B | Outcome |
|---|---|---|
| proved | proved | **CONFIRMED** — recolour |
| proved modulo X | proved modulo X (same inputs) | **CONFIRMED modulo X** — recolour only if every input in X is itself black or a verified citation; otherwise it stays blue and the inputs become the next `[verify]` items |
| proved | anything else | **disagreement** — no recolouring; relay both reports in full and file the weaker verdict's blocking step as a roadmap item |
| disproved (either run) | — | **disproved** — no recolouring; the counterexample goes to the author immediately, whatever the other run said |
| anything else | anything else | no recolouring; report the union of the findings |
| gap / partial / reduced / not settled | not launched | **single negative run** — no recolouring; A's blocking step is filed as the repair item, and the ledger says B was skipped by design |

Disagreement is the interesting case, not a nuisance: two hostile readings that differ
have found an ambiguity in the write-up even when the mathematics is fine.

## 3. Recolouring, when it is earned

The recolouring is a LaTeX edit, not a mathematical one, and neither the verifiers nor
`master-verifier` may make it. When its report says a recolouring is earned, dispatch
`latex-fixer` with the label, the verdict, and this instruction:

> Recolour `<label>`: remove the `sketch` environment around the statement (or the
> colour command around the span) and delete the machine note that said the proof was
> unverified. Change nothing else — no wording, no hypothesis, no other note.

## 4. The ledger

`master-verifier` writes `Drafts/verdicts.md` itself, newest first, in the shape
`paper:verify-conclude` gives. Do not write it again from here. This ledger is what
`note-sweeper` reads to decide that a "blue because unverified" note has been answered,
so a run that never reaches it did not happen.

## 5. Report

Relay `master-verifier`'s report, not a summary of it: both verdicts in the verifiers'
own words, side by side; the decision the table gives; the input-by-input status; the
**blast radius** when there is one — lead with it; the recolouring if it happened, with
the file and the line; and where the ledgers were written. Never ask questions.
