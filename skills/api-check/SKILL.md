---
name: api-check
description: Confirm that a sage-flatsurf / surface_dynamics / libgap call actually exists and behaves as assumed, by running it in WSL Sage against a case with a known answer before it goes into an experiment — then record the confirmed signature, or the refutation, in the flatsurf-computation skill's api-recipes.md so the trap list grows. Use before writing any unfamiliar call, before a script with an unfamiliar call is queued, when a tutorial or memory suggests a method, and whenever a traceback says an attribute does not exist.
---

# Check the call before it goes in the script

`$ARGUMENTS` is the call in question, a list of calls, or the thing you want to do
("get the Veech group generators of this origami").

The libraries here changed a lot recently. A call that reads plausibly, that appears
in a 2019 tutorial, that a model remembers confidently, may simply not exist —
`surface.cylinder_decomposition`, `SaddleConnection.start()`,
`veech_group().gens()`. Each of those cost a debugging session before it was written
down.

**A call that has not been run in this session, and is not in `api-recipes.md`, is a
guess.** A guess inside a queued experiment fails an hour later, on lingo, in a log —
after the VPN window has closed. The cost of checking now is a minute.

## Dispatch

Read `.claude/flatsurf.json`: `lab` is FlatSurfLab, where every probe runs, and
`knownCases` lists this repo's cases with independently known answers.

Look the call up in `~/.claude/skills/flatsurf-computation/references/api-recipes.md`
first; a confirmed entry at the installed versions ends the question.

Otherwise dispatch one `flatsurf:api-prober` agent **per call**, all in one message so
they run concurrently. Each gets exactly one question. The agent answers by running
the call, never by recalling it, and records the outcome in `api-recipes.md`. For a
single one-line check you may run it yourself, in the same order:

```
cd <lab>; scripts\run.ps1 -Code "from flatsurf import translation_surfaces; S = translation_surfaces.veech_double_n_gon(5); print([m for m in dir(S) if 'cylinder' in m])"
cd <lab>; scripts\run.ps1 scratch\probe_<thing>.py
```

Probes go in FlatSurfLab's `scratch/`, never the system temp directory: `run.ps1`
refuses any path outside the repo. Never queue anything and never run an experiment
from this pass.

## The order of each check

Existence, then signature, then return type, then **a case whose answer is known
independently**, then labels, indices and factors. The fourth step separates "the call
ran" from "the call does what was assumed". `agents/api-prober.md` has the detail and
the silent traps to pin; FlatSurfLab's `docs/api-traps.md` has the ones this project hit.

Anything the lingo pipeline depends on structurally — above all that `surface_dynamics`
and `libgap` import without `pyflatsurf` — is confirmed on lingo too
(`scripts\run.ps1 -Target ssh:lingo -Code "..."`, needs the VPN).

## Then write it down

The point of the check is that it happens once. In `api-recipes.md`, in the shape of the
existing entries:

- **Confirmed** — the call, the exact signature, the versions (sage-flatsurf 0.8.0,
  surface_dynamics 0.7.0), and the known case it reproduced. A recipe with no worked
  case is a signature, not a recipe.
- **Refuted** — the call that does not exist, what was tried instead, and, if the
  mistake reads as correct, a line for the pitfall list.

If the check changes something in FlatSurfLab's `docs/api-traps.md` or the five-trap list
in its `CLAUDE.md`, say so; a stale entry there is worse than none.

## When the check fails

A missing attribute is an answer, not a bug. Do not wrap the call in `try`/`except` and
carry on: find what the library does offer (`GL2ROrbitClosure(S).decomposition(v)` for
the cylinder decomposition, `surface_dynamics` origamis for Veech groups,
`fslab.sd_extras` for anything the relabelling breaks), confirm *that*, and record both.

## Report

Per call: the question, the verdict (confirmed or refuted), the signature or the
traceback **verbatim**, the known case and the value it gave, what was written to
`api-recipes.md`, and anything left unsettled. Quote the output; do not paraphrase it.
