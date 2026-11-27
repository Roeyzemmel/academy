---
name: verify
description: 'Review one registry statement''s proof with two independent blind rigor-reviewer runs (B only if A is CONFIRMED), adjudicated by script, with a verification packet; the route from sketch to proved. Use for every verify ticket and "verify lemma X".'
---

# Verify one statement

`$ARGUMENTS` is a claim id (`paper:lem:strip-bound`), optionally a ticket id (`T-NNNN`)
and the question; or empty, meaning the first `verify` ticket that
`py ${CLAUDE_PLUGIN_ROOT}/scripts/inbox.py` lists. **One statement per invocation**: this
is the most expensive pass in the academy. Say which statement you took and why. Run it
from the library home (the Expert instance's home), so the MCP tools act for the Expert.
This is the sanctioned route from `sketch` to `proved`, and it comes before any recolouring.

## 1. Run the workflow

The sequencing is code, not prose (the human's decision, 2026-10-31): call the **Workflow**
tool with

    scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/verify.js
    args: {models: <the JSON object that py "${CLAUDE_PLUGIN_ROOT}/../academy/scripts/models.py" launches prints>, root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>", claim: "<ns:id>", ticket: "T-NNNN" or omitted, question: "<if not 'may it be raised to proved?'>",
           mode: "blind" | "reword", base_pass: "<reword only>", base_subject: "<renamed label only>"}

The script runs the blind `rigor-reviewer` run A, launches B at once (A's brief byte for
byte, `run: B`) only when `decision_table.py` says `launch_b` and the statement hash has not
moved (a counterexample already on record stops it), relaunches a run that did not land
once, stops on a lost run. A falsifier is triggered by a failure, never a gate between A
and B (the human's design, 2026-11-20): when A, or B after a CONFIRMED A, says GAP and the
claim has no clean falsifier on record for this statement hash and none pending, a chair
stage files the falsifier request, naming the blocking step, alongside the follow-up repair
(`references/conclude.md` section 1a); it blocks nothing. The script then hands the landed
runs to a `review-chair` stage that writes the record, the evidence, the proposal, the
follow-up tickets and the packet (`references/conclude.md`). The `land_verdict` hook files
each verdict; a hand-launched `rigor-reviewer` is refused by the `review_launch_guard` hook.
Pass no `model` override.

**Reword mode** (`mode: "reword"`, T-0347): the statement's text changed after a pass that
decided `confirmed` / `confirmed-modulo`, and the proof is unchanged or changed only in
wording. One informed run R replaces the blind pair. The base is the last confirmed pass,
blind or reword (#127: a reword on a reword compares the wording the earlier reword
confirmed; the chain ends in a CONFIRMED x2 blind pass). Find it with
`py ${CLAUDE_PLUGIN_ROOT}/scripts/reviews.py list <id>`; for a renamed label, give the old
id as `base_subject` (T-0476). A verify ticket titled `Verify <claim> (reword of <pass>)`
(the one `/researcher:prove` files when a repair reworded a reviewed statement, #85) is run
in reword mode with that `base_pass`; the inbox does this from the title. The same title is
filed by `registry.py stale --file-reword` (#109): one ticket per proved / proved-modulo claim
whose statement hash moved off its last positive pass, which `registry.py check` flags and the
views show as `proved (stale)` until the reword pass lands. A rewording that answers a hypothesis, statement or proof
finding, or a changed proof, takes the blind pass.

**By hand**, only when the Workflow tool cannot run: the human sets
`ACADEMY_ALLOW_MANUAL_REVIEW=1`, and this seat follows `references/conclude.md` section 1
itself, launching the runs. It files as `main`, and `main` is not a liaison for
expert->author / expert->researcher, so it lists the follow-up tickets (receiver, claim,
ask) in its report instead of filing them; `claims_propose_status` still goes out. The
report says the pass ran by hand.

## 2. After the workflow returns

- **`falsifier_request`** (in the result): the request a GAP verdict filed (a `research`
  ticket to the Researcher with `final_to: scientist`, naming the gap), or null when a
  falsifier was on record or pending, no Researcher could be named (a note says so), or the
  verdict was no GAP. Nothing waits for it: the pass concluded and the ticket was delivered
  as without it. Name it in your report.
- **`awaiting-amendment`**: A was CONFIRMED and suggested a dependency (`add_dependency`,
  an existing result the proof relies on but does not list; `references/conclude.md`
  section 1b). The chair filed a `prove` repair to the producer (marked `amendment for
  verify <T> pass <pass>`, so it files no verify ticket of its own) and blocked the verify
  ticket on it; the pass stays open. On the rerun B runs in **amend mode** on the amended
  proof, told the suggestion only, and A + B are the two verdicts (proved-modulo the added
  dependencies until established) — but only once that repair ended delivered or closed,
  the attempt is not the one A reviewed, and each dependency is declared with its pinpoint.
- **`new-pass-after-amendment`** (in the table): a blind B, not A, suggested a dependency.
  No status; the dependency goes to the producer as a repair, and a new pass follows it.
- **`falsifier-counterexample`**: a falsifier on record broke the claim. No B, no status; the
  counterexample went to the human as a `decision` ticket (the one rule for a
  counterexample, `references/conclude.md` section 4.3) and is in the packet.

- `notes` and `anomalies` go into your report verbatim (a skipped B, a relaunch, a lost
  run, a run file the workflow did not launch).
- **A recolouring** is the Author's edit: the ticket result says "recolour earned" and the
  Author's `math-editor` makes it.
- **A counterexample** (DISPROVED) goes to the human at once, in full.
- The status moves only when the claim-keeper accepts the proposal ticket.
- `ship`: the pass's checkpoint (`inbox.py --check` of its ticket, run once; without a
  ticket `not-run` with the command). Report a refusal; never retry it.

## 3. Report

Relay the chair's `report`: both verdicts in the reviewers' own words, side by side; the
outcome and the input-by-input status; the **blast radius** first when there is one; the
record path, evidence rows, proposal ticket and packet id. Never ask questions; the human
decides in `/academy:review`. The decision table itself is `scripts/decision_table.py`
(its docstring is the table; `tests/test_decision_table.py` pins every row).
