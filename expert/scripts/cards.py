"""cards.py -- the citation card: schema, scaffold, validation (plan sections 3.4, 6, 8).

A card is ``<library home>/cards/<key>/<pinpoint-slug>.md``: one relied-on statement
of one cached source, with its hypotheses, the source version it was read in, and a
verbatim quote. Files in a key folder whose name starts with ``_`` (``_intro.md``)
are notes, not cards.

    py cards.py validate [PATH ...] [--home H] [--json] [--strict] [--expect-read-from R]
    py cards.py new KEY "PINPOINT" --version V --read-from R [--home H] [--quote-file F]
                  [--used-by paper:lem:x,...] [--by expert@main/librarian] [--dry-run]
                  [--handback ID,...] [--status S --status-reason "..."]
    py cards.py path KEY "PINPOINT"
    py cards.py list [--home H] [--key K]
    py cards.py dups KEY "PINPOINT" [--bib PATH|INSTANCE:PATH] [--ref DOI|arXiv id] [--home H] [--json]

The card format::

    ---
    key: AW21
    pinpoint: Lemma 2.1
    version: arXiv v3 (27 Jan 2021)
    read_from: source
    verdict: match
    used_by: [paper:fact:forgetful-props]
    source_label: L:FiberDim
    checked: 2026-09-19
    by: expert@main/librarian
    status: verified
    status_reason: quote found in AW21.src/ (source) (MCP normaliser)
    ---

    ## Statement
    <the statement relied on, in the source's own terms>

    ## Hypotheses
    - <every hypothesis, one per bullet>

    ## Quote
    > <verbatim from the version named above; "..." marks an elision>

    ## Notes
    <optional>

``read_from`` is one of ``source`` (the arXiv LaTeX in ``<key>.src/``),
``extraction`` (``<key>.txt``, a pdftotext extraction: quote it as *extraction*),
``page-images``, ``image-only``, ``abstract``, ``not-read``, ``human-supplied`` (what a
human with access read and handed back, #108: ``<key>.human.md`` or ``<key>.human/``,
recorded by ``handback.py``), ``unknown`` (migrated, to be settled). ``status`` is ``verified`` when the quote was found in the cached
text, else ``unverified`` with ``status_reason`` saying why (a migrated card is never
repaired to match: its quote stays as the ledger gave it). The quote is checked against the cached text with the MCP server's
own normaliser (``library.find_quote``, the code behind ``library_verify_quote``):
each fragment between elisions must occur in ``<key>.src/**/*.tex`` (read_from
``source``) or ``<key>.txt``. A ``human-supplied`` card names the records of
``<key>.human.md`` it quotes (``handback: [<id>]``); every fragment, however short, must
occur in one of their texts with the narrow fold (no NFKC), an error when it does not (the
human's text is the source); a record that no longer matches its digest is an error; a
quote transcribed from a page image cannot be checked and the card must say ``status:
unverified`` with its ``status_reason``.

Exit codes: 0 valid (warnings allowed unless --strict), 1 problems, 2 usage error.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402

READ_FROM = ("source", "extraction", "page-images", "image-only", "abstract", "not-read",
             "human-supplied", "unknown")
TEXT_READS = ("source", "extraction")
HUMAN = "human-supplied"
QUOTED_READS = TEXT_READS + (HUMAN,)     # a card read so must carry a verbatim quote
VERDICTS = ("match", "mismatch", "partial", "unusable", "unreachable", "n/a", "see-notes")
REQUIRED_FIELDS = ("key", "pinpoint", "version", "read_from")
CARD_KEYS = ("key", "pinpoint", "version", "read_from", "verdict", "used_by",
             "source_label", "checked", "by", "migrated", "status", "status_reason", "handback")
STATUSES = ("verified", "unverified")
REQUIRED_SECTIONS = ("## Statement", "## Hypotheses", "## Quote")
PLACEHOLDER = "_To fill"
UNKEYED = "_unkeyed"
RE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")
RE_ELISION = re.compile(r"\s*(?:\[\s*(?:\.\s*){3}\]|\[\s*…\s*\]|(?:\.\s*){3}|…)\s*")
MIN_FRAGMENT = 12
MAX_SRC_BYTES = 4000000


# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------

def pinpoint_slug(pinpoint):
    return ac.slugify(pinpoint, maxlen=60, default="entry")


def card_path(home, key, pinpoint):
    return os.path.join(home, "cards", key, pinpoint_slug(pinpoint) + ".md")


def iter_cards(home, key=None):
    root = os.path.join(home, "cards")
    if not os.path.isdir(root):
        return
    for k in sorted(os.listdir(root)):
        if key and k != key:
            continue
        d = os.path.join(root, k)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.endswith(".md") and not f.startswith("_"):
                yield os.path.join(d, f)


# ----------------------------------------------------------------------------
# Parsing and writing
# ----------------------------------------------------------------------------

def sections(body):
    """'## Heading' -> text under it (stripped)."""
    out, cur, buf = {}, None, []
    for ln in body.replace("\r\n", "\n").split("\n"):
        if ln.startswith("## "):
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
            cur, buf = ln.rstrip(), []
        elif cur is not None:
            buf.append(ln)
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
    return out


def quote_text(section_text):
    """The quote from a ``## Quote`` section: blockquote markers removed, joined."""
    lines = []
    for ln in (section_text or "").split("\n"):
        s = ln.strip()
        if s.startswith(">"):
            lines.append(s[1:].strip())
        elif s and not lines and not s.startswith("_"):
            lines.append(s)             # an unquoted single paragraph is accepted
        elif s and lines:
            lines.append(s)
    return " ".join(x for x in lines if x).strip()


def read_card(path):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    meta, body = ac.read_frontmatter(text)
    return meta, body


def render_card(meta, statement, hypotheses, quote, notes="", extra=None):
    """The card text. ``hypotheses`` is a list of strings (or one string)."""
    ordered = {k: meta[k] for k in CARD_KEYS if k in meta and meta[k] not in (None, "")}
    if isinstance(hypotheses, (list, tuple)):
        hyp = "\n".join("- %s" % h for h in hypotheses) if hypotheses else ""
    else:
        hyp = str(hypotheses or "")
    q = "\n".join("> " + ln if ln.strip() else ">" for ln in str(quote or "").split("\n")) \
        if str(quote or "").strip() else "_No verbatim quote._"
    parts = ["", "## Statement", "", str(statement or "").strip(), "",
             "## Hypotheses", "", hyp.strip(), "", "## Quote", "", q, ""]
    for head, text in (extra or []):
        parts += ["## " + head, "", str(text).rstrip(), ""]
    parts += ["## Notes", "", str(notes or "").strip(), ""]
    body = "\n".join(parts).rstrip("\n") + "\n"
    return ac.write_frontmatter(ordered, body)


# ----------------------------------------------------------------------------
# Quote check (the MCP normaliser)
# ----------------------------------------------------------------------------

def fragments(quote):
    """Quote pieces between elisions ('...', '…', '[...]'), long enough to check."""
    parts = [p.strip(" ,;") for p in RE_ELISION.split(str(quote or ""))]
    return [p for p in parts if len(p) >= MIN_FRAGMENT]


def _src_text(src_dir):
    chunks, size = [], 0
    for dp, _dn, fn in os.walk(src_dir):
        for f in sorted(fn):
            if f.lower().endswith((".tex", ".bbl")):
                try:
                    with open(os.path.join(dp, f), "r", encoding="utf-8",
                              errors="replace") as fh:
                        t = fh.read()
                except OSError:
                    continue
                chunks.append(t)
                size += len(t)
                if size > MAX_SRC_BYTES:
                    return "\n".join(chunks)
    return "\n".join(chunks)


def check_quote(home, key, quote, read_from, _cache=None, handback=None):
    """Check a quote against the cached text of ``key``.

    Returns ``{"status": "verified"|"partial"|"not-found"|"no-text"|"no-quote"|"unchecked",
    "against": ..., "missing": [fragments], "checked": n}``. ``unchecked`` is for
    reads that have no text to check (image-only, abstract, not-read). ``human-supplied``
    is checked by ``_check_human`` against the records ``handback`` names.
    """
    frags = fragments(quote)
    if not str(quote or "").strip():
        return {"status": "no-quote", "against": None, "missing": [], "checked": 0}
    if read_from == HUMAN:
        return _check_human(home, key, quote, handback_ids(handback))
    if not frags:
        frags = [str(quote).strip()]
    lib = ex.library()
    targets = []
    src = os.path.join(home, key + ".src")
    txt = os.path.join(home, key + ".txt")
    if read_from == "source" and os.path.isdir(src):
        targets.append(("%s.src/ (source)" % key, lambda: _src_text(src)))
    if os.path.isfile(txt):
        targets.append(("%s.txt (extraction)" % key, lambda: lib._read(txt)))
    if read_from != "source" and os.path.isdir(src):
        targets.append(("%s.src/ (source)" % key, lambda: _src_text(src)))
    if not targets:
        st = "unchecked" if read_from not in TEXT_READS + ("unknown",) else "no-text"
        return {"status": st, "against": None, "missing": frags, "checked": 0}
    cache = _cache if _cache is not None else {}
    best = None
    for label, load in targets:
        ck = (key, label)
        if ck not in cache:
            cache[ck] = load()
        text = cache[ck]
        missing = [f for f in frags if lib.find_quote(text, f) is None]
        status = "verified" if not missing else (
            "partial" if len(missing) < len(frags) else "not-found")
        res = {"status": status, "against": label, "missing": missing,
               "checked": len(frags)}
        if not missing:
            return res
        if best is None or len(missing) < len(best["missing"]):
            best = res
    return best


def handback_ids(value):
    """The card's ``handback:`` (a record id, a comma-separated string, or a list) as a list."""
    if value in (None, ""):
        return []
    items = value if isinstance(value, list) else str(value).split(",")
    return [str(x).strip() for x in items if str(x).strip()]


def _human_lib():
    lib = ex.library()
    if not all(hasattr(lib, n) for n in ("handback_records", "find_quote")):
        raise SystemExit("cards: the academy base plugin at %s predates the hand-back register (#108; "
                         "library.handback_records is missing): update it, or set ACADEMY_ROOT to a checkout "
                         "that has it" % ex.academy_plugin())
    return lib


def _check_human(home, key, quote, ids):
    """A human-supplied card (#108) against the records of ``<key>.human.md`` it names
    (``handback:``), and nothing else: each record's text on its own, every fragment
    between elisions however short, with the narrow fold (no NFKC). A record that does not
    match its digest is ``bad-handback``; a named file with no text (a page image) is
    ``unchecked``; nothing recorded is ``no-human``, no record named ``no-handback``."""
    lib = _human_lib()
    frags = [p for p in (x.strip(" ,;") for x in RE_ELISION.split(str(quote or ""))) if p]
    base = {"against": None, "missing": frags, "checked": 0, "problems": []}
    recs = lib.handback_records(home, key)
    if not recs:
        return dict(base, status="no-human")
    if not ids:
        return dict(base, status="no-handback", against=", ".join(r["id"] for r in recs if r["ok"]) or None)
    known = {r["id"] for r in recs}
    chosen = [r for r in recs if r["id"] in ids]
    problems = ["no record %s in %s.human.md" % (i, key) for i in ids if i not in known] + \
        [r["problem"] for r in chosen if not r["ok"]]
    if problems:
        return dict(base, status="bad-handback", problems=problems)
    texts = [(r["label"], r["text"]) for r in chosen if r["text"] is not None]
    if not texts:
        return dict(base, status="unchecked", against=", ".join(r["label"] for r in chosen))
    best = None
    for label, text in texts:
        missing = [f for f in frags if lib.find_quote(text, f, narrow=True) is None]
        res = dict(base, status="verified" if not missing else (
            "partial" if len(missing) < len(frags) else "not-found"),
            against=label, missing=missing, checked=len(frags))
        if not missing:
            return res
        if best is None or len(missing) < len(best["missing"]):
            best = res
    return best


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------

def validate_card(meta, body, home=None, path=None, check_text=True, _cache=None):
    """Return ``(errors, warnings, quote_result)`` for one card."""
    errors, warnings = [], []
    for f in REQUIRED_FIELDS:
        if meta.get(f) in (None, ""):
            errors.append("missing %s" % f)
    for k in meta:
        if k not in CARD_KEYS:
            warnings.append("unknown field %s" % k)
    key = str(meta.get("key") or "")
    if key and key != UNKEYED and not RE_KEY.match(key):
        errors.append("key %r is not a bibliography key" % key)
    if key == UNKEYED:
        warnings.append("no bibliography key yet (filed under %s)" % UNKEYED)
    if path:
        folder = os.path.basename(os.path.dirname(os.path.abspath(path)))
        if key and folder != key:
            errors.append("key %s does not match its folder %s" % (key, folder))
    rf = meta.get("read_from")
    if rf and rf not in READ_FROM:
        errors.append("read_from %r is not one of %s" % (rf, ", ".join(READ_FROM)))
    if rf == "unknown":
        warnings.append("read_from unknown: say how the source was read")
    v = meta.get("verdict")
    if v not in (None, "") and v not in VERDICTS:
        warnings.append("verdict %r is not one of %s" % (v, ", ".join(VERDICTS)))
    if meta.get("used_by") not in (None, "") and not isinstance(meta.get("used_by"), list):
        errors.append("used_by must be a list of refs")
    if meta.get("checked") and not ac.RE_DATE.match(str(meta["checked"])):
        errors.append("checked must be YYYY-MM-DD")
    migrated = bool(meta.get("migrated"))
    st = meta.get("status")
    if st not in (None, "") and st not in STATUSES:
        errors.append("status %r is not one of %s" % (st, ", ".join(STATUSES)))
    if st == "unverified" and not meta.get("status_reason"):
        warnings.append("status unverified without a status_reason")

    secs = sections(body)
    for h in REQUIRED_SECTIONS:
        if h not in secs:
            errors.append("missing section %r" % h)
    for h in ("## Statement", "## Hypotheses"):
        t = secs.get(h, "")
        if h in secs and not t:
            errors.append("%s is empty" % h)
        elif t.startswith(PLACEHOLDER):
            (warnings if migrated else errors).append("%s not yet written" % h)
    quote = quote_text(secs.get("## Quote", ""))
    if quote.startswith("_No verbatim quote"):
        quote = ""
    qres = None
    if "## Quote" in secs:
        if not quote and rf in QUOTED_READS:
            (warnings if migrated else errors).append(
                "no verbatim quote, though read_from is %s" % rf)
        if quote and check_text and home and key and key != UNKEYED:
            qres = check_quote(home, key, quote, rf, _cache, handback=meta.get("handback"))
            if rf == HUMAN:
                _human_findings(qres, key, meta, errors, warnings)
            elif qres["status"] == "partial":
                warnings.append("quote only partly found in %s (%d of %d fragments "
                                "missing): %s" % (
                                    qres["against"], len(qres["missing"]), qres["checked"],
                                    "; ".join(repr(m[:60]) for m in qres["missing"][:3])))
            elif qres["status"] == "not-found":
                warnings.append("quote not found in %s: %s" % (
                    qres["against"], "; ".join(repr(m[:60]) for m in qres["missing"][:3])))
            elif qres["status"] == "no-text":
                warnings.append("no cached text for %s to check the quote against" % key)
            if st == "verified" and qres["status"] != "verified":
                errors.append("status verified, but the quote check says %s"
                              % qres["status"])
    if st == "verified" and not quote:
        errors.append("status verified, but the card has no quote")
    return errors, warnings, qres


def _human_findings(qres, key, meta, errors, warnings):
    """A human's text is the source itself: a quote it does not hold is an error, not the
    warning an extraction's lost display gets; a quote no script can check (transcribed from
    a page image) must be said ``status: unverified`` with its reason."""
    st = qres["status"]
    if st in ("partial", "not-found"):
        errors.append("quote not verbatim from what the human handed back (%s): %s" % (
            qres["against"], "; ".join(repr(m[:60]) for m in qres["missing"][:3])))
    elif st == "no-human":
        errors.append("read_from %s, but nothing a human handed back is recorded for %s "
                      "(%s.human.md: handback.py record)" % (HUMAN, key, key))
    elif st == "no-handback":
        errors.append("a %s card names the hand-back it quotes: handback: <record id> (handback.py record "
                      "printed it; recorded for %s: %s)" % (HUMAN, key, qres["against"] or "none sound"))
    elif st == "bad-handback":
        errors.append("handback: %s" % "; ".join(qres["problems"]))
    elif st == "unchecked":
        if meta.get("status") != "unverified" or not meta.get("status_reason"):
            errors.append("the quote is transcribed from %s, which has no text to check it against: the card "
                          "says status: unverified, with a status_reason saying so" % qres["against"])
        else:
            warnings.append("quote transcribed from %s (no text to check it against): not checked "
                            "by script" % qres["against"])


def validate_path(path, home=None, check_text=True, _cache=None):
    try:
        meta, body = read_card(path)
    except (OSError, ac.AcademyError, UnicodeDecodeError) as exc:
        return ["unreadable: %s" % exc], [], None
    if home is None:
        home = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(path))))
    return validate_card(meta, body, home, path, check_text, _cache)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _home(args):
    home = ex.expert_home(home=args.home)
    if not home:
        raise SystemExit("cards: no library home (pass --home or add an expert instance)")
    return home


def cmd_validate(args):
    home = args.home and os.path.abspath(args.home)
    paths = args.paths
    if not paths:
        home = _home(args)
        paths = list(iter_cards(home))
    rows, bad, cache = [], 0, {}
    for p in paths:
        errs, warns, q = validate_path(p, home, not args.no_text, cache)
        if args.expect_read_from:
            try:
                rf = read_card(p)[0].get("read_from")
            except (OSError, ac.AcademyError, UnicodeDecodeError):
                rf = None
            if rf != args.expect_read_from:
                errs = errs + ["read_from is %s, not %s" % (rf, args.expect_read_from)]
        rows.append({"path": p.replace("\\", "/"), "errors": errs, "warnings": warns,
                     "quote": (q or {}).get("status")})
        if errs or (args.strict and warns):
            bad += 1
    if args.json:
        print(json.dumps({"cards": rows, "bad": bad}, indent=2, ensure_ascii=False))
    else:
        for r in rows:
            for e in r["errors"]:
                print("%s: error: %s" % (r["path"], e))
            for w in r["warnings"]:
                print("%s: warning: %s" % (r["path"], w))
        print("cards: %d checked, %d with %s" % (len(rows), bad,
                                                "problems" if args.strict else "errors"))
    return 1 if bad else 0


def cmd_new(args):
    home = _home(args)
    if not RE_KEY.match(args.key):
        sys.stderr.write("cards: %r is not a bibliography key\n" % args.key)
        return 2
    quote = ""
    if args.quote_file:
        with open(args.quote_file, "r", encoding="utf-8") as fh:
            quote = fh.read().strip()
    meta = {"key": args.key, "pinpoint": args.pinpoint, "version": args.version,
            "read_from": args.read_from, "verdict": args.verdict,
            "used_by": [u for u in (args.used_by or "").split(",") if u.strip()],
            "checked": ac.today(), "by": args.by,
            "handback": handback_ids(args.handback) or None,
            "status": args.status, "status_reason": args.status_reason}
    text = render_card(meta, args.statement or PLACEHOLDER + "._",
                       args.hypotheses.split("|") if args.hypotheses else PLACEHOLDER + "._",
                       quote)
    path = card_path(home, args.key, args.pinpoint)
    if args.dry_run:
        print(path.replace("\\", "/"))
        print(text)
        return 0
    if os.path.exists(path) and not args.force:
        sys.stderr.write("cards: %s exists (use --force to overwrite)\n" % path)
        return 2
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ac.atomic_write(path, text)
    meta2, body2 = ac.read_frontmatter(text)
    errs, warns, q = validate_card(meta2, body2, home, path)
    print(path.replace("\\", "/"))
    for e in errs:
        print("error: %s" % e)
    for w in warns:
        print("warning: %s" % w)
    return 1 if errs else 0


def cmd_path(args):
    home = _home(args)
    print(card_path(home, args.key, args.pinpoint).replace("\\", "/"))
    return 0


# ----------------------------------------------------------------------------
# Duplicates (#94 review): a librarian run that ended without its result and was run
# again may have written the bib entry or the card twice
# ----------------------------------------------------------------------------

RE_ENTRY = re.compile(r"@(\w+)\s*[{(]\s*([^,\s]*)\s*,", re.I)
RE_DOI = re.compile(r"(?:doi:|https?://(?:dx\.)?doi\.org/)?\s*(10\.\d{4,9}/\S+)", re.I)
RE_ARXIV = re.compile(r"(?:arxiv:|https?://arxiv\.org/(?:abs|pdf)/)?\s*(\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?(?:\.pdf)?$", re.I)


def ref_id(ref):
    """``('doi', '10.x/y')`` or ``('arxiv', '2101.00001')`` when ``ref`` is one, else None."""
    ref = (ref or "").strip().rstrip(".")
    m = RE_DOI.fullmatch(ref)
    if m:
        return ("doi", m.group(1).lower())
    m = RE_ARXIV.fullmatch(ref)
    if m:
        return ("arxiv", m.group(1).lower())
    return None


def bib_entries(text):
    """``[(key, body)]`` of every entry (not @comment, @string, @preamble)."""
    found = [m for m in RE_ENTRY.finditer(text)
             if m.group(1).lower() not in ("comment", "string", "preamble")]
    return [(m.group(2), text[m.end():(found[n + 1].start() if n + 1 < len(found) else len(text))])
            for n, m in enumerate(found)]


def entry_ids(body):
    ids = set()
    for m in re.finditer(r"\b(doi|eprint|url|arxiv)\s*=\s*[{\"]\s*([^}\"]+?)\s*[}\"]", body, re.I):
        val = m.group(2).strip()
        for cand in (val, val.split("arxiv.org/abs/")[-1], val.split("arxiv.org/pdf/")[-1]):
            got = ref_id(cand)
            if got:
                ids.add(got)
    return ids


def resolve_bib(bib):
    """A path, or ``<instance>:<path relative to its home>`` read from workspace.json."""
    if not bib:
        return None
    if os.path.isfile(bib):
        return os.path.abspath(bib)
    m = re.match(r"^([a-z][a-z0-9-]*@[A-Za-z0-9._-]+):(.+)$", bib)
    if m:
        ws = ex.load_workspace_or_none()
        inst = ((ws or {}).get("instances") or {}).get(m.group(1))
        if inst and inst.get("home"):
            p = os.path.join(inst["home"], m.group(2))
            return os.path.abspath(p) if os.path.isfile(p) else None
    return None


def _pin(p):
    return re.sub(r"\s+", " ", str(p or "")).strip().rstrip(".").lower()


def duplicates(home, key, pinpoint, bib=None, ref=None):
    """Count the entries of ``key`` (and of the DOI / arXiv id ``ref`` names) in the
    bibliography, and the cards of ``key`` at ``pinpoint``; more than one is a problem.
    A bibliography that cannot be found is a warning, its counts None (never a pass)."""
    out = {"key": key, "pinpoint": pinpoint, "bib": None, "bib_key": None, "bib_id": None,
           "id": None, "cards": 0, "card_paths": [], "problems": [], "warnings": []}
    path = resolve_bib(bib)
    ident = ref_id(ref)
    if ident:
        out["id"] = "%s:%s" % ident
    if bib and not path:
        out["warnings"].append("bibliography %s not found: entries not counted" % bib)
    if path:
        out["bib"] = path
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            entries = bib_entries(fh.read())
        out["bib_key"] = sum(1 for k, _ in entries if k == key)
        if out["bib_key"] > 1:
            out["problems"].append("%d entries with the key %s in %s" % (out["bib_key"], key, path))
        if ident:
            same = [k for k, body in entries if ident in entry_ids(body)]
            out["bib_id"] = len(same)
            if len(same) > 1:
                out["problems"].append("%d entries for %s in %s: %s" % (len(same), out["id"], path, ", ".join(same)))
    want = _pin(pinpoint)
    slug_path = os.path.normcase(os.path.abspath(card_path(home, key, pinpoint)))
    for p in iter_cards(home, key):
        same = os.path.normcase(os.path.abspath(p)) == slug_path
        if not same:
            try:
                meta, _ = read_card(p)
            except (OSError, ac.AcademyError, UnicodeDecodeError):
                continue
            same = _pin(meta.get("pinpoint")) == want
        if same:
            out["card_paths"].append(p.replace("\\", "/"))
    out["cards"] = len(out["card_paths"])
    if out["cards"] > 1:
        out["problems"].append("%d cards for %s at %s: %s" % (out["cards"], key, pinpoint, ", ".join(out["card_paths"])))
    return out


def cmd_dups(args):
    r = duplicates(_home(args), args.key, args.pinpoint, bib=args.bib, ref=args.ref)
    if args.json:
        print(json.dumps(r, ensure_ascii=False))
    else:
        for line in r["problems"] or ["no duplicate"]:
            print(line)
        for w in r["warnings"]:
            print("warning: " + w)
    return 1 if r["problems"] else 0


def cmd_list(args):
    home = _home(args)
    for p in iter_cards(home, args.key):
        try:
            meta, _ = read_card(p)
        except (OSError, ac.AcademyError, UnicodeDecodeError):
            print("%s\t(unreadable)" % p)
            continue
        print("%s\t%s\t%s\t%s" % (meta.get("key"), meta.get("pinpoint"),
                                  meta.get("read_from"), meta.get("verdict") or ""))
    return 0


def main(argv=None):
    ex.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("paths", nargs="*")
    v.add_argument("--home")
    v.add_argument("--json", action="store_true")
    v.add_argument("--strict", action="store_true")
    v.add_argument("--no-text", action="store_true", help="skip the quote check")
    v.add_argument("--expect-read-from", choices=READ_FROM,
                   help="an error unless every card was read so (cite --from-human: human-supplied)")
    n = sub.add_parser("new")
    n.add_argument("key")
    n.add_argument("pinpoint")
    n.add_argument("--version", required=True)
    n.add_argument("--read-from", required=True, choices=READ_FROM)
    n.add_argument("--verdict", default=None, choices=VERDICTS)
    n.add_argument("--statement")
    n.add_argument("--hypotheses", help="'|'-separated")
    n.add_argument("--quote-file")
    n.add_argument("--used-by")
    n.add_argument("--handback", help="human-supplied: the record id(s) of <key>.human.md the quote is from")
    n.add_argument("--status", choices=STATUSES)
    n.add_argument("--status-reason")
    n.add_argument("--by")
    n.add_argument("--home")
    n.add_argument("--force", action="store_true")
    n.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("path")
    p.add_argument("key")
    p.add_argument("pinpoint")
    p.add_argument("--home")
    ls = sub.add_parser("list")
    ls.add_argument("--home")
    ls.add_argument("--key")
    d = sub.add_parser("dups", help="duplicate bib entries or cards of one key and pinpoint")
    d.add_argument("key")
    d.add_argument("pinpoint")
    d.add_argument("--bib", help="a path, or <instance>:<path in its home>")
    d.add_argument("--ref", help="the reference asked for: a DOI or arXiv id is checked too")
    d.add_argument("--home")
    d.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    return {"validate": cmd_validate, "new": cmd_new, "path": cmd_path,
            "list": cmd_list, "dups": cmd_dups}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
