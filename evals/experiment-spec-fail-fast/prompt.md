---
description: experiment-spec fails fast when the lab already has a result for that claim and class
tags: [judgement]
runs: 3
plugins: ["../../researcher", "../../academy"]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Agent]
env:
  EVAL_ACADEMY_ALLOW_LAUNCH: "1"
---

Launch the agent `researcher:experiment-spec` (Agent tool) with exactly this brief, then reply with its answer verbatim:

WORKFLOW RELAY forward leg. Ticket T-0903, which you relay for researcher@t; it is in-progress. Decide per your agent definition: fail fast (return decision fail-fast with the reason and the ## Result text), or sharpen and forward: file ONE child with tickets_create to the scientist instance only, kind experiment or test, parent T-0903, final_to scientist, and return decision forward with its id. Make no status move on T-0903 (the workflow concludes it). A tickets_create refusal: decision refused, with the refusal verbatim.
