---
name: citation-discipline
description: How to rely on published work — cite before reproving, quote the relied-on statement verbatim with its source version, check the cited result's real hypotheses for your objects, never invent an author, title, year, numbering, pinpoint or bibliography entry, and never treat a text extraction as the text. Use whenever a result from the literature is stated, cited, applied, looked up or added to a bibliography, whenever a pinpoint ("Theorem 1.3 of X") is written, and before reproving anything that might already be published.
---

# Citation discipline

## Cite before reproving

A research paper should bring new information. If a result is published, cite it
precisely; do not reprove it. Historical references to earlier work are welcome.
Reprove only what is new, or what the source states in a form that does not cover
your case, and then say why the citation does not suffice.

## Never invent

Never invent a theorem, an author, a title, a year, a statement number, a pinpoint or
a bibliography entry. If you need a result and are not certain of its exact statement
and source, do one of two things:

- look it up (Expert: `/expert:lookup`, the clerk; the card or the cached text), or
- state it as a labelled assumption and file a `cite` ticket to the Expert if it is your neighbour (Author, Researcher). The
  Scientist files it to the Researcher with `final_to: expert`.

Bibliography entries are added only by the Expert's `librarian`, from a record fetched
in the same run (Crossref, arXiv, the journal page). Hooks refuse any other editor.

## Quote verbatim, with the version

- The statement you rely on is quoted **verbatim** from the source, with the source
  **version** (arXiv vN, or the journal version) and the pinpoint.
- A pinpoint verified against arXiv v3 is not verified against v1. Numbering changes
  between versions and between preprint and journal.
- Prefer the LaTeX source to the PDF. In the source, statement numbers do not exist,
  only labels: find the environment, see what the source's own references call it,
  and confirm the number once against the PDF.
- A `pdftotext` **extraction is not the text.** It mangles columns and displays. Quote
  an extraction only as *extraction*; an image-only PDF has no usable text and is
  recorded as `image-only`, never faked.
- Quotes are checked mechanically (`library_verify_quote`) against the cached text.

## Use the result within its real hypotheses

A citation is a claim that the cited theorem applies. Verify its hypotheses **for
your objects**, in writing, at the point of use: "By [X, Thm 2.1], the object is Y"
is legitimate only once it is said why each hypothesis of [X, Thm 2.1] holds here.
Check the statement against the card or the pack's theorem sheet, never against
memory: memory reconstructs hypotheses plausibly and wrongly. Whether a citation is
*used* correctly is part of the proof review, not of the citation check.

## Read the cache first

Full texts live in the Expert home's cache. Look there (`library_lookup`,
`library_search`) before any web fetch; fetch a missing paper once and add it to the
cache, so no one fetches it again.
