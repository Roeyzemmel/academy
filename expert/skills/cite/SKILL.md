---
name: cite
description: 'Add or verify a citation through the librarian, the only route into references.bib and the library''s cards: fetch, cache once, write the card and index row, report key and pinpoint. Use before adding any citation and for every cite ticket.'
---

# Add a citation, properly

`$ARGUMENTS` is a DOI, an arXiv id, a bib key or a paper's title, optionally with the
pinpoint wanted and the sentence of the paper (or the claim id) that will rely on it; or a
`cite` ticket id (`T-NNNN`). Run it from the library home. Budget: one librarian run, plus
at most one fix (`academy/references/budget.md`).

The bibliography gate refuses an edit to a `references.bib` from anyone but the librarian.
An entry filled in from memory is the easiest way to put a fabricated reference into a
paper. A plausible entry with a nonexistent lemma number survives every check but a human
one.

**Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/cite.js` and
`args: {ticket: "T-NNNN"}` or `{ref, pinpoint, relying, bib: "<author instance>:references.bib"}`.
The inbox runs the same script for a `cite` ticket. The order is code (2026-10-31;
docs/workflows.md):
1. the ticket is taken and its ask read;
2. one `librarian` run, briefed by the script: verify an existing key against the record,
   or fetch and add the entry; the card with a verbatim quote; the index row when newly
   cached;
3. `cards.py validate`: a failing card goes back to the librarian once, and a second
   failure is reported;
4. the `citation` packet, then the ticket delivered with
   `<key>, <pinpoint>, verdict <v>, card <path>`.

The librarian's fetches stay on the allowlist of sources (`scripts/source_guard.py`).

## What comes back, and what to do with it

- **The key and the pinpoint** to write in the tex. The `\cite` itself is the Author's
  edit, not this pass's.
- **A mismatch** (`notes` starts with it) between what the paper wants and what the source
  states is a mathematical finding: say so first, and name the relying statement. The
  Author files it (a `verify` ticket back here if an argument now rests on a wrong reading).
- **Unreachable** (paywalled, image-only, no text): the entry may still be added, but the
  card records how it was read. Anything resting on it stays an unverified input until a
  human reads it. Say that plainly.

Never write the entry yourself, never invent a pinpoint, never let a card stand in for a
statement nobody read. Never ask questions.
