"""agenda_lib -- the Author's agenda (Drafts/agenda.md) and roadmap (Drafts/roadmap.md).

Plan section 4. Both files are plain Markdown that Roey reads and edits; this module
is their one parser and writer. Formats (also in references/formats.md):

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

roadmap.md
----------
One work item per ``## R-NNNN [tag] title`` heading, then its fields as
``- key: value`` lines, then free Markdown::

    ## R-0007 [apply] Delete the stale note after lem:thick-part-compact
    - status: open
    - agenda: paper:lem:thick-part-compact
    - priority: normal
    - depends_on: [R-0003, T-0012]

    Free text (what to do, quotes, history).

Other ``##`` headings (sections of prose) are kept verbatim between items.
"""

import os
import re

STATUS_RANK = {"open": 0, "conjectured": 1, "sketch": 2, "supported": 2,
               "proved-modulo": 3, "proved": 4}
FALSE_STATUSES = ("refuted", "refuted-as-stated")
CLAIM_STATUSES = ("open", "conjectured", "sketch", "supported", "proved-modulo", "proved",
                  "refuted", "refuted-as-stated")

TAGS = ("write", "apply", "lead", "verify", "cite", "experiment", "figure", "build",
        "notation", "sweep", "referee")
ITEM_STATUSES = ("open", "ticketed", "blocked", "needs-human", "done", "dropped")
PRIORITIES = ("high", "normal", "low")
PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}
ITEM_FIELD_ORDER = ("status", "agenda", "priority", "depends_on", "ticket", "route",
                    "source", "created", "updated")
AGENDA_COLUMNS = ("#", "label", "claim", "required", "depends_on", "owner", "status")

RE_ITEM_HEAD = re.compile(r"^## (R-\d{4,}) \[([a-z][a-z-]*)\] ?(.*)$")
RE_FIELD = re.compile(r"^- ([a-z_]+):(?: (.*))?$")
RE_ITEM_ID = re.compile(r"^R-(\d{4,})$")
RE_TICKET_ID = re.compile(r"^T-\d{4,}$")
RE_MILESTONE = re.compile(r"^- `?([A-Za-z0-9][A-Za-z0-9_.-]*)`?:\s*(.*)$")


class AgendaError(Exception):
    """A malformed agenda or roadmap."""


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

The paper's results in paper order. `/author:next` works on the items that unblock
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
# Roadmap
# ----------------------------------------------------------------------------

class Item(object):
    """One roadmap work item."""

    def __init__(self, id, tag, title, fields=None, body=""):
        self.id = id
        self.tag = tag
        self.title = title
        self.fields = dict(fields or {})
        self.body = body

    @property
    def status(self):
        return (self.fields.get("status") or "open").strip()

    @property
    def agenda(self):
        return (self.fields.get("agenda") or "").strip().strip("`")

    @property
    def priority(self):
        p = (self.fields.get("priority") or "normal").strip()
        return p if p in PRIORITIES else "normal"

    @property
    def depends_on(self):
        return split_list(self.fields.get("depends_on", ""))

    @property
    def ticket(self):
        return (self.fields.get("ticket") or "").strip()

    @property
    def number(self):
        return int(RE_ITEM_ID.match(self.id).group(1))

    def as_dict(self):
        return {"id": self.id, "tag": self.tag, "title": self.title, "status": self.status,
                "agenda": self.agenda, "priority": self.priority,
                "depends_on": self.depends_on, "ticket": self.ticket,
                "route": (self.fields.get("route") or "").strip(),
                "source": (self.fields.get("source") or "").strip()}


class Roadmap(object):
    """``preamble`` text, then ``blocks``: Items and raw text blocks (str)."""

    def __init__(self, preamble="", blocks=None):
        self.preamble = preamble
        self.blocks = list(blocks or [])

    @property
    def items(self):
        return [b for b in self.blocks if isinstance(b, Item)]

    def get(self, iid):
        for it in self.items:
            if it.id == iid:
                return it
        return None

    def next_id(self):
        nums = [it.number for it in self.items]
        return "R-%04d" % ((max(nums) if nums else 0) + 1)


def parse_roadmap(text):
    lines = text.replace("\r\n", "\n").split("\n")
    pre, blocks = [], []
    i = 0
    while i < len(lines) and not lines[i].startswith("## "):
        pre.append(lines[i])
        i += 1
    seen = set()
    while i < len(lines):
        head = lines[i]
        j = i + 1
        while j < len(lines) and not lines[j].startswith("## "):
            j += 1
        chunk = lines[i + 1:j]
        m = RE_ITEM_HEAD.match(head)
        if not m:
            blocks.append("\n".join([head] + chunk))
            i = j
            continue
        iid, tag, title = m.group(1), m.group(2), m.group(3).strip()
        if iid in seen:
            raise AgendaError("duplicate roadmap item %s" % iid)
        seen.add(iid)
        fields, k = {}, 0
        while k < len(chunk) and not chunk[k].strip():
            k += 1
        while k < len(chunk):
            fm = RE_FIELD.match(chunk[k])
            if not fm:
                break
            fields[fm.group(1)] = (fm.group(2) or "").strip()
            k += 1
        body = "\n".join(chunk[k:]).strip("\n")
        blocks.append(Item(iid, tag, title, fields, body))
        i = j
    return Roadmap("\n".join(pre), blocks)


def render_item(it):
    out = ["## %s [%s] %s" % (it.id, it.tag, it.title)]
    keys = [k for k in ITEM_FIELD_ORDER if k in it.fields]
    keys += [k for k in it.fields if k not in ITEM_FIELD_ORDER]
    for k in keys:
        v = it.fields[k]
        out.append("- %s:%s" % (k, (" " + v) if v not in (None, "") else ""))
    text = "\n".join(out) + "\n"
    if it.body.strip():
        text += "\n" + it.body.strip("\n") + "\n"
    return text


def write_roadmap(rm):
    parts = [rm.preamble.rstrip("\n") + "\n"] if rm.preamble.strip() else []
    for b in rm.blocks:
        if isinstance(b, Item):
            parts.append(render_item(b))
        else:
            parts.append(b.strip("\n") + "\n")
    return "\n".join(parts)


ROADMAP_HEADER = """# Roadmap: {instance}

<!-- academy roadmap v1 (author plugin, references/formats.md). One work item per
`## R-NNNN [tag] title` heading, then `- key: value` fields, then free text.
Tags: write apply lead verify cite experiment figure build notation sweep referee.
Status: open ticketed blocked needs-human done dropped. `/author:next` picks from
here and from the board; `/author:notes` and `/author:agenda` file new items. -->

The Author's own work items. Items needing another role (a proof, a verification, a
citation, an experiment) become board tickets when `/author:next` reaches them; the
item then waits in `ticketed` until the ticket is delivered.
"""


def new_roadmap_text(instance, items, preface=""):
    pre = ROADMAP_HEADER.format(instance=instance)
    if preface:
        pre += "\n" + preface.strip("\n") + "\n"
    return write_roadmap(Roadmap(pre, items))


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------

def check(agenda, roadmap, ns=""):
    """Problems (list of str) with an agenda and a roadmap taken together."""
    probs = []
    labels = {}
    for e in agenda.entries:
        if e.label in labels:
            probs.append("agenda: duplicate label %s" % e.label)
        labels[e.label] = e
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
    ids = {it.id for it in roadmap.items}
    for it in roadmap.items:
        if it.tag not in TAGS:
            probs.append("roadmap: %s: unknown tag [%s]" % (it.id, it.tag))
        if it.status not in ITEM_STATUSES:
            probs.append("roadmap: %s: unknown status %r" % (it.id, it.status))
        if it.fields.get("priority") and it.priority != it.fields["priority"].strip():
            probs.append("roadmap: %s: priority must be high, normal or low" % it.id)
        if it.agenda and it.agenda != "global" and agenda.lookup(it.agenda, ns) is None:
            probs.append("roadmap: %s: agenda entry %s is not in the agenda"
                         % (it.id, it.agenda))
        for d in it.depends_on:
            if RE_ITEM_ID.match(d):
                if d not in ids:
                    probs.append("roadmap: %s depends on unknown item %s" % (it.id, d))
            elif not RE_TICKET_ID.match(d) and agenda.lookup(d, ns) is None and ":" not in d:
                probs.append("roadmap: %s depends on unknown %s" % (it.id, d))
        if it.status == "ticketed" and not RE_TICKET_ID.match(it.ticket or ""):
            probs.append("roadmap: %s is ticketed but names no ticket" % it.id)
    return probs
