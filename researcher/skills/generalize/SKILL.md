---
name: generalize
description: 'Turn a reviewed experiment''s Conclusion into conjectures: prover proposes generalizations, each with a falsifier and a test ticket to the Scientist, never above conjectured. Use for "/researcher:generalize <report>", generalize tickets.'
---

# Generalize from an experiment

`$ARGUMENTS` is an experiment-report packet (`P-NNNN`), a lab claim id, or a `generalize`
ticket whose `refs` name them. The flow is docs/protocol.md section 6.2. Run from the
Researcher home.

**Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/generalize.js`
and `args: {ref: "<P-NNNN | lab:id>", ticket: "<the generalize ticket>", home: "<this home>", instance: "<this instance>"}`.
The inbox runs it for a `generalize` ticket. The order is code (2026-10-31;
docs/workflows.md):
1. `generalize.py source` refuses unless the experiment review has cleared
   (`/researcher:review-experiment` first);
2. one `prover` writes only the proposals file, at most `researcher.generalize.maxPerRun`
   (three), each a conjecture with its falsifier and at most three lemmas;
3. `generalize.py validate` checks the file. Problems go back to the prover once; a second
   failure drops that proposal;
4. `generalize.py create --apply` writes the objects (`conjectured`, lemmas `open` or
   `sketch`);
5. the `generalization` packet.

What comes back for this session:
- **`needs_ticket`**: open the generalize ticket to this instance first (`py <academy>/scripts/board.py new
  --to <instance> --kind generalize --title "Generalize <lab-id>" --refs <lab-id>,<P-NNNN> --ask ...
  --deliverable ... --as <instance>`), then call again with it.
- **`to_file`**: run its one command (`generalize.py tickets ... --apply`). It files the
  falsifier tests as `main`, the researcher -> scientist liaison; the prover files no
  ticket to the Scientist. Then call the workflow again with `mode: "deliver"` and the
  `then` values. It checks that a test names each conjecture before it delivers the
  ticket.

A generalization that survives its test is proved through `/researcher:prove`; one that
fails is refuted through claim-keeper on the test's reviewed result. Nothing here goes
above `conjectured` (a lemma: `sketch`).
