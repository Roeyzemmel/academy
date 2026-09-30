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
| `inbox.py` | inbox, status, notes, agenda, the agents | `[--sync] [--n N] [--all] [--json] [--campaign TARGET]` (the inbox: exit 1 nothing to take) · `--check T-NNNN` (exit 3 unfinished) · `sync [--dry-run]` (file the ready items once; settle delivered self-tickets) · `file R-NNNN [--dry-run]` · `mark R-NNNN [--status S] [--note T] [--ticket T-NNNN]` · `add --tag T --title T [--attach ID] [--priority P] [--depends-on a,b] [--route AGENT] [--source S] [--body T]` |
| `routes.py` | inbox | the routing table (`route(meta)`, `land_route(tag)`); a module, not a command |
| `agenda.py` | agenda, status, presync | `check` · `status [--statuses FILE]` · `gaps [--json]` · `milestones [--json]` · `show [--json]` |
| `agenda_migrate.py` | the first paper's switch-over (phase 5) | `--roadmap OLD --out DIR [--paper-root HOME] [--statuses FILE \| --claims-cmd CMD] [--instance I] [--ns NS] [--date D]` |
| `check_paper.py` | tex_edit_check, commit_gate, build_gate, inbox, presync, status | `[--root HOME] [--strict] [--registry PATH] [--no-registry] [--no-log] [--config FILE] [--defaults] [--self-test]` |
| `commit_gate.py` | the PreToolUse hook; tex-engineer | (hook) · `--write-baseline [--root HOME]` |
| `build_gate.py` | the SubagentStop hook | (hook) |
| `tex_edit_check.py` | the PostToolUse hook | (hook) |
| `bib_gate.py` | the PreToolUse hook | (hook) |

Library modules (imported, not run): `agenda_lib.py` (the formats), `_author.py` (hook
helpers: home and config, checker runs, baseline, dirty marker, build lock),
`_academy.py` (the vendored `academy_common`; never edit the copy, run
`academy/scripts/sync_common.py` after a lib change).

Tests: `py -m unittest discover -s ${CLAUDE_PLUGIN_ROOT}/tests -t ${CLAUDE_PLUGIN_ROOT}/tests`.
