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

The script runs the blind `rigor-reviewer` run A, then holds the claim's falsifier
(the order is attempt, A, falsifier, B: the human's design, 2026-11-20), launches B (A's
brief byte for byte, `run: B`) only when `decision_table.py` says `launch_b`, the statement
hash has not moved and the falsifier on record found nothing, relaunches a run that did
not land once, stops on a lost run, and hands the landed
runs to a `review-chair` stage that writes the record, the evidence, the proposal, the
follow-up tickets and the packet (`references/conclude.md`). The `land_verdict` hook files
each verdict; a hand-launched `rigor-reviewer` is refused by the `review_launch_guard` hook.
Pass no `model` override.

**Reword mode** (`mode: "reword"`, T-0347): the statement's text changed after a pass that
decided `confirmed` / `confirmed-modulo`, and the proof is unchanged or changed only in
wording. One informed run R replaces the blind pair. Find the base with
`py ${CLAUDE_PLUGIN_ROOT}/scripts/reviews.py list <id>`; for a renamed label, give the old
id as `base_subject` (T-0476). A rewording that answers a hypothesis, statement or proof
finding, or a changed proof, takes the blind pass.

**By hand**, only when the Workflow tool cannot run: the human sets
`ACADEMY_ALLOW_MANUAL_REVIEW=1`, and this seat follows `references/conclude.md` section 1
itself, launching the runs. It files as `main`, and `main` is not a liaison for
expert->author / expert->researcher, so it lists the follow-up tickets (receiver, claim,
ask) in its report instead of filing them; `claims_propose_status` still goes out. The
report says the pass ran by hand.

## 2. After the workflow returns

- **`awaiting-falsifier`**: A was CONFIRMED and the claim had no falsifier on record
  (`references/conclude.md` section 1a). The chair filed the falsifier request
  (`falsifier_request`, a `research` ticket to the Researcher with `final_to: scientist`)
  and blocked the verify ticket on it; the pass stays open. Once the request is back,
  the Expert's inbox releases the ticket (`inbox.py`, a `released` row) and runs this skill
  on it again (a rejected or cancelled request releases it to the human instead): the pass resumes (A is tabled, not
  relaunched) and B launches only if the falsifier found nothing. A pass with no ticket
  never waits: it could not be resumed (`reviews.py` resumes a ticket's own pass only),
  so the falsifier stage is skipped with a note in the record and B runs as before.
- **`falsifier-counterexample`**: the falsifier broke the claim. No B, no status; the
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
