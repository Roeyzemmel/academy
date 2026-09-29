---
name: cite
description: 'Add or verify a citation through the librarian, the only route into references.bib and the library''s cards: fetch, cache once, write the card and index row, report key and pinpoint. Use before adding any citation and for every cite ticket.'
---

# Add a citation, properly

`$ARGUMENTS` is a DOI, an arXiv id, a bib key or a paper's title, optionally with the
pinpoint wanted and the sentence of the paper (or the claim id) that will rely on it;
or a `cite` ticket id (`T-NNNN`). Budget: one librarian run
(`academy/references/budget.md`). Run it from the library home, so the MCP tools act
for the Expert instance.

The bibliography gate refuses an edit to a `references.bib` from anyone but the
librarian. An entry filled in from memory is the easiest way to put a fabricated
reference into a paper, and a plausible entry with a nonexistent lemma number
survives every check but a human one.

1. **With a ticket**: `tickets_update` it `open -> accepted -> in-progress`, and take
   the key, pinpoint, sentence and target bibliography from its ask and refs.
2. **Dispatch one `librarian`** (`subagent_type: expert:librarian`):

   > <The DOI / arXiv id / title / key.> <The pinpoint intended, and the sentence or
   > claim id that relies on it.> <The bibliography: `<author instance>:references.bib`.>
   >
   > If the key is already in that bibliography, verify it against the record rather
   > than adding it again, and say whether the fields match. If it is new, fetch the
   > record and add the entry in the file's key style. Then locate the statement, write
   > its card with a verbatim quote from the version named, validate the card, and add
   > the index row if the source is newly cached.

3. **Check what came back**: `py ${CLAUDE_PLUGIN_ROOT}/scripts/cards.py validate
   <card>` must report no error. A quote it cannot find in the cached text is sent
   back to the librarian once, or the card must say why.
4. **Land it**: a packet (`packets_create`, kind `citation`, subject
   `[bib:<key>#<pinpoint>]`, the card path under `## Produced`, the verdict under
   `## Established vs assumed`), then the ticket's `result` (`<key>, <pinpoint>,
   verdict <match|...>, card <path>`) and `in-progress -> delivered`.

## What comes back, and what to do with it

- **The key and the pinpoint** to write in the tex. The `\cite` itself is the
  Author's edit, not this pass's.
- **A mismatch** between what the paper wants and what the source states is a
  mathematical finding: say so first, and name the relying statement; the Author
  files it (a `verify` ticket back here if an argument now rests on a wrong reading).
- **Unreachable** (paywalled, image-only, no text): the entry may still be added, but
  the card records how it was read, and anything resting on it stays an unverified
  input until a human reads it. Say that plainly.

Never write the entry yourself, never invent a pinpoint, never let a card stand in
for a statement nobody read. Never ask questions.
