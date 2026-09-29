---
name: corollaries
description: 'Derive corollaries of one established claim: prover writes each as a new unsettled object (sketch at most) depending on the source, with a short proof attempt. Use for "/researcher:corollaries <claim>" and after a claim turns proved.'
---

# Corollaries of a claim

`$ARGUMENTS` is a claim id. Scripts: `$R`, `$A` as in
`${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Budget: `academy/references/budget.md`
(at most `budget.itemsPerRun` new corollaries per run).

1. **Source.** `claims_show <id>`. Its status bounds what follows: a corollary of a
   `proved` claim can itself reach `proved`; of a `proved-modulo` claim, at most
   `proved-modulo` the same inputs; of anything unsettled, it is conditional and says
   so in its statement. Refuse a `refuted` source. What already rests on it:
   `claims_deps {id, reverse: true}` — do not restate an existing corollary.
2. **One `prover`**, briefed with the source id and the cap. It proposes at most three
   corollaries, each:
   - a new object (`claims_new`, status `sketch` when the derivation is written out,
     otherwise `open`) with `depends_on: [<source>, ...every other input]`;
   - a short attempt under `proofs/<new id>/` (`py $R/notebook.py attempt <new id>
     --create`) whose inputs name the source and every other object used, with
     statuses;
   - no corollary that needs a new idea: that is a claim for `/researcher:prove`, and
     the report says so.
3. **Route.** A corollary whose attempt is complete gets a `verify` ticket to the
   Expert exactly as `/researcher:prove` step 4 files it — one per corollary, within the
   budget; the rest wait, listed in the report.
4. **Report**: the new ids with statuses, their `depends_on`, the attempts, the
   tickets filed, and the ones deferred.

Nothing here raises a status above `sketch`; the Expert's reviews and claim-keeper do.
