# Handoff: continuing the maintenance round in another session

Written 2026-11-14, at the end of the session that did the round recorded in
`error-ledger-review-2026-11-13.md` (the full record: every pull request in merge order,
each measurement, the human's list). This note is what a new session needs to go on
without the old one's memory.

## Where things stand

- **The academy repo**: the chain of pull requests #23 to #81 was merged into `main` by
  the human on 2026-11-14 (one merge of its tip), together with a campaign branch of the
  ticket sessions. **Work from `main`**: `git -C academy fetch origin main`, then a new
  branch with `py scripts/ship.py start academy <topic> --role human`. A fresh checkout
  of the workspace may still put the academy submodule at an older commit until the
  human bumps the pointer; the session's first line says when the checkout is behind.
- **The workspace repo**: branch `2026-11-13/ship-docs/human` (its docs, the cloud TeX
  script, the session's error ledger under `board/.errors`).
- **The lab, the notebook, the paper**: one branch each from 2026-11-13
  (`tests-skip-optional`, `library-path`, `forgetful-clause`), untouched since. Content
  of the homes is not this work's to change: it goes to the home's instance as a ticket.
- Nothing is uncommitted and there are no worktrees.

## Not done, in order of weight

1. **Nothing of this has run on the human's Windows machine.** Everything ran on Linux
   with Python 3.11 and 3.13. The smoke run after merging: one shell command and one
   edit (the hook dispatchers), `ship.py start --worktree` and one `push` (the gate needs
   Git Bash), `/author:presync` (the diff).
2. **The new behaviour has not run in a real inbox session**: the run's budget (rule 7),
   an unfinished ticket skipping only itself, `decisions.py proceed`. Their tests pass;
   the first real `/academy:inbox` after the merge is the test. Read its `budget`,
   `notes` and `taken` against `skills/inbox/SKILL.md`.
3. **`/academy:maintain` has not run for real**, in either mode.
4. **The human's own list** is at the end of the record. The chain is merged; what
   still blocks others: bump the workspace's academy pointer and run `scripts/bootstrap.py`
   on each machine; allow `mcp__plugin_academy_academy__tickets_update` (a session cannot
   write its own permission rules; about a hundred open tickets cannot start without
   it); look at `expert:rigor-reviewer` in a new session's agent list and decide about the
   proof reviews run since 2026-10-31.
5. **Left open on purpose**: the proof-structure redesign (the human writes an example
   proof first); shortening the agent descriptions (they carry the guard rails, so it is
   a pass to do together); the `mcp__academy__` tool names in the agent files (needed
   only if the server is still registered outside the plugin anywhere).

## How to go on

- **A maintenance task**: `/academy:maintain` (its skill is the procedure; `--survey`
  shows the candidates with their evidence). By hand the steps are the same: measure,
  one concern per branch, a failing test first, the suites, measure again, someone who
  did not write it reads it, push through the gate.
- **The latest errors**: the ticket sessions' ledger records are on their own branches
  of the workspace repo until those are merged (`2026-11-14/campaign/author` and the
  per-ticket branches). `maintain.py survey` reads only the checked-out board, so fetch
  those branches and compare `board/.errors/*.jsonl` when the survey looks stale.
- **Shipping**: `py scripts/ship.py` from the workspace root, never raw `git commit` or
  `git push` (a hook refuses them). `start <sub> <topic> --role human` stacks on the
  current branch; `ship <sub> --all -m "..."` commits and pushes through the gate, which
  runs the repo's own CI files (about a minute for the academy repo). To keep working
  during a gate: `commit`, then `start ... --worktree`, then `push --repo <the committed
  checkout>` in the background. Read a background push by its own exit status; a pipe
  through `tail` hides a refusal.
- **Pull requests**: one per branch, base = the branch below it, opened only on the
  human's word. After a change, add its row to the merge-order table of the record.
- **Commit messages and pull requests** say what was wrong, what changed and the
  numbers before and after. No model name in anything pushed.

## What this session learned the hard way

- **Measure on the live board, not on fixtures.** Every large finding of the round came
  from running the real commands on 1200 tickets: the listings that took minutes, the
  outputs of hundreds of thousands of characters, the packets never asked.
- **Passing suites are not a review.** An agent that had not written the code found four
  defects in changes whose tests all passed. Give it the diff range and no conclusions.
- **Compare outputs, not only timings**, when a change is meant to keep results the
  same: byte for byte against the old code on live data.
- **Count what a split or a filter drops.** Splitting a suite by file name silently lost
  two test files until the counts were compared.
- **A checkout being gated must not change under the gate.** Use another worktree.
- **Look at `main` before a push, not only at the start.** It moved by nine commits
  during this session (the human merged the chain), and six tests that read how far the
  checkout was behind failed until they were made independent of it.
- **A session does not write permission rules**, its own or the workspace's. Propose
  the line to the human.
- **After every change, the repos are left clean**: the board's error ledger grows while
  a session works and is shipped with `ship.py ship board --all`.
