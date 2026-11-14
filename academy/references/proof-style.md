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

## 2. Short statements in a chain, not one long proof

- **A proof is short.** Most are 1–10 lines. Past about **15 lines of output** (the typeset
  PDF at the paper's text width, displays included; the rendered Markdown for a notebook
  attempt; never the source), extract a lemma. A proof that keeps growing is a sign to
  re-plan the chain with the human (a supporting lemma or a better definition), not to push on.
- **Build a chain:** definition, lemma, corollary, each small. A corollary's proof is often
  one line ("Follows from Lemma 6.").
- **The main theorem is an assembly** of named results in a few sentences ("By Lemma 2.13
  … Hence Proposition 2.10 gives the result"). When the parts come later: "Proof of
  Theorem 1 assuming Propositions 3 and 6", then each under "Proof of Proposition 3."
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
- Discussion that **clarifies a main idea** of a step is welcome here, and only here (rule 4).

## 4. Discussion and intuition live outside the proof

SW08's way (the human, 2026-11-14; earlier: "Way too much discussion").

- **A proof is deduction.** The exception is a composite proof kept together (rule 3).
- **A statement holds assumptions, then the claim in one sentence, then optionally a list
  of properties.** No reasoning, motivation or discussion inside a statement environment.
- **Intuition** for a statement goes in its own paragraph before it, or before the group of
  results it explains.
- **Alternative arguments, sharpness examples and asides** go in a Remark or Example after
  the proof.

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

## 6. Inside a proof

- **Every inference carries its reason in the same sentence**: "by Lemma 5", "since *P* is
  convex", "by the triangle inequality". A pointer, not a paragraph.
- **Open directly**: the first deduction, a construction ("Let … and define …"), the goal
  ("We need to show …") or a reduction ("It suffices to …, since …"). No restating the
  statement. A plan only for a composite proof (rule 3).
- **Fix objects explicitly**: "Let … be …", "Take …", "Denote …". Justify a choice where it
  is made ("Let *r* > 0 be smaller than half the shortest saddle connection; then …").
- **Display the computation that carries the proof**: the chain of (in)equalities, the
  formula for a map, the case-defined function. A display is part of a sentence.
- **End on the last deduction**: the contradiction reached, or the conclusion with the part
  it closes ("… completing the proof of (iii)"). No summary paragraph.

## 7. Statements, definitions and names

- **Definitions and notation come before the statement** that uses them, not inside a
  proof, when they are used again. An explicit construction (a map, an atlas, a
  decomposition) is a definition of its own, given before the claims about it.
- **A statement with several conclusions lists them** ((i)–(iii) or bullets), and its proof
  follows the same list.
- **A short name in brackets** for a statement referred to by content: "Lemma 6 [Lower
  bound on path metric]".

## 8. Citations

- **Cite rather than reprove.** A known result is reproved only with a stated reason ("for
  the reader's convenience"), and briefly.
- **Pinpoint every specific result**: "by [EFW18, Theorem 1.5]". A bare key only for a whole
  theory.
- **Check the cited hypotheses in place**, one short clause each, just before applying the
  result (`citation-discipline`). A heavily used external theorem is restated once in the
  preliminaries with attribution, then cited by its internal number.

## 9. Source and voice

- **Split source lines freely**: one sentence, or one clause of a long sentence, per line;
  each display on its own lines. A diff, a review comment or a margin note then points at
  one step. (The length limit of rule 2 counts output lines, not these.)
- "We", present tense, short declarative sentences; connectives *hence, so, thus,
  therefore, in particular, indeed*. Never begin a sentence with a symbol.

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
