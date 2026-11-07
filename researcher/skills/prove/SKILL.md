---
name: prove
description: 'Take one notebook claim to a reviewable proof: prover writes the next attempt under proofs/<id>/, a complete attempt becomes a verify ticket to the Expert. Never sets a status. Use for "/researcher:prove <claim>", prove tickets, research tickets from lead-researcher.'
---

# Prove a claim

`$ARGUMENTS` is a claim id (`<ns>:<id>`) or a `prove` ticket. Run from the Researcher home.
Independence: `academy/references/roster-rules.md` (the producer never grades its own work).

The order is code (2026-10-31; docs/workflows.md). Call the **Workflow** tool with
`scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/prove.js` and
`args: {claim: "<ns:id>", ticket: "T-NNNN" or omitted, home: "<this home, absolute>", instance: "<this instance>"}`.
The inbox runs the same script for a `prove` ticket. The script:

1. **State.** The clerk takes the ticket and reports the claim's status, its unsettled
   inputs, earlier attempts, whether a falsifier ran, and whether an attack exists. A
   `proved` claim needs nothing. A claim resting on an unsettled input can be proved at
   most `proved-modulo` it; the brief says so.
2. **Falsified first.** A claim nobody tried to break returns `needs_explore`: run
   `/researcher:explore` (its falsifier), then call again. A statement nobody attacked on
   paper first gets one attack-only `prover` run (`academy/skills/rigor/references/attack-brief.md`,
   writing `proofs/<id>/attack.md`).
3. **One `prover` attempt** in the path from `notebook.py attempt <id> --create`: prior art
   first (cite before reproving), then the statement as attempted, the strategy, the
   proof, the inputs with their statuses, the gaps. A repair is a new attempt.
4. **The outcome is read from the attempt's frontmatter** by the clerk, never from the
   prover's summary:
   - `complete` with no gaps: the prover files one `verify` ticket to the Expert (the
     script checks it). If the claim was `open`, the prover also proposes `sketch`.
   - otherwise: nothing goes to review. The prover's attempt records the gaps; a gap
     that is a separate lemma becomes its own object with a `prove` ticket.

   On a ticket, the result line names the verify ticket, or the gaps.

Nothing goes above `sketch`: `proved` and `proved-modulo` come only from two agreeing
Expert reviews, through claim-keeper. **Report** the attempt path and outcome, each gap,
the inputs and their statuses, the ticket filed, the status proposed, and the script's
`notes`.
