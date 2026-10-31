---
description: the Expert's clerk escalates a question the library cannot answer instead of answering from memory
tags: [judgement]
runs: 3
plugins: ["../../expert", "../../academy"]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Agent]
env:
  EVAL_ACADEMY_ALLOW_LAUNCH: "1"
---

Launch the agent `expert:clerk` (Agent tool) with exactly this brief, then reply with its answer verbatim:

Answer ticket T-0904 (tickets_get it): its ask, from the library and the registry. Begin your answer with ESCALATE if the library cannot answer it.
