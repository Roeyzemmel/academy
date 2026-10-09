---
name: experiment-method
description: 'Discipline for computational experiments in mathematics: numerics refute and suggest, never prove; state the refutation first, validate on known cases, prefer exact arithmetic, keep provenance. Use whenever a claim is tested numerically or a result is quoted.'
---

# Experiment method

Numerics in research mathematics earn their keep by killing false conjectures cheaply
and by revealing what the correct statement should be. **They never prove anything.**
Keep that boundary visible in everything reported: an experiment produces "no
counterexample found below bound 40 over these 6 objects", never "true".

The subject's own material lives in the active domain pack, read by file name through
`domain_get` (the lab's domain comes from `lab.py home` or `config_get`):
`examples.md` for the standard examples and their known values, `traps.md` for the
subject's failure modes, `computation/README.md` and `computation/api/` for the
libraries, how their environment is activated, and the calls already confirmed.

## The seven steps

1. **Say what would refute the claim** before computing anything. An experiment with
   no refuting outcome is not an experiment. Then ask: *if the claim were false, what
   would this experiment still report?* If the answer is "the same thing", it checks
   a shadow of the claim.
2. **Validate the setup on something you know.** The standard examples of the pack's
   `examples.md`, a value from the literature with its source, a hand computation.
   If the pipeline gets the simplest example wrong, nothing downstream means
   anything. For a search, a known example *and* a known non-example: a bug in the
   property shows up as a false positive.
3. **Prefer exact arithmetic.** Exact rationals, number fields, exact reals. Floating
   point turns "these two points coincide" into a threshold choice, and the answer
   then depends on the threshold.
4. **Watch the invariants that silently change.** A construction step (marking a
   point, passing to a cover, normalising, relabelling) can change the object's
   invariants and so the question. Print the relevant invariants at every stage; the
   pack's `traps.md` names the ones this subject hides.
5. **Report the bound and the class searched.** "No example below bound B, over these
   objects, searching only X" is a usable research statement; "it doesn't happen" is
   not. Naming the class is what lets a reader notice that the search space
   **structurally could not have contained** the counterexample, the most common way
   an exhaustive-looking computation means nothing. Every constraint carries its
   reason: feasibility (the first thing to relax), setting (part of the question),
   or excludes (known to rule out part of the phenomenon, and why).
6. **Don't let the computation replace the argument.** Before building validation
   layers around a numerical result, check whether a short proof settles it.
   Reaching for exhaustive search where a clean argument exists is the characteristic
   waste.
7. **Save the script, with provenance.** Referees and coauthors ask how a computation
   was done; a rerunnable file with its commit, versions, arguments and seed is the
   answer. Script and result are committed together.

**When an experiment produces something surprising, suspect the code first**: an
invariant that changed under a construction, a squared-versus-linear bound, a factor
of two, an off-by-one index base. Debug (`superpowers:systematic-debugging`) before
believing a new theorem.

## The kinds, and what each can establish

| Kind | Asks | Strong outcome | Weak outcome |
|---|---|---|---|
| `search` | is there an example of a phenomenon (a falsifier: "violates claim C") | **found**, with a certificate that rechecks without the search | "not found under these constraints" only |
| `measure` | what is this quantity over a class | the values, with the class and what it excludes | — |
| `verify` | does one named object have a property | holds / fails, by two independent routes if it will be cited | one route: evidence, not a check |
| `probe` | is it computable, how large does it get | a recommendation; feasibility, **not evidence** | — |

A computation reaches `supported`, `refuted` or `refuted-as-stated` in the registry,
after two agreeing experiment reviews; never `proved` (`academy:status-vocabulary`).
An exact, independently rechecked certificate of an existence claim is the one case
where a proof may follow, and that proof goes through proof review, not here.

## Negative results, unverified inputs, and ranking candidates

- **A negative is worth exactly the completeness of its enumeration.** "No element of
  the class has property P" is only as good as the certificate that the class was
  enumerated in full (every member, every value the definition ranges over). A record
  whose enumeration is incomplete is *undecided*, never a counterexample and never
  evidence for the claim. A refutation should also carry a **hand-checkable
  certificate**: the failed necessary condition stated on a single, named object.
- **Flag what this lab has not verified.** A statement taken from the literature or a
  note without a check here may shape a search and may serve as a validation case; it
  may never be the reason a counterexample is believed, and anything resting on it
  inherits the flag.
- **Rank candidates on separate axes, report the Pareto front, never a scalar.** When a
  search ranks members for follow-up (for example "how likely to fail" against "how
  strong a hypothesis it satisfies"), keep each axis on its own ordering, report the
  non-dominated members **together with the full table**, and leave the choice between
  front members to the human or the lead researcher. A weighted sum hides the trade-off
  it decided.
- **One finding per surface is not a trap test.** A library quirk (silent relabelling,
  a doubled area, a changed index base) that does not show on one example may show on
  the next; validate a workaround on two examples that differ in the relevant way.

## Also

- **The home's rules win.** A lab may forbid running experiments locally at all
  (`policy.run` names a remote profile). Read the lab's `CLAUDE.md` before choosing
  where to run.
- **Use the recipe files, not memory**, for library calls: the APIs change and
  plausible calls from older tutorials silently do not exist. An unconfirmed call
  goes through `/scientist:api-check` before it enters a script.
- A check on code (does the package compute what it should) is a **test**, not an
  experiment, even when it is slow.
