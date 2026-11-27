"""Discharge (#127, the human's ruling of 2026-11-27: "mechanical"): a ``proved-modulo``
record becomes ``proved`` once every input in its ``modulo`` list is established.

An input is established when it

* resolves (through the federation, aliases included; a bare id is read in the record's
  own namespace) to a record whose status is ``proved`` -- not ``proved-modulo``: a chain
  discharges bottom-up -- or to a definition tagged ``notation-only`` (the decision
  table drops such a definition from a verdict's modulo, #103); or
* is a card pinpoint ``bib:KEY#PIN`` whose card in the Expert's library (``cards/KEY/``,
  the card at that pinpoint) has verdict ``match``: a verified citation card, what the
  decision table counts as established for a ``bib:`` input.

Anything else holds the record and is reported: free text (it names no record, so it
cannot be followed), an id that does not resolve or whose home is not beside this repo,
an input that is itself proved-modulo or less, a ``bib:`` item without a pinpoint or
without a matching card.

The change itself is written by the record's profile (``fsl.set_status`` with grounds of
basis ``discharge``; ``s1kb.discharge``), which assesses the record again here rather
than trust the caller: the status goes to ``proved``, ``modulo`` is removed, one evidence
row ``discharge | <inputs> | proved | - | <each input and its status>`` and one history
row ``YYYY-MM-DD | proved | discharged: inputs X, Y proved`` are added. The two CONFIRMED
reviews that carried ``proved-modulo`` stay on the record as its evidence and are not
re-read: the discharge adds only the inputs. ``core.grounds.check_grounds`` is the gate
(basis ``discharge``, or proof grounds carrying a ``discharge`` list).
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

from . import federation, schema, workspace
from . import grounds as _grounds

#: the card verdict that makes a ``bib:`` input established
CARD_MATCH = "match"


def _norm_pin(s):
    """A pinpoint compared by its letters and digits only: ``Theorem 3.6``,
    ``theorem-3-6`` and ``Thm. 3.6`` differ, ``Theorem 3.6`` and ``theorem-3-6`` do not."""
    return re.sub(r"[^0-9a-z]", "", str(s or "").lower())


def library_cards(repo):
    """The Expert library's ``cards/`` folder as seen from ``repo``, or None."""
    names = sorted(workspace.instances_of_role("expert"))
    for inst in names:
        home = workspace.instance_home(inst, repo)
        if home is None:
            continue
        rel = (((workspace.read_config(home) or {}).get("paths") or {}).get("cards")
               or "cards")
        if isinstance(rel, list):
            rel = rel[0]
        root = Path(home) / rel
        if root.is_dir():
            return root
    return None


def _card_meta(path):
    """The flat ``key: value`` lines of a card's frontmatter ({} when unreadable)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    return _grounds.record_fields(text)


def card_state(item, repo):
    """``(established, detail)`` of a ``bib:KEY#PIN`` input."""
    key, _, pin = item[len("bib:"):].partition("#")
    key, pin = key.strip(), pin.strip()
    if not pin:
        return False, "no pinpoint: a citation counts at the pinpoint of its card"
    cards = library_cards(repo)
    if cards is None:
        return False, "no Expert library beside this repo: the card cannot be read"
    d = cards / key
    if not d.is_dir():
        return False, "the library has no card of %s" % key
    want, found = _norm_pin(pin), []
    for p in sorted(d.glob("*.md")):
        if p.name.startswith("_"):
            continue
        meta = _card_meta(p)
        if _norm_pin(p.stem) == want or _norm_pin(meta.get("pinpoint")) == want:
            found.append((p, str(meta.get("verdict") or "").strip().lower()))
    if not found:
        return False, "no card of %s at %s" % (key, pin)
    for p, v in found:
        if v == CARD_MATCH:
            return True, "card %s/%s, %s" % (key, p.name, CARD_MATCH)
    return False, "the card of %s at %s says %s (only %s counts)" % (
        key, pin, ", ".join(sorted(set(v or "no verdict" for _, v in found))), CARD_MATCH)


def _head(s):
    """``(id, pointer text)`` of an item ``id`` / ``id#pin`` / ``id (pointer)``, or
    ``(None, "")`` for free text."""
    m = re.match(r"^(\S+?)\s*\((.*)\)\s*$", s)
    head, pointer = (m.group(1), m.group(2)) if m else (s, "")
    head = head.split("#", 1)[0]
    if not head or re.search(r"\s", head) or not schema.looks_like_id(head) and \
            not re.match(r"^[A-Za-z][\w′'.-]*$", head):
        return None, ""
    return head, pointer


def resolve_input(item, own_ns, repo):
    """One modulo input: ``{"input", "id", "status", "established", "why"}``."""
    s = " ".join(str(item or "").split()).strip("`'\"")
    out = {"input": str(item), "id": None, "status": None, "established": False, "why": ""}
    if not s:
        out["why"] = "an empty item"
        return out
    if s.startswith("bib:"):
        ok, why = card_state(s, repo)
        out.update(id=s, status="cited" if ok else None, established=ok, why=why)
        return out
    head, _pointer = _head(s)
    if head is None:
        out["why"] = ("free text: it names no record, so it cannot be followed (write it "
                      "as an id or bib:KEY#PIN)")
        return out
    spaces = workspace.namespaces()
    ns = head.split(":", 1)[0] if ":" in head else None
    qid = head if ns in spaces else "%s:%s" % (own_ns, head)
    state, rec, detail = federation.resolve(qid, repo)
    if rec is None:
        out["why"] = ("%s does not resolve (%s%s)"
                      % (qid, state, ": " + detail if detail else ""))
        return out
    out["id"] = rec.qid
    st = rec.status or ""
    out["status"] = st or None
    tags = rec.fields.get("tags") if isinstance(rec.fields.get("tags"), list) else []
    kind = str(rec.fields.get("kind") or rec.type or "")
    if st == "proved":
        out["established"] = True
    elif kind in ("definition", "def", "defn") and "notation-only" in tags:
        out.update(status="notation-only", established=True)
    elif st == "proved-modulo":
        out["why"] = "%s is proved-modulo (a chain discharges bottom-up)" % rec.qid
    else:
        out["why"] = "%s is %s" % (rec.qid, st or "without a status")
    return out


def modulo_of(store, rid):
    """The record's ``modulo`` list ([] when none), or None for a schema-v1 record."""
    kb = getattr(store, "kb", None)
    if kb is not None:                    # the notebook profile: its file as written
        e = kb.entities.get(rid)
        v2 = e.v2 if e is not None else None
        if v2 is None:
            return None
        m = v2.get("modulo")
    else:
        f = store.records[rid].fields
        if not schema.is_v2(f):
            return None
        m = f.get("modulo")
    return [str(x) for x in m] if isinstance(m, list) else []


def assess(qid, repo):
    """Whether record ``qid`` (seen from ``repo``) is dischargeable now::

        {"id", "status", "modulo", "inputs": [resolve_input ...], "dischargeable",
         "problems": [why not]}
    """
    out = {"id": qid, "status": None, "modulo": [], "inputs": [], "dischargeable": False,
           "problems": []}
    state, rec, detail = federation.resolve(qid, repo)
    if rec is None:
        out["problems"].append("%s does not resolve (%s%s)"
                               % (qid, state, ": " + detail if detail else ""))
        return out
    out["id"], out["status"] = rec.qid, rec.status
    if rec.status != "proved-modulo":
        out["problems"].append("status %s, not proved-modulo" % (rec.status or "none"))
        return out
    store = federation.store_from(rec.ns, repo)
    modulo = modulo_of(store, rec.id)
    if modulo is None:
        out["problems"].append("a schema-v1 record keeps no modulo list to follow")
        return out
    out["modulo"] = modulo
    home = store.home
    out["inputs"] = [resolve_input(m, rec.ns, home) for m in modulo]
    ok, why = _grounds.check_grounds("proved", grounds(out))
    out["dischargeable"] = ok
    if not ok:
        out["problems"] = why
    return out


def grounds(a):
    """The discharge grounds of an assessment (what ``check_grounds`` reads)."""
    return {"basis": "discharge", "modulo": list(a.get("modulo") or []),
            "inputs": [dict(i) for i in a.get("inputs") or []],
            "note": history_note(a)}


def _said(i):
    return "%s %s" % (i.get("id") or i["input"], i.get("status") or "open")


def history_note(a):
    """``discharged: inputs X, Y proved`` (statuses named where not ``proved``)."""
    ins = a.get("inputs") or []
    if ins and all(i.get("status") == "proved" for i in ins):
        return "discharged: inputs %s proved" % ", ".join(i.get("id") or i["input"]
                                                          for i in ins)
    return "discharged: inputs %s" % ", ".join(_said(i) for i in ins)


def evidence_row(a):
    """The one evidence row a discharge adds (schema v2)."""
    ins = a.get("inputs") or []
    ref = ", ".join(str(i.get("id") or i["input"]).replace("|", "/") for i in ins)
    note = "; ".join("%s: %s%s" % (i["input"], i.get("status"),
                                   (" (%s)" % i["why"]) if i.get("why") else "")
                     for i in ins)
    return schema.evidence_row("discharge", ref, "proved", "",
                               ("inputs established: " + note).replace("|", "/"))


def explain(i):
    """One input as a report line."""
    if i.get("established"):
        extra = (" (%s)" % i["why"]) if i.get("why") else ""
        return "%s %s%s" % (i.get("id") or i["input"], i.get("status"), extra)
    return "%s: %s" % (i["input"], i.get("why") or "not established")


def candidates(repo, ids=(), namespaces=(), inputs=()):
    """The qualified ids to assess: ``ids`` (bare ones in this repo's namespace), every
    proved-modulo record of ``namespaces``, and every proved-modulo record of any
    reachable namespace whose ``modulo`` names one of ``inputs``."""
    own = workspace.repo_ns(repo)
    out = []
    for i in ids:
        q = i if federation.split(i)[0] in workspace.namespaces() else "%s:%s" % (own, i)
        if q not in out:
            out.append(q)
    for ns in namespaces:
        st = federation.store_from(ns, repo)
        for rid in sorted(st.records) if st is not None else ():
            if st.records[rid].status == "proved-modulo" and \
                    st.records[rid].qid not in out:
                out.append(st.records[rid].qid)
    if inputs:
        want = set()
        for q in inputs:
            r = resolve_input(q, own, repo)
            want.add(r["id"] or q)
        for ns, st in sorted(federation.reachable(repo).items()):
            for rid in sorted(st.records):
                rec = st.records[rid]
                if rec.status != "proved-modulo" or rec.qid in out:
                    continue
                for m in modulo_of(st, rid) or []:
                    if resolve_input(m, ns, st.home)["id"] in want:
                        out.append(rec.qid)
                        break
    return out


def apply(qid, repo, date=None):
    """Discharge ``qid`` through its profile; returns the assessment it rested on.
    Raises ``ValueError`` with the reasons when the record is not dischargeable or its
    profile refuses the edit."""
    a = assess(qid, repo)
    if not a["dischargeable"]:
        raise ValueError("%s is not dischargeable:\n- %s" % (qid, "\n- ".join(a["problems"])))
    ns, rid = federation.split(a["id"])
    store = federation.store_from(ns, repo)
    home = Path(store.home)
    date = date or datetime.date.today().isoformat()
    from ..profiles import s1kb, fsl      # late: the profiles import the core
    try:
        if getattr(store, "kb", None) is not None:
            s1kb.discharge(home, rid, date=date)
        else:
            fsl.set_status(home, a["id"], "proved", {"basis": "discharge"}, date=date)
    except fsl.Refused as exc:
        raise ValueError("refused: %s" % exc)
    finally:
        federation.CACHE.clear()
    return a
