# Attack brief: break the statement before proving it

An attack-only pass on a statement not yet proved. Its only job is to find where the
statement fails as written. It proves nothing, because an agent asked to "check" a claim
tends to agree with it. Run it before the first proof attempt, and again on a restated
claim.

## The brief (paste the exact statement into it)

> Claim: <the exact statement, with its standing assumptions>.
> Do not try to prove this; your only job is to find where it fails.
> (a) List every hypothesis, explicit and implicit (compactness, regular point vs
> singularity, how limits and degenerate objects are treated).
> (b) For each, attempt an explicit counterexample if it is dropped.
> (c) For the claim as stated, name the three edge cases a careful proof must handle
> explicitly.
> Flag anything you are unsure of rather than smoothing it over.

## What comes back

- The hypotheses, each marked explicit or implicit.
- For each: a concrete counterexample if dropped, or "none found, tried <what>". A
  counterexample is verified explicitly, not only proposed.
- Three edge cases, each with what the proof must say about it.
- A list of what the attacker is unsure of.

A counterexample is a success (`SKILL.md` section 2): the statement is repaired (a new
hypothesis, "finitely many exceptions") as a new statement, never silently. The
attack grades nobody's work and sets no status. Findings go into the proof brief;
a computational falsifier remains `/researcher:explore`'s job.

## Example prompt (an example of the form, not a claim asserted true)

> Claim: let X be a compact translation surface and p a point of X. The set of points
> of X not illuminated from p is finite. Do not try to prove this; your only job is to
> find where it fails. (a) List every hypothesis, including implicit ones (compactness,
> p regular vs a cone point, how trajectories through singularities are treated).
> (b) For each, attempt an explicit counterexample if it is dropped: p at a
> singularity, X of infinite type, "finite" replaced by "empty". (c) Name the three edge
> cases a careful proof must handle explicitly. Flag anything you are unsure of.
