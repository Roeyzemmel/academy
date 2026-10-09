# Library

The home of the academy's Expert instance `{{instance}}` (`.claude/academy.json`): full
texts of the sources the workspace's papers and notebooks cite, fetched once and reused
by every agent. **Check here before fetching anything from the web.** Refetching a paper
that is already cached wastes calls and time: a full extraction is tens of thousands of
tokens. Written by `/academy:init` from the Expert plugin's `templates/library/README.md`;
add below what is particular to this library.

Git tracks `index.md`, the `.meta` and `.txt` files, the citation cards (`cards/`), the
literature-watch ledgers (`ledgers/<instance>/`), the review records (`reviews/<ns>/`),
`hot.md` and the generated views (`views/`). The PDFs, the `.src/` trees and the e-print
tarballs are ignored (`.gitignore`): nothing here is redistributed; these are personal
research copies of cited papers.

## Layout

```
<bibkey>.src/    the LaTeX source, when the paper is on arXiv — READ THIS FIRST
<bibkey>.pdf     the PDF, as fetched
<bibkey>.txt     `pdftotext -layout` extraction, the fallback when there is no source
<bibkey>.meta    one line per field: source URL, version, date fetched, how read
index.md         one row per cached or recorded source, kept in sync (/expert:library-index)
cards/           one card per relied-on statement: pinpoint, version, verbatim quote
```

**Prefer the LaTeX source over everything else.** It is the paper as written:
theorem environments carry their labels, formulas are intact, and the numbering can be
resolved from the `\label`s rather than guessed from a mangled two-column extraction.
`pdftotext` loses columns, ligatures and every displayed formula, which is exactly where
a hypothesis hides. Keep the PDF too: it is what a human opens, and the only artefact for
a paper not on arXiv.

`<bibkey>` is the key in the bibliography. A paper with no entry yet uses `author-year`
until `/expert:cite` gives it a key.

## How to use it

Read through the clerk (`/expert:lookup`, MCP `library_lookup` / `library_search`), or
directly:

```bash
ls $ACADEMY_LIBRARY                                   # is it here?
grep -rn "begin{lemma}" $ACADEMY_LIBRARY/<KEY>.src    # the source, if there is one
grep -n "Lemma 2.1"     $ACADEMY_LIBRARY/<KEY>.txt    # otherwise the extraction
```

Resolving a numbered statement in the source: the numbers are not in the file, the
`\label`s are. Find the environment, read its label, count the environments sharing its
counter, and confirm the number against the PDF or the extraction once.

Adding a paper (only the `librarian`, through `/expert:cite`, and only when it is
genuinely absent): the e-print into `<KEY>.src/`, the PDF, the extraction, then
`<KEY>.meta` and the `index.md` row. Record the **version** in both: arXiv numbering
drifts between versions, and a pinpoint verified against v3 is not verified against v1.
What fetches from which publisher: the Expert plugin's `references/publisher-access.md`.

## Rules

- **The extraction is not the paper.** Quote a `.txt` as *extraction*, never as *text*,
  and say which version (`academy:citation-discipline`). If a statement matters and the
  extraction is garbled, fetch the published PDF or read the pages as images, and say so.
- **An image-only PDF stays uncached as text.** Record it in `index.md` as `image-only`
  and do not pretend a `.txt` is the content.
- **Do not cache what you may not store.** A paywalled PDF fetched under a subscription
  is used, not cached; record the URL in `index.md` as `not cached` with the reason.
- **Never edit a cached file.** It is evidence. Corrections go on the card.
- **Only the librarian writes** the bibliography, the cards and `index.md` (the bib gate
  enforces it for the bibliography); graders write nothing.

## Librarian notes

The librarian's working notes particular to this library (network quirks of this
machine, institution-specific access) are its project memory,
`.claude/agent-memory/expert-librarian/` (index: `MEMORY.md`).
