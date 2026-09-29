---
name: api-check
description: 'Confirm a library call the lab relies on exists and behaves as assumed, by running it on the probe profile against a known answer, and record the result in the domain pack. Use before writing or queuing any unfamiliar call.'
---

# Check the call before it goes in the script

`$ARGUMENTS` is the call in question, a list of calls, or the thing to do ("get the
generators of this group").

The libraries here change. A call that reads plausibly, that appears in an old
tutorial, that a model remembers confidently, may simply not exist. **A call that has
not been run in this session and is not in the recipe files is a guess**, and a guess
inside a queued experiment fails an hour later in a remote log. Checking now costs a
minute.

## Dispatch

1. `py "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" home` gives the domain and the probe
   profile.
2. Look the call up first: `domain_get(name=<domain>, file="computation/api/INDEX.md")`
   names the one topic file; read it. A confirmed entry at the installed versions
   ends the question.
3. Otherwise dispatch one `api-prober` **per call**, one after another (budget:
   at most three per run, serially; `${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md`).
   Each gets exactly one question, answers by running the call, and records the
   outcome in the pack. For a single one-line check you may run it yourself, in the
   same order, with the command `lab.py cmd run -Code "..."` prints.

Probes go in the lab's `scratch/`. Never queue anything and never run an experiment
from this pass.

## The order of each check

Existence, then signature, then return type, then **a case whose answer is known
independently** (the pack's `examples.md`, the lab's tests), then labels, indices and
factors. The fourth step separates "the call ran" from "the call does what was
assumed". `agents/api-prober.md` has the detail.

## Then it is written down

In the pack's `computation/api/<topic>.md`, as the next numbered entry, plus one line
in the pack's `CHANGELOG.md`: confirmed (signature, versions, the known case and its
value) or refuted (the traceback verbatim, the alternative, confirmed the same way).
If the finding contradicts the pack's `traps.md` or a home's own trap list, say so;
the prober does not edit those.

A missing attribute is an answer, not a bug: do not wrap the call in `try/except`
and carry on. Find what the library does offer, confirm that, record both. If the
library contradicts its **own documentation**, the prober files an `Upstream:` code
ticket to the lab; `/scientist:inbox` routes it to upstream-contributor, which only
drafts.

## Report

Per call: the question, the verdict, the signature or the traceback **verbatim**, the
known case and the value it gave, what was written to which file and §, any upstream
ticket, and anything left unsettled. Quote the output; do not paraphrase it.
