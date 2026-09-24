---
name: claims
description: Answer "what is known about X" from the claim registry instead of from prose — show a claim with its evidence and back-links, list by status, grep, query, create a claim, link an experiment to it, and route status changes through claim-keeper. Covers the federated registries (lab: in FlatSurfLab, paper: in BilliardIllumination, s1: in Slope1's kb). Use whenever the status of a statement, lemma, conjecture or computation is asked, before citing a result, and when an experiment needs a claim id.
---

# The claim registry

`$ARGUMENTS` is an id (`lab:<name>`, `paper:<label>`, `s1:<id>`), a text to search, or
what to do.

Read `.claude/flatsurf.json`: `registry.cmd` runs the tool from this repo,
`registry.setStatus` says who changes a status. The format, the status vocabulary and
the rules are FlatSurfLab's `docs/claims.md`; read the section you need, not the whole.

**Do not reconstruct a status from prose** — the roadmap, a header, a chat log, a
ledger. If the registry is missing something, fix the registry.

## Reading

```
<cmd> show <id>                  the claim, and who cites it (claims, experiments, results)
<cmd> list --status refuted      also: --ns lab|paper, --where <path>
<cmd> grep "torus cover"
<cmd> sql "select id, status from claims where ns = 'paper' and status = 'sketch'"
<cmd> check                      links across all three registries
```

`show` on an id owned by another repo prints it from there (`lab:` and `paper:`) or says
where to look (`s1:` → `py tools/kb.py show <id>` in Slope1). In Slope1 itself the tool
is `kb.py`: `show`, `find`, `deps`, `usedby`, `resolve <old label>`.

Status words that are easy to misread: `supported` is a bounded computation that found
no counterexample — **not a proof**. `sketch` is an argument never verified. `proved`
for a `paper:` claim means black in the draft; `check` warns when no verdict or citation
backs it.

## Writing

- **A new claim** (no status change): `<cmd> new lab:<name> --title "..." --where
  experiments/<script>.py`, then fill `bears_on:` (the `paper:` label or `s1:` id it is
  evidence for). The experiment header's `Claims:` line and `save_result(claims=[...])`
  name the same id; the queue job's `-Label` too.
- **A status change** goes through `flatsurf:claim-keeper` (in Slope1, `kb.py
  set-status` through its `status-keeper`), with its grounds: a cleared result, a double
  verifier sign-off, or Roey's word. Anything less stays `open`, with the reason under
  `open:`.
- **Nothing is deleted.** A false claim becomes `refuted`; a repaired statement keeps its
  refutation as a history line.
- After any edit: `<cmd> check` (a hook runs it on claim files) and `<cmd> render`; in
  BilliardIllumination also `<cmd> ledger`, which regenerates `Drafts/experiments.md`.
