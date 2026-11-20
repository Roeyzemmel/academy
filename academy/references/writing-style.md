# Writing style

The academy's one general guide to how mathematics is written: statements, proofs, prose,
remarks, examples, figures and their captions, proof level and length, section size,
notation habits and LaTeX habits. Every agent that writes, rewrites or judges text reads
it: the prover (notebook attempts), math-writer, math-editor, figure-maker and
note-sweeper (the paper), and the rigor-reviewer, referee and notation-auditor who judge
them. `rigor` decides whether an argument is *correct*; this file decides what a correct
argument *looks like*. A style defect is never a gap: a reviewer reports it as a separate
style finding.

## The two style sources and their precedence

There are exactly two style sources (the human, 2026-11-19, academy issue #106):

1. **This guide**, `academy/references/writing-style.md` in the base plugin: style and
   habits of writing, for any paper or notebook.
2. **The paper's own file**, `<paper home>/.claude/rules/style.md`: its notation choices,
   the domain conventions the human prefers over the pack's, its paper-specific decisions,
   its macros and its margin-note rules. It only refines this guide: it never restates a
   general rule (it cites the rule's number here) and never contradicts one (the human,
   2026-11-20: "I expect the convention files to not contradict each other, rather be more
   specific as it goes").

**Precedence: the paper file > this guide > the domain pack.** The pack's `notation.md`
and `figures.md` (`domain_get <domain> notation.md`) are a reference, read only for the
symbols and figure conventions the paper file does not settle. A home with no paper file
(a Researcher's notebook) follows this guide, then the pack. A contradiction found between
the two style sources is reported to the human; a writer never settles it.

Not style sources, and read only when the work needs them: the procedures
`author/skills/paper-method/references/editing-tex.md` (editing without costing a build,
labels, margin-note mechanics) and `draft-colours.md` (the colour mechanism); the role cut
and the aesthetic pass, `author/references/aesthetic-vision.md`; the catalogue of preamble
proposals, `paper-method/references/modern-latex.md` (tex-engineer's, each item proposed,
never imposed). A paper home's `Drafts/vision.md` keeps the arc of that paper and its
decisions log; its style decisions are in the paper file.

**Models** (the human, 2026-11-14): the human's own notes *Dynamics on moduli spaces of
translation surfaces — exercises solution*; Apisa–Wright `AW21`; Lelièvre–Monteil–Weiss
`LMW16`; Smillie–Weiss `SW08`; and, in a paper home, the sections the human has revised.
Where they disagree, the human's choice is recorded at the rule.

The rules are in order of weight: when two pull apart, the earlier one wins. Each rule
states its exceptions; a later rule never overrides an earlier one silently. Rules 1-11
keep the numbers they had in `proof-style.md`, which tickets and reviews cite; rules
12-16 were gathered here on 2026-11-20 from `aesthetic-vision.md`, `paper-method`,
`modern-latex.md` and `notation-discipline`.

## 1. Every statement is fully proved, precisely cited, or folklore by the human's word

The human, 2026-11-14: "I am a master's student and do not have the reputation to leave
half-proved statements."

- **No "Proof sketch" in the paper.** A sketch is a notebook status (`sketch`) and a draft
  colour, never a heading.
- **Nothing is left to the reader wholesale** (AW21's and SW08's way, not LMW16's): no
  whole case or direction of the text's own arguments. What may be skipped is listed in
  rule 7, and only with a pointer. The two exceptions are the human's word, never a
  writer's judgement: folklore (below), and elementary properties named together in one
  sentence with their proofs omitted (rule 2; the human, 2026-11-20). The bar "no
  half-proved statements" is for the paper's own content, not for what a graduate reader
  supplies at once.
- **Never left out:** the construction, the key estimate, why a map is well defined, and
  each use of a cited or deep result. A missing idea or hypothesis is a gap, not an
  omission.
- **Folklore is the human's call** (the human, 2026-11-14: "folklore statements may be subtly
  assumed or stated as a fact, decision on my word for what I find folklore as it may be in
  the paper's direct topic or in more classical theory"). Folklore, in the text's own topic
  or in classical theory, may be used silently or stated as an unproved Fact; a statement
  the human calls trivial is used without proof. Easy steps of the text's own arguments
  are not folklore: they are clauses of the proof that uses them (rules 3 and 7). A writer
  who thinks a statement is folklore or trivial asks the human; it never drops a proof on
  its own judgement.
- **Uncertainty is marked, never written around.** In the paper, the draft colour or a
  machine margin note (the home's `author.noteMacros.machine`); in the notebook, the
  attempt's *Gaps* list. A speculation ("the bound can likely be improved by …") is a
  Remark marked as unverified. No hedging inside the mathematics (`paper-method`): "we
  believe", "roughly", "it seems" belong in the introduction's discussion of open
  problems; an uncertain step is marked, not softened.
- **A statement resting on an unverified input is marked unverified** (the human,
  2026-11-14: "mark the result as a sketch and we will handle it later"). When a proof is
  rewritten or a lemma newly extracted, the statement using it, and everything resting on
  it, takes the draft colour (or `sketch`) until the input is verified. Never keep an
  outdated proof, or leave the colour unchanged, to avoid the cascade.
- **Nothing depends on a question or a conjecture** (the human, 2026-11-14: "Dependence on
  questions is undefined"). Remove the reference, or turn the dependence into a stated
  hypothesis and name the statement that justifies it.

## 2. Say everything once

The human, 2026-11-14: "I don't allow duplications." This rule outranks every rule below
that would create a second statement, proof or recollection of the same thing.

- **No two statements state the same thing**, for instance a lemma that another statement
  merely quotes, or an item that copies a lemma (rule 3).
- **A statement holds only what it adds.** Delete an item, remark or corollary that is a
  special case of another statement, contained in one, or immediate from the statements it
  rests on (a trivial corollary becomes a sentence citing them), and cite those statements
  where it was used. Fold a remark that extends a statement into that statement; likewise
  a requested generalization goes into the statement it generalizes (drop the hypothesis,
  give the proof or its adaptation there), not into a separate remark (`paper-method`).
- **Economy of statements** (`aesthetic-vision`, item 2). Prefer the clean general
  statement over a list of cases, one good definition over three patched ones, a
  hypothesis that is used over one that is carried along. A case split follows the
  structure of the objects, and an uninteresting case goes to a remark rather than into
  the statement (the human, margin note of 2026-09).
- **One proof per statement** (the human: "Default to deleting alternative proofs"). Keep the
  shorter one that reuses a result already in the text; the other is deleted, not kept as a
  Remark.
- **State each fact once and prove each property once**, then point to it; no restatement,
  even within one paragraph. No idle repetition (the human, PR 7, 2026-10-10: repetitions
  without a specific intention behind them "bloat the article and make it difficult to
  read").
- **Do not recall a definition**, its working form or a convention at the start of each proof
  that uses it: give it once, before the group of results, and cite it. An item that holds
  by definition is proved by the words "by definition", with the definition cited.
- **Background is stated once**, then cited, never re-derived (rule 9 says where).
- **A section holds few statements** (the human, 2026-11-20: "there are way too many
  statements for a section … this should bother us"). About **30 numbered statements per
  section**, examples and remarks included, is the ceiling (the human, 2026-11-20). Before
  adding a statement, ask whether the narrative needs it or it contributes a technique;
  if neither, it is a sentence, an appendix item, or nothing. Past the ceiling, stop and
  re-plan with the human; do not keep adding. When every statement is interesting and
  must stay, the remedy is to **split the section**, not to keep it long.
- **Elementary properties are one sentence, not a lemma each** (the human, 2026-11-20).
  Properties a structure inherits in an elementary way from a classical setting are named
  together in one sentence near the definition ("the flat structures defined here inherit
  many properties of …, including …; the proofs are elementary and omitted"), on the
  human's word (rule 1). The less trivial of these proofs may go to an appendix (rule 9).
- **General facts in general, special facts once** (the human, 2026-11-20). A property that
  holds for a general construction (normal coverings) is stated once in that generality
  (where: rule 9); the special case (the unfolding) gets only what is not a special case of
  it, collected in one statement ("Properties of the unfolding") that says which known
  discussions it generalises.

## 3. Short statements in a chain, not one long proof

- **Extract a step only when it earns a statement** (the human, 2026-11-20, narrowing
  2026-11-14's "easy steps that can pose as lemmas"): when it is used elsewhere (never cite
  a paragraph or step inside another proof: an argument used elsewhere is a lemma); when
  it is a more general phenomenon, or a special case the main statement is reduced to (it
  holds without the main statement's special hypothesis, which stays in the main proof);
  or when the proof would otherwise pass the length limit below. A step a graduate reader
  supplies at once is a clause (rule 7), never a lemma, and extraction never pushes a
  section past its statement ceiling (rule 2). Extracting easy steps one by one is how a
  section fills with simple statements that repeat each other.
- **A proof is short**, constructive and elegant (the human, 2026-10-08). Most are 1–10
  lines. Past about **15 lines of output** (the typeset PDF at the paper's text width,
  displays included; the rendered Markdown for a notebook attempt; never the source; the
  human, 2026-11-14: "15 lines of output, as the line count in the source is unrelated"),
  something extractable has been missed. A proof that keeps growing is a sign to re-plan
  the chain with the human (a supporting lemma or a better definition), not to push on.
- **Build a chain:** definition, lemma, corollary, each small. A corollary's proof is often
  one line ("Follows from Lemma 6.").
- **An argument that handles objects one at a time is an induction** (the human,
  2026-11-14): the one-object step is a lemma, or an item of the statement it belongs to
  (rule 4), and the general case follows by induction, with the inductive statement
  strengthened if needed.
- **The statement comes at the end of its chain** by default (the human, 2026-11-14), after
  the lemmas it rests on, so its proof follows it and is an assembly of named results in a
  few sentences ("By Lemma 2.13 … Hence Proposition 2.10 gives the result"). It comes before
  its lemmas only when it is a theorem stated in the introduction (of the section or the
  paper), or for a narrative reason; its proof, separated from it, then opens "Proof of
  Theorem N" (or "Proof of Theorem 1 assuming Propositions 3 and 6").
- **Lemmas and the items of a list** (rules 2 and 4). A lemma is extracted from a listed
  statement only when it is more general than an item, or treats a special case the item is
  then reduced to; the item's proof applies or reduces to it in one sentence ("Item (ii)
  follows from Lemma B applied to π."). A lemma that would state exactly what an item
  states is not extracted: the item is proved in place. **An item another item implies**
  is stated as its consequence (the human, 2026-11-20), not proved on its own.
- **Lemmas about one construction are one proposition** (the human, 2026-11-20): several
  lemmas on the same object or construction (the lifts of a map, say) are merged into a
  single proposition with items, and the first item's proof carries what the others would
  repeat, so the proof is shorter than the lemmas' together.
- **A definition defines one notion** (the human, 2026-11-14), and the length limit applies to
  it too. Split a definition that introduces several objects into consecutive definitions,
  with short discussion between them (SW08's way). Define a property of an element in
  words, then name the set of such elements; no itemised list or set-builder display for one
  notion.
- **Labels are a warning sign.** A proof that needs parts, steps or cases is often proving a
  composite statement: first try to split it into a chain of claims, each step its own lemma
  (within rule 2).
- **When not to extract:** the sub-statement's setting is so specific to this proof that,
  stated alone, it would restate the whole setup or mean nothing outside the proof. Then
  keep the proof together and write it as in rule 5.

## 4. Statements: order, role, shape and names

- **Definitions and notation come before the statement** that uses them, not inside a
  proof, when they are used again. An explicit construction (a map, an atlas, a
  decomposition) is a definition of its own, given before the claims about it.
- **Shared hypotheses and notation are given once before the statements** (the human,
  2026-11-14): a "Setting" definition, a sentence of standing assumptions or a run-in
  *Notation.* paragraph, which each statement cites. A statement never defines notation in
  passing; notation used across sections is defined once in the introduction. A section may
  open with a "Setup and notation" subsection when its shared setting needs one.
- **Statements come in constructive order** (the human, 2026-11-14): supporting statements
  before what uses them; main theorems may also appear in the introduction of the section or
  of the whole paper (rule 3). Within the freedom dependency leaves ("Dependency order
  precedes difficulty"), go from the easiest and shortest to the hardest and longest, and
  place an elementary example that needs no heavy setup early.
- **The environment marks the role** (the human, 2026-11-14): the result a section exists for
  is a Theorem; a subsection's main result a Proposition; statements proved to feed it are
  Lemmas; what follows in a few lines a Corollary; a folklore input a Fact (rule 1). Split a
  trailing "so …" conclusion off as its Corollary (unless rule 2 makes it a sentence), and
  rename the environment when extraction changes a statement's role.
- **A statement holds only assumptions and results** (the human, 2026-10-08; a margin note of
  2026-09: "several sentences of assumptions, then the claim in one sentence, possibly
  followed by a list of properties"): assumptions, then the claim in one sentence, then
  optionally a list (whose items may add assumptions along the way) and a concluding
  sentence. No reasoning, motivation or discussion inside a statement environment: that
  goes in the proof or in plain text after it (rule 6). This binds definitions, facts,
  lemmas, propositions, corollaries, theorems and claims, not examples, exercises,
  questions, remarks or proofs; writers and reviewers flag a statement that breaks it.
- **A corollary states every direction its source proves** (`paper-method`): if the lemma
  gives an equality of sets, the corollary says the equality, not one inclusion or its
  consequence.
- **A list inside one statement** is allowed when its items all describe properties of a
  single object (the human, 2026-11-14), consolidating them under that object; statements
  about different objects are separate statements, and so are the two jobs of a statement
  that does two (the human, 2026-09: "Separate to different lemmas?"). The items are
  numbered ((i)–(iii)) and labelled when referred to, and the proof treats them in the same
  order, in paragraphs opening "For \cref{it:…}, …" (rule 14), never as an itemised list and
  with no "we prove the items in order" preamble.
- **A Question opens with its setup** ("Let … . We ask:"), then one question per item and
  what it turns on; what a positive answer would give, and which questions depend on which,
  come after the list.
- **A short name in brackets** for a statement referred to by content: "Lemma 6 [Lower
  bound on path metric]". The name of an example, counterexample or remark says what it is
  and the situation it shows ("Counterexample where *Y* is a torus"), not the hypothesis it
  discusses.

## 5. A composite proof, or a chain, is written for the reader

- **A composite proof kept together** (rule 3, "When not to extract") opens with a **plan**:
  the steps and how they combine ("The proof proceeds in three steps …"), and gives the
  **intuition before the details**: the main idea, in a few sentences.
- Each step is its **own clear paragraph**, opening with a run-in bold label that says what
  it establishes ("**Step 1:** *p* lies in a cylinder of *C*.", "**Case 1.** *x = y* is
  nonsingular.", "**Well-defined.**"). No lists of reasoning inside a proof.
- The closing deduction needs **no "Conclusion" label** (the human, 2026-11-14): it is
  written as plain text after the last step.
- Discussion that **clarifies a main idea** of a step is welcome here, and only here (rule 6).
- **A chain gets its plan before it** (the human, 2026-11-14): when one long proof becomes a
  chain, a short paragraph before the chain gives the idea and names the lemmas in the order
  they are used. Where the text turns from the general case to a special family, a narrative
  paragraph says why it is treated; a long group gets its own subsection.
- **Figures.** A diagram or figure is added where it carries the idea: a commutative diagram
  for the maps, a picture of the surface or the cylinders for the geometry. Every
  counterexample, and every example or remark describing concrete configurations, gets a
  figure showing the situation that makes it work (the human, 2026-11-14). A schematic figure
  says that it is schematic and what it does not show. How a figure is drawn and captioned:
  rule 15.

## 6. Discussion and intuition live outside the proof

SW08's way (the human, 2026-11-14; earlier: "Way too much discussion").

- **A proof is deduction.** The exception is a composite proof kept together (rule 5).
- **Intuition** for a statement goes in its own paragraph before it, or before the group of
  results it explains.
- **Sharpness examples and asides** go in a Remark or Example after the proof (alternative
  proofs do not: rule 2).
- **Remarks are scattered side stories** (the human, 2026-11-20: "having two or more
  remarks in a row is weird"). A remark enriches the narrative where it stands; two
  remarks in a row are a defect. Scatter them to where each belongs, turn some into a
  discussion paragraph, or join one with another statement (another remark included).
- **A paragraph, remark or example carries one discussion** (the human, 2026-11-14). Separate
  an example's configurations from a general analysis of them, and give the analysis its own
  short remark by the shortest route (a structural fact or a citation). Compact a long
  expository paragraph, or split it into short ones, one idea each.

## 7. Written for a graduate reader in the field

- **Proofs at the right level** (the human, 2026-10-08: proofs assume a graduate reader;
  small technical details are not written out, and the human asks for elaboration where
  needed). Writers do not pad, and reviewers judge a step against that reader: a gap is a
  missing idea or hypothesis, not a routine verification (rule 1).
- **Leave out, and say which, in one clause with a pointer:** definitional checks ("by
  definition", rule 2), immediate converses, and cases analogous to one written ("The other
  direction is trivial." "The argument for *p_b* is the same." "The proof of (ii) is
  identical, with *x* replaced by *ξ*.").
- **A routine method is named, never silent** (the human, 2026-11-14: "Routine methods may be
  removed or extracted into facts. Explicitness is required, taking form of specifying the
  routine's common name"). Write "by induction on the number of marked points", "by
  compactness", "WLOG *V* = *B(x, r)*", "passing to a subsequence": one clause, no further
  justification. A non-routine WLOG gets its reason, or a Remark before the statement; a
  trivial WLOG is not elaborated (the human, 2026-09).
- **Folklore notation and routine are not spelled out** (the human, 2026-11-20: "the proof
  uses many symbols … when the proof is generally simple"). A symbol from folklore is
  defined explicitly only when the text uses it extensively; otherwise a sentence of
  intuition stands for what working through the folklore routine shows. A routine
  verification (a chart transition, say) is named, not written out. A simple proof with
  many symbols is a defect even when correct.
- **No "clearly", "obviously", "trivially" or "it is easy to see"** as a reason
  (`paper-method`: they add nothing or mark the place the author stopped thinking). On a
  step that is not routine they hide a gap; on a routine step the reason (rule 8, a
  `\cref`) is shorter and better.

## 8. Inside a proof

- **Every inference carries its reason**: "by Lemma 5", "since *P* is convex", "by the
  triangle inequality". A pointer, not a paragraph.
- **Open directly**: the first deduction, a construction ("Let … and define …"), the goal
  ("We need to show …") or a reduction ("It suffices to …, since …"). No restating the
  statement. A plan only for a composite proof (rule 5).
- **Fix objects explicitly**, the ones the argument uses again (a symbol used once is a
  word; rule 7): "Let … be …", "Take …", "Denote …", "Fix …". Justify a choice
  where it is made ("Let *r* > 0 be smaller than half the shortest saddle connection; then
  …"). No "Normalise …; this is harmless, since …" paragraph, and no side remark that only
  reassures.
- **Display the computation that carries the proof**: the chain of (in)equalities, the
  formula for a map, the case-defined function; every formula that defines a map or a lift
  the argument uses, and every identity the argument turns on, even in a short proof. A
  routine verification (a chart transition) is named, not displayed (rule 7). A display is
  part of a sentence and gets the punctuation that implies. After a displayed chain, the
  reason for each non-immediate link is given by position ("the second equality by …, the
  last since …"). An equality of sets is proved as two stated inclusions.
- **End on the last deduction**: the contradiction reached, or the conclusion with the part
  it closes ("… completing the proof of (iii)"). No summary paragraph.

## 9. Citations and background

- **Cite rather than reprove.** A known result is reproved only with a stated reason ("for
  the reader's convenience"), and briefly. A result equivalent to a published one is cited,
  not restated (`paper-method`): no second copy of the source's formulation, no proof sketch
  of a trivial rewording; state ours once, with the reference (and the original authors'
  names when the source credits them).
- **Pinpoint every specific result**: "by [EFW18, Theorem 1.5]". A bare key only for a whole
  theory. When a step follows from a cited construction, name that result with a pinpoint;
  never "it follows".
- **Credit the original** (the human, 2026-11-14): for a result the text uses, cite the
  original with the exact theorem, as well as the source it was read in. Background and
  history get the short report below, not pinpoints. An analogue of a published result follows the
  original proof's lines, and says so with a pinpoint.
- **A report of sources is short** (the human, 2026-11-20): one general pointer
  ("definitions in more restricted settings are in [A], [B]"), less exact rather than
  exhaustive. A source's own setting is explained only when it matters to the paper's
  narrative, for instance a popular case the reader knows.
- **Check the cited hypotheses in place**, one short clause each, just before applying the
  result (`citation-discipline`).
- **Where background lives** (the human, 2026-11-14: "Facts should appear in the section by
  default"; 2026-11-20 for general theory). A Fact, or a heavily used external theorem
  restated with attribution, about the paper's own objects appears once, in the section
  that first needs it (in the preliminaries when several sections do), and is then cited
  by its internal number. General theory that is not specific to the paper's objects (the
  properties of normal coverings, say) goes to an appendix by default, and the section
  keeps only its setting-specific consequences (rule 2). Moving one of the paper's own
  statements or proofs to an appendix is the human's decision; a writer may propose it
  in a note.

## 10. Settings and symbols

- **One working setting** (the human, 2026-11-14): fix the setting whose structure is
  nicest and prove in it. Pass to another only where a result needs it, through the
  reductions below, never re-derived in each proof.
- **Nested settings: reduce, do not restate** (the human, 2026-11-20). When the paper has a
  base setting and wider or special ones (flat structures, dihedral flat structures,
  billiard tables), the plan is: state the basic properties in the base setting; define
  the wider setting together with a short list of its properties (about six) that make the
  reductions between the classes, once; then state each shared property once, for the
  wider setting. Where the list makes the reduction, the proof is the base case plus one
  sentence citing the list; where it does not, the proof has two steps inside one proof
  (the base case, then the reduction). Never one lemma per setting, since the statements
  would be almost the same. A special setting is given as an explicit example of the
  general one, and only what does not follow from the general setting alone is stated for
  it; that list is short, and the writer asks the human about each item on it.
- **Conventions are not pathologies** (the human, 2026-11-20). A remark that lists
  difficulties holds only real ones: a choice is a convention stated with the definition,
  a phenomenon is an example, and items that are the same thing (marked mirror points,
  sector points and cone points) are joined.
- **Letter families by role** (the human, 2026-11-14): each kind of object has a fixed
  letter family, in a fixed order of precedence, set once in the paper file's notation
  section. The letter follows the kind of object in the field's habit (the domain pack's
  `notation.md` where the paper file is silent); an unusual letter (a surface called *B*)
  is a finding even when it clashes with nothing yet. A derived object is named by
  decorating its letter, never by a fresh letter or one reserved for another role, and the
  main object gets the plainest symbol. Drop a decoration the context determines, and state
  a standing identification (objects up to isomorphism) once, where the objects are
  introduced (rule 2).

## 11. Source and voice

- **Split source lines freely**: one sentence, or one clause of a long sentence, per line;
  each display on its own lines (the human, 2026-11-14: "splitting lines in the source is
  well recommended"). A diff, a review comment or a margin note then points at one step,
  and rewording one sentence is a one-line diff. (The length limit of rule 3 counts output
  lines, not these.)
- **"We", present tense, short declarative sentences, one inference per sentence**, with the
  reason or the existence first (the human, 2026-11-14): "As *g* > 1, *ω* has a zero; let *σ*
  be one." Justify by "Indeed, …", not by a colon. Connectives *hence, so, thus, therefore,
  in particular, indeed*.
- **Never begin a sentence with a symbol**, also in text already accepted (the human,
  2026-11-14: enforced).
- **Signpost before you act** (`paper-method`): "We first prove the bound for finite groups;
  the general case follows by passing to a limit." Two sentences save a page. One idea per
  paragraph (rule 6).
- **One voice** (`aesthetic-vision`, item 7): consistent tense, person, terminology and
  level of formality across sections written at different times by different hands.

## 12. The paper as a whole

- **The arc** (`aesthetic-vision`, item 1). The paper tells one story. Results are revealed
  in the order a reader needs them: the main theorem stated early, the tools before the
  proofs that use them, the technical heart where the reader is ready for it. Every section
  earns its place in the arc; a section the arc does not need is an appendix or a different
  paper. The arc of a given paper is its `Drafts/vision.md`.
- **Abstract**: the result in one or two sentences, precise enough to be useful and plain
  enough for someone one field over. Not a table of contents.
- **Introduction**, the largest investment: context, then the main theorems stated in full
  (labelled Theorem A, B, … so they can be restated verbatim where proved, and the reader
  never pages back), then what is new, then a paragraph of proof strategy giving the *idea*
  rather than the details, then related work, then a short section outline last.
- **The introduction's promise kept** (`aesthetic-vision`, item 6). Every result the
  introduction announces is proved (or cited) in the body, in the form announced; the body
  proves nothing the introduction should have announced and did not.
- **Preliminaries**: only what is actually used; cite instead of reproducing a textbook
  chapter, stating precisely the form used (rule 9).
- **Body**: one idea per section, each opening with what it will produce, within the
  statement ceiling of rule 2 and the reductions of rule 10.
- **Appendices**: long computations and routine verifications a reader skips but a referee
  needs, general theory (rule 9), and the less trivial proofs of elementary properties the
  body names in one sentence (rule 2); moving the paper's own material there is the human's
  decision.
- **Examples and figures where they carry the idea** (`aesthetic-vision`, item 5): an
  example right after a definition that is hard to picture; a figure where a picture
  replaces a paragraph (rule 5). Never decoration.

## 13. Notation

- **One object, one symbol; one symbol, one meaning** within a document. A clash is a
  finding, not a style preference. One name per object, also for words (the human, 2026-09:
  "Three distinct names, one per torus").
- **Introduce before use.** Every symbol is defined, or points to its definition, before its
  first use; a result stated in the introduction points forward.
- **Notation that earns its place** (`aesthetic-vision`, item 3). A symbol is introduced only
  when it is used again (a symbol used once is a word: rules 7 and 8), once, before its first
  use. Notation used throughout is collected in the paper's notation section (rule 4);
  notation used locally is introduced where it is used; never both.
- **The letter follows the kind of object** (rule 10).
- **Follow the settled choices** (the paper file) even where you would choose differently.
  Propose a change; do not make it. A rename is its own item, never a side effect of other
  work, with a machine note at each changed site.
- **Quoted statements keep the source's notation**, verbatim, with a sentence translating
  it if it differs.
- **Named terms are notation too.** A defined word is used in its defined sense only; a
  second sense needs a different word.
- **The draft and the paper file** (the human, 2026-11-20). The human's dated notation
  decisions in the paper file lead the draft: new text follows them, and a place where the
  draft still differs is a clash to fix in the draft (a ticket), never a reason to change
  the decision. Where the paper file has no decision, the draft's usage is the record, and
  the notation-auditor writes it into the paper file. A change to the domain's standard notation is a
  `notation` ticket to the Expert; who changes what is the `notation-discipline` skill.

## 14. LaTeX habits

- **Cross-references** are always `\cref{…}` / `\Cref{…}`, never a hand-typed
  "Theorem~\ref{…}", so the type can never drift from the target, with typed label prefixes
  (`thm:` `lem:` `prop:` `cor:` `defn:` `eq:` `sec:` `fig:`; the paper's own list is its
  `author.labels`).
- **Items are referred to by `\cref`** (the human, 2026-11-15: "Item numberings- use cref to
  refer"). Every item that is referred to carries a label (`it:…`), and every reference to
  it, inside its proof or elsewhere, is `\cref{it:…}` (or `\cref{lem:…}, \cref{it:…}`), never
  a hand-typed "item (i)", "(2)" or "the first item". The printed numbering then follows the
  environment. In a proof that treats the items in order, the paragraph opener is
  "For \cref{it:…}, …".
- **Macros.** Use the ones that exist. Define a new one only for an object with structure
  that recurs, and say that you did. Never define a second macro for something already
  covered: that is how a preamble becomes a second language the coauthors must learn. A
  preamble change goes as the home's `author.preamble.policy` says (`editing-tex.md`).
- **Bibliography.** Entries come from a fetched record, never typed from memory and never
  invented (`citation-discipline`); in the academy only the Expert's librarian edits the
  bibliography. Include both arXiv and published references when both exist.
- **Small habits in the text, recommended for new text** (`modern-latex.md`, where the
  preamble provides them; the human, 2026-11-20: they bind new text only and are never a
  reason to rewrite accepted text): `\left…\right` only where the
  content needs scaling (prefer `\bigl(` and kin when the size is known); `\emph` rather
  than `\textit`; `\dots` rather than `\ldots`/`\cdots`; `\operatorname{…}` for a one-off
  operator, `\DeclareMathOperator` (a preamble change) only for one used repeatedly;
  `\coloneqq` for a new definition; `enumitem` labels (`[label=(\roman*)]`) rather than
  redefining `\labelenumi`.

## 15. Figures and captions

- **A figure earns its place** (rule 5 and rule 12 say where one is owed). A
  textbook-standard picture (the unfolding of a billiard, a polygon with its glued sides) is
  cited from the book or article, not redrawn (the Author's PR reviews, 2026-11).
- **Legible and plain**: no table and no running text inside a figure; every label legible
  at the printed width (judge the rendered page at the real width, not zoomed); several
  small panels become a grid of large ones (2x2) with bare symbols only; legible in
  grayscale.
- **The caption** is two or three sentences and stands alone; the paragraph that cites the
  figure carries the explanation.
- **Consistency across the paper** in marks, shading and labels; the domain's drawing
  conventions are the pack's `figures.md`, unless the paper file settles otherwise. Each
  figure is its own file, compiled alone while iterating.

## 16. From notes, or a delivered proof, to the paper

- **The order of discovery is not the order of exposition.** Notes run bottom-up (what
  could be proved); a paper runs top-down (what the reader needs). Expect to invert the
  structure.
- **Name the lemmas a long computation hides**, within rule 3: a step becomes a lemma only
  when it earns a statement there.
- **Preserve every hypothesis, including the tacit ones.** Notes carry standing
  assumptions in the author's head. Hunt for them and state them; a silently dropped
  hypothesis is a false theorem.
- **Flag, do not smooth.** Where the source is compressed or skips a step, mark it (rule 1)
  instead of writing fluent prose across the gap, and say so in the report.

## In a notebook attempt

The attempt keeps its sections (*Statement as attempted*, *Strategy*, *Proof*, *Inputs and
their status*, *Gaps*).

- *Strategy* holds the plan and the intuition: a few sentences for an ordinary proof; a
  fuller paragraph for a composite proof kept together, with a sketch of the figure it
  needs.
- *Proof* is written as it would appear in the paper.
- Intermediate results are split out as their own claim objects (rule 3), each with its
  own short proof.
- Reasoning that did not survive goes under *Why it fails*, not into *Proof*.

## For reviewers

Judge correctness first. Style findings go in a separate list, each citing its rule (of this
guide, or of the paper file by its section), and never change the verdict. The findings that
matter most, in the rules' order:

- a missing piece passed off as routine, a proof dropped as folklore without the human's
  word, or a statement resting on an unverified input without the unverified colour (rule 1);
- a duplicate: an item copying a lemma, a statement another contains, a second proof, a
  restated fact or a recalled definition; a section past about 30 statements (examples
  and remarks included), or an elementary property given its own lemma (rule 2);
- a step used elsewhere left inside another proof, a lemma a graduate reader supplies at
  once, or a proof over about 15 output lines (rule 3);
- a statement out of dependency order, in the wrong environment for its role, holding
  reasoning or discussion, or listing properties of different objects (rule 4);
- a composite proof or a chain with no plan or intuition (rule 5);
- discussion inside a statement, or inside a proof outside rule 5; two remarks in a row
  (rule 6);
- an omission without a pointer, or a routine step left unnamed (rule 7);
- an inference without its reason (rule 8);
- a symbol with two meanings, an object with two symbols, a symbol used before it is
  introduced, or a departure from the paper file's settled notation (rule 13);
- a hand-typed reference to a statement or an item (rule 14).
