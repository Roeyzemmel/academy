---
name: litwatch
description: 'Literature watch for one paper or notebook: related-work-scout runs its keywords over the newest arXiv listings and logs hits in the library ledger; with an id, a prior-art search. Use weekly, before a coauthor round or submission, "has anyone done this".'
---

# Literature watch

`$ARGUMENTS` is an instance (default: the only Author instance in `workspace.json`),
or an instance and a statement id for a one-statement prior-art search
(`author@main paper:thm:main`). Budget: one scout run for a statement; for the watch, a planning run, at most four parallel searches (read-only) and one writing run (`academy/references/budget.md`).
The scout writes only in the library home's `ledgers/<instance>/`.

The watch answers "what appeared since last time", so a paper that scoops part of the
draft is noticed in a week rather than by a referee. The per-statement search answers
"has this been proved already".

1. **Check the header exists**: `ledgers/<instance>/_header.md` in the library home
   (the priority list of statements, and the search vocabulary below). The vocabulary
   is the header's `## Search vocabulary` block or, when the header has none, the one
   block with that heading under the watched home's `.claude/rules/` (an Author home
   may keep its paper's vocabulary there). If neither exists, say so and stop: the
   watch has nothing to search with.
2. **Run the workflow**: the Workflow tool with
   `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/litwatch.js` and
   `args: {instance: "<instance>"}` (add `statement: "<id>"` for a one-statement
   search, which stays one scout). Since 2026-10-31 the watch fans out (docs/workflows.md):
   - one return-only scout reads the header and the vocabulary;
   - the script splits the sources into at most four groups: the categories, the
     anchors, and the keywords with the authors that narrow them;
   - one return-only scout searches each group, in parallel;
   - the script dedupes the hits by arXiv id or DOI, keeping the sharper verdict;
   - one scout writes `ledgers/<instance>/watch-<today>.md` (a watch with no hits still
     gets its file).

   A search that was lost is named in the file. A file that appeared outside the
   writing stage comes back under `anomalies`: report it.
3. **Hits worth citing** come back as `cite` requests: relay them; each becomes
   `/expert:cite` or a `cite` ticket when the human says so. A hit that overlaps a statement
   of the paper is reported first, with the statement's id.

## The search vocabulary block

One block per watched instance, written by whoever owns the paper's or notebook's scope
(the human or the Author; the scout only proposes drift in its report). Four labelled
lines, items separated by ` · ` or commas, each optional except `Keywords`:

```markdown
## Search vocabulary

Keywords: first phrase · second phrase · third phrase · ...
Authors: Surname, Surname, ...        (searched with a keyword when a keyword alone is too broad)
Anchors: `KEY1`, `KEY2`, ...          (library keys whose citing lists are worth walking)
Categories: `math.DS`, `math.GT`      (primary arXiv listings; others in brackets)
```

`Keywords` are phrases searched one by one; `Authors` narrow a broad keyword; `Anchors`
are bibkeys of the library (`index.md`), whose recent-citations lists are walked;
`Categories` are the arXiv listing pages read for new submissions. The scout runs every
item and says which it ran.

## Scheduling it

Since 2026-10-31 a cloud scheduled task runs it weekly (Sundays 19:47 Asia/Jerusalem,
"Academy weekly Expert sources run"): a fresh session attaches the workspace (the library
is a submodule), runs this watch and at most three `cite`/`lookup` tickets, checkpoints the
library and the board, and sends a push notification. Its fetches stay on the allowlist
of sources (`scripts/source_guard.py --list`); those hosts must also be in the cloud
environment's Allowed domains, or the run reports them as denied. By hand still works:
run `/expert:litwatch` whenever the newest `watch-*.md` is more than a week old. Nothing
schedules itself (`budget.md` rule 3).

## Report

The window covered, the pages and queries actually run, the hits ranked by overlap
with their verdicts and statement ids, the file written, and the explicit sentence
that absence of a hit is not evidence of novelty. Never ask questions.
