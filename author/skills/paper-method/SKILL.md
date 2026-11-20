---
name: paper-method
description: 'Writing a math paper in LaTeX: the two style sources (writing-style.md, the paper''s style.md), the paper''s mechanics, handing back a section, the pre-send checklist. Use whenever writing, restructuring or cleaning up a paper.'
---

# Writing the paper

The reader is a competent mathematician who is not in your head, is reading on a
Tuesday afternoon, and will stop at the first sentence that costs them more than it
gives. Everything below serves that person.

Companion skills: the academy `rigor` skill governs whether the mathematics is honest.
Read it before writing up any argument, because fluent prose over an unverified step
is the failure mode this subject punishes most. `notation-discipline` says who changes
notation.

**How the paper is written: exactly two style sources.** The academy's general guide
`${CLAUDE_PLUGIN_ROOT}/../academy/references/writing-style.md` (statements, proofs,
prose, remarks, examples, figures and captions, proof level and length, section size,
notation and LaTeX habits; the structure of a paper, rule 12; turning notes into a paper,
rule 16), and the paper's own `.claude/rules/style.md` (its notation, the domain
conventions it prefers, its decisions, macros and margin-note rules), which refines the
guide and wins over it. The domain pack (`domain_get <domain> notation.md`,
`figures.md`) is read only for what the paper file does not settle. `Drafts/vision.md`
holds the paper's arc and its decisions log. Apply them within the writer's remit
(`${CLAUDE_PLUGIN_ROOT}/references/aesthetic-vision.md`, the role cut and the aesthetic
pass). A cleaner statement or a new argument is never written here: it is a `research`
ticket to the Researcher (`final_to: researcher`), and a statement pinned by a review
(`${CLAUDE_PLUGIN_ROOT}/scripts/pinned.py`) is not reworded
(`academy/references/roster-rules.md`, "Role cut").

**The paper's mechanics.** The home's `CLAUDE.md`, `.claude/rules/` and its
`.claude/academy.json` `author` block are authoritative (`statusLevels`, `preamble`,
`labels`, `notes`, `figures`, `bib`: `references/editing-tex.md`). Write today's `.tex`
correctly against the preamble as it stands; a preamble change goes as
`author.preamble.policy` says (default `propose`: a proposal with the reason, since a
paper with several coauthors breaks when the preamble changes underneath them). Draft
comments go through the paper's margin-note macros; **never sign a note as a human
coauthor.** The bibliography is the Expert librarian's: a missing entry is a `cite`
ticket. A figure is compiled on its own while iterating (far faster than rebuilding the
paper); its directory and inclusion command are the home's.

**Say what changed.** When handing back a rewritten section, distinguish transcription
(same argument, better prose), repair (you changed the mathematics: not yours in the
academy, it becomes a `research` ticket to the Expert with `final_to: researcher`) and
replacement (a different proof: likewise). Name the places, so the author can check
exactly those.

## Before sending anything out

- Compiles clean, and the `Overfull \hbox` warnings are checked for lines that actually
  run into the margin.
- Every `\cref` resolves; no `??` in the PDF.
- Every macro used exists in the preamble.
- Every sketched, conjectural or unverified step carries its visible marker and is
  named in the accompanying message.
- Every theorem cited from the literature has its hypotheses verified *in the text*
  for the objects at hand, not merely asserted.
- Figures legible in grayscale and at the printed width, no tiny text or tables inside
  them; captions short and standing alone.
- For arXiv: flatten to one directory, include only used files, confirm it builds from
  a clean checkout, remove debugging packages (label display), and check the abstract
  as plain text.

`/author:presync` runs this list's mechanical half at a milestone.

## Reference

`references/editing-tex.md`: line endings, the clean-build criteria, environments and
typed labels, margin-note rules. `references/draft-colours.md`: applying the status
colours (environment or command) and the provenance marker (`author.provenance`).
`references/modern-latex.md`: a catalogue of modern LaTeX practice for the preamble and
the build (argument specs, paired delimiters, biblatex vs BibTeX, microtype, engines and
fonts, build and lint), each item to be proposed, not imposed; not a style source (its
habits for the text are `writing-style.md`, rule 14).
