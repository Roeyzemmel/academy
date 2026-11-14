# Proof style

How a proof is written by every agent that writes or rewrites one: the prover (notebook
attempts), math-writer and math-editor (the paper), and the reviewers who judge them.
`rigor` decides whether an argument is *correct*; this file decides what a correct
argument *looks like*. A style defect is never a gap: a reviewer reports it as a separate
style finding.

**Models** (the human, 2026-11-14): the human's own notes *Dynamics on moduli spaces of translation
surfaces — exercises solution*; Apisa–Wright `AW21`; Lelièvre–Monteil–Weiss `LMW16`;
Smillie–Weiss `SW08`. Where they disagree, the human's choice is recorded at the rule. A paper
home's `Drafts/vision.md` wins over this file.

The rules are in order of weight: when two pull apart, the earlier one wins.

## 1. Every statement is fully proved or precisely cited

The human, 2026-11-14: "I am a master's student and do not have the reputation to leave
half-proved statements."

- **No "Proof sketch" in the paper.** A sketch is a notebook status (`sketch`) and a draft
  colour, never a heading.
- **Nothing is left to the reader wholesale** (AW21's and SW08's way, not LMW16's): no
  whole case, lemma or direction. What may be skipped is listed in rule 5, and only with a
  pointer.
- **Never left out:** the construction, the key estimate, why a map is well defined, and
  each use of a cited or deep result. A missing idea or hypothesis is a gap, not an
  omission.
- **Uncertainty is marked, never written around.** In the paper, the draft colour or a
  `\Claude{…}` note; in the notebook, the attempt's *Gaps* list. A speculation ("the bound
  can likely be improved by …") is a Remark marked as unverified.
- **A statement resting on an unverified input is marked unverified** (the human, 2026-11-14): when a proof is
  rewritten or a lemma newly extracted, the statement using it, and everything resting on
  it, takes the draft colour (or `sketch`) until the input is verified. Never keep an
  outdated proof, or leave the colour unchanged, to avoid the cascade.
- **Folklore is the human's call** (the human, 2026-11-14): "folklore statements may be subtly assumed or
  stated as a fact, decision on my word for what I find folklore as it may be in the
  paper's direct topic or in more classical theory." Folklore, in the text's own topic or
  in classical theory, may be used silently or stated as a Fact without proof. Easy steps
  of the text's own arguments are not folklore: they are short lemmas (rule 2). A writer who
  thinks a statement is folklore asks the human; it never drops a proof on its own judgement.
- **Nothing depends on a question or a conjecture** (the human, 2026-11-14): "Dependence on questions is
  undefined." Remove the reference, or turn the dependence into a stated hypothesis and name
  the statement that justifies it.

## 2. Short statements in a chain, not one long proof

- **A proof is short.** Most are 1–10 lines. Past about **15 lines of output** (the typeset
  PDF at the paper's text width, displays included; the rendered Markdown for a notebook
  attempt; never the source), extract a lemma. A proof that keeps growing is a sign to
  re-plan the chain with the human (a supporting lemma or a better definition), not to push on.
- **Extract every step with its own conclusion** (the human, 2026-11-14), even an easy one, even when the proof
  is under the limit ("easy steps that can pose as lemmas"). Extract the steps that hold
  without the main statement's special hypothesis, and keep the step that uses it in the
  main proof. Never cite a paragraph or step inside another proof: an argument used
  elsewhere is a lemma.
- **An argument that handles objects one at a time is an induction** (the human, 2026-11-14): the one-object
  step is a lemma (or an item of the statement it belongs to), and the general case follows
  by induction, with the inductive statement strengthened if needed.
- **Build a chain:** definition, lemma, corollary, each small. A corollary's proof is often
  one line ("Follows from Lemma 6.").
- **The main theorem is an assembly** of named results in a few sentences ("By Lemma 2.13
  … Hence Proposition 2.10 gives the result"). When the parts come later: "Proof of
  Theorem 1 assuming Propositions 3 and 6", then each under "Proof of Proposition 3."
- **The statement comes at the end of its chain** by default (the human, 2026-11-14), after the lemmas it rests
  on, so its proof follows it. It comes before its lemmas only when it is a theorem stated
  in the introduction (of the section or the paper), or for a narrative reason; its proof,
  separated from it, then opens "Proof of Theorem N."
- **An item is never a copy of a lemma** (the human, 2026-11-14): "I don't allow duplications." A lemma is
  extracted from a listed statement only when it is more general than the item, or treats a
  special case the item is then reduced to; the item's proof then applies or reduces to it
  in one sentence ("Item (ii) follows from Lemma B applied to π."). A lemma that would state
  exactly what an item states is not extracted: the item is proved in place. Items are
  proved in paragraphs ("For the first item, …"), never in an itemised list, with no "we
  prove the items in order" preamble.
- **A definition defines one notion** (the human, 2026-11-14), and the length limit applies to it too. Split a
  definition that introduces several objects into consecutive definitions, with short
  discussion between them (SW08's way). Define a property of an element in words, then
  name the set of such elements; no itemised list or set-builder display for one notion.
- **Labels are a warning sign.** A proof that needs parts, steps or cases is often proving
  a composite statement. First try to split it into a chain of claims: each step its own
  lemma, each conclusion of a listed statement its own lemma or corollary.
- **When not to extract:** the sub-statement's setting is so specific to this proof that,
  stated alone, it would restate the whole setup or mean nothing outside the proof. Then
  keep the proof together and write it as in rule 3.

## 3. A composite proof that stays together is written for the reader

- It **opens with a plan**: the steps and how they combine ("The proof proceeds in three
  steps …").
- It gives the **intuition before the details**: the main idea, in a few sentences.
- Each step is its **own clear paragraph**, opening with a run-in bold label that says what
  it establishes ("**Step 1:** *p* lies in a cylinder of *C*.", "**Case 1.** *x = y* is
  nonsingular.", "**Well-defined.**"). No nested lists of reasoning.
- A **diagram or figure** is added where it carries the idea: a commutative diagram for the
  maps, a picture of the surface or the cylinders for the geometry.
- The closing deduction needs **no "Conclusion" label** (the human, 2026-11-14): it is
  written as plain text after the last step.
- Discussion that **clarifies a main idea** of a step is welcome here, and only here (rule 4).
- **A chain gets its plan before it** (the human, 2026-11-14): when one long proof becomes a chain, a short
  paragraph before the chain gives the idea and names the lemmas in the order they are used.
  Where the text turns from the general case to a special family, a narrative paragraph says
  why it is treated; a long group gets its own subsection.
- **Figures beyond composite proofs** (the human, 2026-11-14): every counterexample, and every example or remark
  describing concrete configurations, gets a figure showing the situation that makes it
  work. A schematic figure says that it is schematic and what it does not show.

## 4. Discussion and intuition live outside the proof

SW08's way (the human, 2026-11-14; earlier: "Way too much discussion").

- **A proof is deduction.** The exception is a composite proof kept together (rule 3).
- **A statement holds assumptions, then the claim in one sentence, then optionally a list
  of properties.** No reasoning, motivation or discussion inside a statement environment.
- **Intuition** for a statement goes in its own paragraph before it, or before the group of
  results it explains.
- **Sharpness examples and asides** go in a Remark or Example after the proof.
- **One proof per statement** (the human, 2026-11-14: "Default to deleting alternative
  proofs."). Keep the shorter one that reuses a result already in the text; the other is
  deleted, not kept as a Remark.
- **A paragraph, remark or example carries one discussion** (the human, 2026-11-14). Separate
  an example's configurations from a general analysis of them, and give the analysis its own
  short remark by the shortest route (a structural fact or a citation). Compact a long
  expository paragraph, or split it into short ones, one idea each.

## 5. Written for a graduate reader in the field

- **Leave out, and say which, in one clause with a pointer:** definitional checks,
  immediate converses, and cases analogous to one written ("The other direction is
  trivial." "The argument for *p_b* is the same." "The proof of (ii) is identical, with *x*
  replaced by *ξ*.").
- **WLOG, contradiction, passing to a subsequence:** one clause, not justified when
  routine ("WLOG *V* = *B(x, r)*"). A non-routine WLOG gets its reason, or a Remark before
  the statement.
- **No "clearly" or "it is easy to see"** on a step that is not routine. On a routine step
  the reason (rule 6) is shorter and better.
- **A routine method is named, never silent** (the human, 2026-11-14): "Routine methods may be removed or
  extracted into facts. Explicitness is required, taking form of specifying the routine's
  common name." Write "by induction on the number of marked points", "by compactness", not
  nothing.
- **Say it once** (the human, 2026-11-14): state each fact once and prove each property once, then point to it;
  no restatement, even within one paragraph. Do not recall a definition, its working form or
  a convention at the start of each proof that uses it: give it once, before the group of
  results, and cite it. An item that holds by definition is proved by the words "by
  definition", with the definition cited.

## 6. Inside a proof

- **Every inference carries its reason in the same sentence**: "by Lemma 5", "since *P* is
  convex", "by the triangle inequality". A pointer, not a paragraph.
- **Open directly**: the first deduction, a construction ("Let … and define …"), the goal
  ("We need to show …") or a reduction ("It suffices to …, since …"). No restating the
  statement. A plan only for a composite proof (rule 3).
- **Fix objects explicitly**: "Let … be …", "Take …", "Denote …", "Fix …". No "Normalise …;
  this is harmless, since …" paragraph, and no side remark that only reassures. Justify a
  choice where it is made ("Let *r* > 0 be smaller than half the shortest saddle connection; then …").
- **Display the computation that carries the proof**: the chain of (in)equalities, the
  formula for a map, the case-defined function. A display is part of a sentence. Every
  formula that defines a map or a lift, and every identity the argument turns on, is
  displayed, even in a short proof. After a displayed chain, the reason for each
  non-immediate link is given by position ("the second equality by …, the last since …").
  An equality of sets is proved as two stated inclusions.
- **End on the last deduction**: the contradiction reached, or the conclusion with the part
  it closes ("… completing the proof of (iii)"). No summary paragraph.

## 7. Statements, definitions and names

- **Definitions and notation come before the statement** that uses them, not inside a
  proof, when they are used again. An explicit construction (a map, an atlas, a
  decomposition) is a definition of its own, given before the claims about it.
- **Statements come in constructive order** (the human, 2026-11-14): supporting statements
  before what uses them. Main theorems are the exception: they may appear in the
  introduction of the section or of the whole paper. Within the freedom dependency leaves
  ("Dependency order precedes difficulty"), go from the easiest and shortest to the hardest
  and longest, and place an elementary example that needs no heavy setup early.
- **Shared hypotheses and notation are given once before the statements** (the human,
  2026-11-14): a "Setting" definition, a sentence of standing assumptions or a run-in
  *Notation.* paragraph, which each statement cites. A statement never defines notation in
  passing; notation used across sections is defined once in the introduction. A section may
  open with a "Setup and notation" subsection when its shared setting needs one.
- **No two statements state the same thing** (the human, 2026-11-14), for instance a lemma
  that another statement merely quotes. A lemma is extracted when a more general
  phenomenon occurs, or when a special case is treated and then reduced into; a list
  inside one statement is for narrative reasons, to consolidate several statements.
- **A statement holds only what it adds** (the human, 2026-11-14). Delete an item, remark or
  corollary that is a special case of another statement, contained in one, or immediate from
  the statements it rests on (a trivial corollary is folded into a sentence), and cite those
  statements where it was used. Fold a remark that extends a statement into that statement.
- **A statement may be a list of statements when they all describe properties of a single
  object** (the human, 2026-11-14); statements about different objects are separate.
- **The environment marks the role** (the human, 2026-11-14): the result a section exists for
  is a Theorem; a subsection's main result a Proposition; statements proved to feed it are
  Lemmas; what follows in a few lines a Corollary; a folklore input a Fact (rule 1). Split a
  trailing "so …" conclusion off as its Corollary, and rename the environment when
  extraction changes a statement's role.
- **A Question opens with its setup** ("Let … . We ask:"), then one question per item and
  what it turns on; what a positive answer would give, and which questions depend on which,
  come after the list.
- **A statement with several conclusions lists them** ((i)–(iii) or bullets), and its proof
  follows the same list.
- **A short name in brackets** for a statement referred to by content: "Lemma 6 [Lower
  bound on path metric]". The name of an example, counterexample or remark says what it
  is and the situation it shows ("Counterexample where *Y* is a torus"), not the hypothesis
  it discusses.

## 8. Citations

- **Cite rather than reprove.** A known result is reproved only with a stated reason ("for
  the reader's convenience"), and briefly.
- **Pinpoint every specific result**: "by [EFW18, Theorem 1.5]". A bare key only for a whole
  theory.
- **Check the cited hypotheses in place**, one short clause each, just before applying the
  result (`citation-discipline`). A heavily used external theorem is restated once in the
  preliminaries with attribution, then cited by its internal number.
- **Credit the original** (the human, 2026-11-14): cite the original with the exact theorem,
  as well as the source it was read in. When a step follows from a cited construction, name
  that result with a pinpoint; never "it follows". An analogue of a published result follows
  the original proof's lines, and says so with a pinpoint.
- **Background is stated once** (the human, 2026-11-14), then cited, never re-derived. A Fact
  appears by default in the section that uses it ("Facts should appear in the section by
  default"); moving it to an appendix is the human's decision, which a writer may propose.

## 9. Source and voice

- **Split source lines freely**: one sentence, or one clause of a long sentence, per line;
  each display on its own lines. A diff, a review comment or a margin note then points at
  one step. (The length limit of rule 2 counts output lines, not these.)
- "We", present tense, short declarative sentences; connectives *hence, so, thus,
  therefore, in particular, indeed*. Never begin a sentence with a symbol: enforced, also in
  text already accepted (the human, 2026-11-14).
- **One inference per sentence, the reason or the existence first** (the human,
  2026-11-14): "As *g* > 1, *ω* has a zero; let *σ* be one." Justify by "Indeed, …", not by a
  colon.

## 10. Settings and symbols

- **One working setting** (the human, 2026-11-14): fix the setting whose structure is
  nicest and state every result in it. Pass to another only where a result needs it, once,
  through one cited remark, not in each proof.
- **Letter families by role** (the human, 2026-11-14): each kind of object has a fixed
  letter family, in a fixed order of precedence, set once in the home's notation decisions.
  A derived object is named by decorating its letter, never by a fresh letter or one
  reserved for another role, and the main object gets the plainest symbol. Drop a decoration
  the context determines, and state a standing identification (objects up to isomorphism)
  once, where the objects are introduced.

## In a notebook attempt

The attempt keeps its sections (*Statement as attempted*, *Strategy*, *Proof*, *Inputs and
their status*, *Gaps*).

- *Strategy* holds the plan and the intuition: a few sentences for an ordinary proof; a
  fuller paragraph for a composite proof kept together, with a sketch of the figure it
  needs.
- *Proof* is written as it would appear in the paper.
- Intermediate results are split out as their own claim objects (rule 2), each with its
  own short proof.
- Reasoning that did not survive goes under *Why it fails*, not into *Proof*.

## For reviewers

Judge correctness first. Style findings go in a separate list, each citing its rule, and
never change the verdict. The findings that matter most are:

- a missing piece passed off as routine (rule 1);
- a proof over about 15 output lines with an extractable lemma, or a labelled proof whose
  steps could be a chain of claims (rule 2);
- a composite proof with no plan or intuition (rule 3);
- discussion inside a statement, or inside a proof outside rule 3 (rule 4);
- an omission without a pointer (rule 5);
- an inference without its reason (rule 6).
- a duplicate: a lemma that an item copies, a statement another contains, a restated fact
  or a recalled definition (rules 2, 5, 7);
- a statement resting on an unverified input without the unverified colour (rule 1);
- a proof dropped as folklore without the human's word (rule 1).
