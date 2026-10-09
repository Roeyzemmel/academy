"""SubagentStop hook: land a rigor-reviewer's verdict as a review record.

The rigor-reviewer is read-only (no Write, no shell; roster-rules.md rule 2), so its
verdict reaches the files here. Fires for ``expert:rigor-reviewer`` (or a bare
``rigor-reviewer``) only; silent for every other agent. It reads the agent's final
message, parses its closing ``VERDICT`` block (decision_table.parse_verdict_block)
and writes::

    <expert home>/reviews/<ns>/<id-slug>/<pass>/<run>.md

with the block's fields as frontmatter plus a hook-assigned ``run_id``, ``agent``
and ``landed`` date, and the whole report as the body.

**Idempotent by run.** A landing is keyed by the reviewer's agent id (the tail of
``run_id``): a second SubagentStop of the same reviewer -- the hook firing twice, a
manual re-landing -- finds its record and leaves it (identical report) or rewrites it in
place (a changed report), never a ``<run>-2.md``. Only a *different* reviewer landing
the same run letter of the same pass is written as ``<run>-2.md``, and the hook says so.

**Never filed under a placeholder pass.** The pass and statement hash come from the
brief; a block whose ``pass`` is not a pass name (``YYYY-MM-DD[-...]``, as
``reviews.py new-pass`` prints) or whose ``statement_hash`` is not hex (``not in
brief``) blocks the stop once, asking for them; a second stop lands the report under
``<subject>/_unfiled/`` with a visible error for the review-chair, so it never reaches
a pass folder the decision table reads (2026-10-07: ``not-in-brief/B.md``).

With no ``VERDICT`` block the stop is blocked once, asking the reviewer to close
with it (``stop_hook_active`` prevents a loop); a second stop without it lands the
report under ``<run>-noverdict.md`` so nothing is lost. Every landing that does not
happen (no library home, a write error, an empty final message) is reported as a
visible ``systemMessage``, never skipped silently. The library home comes from
workspace.json (the first Expert instance; ``$ACADEMY_WORKSPACE`` overrides it).
"""

import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402
import decision_table as dt  # noqa: E402
import reviews  # noqa: E402

AGENT = "rigor-reviewer"
#: ``gap_class`` (the blocking finding's class) is read back by decision_table.py
RECORD_KEYS = ("subject", "pass", "run", "run_id", "verdict", "modulo", "model",
               "statement_hash", "blocking", "gap_class", "ticket", "agent", "landed")

ASK = ("Close your report with the VERDICT block, exactly in the shape your "
       "instructions give (VERDICT, then subject, pass, run, verdict, modulo, model, "
       "statement_hash, blocking, gap_class, ticket), as the last thing in your final message. "
       "The hook that lands your verdict reads only that block.")


RE_PASS_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}(?:-[A-Za-z0-9][A-Za-z0-9._-]*)?$")
RE_HASH = re.compile(r"^[0-9a-f]{8,64}$")
UNFILED = "_unfiled"

ASK_PASS = ("Your VERDICT block's %s is not a value from your brief (got %s). Copy "
            "subject, pass and statement_hash exactly as the brief gives them, and close "
            "with the VERDICT block again. If the brief gave none, say so in one line and "
            "close anyway: the record is then held aside for the review-chair.")


def agent_key(event):
    """The reviewer's agent id, as the tail of its run ids ('x' when there is none)."""
    return "".join(c for c in str(event.get("agent_id") or event.get("session_id") or "")
                   if c.isalnum())[:6].lower() or "x"


def run_id(event, now=None):
    now = now or datetime.datetime.now()
    return "rv-%s-%s" % (now.strftime("%Y%m%d-%H%M%S"), agent_key(event))


def free_path(folder, stem):
    p = os.path.join(folder, stem + ".md")
    n = 2
    while os.path.exists(p):
        p = os.path.join(folder, "%s-%d.md" % (stem, n))
        n += 1
    return p


def block_problems(block):
    """What makes a VERDICT block unfit to file into a pass: a list of field names."""
    probs = []
    subject = (block.get("subject") or "").strip()
    if not reviews.split_subject(subject)[0]:
        probs.append("subject")
    if not RE_PASS_NAME.match((block.get("pass") or "").strip()):
        probs.append("pass")
    if not RE_HASH.match((block.get("statement_hash") or "").strip().lower()):
        probs.append("statement_hash")
    return probs


def _same_run(folder, key, body):
    """``(path, meta, same_body)`` of the record in ``folder`` landed by the same
    reviewer (run id ending in ``-key``), or of one with this very body when the
    reviewer has no id; None if there is none."""
    if not os.path.isdir(folder):
        return None
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md") or name == "decision.md":
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                meta, old_body = ac.read_frontmatter(fh.read())
        except (OSError, ac.AcademyError):
            continue
        rid = str(meta.get("run_id") or "")
        same_body = old_body.strip() == body.strip()
        if (key != "x" and rid.endswith("-" + key)) or (key == "x" and same_body):
            return path, meta, same_body
    return None


def land(event, text, home, now=None, report=None):
    """Write the record; return its path. ``text`` is the reviewer's final message.

    ``report`` (a list) collects what the caller should tell: a duplicate skipped, a
    record rewritten, a held-aside landing."""
    report = report if report is not None else []
    now = now or datetime.datetime.now()
    block = dt.parse_verdict_block(text) or {}
    subject = (block.get("subject") or "").strip()
    run = (block.get("run") or "").strip().upper()[:1] or "X"
    probs = block_problems(block) if block else []
    if block and probs:
        folder = os.path.join(reviews.subject_dir(home, subject or "unknown"), UNFILED)
        pass_name = (block.get("pass") or "").strip() or None
    else:
        pass_name = (block.get("pass") or "").strip() or \
            "%s-unpaired" % now.strftime("%Y-%m-%d")
        folder = reviews.pass_dir(home, subject or "unknown", pass_name)
    rec = dt.parse_record(text)
    ns, name = ac.agent_identity(event)
    key = agent_key(event)
    body = "\n" + text.strip() + "\n"
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
        "gap_class": rec.get("gap_class") or None,
        "ticket": block.get("ticket") or None,
        "agent": ("%s:%s" % (ns, name)) if ns else name,
        "landed": now.strftime("%Y-%m-%d"),
    }
    prior = _same_run(folder, key, body)
    if prior:
        path, old, same_body = prior
        if same_body:
            report.append("already landed (run id %s); nothing written" % old.get("run_id"))
            return path
        meta["run_id"] = old.get("run_id") or meta["run_id"]
        report.append("the same reviewer's record was rewritten in place (run id %s)"
                      % meta["run_id"])
    else:
        stem = run if block else run + "-noverdict"
        if block and probs:
            stem = "%s-%s" % (run, meta["run_id"])
        path = free_path(folder, stem)
        if os.path.basename(path) != stem + ".md":
            report.append("run %s of this pass was already landed by another reviewer: "
                          "this one is %s; the review-chair decides which run counts"
                          % (run, os.path.basename(path)))
    if block and probs:
        report.append("ERROR: not filed into a pass: the VERDICT block's %s %s not from "
                      "the brief; held aside for the review-chair, who moves it into the "
                      "pass folder once pass and statement hash are known"
                      % (" and ".join(probs), "is" if len(probs) == 1 else "are"))
    ac.atomic_write(path, ac.write_frontmatter({k: meta[k] for k in RECORD_KEYS}, body))
    return path


def _error(text):
    sys.stderr.write("land_verdict: %s\n" % text)
    return ac.emit({"systemMessage": "rigor-reviewer verdict NOT landed: %s" % text})


def main():
    event = ac.read_event()
    if not ex.is_expert_agent(event, AGENT):
        return 0
    text = ex.final_message(event)
    if not text.strip():
        # nothing said (limit error, crash): nothing to land, but say so
        return _error("the reviewer ended with no final message (a limit or a crash?); "
                      "relaunch the run")
    block = dt.parse_verdict_block(text)
    if not event.get("stop_hook_active"):
        if block is None:
            return ac.emit_block(ASK)
        probs = block_problems(block)
        if probs:
            got = ", ".join("%s %r" % (p, (block.get(p) or "").strip()) for p in probs)
            return ac.emit_block(ASK_PASS % (" and ".join(probs), got))
    home = ex.expert_home()
    if not home or not os.path.isdir(home):
        return _error("no Expert library home in workspace.json (%s); the report is only "
                      "in the agent's transcript" % (home or "none"))
    report = []
    try:
        path = land(event, text, home, report=report)
    except (OSError, ac.AcademyError) as exc:
        return _error("could not write the record: %s" % exc)
    msg = "rigor-reviewer verdict landed: %s" % path.replace("\\", "/")
    if report:
        msg += " (" + "; ".join(report) + ")"
    return ac.emit({"systemMessage": msg})


if __name__ == "__main__":
    sys.exit(main())
