# The Author's aesthetic vision

The Author owns the paper's form and taste, not only the typing of settled results. This
file is the generic standard; each paper home keeps its own `Drafts/vision.md` (scaffolded
from `author/templates/vision.md` by `/academy:init`), where the human's stated taste is
recorded and wins over anything here. `paper-method` is the craft (structure, prose,
labels); this file is the judgement about what the paper should look like.

## What the vision covers

1. **The arc.** The paper tells one story. Results are revealed in the order a reader
   needs them: the main theorem stated early, the tools before the proofs that use them,
   the technical heart where the reader is ready for it. Every section earns its place
   in the arc; a section the arc does not need is an appendix or a different paper.
2. **Economy of statements.** Prefer the clean general statement over a list of cases,
   one good definition over three patched ones, a hypothesis that is used over one that
   is carried along. A statement holds assumptions and a conclusion, not discussion.
3. **Notation that earns its place.** A symbol is introduced only when it is used again,
   once, before its first use, and never for two objects (`academy:notation-discipline`).
4. **Proofs at the right level.** Short proofs for the paper's reader; routine details
   omitted or moved to a lemma or an appendix; a long proof is a sign the plan needs a
   supporting lemma or a better definition, not more text.
5. **Examples and figures where they carry the idea.** An example right after a
   definition that is hard to picture; a figure where a picture replaces a paragraph.
   Never decoration.
6. **The introduction's promise kept.** Every result the introduction announces is
   proved (or cited) in the body, in the form announced; the body proves nothing the
   introduction should have announced and did not.
7. **One voice.** Consistent tense, person, terminology and level of formality across
   sections written at different times by different hands.

## Exercising it inside the role cut

The vision never licenses crossing the role cut (`academy/references/roster-rules.md`,
"Role cut"):

- **Within remit** (the writers apply it directly): prose, structure and order of
  sections, layout, figures, examples, the introduction's outline, notation already
  settled, proofs being shortened from a delivered argument. `math-writer` and
  `math-editor` read `Drafts/vision.md` before writing.
- **A different statement or a new argument** (a cleaner formulation, a unifying lemma, a
  definition that would absorb three cases, a hypothesis to drop): a `research` ticket to
  the Expert with `final_to: researcher`, saying what the cleaner shape would be and why.
  The Researcher proves; the Author lands what returns.
- **Notation of the domain pack**: a `notation` ticket to the Expert.
- **A pinned statement** (`py <author plugin>/scripts/pinned.py`): never rewritten, not
  even for wording. A proposal that touches one is a ticket; the human decides whether
  the pin is released.

## The aesthetic pass

Run by `/author:agenda` (one section per run, the one the next milestone reaches) and by
`/author:presync` (each section touched since the last sync). One `math-editor` run in
**vision mode**, read-only on the tex, reviews the section against `Drafts/vision.md` and
this file and returns at most five proposals, each with:

- what (one line), where (file and label), which vision item it serves;
- its owner by the role cut: `author` (within remit), `researcher` (a statement or an
  argument), `expert` (pack notation), `human` (a taste question the vision does not
  settle, or a pinned statement);
- the smallest change that realises it.

The calling skill files them: an Author proposal as a `write` or `apply` ticket to the
Author itself; a Researcher proposal as a `research` ticket to the Expert with
`final_to: researcher`; an Expert proposal as a `notation` ticket; a human one as a
question in the skill's report (`/academy:decide` picks up a ticket to `human`). Nothing
is edited during the pass, and a proposal already ticketed is not filed again.

## Keeping `Drafts/vision.md`

The Author maintains it; only the human's words change its decisions. A taste decision
the human states in chat, in a margin note or in a packet answer is recorded there with
its date and source, verbatim where short. A decision that is proposed but not confirmed
is marked "pending" and does not bind. The Expert's referee checks the built paper
against it (`expert/agents/referee.md`).
