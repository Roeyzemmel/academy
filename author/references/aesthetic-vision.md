# The Author's aesthetic vision: role cut and aesthetic pass

The Author owns the paper's form and taste, not only the typing of settled results. The
taste itself is in the two style sources: the academy's general guide
`academy/references/writing-style.md` (base plugin) and the paper's own
`.claude/rules/style.md`, which refines it and wins over it. A paper home's
`Drafts/vision.md` (scaffolded from `author/templates/vision.md` by `/academy:init`) keeps
the paper's arc and its decisions log. This file holds no style rule: it is the procedure
by which the taste is exercised.

## The seven vision items

The aesthetic pass judges a section by these, each a rule of `writing-style.md`: **the
arc** (rule 12, and the paper's `Drafts/vision.md`); **economy of statements** (rule 2);
**notation that earns its place** (rule 13); **proofs at the right level** (rules 3 and 7);
**examples and figures where they carry the idea** (rules 5, 12 and 15); **the
introduction's promise kept** (rule 12); **one voice** (rule 11). The paper's `style.md`
refines each.

## Exercising it inside the role cut

The vision never licenses crossing the role cut (`academy/references/roster-rules.md`,
"Role cut"):

- **Within remit** (the writers apply it directly): prose, structure and order of
  sections, layout, figures, examples, the introduction's outline, notation already
  settled, proofs being shortened from a delivered argument. `math-writer` and
  `math-editor` read the two style sources and `Drafts/vision.md` before writing.
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
**vision mode**, read-only on the tex, reviews the section against the paper's `style.md`,
`writing-style.md` (the seven items above) and the arc in `Drafts/vision.md`, and returns
at most five proposals, each with:

- what (one line), where (file and label), which vision item (rule) it serves;
- its owner by the role cut: `author` (within remit), `researcher` (a statement or an
  argument), `expert` (pack notation), `human` (a taste question the style sources do not
  settle, or a pinned statement);
- the smallest change that realises it.

The calling skill files them: an Author proposal as a `write` or `apply` ticket to the
Author itself; a Researcher proposal as a `research` ticket to the Expert with
`final_to: researcher`; an Expert proposal as a `notation` ticket; a human one as a
question in the skill's report (`/academy:decide` picks up a ticket to `human`). Nothing
is edited during the pass, and a proposal already ticketed is not filed again.

## Keeping the files

The Author maintains the paper's `style.md` and `Drafts/vision.md`; only the human's words
change a decision in either. A taste decision the human states in chat, in a margin note
or in a packet answer is recorded with its date and source, verbatim where short: a style
decision for this paper in `style.md`, a general one (the human chooses) in
`writing-style.md`, a decision about the paper's arc in `Drafts/vision.md`; each also gets
a line in the vision's decisions log. A decision that is proposed but not confirmed is
marked "pending" and does not bind. The Expert's referee checks the built paper against
them (`expert/agents/referee.md`).
