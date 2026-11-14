---
name: maintain
description: 'Measured maintenance round on the academy plugins: survey, fix, gate.'
---

# A maintenance round

Work on the academy's own code, for the human or a session that works for them. It is
run on purpose only ("a round on the academy", "fix the ledger errors", "optimise the
plugins"). `$ARGUMENTS`: empty (survey, then work the best candidates
yourself), `--survey` (show the candidates and stop), `--workflow` (fan the tasks out to
agents), or a description of the tasks. `$M` is `${CLAUDE_PLUGIN_ROOT}/scripts`; the
academy repo is `${CLAUDE_PLUGIN_ROOT}/..`. The branch and ship rules are
`docs/branching.md`.

## 1. Survey (always)

From the workspace root: `py scripts/ship.py status` (the academy checkout must be clean;
its branch is the round's **base**), then `py $M/maintain.py survey`. It prints, in a
screen: the error ledger's families with an error this week or a regression; each daily
command's seconds and characters on the live board, and which are over budget (5 s,
20 000 characters); definitions the harness cannot read; worktrees left behind.

Pick at most four tasks, the most valuable first. One task is one concern. Before
naming one, read the code: say which files it will change and the **measure** that shows
the problem now and will show it gone (a command with a number, or a failing case). Skip,
and say so, what is not this repo's (a home's own text, the network, the harness, a
decision that is the human's) and what an older checkout recorded and the base already
fixes. With `--survey`, stop here.

## 2. The round, yourself (the default)

Light on context: you read the survey, the files of one task at a time, and one review.
For each task, in order:

1. `py scripts/ship.py start academy <topic> --worktree` (on the base, or on the branch
   of a task whose files it shares). Work only in that worktree.
2. Take the measure. Write the test that fails, then the change. Run the suites of the
   plugins you touched and `ruff check .`. Take the measure again; on live data the
   output must be the same wherever it is not what you changed.
3. `py scripts/ship.py commit academy --repo <worktree> --all -m "..."`: what was wrong,
   what changed, the before and after numbers.
4. **Someone who did not write it reads it.** Launch one agent (`scientist:test-engineer`
   when installed, else a general one) with the diff range and no conclusions of yours:
   wrong results, inputs that crash, callers that relied on what changed; read-only. Fix
   what it reproduces, with a test, in a commit of its own.
5. `py scripts/ship.py push academy --repo <worktree>` in the background, and start the
   next task meanwhile: the gate checks that worktree, which you no longer touch. Read
   the push's own exit status when it ends.

When tasks were made side by side from one base, finish with
`py $M/maintain.py union --base <base> --branches <each lane's last branch>`: they are
merged in a throwaway worktree and gated together.

## 3. The round, fanned out (`--workflow`)

Call the **Workflow** tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/maintain.js` and
`args: {root: "<the academy repo, absolute>", workspace: "<the workspace root>", base:
"<the base branch>", cap: 4}`; add `tasks: [{slug, title, kind, files, measure, why}]`
when they are already chosen (the survey and plan stages are then skipped). The script
applies the plan's rules, puts tasks that share a file in one stacked lane and runs the
lanes side by side; each task is developed by `scientist:developer`, reviewed by
`scientist:test-engineer`, gets one fix round and a second look for a blocking finding,
and is pushed through the gate; a task still blocked, refused or unreviewed is not pushed
and nothing is stacked on it; `union` gates the lanes together. It needs the Scientist
plugin. Do not relaunch a failed round: read `reason`, `dropped` and each task's reason.

## 4. After

1. Report per task: pushed or not and why, the before and after numbers, what the
   review found.
2. Pull requests, each lane bottom first (the workflow returns them in `pull_requests`),
   only when the human asked for them; otherwise list the branches.
3. Remove the worktrees whose branch is pushed and clean; ship the board's error ledger if
   the round added to it (`py scripts/ship.py ship board --all -m "..."`).
4. Merging is the human's (`ship.py merge`). So is resolving a ledger family the round
   fixed, after the merge.

## Never

Commit to `main`; pass a gate with `--no-gate`; push a change nobody else read; change a
home's content (that is a ticket to the home's instance) or a registry status; resolve a
ledger class; edit permission rules.
