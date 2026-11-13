"""Packets (docs/packet-template.md): vocabulary, decisions and answers, validation.

Part of the academy library (see the package docstring in ``__init__.py``); callers use
the names through the package, never through this module.
"""

import re

from ._base import AcademyError, HUMAN, RE_INSTANCE, RE_PACKET_ID, RE_TICKET_ID, today
from ._tickets import RE_WHO

# ----------------------------------------------------------------------------
# Packets (docs/packet-template.md)
# ----------------------------------------------------------------------------

PACKET_KEY_ORDER = ("packet", "title", "instance", "kind", "by", "ticket", "agenda",
                    "subject", "status_before", "status_proposed", "state", "created",
                    "decided")
REQUIRED_PACKET_FIELDS = ("packet", "title", "instance", "kind", "by", "state", "created")
PACKET_KINDS = ("verification", "citation", "referee", "experiment-report",
                "experiment-review", "generalization", "proof", "notation", "agenda",
                "migration", "handover", "usage", "failure", "other")
PACKET_STATES = ("open", "decided", "withdrawn")
CLAIM_STATUSES = ("open", "conjectured", "sketch", "supported", "proved-modulo",
                  "proved", "refuted", "refuted-as-stated")
PACKET_SECTIONS = ("## Summary", "## Produced", "## Established vs assumed",
                   "## Evidence", "## Decisions needed", "## Machine notes",
                   "## Decision")
RE_DECISION_Q = re.compile(r"^### D(\d+)\. (.+)$")
RE_OPTION = re.compile(r"^- \(([a-d])\) (.+)$")
RE_DECISION_LINE = re.compile(
    r"^- D(\d+): (\([a-d]\)|other|ack) \| (\d{4}-\d{2}-\d{2}) \| ([^\s|]+)(?: \| (.*))?$")


def _sections(body):
    """Map '## Heading' -> list of lines under it (up to the next '## ')."""
    out, cur = {}, None
    for ln in body.replace("\r\n", "\n").split("\n"):
        if ln.startswith("## "):
            cur = ln.rstrip()
            out.setdefault(cur, [])
        elif cur is not None:
            out[cur].append(ln)
    return out


def packet_decisions(body):
    """The decisions asked in '## Decisions needed': {k: {"question", "options", "recommendation"}}.

    ``options`` maps letter -> text. An informational packet ('None.') gives {}.
    """
    lines = _sections(body).get("## Decisions needed", [])
    out, cur = {}, None
    for ln in lines:
        m = RE_DECISION_Q.match(ln.strip())
        if m:
            cur = int(m.group(1))
            out[cur] = {"question": m.group(2).strip(), "options": {},
                        "recommendation": None}
            continue
        if cur is None:
            continue
        mo = RE_OPTION.match(ln.strip())
        if mo:
            out[cur]["options"][mo.group(1)] = mo.group(2).strip()
        elif ln.strip().startswith("- Recommendation:"):
            out[cur]["recommendation"] = ln.strip()[len("- Recommendation:"):].strip()
    return out


def packet_answers(body):
    """The answers in '## Decision': {k: (choice, date, speaker, note)}; last line wins."""
    out = {}
    for ln in _sections(body).get("## Decision", []):
        m = RE_DECISION_LINE.match(ln.rstrip())
        if m:
            out[int(m.group(1))] = (m.group(2), m.group(3), m.group(4), m.group(5) or "")
    return out


def validate_packet(meta, body):
    """Return a list of problems with a packet (empty when valid)."""
    probs = []
    for f in REQUIRED_PACKET_FIELDS:
        if meta.get(f) in (None, ""):
            probs.append("missing %s" % f)
    for k in meta:
        if k not in PACKET_KEY_ORDER:
            probs.append("unknown field %s" % k)
    if meta.get("packet") and not RE_PACKET_ID.match(str(meta["packet"])):
        probs.append("packet must look like P-0001")
    if meta.get("instance") and not RE_INSTANCE.match(str(meta["instance"])):
        probs.append("instance must be an instance name")
    if meta.get("kind") and meta["kind"] not in PACKET_KINDS:
        probs.append("kind %r is not one of %s" % (meta["kind"], ", ".join(PACKET_KINDS)))
    if meta.get("state") and meta["state"] not in PACKET_STATES:
        probs.append("state must be one of %s" % ", ".join(PACKET_STATES))
    if meta.get("by") and not RE_WHO.match(str(meta["by"])):
        probs.append("by must be a speaker")
    if meta.get("ticket") and not RE_TICKET_ID.match(str(meta["ticket"])):
        probs.append("ticket must be a ticket id")
    if meta.get("subject") is not None and not isinstance(meta["subject"], list):
        probs.append("subject must be a list")
    for f in ("status_before", "status_proposed"):
        if meta.get(f) and meta[f] not in CLAIM_STATUSES:
            probs.append("%s %r is not a registry status" % (f, meta[f]))
    heads = [ln.rstrip() for ln in body.replace("\r\n", "\n").split("\n")
             if ln.startswith("## ")]
    pos = []
    for h in PACKET_SECTIONS:
        if h not in heads:
            probs.append("missing section %r" % h)
        else:
            pos.append(heads.index(h))
    if len(pos) == len(PACKET_SECTIONS):
        if pos != sorted(pos):
            probs.append("sections out of order")
        extra = heads[pos[3] + 1:pos[4]]
        other = [h for h in heads if h not in PACKET_SECTIONS and h not in extra]
        if other:
            probs.append("extra sections only between Evidence and Decisions needed: %s"
                         % ", ".join(other))
    secs = _sections(body)
    summary = [ln for ln in secs.get("## Summary", []) if ln.strip()]
    if len(summary) > 3:
        probs.append("## Summary has more than three lines")
    asked = packet_decisions(body)
    needed = [ln.strip() for ln in secs.get("## Decisions needed", []) if ln.strip()]
    if not asked and needed != ["None."]:
        probs.append("## Decisions needed must be 'None.' or D1.. decisions")
    if asked and sorted(asked) != list(range(1, len(asked) + 1)):
        probs.append("decisions must be numbered D1..Dn without gaps")
    for k, d in asked.items():
        if not 2 <= len(d["options"]) <= 4:
            probs.append("D%d needs 2-4 options" % k)
        if not d["recommendation"]:
            probs.append("D%d needs a Recommendation line" % k)
    for ln in secs.get("## Decision", []):
        if ln.strip() and not RE_DECISION_LINE.match(ln.rstrip()):
            probs.append("malformed decision line: %r" % ln)
    return probs


def record_decision(body, k, choice, note="", who=HUMAN, date=None):
    """Append one answer line to '## Decision' and return the new body.

    ``choice`` is an option letter ('a'..'d'), 'other' (``note`` required) or 'ack'
    (``k`` must be 0). The caller then checks ``packet_answers`` against
    ``packet_decisions`` to decide whether the packet becomes 'decided'.
    """
    date = date or today()
    if choice in ("other", "ack"):
        token = choice
    elif re.match(r"^[a-d]$", str(choice)):
        token = "(%s)" % choice
    else:
        raise AcademyError("choice must be a-d, 'other' or 'ack'")
    if choice == "other" and not note.strip():
        raise AcademyError("an 'other' answer needs its text")
    if (choice == "ack") != (k == 0):
        raise AcademyError("'ack' is exactly the D0 answer")
    line = "- D%d: %s | %s | %s" % (k, token, date, who)
    if note.strip():
        line += " | " + " ".join(note.split())
    lines = body.replace("\r\n", "\n").rstrip("\n").split("\n")
    if "## Decision" not in lines:
        raise AcademyError("packet has no '## Decision' section")
    start = lines.index("## Decision") + 1
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    last = end
    while last > start and not lines[last - 1].strip():
        last -= 1
    if last == start:
        new = lines[:start] + [""] + [line] + lines[end:]
    else:
        new = lines[:last] + [line] + lines[last:]
    return "\n".join(new) + "\n"


def packet_is_decided(body):
    """True once every asked decision has an answer (or D0 is acknowledged)."""
    asked, answers = packet_decisions(body), packet_answers(body)
    if not asked:
        return 0 in answers
    return all(k in answers for k in asked)
