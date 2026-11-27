---
name: explore
description: 'Work one research direction forward, at most three unsettled items per run: prior art, prove (handed back), falsify only after a failed attempt or GAP. Use for "/researcher:explore <direction>", "what should we try next on X", question tickets.'
---

# Explore a direction

`$ARGUMENTS` is a direction id (an object under `objects/direction/`), optionally with the
items to take. A `question` ticket counts as a one-item run. Run from the Researcher home.
Budget: at most `budget.itemsPerRun` items (never more than 3), serially; nothing starts
itself. Under `/researcher:campaign` a direction may belong to an approach; `next` gives
nothing for a blocked, dropped or delivered one.

The main session briefs and relays. It writes no mathematics, no code and no experiment
script, and decides no truth.

**Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/explore.js` and
`args: {models: <the JSON object that py "${CLAUDE_PLUGIN_ROOT}/../academy/scripts/models.py" launches prints>, direction: "DIR-n", items: [...], ticket: "T-NNNN", home: "<this home>", instance: "<this instance>", root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>"}`.
The inbox runs it for a `question` ticket. The order is code (2026-10-31; docs/workflows.md):
1. the clerk reads the direction. A missing one is created and filled by `lead-researcher`
   first, and no item is worked in that run;
2. the clerk picks the next items with `notebook.py next`;
3. one `lead-researcher`, briefed with ids only, moves each item one step, in the order of
   `/researcher:prove` (the human's ruling of 2026-11-20, academy#87):
   - **prior art** first: the prover's scout pass, and `lookup` or `cite` tickets to the Expert;
   - **prove**: an item with no proof attempt (or one to repair). The attempt does not wait
     for a falsifier. The lead cannot launch `prover` inside the run (T-1271): it makes sure
     the item is a registry claim (a question naming none: `claims_new`), writes the prover
     brief in today's journal, and returns the claim; the workflow hands it back;
   - **falsify** only after an attempt: an item whose attempt failed or came back
     incomplete, or whose proof got a GAP verdict, with no falsifier on record or pending,
     gets its smallest falsifier, an `experiment` ticket to the Scientist that the lead files
     as the liaison (one named example is a `probe`; a family, a range or a bound is a
     search; the ticket carries the claim id, what would refute it, a validation case and
     the unsettled inputs). Never before an attempt;
4. the script checks:
   - a falsify step names the attempt or verify ticket behind it, which a clerk reads (a
     failed or incomplete attempt, or a GAP verdict; otherwise it is an anomaly and counts
     for nothing), and its experiment ticket goes to the Scientist naming the item;
   - a prove step's claim resolves (`registry.py statement`);
   - one step per item; today's journal records the run; the artefacts the lead names exist;
5. the end:
   - **a prove step** comes back as `for_main` (`skill: researcher:prove`, `handback:
     lead-researcher`, `args`; several prove items: `runs`, the ticket on the first). Run the
     Workflow `prove.js` with `for_main.args`, then each further entry of `runs`; the ticket
     stays `in-progress` and prove.js delivers it. Without `args`, `why` says what to fix
     first (register the claim with `claims_new`);
   - **a ticket** is delivered only on an artefact (a ticket filed, a direction item or
     object made or updated, an attempt), and its result names them; with none it stays
     `in-progress` with a thread note (`outcome: no-artefact`).

**Report** the lead's `report` (not a summary of it), each item's step and tickets, the
`artefacts`, every `anomalies` entry, the next picks, what `for_main` handed back and what
its prove run did, and `ship` (a question ticket's checkpoint, run once; a
direction run ships `explore-<direction>` through `inbox.py --ship-slug`, #136; a refusal is
reported, never retried).

**Reading a returned result.** An undecided search (a cap hit) is not a counterexample. A
candidate counterexample from a probe is a lead, not a finding: it has no provenance and no
review until it is run as an experiment and settled (`/researcher:settle`). A probe that
disagrees with a queued run is a reason to suspect both.
