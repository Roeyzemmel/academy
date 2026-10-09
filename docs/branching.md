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

When the hook says it did not run, or failed, run the scoped command it printed (with its
`--only`), from your own checkout's root. The unscoped run (no `--only`: every dirty
submodule and the board) is for the human or the session that owns the checkout.

## Working from a CLI session at the workspace root

One plain command per step, from the workspace root (the relative form is what the
allowlist matches; `py scripts/ship.py --help` lists the flags):

    py scripts/ship.py status                               # what is dirty / unpushed, per target
    py scripts/ship.py start <sub> <topic> [--role R]       # branch <date>/<topic>/<role> (--worktree for an isolated checkout)
    ... edit ...
    py scripts/ship.py ship <sub> -m "..." --paths P...     # commit + push (or `commit` and `push` separately)
    (human)  py scripts/ship.py merge <sub> <branch> --sha <tip> [-m MSG] [--bump]
    (human)  py scripts/ship.py publish <sub> --sha <main tip>

`<sub>` is a submodule path, or `board`. `--paths` are relative to the submodule (for
`board`, to the board's directory), not the cwd.

- `status`, `start`, `commit`, `push`, `ship` and `checkpoint` are allowlisted (the
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
