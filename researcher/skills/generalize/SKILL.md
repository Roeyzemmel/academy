---
name: generalize
description: 'Turn a reviewed experiment''s Conclusion into conjectures: prover proposes generalizations, each with a falsifier, one test ticket each to the Scientist, never above conjectured. Use for "/researcher:generalize <report>", generalize tickets, after an experiment review clears.'
---

# Generalize from an experiment

`$ARGUMENTS` is an experiment-report packet (`P-NNNN`), a lab claim id, or a
`generalize` ticket whose `refs` name them. The flow is docs/protocol.md section 6.2.
Scripts: `$R`, `$A` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Budget:
`academy/references/budget.md`.

1. **Source.** `py $R/generalize.py source <P-NNNN|lab-id>`: the report's
   `## Conclusion` and the review state of its lab claim(s). It refuses (exit 2) unless
   the experiment review has cleared (`/researcher:review-experiment` first). On a
   ticket: move it `accepted`, then `in-progress`. If there is no `generalize` ticket
   yet, open one to this instance so the tests have a parent (`py $A/board.py new --to
   <instance> --kind generalize --title "Generalize <lab-id>" --refs <lab-id>,<P-NNNN>
   --ask ... --deliverable ... --as <instance>`).
2. **One `prover`**, on its primary model, briefed with the packet id, the lab claim,
   the cap (`researcher.generalize.maxPerRun`, at most three) and the output file
   `<scratchpad>/generalize-<lab-id>.json`. It reads the Conclusion (and the domain's
   `examples.md` / `theorems/INDEX.md` through `domain_get` for what is already known),
   scouts prior art, and writes the proposals JSON in the shape `generalize.py`'s
   docstring gives: id in this instance's namespace, title, statement, kind
   `conjecture`, status `conjectured`, `bears_on` including the lab claim, the
   `falsifier`, the `pattern` (wider class / relaxed hypothesis / pattern / invariant)
   and a one-line rationale. It writes only that file; it creates no object.
3. **Validate.** `py $R/generalize.py validate <file> --lab-claim <lab-id>`. A problem
   goes back to prover once; a second failure drops that proposal and the report says
   why.
4. **Objects.** `py $R/generalize.py create <file> --lab-claim <lab-id>` shows the
   files; `--apply` writes each as `objects/conjecture/<id>.md`, status `conjectured`,
   `bears_on` the lab claim, with its `## Falsifier` section.
5. **Tickets.** `py $R/generalize.py tickets <file> --lab-claim <lab-id> --parent
   <generalize ticket>` prints one `test` ticket per proposal (to the lab instance,
   "test the falsifier first"); check them, then run it again with `--apply`. This
   main session files them, as the agent `main` (a researcher -> scientist liaison,
   docs/protocol.md 5.1); `prover` files no ticket to the Scientist.
6. **Packet.** `py $R/generalize.py packet-body <file> --lab-claim <lab-id> --report
   <P-NNNN> --out <scratchpad>/generalize-body.md`, then `py $A/packets.py new
   --instance <instance> --kind generalization --title "Generalizations of <lab-id>"
   --ticket <generalize ticket> --subject <new ids, comma-separated>
   --status-proposed conjectured --body <that file>`.
7. **Deliver** the generalize ticket with the result "N conjectures filed: <ids>;
   tests <T-ids>", and report the same.

A generalization that survives its test is proved through `/researcher:prove`; one
that fails is refuted through claim-keeper on the test's reviewed result. This skill
never sets any status above `conjectured`.
