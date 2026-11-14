---
name: maintain
description: 'Measured maintenance round on the academy plugins: survey, fix, gate.'
---

# Maintain

A round of work on the academy's own code, for the human or a session that works for
them. `$ARGUMENTS` is empty (survey, then work the best candidates), `--survey` (only
show the candidates), or a description of the tasks to do. Scripts: `$S` as in
`${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. The branch and ship rules are
`docs/branching.md`; the round this was drawn from is
`docs/error-ledger-review-2026-11-13.md`.

## Before

1. From the workspace root, `py scripts/ship.py status`: the academy checkout must be
   clean. Its current branch is the round's **base** (`main`, or the tip of a stack still
   awaiting merge). A round never starts on a dirty checkout.
2. `--survey`, or to look first: `py $S/maintain.py survey` prints the candidates with
   their evidence (the error ledger's families, each daily command's seconds and
   characters against the budget, definitions the harness cannot read, worktrees left
   behind) and stops there.

## The round

Call the **Workflow** tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/maintain.js`
and `args: {root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>", workspace: "<the
workspace root>", base: "<the base branch>", cap: 4}`; add `tasks: [{slug, title, kind,
files, measure, why}]` when the human named the work (the survey and the plan are then
skipped). The script holds the round:

- **Survey and plan.** The candidates come from `maintain.py survey`; the plan keeps at
  most `cap` tasks, each one concern with the files it will touch and a measure that
  shows the problem now and gone afterwards. A candidate whose cause is outside this repo
  is skipped with its reason.
- **Lanes.** Tasks that touch the same file or folder share a lane and are stacked in
  order; tasks in different lanes run side by side, each in its own worktree
  (`ship.py start --worktree`), their push gates too.
- **Each task**: developed test-first by `scientist:developer` (measure, failing test,
  change, suites, measure again, commit); reviewed read-only by `scientist:test-engineer`,
  who did not write it; a blocking finding gets one fix round and a second look; then
  `ship.py push`, through the gate. A task still blocked, refused by the gate or lost in
  review is **not pushed**, and nothing is stacked on it.
- **Union.** `maintain.py union` merges the lanes' tips in a throwaway worktree and runs
  the gate on that: what `main` will hold once all are merged.

It needs the Scientist plugin (its developer and test-engineer). Without it, do the same
steps yourself in the same order; the script and `union` do not depend on the agents.

## After (the session's part)

1. Report per task: pushed or not and why, the before and after numbers, the review.
   `ok` is true only when every task was pushed and the union passed; `reason`,
   `dropped` and `skipped` say the rest. Do not relaunch a failed round: read the reason.
2. Open the pull requests in `pull_requests`, each lane bottom first, with the given
   head, base and body. A pull request is opened only on the human's word for it (asking
   for the round with pull requests is that word); otherwise list the branches.
3. Remove the worktrees in `cleanup` whose branch is pushed and clean
   (`git worktree remove`), and ship the board's error ledger if the round added to it
   (`py scripts/ship.py ship board --all -m "..."`).
4. Merging is the human's (`ship.py merge`, whose prompt is the approval). Resolving a
   ledger family the round fixed is the human's word too, after the merge
   (`error_ledger.py resolve --family ... --commit <sha>`).

## What a round never does

Commit to `main`, pass a gate with `--no-gate`, push a change nobody else read, change a
home's content (that is a ticket to the home's instance), change a registry status, or
resolve a ledger class.
