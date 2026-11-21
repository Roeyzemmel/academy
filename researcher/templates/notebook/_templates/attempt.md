---
object: {{ref}}
attempt: {{n}}
by: {{by}}
date: {{date}}
outcome: in-progress
---

<!-- outcome: in-progress | complete | failed | superseded. A failed attempt is kept:
why it fails is knowledge. The object's `proof:` field points at the current attempt.
Add the frontmatter key `dependencies`: every registry id and bib:<key>#<pinpoint> the proof
relies on, the same items as "Inputs and their status", e.g.
  `[paper:lem:unfold, flat:GEO-2, bib:LMW16#Theorem 11]`; an empty list only for a
proof that uses no input (required: a complete attempt without the key, or with an input left
out of it, is not filed for review). -->

## Statement as attempted

## Strategy

<!-- the plan and the intuition: a few sentences; a fuller paragraph, with a sketch of the
figure, for a composite proof kept together (academy/references/writing-style.md, rules 3 and 5) -->

## Proof

<!-- as it would appear in the paper: deduction only, every inference with its reason,
intermediate results split out as their own claim objects (writing-style.md, rule 3) -->

## Inputs and their status

<!-- every result used, with its id and registry status, or its citation (bib:<key>#<pinpoint>);
each one also in the frontmatter's dependencies: -->

## Related statements

<!-- each related statement the brief listed: "used as input", or why not (a proved
statement that does the work is cited, never reproved) -->

## Gaps

<!-- each unproved step, marked, one item each, tagged with its class (#126):
  - [fix-known] a routine step, a missing citation, or the proof resting on an existing
    registry statement (open, sketch or proved-modulo: a dependency; name its id)
  - [fix-unclear] no route to close it is known
  - [needs-assumption] closing it needs a hypothesis the statement does not carry now
Only the last two call for a falsifier. "None." when the proof is complete; a proof that is
complete modulo unreviewed inputs says so under Inputs, not here. -->

## Why it fails

<!-- failed attempts only -->
