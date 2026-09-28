---
name: experiment
description: Take a mathematical claim from words to a queued, provenance-stamped experiment in the lab (the Scientist home) and, when the result is back, to a report packet — classify the work (two-line argument / probe / experiment), get the header approved before any compute, have the experimenter scaffold it with a validation case and a lab claim, file the run on the policy's run profile, then generate the experiment report (search / measure / verify / probe) with its mandatory ## Conclusion and file a review ticket to the Researcher. Use on "let's check this", "can we test", "find a counterexample to", "measure ...", before any new experiment script, and when a finished run needs its report.
---

# An experiment, from a claim to a reviewed report

`$ARGUMENTS` is the claim in Roey's words, a ticket id (`T-NNNN`, kind `experiment`
or `test`), or `report <script>` for a run whose result is back.

This skill orchestrates; the discipline is `scientist:experiment-method`, the budget
is `${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md` (at most three items per
run, serially, no relaunch after a limit error) and the independence rules are
`${CLAUDE_PLUGIN_ROOT}/../academy/references/roster-rules.md`.

## 0. Where, and which path

```
py "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" home
```

names the lab instance, its home, domains, env profiles and policy. A home may have
its own entry point for one kind of experiment (a family hunt); that one wins for
its kind.

Classify the work and say which path you took, in one sentence:

| Path | When | Ends in |
|---|---|---|
| **Two-line argument** | an argument settles it more cheaply than code | the argument, no script. Stop and give it: that is a better result |
| **Probe** | "is it computable, how big does it get": feasibility, not evidence | a throwaway in `scratch/` with a header `Kind: probe`, `Goal:` and `Decides:` written *before* it runs; a probe report |
| **Experiment** | a claim that a search could refute, a quantity to measure, one object to verify | the full path below |

## 1. The header, approved before any compute

Dispatch one `experimenter` with the claim (or ticket id) and the kind. It reads the
statement from its owner, the pack's `examples.md` / `traps.md` / `computation/`
through `domain_get`, the nearest existing script and the lab's package, and
returns the **header only**. An unfamiliar library call goes through
`/scientist:api-check` first.

Show the header to Roey and ask with `AskUserQuestion`: approve / change / drop.
Put the design question with it: *if the claim were false, what would this
experiment still report?* This is the one rule with no exception; no body is
written before the answer.

## 2. Scaffold, check, stop for the commit

Dispatch the experimenter again with the approved header: package code test-first,
the script from the lab's template, `validate()` before `run()`, the lab claim
created (`claims_new`, status `open`). Check mechanically (the hook also does this
after every edit):

```
py "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" cmd check experiments/<stem>.py --strict
```

The queue runs the committed script, so **Roey commits** experiment scripts: stop
with the script ready and say so, unless he has said to commit.

## 3. Queue

File the run on the `policy.run` profile with `queue_add` (script, label = the lab
claim id, note, script arguments). While it answers with `dry_run: true` (the lab's
academy.json has `scientist.queue.mcpAdd` off), run the command its `note` names, or
the one
`lab.py cmd queue -Add experiments/<stem>.py -Label lab:<id> -Note "..." -ScriptArgs "..."`
prints. Then hand over to `/scientist:queue`.

## 4. When the result is back: the report

1. The experimenter fills the header's `Result:` ("no counterexample below bound B
   over class C", never "true") and writes the report draft
   `reports/<stem>.md` with `## Conclusion` (`Establishes:` supports / refutes /
   inconclusive, `Does not establish:`, `Proposed status:`, `Next step:`) and
   `## Validation` (`Reproduced: yes|no`).
2. Check, then show Roey the rendered packet:

   ```
   py "${CLAUDE_PLUGIN_ROOT}/scripts/report.py" check  experiments/<stem>.py [--env <profile>] [--job <id>]
   py "${CLAUDE_PLUGIN_ROOT}/scripts/report.py" render experiments/<stem>.py [...]
   ```

   The script refuses without an experiment type (`search | measure | verify |
   probe`), without `## Conclusion`, with a proposed `proved`, or when a required
   field (claims, question, what the class cannot contain, env profile, commit,
   whether the validation reproduced) is missing. Report a refusal as it is; the fix
   is in the header or the draft, never a hand-written packet. Templates:
   `${CLAUDE_PLUGIN_ROOT}/templates/report-<type>.md`.
3. File it:

   ```
   py "${CLAUDE_PLUGIN_ROOT}/scripts/report.py" file experiments/<stem>.py [--env ...] [--job ...] [--ticket T-NNNN]
   ```

   This writes packet `P-NNNN` (kind `experiment-report`) under the lab's
   `board/packets/` folder, linked to the commissioning ticket if there is one, and
   files a `review-experiment` ticket to the Researcher that owns the claims'
   namespace (`--to` overrides), refs = the claims, the packet and the files, budget
   two runs at most `fable`. Say which Researcher and why (the script prints it).

**A surprising result is a bug until shown otherwise**
(`superpowers:systematic-debugging`): debug before believing a new theorem. A status
change on the lab claim is proposed only; the claim-keeper makes it after two
agreeing experiment reviews. Script and result JSON are committed together; the
commit gate enforces it.

## Report to Roey

The path taken; the header (approved or not); the files written; the job filed; for
a report, the packet and ticket ids and the reviewer; what is left and who has it.
