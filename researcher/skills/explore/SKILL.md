---
name: explore
description: 'Work one research direction forward, at most three unsettled items per run, in the order falsify, prior art, prove (probes to the Scientist as experiment tickets, arguments to prover). Use for "/researcher:explore <direction>", "what should we try next on X", question tickets.'
---

# Explore a direction

`$ARGUMENTS` is a direction id (an object under `objects/direction/`), optionally with
the items to take. A `question` ticket counts as a one-item run. Scripts: `$R`, `$A`
as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Budget: `academy/references/budget.md`
(at most `budget.itemsPerRun` items, serially; nothing starts itself).

The main session briefs and relays. It writes no mathematics, no code and no
experiment script, and decides no truth.

1. **Read the direction.** `py $R/notebook.py direction <id>`: its questions, candidate
   claims and falsifiers, each with its registry status. No direction object yet: make
   one with `py $R/notebook.py new direction <id> --title "..."` and let
   `lead-researcher` fill its program and lists before anything else.
2. **Pick.** `py $R/notebook.py next <id>` gives the next unsettled items, in the
   direction's own order (at most three). Say how many remain.
3. **Brief one `lead-researcher`** with the direction id and the picked item ids, and
   nothing pasted in. It moves each item one step, in this order:
   - **Falsify.** A candidate claim gets a falsifier: the smallest case where it could
     fail. `lead-researcher` files the ticket to the Scientist, as a researcher ->
     scientist liaison (docs/protocol.md 5.1); `prover` may not. One named example is
     a `probe` (`experiment` ticket asking for the probe type); a family, a parameter range or a bound is a search (`experiment` ticket).
     The ticket carries the claim id, what output would refute it, the validation case
     with an independently known answer, and which inputs are still unsettled (a code
     path resting on an unsettled claim may validate but not refute). The Scientist's
     experimenter gets its header approved before any code; nothing is queued until
     then.
   - **Prior art.** What is already known: `prover`'s scout pass, and `lookup` / `cite`
     tickets to the Expert. A hit against the claim is the most valuable outcome.
   - **Prove.** An item that survived falsification and has no prior proof goes to
     `prover` for an attempt, then `/researcher:prove` files the review.
   - A small local hand-check of one example is the Scientist's `probe` policy
     (`scientist.policy.probe`), not something run from here. A loop over parameters is
     a search and goes through the queue.
4. **Record.** The lead updates the direction's lists and today's journal
   (`py $R/notebook.py journal --create`): tried, dead ends, next. New questions or
   claims become objects (`claims_new` / `notebook.py new`), unsettled.
5. **Report** the lead's report, not a summary of it: each item, the step it moved,
   the ticket ids filed, and what the next run would pick.

**Reading a returned result.** An undecided search (a cap hit) is not a counterexample.
A candidate counterexample from a probe is a lead, not a finding: it has no
provenance and no review until it is run as an experiment and settled
(`/researcher:settle`). A probe that disagrees with a queued run is a reason to suspect
both.
