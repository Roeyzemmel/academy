---
name: cite
description: 'Add or verify a citation through the librarian, the only route into references.bib and the library''s cards: fetch, cache once, write the card and index row, report key and pinpoint. Use before adding any citation and for every cite ticket.'
---

# Add a citation, properly

`$ARGUMENTS` is a DOI, an arXiv id, a bib key or a paper's title, optionally with the
pinpoint wanted and the sentence of the paper (or the claim id) that will rely on it; or a
`cite` ticket id (`T-NNNN`); or `--from-human <ticket> <file|text>` (below). Run it from the library home. Budget: one librarian run, plus
at most one retry of a run that returned nothing and one fix (`academy/references/budget.md`).

The bibliography gate refuses an edit to a `references.bib` from anyone but the librarian.
An entry filled in from memory is the easiest way to put a fabricated reference into a
paper. A plausible entry with a nonexistent lemma number survives every check but a human
one.

**Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/cite.js` and
`args: {models: <the JSON object that py "${CLAUDE_PLUGIN_ROOT}/../academy/scripts/models.py" launches prints>, root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>", ticket: "T-NNNN"}` or `{root, ref, pinpoint, relying, bib: "<author instance>:references.bib"}`.
The inbox runs the same script for a `cite` ticket. The order is code (2026-10-31;
docs/workflows.md):
1. the ticket is taken and its ask read;
2. one `librarian` run, briefed by the script: verify an existing key against the record,
   or fetch and add the entry; the card with a verbatim quote; the index row when newly
   cached. A run that returns no result (or ends without its structured output) is run
   once more, told to look for what the first one wrote; a second empty run is the
   outcome `lost`, with a note on the ticket's thread (#94), and ends this ticket only.
   After a retry, `cards.py dups` counts the key's entries (and the DOI's or arXiv id's)
   in the bibliography and the cards at the pinpoint: more than one is `lost` likewise;
3. `cards.py validate`: a failing card goes back to the librarian once, and a second
   failure is reported;
4. the `citation` packet, then the ticket delivered with
   `<key>, <pinpoint>, verdict <v>, card <path>`.

The librarian's fetches stay on the allowlist of sources (`scripts/source_guard.py`).

## A human's hand-back: `--from-human <ticket> <file|text>`

A `cite` ticket whose source no session could read is parked on the human (`blocked`,
`waiting_on [human]`, reason "source unreachable from this session: <key>; a human with
access reads <what> for <relying>"). The human resumes it with what they read:

- `<file>`: a PDF or a page image, a path inside the workspace (or one of its homes) and
  outside the library. Pass
  it when the rest of `$ARGUMENTS` names an existing file: `from_human: {file: "<absolute path>"}`.
- `<text>`: anything else is the quoted statement, passed **exactly as the human wrote it**
  (no cleaning, no reflowing): `from_human: {text: "<the human's words>"}`.

Run the same workflow with `args: {models, root, ticket: "T-NNNN", from_human: {...}}`
(and `ref: "<key>"` only when the park reason names no bib key). In code:
1. the ticket is read, not moved: only a `cite` ticket parked by cite for an unreachable
   source is taken (anything else is `not-started`), and a `ref` that is not the parked key
   is refused;
2. the material is recorded in the library by `scripts/handback.py`, in the register
   `<key>.human.md`, each record with its sha256: a text verbatim, refused unless its
   digest is that of what the human gave (written again once); a file from outside the
   library copied into `<key>.human/`, a PDF's text extracted beside it;
3. one `librarian` run writes the card from that material alone, `read_from:
   human-supplied`, naming the records it quotes (`handback:`), the quote verbatim from
   them; a quote transcribed from a page image is `status: unverified` with its reason.
   `cards.py validate --expect-read-from human-supplied` checks it, with one fix: every
   fragment must be in the named record's text (no NFKC folding), and a record that no
   longer matches its digest is an error;
4. the packet, then the ticket unparked (`blocked -> in-progress`, `waiting_on` cleared)
   and delivered, two stages; a delivery that fails after the unpark is the outcome
   `cited, ticket not delivered`, with a thread line.

Material that does not hold the pinpoint (another page, cut off, unreadable) writes no
card: the ticket stays parked, with a thread line saying exactly what is still missing
(`outcome: still missing (on the human)`, `gate.missing`). Tell the human that line.

## What comes back, and what to do with it

- **The key and the pinpoint** to write in the tex. The `\cite` itself is the Author's
  edit, not this pass's.
- **A mismatch** (`notes` starts with it) between what the paper wants and what the source
  states is a mathematical finding: say so first, and name the relying statement. The
  Author files it (a `verify` ticket back here if an argument now rests on a wrong reading).
- **Unreachable** (paywalled, image-only, no text): the entry may still be added, but the
  card records how it was read. Anything resting on it stays an unverified input until a
  human reads it. Say that plainly. The parked tickets are collected into the human's reading
  list, `<library>/views/reading-list.md`, by `py <expert scripts>/reading_list.py --write` (#108):
  per source, exactly what to read, the claims it blocks and the statements resting on them.
- **`ship`** (a standalone run; docs/workflows.md): with a ticket, its checkpoint ran once
  (`inbox.py --check`); without one the run ships `cite-<key>` through `inbox.py --ship-slug`
  (the same guards and scope, #136). With a ticket the Author home's `references.bib` ships with it
  (the touch ledger passes it as `--touched`, on the Expert's branch there); without one the
  notes say to add `--touched` for it. A refusal is reported, never retried.

Never write the entry yourself, never invent a pinpoint, never let a card stand in for a
statement nobody read. Never ask questions.
