"""SubagentStop hook: land a referee report as a review packet.

The referee is read-only (no Write, no shell), so its report reaches the board here.
Fires for ``expert:referee`` (or a bare ``referee``) only; silent otherwise. It
reads the agent's final message:

* the closing ``REFEREE`` block (``subject: <author instance>``, ``ticket:``,
  ``model:``, ``strength: full|reduced``), parsed like the VERDICT block;
* the report itself, which the referee writes in the packet shape
  (docs/packet-template.md): ``## Summary`` ... ``## Machine notes``, ``## Decision``
  empty, with its findings in extra sections between ``## Evidence`` and
  ``## Decisions needed``.

It then

1. keeps a copy at ``<expert home>/reviews/referee/<instance>/<date>[-n].md``
   (the drift between runs stays visible), and
2. files the packet (kind ``referee``, by ``<expert instance>/referee``) through
   the base plugin's ``packets.create_packet`` -- the library directly, not the MCP
   server, as protocol.md section 5 prescribes for graders -- linked to the ticket
   when the block names one that exists.

A report that does not validate as a packet body is wrapped whole into a valid one
(its own ``##`` headings demoted), with a machine note saying so. A report on a
model other than a primary (Fable or Opus 5.5, ``decision_table.PRIMARY_MODELS``) is
marked reduced-strength in the title and the notes.
With no ``REFEREE`` block the stop is blocked once to ask for it.
"""

import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
import decision_table as dt  # noqa: E402
from _expert import ac  # noqa: E402

AGENT = "referee"
PRIMARY = ", ".join(dt.PRIMARY_MODELS)    # for messages; the test is dt.is_primary
ASK = ("Close your final message with the REFEREE block (REFEREE, then subject: "
       "<author instance>, ticket: <T-NNNN or none>, model: <your model>, strength: "
       "full|reduced), after the report written in the packet shape your "
       "instructions give. The hook that lands the report reads only your final message.")


def parse_block(text, word="REFEREE"):
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().strip("`*#: ").upper() == word:
            start = i
    if start is None:
        return None, text
    out = {}
    end = len(lines)
    for j, ln in enumerate(lines[start + 1:], start + 1):
        if not ln.strip() or ln.strip().startswith("```"):
            if out:
                end = j
                break
            continue
        m = re.match(r"^\s*([A-Za-z_]+)\s*:\s*(.*?)\s*$", ln)
        if not m:
            end = j
            break
        out[m.group(1).lower()] = m.group(2)
    # the report is everything before the block (dropping an opening fence line)
    head = lines[:start]
    if head and head[-1].strip().startswith("```"):
        head = head[:-1]
    return out, "\n".join(head).rstrip()


def packet_body(report):
    """From ``## Summary`` onward, with an empty ``## Decision`` guaranteed."""
    i = report.find("## Summary")
    if i < 0:
        return None
    body = report[i:].rstrip()
    m = re.search(r"^## Decision\s*$", body, flags=re.M)
    if m:
        body = body[:m.start()].rstrip()
    return "\n" + body + "\n\n## Decision\n"


def wrap(report, ref, note):
    """A valid packet body around a report that is not in the packet shape."""
    demoted = re.sub(r"^(#{1,2}) ", lambda m: "#" * (len(m.group(1)) + 2) + " ",
                     report.strip(), flags=re.M)
    first = [ln.strip() for ln in report.strip().split("\n\n")[0].split("\n") if ln.strip()]
    summary = " ".join(first)[:400] or "Referee report (see Report below)."
    return "\n".join([
        "", "## Summary", "", summary, "",
        "## Produced", "", "- The referee report: `%s`." % ref, "",
        "## Established vs assumed", "",
        "- **Not established:** a referee report checks no proof line by line and "
        "certifies nothing; a clean section is not a correctness claim.", "",
        "## Evidence", "", "- The report as written: `%s`." % ref, "",
        "## Report", "", demoted, "",
        "## Decisions needed", "", "None.", "",
        "## Machine notes", "", "- land_referee: %s" % note, "",
        "## Decision", ""])


def add_note(body, note):
    """Append one bullet to ``## Machine notes`` (replacing a lone ``None.``)."""
    lines = body.split("\n")
    try:
        i = next(k for k, ln in enumerate(lines) if ln.rstrip() == "## Machine notes")
    except StopIteration:
        return body
    j = next((k for k in range(i + 1, len(lines)) if lines[k].startswith("## ")),
             len(lines))
    sec = [ln for ln in lines[i + 1:j] if ln.strip() and ln.strip() != "None."]
    sec.append("- %s" % note)
    return "\n".join(lines[:i + 1] + [""] + sec + [""] + lines[j:])


def copy_path(home, instance, date):
    folder = os.path.join(ex.home_path(home, ex.expert_config(home), "reviews", "reviews"),
                          "referee", ex.slug_id(instance or "unknown"))
    p = os.path.join(folder, date + ".md")
    n = 2
    while os.path.exists(p):
        p = os.path.join(folder, "%s-%d.md" % (date, n))
        n += 1
    return p


def land(event, text, workspace, home, now=None):
    """Keep the copy and file the packet; return ``(copy path, packet path)``."""
    now = now or datetime.datetime.now()
    date = now.strftime("%Y-%m-%d")
    block, report = parse_block(text)
    block = block or {}
    subject = (block.get("subject") or "").strip()
    ticket = (block.get("ticket") or "").strip()
    ticket = ticket if ac.RE_TICKET_ID.match(ticket) else None
    model = (block.get("model") or "").strip()
    reduced = (block.get("strength") or "").strip().lower().startswith("reduced") or \
        bool(model and not dt.is_primary(model))
    expert = ex.expert_instance_for_home(workspace, home) or \
        (ex.expert_instances(workspace) or [None])[0]
    if not expert:
        raise ac.AcademyError("no expert instance in workspace.json")

    cpath = copy_path(home, subject, date)
    ac.atomic_write(cpath, report.strip() + "\n")
    ref = "file:%s/%s" % (expert, os.path.relpath(cpath, home).replace("\\", "/"))

    notes = []
    body = packet_body(report)
    meta_probe = {"packet": "P-0000", "title": "x", "instance": expert, "kind": "referee",
                  "by": expert + "/referee", "state": "open", "created": date}
    if body is None or ac.validate_packet(meta_probe, body):
        why = "the report was not in the packet shape" if body is None else \
            "the report's packet shape did not validate (%s)" % \
            "; ".join(ac.validate_packet(meta_probe, body))[:300]
        body = wrap(report, ref, why + "; wrapped whole")
    if reduced:
        notes.append("land_referee: reduced-strength report (model %s, not a primary: %s); "
                     "its clean sections are not treated as cleared" % (model or "unnamed",
                                                                        PRIMARY))
    store = ac.open_store(workspace)                # the ticket board, either backend
    packets = ex.base_script("packets")
    if ticket and not store.find(ticket):
        notes.append("land_referee: ticket %s named by the referee is not on the board; "
                     "the packet is filed unlinked" % ticket)
        ticket = None
    for n in notes:
        body = add_note(body, n)
    title = "Referee report on %s (%s)%s" % (subject or "the paper", date,
                                              " - reduced strength" if reduced else "")
    subj = ["file:%s/main.tex" % subject] if ac.RE_INSTANCE.match(subject or "") else []
    ppath = packets.create_packet(store, expert, title, kind="referee",
                                  by=expert + "/referee", ticket=ticket, subject=subj,
                                  body=body, workspace=workspace, date=date)
    return cpath, ppath


def main():
    event = ac.read_event()
    if not ex.is_expert_agent(event, AGENT):
        return 0
    text = ex.final_message(event)
    if not text.strip():
        return 0
    block, _ = parse_block(text)
    if block is None and not event.get("stop_hook_active"):
        return ac.emit_block(ASK)
    ws = ex.load_workspace_or_none()
    home = ex.expert_home(ws)
    if not ws or not home or not os.path.isdir(home):
        return 0
    try:
        cpath, ppath = land(event, text, ws, home)
    except (OSError, ac.AcademyError) as exc:
        sys.stderr.write("land_referee: could not land the report: %s\n" % exc)
        return 0
    return ac.emit({"systemMessage": "referee report landed: %s; packet %s"
                    % (cpath.replace("\\", "/"), os.path.basename(ppath))})


if __name__ == "__main__":
    sys.exit(main())
