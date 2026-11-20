---
name: prove
description: 'Take one notebook claim to a reviewable proof: prover writes the next attempt under proofs/<id>/ (the related registry statements in its brief, its dependencies declared), a complete attempt becomes a verify ticket to the Expert. Never sets a status. Use for "/researcher:prove <claim>", prove tickets, research tickets from lead-researcher.'
---

# Prove a claim

`$ARGUMENTS` is a claim id (`<ns>:<id>`) or a `prove` ticket. Run from the Researcher home.
Independence: `academy/references/roster-rules.md` (the producer never grades its own work).

The order is code (2026-10-31; docs/workflows.md). Call the **Workflow** tool with
`scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/prove.js` and
`args: {models: <the JSON object that py "${CLAUDE_PLUGIN_ROOT}/../academy/scripts/models.py" launches prints>, claim: "<ns:id>", ticket: "T-NNNN" or omitted, mode: "repair" when the human or a hand-back asks for a repair, home: "<this home, absolute>", instance: "<this instance>", root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>"}`.
The inbox runs the same script for a `prove` ticket. The script:

1. **State.** The clerk takes the ticket and reports the claim's status, its unsettled
   inputs, earlier attempts, whether a falsifier is on record, whether an attack exists, and whether
   the ticket asks for a **repair** (repair, polish, restyle or record an argument, or
   answer a negative review) rather than a first proof (`mode: "repair"` forces it). A
   `proved` claim with no repair asked is handed back (`already_proved`; the inbox returns
   it to the main session with `mode: "repair"` to rerun), never delivered with nothing
   done (#85); called directly with a ticket, read it and rerun with `mode: "repair"`, or
   deliver or cancel the ticket (it is left `in-progress`). A claim resting on an unsettled input can be proved at
   most `proved-modulo` it; the brief says so.
2. **No falsifier wait** (2026-11-20). The attempt goes ahead whether or not a falsifier
   is on record: the verify workflow runs it after review A. A falsifier counts as on
   record when it attacked this claim, or is recorded on a declared input (`depends_on`) or
   the parent lead whose class covers it, or the human waived it on the ticket (#117); the
   script checks an input's id against the declared inputs and a waiver for the human's
   line, and the result (`falsifier_on_record`, `falsifier_source`, `falsifier`) and the
   verify ticket's ask say which, or that none is on record. A statement nobody attacked on
   paper first gets one attack-only `prover` run (`academy/skills/rigor/references/attack-brief.md`,
   writing `proofs/<id>/attack.md`).
3. **Related statements.** A clerk stage searches the registries (the paper's and the
   notebooks', `registry.py find` / `grep`) for statements related to the claim and returns
   at most twelve, proved and proved-modulo first (`related` in the result). They go into
   the prover's brief: cite each one that does the work, never reprove a proved statement,
   and say in the attempt for each one "used as input" or why not.
4. **One `prover` attempt** in the path from `notebook.py attempt <id> --create`: prior art
   first (cite before reproving), then the statement as attempted, the strategy, the
   proof, the inputs with their statuses, the gaps, and the frontmatter's `dependencies:`
   (every id and `bib:<key>#<pinpoint>` it relies on, the same items as its inputs). A
   repair is a new attempt.
5. **The outcome is read from the attempt's frontmatter** by the clerk, never from the
   prover's summary:
   - `complete` with no gaps and its dependencies declared (the list present, every input
     of *Inputs and their status* in it): the prover files one `verify` ticket to the
     Expert, naming the dependencies in its refs and ask, and whether a falsifier is on
     record (the script checks it). If the claim was `open`, the prover also proposes `sketch`.
   - otherwise: nothing goes to review. The prover's attempt records the gaps; a gap
     that is a separate lemma becomes its own object with a `prove` ticket.

   On a ticket, the result line names the verify ticket and the dependencies, or the gaps.

Nothing goes above `sketch`: `proved` and `proved-modulo` come only from two agreeing
Expert reviews, through claim-keeper. **Report** the attempt path and outcome, each gap,
the inputs and their statuses (the declared `dependencies`), the related statements and
what the attempt did with each, whether a falsifier is on record, the ticket filed, the status proposed, the script's
`notes`, and `ship` (the ticket's checkpoint, run once; without a ticket `not-run` with
the command to run from the workspace root; a refusal is reported, never retried).
