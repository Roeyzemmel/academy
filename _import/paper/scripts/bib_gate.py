"""PreToolUse gate: only `source-checker` may edit references.bib.

An entry filled in from memory is the easiest way to get a fabricated reference
into a paper, so the bibliography has exactly one door.
"""

import os
import sys

import _common as c

ALLOWED_AGENT = "source-checker"

# Keys the agent's identity has been observed under, in precedence order.
AGENT_KEYS = ("agent_type", "subagent_type", "agentType", "subagentType")


def agent_identity(event):
    """The acting agent's own name, with any plugin namespace stripped.

    The same agent reaches this gate under more than one spelling. Defined in
    `.claude/agents/` it arrives bare (`source-checker`); shipped by the `paper`
    plugin it arrives namespaced (`paper:source-checker`), which is how a
    dispatched subagent presents itself and why the gate used to refuse its own
    doorkeeper. The namespace says which plugin supplied the agent, not who is
    acting, so the identity is the segment after the last colon. Returns "" when
    the event carries no agent at all -- the main session, which is denied.
    """
    for key in AGENT_KEYS:
        raw = event.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.rsplit(":", 1)[-1].strip().lower()
    return ""


def main():
    event = c.read_event()
    root = c.project_root(event)
    if not c.is_paper_repo(root):
        return 0
    path = c.edited_path(event)
    if not path or os.path.basename(path).lower() != "references.bib":
        return 0
    if agent_identity(event) == ALLOWED_AGENT:
        return 0

    seen = next(
        (event[k] for k in AGENT_KEYS if isinstance(event.get(k), str) and event[k].strip()),
        None,
    )
    who = repr(seen) if seen else "the main session (no agent)"
    c.emit("PreToolUse", {
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            "references.bib is edited only by the source-checker agent, which fetches "
            "the record from Crossref / arXiv / MathSciNet and quotes the cited "
            "statement into Drafts/sources.md. This edit came from {who}. Dispatch "
            "source-checker (or use /paper:cite <DOI|arXiv id|key>) rather than "
            "writing the entry here; do not route around this gate."
        ).format(who=who),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
