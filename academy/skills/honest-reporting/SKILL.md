---
name: honest-reporting
description: How to report finished work so nothing unverified passes as established — the status in the first sentence, checked versus assumed kept apart, a machine note on every judgement call or unverified step, failures and partial results reported plainly, and never claiming a check, run, commit or publication that did not happen. Use at the end of every task that produces a report, a packet, a ticket result, a machine note or a summary for Roey, and whenever an agent is tempted to round a partial result up.
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
