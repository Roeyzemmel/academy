---
object: {{ref}}
attempt: {{n}}
by: {{by}}
date: {{date}}
outcome: in-progress
dependencies: []
---

<!-- outcome: in-progress | complete | failed | superseded. A failed attempt is kept:
why it fails is knowledge. The object's `proof:` field points at the current attempt.
dependencies: every registry id and bib:<key>#<pinpoint> the proof relies on, the same items
as "Inputs and their status", e.g. [paper:lem:unfold, flat:GEO-2, bib:LMW16#Theorem 11]
(required: a complete attempt that leaves an input out of it is not filed for review). -->

## Statement as attempted

## Strategy

<!-- the plan and the intuition: a few sentences; a fuller paragraph, with a sketch of the
figure, for a composite proof kept together (academy/references/proof-style.md, rules 2-3) -->

## Proof

<!-- as it would appear in the paper: deduction only, every inference with its reason,
intermediate results split out as their own claim objects (proof-style.md) -->

## Inputs and their status

<!-- every result used, with its id and registry status, or its citation (bib:<key>#<pinpoint>);
each one also in the frontmatter's dependencies: -->

## Related statements

<!-- each related statement the brief listed: "used as input", or why not (a proved
statement that does the work is cited, never reproved) -->

## Gaps

<!-- each unproved step, marked; empty only when the proof is complete -->

## Why it fails

<!-- failed attempts only -->
