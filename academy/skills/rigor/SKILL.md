---
name: rigor
description: 'Discipline for honest research mathematics: pin the statement down, test before proving, hunt for gaps, report established versus assumed. Use whenever asked to prove, disprove, verify or repair a claim or review a proof ("is this proof correct").'
---

# Doing mathematics honestly

The most damaging thing you can produce is an argument that *reads* correct but is
not. Fluent prose is exactly what makes a bad proof dangerous: a gap in confident
notation can survive months and reach a referee. A flagged gap costs an afternoon.

**The confidence of the writing must track the actual state of the argument.**
Everything below is machinery for making that true. Also load the active domain
pack's `traps.md` (through `domain_get`): it lists the ways this subject's arguments
usually go wrong.

## 1. Pin the statement down first

Most failed proofs are attempts on the wrong statement. If the original was
ambiguous, say which reading you settled on.

- **Write the quantifiers out.** `∀ε ∃N ∀n>N` and `∃N ∀ε ∀n>N` are different
  theorems, and "for large n" hides which one is meant. Uniformity is where most
  errors live.
- **List the hypotheses separately**, including inherited ones (standing assumptions,
  the ambient setting, "throughout this section X is compact"). At the end, check
  which you used. An unused hypothesis means the result is stronger than claimed, or
  a case was skipped.
- **Name the degenerate cases** the statement must survive: empty set, zero, one
  point, the trivial group, the boundary of the parameter range. A claim is most often
  literally false there, and needs a hypothesis rather than a proof.

## 2. Test before you prove

Proving a false statement is the most expensive failure, and ten minutes usually
avoids it.

- Check the smallest nontrivial example and the most degenerate one. If a computation
  can be run, run it (Scientist, or the pack's `computation/`). Numerics cannot prove,
  but they can refute, and refutation is cheap.
- Try to break it: push a parameter to an extreme, drop a hypothesis and see what
  fails, look for a scaling or symmetry the claim should respect.
- A counterexample is a *success*. Present it concretely, verify it explicitly, and
  propose the repaired statement (an added hypothesis, or "finitely many exceptions").

## 3. The gap-hunter's checklist

Read your own argument as a hostile referee.

- **"Clearly" / "it is easy to see" / "similarly".** Each is a place you chose not to
  think. Supply the reason or mark it as an assumption.
- **"The other case follows similarly."** Check it. Asymmetric cases hide here.
- **Existence used before it is established.** A minimal element, a limit, a fixed
  point: is the set nonempty, the space complete, the family compact?
- **Finiteness and convergence assumed silently** for sums, limits, intersections.
- **Choices that must be uniform.** Trace what each chosen constant, neighbourhood or
  index depends on, against the quantifiers of section 1.
- **Circularity.** Draw the dependency order of the lemmas once.
- **Misapplied citation.** The cited theorem's hypotheses must be *verified for your
  objects*, not merely plausible for them. This is the most common serious error in
  an otherwise sound paper, because it looks like scholarship (`citation-discipline`).

## 4. Earn the flag before you write it

Flagging has its own failure mode: it becomes a substitute for thinking. A neatly
marked "unresolved" feels honest and costs nothing, so it is tempting exactly when the
mathematics gets hard. A gap marker is a last resort, not a deliverable. Before
writing one, or reporting "not settled":

- **Say what a counterexample would have to look like**: which object, which
  parameters, what would have to go wrong, what the smallest case is. Writing that
  down often produces the example. A claim you cannot prove is often false, and the
  shape of the obstruction is the shape of the counterexample.
- **Then try to build one.** Search the small cases by hand or by computation.
- **A blocked route is not a blocked question.** "The known construction does not
  transfer here, because the relevant points behave differently" is a fact about one
  route, not evidence that no counterexample exists.
- **Record the class you searched.** "No counterexample among objects of size ≤ 6,
  over pairs of distinguished points only." A search over a class that structurally
  excludes the answer is worth nothing, and stating the class makes that visible.
- **Watch the verification-to-insight ratio.** Validation layers around a computation
  are not a substitute for the clean argument. Ask whether two minutes of thought
  settles it outright.

## 5. Report what you actually have

End every piece of work with one status from `status-vocabulary`, and if it is not
`proved`, say so in the first sentence:

| You have | Report |
|---|---|
| A complete argument, every step justified, citations verified | `proved` (still needs two agreeing verdicts to be recorded as such) |
| A complete argument given named inputs used as black boxes | `proved-modulo`, with the inputs listed as `modulo` |
| A reduction to a cleaner statement | `proved-modulo`, with the reduction target as the `modulo` input |
| Proofs under extra hypotheses or in special cases | split: each proved case is its own claim; the general claim stays `open` and depends on them; say what breaks in general |
| An explicit, verified counterexample | `refuted` (or `refuted-as-stated` with the repaired statement) |
| Nothing settled | `open` / `conjectured` / `sketch`: what you tried, where it broke, the class searched, the obstruction you suspect |

"Not settled" without a described counterexample attempt is a weaker answer than it
looks. Mark the seams inside a written argument too, with the home's machine-note
macro or a bracketed "[gap: needs hypothesis H — not checked]", so nothing unproved
escapes into a submitted version (`honest-reporting`).

## 6. Working on someone else's draft

Say which of three operations you did:

- **Transcription**: same argument, better prose. Safe.
- **Repair**: the argument had a gap and you changed the mathematics. Flag it
  prominently; they must check it.
- **Replacement**: a different proof. Say so, and why; they may have had a reason.

If a step looks wrong, neither quietly fix it nor declare it wrong: state precisely
what you cannot verify and what would make it go through. Assume a competent author,
so an apparent error is more likely a compression than a mistake, but flag it anyway.
