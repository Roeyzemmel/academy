---
name: explore
description: 'Work one research direction forward, at most three unsettled items per run: falsify, prior art, prove (probes to the Scientist, arguments to prover). Use for "/researcher:explore <direction>", "what should we try next on X", question tickets.'
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
`args: {direction: "DIR-n", items: [...], ticket: "T-NNNN", home: "<this home>", instance: "<this instance>"}`.
The inbox runs it for a `question` ticket. The order is code (2026-10-31; docs/workflows.md):
1. the clerk reads the direction. A missing one is created and filled by `lead-researcher`
   first, and no item is worked in that run;
2. the clerk picks the next items with `notebook.py next`;
3. one `lead-researcher`, briefed with ids only, moves each item one step:
   - **falsify**: its smallest falsifier, an `experiment` ticket to the Scientist that the
     lead files as the liaison. One named example is a `probe`; a family, a range or a
     bound is a search. The ticket carries the claim id, what would refute it, a
     validation case and the unsettled inputs;
   - **prior art**: the prover's scout pass, and `lookup` or `cite` tickets to the Expert;
   - **prove**: only an item that survived falsification;
4. the script checks:
   - a falsify step names an experiment ticket to the Scientist naming the item;
   - a prove step has a falsifier on record;
   - one step per item;
   - today's journal records the run.

**Report** the lead's `report` (not a summary of it), each item's step and tickets, every
`anomalies` entry, and the next picks.

**Reading a returned result.** An undecided search (a cap hit) is not a counterexample. A
candidate counterexample from a probe is a lead, not a finding: it has no provenance and no
review until it is run as an experiment and settled (`/researcher:settle`). A probe that
disagrees with a queued run is a reason to suspect both.
