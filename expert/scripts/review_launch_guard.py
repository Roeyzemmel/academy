"""PreToolUse hook (Agent|Task): a rigor-reviewer is launched only by the verify workflow.

The proof review's sequencing (run A, then B only if the decision table says
``launch_b``, the identical brief, a reword pass runs R alone) is held in code by the
``academy-verify`` workflow (``workflows/verify.js``; the 2026-10-31 decision, recorded
in the academy's docs/workflows.md). A workflow launches its agents without the Agent
tool, so this hook never sees them; what it sees is a session or an agent launching a
reviewer by hand, which it refuses with the command to run instead.

The human's escape hatch, for a session where the Workflow tool cannot run:
``ACADEMY_ALLOW_MANUAL_REVIEW=1`` in the environment (the by-hand route of the verify
skill; its report then says the pass ran by hand). Silent for every other agent type.
"""

import json
import os
import sys

AGENT = "rigor-reviewer"
REASON = ("rigor-reviewer runs are launched by the verify workflow, which holds the "
          "sequencing (A, then B only if decision_table.py says launch_b; a reword pass "
          "runs R alone): run Workflow with scriptPath <expert plugin>/workflows/verify.js "
          "and args {claim: '<ns:id>', ticket: 'T-NNNN', mode: 'blind' or 'reword'} "
          "(the verify skill gives the exact call). By hand only when the Workflow tool "
          "cannot run: the human sets ACADEMY_ALLOW_MANUAL_REVIEW=1.")


def decide(event):
    """The PreToolUse output for ``event``, or None to stay silent."""
    if not isinstance(event, dict) or event.get("tool_name") not in ("Agent", "Task"):
        return None
    ti = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    sub = str(ti.get("subagent_type") or "")
    if sub.rsplit(":", 1)[-1] != AGENT:
        return None
    if os.environ.get("ACADEMY_ALLOW_MANUAL_REVIEW") == "1":
        return None
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": REASON}}


def main(raw=None):
    raw = sys.stdin.read() if raw is None else raw
    if AGENT not in raw:            # the common case: exit before parsing
        return 0
    try:
        event = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return 0
    out = decide(event)
    if out:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
