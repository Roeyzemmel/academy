---
name: inbox
description: 'Work every instance''s board inbox in one run, in a fixed order (Author, Expert, Researcher, Scientist), one ticket at a time under the 3-item cap; --campaign T or --cowork S takes only that workplan''s tickets. Use for "work all the inboxes".'
---

# /academy:inbox

The cross-role inbox. The rules are code (the human's decision, 2026-10-31):
`workflows/inbox.js` holds the instance order, the cap over the whole run, one ticket at
a time with its `--check` checkpoint, the stop on a lost agent, every route of the roles'
`routes.py`, and the relays' legs and conclusions (docs/workflows.md). This skill only
calls it and finishes what it hands back.

`$ARGUMENTS`: empty, `--n N` (fewer than 3), `--all` (list only: run
`py <role plugin>/scripts/inbox.py --instance <name> --all` per instance and stop),
`--campaign <target-id>` or `--cowork <slug>` (only that workplan's tickets, under its
own caps, `references/budget.md`), or ticket ids. With no argument, first show the
active workplans (`py "${CLAUDE_PLUGIN_ROOT}/scripts/cowork.py" list`), one line each.

## 0. Decisions hold nothing back

First run `py "${CLAUDE_PLUGIN_ROOT}/scripts/decisions.py" proceed`: every pending packet
decision that has a recommended option (and whose packet proposes no publishing status)
is marked provisional and its tickets are told in one thread line, so the work that
depends on it goes on in this run. Nothing is decided by it; the decisions stay for
`/academy:decide`. Say in the report how many proceed provisionally. An agent that works
under a line "proceeding on P-NNNN Dk (x)" says so in its result and raises no status.

## 1. Run the workflow

Call the **Workflow** tool:

    scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/inbox.js
    args: {models: <the JSON object that py "${CLAUDE_PLUGIN_ROOT}/scripts/models.py" launches prints>, root: "${CLAUDE_PLUGIN_ROOT}/..", n: <N>, cap: <the workplan's cap, campaign/cowork only>,
           campaign: "<T>", cowork: "<S>", ids: ["T-NNNN", ...],
           runs: <agent runs for this run, only when the human gave a number>,
           approve: ["T-NNNN", ...]   (expensive tickets the human said to start)}

Give `root` as an absolute path (expand the variable). `only: ["<instance>"]` limits it to
one instance; the role inboxes pass that.

What the script does, so the report can be read against it: it lists each instance with
`py <role plugin>/scripts/inbox.py --instance <name> --json` (in progress first, then
return legs, then `open` and `accepted` by priority, agenda position, id). With `--campaign` each instance's
listing is not cut at three, and the campaign's own caps apply (`cap`). After each ticket it runs `inbox.py --instance <name> --check T-NNNN`:
exit 0 means delivered, blocked with its reason or rejected. Exit 3 on a ticket that is
`blocked` means parked; otherwise it means unfinished: that ticket is left as it is and not
taken again in this run, and the instance goes on with its next one. A ticket that was
already `in-progress` before the run and is still unfinished after it is moved to
`blocked`, `waiting_on: [human]`, so that it reaches `/academy:decide` instead of heading
every later listing. A second unfinished ticket of one instance closes that instance for
the run.

## 2. What comes back

- **`for_main`**: since 2026-10-31 every route runs in code, so this is only a **human gate**:
  - an experiment header to approve (`/scientist:experiment`, its next mode in `next`);
  - an experiment design that came back with an argument instead (`outcome: argument-instead`, the argument and three `options`): ask accept it (deliver the ticket with it), prove instead (a `prove` ticket to the Researcher, the argument as its lead), or run the experiment anyway (the design again with `next`, which carries `force: true`); and one with no usable header (`outcome: no-header`, its `problems`): run the design again, write the header with the experimenter, or drop it (#88);
  - an experiment script to commit, or a rendered report to look at;
  - a ticket with no route, which an Author or the Scientist puts to the human;
  - decisions that pause a campaign.

  One `for_main` is not a gate but work only this session can launch, marked `handback:
  lead-researcher`: a Researcher ticket whose lead-researcher needs a proof attempt
  (inside the run it cannot launch `prover`; T-1271). Ask nothing; the same holds for
  such an item among a loop's `gates`, whatever the end message says.
  - `skill: researcher:prove` with `args`: run the Workflow `researcher/workflows/prove.js`
    with `for_main.args` (it takes the ticket, still `in-progress`, and delivers it). The
    falsifier the lead reported (`falsifier`) is on the ticket's thread, where prove.js's
    state stage reads it. With none on record the hand-back is the same (2026-11-20): the
    attempt does not wait for a falsifier, a failed attempt or a GAP verdict triggers one, and
    `why` says none is on record (`pending` names falsifier tickets still open).
  - `skill: researcher:prove` with `mode: repair` and `handback: prove` (#85): prove.js found
    the claim `proved` and did not read the ticket as a repair, and delivered nothing. Read
    the ticket: if it asks for a repair, polish or record, run prove.js with `for_main.args`
    (they carry `mode: "repair"`); otherwise deliver or cancel it yourself (it is still
    `in-progress`), saying why.
  - `skill: researcher:prove` without `args`: `why` says what is missing. A claim that is
    missing or does not resolve: register the statement with `claims_new` in that instance,
    then run prove.js as above. A registry check that failed (an exit code, not "does not
    resolve"): run `registry.py statement <claim>` yourself; register only if it reports the
    claim missing.

  Then call the inbox again.

  Ask with `AskUserQuestion`, carry the answer out (the next mode of the workflow named,
  or the ticket move), then call the workflow again with `cap` lowered by `count`.
- **`loop: true`** (the whole academy at once): pass after pass over every inbox until
  nothing moves, at most `cap` tickets (default 12) and `passes` passes (default 6). A
  delivered ticket's return leg and the next actor of a filed child are taken in the next
  pass. A ticket that needs the human is set aside in `gates` and the others go on. At the
  end, `for_main` lists every gate: ask them in one batch, then run the loop again.
- **`budget`**: `{runs, spent, deferred}`. The budget is the run's (`references/budget.md`
  rule 7): each route's cost is declared in the script and counted as the run goes. A
  ticket in `deferred` did not fit what was left; it was not started and is not blocked,
  and comes up in the next run. Report the deferred ones in one line. A gate that says a
  ticket "costs about N agent runs" is the human's to answer: run again with
  `approve: ["<id>"]` if they say so. Never block a ticket to ask for budget.
- **`stopped`**: an agent returned nothing (a limit). Launch nothing further and report it.
- **`notes`**: put them into the report verbatim (an unfinished ticket, one parked on the
  human after two runs, an instance closed after two unfinished tickets, a relay child the check refused, the Author's check_paper reminder).

## 3. Report

One line per ticket in `taken`: instance, id, route, outcome. Then the sweep counts,
`remaining` per instance, and anything parked on the human (`/academy:decide`).
