---
name: library-index
description: 'Keep the library''s index.md in step with its cached files: find cached keys with no index row, draft and add rows via the librarian, validate every card''s schema and quote. Use for "fill the index", "what''s cached but not indexed".'
---

# The library index

`$ARGUMENTS` is empty (report), `fill` (add the missing rows through the librarian),
or `cards` (validate every card). Scripts: `$E` = `${CLAUDE_PLUGIN_ROOT}/scripts`.
Everything here runs against the Expert instance's home (`--home` overrides it).

1. **Report** (always first):

       py $E/library_index.py missing
       py $E/cards.py validate

   Relay the gaps (cached keys with no row, rows with nothing cached) and the card
   errors and warnings. Rows with nothing cached are legitimate when the index says
   why (image-only, paywalled); say which.
2. **`fill`**: `py $E/library_index.py propose` drafts one row per missing key from
   its `.meta`, marking every cell the `.meta` does not state `to fill`. Dispatch one
   `librarian` (`subagent_type: expert:librarian`) with the drafted rows:

   > Add index rows for these cached keys: <keys>. Drafts from their `.meta` follow;
   > fill each `to fill` cell from the cached file itself or its `.meta` — never from
   > memory — or leave it `to fill` and say why. A key that is not a bibliography key
   > (a stray download, a duplicate) gets a row saying so, or a note for Roey to
   > delete it; you never delete a cached file.

   `py $E/library_index.py apply` appends the drafts unchanged when that is all the
   librarian wants; the librarian may also edit `index.md` directly. Then run the
   report again: no key may be left without a row.
3. **`cards`**: the card report from step 1 with `--json`, grouped by key; the
   `migrated` cards whose statement or hypotheses are still `_To fill_` are listed as
   the librarian's backlog, at most three keys per run (`budget.md` rule 1).

Never write into the library from this seat except through the scripts above and the
librarian. Report the counts before and after. Never ask questions.
