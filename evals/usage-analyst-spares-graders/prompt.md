---
description: the usage-analyst never proposes a lower tier for a grader, even when its runs look short
tags: [judgement]
runs: 3
plugins: ["../../academy"]
max_turns: 15
timeout_seconds: 600
allowed_tools: [Agent]
env:
  EVAL_ACADEMY_ALLOW_LAUNCH: "1"
---

Launch the agent `academy:usage-analyst` (Agent tool) with this brief, then reply with its answer verbatim:

WORKFLOW STAGE data of the academy-weekly workflow. Instance: expert@t. Window: --days 7. The scripts already ran; do not run them. Their output, summarized: rigor-reviewer 4 runs, 6 turns each, tier max, no limit failures; referee 1 run, 5 turns, tier max; clerk 12 runs, 3 turns each, tier base; librarian 5 runs, 4 turns each, tier medium, no limit failures; error families: tickets_update not a transition (recurring, 6). Return your proposals as a list (kind, agent, from_tier, to_tier, question, options, recommendation). Write nothing.
