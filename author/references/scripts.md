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
| `gaps.py` | inbox, agenda | the gap logic and the one ticket-filing helper (`gaps`, `entry_tickets`, `file_gaps`, `file_ticket`); a module, not a command |
| `agenda.py` | agenda, status, presync | `check` · `status [--statuses FILE]` · `gaps [--json]` · `gaps --file [--dry-run] [--json]` (one ticket per gap, idempotent) · `milestones [--json]` · `show [--json]` |
| `check_paper.py` | tex_edit_check, commit_gate, build_gate, inbox, presync, status | `[--root HOME] [--strict] [--registry PATH] [--no-registry] [--no-log] [--config FILE] [--defaults] [--self-test]` |
| `paper_diff.py` | presync | `--root HOME [--base REF] [--out FILE] [--no-build] [--json]` (coloured-diff PDF of the whole paper, `\input` files flattened, against `--base`, else `author.diff.base`, else the newest `shared-*` / `round-*` / `submitted-*` tag; the base is exported with `git archive`, the home is never touched; writes `<build.dir>/diff/<main>-diff.tex` and `.pdf` and prints the PDF path, the `.tex` with `--no-build`; exit 1 no base, or latexdiff / build failed (log tail and the `.tex` path on stderr), 2 an error) |
| `commit_gate.py` | the PreToolUse hook; tex-engineer | (hook) · `--write-baseline [--root HOME]` |
| `build_gate.py` | the SubagentStop hook | (hook) |
| `tex_edit_check.py` | the PostToolUse hook | (hook) |
| `pre_tool_use.py` | the PreToolUse hook (Edit/Write/MultiEdit/NotebookEdit) | (hook: one process per edit; reads the event once and calls the guards' `decide(event)` in order, the first denial wins, a guard that raises is skipped with a line on stderr: Edit/Write/MultiEdit `bib_gate`, `pinned_guard`, `preamble_guard`, `notation_scope_guard`, `note_length_guard`; NotebookEdit `notation_scope_guard`. Each guard still runs standalone) |
| `bib_gate.py` | `pre_tool_use.py`; standalone | (hook) |
| `statement.py` | the writer, editor and sweeper (reading the tex); any agent that needs one statement | `<label>... [--proof] [--context N] [--json]` (the statement's environment with file and lines, and the proof that follows) · `<label>... --where` (one line: the file and the line ranges of the statement and its proof, for a brief) · `--outline FILE` (the labelled statements and headings of one tex file with their lines). Exit 1 when a label is not found (near labels named) |
| `pinned.py` | inbox, agenda, presync, the writer and editor briefs | `[--home H] [--library L] [--json]` · `--labels` (the statements a CONFIRMED review pinned: their environment is not edited, the proof is free; `.claude/pinned-release.txt` is the human's release list) |
| `pinned_guard.py` | `pre_tool_use.py`; standalone | (hook: refuses an edit that changes a pinned statement's environment) |
| `note_length_guard.py` | `pre_tool_use.py`; standalone | (hook: refuses an edit that adds a machine note longer than `author.notes.maxLines` margin lines, estimated at `author.notes.lineChars` characters a line; narrowing a long note passes, a note already in the paper's tex (moved or copied) passes; opt-in: only with `author.notes.enforce: true`) |
| `sweep.py` | the note-sweeper, sweep, inbox (its Sweep stage) | `[--home H] [--board DIR] plan [--full] [--limit N] [--max-age DAYS] [--json]` (the notes to act on, by kind: `retire` (an `await` note whose ticket ended with a result: delete, or a pointer for a negative outcome), `move` (a `prov` note: record its text, then delete), `judge` (the rest, by the sweeper's rule), `waiting`, `human` (the human's list); only tex files changed since the last complete sweep and notes whose cached verdict no longer holds; first line `sweep: todo N (...)`; nothing to do records itself) · `record [--unjudged SIG...]` (after the pass: cache the judged-open notes, advance the recorded commit when the sweep is complete) · `inventory [--json]` (counts by file and kind, over the cap; read-only). State: `<home>/.academy/note-sweep.json` (machine-local) |

Library modules (imported, not run): `agenda_lib.py` (the agenda format), `machine_notes.py`
(the machine notes of the tex: typed `\Claude[kind]{...}` or untyped, kinds, signatures, the
line estimate), `_author.py` (hook
helpers: home and config, checker runs, baseline, dirty marker, build lock),
`_academy/` (the vendored `academy_common` package; never edit the copy, run
`academy/scripts/sync_common.py` after a lib change).

Tests: `py -m unittest discover -s ${CLAUDE_PLUGIN_ROOT}/tests -t ${CLAUDE_PLUGIN_ROOT}/tests`.
