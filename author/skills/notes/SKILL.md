---
name: notes
description: 'File the human''s new margin notes as tickets on their agenda entry (to the Author, or to the role owning the work), and referee-packet points. Use when the human left notes in the PDF, after an Overleaf sync, or when a referee packet returns.'
---

# /author:notes

The human's and the coauthors' new margin notes, or a returned referee packet's points,
become tickets. `$ARGUMENTS` may name a base commit, or `referee P-NNNN`. Run from the
Author home.

**Run** the Workflow tool with `scriptPath: ${CLAUDE_PLUGIN_ROOT}/workflows/notes.js` and
`args: {home: "<this home>", instance: "<this instance>", root: "<the absolute path of ${CLAUDE_PLUGIN_ROOT}/..>", base: "<commit>", referee: "P-NNNN"}`.
The inbox runs it for a returned referee ticket. The order is code (2026-10-31;
docs/workflows.md):
1. the clerk collects the new notes and the full inventory from git: `git diff -U0` (or
   against the base) and `git grep` per note macro (`author.noteMacros`, workspace.json
   `human.noteMacro`), each with its whole brace group and the statement it sits on;
2. one agent sorts each note, and files nothing yet:
   - **covered**: an active ticket carries it; a weaker ticket gets the new words;
   - **answers** a machine note: the answered question is recorded in that ticket's
     thread, so the sweep can delete the note;
   - **discrepancy**: an announced but unmade change ("I removed ...") is reported and
     never reconciled silently;
   - **new**: a proposed ticket;
3. the check: every proposed ticket passes `routes.check_filed` and the kind rules.
   - A note asking for a proof is `research` to the Expert with `final_to: researcher`
     (an experiment: `final_to: scientist`), never `write`: the Author invents no
     argument.
   - Self kinds go to this instance.
   - A judgement point, or a decision only the human makes, is filed to this instance
     and parked on `human`.

   A failing proposal goes back once, then is reported unfiled;
4. the same agent files exactly the checked tickets (`board.py new --as <instance>`), adds
   the "covered" and "answers" lines, and makes the park moves. The clerk reads every
   filed ticket back.

**Report** the four lists from the result: Found, Filed, Already covered (`covered`),
Discrepancies. Then the inventory count, the notes no ticket carries (`not_carried`,
`unfiled`), and every `anomalies` entry. Filing starts no work: `/author:inbox` takes the
tickets in agenda order. Never ask questions.
