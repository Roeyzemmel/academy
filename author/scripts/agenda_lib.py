"""agenda_lib -- the Author's agenda (Drafts/agenda.md).

The agenda is plain Markdown that Roey reads and edits; this module is its one parser
and writer. There is no roadmap: the board is the Author's only queue (work items are
tickets; docs/superpowers/specs/2026-09-29-campaign-mode-design.md section 10).
Format (also in references/formats.md):

agenda.md
---------
::

    # Agenda: author@main

    <!-- academy agenda v1. ... -->

    ## Milestones

    - `coauthor-round`: thm:main=proved, lem:strip=sketch

    ## Entries

    | # | label | claim | required | depends_on | owner | status |
    |---|---|---|---|---|---|---|
    | 1 | thm:main | paper:thm:main | proved | lem:strip, prop:x | author@main | sketch |

* Row order is the precedence (paper order by default); ``#`` is renumbered on write.
* ``label`` is the LaTeX label; ``claim`` the registry id (``-`` if none yet).
* ``required`` is the status the entry must reach (one status vocabulary).
* ``depends_on`` lists labels of other entries (or claim ids), comma separated.
* ``owner`` is the instance that must deliver it (default: this Author instance).
* ``status`` is generated (``agenda.py status``); never hand-edited.
"""

import os
import re

STATUS_RANK = {"open": 0, "conjectured": 1, "sketch": 2, "supported": 2,
               "proved-modulo": 3, "proved": 4}
FALSE_STATUSES = ("refuted", "refuted-as-stated")
CLAIM_STATUSES = ("open", "conjectured", "sketch", "supported", "proved-modulo", "proved",
                  "refuted", "refuted-as-stated")

PRIORITIES = ("high", "normal", "low")
PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}
AGENDA_COLUMNS = ("#", "label", "claim", "required", "depends_on", "owner", "status")

RE_TICKET_ID = re.compile(r"^T-\d{4,}$")
RE_MILESTONE = re.compile(r"^- `?([A-Za-z0-9][A-Za-z0-9_.-]*)`?:\s*(.*)$")


class AgendaError(Exception):
    """A malformed agenda."""


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------

def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read().replace("\r\n", "\n")


def write_text(path, text):
    """Write LF text atomically (temp file + replace)."""
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp-%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def split_list(value):
    """``"[a, b]"`` / ``"a, b"`` / ``"a b"`` / ``"-"`` -> ``['a', 'b']``."""
    v = (value or "").strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    if v in ("", "-", "none", "None"):
        return []
    return [x.strip().strip("`") for x in re.split(r"[,\s]+", v) if x.strip().strip("`")]


def fmt_list(items):
    return "[" + ", ".join(items) + "]"


def satisfied(current, required):
    """Does a claim at ``current`` meet ``required``?

    Ranks: open < conjectured < sketch = supported < proved-modulo < proved. A false
    status meets only itself; an unknown or empty status meets nothing.
    """
    if not current or not required:
        return False
    if required in FALSE_STATUSES:
        return current == required
    if current not in STATUS_RANK or required not in STATUS_RANK:
        return False
    return STATUS_RANK[current] >= STATUS_RANK[required]


def local_label(ref, ns):
    """``paper:thm:main`` -> ``thm:main`` when ``ns`` is ``paper``; others unchanged."""
    ref = (ref or "").strip().strip("`")
    if ns and ref.startswith(ns + ":"):
        return ref[len(ns) + 1:]
    return ref


# ----------------------------------------------------------------------------
# Agenda
# ----------------------------------------------------------------------------

class Entry(object):
    __slots__ = ("label", "claim", "required", "depends_on", "owner", "status", "position")

    def __init__(self, label, claim="-", required="proved", depends_on=None, owner="",
                 status="", position=0):
        self.label = label
        self.claim = claim or "-"
        self.required = required
        self.depends_on = list(depends_on or [])
        self.owner = owner
        self.status = status
        self.position = position

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}

    @property
    def done(self):
        return satisfied(self.status, self.required)


class Agenda(object):
    """The parsed agenda: ``head`` (text before the table), ``entries``, ``tail``."""

    def __init__(self, title="", head="", entries=None, tail="", milestones=None):
        self.head = head
        self.entries = list(entries or [])
        self.tail = tail
        self.milestones = dict(milestones or {})
        self.title = title

    def by_label(self):
        return {e.label: e for e in self.entries}

    def lookup(self, ref, ns):
        """The entry named by ``ref`` (a label or a claim id), or None."""
        ref = (ref or "").strip().strip("`")
        lab = local_label(ref, ns)
        bl = self.by_label()
        if lab in bl:
            return bl[lab]
        for e in self.entries:
            if e.claim == ref:
                return e
        return None

    def users(self):
        """label -> labels of the entries that depend on it (direct)."""
        out = {e.label: [] for e in self.entries}
        for e in self.entries:
            for d in e.depends_on:
                if d in out:
                    out[d].append(e.label)
        return out

    def unblock_position(self, label):
        """The earliest position among ``label`` and every entry resting on it."""
        bl = self.by_label()
        if label not in bl:
            return None
        users = self.users()
        best, seen, stack = bl[label].position, {label}, [label]
        while stack:
            cur = stack.pop()
            for u in users.get(cur, []):
                if u not in seen:
                    seen.add(u)
                    best = min(best, bl[u].position)
                    stack.append(u)
        return best


def _cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse_agenda(text):
    """Parse agenda.md text. Raises AgendaError on a malformed table."""
    lines = text.replace("\r\n", "\n").split("\n")
    title = ""
    for ln in lines:
        if ln.startswith("# "):
            title = ln[2:].strip()
            break
    # milestones: '- name: a=b, c=d' lines under '## Milestones'
    milestones, section = {}, None
    for ln in lines:
        if ln.startswith("## "):
            section = ln[3:].strip().lower()
            continue
        if section == "milestones":
            m = RE_MILESTONE.match(ln.strip())
            if m:
                goals = {}
                for part in split_list(m.group(2)):
                    if "=" not in part:
                        raise AgendaError("milestone %s: %r is not label=status"
                                          % (m.group(1), part))
                    lab, st = part.split("=", 1)
                    goals[lab.strip()] = st.strip()
                milestones[m.group(1)] = goals
    # the table: the first header row naming 'label'
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("|") and "label" in [c.lower() for c in _cells(ln)]:
            start = i
            break
    if start is None:
        return Agenda(title, text, [], "", milestones)
    header = [c.lower() for c in _cells(lines[start])]
    for col in ("label", "required"):
        if col not in header:
            raise AgendaError("agenda table has no %r column" % col)
    i = start + 1
    if i < len(lines) and re.match(r"^\s*\|[\s:|-]+\|?\s*$", lines[i]):
        i += 1
    entries = []
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = _cells(lines[i])
        row = dict(zip(header, cells + [""] * (len(header) - len(cells))))
        label = row.get("label", "").strip("`")
        if not label:
            raise AgendaError("agenda row %d has no label" % (i + 1))
        entries.append(Entry(label=label, claim=row.get("claim", "-").strip("`") or "-",
                             required=row.get("required", "").strip() or "proved",
                             depends_on=split_list(row.get("depends_on", "")),
                             owner=row.get("owner", "").strip(),
                             status=row.get("status", "").strip().strip("`"),
                             position=len(entries) + 1))
        i += 1
    head = "\n".join(lines[:start])
    tail = "\n".join(lines[i:])
    return Agenda(title, head, entries, tail, milestones)


def render_agenda_table(entries):
    out = ["| " + " | ".join(AGENDA_COLUMNS) + " |",
           "|" + "|".join("---" for _ in AGENDA_COLUMNS) + "|"]
    for n, e in enumerate(entries, 1):
        out.append("| %d | %s | %s | %s | %s | %s | %s |" % (
            n, e.label, e.claim or "-", e.required,
            ", ".join(e.depends_on) if e.depends_on else "-", e.owner or "-",
            e.status or "?"))
    return "\n".join(out)


def write_agenda(agenda):
    """Serialise: head, the regenerated table, tail. Positions are renumbered."""
    for n, e in enumerate(agenda.entries, 1):
        e.position = n
    parts = [agenda.head.rstrip("\n"), "", render_agenda_table(agenda.entries)]
    tail = agenda.tail.strip("\n")
    text = "\n".join(parts) + "\n"
    if tail:
        text += "\n" + tail + "\n"
    return text.lstrip("\n")


AGENDA_HEADER = """# Agenda: {instance}

<!-- academy agenda v1 (author plugin, references/formats.md). Row order is the
precedence: paper order by default. Edit label, claim, required, depends_on and owner
by hand or with /author:agenda; the status column is refreshed by
`agenda.py status` from the registry and is never edited by hand. -->

The paper's results in paper order. `/author:inbox` works on the items that unblock
the earliest entry first. `required` is the status an entry must reach; `status` is
what the registry says now (vocabulary: the academy `status-vocabulary` skill).
"""


def new_agenda_text(instance, entries, milestones=None, preface=""):
    head = AGENDA_HEADER.format(instance=instance)
    if preface:
        head += "\n" + preface.strip("\n") + "\n"
    head += "\n## Milestones\n\n"
    if milestones:
        for name, goals in milestones.items():
            head += "- `%s`: %s\n" % (name, ", ".join("%s=%s" % kv for kv in goals.items()))
    else:
        head += ("None yet. A milestone is a line `- `name`: label=status, ...` (a "
                 "coauthor round, a submission).\n")
    head += "\n## Entries\n"
    return write_agenda(Agenda("Agenda: " + instance, head, entries, ""))


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------

def check(agenda, ns=""):
    """Problems (list of str) with an agenda."""
    probs = []
    labels, claims = {}, {}
    for e in agenda.entries:
        if e.label in labels:
            probs.append("agenda: duplicate label %s" % e.label)
        labels[e.label] = e
        if e.claim not in ("", "-"):
            if e.claim in claims:
                probs.append("agenda: %s and %s share the claim %s (one entry per claim: a "
                             "ticket's agenda names one entry)" % (claims[e.claim], e.label,
                                                                   e.claim))
            claims.setdefault(e.claim, e.label)
        if e.required not in CLAIM_STATUSES:
            probs.append("agenda: %s: required %r is not a status" % (e.label, e.required))
        if e.status and e.status not in ("?",) + CLAIM_STATUSES + ("superseded", "dropped",
                                                                    "missing"):
            probs.append("agenda: %s: status %r is not a status" % (e.label, e.status))
    for e in agenda.entries:
        for d in e.depends_on:
            if local_label(d, ns) not in labels and ":" not in d:
                probs.append("agenda: %s depends on unknown %s" % (e.label, d))
    # cycles in the agenda graph
    graph = {e.label: [local_label(d, ns) for d in e.depends_on
                       if local_label(d, ns) in labels] for e in agenda.entries}
    state = {}

    def visit(n, path):
        state[n] = 1
        for m in graph.get(n, []):
            if state.get(m) == 1:
                probs.append("agenda: dependency cycle %s" % " -> ".join(path + [n, m]))
            elif not state.get(m):
                visit(m, path + [n])
        state[n] = 2

    for n in graph:
        if not state.get(n):
            visit(n, [])
    for name, goals in agenda.milestones.items():
        for lab, st in goals.items():
            if local_label(lab, ns) not in labels:
                probs.append("milestone %s: unknown entry %s" % (name, lab))
            if st not in CLAIM_STATUSES:
                probs.append("milestone %s: %s=%s is not a status" % (name, lab, st))
    return probs
