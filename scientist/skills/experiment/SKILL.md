---
name: experiment
description: 'Take a mathematical claim from words to a queued, provenance-stamped lab experiment and then to a report packet; header approved before any compute. Use for "let''s check this", "can we test", "find a counterexample to", or a finished run''s report.'
---

# An experiment, from a claim to a reviewed report

`$ARGUMENTS` is the claim in the human's words, a ticket id (`T-NNNN`, kind `experiment` or
`test`), or `report <stem>` for a run whose result is back. The discipline is
`scientist:experiment-method`; the budget is `academy/references/budget.md`.

One leg per call of the Workflow tool, `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/experiment.js`
(2026-10-31; docs/workflows.md). The human gates are the human's, and the script makes them
unskippable; between the legs this session asks with `AskUserQuestion`:

1. **`design`** (`{mode: "design", claim | ticket, kind}`): the lab is located
   (`lab.py home`), and the experimenter classifies the path:
   - a **two-line argument** that settles it more cheaply than code: no script, and that
     is the better result;
   - a **probe**: feasibility, not evidence, with a header `Kind: probe`, `Goal:`,
     `Decides:`;
   - an **experiment**: the header only.

   An unfamiliar library call goes to `/scientist:api-check` first. **Gate:** show the
   header with the design question (*if the claim were false, what would this experiment
   still report?*): approve, change or drop. No body is written before the answer. The
   inbox runs this leg itself for an experiment ticket.
2. **`build`** (`{mode: "build", stem, header: "<the approved text>", commit_ok}`): package
   code test-first, the script from the template, `validate()` before `run()`, the lab claim
   `open`; `lab.py cmd check --strict`, with one fix round. **Gate:** the human commits the
   script, unless they said to (`commit_ok`).
3. **`queue`** (`{mode: "queue", stem}`): refused for an uncommitted script; otherwise the
   run is filed on `policy.run` (label = the lab claim). Then hand over to
   `/scientist:queue`.
4. **`report`** (`{mode: "report", stem, job, env}`, once the result is back): `Result:`
   ("no counterexample below bound B over class C", never "true"), the draft
   `reports/<stem>.md` (`## Conclusion`, `## Validation`), `report.py check` with one fix
   round (the fix is in the header or the draft, never a hand-written packet), then
   `report.py render`. **Gate:** the human sees the rendered packet.
5. **`file`** (`{mode: "file", stem, job, env, ticket}`): `report.py file` writes the
   `experiment-report` packet and the `review-experiment` ticket to the Researcher that
   owns the claim's namespace (say which and why), and the ticket is delivered.

**A surprising result is a bug until shown otherwise** (`superpowers:systematic-debugging`).
A status change on the lab claim is proposed only. Script and result JSON are committed
together; the commit gate enforces it.

## Report to the human

The path taken; the header (approved or not); the files written; the job filed; for a
report, the packet and ticket ids and the reviewer; what is left and who has it.
