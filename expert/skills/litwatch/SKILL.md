---
name: litwatch
description: 'Literature watch for one paper or notebook: related-work-scout runs its keywords over the newest arXiv listings and logs hits in the library ledger; with an id, a prior-art search. Use weekly, before a coauthor round or submission, "has anyone done this".'
---

# Literature watch

`$ARGUMENTS` is an instance (default: the only Author instance in `workspace.json`),
or an instance and a statement id for a one-statement prior-art search
(`author@main paper:thm:main`). Budget: one scout run (`academy/references/budget.md`).
The scout writes only in the library home's `ledgers/<instance>/`.

The watch answers "what appeared since last time", so a paper that scoops part of the
draft is noticed in a week rather than by a referee. The per-statement search answers
"has this been proved already".

1. **Check the header exists**: `ledgers/<instance>/_header.md` in the library home
   (keywords, authors, anchor keys, the priority list of statements). If it is
   missing, say so and stop: the watch has nothing to search with.
2. **Dispatch one `related-work-scout`** (`subagent_type: expert:related-work-scout`),
   in the background:

   > Run the literature watch for `<instance>`. Cover new listings only: since the
   > newest `watch-*.md` in `ledgers/<instance>/`, or the last 30 days. The keyword
   > list, the authors and the anchor keys are in `ledgers/<instance>/_header.md`; run
   > all of them and say which listing pages you read and how deep. Sources in order:
   > the arXiv listing pages for the primary categories, a targeted search per
   > keyword, the recent-citations lists of the anchor entries. Write
   > `ledgers/<instance>/watch-<today>.md`; a watch with no hits still gets its file.

   For a statement: "Search for prior work on `<id>` ...", writing
   `ledgers/<instance>/<today>-<id-slug>.md`.
3. **Hits worth citing** come back as `cite` requests: relay them; each becomes
   `/expert:cite` or a `cite` ticket when Roey says so. A hit that overlaps a statement
   of the paper is reported first, with the statement's id.

## Scheduling it

By hand is the reliable one: run `/expert:litwatch` at the start of a working session
whenever the newest `watch-*.md` is more than a week old (the file names say it). A
desktop scheduled task (Windows Task Scheduler running `claude -p "/expert:litwatch
<instance>"` from the library home) runs weekly with file access; a session cron
dies with the session; a cloud routine cannot see the local library, so it is not a
home for this watch. Nothing schedules itself (`budget.md` rule 3).

## Report

The window covered, the pages and queries actually run, the hits ranked by overlap
with their verdicts and statement ids, the file written, and the explicit sentence
that absence of a hit is not evidence of novelty. Never ask questions.
