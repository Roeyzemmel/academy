---
name: litwatch
description: The scheduled literature watch — run related-work-scout over the paper's keyword list against the newest arXiv listings and append the hits to Drafts/related_work.md under a dated "Watch" heading. Also explains how to schedule it. Use weekly, before a coauthor round, and before submission.
---

# Literature watch

`related-work-scout` normally answers "has this been proved already?", one label at a
time. The watch is the other mode: a standing sweep of what appeared *since last time*,
so a paper that scoops a piece of the draft is noticed in a week rather than by a
referee.

Dispatch `related-work-scout` (`subagent_type: related-work-scout`), in the background.

## The brief

> Run the literature watch. Cover **new listings only**: everything posted since the
> date of the last "Watch" heading in `Drafts/related_work.md`, or the last 30 days if
> there is none. The keyword list, the author names and the anchor bib keys are in the
> header of that ledger — run all of them and say which listing pages you actually read
> and how many entries deep you got.
>
> Sources in order: the arXiv listing pages for the paper's primary categories, then a
> targeted search per keyword, then the recent-citations lists of the anchor entries.
>
> For each hit: authors, title, date, arXiv id, the abstract quoted, the statement of
> the draft it touches (by label, from the priority list at the top of the ledger), and
> a one-line verdict — same result / special case / generalisation / same technique /
> only related.
>
> Append under a heading `## Watch YYYY-MM-DD` with the covered window, the pages read,
> the queries run, and the hits. **A watch with no hits still gets its heading and its
> query list.** Do not edit `sections/` or `references.bib`; a hit that deserves citing
> becomes a roadmap item.

## Scheduling it

**By hand** is the reliable one: run `/paper:litwatch` at the start of a working session
whenever the last "Watch" heading is more than a week old. The dated headings are the
record — the top of the ledger says immediately whether the watch is behind.

**A desktop scheduled task** runs locally, weekly, with file access, and persists
across sessions; it only runs while the machine is awake, and a missed run gets one
catch-up. That is the right home for this watch.

A **session cron** (`CronCreate`) expires after 7 days and dies with the session, so it
is a convenience inside one long session, not standing infrastructure. A **cloud
routine** runs from a fresh clone of the GitHub repo, which means no user-level plugin
and no `/paper:` commands: not this watch.

Before submission, run the watch **and** a per-label `related-work-scout` pass over the
priority list; the watch covers what is new, not what was always there.

## Report

The window covered, the pages and queries actually run, the hits ranked by overlap with
their verdicts and labels, and the explicit sentence that absence of a hit is not
evidence of novelty. Never ask questions.
