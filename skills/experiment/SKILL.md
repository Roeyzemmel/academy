---
name: experiment
description: Take a mathematical claim from words to a queued, provenance-stamped experiment in FlatSurfLab — classify the work (two-line argument / probe / experiment), write and get the header approved before any compute, scaffold from _template.py, wire a validation case that must reproduce something known, record the lab claim, then file the run on the lingo queue. Use whenever a claim is about to be tested numerically, on "let's check this", "can we test", "find a counterexample to", or before writing any new script under FlatSurfLab's experiments/.
---

# An experiment, from a claim to a queued run

`$ARGUMENTS` is the claim, in the author's words. It is not yet an experiment.

Read `.claude/flatsurf.json` first. Its `lab` is FlatSurfLab; every path and command
below is relative to it (`cd <lab>;` first when the session is elsewhere). A repo may
have its own entry point for a kind of experiment — Slope1's `/hunt` for origami
families — and that one wins for its kind.

## The gate

**No compute before the header is written and approved.**

The header is the whole discipline compressed into a dozen lines. Written first, it
forces the question "what would show this is false?" while the answer can still change
the design. Written afterwards, it is a description of whatever the code happened to
do, and it will match the code no matter what the code got wrong.

This is the one rule here with no exception. "It is a two-line check" is the
rationalization that produces a script nobody can interpret a week later. The header is
also the spec: no separate brainstorming spec or plan is written for an experiment.

## Step 0 — classify, and say which path you took

| Path | When | Ends in |
|---|---|---|
| **Two-line argument** | the claim is settled by an argument cheaper than the code | a written argument, no script. Check for one before any big search |
| **Probe** | "is this even computable / how big does it get" — feasibility, not evidence | a throwaway in `scratch/`, a recommendation, no result JSON. Name the probe's question and what its answer decides *before* writing it |
| **Experiment** | a claim that could be refuted by a search, measured, or verified | the full path below |

Say which one you picked and why, in one sentence. If it is the two-line argument,
stop and give the argument — that is a result, and a better one.

## Step 1 — read before designing

- `translation-surfaces` for the statement's real hypotheses. A claim tested under
  the wrong hypotheses refutes nothing.
- `flatsurf-computation` for the API. The calls changed recently; plausible ones
  from old tutorials do not exist. Anything uncertain goes through
  `/flatsurf:api-check` *now*, not inside the experiment.
- The nearest existing script in `experiments/`, and `fslab/` (grep before writing a
  helper; never copy fslab code into a script). Most of the work is usually done.
- The claim registry: `<registry.cmd> show <id>` for what is already known.

## Step 2 — pick the kind, draft the header, and stop

The field lists and rules for each kind are in `experiments/README.md`:

| Kind | When | The strong outcome |
|---|---|---|
| `search` | looking for an example of a phenomenon, including a counterexample to a claim | **found**, with a certificate; "not found" holds only under the constraints |
| `measure` | computing a quantity over a class | the values, with the class stated |
| `verify` | deciding whether one named object has a property | holds / fails, by two routes if it will be cited |

A check on code is a test in `tests/`, not an experiment.

Draft the header and show it to the author before writing a line of the body. The
fields that fail most often:

- **Constraints** (search). Every one carries `[feasibility]`, `[setting]` or
  `[excludes …]`. A feasibility constraint that silently excludes the phenomenon makes
  "not found" meaningless. Ask which constraint the next run would relax.
- **Properties** (search, verify). `required:` decides "found"; `recorded:` makes a
  found example useful afterwards (stratum, hypothesis level, …).
- **Certificate** (search). What lets a "found" be rechecked without trusting the
  search code.
- **Validation.** A case whose answer is known independently (`knownCases` in
  `.claude/flatsurf.json`, the literature, a hand computation, `tests/`). For a search,
  a known example *and* a known non-example, because a bug in P shows up as false
  positives.
- **Claims.** Registry ids. Create the `lab:` claim now — `py scripts\claims.py new
  lab:<name> --title "..." --where experiments/<script>.py` — with `bears_on:` the
  `paper:` label or `s1:` id it is evidence for. The claim's `open:` list is where next
  steps live; the header is frozen once `Result:` is filled.

Then ask the one question that decides whether the design is honest:

> If the claim were false, what would this experiment still report?

If the answer is "the same thing", the design checks a shadow of the claim. Redesign
before scaffolding.

## Step 3 — scaffold

Copy `experiments\_template.py` to `experiments\YYYY-MM-DD_<slug>.py` (today's date,
lowercase slug) and fill the agreed header. Then:

- Exact arithmetic — `Fraction`, number fields, exact reals.
- Print the stratum at every stage.
- `validate()` raises on failure; nothing below it is trusted otherwise.
- `env.banner(__file__)` first, `env.save_result(..., claims=[...])` last.
- Prefer `fslab` and sage-flatsurf. A pure-Python path needs a measured runtime
  difference, stated in the header.
- Any `fslab/` code the script needs is written test-first (in FlatSurfLab,
  `superpowers:test-driven-development`); the script itself is checked by its
  validation case on lingo, not by a unit test.

Check it mechanically (a hook also runs this after each edit in FlatSurfLab):

```
py scripts\check_experiments.py experiments\YYYY-MM-DD_<slug>.py --strict
```

Review against `references/sage-review.md` in this plugin before committing.

## Step 4 — commit, then queue

**Experiments never run on the laptop** — not the real run, not the validation case.
The queue runs HEAD on lingo, so the script is committed first; that is also what keeps
`save_result`'s commit hash honest. **Roey commits** experiment scripts that go to the
queue: stop here with the script ready and say so, unless he has said to commit.

```
scripts\queue.ps1 -Add experiments\YYYY-MM-DD_<slug>.py -Label lab:<name> -Note "..." -ScriptArgs "--bound 40"
```

Arguments go through `-ScriptArgs`; the bare `-- --bound 40` form loses tokens under
PowerShell 5.1. Then hand over to `/flatsurf:queue`.

## Step 5 — when the result comes back

Fill the `Result` field, in the repo's wording:

> no counterexample below bound *B* over class *C*

never "true", never "confirms". Name what the search class **structurally could not
have contained**.

Then run the repo's settle pass (`settle` in `.claude/flatsurf.json`; by default
`/flatsurf:verify-result`) before it is cited anywhere. **A surprising result is a bug
until shown otherwise** — stratum mismatch, squared-versus-linear bound, libflatsurf's
doubled cylinder area — debug it (`superpowers:systematic-debugging` where enabled)
before believing a new theorem.

The status change on the lab claim goes through `flatsurf:claim-keeper`, on the audit's
grounds. Script and result JSON are committed together; the commit gate enforces it.
