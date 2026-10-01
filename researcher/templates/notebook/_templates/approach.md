---
id: {{id}}
kind: approach
title: {{title}}
statement: {{statement}}
target: {{target}}
lifecycle: active
domain: {{domain}}
tags: [{{tags}}]
history:
  - "{{date}} | active | {{created}}"
---

## Mechanism

The idea, in a paragraph: what would make the target true, and why this differs from
the other approaches. Its directions name it with `approach: {{id}}`; the list is
computed (`notebook.py approach show {{id}}`), never kept here.

## Notes

Blocking: `lifecycle: blocked` needs `blocked_by` (the theorem-strength lemma, a
registry id) and `reopen_if` (the new mechanism, invariant or construction that would
justify reopening); reopening adds a history row naming it.
