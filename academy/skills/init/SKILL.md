---
name: init
description: 'Create a new academy instance: scaffold the home''s .claude/academy.json, register it in workspace.json, add .gitattributes and a board folder, and for a Researcher the notebook layout. Use for "/academy:init researcher@<domain>", "add a research domain".'
---

# Initialise an instance

`$ARGUMENTS` is `<role>@<name>`, optionally followed by the home path and the
domain(s). Scripts: `$S` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. The
config fields are `docs/config.md`; the notebook layout is plan section 3.3.

1. **Collect** the instance name, the home (absolute path; default the cwd), the
   domain pack(s) (`domains/<name>/` in the academy repo) and, for a role with a
   registry, the namespace (default the instance's name). If any is missing or
   ambiguous, ask Roey with one `AskUserQuestion`.
2. **Dry run.** `py $S/init_instance.py <instance> --home <home> --domain <d> [--ns
   <ns>] --dry-run`. Show the config it would write and the steps.
3. **Confirm** with `AskUserQuestion`: write it, or stop. The home may belong to
   Roey's work: never pass `--force` unless he asked to overwrite an existing
   academy.json.
4. **Write.** The same command without `--dry-run`. Print its report.
5. **Check.** `py $S/academy_status.py --instances-only`; the new instance must read
   `ok`.
6. **Tell Roey** what is left by hand: the role-specific settings the template leaves
   generic (an Author's coauthor note macros, CRLF files, checker baseline, and the
   human's taste in the scaffolded `Drafts/vision.md`, `author/references/aesthetic-vision.md`; a
   Scientist's environment profiles and `knownCases`, and in the scaffolded lab
   (`scientist/templates/lab/`) the libraries `env.py` records and the scope defaults of
   `experiments/README.md`; an Expert's library `README.md` additions; an Expert's `bibs`), editing
   the home's `CLAUDE.md` to point at `.claude/academy.json`, and committing the new
   files in the home (he commits). If the home already had files before the new
   `.gitattributes`, run `git add --renormalize .` there first, and check
   `git ls-files --eol` for anything listed as `-text` that should be text.

Nothing is committed by this skill. The workspace.json change is in the academy repo
and the board folder is in the board repo; both show up as uncommitted changes.
