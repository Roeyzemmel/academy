"""The academy object schema: schema v2 of every registry (plan section 6, "One schema").

One frontmatter schema for every namespace (``s1:``, ``paper:``, ``lab:`` and future
instances), the same as the Researcher notebook's object template
(``researcher/templates/notebook/_templates/object.md``)::

    id, kind, form, title, status, statement, modulo, depends_on, bears_on, supersedes,
    lifecycle, aliases, domain, tags, proof, where, evidence, history

* ``kind`` is the statement type: definition, claim, conjecture, question, example,
  assumption, direction. ``form`` (optional) keeps the home's finer label where the id
  does not already carry it (a notebook's prop / lemma / remark / draft ...).
* ``status`` is one vocabulary: open, conjectured, sketch, supported, proved-modulo,
  proved, refuted, refuted-as-stated. It belongs to claims, conjectures and questions;
  a profile may allow it on other kinds (the paper's colour rule gives every
  environment a status). A claim with ``form: remark`` may carry none.
* ``modulo`` lists the missing inputs (ids, or plain text where no record carries the
  input): it replaces both lab/paper's ``open:`` and a v1 notebook's reduction text.
* ``supersedes`` is one-way; ``superseded_by`` is derived.
* ``lifecycle``: active, superseded, dropped (a lifecycle, no longer a status). A record
  that is not active projects to ``n/a`` whatever its status.
* ``evidence`` rows: ``type | ref | verdict | run_id | note`` (``-`` for an empty cell).
* ``history`` rows: ``YYYY-MM-DD | status | note``, newest first; the status cell is a
  status, a lifecycle word, or empty (an event that changed neither). The newest row
  with a non-empty cell agrees with the record's state.

A record is schema v2 exactly when it has a ``lifecycle`` field (required in v2, absent
from both v1 schemas), so a home can be read while it is being migrated and the v1
test fixtures keep working.
"""
from __future__ import annotations

import re

from . import projection

KINDS = ("definition", "claim", "conjecture", "question", "example", "assumption",
         "direction")
STATUS_KINDS = ("claim", "conjecture", "question")
STATUSES = ("open", "conjectured", "sketch", "supported", "proved-modulo", "proved",
            "refuted", "refuted-as-stated")
LIFECYCLES = ("active", "superseded", "dropped")
UNSETTLED = ("open", "conjectured", "sketch", "supported")
#: statuses a remark-form claim may omit (it states, it does not assert a result)
STATUSLESS_FORMS = ("remark",)
EVIDENCE_TYPES = ("experiment", "audit", "verdict", "hand", "citation", "note")

FIELD_ORDER = ("id", "kind", "form", "title", "status", "statement", "modulo",
               "depends_on", "bears_on", "supersedes", "lifecycle", "aliases", "domain",
               "tags", "proof", "where", "evidence", "history")
LIST_FIELDS = ("modulo", "depends_on", "bears_on", "supersedes", "aliases", "tags",
               "evidence", "history")
SCALAR_FIELDS = ("id", "kind", "form", "title", "status", "statement", "lifecycle",
                 "domain", "proof", "where")
REQUIRED = ("id", "kind", "title", "lifecycle", "evidence", "history")
#: the lists written one item per line (rows and long free text)
BLOCK_FIELDS = ("modulo", "evidence", "history")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NONE = ("", "-")


def is_v2(fields) -> bool:
    return isinstance(fields, dict) and "lifecycle" in fields


def split_row(item, n):
    parts = [p.strip() for p in str(item).split("|", n - 1)]
    return parts + [""] * (n - len(parts))


def evidence_cells(row):
    """``(type, ref, verdict, run_id, note)`` of a v2 evidence row."""
    return tuple(split_row(row, 5))


def history_cells(row):
    """``(date, status, note)`` of a history row."""
    return tuple(split_row(row, 3))


def cell(v):
    v = str(v or "").strip()
    return v if v else "-"


def evidence_row(type_, ref, verdict="", run_id="", note=""):
    cells = [str(type_ or "").strip(), str(ref or "").strip(), cell(verdict), cell(run_id),
             str(note or "").strip()]
    for c in cells[:4]:
        if "|" in c:
            raise ValueError("an evidence cell may not contain '|': %r" % c)
    return " | ".join(cells).rstrip()


def history_row(date, status, note):
    note = str(note or "").replace("|", "/").strip()
    return f"{date} | {status} | {note}" if status else f"{date} | | {note}"


def state(fields):
    """What the record is now: its lifecycle when not active, else its status ('')."""
    lc = fields.get("lifecycle") or "active"
    if lc != "active":
        return lc
    st = fields.get("status")
    return st if isinstance(st, str) else ""


def project(fields):
    """The projection class of a v2 record: n/a when not active, else by status."""
    if (fields.get("lifecycle") or "active") != "active":
        return projection.NA
    st = fields.get("status")
    return projection.project(st if isinstance(st, str) else "", projection.V2)


def looks_like_id(item, id_re=None):
    """Whether a ``modulo`` item is an id (checked) rather than a plain-text input."""
    s = str(item).strip()
    if " " in s or not s:
        return False
    if re.match(r"^[a-z0-9]+:[^\s:][^\s]*$", s):
        return True
    return bool(id_re and id_re.match(s))


def check_record(fields, *, extra_fields=(), status_kinds=STATUS_KINDS,
                 evidence_types=EVIDENCE_TYPES):
    """The generic rules of the schema, as ``[(level, message)]`` with level ``error``
    or ``warn``. A profile adds its own home-specific rules (and fields: ``extra_fields``
    are accepted besides the core ones; ``status_kinds`` are the kinds that may carry a
    status, the core's three unless the profile widens it)."""
    out = []
    err = lambda m: out.append(("error", m))  # noqa: E731
    for k in REQUIRED:
        if k not in fields:
            err(f"missing field '{k}'")
    unknown = sorted(set(fields) - set(FIELD_ORDER) - set(extra_fields))
    if unknown:
        err("unknown field(s): " + ", ".join(unknown))
    for k in LIST_FIELDS:
        if k in fields and not isinstance(fields[k], list):
            err(f"'{k}' must be a list")
    for k in SCALAR_FIELDS:
        if k in fields and not isinstance(fields[k], str):
            err(f"'{k}' must be a scalar")
    kind = fields.get("kind")
    if kind is not None and kind not in KINDS:
        err(f"kind '{kind}' is not one of: " + ", ".join(KINDS))
    lc = fields.get("lifecycle")
    if lc is not None and lc not in LIFECYCLES:
        err(f"lifecycle '{lc}' is not one of: " + ", ".join(LIFECYCLES))
    st = fields.get("status")
    if st is not None and st != "":
        if st not in STATUSES:
            err(f"status '{st}' is not one of: " + ", ".join(STATUSES))
        if kind in KINDS and kind not in status_kinds:
            err(f"a {kind} carries no status")
    elif kind in STATUS_KINDS and kind in status_kinds \
            and fields.get("form") not in STATUSLESS_FORMS:
        err(f"a {kind} needs a status")
    elif kind in status_kinds and kind not in STATUS_KINDS:
        err(f"a {kind} needs a status in this registry")
    modulo = fields.get("modulo") if isinstance(fields.get("modulo"), list) else []
    if st == "proved-modulo" and not modulo:
        err("proved-modulo needs `modulo` (the missing inputs)")
    if st == "proved" and modulo:
        err("proved with `modulo` inputs is proved-modulo")
    ev = fields.get("evidence") if isinstance(fields.get("evidence"), list) else []
    for row in ev:
        t, ref, verdict, run, note = evidence_cells(row)
        if str(row).count("|") < 4:
            err(f"evidence row `{row}` is not `type | ref | verdict | run_id | note`")
            continue
        if t not in evidence_types:
            err(f"evidence type `{t}` is not one of: " + ", ".join(evidence_types))
        if not ref:
            err(f"evidence `{row}` has no ref")
    hist = fields.get("history") if isinstance(fields.get("history"), list) else []
    dates = []
    for h in hist:
        d, s, _ = history_cells(h)
        if not DATE_RE.match(d):
            err(f"history line `{h}` does not start with YYYY-MM-DD |")
        else:
            dates.append(d)
        if s and s not in STATUSES and s not in LIFECYCLES:
            err(f"history status `{s}` is not in the vocabulary")
    if dates != sorted(dates, reverse=True):
        err("history is not newest first")
    now = state(fields)
    head = next((history_cells(h)[1] for h in hist if history_cells(h)[1]), None)
    if now and head is not None and head != now:
        err(f"latest history status `{head}` != {'lifecycle' if now in LIFECYCLES else 'status'} `{now}`")
    if now and head is None and hist:
        out.append(("warn", f"no history row records the {'lifecycle' if now in LIFECYCLES else 'status'} `{now}`"))
    return out


def derived_superseded_by(records):
    """{id: [ids that supersede it]} from the one-way ``supersedes`` of ``records``
    (an iterable of ``(id, fields)``)."""
    out = {}
    for rid, f in records:
        sup = f.get("supersedes")
        for t in (sup if isinstance(sup, list) else ([sup] if sup else [])):
            out.setdefault(t, []).append(rid)
    return out
