"""PreToolUse hook on Bash / PowerShell: only the main session records the human's answers.

``decisions.py`` writes the human's decisions: ``record`` (and with ``--choice release``
the Author home's ``.claude/pinned-release.txt``), ``select``, ``policy``, ``undo``,
``record-batch``. Only the main session asks the human (``AskUserQuestion``,
references/budget.md rule 5), so only it records what they answered
(``/academy:decide``); a subagent (the secretary phrases, it never records) running one of
those verbs is denied. Reading (``list``, ``batches``, ``phrased``, ``stalled-rulings``)
and ``policy --dry-run`` pass, and the main session is never touched.

A hook bug never blocks a call.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _academy as ac  # noqa: E402

#: the verbs that write the human's answer
WRITE_VERBS = ("record-batch", "record", "select", "policy", "undo")
RE_CALL = re.compile(r"decisions\.py['\"]?((?:\s+--?[\w-]+(?:[ =](?!(?:%s)\b)\S+)?)*)\s+(%s)\b"
                     r"([^;&|\n]*)" % ("|".join(WRITE_VERBS), "|".join(WRITE_VERBS)))


def decide(event):
    """``None`` or ``("deny", reason)``."""
    if ac.tool_name(event) not in ("Bash", "PowerShell"):
        return None
    _ns, bare = ac.agent_identity(event)
    if not bare:
        return None
    cmd = str(ac.tool_input(event).get("command") or "")
    for m in RE_CALL.finditer(cmd):
        verb, rest = m.group(2), m.group(3)
        if verb == "policy" and "--dry-run" in rest:
            continue
        return ("deny", "decide_guard: `decisions.py %s` records the human's answer; only the "
                        "main session runs it, after asking the human (/academy:decide). "
                        "%s returns its text instead." % (verb, bare))
    return None


def main():
    try:
        verdict = decide(ac.read_event())
    except Exception:            # a guard bug never blocks a call
        return 0
    if verdict:
        ac.emit_permission(verdict[0], verdict[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
