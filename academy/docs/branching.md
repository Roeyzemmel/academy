# Branching and shipping in an academy workspace

How work done in a workspace reaches its repositories. A workspace is a superproject: the
academy plugins, the Expert's library and the instance homes are git submodules, each
with its own remote; the board's files (packets, deep-dives, the error ledger) are either
a plain directory of the superproject (`board/`) or, in older workspaces, a submodule of
their own. The tool is the academy's `academy/scripts/ship.py`; a workspace runs it
through its one-line shim `scripts/ship.py` (`templates/workspace/scripts/`), so the
allowlisted `py scripts/ship.py ...` commands match. A project's own `CLAUDE.md` says who
the human reviewer is and anything particular to it.

## The rules

- **Never commit to `main` (or `master`) of any repository, and never touch the
  superproject's submodule pointers.** Pointers move only through the human-run
  `merge --bump`.
- In every repository you changed, create or reuse the branch
  `<YYYY-MM-DD>/<topic>/<role>` (UTC date, kebab-case topic), where role is the role that
  did the work: `author`, `expert`, `researcher`, `scientist`; collaborators use `human`
  and their own commit author. Commit there and push it. The human reviews and merges;
  such a branch overrides a home's "nobody commits" line for that branch only.
- The board's files are ordinary commits too: of the board submodule, or, when `board/`
  is a plain directory of the superproject, of `board/` paths in the superproject on a
  template branch. `ship.py`'s target `board` stages and commits nothing outside the
  board's directory, and never a submodule pointer, whatever else is dirty or staged.
  With `board.backend` `github` the tickets live on GitHub (changed through the board
  tools), but packets and deep-dives stay files and are committed this way; every
  checkpoint commit then carries a `Ticket: OWNER/NAME#N` line, so it shows on the
  ticket's issue.
- In a cloud session a repository may be a separate checkout attached next to the
  workspace (`workspace.json` says where); commit and push in that checkout.
- End a session with the list of branches pushed, per repository.

## After each inbox ticket: the checkpoint

`py scripts/ship.py checkpoint --ticket <id> --role <role>` commits and pushes the
ticket's work on `<date>/<ticket-id>/<role>`. An academy plugin with the checkpoint hook
runs it itself from the inbox's `--check` step, scoped with `--only` to the ticket's
targets (its home's submodule, `board`, and `library` for the Expert), and only when the
session runs inside that workspace (opt out: `"shipCheckpoint": false` in
workspace.json). Under `--only`:

- the other repositories are not looked at;
- a dirty repository still on `main` is refused: start a branch first
  (`py scripts/ship.py start <sub> <topic>`);
- a dirty repository on a branch that is neither `main` nor a template branch is refused
  without switching;
- untracked nested repositories and worktrees, and submodule pointers, are never
  committed (they are listed as skipped).

**Stacked, not forked** (#130, 2026-11-27). A ticket branch is started from whatever
branch the checkout is on, so with parallel runs and the main session shipping between
them, a new one could fork from a branch that lacks the other tickets' work. After its
commit, a checkpoint therefore merges in every recent (7 days) local
`<date>/<topic>/<role>` branch whose tip the ticket's branch and `main` both lack; ledger
and counter conflicts are resolved as `sync` does. A branch it cannot merge stays a fork
and is printed as `FORK: ...` with the reason: a real conflict (the merge is aborted), a
worktree with other uncommitted changes (nothing is merged then), or, for `board`, a
branch that changes files outside `board/`. `ship.py stack` lists the forks of the
current branch (local and `origin/`) under its stack, and `status` counts them.

**The manifest** (#101 part 1, 2026-11-20). Before each ticket that launches an agent, the
inbox workflow's clerk runs `manifest.py snapshot --ticket <id> --run <run>`: every home's
dirty set (each submodule, and the board's directory) with a content hash per path, written
as the run's claim `<workspace>/.academy/run-claims/<run>-<id>.json` (a self-ignoring
directory; one file per run and ticket, so concurrent runs never overwrite each other's
claim; a home whose `git status` fails is recorded as such and nothing of it is claimed:
the check says so). Two runs working at once in one checkout can still attribute each
other's files to their tickets: a snapshot diff cannot tell who changed a path. The
ticket's `--check` diffs it: the paths that were clean before the ticket, or whose content
changed during it, plus the ticket's touch-ledger entries, are its manifest
(`.academy/manifests/<id>.json`), and `ship.py checkpoint --manifest <file>` commits exactly
those, in **every** home that has any (a verify's evidence row in the paper's claim record
included), on the ticket's branch. A path dirty before the ticket and unchanged is not the
ticket's and stays as it is. The rules above hold per home (a home dirty on `main` is
refused, a home with other uncommitted work is not moved); a refused home's part stays in
the manifest for the next `--check`. A ticket that ends blocked, unfinished or lost is
committed and pushed too, as `WIP: <id> unfinished (<outcome>)`. A ticket the inbox did not
snapshot (a standalone skill run, `snapshot: false`) is checkpointed by `--only` as before.

**The stop check** (`stop_check.py`, a `Stop` hook of the academy plugin, opt-in with
`"stopCheck": true` in workspace.json) lists the dirty paths of every home except those a
live claim's run changed since its snapshot; a claim older than 6 hours, or whose pid of
this host is gone, is stale, hides nothing and is removed at the next snapshot or `--check`.
A file above 5 MB is compared by size and mtime, not hashed. By hand: `manifest.py unclaimed`. Claude
Code's own cloud stop check (`~/.claude/stop-hook-git-check.sh`) is not the academy's and
does not read the claims.

**Usage on the board.** When `board` is part of a checkpoint, `ship.py` first appends one
content-free summary per recently active session of this machine (session id, instance
bucket, turns, cache read/write, models, subagent counts, a hashed host; never prompts,
paths or tool inputs) to `board/.usage/<instance>.<host>.jsonl`, so cloud sessions show up in
`usage_report.py` (`--no-board` skips them). The ordinary `add -A -- board/` staging commits
it like `.errors/`. A record is appended only when its session's turns or cache read
changed; readers take the last record per session. The same step compacts this host's files (only the last record per session is kept and sessions idle for more than `usageKeepDays`, default 90, are dropped; by hand: `usage_ledger.py compact`). Opt out with `"usageCheckpoint": false`
(or `"shipCheckpoint": false`) in workspace.json; a failure is a warning, never a failed
checkpoint.

**Writes in another role's home** (2026-11-13). Some routes write, legitimately, in a
home that is not the acting role's: the Expert's librarian adds an entry to an Author
home's `references.bib` (`cite`); a review chair, the librarian or the claim-keeper
writes an evidence row or a status into the registry of whichever home owns the claim's
namespace (`claims_attach_evidence`, `claims_set_status`, `claims_new`; for example an
Expert `verify` on a `paper:` claim, a Researcher `review-experiment` on a `lab:` claim).
Those files are shipped with the ticket, and nothing else there:

- They are recorded when they are written, in the **touch ledger** (one small file per
  write under `~/.claude/academy/touched/<workspace>/`, `$ACADEMY_TOUCHED_DIR` overrides;
  never in a repo): by the `touch_record` hook for an agent's Edit or Write in a home of
  another role, and by the MCP server for the files a claims write changed in such a home
  (the home's uncommitted files compared before and after the call). The main session's
  own edits are the human's and are never recorded.
- The `--check` of a finished ticket claims the role's unclaimed entries for that ticket
  (the inbox works one ticket at a time) and passes them as `--touched SUB:PATH`. In
  each such repo only those paths are staged and committed, on the same
  `<date>/<ticket-id>/<role>` branch, where role is the acting role (an Expert's bib entry
  lands on `.../expert` in the paper repo), through that home's commit gate and push gate.
- The repo is refused, and nothing is shipped there, when it is on `main`, or when it
  would have to switch to the ticket's branch while anything else in it is uncommitted
  (a switch would carry that work onto the ticket's branch). Already on the ticket's
  branch, only the paths are committed. The entries then stay with that ticket, so its
  next `--check` retries them and no other ticket takes them; a shipped repo's entries
  are dropped. Entries are pruned after 14 days.
- `"shipCheckpoint": false` switches this off with the rest (nothing is recorded or
  shipped).

**Unpushed branches hold delivery back** (#101). A developer works in a worktree on a
branch named for the ticket and ends with `py scripts/ship.py push <sub> --repo
<worktree>`. After the checkpoint, the `--check` of a delivered ticket refuses to report
it delivered (exit 3, `unfinished (delivered, unpushed)`) while any local branch naming
the ticket, in any submodule or the superproject, has commits on no remote, or its
worktree has uncommitted changes; each such branch is listed with the command that pushes
it. Opt out: `"unpushedCheck": false` in workspace.json.

When the hook says it did not run, or failed, run the scoped command it printed (with its
`--only` and any `--touched`), from your own checkout's root. The unscoped run (no `--only`: every dirty
submodule and the board) is for the human or the session that owns the checkout.

## Working from a CLI session at the workspace root

One plain command per step, from the workspace root (the relative form is what the
allowlist matches; `py scripts/ship.py --help` lists the flags):

    py scripts/ship.py status [--all]                       # what is dirty / unpushed, per target and per worktree
    py scripts/ship.py start <sub> <topic> [--role R]       # branch <date>/<topic>/<role> (--worktree for an isolated checkout)
    ... edit ...
    py scripts/ship.py ship <sub> -m "..." --paths P...     # commit + push (or `commit` and `push` separately)
    py scripts/ship.py start <sub> <next topic>             # on a template branch: stacked on it (--on BRANCH names the base)
    py scripts/ship.py stack <sub>                          # the chain, bottom first, and each pull request's head and base
    py scripts/ship.py sync <sub> [--from main]             # origin/main into the work branch (ledgers resolved); then push
    py scripts/ship.py sync <sub> --continue                # after resolving a conflict it stopped on: record the merge
    (human)  py scripts/ship.py merge <sub> <branch> --sha <tip> [-m MSG] [--bump]
    (human)  py scripts/ship.py bump <sub>... --sha <main tip>... # pointers to published mains, no merge
    (human)  py scripts/ship.py publish <sub> --sha <main tip>

`<sub>` is a submodule path, `board`, or `workspace` (the workspace repo's own files:
everything but the board and the submodules; never a submodule pointer; not part of a
`checkpoint`). `--paths` are relative to the submodule (for
`board`, to the board's directory), not the cwd.

- **The tool is the default, by a hook** (`ship_guard`, 2026-11-13): in the workspace
  repo and in every submodule checkout (and its worktrees), a shell `git commit`, `git
  push` or new branch (`git switch -c`, `git checkout -b`, `git branch <new>`) is denied
  with the `ship.py` command that does it. Reading, staging, stashing and switching to an
  existing branch are untouched, and so is any repository outside the workspace.
  `"shipGuard": false` in workspace.json switches it off.
- **A work branch behind main** (#91, #119): `sync <sub>` merges `origin/main` into the
  current work branch. The append-only ledgers (`.errors/*.jsonl`: the union of the
  lines) and the counters (`.ids/*`: the larger number) are resolved by it; any other
  conflict stops it with the files listed and the merge in progress. Resolve them,
  `git add` each, then `sync <sub> --continue` records the merge (a `commit --paths` is
  refused during a merge, and the guard denies a shell `git commit`). Then `push`.
- **Work left in a worktree** (#101): `status` ends with the linked worktrees of every
  submodule and of the superproject that hold work not on a remote: uncommitted changes
  (`dirty`, untracked files included), commits on no remote-tracking branch
  (`unpushed`), or a branch ahead of its upstream (`ahead`), with the path (relative to
  the checkout when it is inside it), the branch and `missing` when the directory is
  gone. A clean, pushed worktree is not shown; `status --all` lists it too, marked
  `removable`. Nothing is fetched (the remote-tracking refs as they are) and no index is
  rewritten (`--no-optional-locks`), so the scan never races a commit in that worktree.
  A developer's run ends with its worktree off that list: `push`, or say what is left.
- **A legacy branch name** (uppercase or `_` in the topic, made before `start`
  lowercased topics) is merged by `merge` with a warning (#120).
- **A stack of pull requests.** A `start` made on a template branch records that branch
  as the new one's base; `stack <sub>` prints the chain and, for each branch, the pull
  request it wants: its head, and as base the branch under it (`main` only for the
  bottom one). Open them bottom first, with the session's GitHub tool or `gh pr create
  --head H --base B`; `ship.py` opens none. Merge bottom first too; after a merge the
  next one's base is retargeted to `main`.
- **The push gate.** Nothing runs on GitHub for these repos, so `push`, `ship` and
  `checkpoint` run the repo's CI here first. The workflow files stay the one description
  of the checks: the gate runs the `run:` steps of every `.github/workflows/*.yml`
  triggered by `push` (`academy/scripts/ci_local.py`: the runner's setup and install
  steps are skipped, `python` is this machine's interpreter, `CI=true` is set, a step
  that needs GitHub's context is skipped with the reason), refuses the push when a step
  fails and keeps the commit. A tree that passed is not gated again. The jobs of a
  workflow run side by side (`CI_LOCAL_JOBS=1` for one after another), which is why this
  repo's suites are several jobs: its gate takes about a minute, where the one job took
  four and a half. To change what is
  checked, edit the workflow file; `py academy/scripts/ci_local.py list --repo <dir>`
  shows what will run here and `run` runs it by hand. A repo's `ship.json` is optional:
  `{"pushGate": false}` for no gate, or a list of extra local-only steps.
  `"pushGate": false` in workspace.json switches the gate off for the workspace; `push
  --no-gate` skips it with a warning, on the human's word only.
- **Not waiting for the gate.** The gate checks the checkout it runs in, so that
  checkout must not change under it. To keep working: `commit`, then `start <sub> <next
  topic> --worktree --repo <the checkout just committed>` (the new branch is stacked on
  it, in its own worktree under `<sub>/.claude/worktrees/`, wherever it was started
  from), then `push <sub> --repo <the checkout just committed>` in the background, and
  go on in the new worktree. Read the push's own exit status and last lines when it
  ends (a pipe through `tail` hides a refusal). `commit`, `push` and `ship` take the
  same `--repo`.
- `status`, `start`, `commit`, `push`, `ship`, `stack` and `checkpoint` are allowlisted (the
  workspace bootstrap renders the rules from `templates/workspace/permissions.json` into
  `.claude/settings.local.json`).
- `merge`, `publish` and `accept-baseline` are not: they always raise a permission
  prompt, and that prompt is the approval. Give them the exact `--sha` of the reviewed tip
  (`push` prints it; `merge` prints the `main` tip to publish); a command with a different
  tip is refused. If auto mode denies the prompt, the human runs it in the session as
  `! py scripts/ship.py merge ...`.
- `accept-baseline <sub>` (Author homes) rewrites the commit gate's baseline after its
  findings were reviewed.
- `ship`/`commit` accept `--no-gate`, which skips the Author commit gate without a
  prompt and only prints a warning; do not use it unless the human said so.

## Where the workspace root comes from

`ship.py` takes `--workspace DIR` (the shim always passes its own root), else the nearest
directory at or above the cwd holding `workspace.json` (or `workspace.template.json`),
else `$ACADEMY_WORKSPACE`, else the directory holding the academy checkout when that is a
workspace, else the nearest directory above the cwd with a `.gitmodules`.

## Setting a workspace up

`templates/workspace/` holds what a workspace copies: `scripts/ship.py` and
`scripts/bootstrap.py` (shims that find the academy checkout: `$ACADEMY_ROOT`, the
workspace's `academy/` submodule, or an `academy` checkout next to the workspace) and
`scripts/cloud-setup.sh` (the cloud environment's setup script). The bootstrap
(`academy/scripts/workspace_bootstrap.py`) writes `workspace.json` from
`workspace.template.json`, passing through every key it does not resolve itself
(`human`, `grading`, `compute`, `plugins`, ...), and renders the permission rules:
`templates/workspace/permissions.json` merged with the workspace's own
`workspace.permissions.json` (same keys; its rules are appended).
