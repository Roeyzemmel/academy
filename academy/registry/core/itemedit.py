"""The keeper per item (#127): set one item of a structured record, or discharge its
items, and re-derive the record's status from them.

Both profiles' schema-v2 records are written the same way (line-preserving, through
``core.edit.Doc``): the ``items`` map, the derived ``status`` and ``modulo``, evidence
rows for the grounds' review records, and one history row. The record is checked before
and after in its own home (``record_errors``); an edit that adds an error is put back
byte for byte, and a notebook home must still build, as for every notebook mutation.

Grounds for one item are checked against **that item's hash** when they carry
``item_hash`` (the decision table gives it, #127): a pass on the item stands while the
hypotheses and the item's own text are unchanged, whatever happened to the other items.
Grounds without ``item_hash`` (a whole-statement pass, the human's word) are checked as
for the whole record, against its current statement hash.
"""
from __future__ import annotations

import datetime
from pathlib import Path

from . import discharge as _dis
from . import federation, schema, structure
from . import grounds as _grounds
from .edit import Doc
from .fm import format_scalar_single

#: statuses an item may take (a lifecycle move is the record's, not an item's)
ITEM_STATUSES = schema.STATUSES


class Refused(ValueError):
    """An item mutation refused, with the reason."""


def today():
    return datetime.date.today().isoformat()


def locate(qid, repo):
    """``(store, record)`` of ``qid`` seen from ``repo``; Refused when it does not resolve
    or is not a schema-v2 structured record. Read fresh: a mutation never acts on a
    cached view of the files."""
    federation.CACHE.clear()
    state, rec, detail = federation.resolve(qid, Path(repo))
    if rec is None:
        raise Refused("%s does not resolve (%s%s)" % (qid, state, ": " + detail if detail else ""))
    st = federation.store_from(rec.ns, Path(repo))
    fields = _v2_fields(st, rec)
    if fields is None:
        raise Refused("%s is a schema-v1 record: it carries no items" % rec.qid)
    if not structure.has_structure(fields) or "items" not in fields:
        raise Refused("%s has no `items` (registry.py structure %s proposes them)"
                      % (rec.qid, rec.qid))
    return st, rec


def _v2_fields(st, rec):
    kb = getattr(st, "kb", None)
    if kb is not None:
        e = kb.entities.get(rec.id)
        return e.v2 if e is not None else None
    return rec.fields if schema.is_v2(rec.fields) else None


def record_errors(st, rec):
    """The check errors of one record, read from disk, in its own home."""
    home = Path(st.home)
    federation.CACHE.clear()
    if getattr(st, "kb", None) is not None:
        from ..profiles import s1kb
        kb = s1kb.load_kb(home)
        s1kb.run_check(kb)
        rel = Path(rec.file).resolve().relative_to(home.resolve()).as_posix()
        return [e for e in kb.errors if e.startswith(rel + ":")]
    from ..profiles import fsl
    errs, _w = fsl._check_one(Path(rec.file), home, fsl.registry_root(home))
    return errs


def _resolver(home):
    from ..profiles import fsl
    return lambda ref: fsl.resolve_ref(ref, Path(home))


def check_item_grounds(st, rec, key, status, grounds, human=False):
    """``(ok, reasons)``: whether ``grounds`` carry item ``key`` of ``rec`` to ``status``."""
    s = st.structure(rec.id)
    g = grounds or {}
    if status not in ITEM_STATUSES:
        return False, ["an item takes a status (%s), not %r" % (", ".join(ITEM_STATUSES),
                                                                  status)]
    if g.get("item") not in (None, "", key):
        return False, ["the grounds are for item %s, not %s" % (g.get("item"), key)]
    ih = str(g.get("item_hash") or "").strip()
    if ih:
        now = s["hashes"].get(key)
        if ih != now:
            return False, ["the grounds' item_hash %s is not item %s's current %s (the item "
                           "or a hypothesis changed after the review: re-verify it)"
                           % (ih, key, now)]
        ok, why = _grounds.check_grounds(status, g, None, human=human)
    else:
        ok, why = _grounds.check_grounds(status, g, st.statement_hash(rec.id), human=human)
    if not ok:
        return ok, why
    refs = _grounds.check_verdict_refs(g, _resolver(st.home), rec.qid,
                                       supersedes=rec.fields.get("supersedes"))
    return (not refs), (refs or why)


def _write(st, rec, items, rows, history_note, date):
    """Write ``items`` (``{key: [status, modulo...]}``), the derived status and modulo,
    the evidence ``rows`` and one history row; refuse (file unchanged) on a new check
    error. Returns the derived ``(status, modulo)``."""
    path = Path(rec.file)
    parsed = {k: (v[0], list(v[1:])) for k, v in items.items()}
    dst, dmod = structure.derive(parsed)
    if dst is None:
        raise Refused("the items do not derive a status: %s" % items)
    before = path.read_bytes()
    old_errs = record_errors(st, rec)
    order = _order(st)
    doc = Doc(path, format_scalar_single)
    doc.set_map("items", items, after=order[:order.index("evidence")])
    doc.set_scalar("status", dst, after=("form", "kind", "title"))
    if dst == "proved-modulo":
        doc.set_list("modulo", dmod, after=order[:order.index("modulo")])
    else:
        doc.remove("modulo")
    held = doc.list_items("evidence") or []
    for r in rows:
        if r not in held:
            doc.add_item("evidence", r, after=order[:order.index("evidence")])
            held.append(r)
    doc.add_item("history", schema.history_row(date or today(), dst, history_note),
                 first=True, after=("evidence",))
    doc.save()
    federation.CACHE.clear()
    added = [e for e in record_errors(st, rec) if e not in old_errs]
    if not added and getattr(st, "kb", None) is not None:
        from ..profiles import s1kb
        built = s1kb.load_kb(Path(st.home))
        if s1kb.do_build(built, quiet=True):
            added = built.errors[:1] or ["the notebook does not build"]
    if added:
        path.write_bytes(before)
        federation.CACHE.clear()
        raise Refused("the edit would leave the record inconsistent:\n" + "\n".join(added))
    federation.CACHE.clear()
    return dst, dmod


def _order(st):
    if getattr(st, "kb", None) is not None:
        from ..profiles import s1kb
        return list(s1kb.V2_ORDER)
    from ..profiles import fsl
    return list(fsl.V2_ORDER)


def _items_now(st, rec):
    return {k: structure.item_value(v[0], v[1])
            for k, v in st.structure(rec.id)["items"].items()}


def set_item(qid, repo, key, status, grounds=None, note=None, human=False, date=None):
    """Set item ``key`` of structured record ``qid`` to ``status`` on ``grounds`` (a
    discharge, basis ``discharge``: the item's own modulo inputs, assessed here). The
    record's status and modulo are re-derived. Returns ``{"id", "item", "old", "new",
    "record_old", "record", "modulo"}``; raises Refused."""
    st, rec = locate(qid, repo)
    s = st.structure(rec.id)
    if key not in s["items"]:
        raise Refused("%s has no item %s (its items: %s)"
                      % (rec.qid, key, ", ".join(s["items"])))
    g = dict(grounds or {})
    old = s["items"][key][0]
    rows = []
    if g.get("basis") == "discharge":
        a = assess_item(st, rec, key)
        if not a["dischargeable"]:
            raise Refused("%s item %s cannot be discharged:\n- %s"
                          % (rec.qid, key, "\n- ".join(a["problems"])))
        if status != "proved":
            raise Refused("a discharge carries an item to proved only, not %r" % status)
        modulo = []
        rows.append(_item_row(_dis.evidence_row(a), key))
        why = "item %s %s; %s" % (key, "proved", _dis.history_note(a))
    else:
        ok, why_l = check_item_grounds(st, rec, key, status, g, human=human)
        if not ok:
            raise Refused("the grounds do not support %s item %s -> %s:\n- %s"
                          % (rec.qid, key, status, "\n- ".join(why_l)))
        modulo = [str(m) for m in g.get("modulo") or []] if status == "proved-modulo" else []
        from ..profiles import fsl
        held = (_v2_fields(st, rec) or {}).get("evidence") or []
        rows = fsl._verdict_rows(g, [str(r) for r in held])
        rows = [_item_row(r, key) for r in rows]
        basis = _grounds.summary(g, fsl._human_name()) if g else ""
        why = "; ".join(x for x in ("item %s %s -> %s" % (key, old, status),
                                    (note or "").strip(), basis) if x)
    items = _items_now(st, rec)
    items[key] = structure.item_value(status, modulo)
    rold = rec.status
    dst, dmod = _write(st, rec, items, rows, why.replace("|", "/"), date)
    return {"id": rec.qid, "item": key, "old": old, "new": status, "record_old": rold,
            "record": dst, "modulo": dmod}


def set_all(st, rec, status, modulo=()):
    """The ``items`` map with every item at ``status`` (a whole-record status change on a
    structured record: a pass on the whole statement covers each item)."""
    items = _items_now(st, rec)
    return {k: structure.item_value(status, modulo if status == "proved-modulo" else ())
            for k in items}


def _item_row(row, key):
    """An evidence row with ``item <key>`` in its note."""
    cells = list(schema.evidence_cells(row))
    cells[4] = "; ".join(x for x in ("item %s" % key, cells[4]) if x)
    return schema.evidence_row(*cells)


# --------------------------------------------------------------------------- discharge

def assess_item(st, rec, key):
    """Whether item ``key`` (proved-modulo) is dischargeable: every input of its own
    modulo established (``core.discharge.resolve_input``)."""
    s = st.structure(rec.id)
    ist, mod = s["items"][key]
    out = {"id": rec.qid, "item": key, "status": ist, "modulo": list(mod), "inputs": [],
           "dischargeable": False, "problems": []}
    if ist != "proved-modulo":
        out["problems"].append("item %s is %s, not proved-modulo" % (key, ist))
        return out
    out["inputs"] = [_dis.resolve_input(m, rec.ns, st.home) for m in mod]
    ok, why = _grounds.check_grounds("proved", _dis.grounds(out))
    out["dischargeable"] = ok
    if not ok:
        out["problems"] = why
    return out


def assess(qid, repo):
    """``{key: assess_item}`` for every proved-modulo item of a structured record."""
    st, rec = locate(qid, repo)
    s = st.structure(rec.id)
    return {k: assess_item(st, rec, k) for k, (ist, _m) in s["items"].items()
            if ist == "proved-modulo"}


def discharge(qid, repo, date=None):
    """Discharge every dischargeable item of ``qid`` (each to proved, one ``discharge``
    evidence row per item), then re-derive the record. Returns the per-item assessments;
    raises Refused when no item is dischargeable."""
    st, rec = locate(qid, repo)
    per = assess(qid, repo)
    ready = {k: a for k, a in per.items() if a["dischargeable"]}
    if not ready:
        probs = ["item %s: %s" % (k, "; ".join(a["problems"])) for k, a in per.items()] \
            or ["no item is proved-modulo"]
        raise Refused("%s: no item can be discharged:\n- %s" % (rec.qid, "\n- ".join(probs)))
    items = _items_now(st, rec)
    rows = []
    for k, a in ready.items():
        items[k] = ["proved"]
        rows.append(_item_row(_dis.evidence_row(a), k))
    note = "; ".join("item %s %s" % (k, _dis.history_note(a)) for k, a in ready.items())
    _write(st, rec, items, rows, note.replace("|", "/"), date)
    return per
