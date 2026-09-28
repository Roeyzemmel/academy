---
name: decide
description: Ask Roey about every decision the academy is waiting on — open packet decisions, tickets addressed to human, and tickets anywhere blocked on human — in plain-language batches, then record each answer. Use for "what needs my decision", "ask me", "decisions", "let's go through what's waiting on me", and when the desk or a SessionStart line reports decisions waiting.
---

# Decide

`$ARGUMENTS` is empty (every instance), an instance name, or one decision id
(`P-NNNN/Dk` or `T-NNNN`, answered alone). Scripts: `$S` as in
`${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. Only the main session runs this skill:
only the human decides (`references/roster-rules.md` rule 6), and only the main
session may call `AskUserQuestion` (`references/budget.md` rule 5).

Subagents cannot call `AskUserQuestion`, which is why this is two pieces: the
`decisions.py` script collects and records; the read-only `secretary` agent only
phrases the questions. Neither one asks Roey or records on its own.

## Procedure

1. **Batch.** `py $S/decisions.py batches --json [--instance X]` (a single id in
   `$ARGUMENTS` instead runs `list --json` and keeps only that one). If it reports no
   pending decisions, say so and stop.
2. **Phrase.** Dispatch one `secretary` subagent per batch (or all batches at once if
   there are few) with that batch's JSON in its brief. It returns the array described
   in its own file — `header` (≤12 chars), `question`, `options` (recommended first,
   marked), and `flag` for a stale or contradictory recommendation. Report a
   limit error or empty result and stop (`references/budget.md` rule 4); never
   relaunch.
3. **Ask, batch by batch.** For each phrased batch, one `AskUserQuestion` call, at
   most four questions (`decisions.py batches` already sized them so), using the
   secretary's `header`/`question`/`options` verbatim. Show any `flag` as part of the
   question text, not hidden. Roey may answer free text ("other") on any question, or
   decline to answer (skip it — nothing is recorded for a skipped question).
4. **Record before asking the next batch.** For every answered question in the batch,
   immediately:
   `py $S/decisions.py record <id> --choice <letter|proceed|decline> [--comment "<note or free text>"]`
   — a `P-NNNN` id records through `packets.py decide` (echoed into its ticket's
   thread); a `T-NNNN` id transitions the ticket as human (`accepted`/`rejected` from
   `open`, `accepted`/`cancelled` from `blocked`, with the comment as the reason for a
   decline). Do this before moving to the next batch, so an interrupted run loses
   nothing already answered.
5. **Offer the mechanical shortcut.** After a batch, if every remaining pending
   decision (`py $S/decisions.py list --json`) is `"kind": "mechanical"`, add one more
   option to the next `AskUserQuestion` call: "Accept all remaining recommendations
   (mechanical only)". On that answer, run
   `py $S/decisions.py accept-recommended --mechanical-only` (no `--dry-run`) once,
   report what it accepted, and stop asking — do not also ask the mechanical batches
   individually.
6. **Final summary.** One line per decision recorded (id, choice, and what
   `unblocks` named) and one line for anything left pending (skipped, or a
   `mechanical-only` accept that a substantive item was excluded from). Say plainly
   that nothing was started: the ticket or packet's owner picks the result up on its
   own next inbox run, not here (`references/budget.md` rule 3;
   `docs/protocol.md` section 6.3). If a math-editor, claim-keeper or other agent's
   next run should now proceed, that is a separate step Roey asks for explicitly.

## Notes

- `decisions.py accept-recommended` (used above only in the mechanical-only shortcut)
  never touches a ticket-sourced decision: a raw ticket carries no recorded
  recommendation, so it is always answered explicitly with `record`.
- A `stale` flag is a heuristic (another decided packet shares a `subject` and was
  decided later) — report it, do not resolve it yourself.
- `/academy:review` and `/academy:decide` overlap on packet decisions; use `review`
  when you also want the HTML dashboard, `decide` for the pending-decisions count and
  the human/blocked tickets that `review` does not cover.
