---
name: status
description: One screen on the lab (the Scientist instance) — its home and whether it is switched over, the env profiles and policy, the job queue by state, the tickets addressed to it, its open packets, and the results that have come back with no experiment-report packet yet. Use for "lab status", "what's running", "what came back", "which results still need a report", and after a queue tick.
---

# Lab status

Run, in order, and print the output as it is:

```
py "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" home
py "${CLAUDE_PLUGIN_ROOT}/scripts/lab.py" status
```

`home` names the instance, home, domains (with their pack folders), env profiles and
policy, and says whether the home has its `.claude/academy.json` yet (before the
switch-over the scripts assume the documented layout). `status` counts the local
queue by state (local files only: no remote host is contacted; a tick through
`/scientist:queue` refreshes them), the non-terminal tickets to the instance by
status, the open packets it produced, and the result JSONs with no
experiment-report packet on the board, newest first.

Then, in at most three lines, say what is next: results awaiting a report →
`/scientist:experiment report <script>`; tickets waiting → `/scientist:inbox`;
running jobs → `/scientist:queue`. Start nothing yourself
(`${CLAUDE_PLUGIN_ROOT}/../academy/references/budget.md`, rule 3). For the whole
academy, `/academy:status` and `/academy:desk`.
