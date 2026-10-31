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
2. **Take what was recorded on the page** (since 2026-10-31). The dashboard records
   decisions in its shared store. When `review-dashboard` has a URL
   (`py $S/deep_dive_index.py get review-dashboard`), read it with `ArtifactData`
   (`list` of the collections `owner-decisions` and `input`):
   - each field `P-NNNN_Dk` of the document `owner-decisions/main` is the human's
     own choice (only the owner may write it). Write it back as in step 6, unless the
     decision is answered already or the field says `applied`, then `update` the field
     with `applied: true`;
   - each document under `input/` is a coauthor's input (the document id is their viewer
     id). It is never applied: append it to the packet's ticket thread as input
     (`py $S/board.py append T-NNNN --text "coauthor input on P-NNNN Dk: (x) <note>" --as human`)
     and list it in the report, so the human sees it before deciding.
3. **Render.** `py $S/render_packets.py --interactive --out <board>/.render/review.html`.
4. **Publish** the file as a private artifact with the `Artifact` tool, to the URL
   recorded as `review-dashboard`, the same URL every time (read it first when this
   conversation has not published it), with
   `capabilities: <the JSON of py $S/render_packets.py --capabilities>` (the store's
   rules: only the owner writes `owner-decisions`; each other viewer writes only their
   own `input/<id>`). Record a new URL with `deep_dive_index.py set review-dashboard
   --url <url> --kind dashboard --title "Review dashboard"`. Give the human the link,
   and say that coauthors the page is shared with can record input on it.
5. **Ask.** For each packet in dashboard order, its pending decisions go to
   `AskUserQuestion`, at most four per call, one question per decision, each option
   the packet's (a)–(d) with the recommended one marked, and the coauthors' input from
   step 2 quoted in the question. Informational packets (`None.`) are acknowledged together
   in one question. The human may answer "other" with free text, or skip; a human who
   prefers the page answers there and runs this skill again.
6. **Write back** each answer at once, before asking the next batch:
   `py $S/packets.py decide P-NNNN --decision K --choice <letter|other|ack> [--comment "<note or free text>"]`.
   A skipped decision writes nothing.
7. **Report** one line per packet: decided (in chat or on the page) or still open, the
   ticket it echoed to, and the coauthors' input recorded. Re-render and re-publish the
   dashboard only if the human asks.

Writing a decision starts no work: the ticket's owner picks it up in its next inbox
run (`references/budget.md` rule 3).

This skill renders the dashboard and answers packet decisions only. For a
question-only pass with no dashboard — and one that also covers tickets addressed to
human and tickets blocked waiting on human, which are not packets — use
`/academy:decide` instead. Together: review is the dashboard plus decisions,
`/academy:decide` is decisions alone.
