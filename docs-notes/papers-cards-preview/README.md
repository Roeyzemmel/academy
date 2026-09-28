# Preview: BI's sources ledger as library cards

A preview for the phase-7 ledger move (plan sections 6 and 9, "moving the ledgers" is
review-gated). Nothing here is live and nothing was written into
`C:\Work\Math\papers` or `BilliardIllumination`.

Produced on 2026-09-28 by `expert/scripts/ledger_split.py`, run on temp copies of
`BilliardIllumination/Drafts/sources.md`, `Drafts/related_work.md` and
`references.bib`, with `--library C:/Work/Math/papers` read-only for index versions
and the quote check (the MCP server's `library_verify_quote` normaliser):

- `cards/`: the first 20 cards in ledger order, as they would land in
  `papers/cards/<key>/<pinpoint>.md`;
- `stats.md` / `stats.json`: the whole conversion (86 cards from 24 blocks), the
  read-from / verdict / quote-check distributions, the collisions, the cards moved to
  the source their own text names, and the one block with no bibliography key.

Every card is marked `migrated`: its `## Statement` and `## Hypotheses` are
`_To fill_` for the librarian, and the ledger's bullet is kept verbatim under
`## Ledger text`. A quote "not found" usually means the ledger reworded a display
(`$$...$$` given as `$...$`) or quoted LaTeX against an extraction; the librarian
re-quotes it. Validation: `py expert/scripts/cards.py validate <card> --home
C:/Work/Math/papers`.
