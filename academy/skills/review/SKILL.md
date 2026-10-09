---
name: review
description: 'Review open packets across all instances: render one private HTML dashboard, put each pending decision to the human, and write each answer back to the packet and its ticket. Use for "review", "show me the packets", "let''s go through the decisions".'
---

# Review packets

`$ARGUMENTS` is empty (all open packets), an instance, or packet ids. Scripts: `$S` as
in `${CLAUDE_PLUGIN_ROOT}/references/scripts.md`. The packet format and the write-back
rules are `docs/packet-template.md`; the procedure detail is
`${CLAUDE_PLUGIN_ROOT}/skills/review/references/procedure.md`. Only the main session
runs this skill: only the human decides.

1. **List.** `py $S/packets.py list --open [--instance X] --json`. If none, say so and
   stop.
2. **Render.** `py $S/render_packets.py --out <board>/.render/review.html`.
3. **Publish** the file as a private artifact with the `Artifact` tool, to the URL
   recorded as `review-dashboard` (`py $S/deep_dive_index.py get review-dashboard`):
   the same URL every time, reading it first when this conversation has not
   published it. Record a new URL with `deep_dive_index.py set review-dashboard
   --url <url> --kind dashboard --title "Review dashboard"`. Give the human the link.
4. **Ask.** For each packet in dashboard order, its pending decisions go to
   `AskUserQuestion`, at most four per call, one question per decision, each option
   the packet's (a)–(d) with the recommended one marked. Informational packets
   (`None.`) are acknowledged together in one question. The human may answer "other" with
   free text, or skip.
5. **Write back** each answer at once, before asking the next batch:
   `py $S/packets.py decide P-NNNN --decision K --choice <letter|other|ack> [--comment "<note or free text>"]`.
   A skipped decision writes nothing.
6. **Report** one line per packet: decided or still open, and the ticket it echoed to.
   Re-render and re-publish the dashboard only if the human asks.

Writing a decision starts no work: the ticket's owner picks it up in its next inbox
run (`references/budget.md` rule 3).

This skill renders the dashboard and answers packet decisions only. For a
question-only pass with no dashboard — and one that also covers tickets addressed to
human and tickets blocked waiting on human, which are not packets — use
`/academy:decide` instead. Together: review is the dashboard plus decisions,
`/academy:decide` is decisions alone.
