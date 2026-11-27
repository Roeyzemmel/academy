---
id: {{id}}
kind: {{kind}}
title: {{title}}
status: {{status}}
statement: {{statement}}
modulo: []
depends_on: [{{depends_on}}]
bears_on: [{{bears_on}}]
supersedes: []
lifecycle: active
aliases: []
domain: {{domain}}
tags: [{{tags}}]
proof: ""
evidence: []
history:
  - "{{date}} | {{status}} | {{created}}"
---

## Statement

{{statement_body}}

## Falsifier

{{falsifier}}

## Remarks

<!-- Optional structured form (#127), for a statement with several conclusions: in
## Statement write one line per hypothesis and per conclusion, starting with the bold
markers H1. / C1. (as `**H1.** text`, `**C1.** text`), and add the frontmatter maps
`hypotheses:` (H1: "its text or the definition it uses") and `items:`
(C1: [status, modulo...]) as indented blocks. The record's status is then the one its
items derive; `registry.py structure ID` proposes the maps from those lines. -->
