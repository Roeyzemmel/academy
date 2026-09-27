---
name: latex-paper-writing
description: Write and revise research mathematics papers in LaTeX — structuring a paper, thmtools/amsart setup, macros, cross-referencing, bibliography, figures, and turning handwritten or scratch notes into readable publishable prose. Carries this project's actual preamble and macro conventions plus a modern-LaTeX guide. Use this whenever the task involves a .tex file, a math paper or preprint, an arXiv submission, a theorem environment, a LaTeX macro or preamble, a bibliography or BibTeX entry, a referee report response, or a request to write up, clean up, restructure, or typeset mathematical work. Trigger on "write this up", "turn my notes into a paper", "clean up this draft", "fix my LaTeX", "how should I structure this section", "the proof of Lemma 3 needs rewriting", "prepare this for arXiv", or any mention of .tex, amsart, thmtools, amsthm, TikZ, or BibTeX.
---

# Writing a mathematics paper

The reader is a competent mathematician who is not in your head, is reading on a
Tuesday afternoon, and will stop at the first sentence that costs them more than
it gives. Everything below serves that person.

Companion skills, when present: **math-proof-writing** governs whether the
mathematics is honest — read it before writing up any argument, because fluent
prose over an unverified step is the failure mode this subject punishes most.
**translation-surfaces** carries the notation contract and figure conventions.

## Read the project's conventions first

**`references/macros.md`** — the environments, macros, and traps of this specific
project, extracted from Roey's `main.tex` and compile-verified. Read it before
writing any `.tex`. The things that will otherwise break the build:

- Theorem environments are `thm` `prop` `lem` `cor` `defn` `rmk` `claim` … via
  `thmtools`. `\begin{theorem}` and `\begin{lemma}` **do not exist**.
- Blackboard bold is asymmetric: `\N` `\Z` `\R` bare, but `\bbQ` `\bbC` `\bbH`
  `\bbT` `\bbD`. There is no `\C`.
- Calligraphic H is **`\ccH`**, not `\cH`.
- `\Mod` is the mapping class group; use `\cM` for an invariant submanifold.
- `\parallel` has been redefined to a cylinder-parallel double-slash.
- `\hol` takes two brace arguments, `\hol{}{\gamma}`.
- Draft comments go through the existing `\newComment` margin system —
  `\Roey{…}`, `\Barak{…}` etc. **Never sign a note as a human coauthor.**

`assets/preamble.tex` is that preamble verbatim; `assets/main-skeleton.tex` is the
full document shell. Sections live in `sections/*.tex` and are `\input` — write
there, not in `main.tex`.

**`references/modern-latex.md`** — current best practice with tested upgrades to
this preamble, and the reasons. Roey has said he wants to learn modern practice,
so raising these is welcome. But keep the two things separate: write today's
`.tex` correctly against the preamble as it stands, and propose infrastructure
changes as a separate, explained suggestion. A paper with five coauthors breaks
when the preamble changes underneath them.

## Structure

The standard shape, and what each part is actually for:

1. **Abstract** — the result, in one or two sentences, precise enough to be
   useful and plain enough for someone one field over. Not a table of contents.
2. **Introduction** — the largest investment, and where the paper is won or lost.
   Context, then the main theorems stated in full (labelled Theorem A, B, … so
   they can be restated verbatim where proved), then what is new, then a
   paragraph of proof strategy giving the *idea* rather than the details, then
   related work, then a short section outline last.
3. **Preliminaries** — only what is actually used. A preliminaries section that
   reproduces a textbook chapter signals that the author never decided what the
   paper needs. Cite instead, stating precisely the form used.
4. **Body** — one idea per section, each opening with what it will produce.
5. **Appendices** — long computations and routine verifications a reader skips
   but a referee needs.

State the main theorems in the introduction and restate them verbatim where
proved, so the reader never pages back.

## Prose

- **Signpost before you act.** "We first show every cylinder is parallel to $v$;
  the general case follows by applying $g_t$." Two sentences save a page.
- **Every display is part of a sentence** and gets the punctuation that implies.
- **Introduce notation where used** if used once; collect it in a notation
  section if used throughout. Never both.
- **Kill "clearly", "obviously", "trivially".** They either add nothing or mark
  the place the author stopped thinking. `\cref{lem:x}` is shorter *and* more
  informative.
- **One idea per paragraph.** Long proofs get `claim` sub-environments or numbered
  steps, not more paragraphs.
- **Don't hedge inside the mathematics.** "We believe", "roughly", "it seems"
  belong in the introduction's discussion of open problems. If a step is
  uncertain, mark it visibly rather than softening the prose around it.
- **First person plural**, consistently.

## Mechanics

**Cross-references.** Always `\cref{thm:main}` / `\Cref{...}`, never a hand-typed
"Theorem~\ref{...}" — the type can then never drift from the target. Label with a
typed prefix: `thm:` `lem:` `prop:` `cor:` `defn:` `eq:` `sec:` `fig:`.

**Macros.** Use the ones that exist. Define a new one only for an object with
structure that recurs, and say that you did. Never define a second macro for
something already covered — that is how a preamble becomes a second language the
coauthors have to learn.

**Bibliography.** `amsalpha` + BibTeX currently; `references.bib`. Pull entries
from MathSciNet or the journal/arXiv page — **never type one from memory and never
invent one.** Include both arXiv and published references when both exist; readers
want the arXiv link, referees want the journal reference.

**Figures.** Each in its own file under `figures/`, `\input` or `\import`ed. The
preamble already loads `standalone`, so compile figures on their own while
iterating — far faster than rebuilding the paper. Check the result in grayscale.

## Turning scratchwork into a paper

Notes and a paper differ in more than typesetting.

- **The order of discovery is not the order of exposition.** Notes run bottom-up
  (what could be proved); a paper runs top-down (what the reader needs). Expect to
  invert the structure.
- **Extract the lemmas.** A long computation in notes is usually two or three
  reusable lemmas plus glue. Naming them is most of the work of making the
  argument readable.
- **Preserve every hypothesis, including the tacit ones.** Notes carry standing
  assumptions in the author's head ("all surfaces here are primitive"). Hunt for
  them and state them; ask when unsure rather than guessing, since a silently
  dropped hypothesis is a false theorem.
- **Flag, do not smooth.** Where the notes are compressed or skip a step, the
  temptation is to write fluent prose across the gap. Mark it instead, and say so
  in the reply. Smoothing over a compression is how an error reaches a referee —
  and it is the specific thing a coauthor cannot catch, because the prose looks
  finished.
- **Say what changed.** When handing back a rewritten section, distinguish
  transcription (same argument, better prose), repair (you changed the
  mathematics), and replacement (you proved it differently). Name the places you
  did the latter two, so Roey can check exactly those.

## Before sending anything out

- Compiles clean (`latexmk -pdf`), and the `Overfull \hbox` warnings are checked
  for lines that actually run into the margin.
- Every `\cref` resolves; no `??` in the PDF.
- Every macro used exists in the preamble.
- Every sketched, conjectural, or unverified step carries a visible marker and is
  named in the accompanying message.
- Every theorem cited from the literature has its hypotheses verified *in the
  text* for the objects at hand, not merely asserted.
- Figures legible in grayscale; captions stand alone.
- For arXiv: flatten to one directory, include only used files, confirm it builds
  from a clean checkout, remove `showlabels`, and check the abstract as plain text.
