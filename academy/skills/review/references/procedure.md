# `/academy:review` procedure detail

## Mapping a decision to `AskUserQuestion`

A packet decision (`docs/packet-template.md` section 3) looks like:

```
### D1. Recolour lem:x to established now?
- (a) Yes, recolour now.
- (b) Wait until the dependence is checked.
- Recommendation: (a), both runs agree and the dependence question is separate.
```

It becomes one question:

- `header`: `P-NNNN D1` (at most 12 characters; shorten the packet id's zeros if
  needed, e.g. `P12 D1`).
- `question`: the decision text, prefixed with the packet title if the decision alone
  is ambiguous.
- `options`: one per lettered option, label `(a) <first words>`, description the full
  option text. Put the recommended option first and add "(recommended)" to its label;
  the letter written back is still the packet's own letter.
- `multiSelect`: false.

The tool adds "Other" itself; an "Other" answer is written back as `--choice other
--comment "<the human's text>"`. A decision with more than four options is malformed
(`validate_packet` refuses it); report it instead of asking.

## Batching

- At most four questions per `AskUserQuestion` call; decisions from one packet stay
  together in one call when they fit.
- Write back every answer from a call before the next call, so an interrupted review
  loses nothing.
- Informational packets: one question "Acknowledge these N packets?" with options
  "Acknowledge all" / "Leave open"; on the first, `decide P-NNNN --choice ack` for each.

## Answers that need a note

If the human's answer adds a condition ("yes, but open a ticket on …"), write the letter
with `--comment "<the condition>"`. Filing the follow-up ticket is a separate step
that the human confirms (`/academy:board new`), never implied by the decision.

## When the packet is invalid

`packets.py list --json` carries each packet's `_problems`. A packet with problems is
shown on the dashboard but not asked; report the problems and the producing
instance, so it can be fixed.

## The dashboard artifact

- Private, one artifact reused across reviews, recorded as `review-dashboard` in
  `<board>/deep-dives/index.json`.
- It is a snapshot: after the write-back it is out of date until the next review.
  Say so in the report rather than re-publishing unasked.
