"""Structured claim records (#127, the human's ruling of 2026-11-27: "Hypotheses + items").

A record may name its hypotheses and its conclusions (items) in two optional map fields;
a record without them behaves exactly as before (lazy migration: new and reworded claims
take the structured form, old records keep theirs until next touched)::

    hypotheses:
      H1: "P is a rational polygon"          # its text, or the definition it uses
      H2: "paper:defn:conical"
    items:
      C1: [proved]                           # [status, modulo input, ...]
      C2: [proved-modulo, paper:lem:x]

* **Item keys.** In a notebook (and the lab) ``C<n>``; in the paper the item's tex label
  **without** its ``it:`` prefix (``\\label{it:compact}`` is ``compact``).
* **Item value.** An inline list: the item's status (the academy vocabulary) first, then
  its modulo inputs, non-empty exactly when the status is ``proved-modulo`` (the
  record-level rule, per item).
* **Texts stay in the body.** A notebook's ``## Statement`` (the lab: the body) writes
  each part as a line starting ``**H1.**`` / ``**C1.**`` (a ``- `` bullet before it is
  allowed; ``**C1**.`` and ``**C1:**`` too); a part's text runs to the next part's
  marker, a blank line or a heading (so a continuation line belongs to it, and prose
  between the parts belongs to none). The paper's items are the ``\\item ... \\label{it:KEY}`` of
  the statement's environment (an item runs to the next ``\\item`` of its list or the
  list's end; nested lists stay inside their item). The paper's tex labels no hypothesis,
  so there the frontmatter's ``hypotheses`` values are the hypotheses' texts; in a
  notebook the body's ``**H<n>.**`` text is used when present, else the value.
* **Derived status.** A record with ``items`` has the status its items derive
  (:func:`derive`): every item proved -> proved; every item proved or proved-modulo ->
  proved-modulo, its ``modulo`` the union of the items' (in item order); else the weakest
  item status by :data:`STRENGTH`. ``registry.py check`` refuses a mismatch.
* **Hashes.** The whole-statement hash is unchanged. Each item has its own
  (:func:`item_hashes`): the hash of the hypotheses' texts (in key order) and the item's
  own text, so a changed hypothesis changes every item's hash and a reworded item only
  its own.
"""
from __future__ import annotations

import re

from .model import statement_hash_of
from .schema import STATUSES, STRUCT_FIELDS
HYP_KEY_RE = re.compile(r"^H[1-9][0-9]*$")
NB_ITEM_KEY_RE = re.compile(r"^C[1-9][0-9]*$")
PAPER_ITEM_KEY_RE = re.compile(r"^[^\s{}\\]+$")
#: weakest first: a record's derived status is the weakest of its items' (after the
#: proved / proved-modulo rule). A refuted item makes the conjunction false.
STRENGTH = ("refuted", "refuted-as-stated", "open", "conjectured", "sketch", "supported",
            "proved-modulo", "proved")

#: a notebook part marker: ``**H1.** text``, ``- **C2.** text``, ``**C3**. text``, ``**H1:**``
RE_PART = re.compile(r"^\s*(?:[-*]\s+)?\*\*([HC][1-9][0-9]*)\s*[.:]?\s*\*\*\s*[.:]?\s*(.*)$")


def natural(key):
    """A sort key that orders ``C2`` before ``C10``."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(key))]


def has_structure(fields):
    return isinstance(fields, dict) and any(k in fields for k in STRUCT_FIELDS)


# --------------------------------------------------------------------------- body texts

def nb_parts(text):
    """``(hypotheses, items)`` of a notebook statement: two ``{key: text}`` dicts in the
    order written, from the ``**H<n>.**`` / ``**C<n>.**`` lines (see the module text).
    Lines outside a part (before the first marker, after a blank line) belong to none."""
    hyps, items, cur = {}, {}, None
    for line in str(text or "").replace("\r", "").split("\n"):
        m = RE_PART.match(line)
        if m:
            key, rest = m.group(1), m.group(2)
            cur = (hyps if key[0] == "H" else items, key)
            if key in cur[0]:
                cur[0][key] += "\n" + rest      # a repeated marker: one part (check says so)
            else:
                cur[0][key] = rest
            continue
        if cur is not None:
            if not line.strip() or re.match(r"^#{1,6} ", line):
                cur = None      # a blank line or a heading ends the part
                continue
            cur[0][cur[1]] += "\n" + line
    clean = lambda d: {k: v.strip() for k, v in d.items()}  # noqa: E731
    return clean(hyps), clean(items)


def nb_duplicates(text):
    """The part keys written more than once in a notebook statement."""
    seen, dup = set(), []
    for line in str(text or "").replace("\r", "").split("\n"):
        m = RE_PART.match(line)
        if m:
            k = m.group(1)
            if k in seen and k not in dup:
                dup.append(k)
            seen.add(k)
    return dup


_LIST_ENVS = "enumerate|itemize|description"
RE_TEX_TOKEN = re.compile(r"\\begin\{(?:%s)\*?\}(?:\[[^\]]*\])?|\\end\{(?:%s)\*?\}|\\item\b"
                          r"|\\label\{it:([^}]*)\}" % (_LIST_ENVS, _LIST_ENVS))


def paper_items(env):
    """``{key: text}`` of the ``\\label{it:KEY}`` items of a LaTeX environment, in order:
    each item's text from its ``\\item`` to the next ``\\item`` of the same list (or the
    list's ``\\end``); the key is the label without ``it:``. A label outside any item
    belongs to none (and is reported by :func:`check`)."""
    env = str(env or "")
    stack = []          # per open list: start of its current item, or None
    open_items = []     # (depth, start, [labels]) of items not yet closed
    out = {}

    def close(depth, end):
        while open_items and open_items[-1][0] >= depth:
            d, start, labels = open_items.pop()
            for lab in labels:
                out.setdefault(lab, env[start:end].strip())

    for m in RE_TEX_TOKEN.finditer(env):
        tok = m.group(0)
        if tok.startswith("\\begin"):
            stack.append(True)
        elif tok.startswith("\\end"):
            close(len(stack), m.start())
            if stack:
                stack.pop()
        elif tok.startswith("\\item"):
            depth = len(stack)
            close(depth, m.start())
            open_items.append((depth, m.start(), []))
        else:
            if open_items:
                open_items[-1][2].append(m.group(1))
            else:
                out.setdefault(m.group(1), None)
    close(0, len(env))
    # keep the tex order of the labels
    order = [m.group(1) for m in RE_TEX_TOKEN.finditer(env) if m.group(1)]
    return {k: out[k] for k in dict.fromkeys(order) if k in out}


# --------------------------------------------------------------------------- frontmatter

def parse_items(fields):
    """``({key: (status, [modulo])}, problems)`` of a record's ``items`` field."""
    raw = fields.get("items") if isinstance(fields, dict) else None
    if raw is None:
        return {}, []
    if not isinstance(raw, dict):
        return {}, ["'items' must be a nested map `KEY: [status, modulo...]`"]
    out, probs = {}, []
    for k, v in raw.items():
        vals = v if isinstance(v, list) else [v]
        vals = [str(x).strip() for x in vals if str(x).strip()]
        if not vals:
            probs.append(f"item {k}: no status")
            continue
        out[k] = (vals[0], vals[1:])
    return out, probs


def derive(items):
    """``(status, modulo)`` a record's items derive (see the module text); ``modulo`` is
    the union of the items' inputs (in item order) when the status is proved-modulo.
    ``items``: ``{key: (status, [modulo])}``. ``(None, [])`` when there are none or an
    item's status is outside the vocabulary."""
    if not items:
        return None, []
    sts = [st for st, _m in items.values()]
    if any(st not in STRENGTH for st in sts):
        return None, []
    if all(st == "proved" for st in sts):
        return "proved", []
    if all(st in ("proved", "proved-modulo") for st in sts):
        mod = []
        for st, m in items.values():
            for x in m:
                if x not in mod:
                    mod.append(x)
        return "proved-modulo", mod
    return min(sts, key=STRENGTH.index), []


def item_value(status, modulo=()):
    return [status] + [str(m) for m in (modulo or ()) if str(m).strip()]


# --------------------------------------------------------------------------- hashes

def hypothesis_texts(fields, body_hyps):
    """``{H<n>: text}`` the item hashes use: the body's text where it has the part, else
    the frontmatter value; in key order."""
    fm_h = fields.get("hypotheses") if isinstance(fields.get("hypotheses"), dict) else {}
    keys = sorted(set(fm_h) | set(body_hyps or {}), key=natural)
    return {k: (body_hyps or {}).get(k) or str(fm_h.get(k) or "") for k in keys}


def item_hash(hyp_texts, text):
    """The hash of one item: its hypotheses' texts (in key order), then its own text."""
    parts = ["%s. %s" % (k, hyp_texts[k]) for k in sorted(hyp_texts, key=natural)]
    return statement_hash_of("\n".join(parts + ["--", str(text or "")]))


def item_hashes(hyp_texts, item_texts):
    return {k: item_hash(hyp_texts, t) for k, t in item_texts.items() if t is not None}


# --------------------------------------------------------------------------- check

def check(fields, body_hyps, body_items, *, paper=False, status_kinds=None, dups=()):
    """``[(level, message)]`` for a record's structured fields against its body texts
    (``body_hyps`` / ``body_items``, from :func:`nb_parts` or :func:`paper_items`).
    Silent on a record without ``hypotheses`` and ``items``."""
    out = []
    err = lambda m: out.append(("error", m))  # noqa: E731
    if not has_structure(fields):
        return out
    hyps = fields.get("hypotheses")
    if hyps is not None:
        if not isinstance(hyps, dict):
            err("'hypotheses' must be a nested map `H<n>: \"text\"`")
            hyps = {}
        for k, v in hyps.items():
            if not HYP_KEY_RE.match(k):
                err(f"hypothesis key `{k}` is not H<n>")
            if isinstance(v, list) or not str(v or "").strip():
                err(f"hypothesis {k}: give its text or the definition it uses")
    else:
        hyps = {}
    if not paper:
        bh = set(body_hyps or {})
        if bh != set(hyps) and (bh or hyps):
            miss = sorted(set(hyps) - bh, key=natural)
            extra = sorted(bh - set(hyps), key=natural)
            if miss:
                err("hypotheses without a `**H<n>.**` line in the statement: " + ", ".join(miss))
            if extra:
                err("`**H<n>.**` lines in the statement not under `hypotheses`: "
                    + ", ".join(extra))
    for k in dups:
        err(f"part `{k}` is written twice in the statement")
    items, probs = parse_items(fields)
    for p in probs:
        err(p)
    if "items" not in fields:
        return out
    if status_kinds is not None and fields.get("kind") not in status_kinds:
        err(f"a {fields.get('kind')} carries no status, so no `items`")
    key_re = PAPER_ITEM_KEY_RE if paper else NB_ITEM_KEY_RE
    for k, (st, mod) in items.items():
        if paper and k.startswith("it:"):
            err(f"item `{k}`: write the label without its `it:` prefix (`{k[3:]}`)")
        elif not key_re.match(k):
            err(f"item key `{k}` is not " + ("a tex label" if paper else "C<n>"))
        if st not in STATUSES:
            err(f"item {k}: status `{st}` is not one of: " + ", ".join(STATUSES))
        if st == "proved-modulo" and not mod:
            err(f"item {k}: proved-modulo needs its modulo inputs (`{k}: [proved-modulo, ID]`)")
        if st != "proved-modulo" and mod:
            err(f"item {k}: inputs {', '.join(mod)} are given only with proved-modulo")
    body_items = body_items or {}
    where = "`\\label{it:...}` item of the statement's environment" if paper \
        else "`**C<n>.**` line in the statement"
    miss = [k for k in items if k not in body_items]
    if miss:
        err(f"items without a {where}: " + ", ".join(miss))
    extra = [k for k in body_items if k not in items]
    if extra:
        err(("`\\label{it:...}` items" if paper else "`**C<n>.**` lines")
            + " not under `items`: " + ", ".join(extra))
    none_text = [k for k, t in body_items.items() if t is None and k in items]
    if none_text:
        err("labels outside any \\item: " + ", ".join(none_text))
    st, mod = derive(items)
    rst = fields.get("status")
    if st is not None and (fields.get("lifecycle") or "active") == "active":
        if rst != st:
            err(f"status `{rst}` but the items derive `{st}` (#127: a structured record's "
                "status is its items')")
        elif st == "proved-modulo":
            rmod = [str(m) for m in (fields.get("modulo") or [])] \
                if isinstance(fields.get("modulo"), list) else []
            if set(rmod) != set(mod):
                err("modulo [%s] but the items' inputs are [%s]"
                    % (", ".join(rmod), ", ".join(mod)))
    return out


# --------------------------------------------------------------------------- migration

def propose(fields, body_hyps, body_items, *, paper=False):
    """The ``hypotheses`` / ``items`` fields a record's body suggests (lazy migration,
    ``registry.py structure ID``): each item takes the record's status (and its modulo,
    when proved-modulo) unless it already has one; a hypothesis keeps its value, else
    its body text (the paper's tex has none: ``TODO`` placeholders are not invented)."""
    old_items, _ = parse_items(fields)
    rst = fields.get("status") if isinstance(fields.get("status"), str) else ""
    rmod = [str(m) for m in (fields.get("modulo") or [])] \
        if isinstance(fields.get("modulo"), list) else []
    items = {}
    for k in body_items:
        if k in old_items:
            items[k] = item_value(*old_items[k])
        elif rst:
            items[k] = item_value(rst, rmod if rst == "proved-modulo" else ())
    out = {}
    fm_h = fields.get("hypotheses") if isinstance(fields.get("hypotheses"), dict) else {}
    if paper:
        if fm_h:
            out["hypotheses"] = dict(fm_h)
    else:
        hyps = {k: str(fm_h.get(k) or v) for k, v in (body_hyps or {}).items()}
        if hyps:
            out["hypotheses"] = hyps
    if items:
        out["items"] = items
    return out
