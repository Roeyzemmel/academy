---
name: honest-reporting
description: 'How to report finished work so nothing unverified passes as established: status first, checked versus assumed kept apart, machine notes on judgement calls, failures stated plainly. Use at the end of any task that produces a report, packet or summary.'
---

# Honest reporting

The reader of a report acts on it without redoing the work. So a report must let them
see at once what is established, what is assumed and what was not done.

## The shape of a report

1. **The status first.** The first sentence says what was achieved, in the
   `status-vocabulary` words. If the result is partial, failed or unsettled, the
   first sentence says so, not the last paragraph.
2. **Established vs assumed**, kept apart, as in a packet's
   `## Established vs assumed`:
   - **Established:** what was checked, with how (a verdict, a run id, a quote, a
     build, a test run and its result);
   - **Assumed:** what was used without checking, named precisely;
   - **Not established:** what was asked and not done, and why.
   Every statement named carries its status. A sketch is never presented as a
   theorem, and `supported` is never presented as proved.
3. **Evidence by reference.** Point at the file, id, commit or run; do not paraphrase
   a result from memory.

## The final report of a long run

A campaign or any multi-round run ends with, in this order: the **status first**
(the audited proof, or the strongest rigorously proved derivation and the exact
remaining gap as a claim id); the **table of routes** (each with its lifecycle, what
blocks it and what would reopen it); the **open tickets** and what each waits for;
what could not be done and why. No "best effort" summary, and no explanation of why
the problem is hard.

## Machine notes

Mark every judgement call, sketched step and unverified claim where it lives, with the
home's machine-note macro (in a paper, the `\Claude{…}` family from
`author.noteMacros.machine`; in a packet, `## Machine notes`; in a ticket, a thread
line). One note per call, saying what was decided and what is unverified. Name every
note in the report as well, so none is found only by accident. Never sign a note as a
human.

## What never happens

- Claiming a check that was not run: "tests pass" needs the test command and its
  output in this run; "the build is clean" needs the build.
- Claiming an action that did not happen: a commit, a publication, a filed ticket, a
  status change. Say what the tool result confirmed, and no more.
- Softening a gap into prose ("this should follow", "presumably"). Name the gap.
- Rounding up: a result in special cases reported as the general result, a search
  over a restricted class reported without the class, a fallback-model verdict
  reported as a full one.
- Hiding a failure. A limit error, a capped agent, a refused write or a failing test
  is reported with what was and was not done (`references/budget.md`).
- Inventing to fill a gap in the record. If a fact is missing (a config value, a
  pinpoint, a result), say it is missing.
