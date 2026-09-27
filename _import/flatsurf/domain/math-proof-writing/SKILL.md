---
name: math-proof-writing
description: Discipline for doing research-level mathematics honestly — attacking a claim, hunting for gaps in a proof, and reporting what was actually established versus what was assumed. Use this whenever the task involves proving, disproving, verifying, or repairing a mathematical claim; checking whether a step in a draft is justified; turning a sketch or a piece of scratchwork into a rigorous argument; or deciding whether a conjecture is even true. Trigger on "is this proof correct", "prove that", "does this argument work", "fill in the details", "why is this step justified", "check my lemma", "find the gap", or any request to write up mathematics that will end up in a paper. Applies to all of mathematics, not one subfield.
---

# Doing mathematics honestly

The single most damaging thing you can do in mathematical research is produce an
argument that *reads* correct but is not. Prose fluency is exactly the skill that
makes a bad proof dangerous: a gap dressed in confident notation can survive
months and reach a referee. A gap that is flagged costs an afternoon.

So the governing rule is: **the confidence of the writing must track the actual
state of the argument.** Everything below is machinery for making that true.

## Before attacking anything: pin the statement down

Most failed proof attempts are attempts on the wrong statement. Spend the first
few minutes making the claim unambiguous, and say out loud what you settled on if
the original was ambiguous.

- **Write the quantifier structure explicitly.** `∀ε ∃N ∀n>N` and `∃N ∀ε ∀n>N`
  are different theorems and the prose "for large n" hides which one is meant.
  Uniformity is where most errors live.
- **List the hypotheses separately**, including the ones inherited from context
  (standing assumptions in the paper, the ambient setting, "throughout this
  section X is compact"). Then, at the end, check which ones you actually used.
  A hypothesis you never used is either a sign the result is stronger than
  claimed, or a sign you skipped a case.
- **Identify the degenerate cases** the statement has to survive: empty set, zero,
  one point, the trivial group, genus zero, the boundary of the parameter range.
  These are where a claim is most often literally false as stated and needs a
  hypothesis added rather than a proof found.

## Test before you prove

Trying to prove a false statement is the most expensive failure mode, and it is
usually avoidable in ten minutes. Before investing in a proof:

- Check the claim on the smallest nontrivial example, and on the most degenerate
  one. If a computation can be run, run it — see whether this session has a
  domain skill for computational experiments and use it. Numerics cannot prove
  the statement, but they can *refute* it, and refutation is cheap.
- Try to break it: push a parameter to an extreme, remove a hypothesis and see
  what fails, look for a scaling or symmetry the claim ought to respect.
- If the statement survives, the failed attacks are not wasted — they usually
  reveal which hypothesis is doing the real work, which is the seed of the proof.

If you find a counterexample, that is a *success*, not a failure to report
apologetically. Present it concretely, verify it explicitly, and then propose the
repaired statement — usually the original claim with an extra hypothesis, or with
"finitely many exceptions" inserted.

## While proving: the gap-hunter's checklist

Read your own argument as a hostile referee would. The recurring failure modes:

- **The unjustified "clearly" / "it is easy to see" / "similarly".** Each one is a
  place you decided not to think. Sometimes that is correct and the step really is
  routine. Sometimes it is where the proof is wrong. Go back to each one and
  either supply the reason or mark it as an assumption.
- **"Similarly, the other case follows."** Check that it does. Asymmetric cases
  hide here constantly.
- **Existence used before it is established.** You picked a minimal element, a
  limit, a geodesic, a fixed point — does it exist? Is the set nonempty, the space
  complete, the family compact?
- **Finiteness and convergence assumed silently.** Sums, limits, and intersections
  that are implicitly assumed finite or convergent.
- **Choices that must be uniform.** A constant, a neighborhood, or an index chosen
  depending on something it should not depend on. Trace what each chosen object
  depends on and check it against the quantifier structure you wrote down.
- **Circularity.** The lemma invoked in step 4 is proved using the proposition
  step 4 is establishing. Draw the dependency order of your lemmas once.
- **Misapplied citation.** The cited theorem's hypotheses must be *verified for
  your objects*, not merely plausible for them. This is the most common serious
  error in a paper that is otherwise fine, because it looks like scholarship.

## The effort budget: earn the flag before you write it

Everything above tells you to mark what you have not established. That machinery
has a failure mode, and it is a real one: **flagging becomes a substitute for
thinking.** A beautifully-marked "this step is unresolved" feels like honest work
and costs nothing, so it is tempting to reach for it at exactly the moment the
mathematics gets hard — which is the moment the mathematics is worth doing. A gap
marker is a last resort, not a deliverable.

So before writing any marker, or reporting "not settled":

- **Say what a counterexample would have to look like.** Concretely: which
  surface, which genus, what would have to go wrong, what the smallest case is.
  Writing the specification usually takes two minutes and very often produces the
  example — a claim you cannot yet prove is frequently a claim that is false, and
  the shape of the obstruction is the shape of the counterexample.
- **Then actually try to build one.** Search the small cases by hand or by
  computation. Push the hypothesis you suspect is doing the work until it breaks.
- **If a route looks blocked, do not conclude the question is.** "Tokarsky's
  construction doesn't transfer, because those corners unfold to regular points"
  is a correct observation about one route. It is not evidence that no
  counterexample exists, and treating it as such is how a findable example gets
  written up as an open question.
- **Record the class you searched.** A negative search result is only meaningful
  alongside what it covered: "no counterexample among origamis with ≤ 6 squares,
  searching over vertex pairs only". Say that plainly, so a reader can see whether
  the class could even have contained the answer. A search over a class that
  structurally excludes the counterexample is worth nothing, and stating the class
  is what makes that visible — to the reader and to you.
- **Watch the verification-to-insight ratio.** Elaborate sanity checks around a
  result are not a substitute for finding the clean argument. If a computation is
  being wrapped in validation layers, stop and ask whether two minutes of thought
  settles it outright — often the good proof is short and was one observation
  away. Verification is for results you could not see through; it is not a way of
  looking busy in front of a hard question.

The honest report is still the goal. This section is about making sure the report
is honest *and* that you did the work first.

## Citations: the hard rule

Never invent a theorem, an author, a paper, a numbering, or a year. If you need a
result and are not certain of its exact statement and source, do one of two
things: look it up, or state it as a labelled assumption you are using and flag
that it needs a reference.

When you do cite, the hypotheses of the cited result get verified explicitly for
the case at hand, in writing. "By [EM18], the orbit closure is an affine invariant
submanifold" is only legitimate once it is said why the ambient hypotheses hold.
If a domain skill in this session carries a theorem reference sheet, check the
statement against it rather than against memory — memory reconstructs hypotheses
plausibly and wrongly.

## Reporting: say what you actually have

Finish every piece of mathematical work with an explicit status. Use whichever of
these is true — and if it is one of the last three, say so in the first sentence,
not buried at the end:

1. **Proved.** Complete argument, every step justified, citations verified.
2. **Proved modulo stated inputs.** The argument is complete given Lemma X /
   the cited result Y, which is used as a black box. Name the inputs.
3. **Reduced.** Not proved, but reduced to a cleaner or more tractable statement.
   Say precisely what remains.
4. **Partial.** Proved under extra hypotheses, or in special cases. Say which,
   and say what breaks in general — the obstruction is often the most useful
   thing you produce.
5. **Disproved.** With an explicit, verified counterexample, plus a proposed
   repair of the statement.
6. **Not settled.** You could not do it. Say what you tried, where it broke, what
   class any failed search covered, and what you think the real obstruction is.
   This is a legitimate outcome and far better than a fabricated proof — but only
   after the effort budget above has actually been spent. "Not settled" reported
   without a described counterexample attempt is a weaker answer than it looks.

Mark the seams inside a written argument too. `\begin{remark}` or a bracketed
"[gap: this step needs the surface to be primitive — not yet checked]" costs
nothing and is exactly what a coauthor needs to see. When drafting into a real
manuscript, prefer a visible marker (a `\gap{...}` macro, a `TODO`) over silent
smoothing, so nothing unproved can escape into a submitted version.

## Working with a coauthor's draft

When repairing or rewriting someone's mathematics, separate three distinct
operations and tell them which you did:

- **Transcription** — same argument, better prose. Safe.
- **Repair** — the argument had a gap and you changed the mathematics to fix it.
  This must be flagged prominently; they need to check it.
- **Replacement** — you proved it a different way. Say so, and say why, since they
  may have had a reason for the original route.

If a step in their draft looks wrong, the useful response is not to quietly fix it
and not to declare it wrong: it is to state precisely what you cannot verify and
what would make it go through. Often they know something you do not. Assume the
mathematician is competent and that an apparent error is more likely a compression
than a mistake — but do not let that assumption stop you from flagging it.
