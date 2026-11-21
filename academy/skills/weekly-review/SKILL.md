---
name: weekly-review
description: 'One private weekly page: paper changes, statements ready, real decisions, merges, problems.'
---

# Weekly review

`$ARGUMENTS`: optional `--since YYYY-MM-DD` and `--until YYYY-MM-DD` (default: the seven
days up to today). Scripts: `$S` as in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`.
`<board>` is workspace.json's `board` path. Nothing here edits a home, a registry or a
ticket, and nothing is decided: answers go through `/academy:decide`.

1. **Gather** (read-only): `py $S/weekly_review.py [--since D] [--until D] --out
   <board>/.render/weekly-review.md`. It prints one line with the counts. A non-zero exit
   is reported as it is; stop. The script never publishes.
2. **Publish**, one private page updated in place each week:
   - With the `Artifact` tool: if `py $S/deep_dive_index.py get weekly-review` prints a URL,
     publish the markdown to it (read it first when this conversation has not published
     it); otherwise publish new, private, title "Weekly review", then record it with
     `py $S/deep_dive_index.py set weekly-review --url <url> --kind weekly-review --title
     "Weekly review" --subject weekly-review`.
   - Without it: copy the markdown to `<board>/weekly/<until>.md` and say in the reply
     that the page was written there and not published.
3. **Reply**: the link (or the file), the counts line, and the page's "Not gathered"
   list as it is (a missing tool or an unread source is named, never left out).
