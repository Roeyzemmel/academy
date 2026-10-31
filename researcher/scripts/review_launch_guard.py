"""PreToolUse hook (Agent|Task): an experiment-reviewer is launched only by its workflow.

The experiment review's sequencing (run A, then B only when ``reviews.py decide`` says
``need-B``, the brief built by the script, claim-keeper only on a clean clear) is held
in code by the ``academy-review-experiment`` workflow (``workflows/review-experiment.js``; the 2026-10-31 decision, recorded
in the academy's docs/workflows.md). A workflow launches its agents without the Agent
tool, so this hook never sees them; what it sees is a session or an agent launching a
reviewer by hand, which it refuses with the command to run instead. (The expert plugin has the
same guard for rigor-reviewer.)

The human's escape hatch, for a session where the Workflow tool cannot run:
``ACADEMY_ALLOW_MANUAL_REVIEW=1`` in the environment (the by-hand route of the
review-experiment skill; its report then says the pass ran by hand). Silent for every other agent type.
"""

import json
import os
import sys

AGENT = "experiment-reviewer"
REASON = ("experiment-reviewer runs are launched by the review-experiment workflow, "
          "which holds the sequencing (A, then B only when reviews.py decide says need-B): "
          "run Workflow with scriptPath <researcher plugin>/workflows/review-experiment.js "
          "and args {subject: 'lab:<id>', ticket: 'T-NNNN', mode: 'review' or "
          "'settle-audit' or 'settle-conclude'} (the review-experiment skill gives the exact call). By hand only when the Workflow tool "
          "cannot run: the human sets ACADEMY_ALLOW_MANUAL_REVIEW=1.")

#: the relays of this plugin: launched only by the inbox workflow (academy/workflows/
#: inbox.js), which moves their tickets and checks the child they file
RELAYS = ("experiment-spec", "lit-request")
RELAY_REASON = ("%s is launched by the inbox workflow, which makes its ticket moves and "
                "checks the child it files: run Workflow with scriptPath "
                "<academy plugin>/workflows/inbox.js (the role's inbox skill gives the "
                "exact call). By hand only when the Workflow tool cannot run: the human sets "
                "ACADEMY_ALLOW_MANUAL_REVIEW=1.")


def decide(event):
    """The PreToolUse output for ``event``, or None to stay silent."""
    if not isinstance(event, dict) or event.get("tool_name") not in ("Agent", "Task"):
        return None
    ti = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    bare = str(ti.get("subagent_type") or "").rsplit(":", 1)[-1]
    if bare == AGENT:
        reason = REASON
    elif bare in RELAYS:
        reason = RELAY_REASON % bare
    else:
        return None
    if os.environ.get("ACADEMY_ALLOW_MANUAL_REVIEW") == "1":
        return None
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def main(raw=None):
    raw = sys.stdin.read() if raw is None else raw
    if AGENT not in raw and not any(r in raw for r in RELAYS):   # the common case
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
