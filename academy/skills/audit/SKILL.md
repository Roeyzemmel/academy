---
name: audit
description: 'Read-only audit: board and registry states that contradict their evidence. Use for "audit".'
---

# Academy audit (#111)

Scripts: `$S` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Read-only.

1. `py $S/audit.py` (`--json` for the rows; `--class C` for one class; `--limit 0` for
   every row; `--no-tickets` / `--no-packets` / `--no-registry` to skip a source; the
   ticket listing on the GitHub board takes about half a minute).
2. Show the report as it is: per class the count, the first rows with the suggested fix,
   and the "Not audited" lines (a home whose claims could not be read is named, never
   left out silently).
3. Fix nothing here. Each fix is a move the class names: a release through `/academy:board`,
   a renumbered packet, a reword verify (`registry.py stale --file-reword`), or a decision
   for the human (`claim-no-positive-pass`: a blind verify, or the status reverts). Offer
   the moves; make one only on the human's word.

The classes and what each means are the script's docstring (`audit.py --help`).
Not covered yet: the draft colour against the registry status, and tickets cancelled
although their work was delivered.
