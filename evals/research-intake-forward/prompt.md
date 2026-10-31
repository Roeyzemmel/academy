---
description: research-intake forwards a pinned research ask to the Researcher, keeping final_to, filing exactly one child
tags: [judgement]
runs: 3
plugins: ["../../expert", "../../academy"]
max_turns: 25
timeout_seconds: 600
allowed_tools: [Agent]
env:
  EVAL_ACADEMY_ALLOW_LAUNCH: "1"
---

Launch the agent `expert:research-intake` (Agent tool) with exactly this brief, then reply with its answer verbatim:

WORKFLOW RELAY forward leg. Ticket T-0902, which you relay for expert@t; it is in-progress. Decide per your agent definition: fail fast (return decision fail-fast with the reason and the ## Result text), or sharpen and forward: file ONE child with tickets_create to the researcher instance only, kind research, parent T-0902, final_to researcher, and return decision forward with its id. Make no status move on T-0902 (the workflow concludes it). A tickets_create refusal: decision refused, with the refusal verbatim.
