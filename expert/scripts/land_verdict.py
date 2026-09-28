"""SubagentStop hook: land a rigor-reviewer's verdict as a review record.

The rigor-reviewer is read-only (no Write, no shell; roster-rules.md rule 2), so its
verdict reaches the files here. Fires for ``expert:rigor-reviewer`` (or a bare
``rigor-reviewer``) only; silent for every other agent. It reads the agent's final
message, parses its closing ``VERDICT`` block (decision_table.parse_verdict_block)
and writes::

    <expert home>/reviews/<ns>/<id-slug>/<pass>/<run>.md

with the block's fields as frontmatter plus a hook-assigned ``run_id``, ``agent``
and ``landed`` date, and the whole report as the body. An existing record is never
overwritten: a second landing of the same run is written as ``<run>-2.md`` and so
on. The review-chair then runs ``decision_table.py`` on the pass folder's A and B.

With no ``VERDICT`` block the stop is blocked once, asking the reviewer to close
with it (``stop_hook_active`` prevents a loop); a second stop without it lands the
report under ``<run>-noverdict.md`` so nothing is lost. The library home comes from
workspace.json (the first Expert instance; ``$ACADEMY_WORKSPACE`` overrides it).
"""

import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402
import decision_table as dt  # noqa: E402
import reviews  # noqa: E402

AGENT = "rigor-reviewer"
RECORD_KEYS = ("subject", "pass", "run", "run_id", "verdict", "modulo", "model",
               "statement_hash", "blocking", "ticket", "agent", "landed")

ASK = ("Close your report with the VERDICT block, exactly in the shape your "
       "instructions give (VERDICT, then subject, pass, run, verdict, modulo, model, "
       "statement_hash, blocking, ticket), as the last thing in your final message. "
       "The hook that lands your verdict reads only that block.")


def run_id(event, now=None):
    now = now or datetime.datetime.now()
    aid = "".join(c for c in str(event.get("agent_id") or event.get("session_id") or "")
                  if c.isalnum())[:6] or "x"
    return "rv-%s-%s" % (now.strftime("%Y%m%d-%H%M%S"), aid.lower())


def free_path(folder, stem):
    p = os.path.join(folder, stem + ".md")
    n = 2
    while os.path.exists(p):
        p = os.path.join(folder, "%s-%d.md" % (stem, n))
        n += 1
    return p


def land(event, text, home, now=None):
    """Write the record; return its path. ``text`` is the reviewer's final message."""
    now = now or datetime.datetime.now()
    block = dt.parse_verdict_block(text) or {}
    subject = (block.get("subject") or "").strip()
    pass_name = (block.get("pass") or "").strip() or "%s-unpaired" % now.strftime("%Y-%m-%d")
    run = (block.get("run") or "").strip().upper()[:1] or "X"
    folder = reviews.pass_dir(home, subject or "unknown", pass_name)
    rec = dt.parse_record(text)
    ns, name = ac.agent_identity(event)
    meta = {
        "subject": subject or None,
        "pass": pass_name,
        "run": run,
        "run_id": run_id(event, now),
        "verdict": rec["verdict"] or (block.get("verdict") or None),
        "modulo": rec["modulo"],
        "model": block.get("model") or None,
        "statement_hash": block.get("statement_hash") or None,
        "blocking": rec["blocking"] or None,
        "ticket": block.get("ticket") or None,
        "agent": ("%s:%s" % (ns, name)) if ns else name,
        "landed": now.strftime("%Y-%m-%d"),
    }
    stem = run if block else run + "-noverdict"
    path = free_path(folder, stem)
    body = "\n" + text.strip() + "\n"
    ac.atomic_write(path, ac.write_frontmatter({k: meta[k] for k in RECORD_KEYS}, body))
    return path


def main():
    event = ac.read_event()
    if not ex.is_expert_agent(event, AGENT):
        return 0
    text = ex.final_message(event)
    if not text.strip():
        return 0                        # nothing said (limit error, crash): nothing to land
    has_block = dt.parse_verdict_block(text) is not None
    if not has_block and not event.get("stop_hook_active"):
        return ac.emit_block(ASK)
    home = ex.expert_home()
    if not home or not os.path.isdir(home):
        return 0
    try:
        path = land(event, text, home)
    except (OSError, ac.AcademyError) as exc:
        sys.stderr.write("land_verdict: could not land the verdict: %s\n" % exc)
        return 0
    return ac.emit({"systemMessage": "rigor-reviewer verdict landed: %s"
                    % path.replace("\\", "/")})


if __name__ == "__main__":
    sys.exit(main())
