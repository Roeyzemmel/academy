---
name: referee
description: 'Whole-paper referee report for one Author instance: the read-only referee agent reads the built PDF cold, and its report lands as a referee packet for Roey. Use for a referee ticket (from presync), before a coauthor round or submission.'
---

# Referee the whole paper

`$ARGUMENTS` is an Author instance (default: the only one in `workspace.json`), or a
`referee` ticket id. Budget: one referee run (`academy/references/budget.md`). Run it
from the library home so the landed packet and the ticket belong to the Expert
instance.

Not a proof check — `/expert:verify` does that, one statement at a time. This is the
other failure mode: every proof fine and the document not holding together.

1. **With a ticket**: `tickets_update` it `open -> accepted -> in-progress`.
2. **The PDF.** Read the Author home's config (`config_get {instance}`): `author.main`
   and `author.build`. The PDF is `<build.dir>/<main stem>.pdf`. If it is missing or
   older than the newest `.tex` in `paths.tex`, build it in the Author home with
   `author.build.cmd`, unless `author.build.lock` exists (LaTeX Workshop is building:
   wait for it to go, at most two minutes, then report and stop). Never edit the
   Author home. The referee has no shell, so the build is yours.
3. **Dispatch one `referee`** (`subagent_type: expert:referee`), in the background:

   > Referee `<instance>` cold. The PDF is `<absolute path>`, built `<date>`. <What
   > changed since the last report, if there was one, and its date.> <Anything Roey
   > wants looked at hardest, if he said.> Do not read the agenda or tickets
   > before your cold reading. After it, check the paper against its vision,
   > `<Author home>/Drafts/vision.md` <or: there is none>. Ticket: `<T-NNNN or none>`.

   Add nothing else: telling a referee where the weak parts are destroys the pass.
   Pass no `model` override. Fable and Opus 5.5 are equal primaries; a run on any
   other model marks itself reduced-strength.
4. **The landing is automatic**: the `land_referee` hook keeps the report at
   `reviews/referee/<instance>/<date>.md` and files a `referee` packet, linked to the
   ticket. Find the packet id in the hook's message or with `packets_list`.
5. **With a ticket**: `result` (`referee packet P-NNNN; <n> blocking`), then
   `in-progress -> delivered`. The Author's `notes` skill files the packet's objective
   points into its agenda; the judgement points go to the author untouched.

## Report

The overall assessment paragraph in full, the counts per class and severity, the five
findings the referee would fix first, the packet id and the copy's path. Never ask
questions.
