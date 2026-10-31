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

## 1. Run the workflow

Call the **Workflow** tool:

    scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/inbox.js
    args: {root: "${CLAUDE_PLUGIN_ROOT}/..", n: <N>, cap: <the workplan's cap, campaign/cowork only>,
           campaign: "<T>", cowork: "<S>", ids: ["T-NNNN", ...]}

Give `root` as an absolute path (expand the variable). `only: ["<instance>"]` limits it to
one instance; the role inboxes pass that.

What the script does, so the report can be read against it: it lists each instance with
`py <role plugin>/scripts/inbox.py --instance <name> --json` (in progress first, then
return legs, then `open` and `accepted` by priority, agenda position, id). With `--campaign` each instance's
listing is not cut at three, and the campaign's own caps apply (`cap`). After each ticket it runs `inbox.py --instance <name> --check T-NNNN`:
exit 0 means delivered, blocked with its reason or rejected. Exit 3 means unfinished,
and nothing more is taken from that instance in this run.

## 2. What comes back

- **`for_main`**: the run stopped at a ticket only this main session may run: a skill
  route (`author:notes`, `researcher:settle`, `/scientist:experiment`, ...), a question to the human
  (an Author ticket with no route: `AskUserQuestion`), a research ticket only `main` may
  file, or `/researcher:settle`. Run it as the role's inbox skill says, then its
  `py <role plugin>/scripts/inbox.py --instance <name> --check T-NNNN`. Then call the
  workflow again with `cap` lowered by `count + 1`, until the cap is spent or nothing is
  left.
- **`stopped`**: an agent returned nothing (a limit). Launch nothing further and report it.
- **`notes`**: put them into the report verbatim (an unfinished ticket that closed its
  instance, a relay child the check refused, the Author's check_paper reminder).

## 3. Report

One line per ticket in `taken`: instance, id, route, outcome. Then the sweep counts,
`remaining` per instance, and anything parked on the human (`/academy:decide`).
