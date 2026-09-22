---
name: cite
description: Add or verify a bibliography entry through source-checker — the only sanctioned route into references.bib. Fetches the record from Crossref, arXiv, MathSciNet or the journal page, quotes the statement being relied on into Drafts/sources.md, and reports the key and the pinpoint to use. Use before adding any citation.
---

# Add a citation, properly

`$ARGUMENTS` is a DOI, an arXiv id, a bib key already in the file, or a paper's title —
optionally followed by the statement of the paper that will rely on it.

The bibliography gate refuses an edit to `references.bib` from anyone but
`source-checker`, so this is not a convenience: it is the route. An entry filled in from
memory is the single easiest way to put a fabricated reference into a paper, and a
plausible-looking entry with the wrong volume or a nonexistent lemma number survives
every check but a human one.

If the project defines a paper cache (its `.claude/rules/` say so), the source may
already be on disk in full; `source-checker` looks there before fetching and adds what
it fetches, so a second call on the same paper costs nothing.

Dispatch `source-checker` (`subagent_type: source-checker`) with:

> <The DOI / arXiv id / title.> <The sentence of the paper that will cite it, and the
> pinpoint intended, if there is one.>
>
> If the key is already in `references.bib`, verify it against the record rather than
> adding it again, and say whether the existing fields match. If it is new, fetch the
> record and add the entry in the file's existing key style. Then, if a statement was
> given, locate it in the source, quote it verbatim with its number in that version, and
> record the block in `Drafts/sources.md`.

## What comes back, and what to do with it

- **The key and the pinpoint** to write in the tex — the main session relays them; the
  `\cite` itself is a writer's edit, not this pass's.
- **A mismatch** between what the paper wants to say and what the source states: that is
  a mathematical finding, not a bibliographic one. It goes to the author, and the
  sentence relying on it becomes a `[verify]` roadmap item.
- **Unreachable** (paywalled, image-only scan, no machine-readable text): the entry may
  still be added, but the ledger records how it was read, and anything resting on it
  stays an unverified input until a human reads it. Say that plainly.

Never write the entry yourself, never invent a pinpoint, and never let a verified-looking
ledger block stand in for a statement nobody actually read. Never ask questions.
