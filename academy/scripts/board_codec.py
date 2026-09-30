"""board_codec.py -- ticket <-> GitHub issue codec (docs/github-board.md).

Pure and offline: no network, no board directory. The same rules serve every transport
(the github MCP in a cloud session, a token over REST, the migration manifest).

Mapping (one ticket = one issue, ``issue number == ticket number``):

    title            ``T-0042: <title>``
    state            open, or closed for a terminal status
                     (closed -> completed; rejected / cancelled -> not_planned)
    labels           ``status:`` ``to:`` ``role:`` (derived from ``to``) ``from:`` ``kind:``
                     ``prio:``; exactly one of each
    body             ``<!-- academy:meta {json} -->`` (the fields no label carries) followed
                     by the ticket body up to, not including, ``## Thread``
    comments         one per thread entry: ``<!-- academy:thread -->`` ``**who** date`` text

Labels are the write surface: on decode a label overrides the meta line. Usage:

    py board_codec.py encode   < ticket.json    {"meta": {...}, "body": "..."}
    py board_codec.py decode   < issue.json     {"issue": {...}, "comments": [...]}
    py board_codec.py validate < issue.json     problems as a JSON list (exit 1 if any)
    py board_codec.py transition < req.json     {"old": "open", "new": "accepted", "party": "receiver"}
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lib"))

import academy_common as ac  # noqa: E402

META_PREFIX = "<!-- academy:meta "
META_SUFFIX = " -->"
THREAD_MARK = "<!-- academy:thread -->"
LABEL_FIELDS = (("status", "status"), ("to", "to"), ("from", "from"),
                ("kind", "kind"), ("priority", "prio"))
#: fields carried by the meta line (everything else is a label or the title)
META_FIELDS = tuple(k for k in ac.TICKET_KEY_ORDER
                    if k not in ("id", "title", "status", "to", "from", "kind", "priority"))
ROLES = ("author", "researcher", "expert", "scientist", "human")
RE_TITLE = re.compile(r"^(T-\d{4,}): (.*)$", re.S)
RE_META = re.compile(r"^<!-- academy:meta (.*) -->$")
RE_COMMENT = re.compile(r"^<!-- academy:thread -->\n\*\*(\S+)\*\* (\d{4}-\d{2}-\d{2})\n\n(.*)$", re.S)
MAX_BODY = 65000


class CodecError(ac.AcademyError):
    pass


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------

def ticket_number(tid):
    return int(str(tid).split("-", 1)[1])


def role_of(to):
    """The role label value for a ``to``: 'human' or the instance's role."""
    if to == ac.HUMAN:
        return "human"
    m = ac.RE_INSTANCE.match(str(to))
    if not m:
        raise CodecError("cannot derive a role from to=%r" % (to,))
    return m.group(1)


def label_names(labels):
    """Label names from the strings or ``{"name": ...}`` dicts an API returns."""
    return [x["name"] if isinstance(x, dict) else str(x) for x in labels or []]


def state_of(status):
    """``(state, state_reason)`` of an issue for a ticket status."""
    if status == "closed":
        return "closed", "completed"
    if status in ("rejected", "cancelled"):
        return "closed", "not_planned"
    return "open", None


def _dump_meta(fields):
    text = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
    return META_PREFIX + text.replace(">", "\\u003e") + META_SUFFIX


def _split_thread(body):
    """``(pre, entries)``: the body before ``## Thread`` and the thread entries."""
    lines = body.replace("\r\n", "\n").split("\n")
    if ac.THREAD_HEADING not in lines:
        return body, []
    i = lines.index(ac.THREAD_HEADING)
    pre = "\n".join(lines[:i]) + "\n"
    return pre, ac.thread_lines(body)


# ----------------------------------------------------------------------------
# Ticket -> issue
# ----------------------------------------------------------------------------

def labels_for(meta):
    out = []
    for field, prefix in LABEL_FIELDS:
        if meta.get(field) not in (None, ""):
            out.append("%s:%s" % (prefix, meta[field]))
    out.insert(2, "role:%s" % role_of(meta["to"]))
    return out


def encode_comment(date, who, text):
    return "%s\n**%s** %s\n\n%s" % (THREAD_MARK, who, date, text)


def encode(meta, body):
    """The issue payload of a ticket: number, title, body, labels, state, comments, links."""
    fields = {k: meta[k] for k in META_FIELDS if k in meta}
    pre, entries = _split_thread(body)
    issue_body = _dump_meta(fields) + "\n" + pre
    status = meta["status"]
    state, reason = state_of(status)
    return {
        "number": ticket_number(meta["id"]),
        "title": "%s: %s" % (meta["id"], meta["title"]),
        "body": issue_body,
        "labels": labels_for(meta),
        "state": state,
        "state_reason": reason,
        # the receiving human gets the native assignee; instances are not GitHub users
        "assign_human": meta["to"] == ac.HUMAN,
        "comments": [encode_comment(d, w, t) for d, w, t in entries],
        "parent": meta.get("parent") or None,
        "blocked_by": [t for t in (meta.get("waiting_on") or [])
                       if ac.RE_TICKET_ID.match(str(t))],
    }


def placeholder(number):
    """A closed 'not planned' issue that keeps ``number`` reserved for a missing ticket id."""
    return {"number": number, "title": "T-%04d: (unused id)" % number,
            "body": "Reserved so that issue numbers equal ticket ids.\n",
            "labels": ["placeholder"], "state": "closed", "state_reason": "not_planned",
            "assign_human": False, "comments": [], "parent": None, "blocked_by": []}


# ----------------------------------------------------------------------------
# Issue -> ticket
# ----------------------------------------------------------------------------

def _one_label(names, prefix):
    vals = [n[len(prefix) + 1:] for n in names if n.startswith(prefix + ":")]
    return vals


def decode(issue, comments=()):
    """``(meta, body)`` of an issue. ``comments`` are the comment bodies, oldest first.

    Comments that are not thread entries (no marker) are ignored: people may talk on the
    issue; only marked comments are the ticket's Thread.
    """
    m = RE_TITLE.match(issue.get("title") or "")
    if not m:
        raise CodecError("issue #%s: title does not start with 'T-NNNN: '" % issue.get("number"))
    tid, title = m.group(1), m.group(2)
    if ticket_number(tid) != issue.get("number"):
        raise CodecError("issue #%s carries %s" % (issue.get("number"), tid))
    text = issue.get("body") or ""
    first, _, pre = text.partition("\n")
    mm = RE_META.match(first)
    if not mm:
        raise CodecError("issue #%s: no academy:meta line" % issue["number"])
    fields = json.loads(mm.group(1))
    names = label_names(issue.get("labels"))
    meta = {"id": tid, "title": title}
    for field, prefix in LABEL_FIELDS:
        vals = _one_label(names, prefix)
        if len(vals) != 1:
            raise CodecError("issue #%s: need exactly one %s: label, found %d"
                             % (issue["number"], prefix, len(vals)))
        meta[field] = vals[0]
    meta.update(fields)
    ordered = {k: meta[k] for k in ac.TICKET_KEY_ORDER if k in meta}
    for k in meta:
        ordered.setdefault(k, meta[k])
    body = pre + ac.THREAD_HEADING + "\n\n"
    entries = []
    for c in comments:
        cm = RE_COMMENT.match(c.replace("\r\n", "\n"))
        if not cm:
            continue
        who, date, txt = cm.groups()
        parts = txt.strip("\n").split("\n")
        entries.append("- %s %s: %s" % (date, who, parts[0]))
        entries.extend("  " + p for p in parts[1:])
    body += "\n".join(entries) + "\n" if entries else ""
    return ordered, body


def render(meta, body):
    """The ticket file text for ``(meta, body)`` (what board.py writes)."""
    ordered = {k: meta[k] for k in ac.TICKET_KEY_ORDER if k in meta}
    return ac.write_frontmatter(ordered, body)


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------

def validate_issue(issue, comments=()):
    """Problems with an issue as a ticket (empty when consistent)."""
    try:
        meta, body = decode(issue, comments)
    except (CodecError, ValueError) as e:
        return [str(e)]
    probs = ac.validate_ticket(meta, body)
    names = label_names(issue.get("labels"))
    roles = _one_label(names, "role")
    try:
        want = role_of(meta["to"])
    except CodecError as e:
        return probs + [str(e)]
    if roles != [want]:
        probs.append("role label %s does not match to=%s (want role:%s)" % (roles, meta["to"], want))
    state, reason = state_of(meta["status"])
    if issue.get("state") and issue["state"] != state:
        probs.append("issue is %s but status %s wants %s" % (issue["state"], meta["status"], state))
    if state == "closed" and issue.get("state_reason") not in (None, reason):
        probs.append("state_reason %s but status %s wants %s"
                     % (issue.get("state_reason"), meta["status"], reason))
    if len(issue.get("body") or "") > MAX_BODY:
        probs.append("issue body exceeds %d characters" % MAX_BODY)
    return probs


def check_transition(old, new, party, human=False):
    """Problems with a status change by ``party`` in {'sender', 'receiver'} (or human)."""
    if old == new:
        return []
    if human:
        return []
    allowed = ac.TRANSITIONS.get((old, new))
    if allowed is None:
        return ["%s -> %s is not a legal transition" % (old, new)]
    if party not in allowed:
        return ["%s -> %s is the %s's move, not the %s's" % (old, new, allowed[0], party)]
    return []


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("encode", "decode", "validate", "transition"):
        sys.stderr.write(__doc__)
        return 2
    req = json.load(sys.stdin)
    cmd = argv[0]
    if cmd == "encode":
        out = encode(req["meta"], req["body"])
    elif cmd == "decode":
        meta, body = decode(req["issue"], req.get("comments", []))
        out = {"meta": meta, "body": body}
    elif cmd == "validate":
        out = validate_issue(req["issue"], req.get("comments", []))
    else:
        out = check_transition(req["old"], req["new"], req.get("party", "receiver"),
                               bool(req.get("human")))
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 1 if cmd in ("validate", "transition") and out else 0


if __name__ == "__main__":
    sys.exit(main())
