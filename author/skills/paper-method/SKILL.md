---
name: paper-method
description: How to write a research mathematics paper in LaTeX so a reader one field over can follow it — structure (abstract, introduction, preliminaries, body, appendices), prose habits, cross-referencing and labels, macros, bibliography mechanics, turning scratchwork and delivered proofs into exposition, and the pre-send checklist; with a reference on modern LaTeX practice. Generic: the paper's own conventions live in its home's rules. Preloaded by the Author's writing agents; use whenever writing, restructuring or cleaning up a paper's prose or LaTeX.
---

# Writing the paper

The reader is a competent mathematician who is not in your head, is reading on a
Tuesday afternoon, and will stop at the first sentence that costs them more than it
gives. Everything below serves that person.

Companion skills: the academy `rigor` skill governs whether the mathematics is honest.
Read it before writing up any argument, because fluent prose over an unverified step
is the failure mode this subject punishes most. `notation-discipline` says whose
notation wins; the domain pack (`domain_get <domain> notation.md`, `figures.md`)
carries the field's notation and figure conventions.

**The paper's own conventions come first.** The home's `CLAUDE.md` and
`.claude/rules/` (macros, environments, colours, line endings, build) and its
`.claude/academy.json` `author` block are authoritative. Write today's `.tex` correctly
against the preamble as it stands, and propose infrastructure changes separately, with
the reason: a paper with several coauthors breaks when the preamble changes underneath
them. Draft comments go through the paper's margin-note macros; **never sign a note as
a human coauthor.**

## Structure

1. **Abstract**: the result in one or two sentences, precise enough to be useful and
   plain enough for someone one field over. Not a table of contents.
2. **Introduction**: the largest investment, and where the paper is won or lost.
   Context, then the main theorems stated in full (labelled Theorem A, B, ... so they
   can be restated verbatim where proved), then what is new, then a paragraph of proof
   strategy giving the *idea* rather than the details, then related work, then a short
   section outline last.
3. **Preliminaries**: only what is actually used. A preliminaries section that
   reproduces a textbook chapter signals that the author never decided what the paper
   needs. Cite instead, stating precisely the form used.
4. **Body**: one idea per section, each opening with what it will produce.
5. **Appendices**: long computations and routine verifications a reader skips but a
   referee needs.

State the main theorems in the introduction and restate them verbatim where proved, so
the reader never pages back.

## Prose

- **Signpost before you act.** "We first prove the bound for finite groups; the general
  case follows by passing to a limit." Two sentences save a page.
- **Every display is part of a sentence** and gets the punctuation that implies.
- **Introduce notation where used** if used once; collect it in a notation section if
  used throughout. Never both.
- **Kill "clearly", "obviously", "trivially".** They either add nothing or mark the
  place the author stopped thinking. `\cref{lem:x}` is shorter *and* more informative.
- **One idea per paragraph.** Long proofs get `claim` sub-environments or numbered
  steps, not more paragraphs.
- **Don't hedge inside the mathematics.** "We believe", "roughly", "it seems" belong in
  the introduction's discussion of open problems. If a step is uncertain, mark it
  visibly (the draft colour, a machine note) rather than softening the prose around it.
- **First person plural**, consistently.

## Mechanics

**Cross-references.** Always `\cref{thm:main}` / `\Cref{...}`, never a hand-typed
"Theorem~\ref{...}", so the type can never drift from the target. Label with a typed
prefix: `thm:` `lem:` `prop:` `cor:` `defn:` `eq:` `sec:` `fig:`.

**Macros.** Use the ones that exist. Define a new one only for an object with structure
that recurs, and say that you did. Never define a second macro for something already
covered: that is how a preamble becomes a second language the coauthors must learn.

**Bibliography.** Entries come from a fetched record (MathSciNet, the journal or arXiv
page), **never typed from memory and never invented** (`citation-discipline`). In the
academy only the Expert's librarian edits the bibliography; a missing entry is a `cite`
ticket. Include both arXiv and published references when both exist: readers want the
arXiv link, referees want the journal reference.

**Figures.** Each in its own file, compiled on its own while iterating (far faster than
rebuilding the paper); the directory and inclusion command are the home's, the drawing
conventions the domain pack's `figures.md`. Check the result in grayscale.

## Turning scratchwork (or a delivered proof) into a paper

- **The order of discovery is not the order of exposition.** Notes run bottom-up (what
  could be proved); a paper runs top-down (what the reader needs). Expect to invert the
  structure.
- **Extract the lemmas.** A long computation in notes is usually two or three reusable
  lemmas plus glue. Naming them is most of the work of making the argument readable.
- **Preserve every hypothesis, including the tacit ones.** Notes carry standing
  assumptions in the author's head. Hunt for them and state them; a silently dropped
  hypothesis is a false theorem.
- **Flag, do not smooth.** Where the source is compressed or skips a step, mark it
  instead of writing fluent prose across the gap, and say so in the report. Smoothing
  over a compression is how an error reaches a referee, and it is the thing a coauthor
  cannot catch, because the prose looks finished.
- **Say what changed.** When handing back a rewritten section, distinguish
  transcription (same argument, better prose), repair (you changed the mathematics:
  not yours in the academy, it becomes a `research` ticket to the Expert with
  `final_to: researcher`) and replacement (a
  different proof: likewise). Name the places, so the author can check exactly those.

## Before sending anything out

- Compiles clean, and the `Overfull \hbox` warnings are checked for lines that actually
  run into the margin.
- Every `\cref` resolves; no `??` in the PDF.
- Every macro used exists in the preamble.
- Every sketched, conjectural or unverified step carries its visible marker and is
  named in the accompanying message.
- Every theorem cited from the literature has its hypotheses verified *in the text*
  for the objects at hand, not merely asserted.
- Figures legible in grayscale; captions stand alone.
- For arXiv: flatten to one directory, include only used files, confirm it builds from
  a clean checkout, remove debugging packages (label display), and check the abstract
  as plain text.

`/author:presync` runs this list's mechanical half at a milestone.

## Reference

`references/modern-latex.md`: modern LaTeX practice (argument specs, paired
delimiters, one sentence per line, biblatex vs BibTeX, microtype, engines and fonts,
build and lint), each item to be proposed, not imposed.
