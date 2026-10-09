# The Author plugin's scripts, as the skills call them

`$S` below is `${CLAUDE_PLUGIN_ROOT}/scripts`; if the variable is not expanded, use
`~/.claude/skills/author/scripts`. The base plugin's scripts (`board.py`,
`packets.py`, ...) are at `${CLAUDE_PLUGIN_ROOT}/../academy/scripts`
(`academy/references/scripts.md`). Every script is stdlib Python 3.10 run with `py`,
writes LF, prints UTF-8, and finds the home from the cwd (`--home` overrides). Exit
code 0 is success, 1 "nothing found/ready" where noted, 2 an error with one line on
stderr. A skill reports a non-zero exit as it is and does not retry in a loop.

| Script | Used by | Command lines |
|---|---|---|
| `inbox.py` | inbox, status, notes, agenda, the agents | `[--n N] [--all] [--json] [--campaign TARGET]` (the inbox: exit 1 nothing to take; landings and released tickets first, the sweep step, the gap count) · `--check T-NNNN` (exit 3 unfinished). There is no roadmap and no filing command: tickets are filed with `board.py new` or `agenda.py gaps --file` |
| `routes.py` | inbox, gaps | the routing table (`route(meta)`, `land_route(kind)`, `check_filed(meta)`: an argument is asked as `research` to the Expert with `final_to: researcher`; `--tables`, `--sync FILE` generate the doc tables, `OUT_ROUTES`); a module, not a command |
| `gaps.py` | inbox, agenda, agenda_migrate | the gap logic and the one ticket-filing helper (`gaps`, `entry_tickets`, `file_gaps`, `file_ticket`); a module, not a command |
| `agenda.py` | agenda, status, presync | `check` · `status [--statuses FILE]` · `gaps [--json]` · `gaps --file [--dry-run] [--json]` (one ticket per gap, idempotent) · `milestones [--json]` · `show [--json]` |
| `agenda_migrate.py` | a one-shot conversion of an old `Drafts/roadmap.md` | `--roadmap OLD [--home HOME] [--apply] [--json]` (dry run unless `--apply`; the file is only read) |
| `check_paper.py` | tex_edit_check, commit_gate, build_gate, inbox, presync, status | `[--root HOME] [--strict] [--registry PATH] [--no-registry] [--no-log] [--config FILE] [--defaults] [--self-test]` |
| `commit_gate.py` | the PreToolUse hook; tex-engineer | (hook) · `--write-baseline [--root HOME]` |
| `build_gate.py` | the SubagentStop hook | (hook) |
| `tex_edit_check.py` | the PostToolUse hook | (hook) |
| `bib_gate.py` | the PreToolUse hook | (hook) |
| `pinned.py` | inbox, agenda, presync, the writer and editor briefs | `[--home H] [--library L] [--json]` · `--labels` (the statements a CONFIRMED review pinned: their environment is not edited, the proof is free; `.claude/pinned-release.txt` is the human's release list) |
| `pinned_guard.py` | the PreToolUse hook | (hook: refuses an edit that changes a pinned statement's environment) |

Library modules (imported, not run): `agenda_lib.py` (the agenda format), `_author.py` (hook
helpers: home and config, checker runs, baseline, dirty marker, build lock),
`_academy.py` (the vendored `academy_common`; never edit the copy, run
`academy/scripts/sync_common.py` after a lib change).

Tests: `py -m unittest discover -s ${CLAUDE_PLUGIN_ROOT}/tests -t ${CLAUDE_PLUGIN_ROOT}/tests`.
