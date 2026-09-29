---
name: verify
description: 'Review one registry statement''s proof with two independent blind rigor-reviewer runs (B only if A is CONFIRMED), adjudicated by script, with a verification packet; the sanctioned route from sketch to proved. Use for every verify ticket and "verify lemma X".'
---

# Verify one statement

## Scope notes

- This is the sanctioned route from `sketch` to `proved`; use it before any recolouring.

`$ARGUMENTS` is a claim id (`paper:lem:strip-bound`), optionally a ticket id
(`T-NNNN`) and the question asked; or empty, meaning the first `verify` ticket that
`py ${CLAUDE_PLUGIN_ROOT}/scripts/inbox.py` lists. **One statement per invocation**:
this is the most expensive pass in the academy, and Roey decides how much of it to
spend. Say which statement you took and why before dispatching.

Budget and independence: `academy/references/budget.md` and
`academy/references/roster-rules.md` (the base plugin's `references/`). Run it from
the library home (the Expert instance's home), so the MCP tools act for the Expert
instance.

A single adversarial read is not a sign-off: repeated runs of the same proof check
disagree in the tens of percent. So the check runs **twice, independently, in
sequence**, and disagreement is itself a finding.

## 1. Dispatch one review-chair

Dispatch **one** `review-chair` (`subagent_type: expert:review-chair`) with the claim
id, the ticket id if any, and the question. It hashes the statement, launches the
blind `rigor-reviewer` runs, runs `decision_table.py`, writes the record, attaches the
evidence, proposes the status and files the packet, following
`references/conclude.md`. **Do not launch `rigor-reviewer` yourself** — the pair and
its concluder belong in one agent. Pass no `model` override.

**By hand**, only if `review-chair` cannot be launched: follow
`references/conclude.md` in this seat, launching the runs yourself, and say in the
report that the pass ran by hand. This seat files as the agent `main`, and
`main` is not a liaison for expert->author or expert->researcher: the follow-up repair
tickets of `conclude.md` are not filed from here. Leave them to a `review-chair` run once one
can be launched, or list each (receiver, claim, ask) in the report for Roey. The
status proposal (`claims_propose_status`) is exempt and still goes out.

## 2. The decision table

`scripts/decision_table.py` is the table; its docstring states it and
`tests/test_decision_table.py` pins every row. In short: CONFIRMED x2 → propose
`proved` (recolour earned); CONFIRMED modulo X x2 → propose `proved-modulo`, recolour
only when every input is established; CONFIRMED vs GAP, or different inputs →
disagreement; any DISPROVED → the counterexample to Roey, no status; a GAP run A →
single negative, B skipped by design; any PLAUSIBLE → degraded, never counts. A
CONFIRMED counts on Fable or Opus 5.5 (equal primaries); on any other model it reads
as PLAUSIBLE.

## 3. After the chair returns

- **A recolouring** is the Author's edit, never the Expert's: the ticket result says
  "recolour earned" and the sending Author instance's `math-editor` makes it when its
  next run closes the ticket.
- **A counterexample** (DISPROVED) goes to Roey at once: relay it in full.
- The status itself moves only when the claim-keeper accepts the proposal ticket the
  chair filed (`claims_propose_status`).

## 4. Report

Relay the chair's report, not a summary: both verdicts in the reviewers' own words,
side by side; the outcome and the input-by-input status; the **blast radius** first
when there is one; the record path, the evidence rows, the proposal ticket and the
packet id. Never ask questions; Roey decides in `/academy:review`.
