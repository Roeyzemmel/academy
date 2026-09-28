"""ledger_split.py -- turn BI's ledgers into library records (plan sections 6, 9 phase 7).

    py ledger_split.py --sources SOURCES.md [--related RELATED.md] [--verdicts VERDICTS.md] --out DIR
                       [--library HOME] [--bib BIB] [--instance author@bi] [--report-dir D] [--force]

* ``Drafts/sources.md``: one ``## <KEY> — ...`` block per source, one bullet per
  pinpoint. Each bullet becomes a card ``DIR/cards/<key>/<pinpoint-slug>.md``
  (``cards.py`` schema), marked ``migrated``: the fields the ledger states are
  carried (version, how read, verdict, date, the labels using it, the verbatim quote);
  the statement and hypotheses are left ``_To fill_`` for the librarian, and the
  bullet itself is kept verbatim under ``## Ledger text``. A block's text before its
  first bullet goes to ``cards/<key>/_intro.md``. A block whose heading names no
  bibliography key goes under ``cards/_unkeyed/``.
* ``Drafts/related_work.md``: the header (before the first ``## ``) becomes
  ``DIR/ledgers/<instance>/_header.md`` (the keyword and priority lists the watch
  reads), and each ``## `` block ``DIR/ledgers/<instance>/<date>-<slug>.md``, verbatim.
* ``Drafts/verdicts.md`` (``--verdicts``): one review pass per entry (a
  ``## <label> -- date (note)`` block, or a ``### `` pair inside one) as
  ``DIR/reviews/<ns>/<id>/<date>[-<note>]/A.md``, ``B.md`` (the run bullets, verbatim,
  with the fields they state as frontmatter; no run id or statement hash is invented)
  and ``decision.md`` (the rest of the entry, verbatim). An entry whose first two
  bullets are not run A and run B goes verbatim into ``DIR/reviews/_unparsed.md``.
* With ``--library``, every card gets ``status: verified`` when its quote is found in
  the cached text by the MCP normaliser, else ``status: unverified`` with
  ``status_reason``. A quote is never altered to make it match.
* Every record holds its piece of the ledger verbatim; ``DIR/ledgers/<instance>/
  _manifest-<ledger>.json`` holds the order and the headings between pieces, and the
  run checks that the records reproduce each ledger byte for byte
  (``ledger_views.py`` rebuilds them as generated views).
* ``stats.json``, ``stats.md`` and ``ledger-split-report.md`` (the mapping report:
  counts, every block and its records, anything unmapped, every card's status) go to
  ``--report-dir`` (default DIR). Exit 1 when a ledger is not reproduced.

It never writes into a home: ``--out`` must lie outside every workspace home
unless ``--force`` is given. Run it on copies (plan 9b: moving the ledgers is a
review-gated step with its own packet).
"""

import argparse
import collections
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _expert as ex  # noqa: E402
from _expert import ac  # noqa: E402
import cards as cardlib  # noqa: E402

RE_KEYLIKE = re.compile(r"^[A-Z][A-Za-z]*\d{2,4}[a-z]?(?:-[a-z]+)?$")
RE_LABEL = re.compile(r"`((?:thm|lem|prop|cor|defn|def|rmk|fact|conj|ex|claim|quest|sec|eq|"
                      r"fig|problem|exc|case|tab|app|subsec|cond):[^`\s]+)`")
RE_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
RE_QUOTE = re.compile(r"[\"“](.+?)[\"”]", re.S)
RE_COLON_QUOTE = re.compile(r":\s*[\"“](.+?)[\"”]", re.S)
RE_PINPOINT_QUOTE = re.compile(r"`[^`]*:\d+(?:[-–]\d+)?`\)?\s*:\s*[\"“](.+?)[\"”]", re.S)
RE_HEAD_SPLIT = re.compile(r"\s+[—–-]\s+|\s*\(")
QUOTE_ANCHORS = (("erbatim", 300), ("quoted", 60), ("reads:", 4), ("reads ", 4))
QUOTE_BAD_START = (")", ",", ".", ";", ":")
VERDICT_WORDS = (("mismatch", "mismatch"), ("no hit", "unusable"), ("unusable", "unusable"),
                 ("partial", "partial"), ("unreachable", "unreachable"),
                 ("match", "match"))


# ----------------------------------------------------------------------------
# sources.md
# ----------------------------------------------------------------------------

def split_blocks(text):
    """``(preamble, [(heading, [body lines], first line no)])``; a heading may wrap onto
    following non-blank lines, which are joined to it."""
    lines = text.replace("\r\n", "\n").split("\n")
    pre, blocks, cur = [], [], None
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("## "):
            head = ln[3:].strip()
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].startswith(("- ", "#")):
                head += " " + lines[j].strip()
                j += 1
            cur = (head, [], i + 1)
            blocks.append(cur)
            i = j
            continue
        if cur is None:
            pre.append(ln)
        else:
            cur[1].append(ln)
        i += 1
    return "\n".join(pre).strip("\n"), blocks


def heading_keys(head, bib_keys=()):
    """The bibliography keys a heading names, in order (may be empty)."""
    lead = RE_HEAD_SPLIT.split(head, 1)[0]
    out = []
    for tok in lead.split(","):
        tok = tok.strip().strip("*`")
        if tok and (tok in bib_keys or RE_KEYLIKE.match(tok)):
            out.append(tok)
    return out


def split_bullets(lines):
    """``(intro lines, [bullet text])``: a bullet runs until the next column-0 ``- ``.

    After the first bullet, a column-0 paragraph that opens with ``**...**`` after a
    blank line (the ledger's un-bulleted sub-entries) starts a bullet of its own,
    written as ``- **...**`` so it parses like the others.
    """
    intro, bullets, cur = [], [], None
    prev_blank = True
    for ln in lines:
        if ln.startswith("- "):
            cur = [ln]
            bullets.append(cur)
        elif cur is not None and prev_blank and ln.startswith("**"):
            cur = ["- " + ln]
            bullets.append(cur)
        elif cur is None:
            intro.append(ln)
        else:
            cur.append(ln)
        prev_blank = not ln.strip()
    return "\n".join(intro).strip("\n"), ["\n".join(b).rstrip() for b in bullets]


RE_FILE_KEY = re.compile(r"\b([A-Za-z][A-Za-z0-9-]*)\.(?:src/|txt\b|pdf\b|meta\b)")


def evidence_key(bullet, block_keys, known):
    """A key the bullet's file references point at instead of its block's keys.

    A bullet that cites only another source's cached files (``AW21.src/main.tex:543``)
    inside, say, the Lan08 block belongs to that source. Returns the key, or None
    when the files name a block key, several keys, or none."""
    if any(re.search(r"\b%s\b" % re.escape(k), bullet) for k in block_keys):
        return None                     # the bullet names its own block's source
    ks = {k for k in RE_FILE_KEY.findall(bullet) if k in known}
    if len(ks) != 1:
        return None
    return ks.pop()


def bullet_pinpoint(bullet, keys):
    """``(key or None, pinpoint)`` from a bullet's leading ``**...**``."""
    m = re.match(r"^- \*\*(.+?)\*\*", bullet, re.S)
    if not m:
        return None, "entry"
    pin = " ".join(m.group(1).split()).strip(" .,:;—-")
    for k in keys:
        if pin.startswith(k + ",") or pin.startswith(k + " "):
            return k, pin[len(k):].strip(" ,")
    return None, pin or "entry"


def classify_read(bullet):
    """``read_from`` from the bullet's "How read:" clause (or its wording)."""
    low = " ".join(bullet.lower().split())
    i = low.rfind("how read")
    seg = low[i:i + 160] if i >= 0 else low
    for words, val in ((("page image",), "page-images"), (("image-only", "image only"),
                                                          "image-only"),
                       (("**source**", "source (", "latex source", "read: source"),
                        "source"),
                       (("extraction", "pdftotext", "text layer", "pdf text"), "extraction"),
                       (("abstract",), "abstract"),
                       (("not read", "toc-only", "table of contents"), "not-read")):
        if any(w in seg for w in words):
            return val
    if i < 0:
        if "bib data" in low and "verbatim" not in low:
            return "not-read"
        return "unknown"
    return "unknown"


def classify_verdict(bullet):
    low = " ".join(bullet.lower().split())
    i = low.find("verdict")
    if i < 0:
        return None
    seg = low[i:i + 60]
    for w, v in VERDICT_WORDS:
        if w in seg:
            return v
    return "see-notes"


def extract_quote(bullet):
    """The verbatim quote the ledger gives, or ''. Only a quotation that follows the
    word "verbatim" (or "quoted"/"reads") counts; a stray quoted word does not.

    Within the anchor's window, a quotation introduced by its own colon wins over an
    earlier one: "paragraph \"Marked points ...\" in the Introduction: \"Define an
    n-point marking ...\"" names the paragraph in quotes before getting to the
    relied-on statement, and the colon marks where that statement actually starts."""
    flat = bullet.replace("\n", " ")
    for anchor, window in QUOTE_ANCHORS:
        i = flat.find(anchor)
        if i < 0:
            continue
        cm = RE_COLON_QUOTE.search(flat, i)
        m = cm if cm else RE_QUOTE.search(flat, i)
        if not m:
            continue
        # the quotation must open near its anchor ("reads off the tiling ... (\"" is not
        # a quote), and a span that starts with closing punctuation straddles two
        # quotations rather than being one. The window bounds where the quotation may
        # *open*, not how long it may run once it has.
        if m.start() - (i + len(anchor)) > window:
            continue
        q = m.group(1).strip()
        if len(q) >= 20 and not q.startswith(QUOTE_BAD_START):
            return " ".join(q.split())
    # A bullet that pins a precise file:line reference directly before its quotation
    # needs no anchor word at all: "(`MS91.txt:1033-1034`): \"The map ...\"." -- the
    # pinpoint itself introduces the quote.
    m = RE_PINPOINT_QUOTE.search(flat)
    if m:
        q = m.group(1).strip()
        if len(q) >= 20 and not q.startswith(QUOTE_BAD_START):
            return " ".join(q.split())
    return ""


def version_for(key, head, index_rows):
    row = index_rows.get(key)
    if row and row.get("version"):
        return " ".join(row["version"].split())
    m = re.search(r"arXiv:?\s*([\w./-]+?v\d+)", head)
    if m:
        return "arXiv %s" % m.group(1)
    rest = RE_HEAD_SPLIT.split(head, 1)
    return " ".join(rest[1].split()).strip(" ()") if len(rest) > 1 else ""


def make_card(key, pinpoint, bullet, head, index_rows, instance, status=None):
    """``(meta, quote, card text)``. ``status`` is ``(status, reason)`` from the quote
    check (``quote_status``), or None when no library was given."""
    labels = sorted(set("paper:" + m for m in RE_LABEL.findall(bullet)))
    dates = RE_DATE.findall(bullet)
    sl = re.search(r"source label `([^`]+)`", bullet)
    meta = {"key": key, "pinpoint": pinpoint,
            "version": version_for(key, head, index_rows) or "unstated in the ledger",
            "read_from": classify_read(bullet), "verdict": classify_verdict(bullet),
            "used_by": labels, "source_label": sl.group(1) if sl else None,
            "checked": dates[-1] if dates else None, "by": "%s/source-checker" % instance,
            "migrated": "Drafts/sources.md (%s)" % instance}
    quote = extract_quote(bullet)
    if status:
        meta["status"], meta["status_reason"] = status
    text = cardlib.render_card(
        meta, cardlib.PLACEHOLDER + " (migrated): the statement relied on._",
        cardlib.PLACEHOLDER + " (migrated): the hypotheses, one per bullet._", quote,
        notes="Migrated by ledger_split.py; the ledger's own text is kept verbatim above.",
        extra=[("Ledger text", bullet)])
    return meta, quote, text


def quote_status(library, key, quote, read_from, cache):
    """``((status, reason), check result)`` for a card's quote, with the MCP normaliser.

    ``verified`` only when every fragment of the quote is found in the cached text;
    everything else is ``unverified`` with the reason. The quote itself is never
    touched: a mismatch is recorded, not repaired."""
    if key == cardlib.UNKEYED:
        return ("unverified", "no bibliography key, so no cached text to check against"), None
    if not quote:
        return ("unverified", "no verbatim quote in the ledger entry to check"), \
            {"status": "no-quote", "against": None, "missing": [], "checked": 0}
    q = cardlib.check_quote(library, key, quote, read_from, cache)
    st = q["status"]
    miss = "; ".join(repr(m[:70]) for m in q["missing"][:2])
    if st == "verified":
        return ("verified", "quote found in %s (MCP normaliser)" % q["against"]), q
    if st == "partial":
        return ("unverified", "quote only partly found in %s: %d of %d fragment(s) missing, "
                              "first %s" % (q["against"], len(q["missing"]), q["checked"],
                                            miss)), q
    if st == "not-found":
        return ("unverified", "quote not found in %s: %s" % (q["against"], miss)), q
    if st == "no-text":
        return ("unverified", "no cached text (.txt or .src/) for %s to check the quote "
                              "against" % key), q
    return ("unverified", "read_from %s: no text to check the quote against" % read_from), q


def _free_card_path(path, written):
    """``path`` unless this run already wrote it or it holds a card this script did
    not migrate; then the next free ``-N`` suffix."""
    def taken(p):
        if p in written:
            return True
        if not os.path.exists(p):
            return False
        try:
            meta, _ = cardlib.read_card(p)
        except (OSError, ac.AcademyError, UnicodeDecodeError):
            return True
        return not meta.get("migrated")
    if not taken(path):
        return path, False
    base, n = path[:-3], 2
    while taken("%s-%d.md" % (base, n)):
        n += 1
    return "%s-%d.md" % (base, n), True


def convert_sources(text, out, library=None, bib_keys=(), instance="author@bi",
                    pieces=None):
    """Cards from ``Drafts/sources.md``. ``pieces``, when a list, receives the verbatim
    pieces in document order as ``(ref, text)`` for the manifest (``build_manifest``)."""
    pre, blocks = split_blocks(text)
    index_rows = {}
    if library:
        index_rows = {r["key"]: r for r in ex.library().load_index(library)}
    stats = collections.OrderedDict(
        blocks=len(blocks), cards=0, unkeyed_blocks=[], collisions=[], read_from=collections.Counter(),
        verdict=collections.Counter(), quotes=collections.Counter(), per_key=collections.Counter(),
        status=collections.Counter(), with_labels=0, errors=0, warnings=0, reassigned=[],
        intros=0, cards_by_status={})
    written, cache = [], {}
    pieces = pieces if pieces is not None else []
    known = set(bib_keys) | set(index_rows) | set(k for h, _b, _l in blocks
                                                  for k in heading_keys(h, bib_keys))
    header_path = os.path.join(out, "ledgers", instance, "_sources-header.md")
    if pre.strip():
        ac.atomic_write(header_path, piece_file([("Drafts/sources.md (%s), preamble"
                                                  % instance, pre.strip())]))
        pieces.append(({"file": _rel(header_path, out), "piece": 1}, pre.strip()))
    intro_paths = set()
    for head, body, line in blocks:
        keys = heading_keys(head, bib_keys)
        intro, bullets = split_bullets(body)
        default_key = keys[0] if keys else cardlib.UNKEYED
        if not keys:
            stats["unkeyed_blocks"].append(head[:80])
        folder_key = default_key
        if intro.strip():
            p = os.path.join(out, "cards", folder_key,
                             "_intro.md" if keys else "_intro-%s.md" % ac.slugify(head, 40))
            if p in intro_paths:
                raise ValueError("two blocks would share the intro file %s" % p)
            intro_paths.add(p)
            ac.atomic_write(p, piece_file([("Drafts/sources.md (%s), line %d: the text of "
                                            "the block before its first entry"
                                            % (instance, line), intro.strip())]))
            pieces.append(({"file": _rel(p, out), "piece": 1}, intro.strip()))
            stats["intros"] += 1
        for b in bullets:
            k, pin = bullet_pinpoint(b, keys + sorted(known - set(keys)))
            if not k:
                k = evidence_key(b, keys, known)
            if k and k not in keys:
                stats["reassigned"].append("%s -> %s / %s" % (default_key, k, pin[:50]))
            key = k or default_key
            if not keys:
                pin = "%s — %s" % (RE_HEAD_SPLIT.split(head, 1)[0].strip(), pin)
            status, q = None, None
            if library:
                status, q = quote_status(library, key, extract_quote(b), classify_read(b),
                                         cache)
            meta, quote, ctext = make_card(key, pin, b, head, index_rows, instance, status)
            path, collided = _free_card_path(cardlib.card_path(out, key, pin), written)
            if collided:
                stats["collisions"].append("%s / %s" % (key, pin))
            ac.atomic_write(path, ctext)
            written.append(path)
            ref = {"card": _rel(path, out)}
            if b.startswith("- **") and not text_has_line(text, b):
                ref["strip"] = 2            # an un-bulleted "**...**" paragraph
            pieces.append((ref, b[ref.get("strip", 0):]))
            stats["cards"] += 1
            stats["per_key"][key] += 1
            stats["read_from"][meta["read_from"]] += 1
            stats["verdict"][meta["verdict"] or "none"] += 1
            stats["with_labels"] += bool(meta["used_by"])
            if status:
                stats["status"][status[0]] += 1
                stats["cards_by_status"][_rel(path, out)] = [status[0], status[1]]
            if library:
                m2, b2 = ac.read_frontmatter(ctext)
                errs, warns, _q = cardlib.validate_card(m2, b2, library, None, False, cache)
                stats["errors"] += bool(errs)
                stats["warnings"] += bool(warns)
                stats["quotes"][(q or {}).get("status") or ("no-quote" if not quote
                                                            else "unchecked")] += 1
            else:
                stats["quotes"]["present" if quote else "no-quote"] += 1
    return written, stats


def text_has_line(text, bullet):
    """True when the bullet's first line occurs as a line of ``text`` as written."""
    first = bullet.split("\n", 1)[0]
    return ("\n" + first + "\n") in ("\n" + text.replace("\r\n", "\n") + "\n")


# ----------------------------------------------------------------------------
# related_work.md
# ----------------------------------------------------------------------------

def raw_blocks(text):
    """The ``## `` blocks of ``text`` as written: ``[(first line no, raw text)]``, each
    running from its heading line to the line before the next ``## `` heading, with
    trailing blank lines left out."""
    lines = text.replace("\r\n", "\n").split("\n")
    starts = [i for i, ln in enumerate(lines) if ln.startswith("## ")]
    out = []
    for n, i in enumerate(starts):
        j = starts[n + 1] if n + 1 < len(starts) else len(lines)
        out.append((i + 1, "\n".join(lines[i:j]).rstrip()))
    return out


def convert_related(text, out, instance="author@bi", pieces=None):
    pre, blocks = split_blocks(text)
    pieces = pieces if pieces is not None else []
    folder = os.path.join(out, "ledgers", instance)
    written = []
    hp = os.path.join(folder, "_header.md")
    ac.atomic_write(hp, piece_file([("Drafts/related_work.md (%s), header: keywords, "
                                     "priority list" % instance, pre.strip())]))
    written.append(hp)
    if pre.strip():
        pieces.append(({"file": _rel(hp, out), "piece": 1}, pre.strip()))
    raws = raw_blocks(text)
    if len(raws) != len(blocks):
        raise ValueError("related_work: %d headings but %d blocks" % (len(raws), len(blocks)))
    for (head, body, line), (_l, raw) in zip(blocks, raws):
        m = RE_DATE.search(head)
        date = m.group(1) if m else "undated"
        slug = ac.slugify(RE_DATE.sub("", head), 50, "block")
        p = os.path.join(folder, "%s-%s.md" % (date, slug))
        n = 2
        while p in written:
            p = os.path.join(folder, "%s-%s-%d.md" % (date, slug, n))
            n += 1
        ac.atomic_write(p, piece_file([("Drafts/related_work.md (%s), line %d"
                                        % (instance, line), raw)]))
        written.append(p)
        pieces.append(({"file": _rel(p, out), "piece": 1}, raw))
    return written


# ----------------------------------------------------------------------------
# verdicts.md -> reviews/<ns>/<id>/<pass>/
# ----------------------------------------------------------------------------

RE_VHEAD = re.compile(r"^([a-z][a-z0-9-]*:[^\s]+)\s+(?:--|—|–)\s+(\d{4}-\d{2}-\d{2})"
                      r"(?:\s+\((.+)\))?\s*$")
RE_RUN = re.compile(r"^- run ([AB]): (.+?) / (CONFIRMED|PLAUSIBLE|GAP|DISPROVED) / (\S+)"
                    r"(?: \(([^)]*)\))? (?:--|—) blocking: (.*)$", re.S)
RE_OUTCOME = re.compile(r"^- outcome: \*\*(.+?)\*\*")
REVIEW_KEYS = ("subject", "pass", "run", "run_id", "verdict", "modulo", "model",
               "statement_hash", "blocking", "ticket", "agent", "landed",
               "reported_status", "model_note", "migrated")
DECISION_KEYS = ("subject", "pass", "outcome", "runs", "decided", "by", "migrated")


def _entries(block_head, body_lines, line):
    """Split one ``## `` verdict block into entries at its ``### `` sub-headings:
    ``[(heading text, sub-heading or None, [lines], first line no of the lines)]``."""
    out = [(block_head, None, [], line + 1)]
    for n, ln in enumerate(body_lines):
        if ln.startswith("### "):
            out.append((ln[4:].strip(), ln[4:].strip(), [], line + 1 + n + 1))
        else:
            out[-1][2].append(ln)
    return out


def parse_run(bullet):
    """Fields of a ``- run X: status / VERDICT / model (note) -- blocking: ...`` bullet,
    or None when it does not have exactly that shape."""
    flat = re.sub(r"[ ]*\n[ ]*", " ", bullet)       # join the wrapped lines only
    m = RE_RUN.match(flat)
    if not m:
        return None
    return {"run": m.group(1), "reported_status": m.group(2).strip(),
            "verdict": m.group(3), "model": m.group(4),
            "model_note": (m.group(5) or "").strip() or None,
            "blocking": m.group(6).strip() or None}


def convert_verdicts(text, out, instance="author@bi", ns_default="paper", pieces=None):
    """Review records from ``Drafts/verdicts.md``: per entry (a ``## <label> -- date``
    block, or a ``### `` pair inside one) ``reviews/<ns>/<id>/<pass>/A.md``, ``B.md``
    and ``decision.md`` (the rest of the entry, verbatim), plus ``_context.md`` for
    text before run A. An entry without two parseable run bullets goes verbatim into
    ``reviews/_unparsed.md``. Nothing is inferred that the ledger does not say: no
    run ids, statement hashes or modulo sets are invented."""
    pieces = pieces if pieces is not None else []
    pre, blocks = split_blocks(text)
    stats = collections.OrderedDict(blocks=len(blocks), entries=0, records=0, runs=0,
                                    unparsed=[], passes=[], verdicts=collections.Counter(),
                                    outcomes=collections.Counter())
    root = os.path.join(out, "reviews")
    written, unparsed = [], []
    hp = os.path.join(root, ns_default, "_ledger-header-%s.md" % instance)
    if pre.strip():
        ac.atomic_write(hp, piece_file([("Drafts/verdicts.md (%s), preamble" % instance,
                                         pre.strip())]))
        pieces.append(({"file": _rel(hp, out), "piece": 1}, pre.strip()))
        written.append(hp)
    unparsed_path = os.path.join(root, "_unparsed.md")
    used = set()
    for head, body, line in blocks:
        hm = RE_VHEAD.match(head)
        for ehead, sub, elines, eline in _entries(head, body, line):
            entry_text = "\n".join(elines).strip("\n")
            if not entry_text.strip():
                continue
            stats["entries"] += 1
            intro, bullets = split_bullets(elines)
            runs = [(b, parse_run(b)) for b in bullets[:2]]   # later "- run A adds ..." bullets are findings
            ok = (hm is not None and len(runs) == 2 and all(r for _b, r in runs)
                  and [r["run"] for _b, r in runs] == ["A", "B"]
                  and bullets[:2] == [runs[0][0], runs[1][0]])
            if not ok:
                why = ("heading not '<label> -- YYYY-MM-DD (note)'" if hm is None else
                       "not exactly two parseable run bullets (A then B) at the start")
                unparsed.append(("Drafts/verdicts.md (%s), line %d, entry %r: %s"
                                 % (instance, eline, ehead[:60], why), entry_text))
                pieces.append(({"file": _rel(unparsed_path, out), "piece": len(unparsed)},
                               entry_text))
                stats["unparsed"].append("line %d: %s (%s)" % (eline, ehead[:60], why))
                continue
            label, date, qual = hm.group(1), hm.group(2), hm.group(3)
            if sub:
                qual = sub
            subject = label if re.match(r"^[a-z0-9-]+:[a-z]+:", label) else \
                "%s:%s" % (ns_default, label)
            ns, cid = subject.split(":", 1)
            pname = date + ("-" + ac.slugify(qual, 40) if qual else "")
            folder = os.path.join(root, ns, ex.slug_id(cid), pname)
            n = 2
            while folder in used:
                folder = os.path.join(root, ns, ex.slug_id(cid), "%s-%d" % (pname, n))
                n += 1
            used.add(folder)
            pname = os.path.basename(folder)
            src = "Drafts/verdicts.md (%s), line %d" % (instance, eline)
            if intro.strip():
                cp = os.path.join(folder, "_context.md")
                ac.atomic_write(cp, piece_file([(src + ": text before run A", intro.strip())]))
                pieces.append(({"file": _rel(cp, out), "piece": 1}, intro.strip()))
                written.append(cp)
            for b, r in runs:
                meta = {"subject": subject, "pass": pname, "run": r["run"], "run_id": None,
                        "verdict": r["verdict"], "modulo": None, "model": r["model"],
                        "statement_hash": None, "blocking": r["blocking"], "ticket": None,
                        "agent": "paper:proof-verifier", "landed": date,
                        "reported_status": r["reported_status"],
                        "model_note": r["model_note"], "migrated": src}
                rp = os.path.join(folder, "%s.md" % r["run"])
                ac.atomic_write(rp, ac.write_frontmatter(
                    {k: meta[k] for k in REVIEW_KEYS},
                    "\n" + piece_file([(src + ": run %s, verbatim" % r["run"], b)])))
                pieces.append(({"file": _rel(rp, out), "piece": 1}, b))
                written.append(rp)
                stats["runs"] += 1
                stats["verdicts"]["%s (%s)" % (r["verdict"], r["model_note"] or "no note")] += 1
            # the rest of the entry, as written: everything after run B's bullet
            tail = entry_text[entry_text.index(runs[1][0]) + len(runs[1][0]):]
            tail = tail.strip("\n").rstrip()
            if tail.strip():
                om = RE_OUTCOME.match(tail)
                outcome = om.group(1).strip().rstrip(".") if om else None
                dmeta = {"subject": subject, "pass": pname, "outcome": outcome,
                         "runs": ["A", "B"], "decided": date,
                         "by": "%s /paper:verify (master-verifier)" % instance,
                         "migrated": src}
                dp = os.path.join(folder, "decision.md")
                ac.atomic_write(dp, ac.write_frontmatter(
                    {k: dmeta[k] for k in DECISION_KEYS},
                    "\n" + piece_file([(src + ": outcome, inputs and findings, verbatim",
                                        tail)])))
                pieces.append(({"file": _rel(dp, out), "piece": 1}, tail))
                written.append(dp)
                stats["outcomes"][outcome or "(no outcome line)"] += 1
            stats["records"] += 1
            stats["passes"].append("%s / %s" % (subject, pname))
    if unparsed:
        ac.atomic_write(unparsed_path, piece_file(unparsed))
        written.append(unparsed_path)
    return written, stats


# ----------------------------------------------------------------------------
# Verbatim pieces and the manifest (the generated views are rebuilt from these)
# ----------------------------------------------------------------------------

PIECE_MARK = "<!-- piece:%d %s -->"
RE_PIECE = re.compile(r"^<!-- piece:(\d+) [^\n]*-->\n\n", re.M)


def _rel(path, out):
    return os.path.relpath(path, out).replace("\\", "/")


def piece_file(pieces):
    """A file of verbatim pieces ``[(provenance, text)]``, each after its marker line."""
    return "\n".join("%s\n\n%s\n" % (PIECE_MARK % (n, " ".join(src.replace("--", "-").split())),
                                     text) for n, (src, text) in enumerate(pieces, 1))


def read_piece(path, n=1):
    """Piece ``n`` of a piece file (frontmatter allowed before the first marker)."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        text = fh.read().replace("\r\n", "\n")
    marks = list(RE_PIECE.finditer(text))
    for i, m in enumerate(marks):
        if int(m.group(1)) == n:
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            seg = text[m.end():end]
            suffix = "\n\n" if i + 1 < len(marks) else "\n"
            if not seg.endswith(suffix):
                raise ValueError("%s: piece %d is not terminated as written" % (path, n))
            return seg[:-len(suffix)]
    raise ValueError("%s has no piece %d" % (path, n))


def build_manifest(text, pieces, ledger, instance):
    """Locate each verbatim piece in ``text`` in order; the text between pieces is kept
    as ``glue`` (headings and blank lines). Returns ``(manifest, problems)``: a piece
    that cannot be found at or after the previous one is a problem. Every non-blank
    glue line is listed in ``glue_lines`` so the report can show nothing hides there."""
    text = text.replace("\r\n", "\n")
    segs, pos, problems, glue_lines = [], 0, [], []
    for ref, piece in pieces:
        i = text.find(piece, pos)
        if i < 0:
            problems.append("not found in order: %s" % json.dumps(ref, ensure_ascii=False))
            continue
        if i > pos:
            segs.append({"glue": text[pos:i]})
        segs.append(dict(ref))
        pos = i + len(piece)
    if pos < len(text):
        segs.append({"glue": text[pos:]})
    for s in segs:
        if "glue" in s:
            glue_lines += [ln for ln in s["glue"].split("\n") if ln.strip()]
    man = {"ledger": ledger, "instance": instance,
           "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
           "segments": segs, "glue_lines": glue_lines}
    return man, problems


def render_segment(home, seg):
    """The verbatim text of one manifest segment, read back from its record."""
    if "glue" in seg:
        return seg["glue"]
    if "card" in seg:
        _meta, body = cardlib.read_card(os.path.join(home, seg["card"]))
        t = cardlib.sections(body).get("## Ledger text", "")
        return t[seg.get("strip", 0):]
    return read_piece(os.path.join(home, seg["file"]), seg.get("piece", 1))


def render_manifest(home, manifest):
    return "".join(render_segment(home, s) for s in manifest["segments"])


# ----------------------------------------------------------------------------
# Stats and CLI
# ----------------------------------------------------------------------------

def stats_md(stats, related_n):
    s = stats
    lines = ["# ledger_split preview: statistics", "",
             "- blocks in sources.md: %d; cards written: %d; related-work files: %d"
             % (s["blocks"], s["cards"], related_n),
             "- cards naming a paper label (`used_by`): %d" % s["with_labels"],
             "- cards with validation errors: %d; with warnings: %d"
             % (s["errors"], s["warnings"]),
             "- blocks with no bibliography key (filed under `_unkeyed`): %s"
             % ("; ".join(s["unkeyed_blocks"]) or "none"),
             "- pinpoint collisions (second card suffixed -2): %s"
             % ("; ".join(s["collisions"]) or "none"),
             "- cards moved out of their block to the source their own text names: %s"
             % ("; ".join(s["reassigned"]) or "none"), "",
             "| read_from | cards |", "|---|---|"]
    lines += ["| %s | %d |" % kv for kv in sorted(s["read_from"].items())]
    lines += ["", "| verdict | cards |", "|---|---|"]
    lines += ["| %s | %d |" % kv for kv in sorted(s["verdict"].items())]
    lines += ["", "| quote check | cards |", "|---|---|"]
    lines += ["| %s | %d |" % kv for kv in sorted(s["quotes"].items())]
    lines += ["", "| key | cards |", "|---|---|"]
    lines += ["| %s | %d |" % kv for kv in sorted(s["per_key"].items())]
    return "\n".join(lines) + "\n"


def bib_keys_of(path):
    if not path or not os.path.isfile(path):
        return set()
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", fh.read()))


def guard_out(out, force):
    ws = ex.load_workspace_or_none()
    if force or not ws:
        return None
    for name, inst in ws["instances"].items():
        if ex.is_under(out, inst["home"]):
            return "%s lies in the home of %s; write to a copy (or pass --force)" % (out, name)
    return None


def manifest_path(out, instance, name):
    return os.path.join(out, "ledgers", instance, "_manifest-%s.json" % name)


def block_map(manifest):
    """``[(heading line(s), [record refs])]`` in ledger order, from a manifest: a glue
    line starting with ``#`` opens a block; the records after it belong to it."""
    out = [("(before the first heading)", [])]
    for s in manifest["segments"]:
        if "glue" in s:
            heads = [ln for ln in s["glue"].split("\n") if ln.startswith("#")]
            for h in heads:
                out.append((h, []))
            continue
        ref = s.get("card") or s.get("file")
        if s.get("piece", 1) != 1 or "_unparsed" in ref:
            ref = "%s (piece %d)" % (ref, s.get("piece", 1))
        out[-1][1].append(ref)
    return [b for b in out if b[1] or b[0] != "(before the first heading)"]


def report_md(results, sstats, vstats, rel_n, args):
    """The mapping report: counts, every block and the records it went to, what is
    unmapped, and every card's status."""
    L = ["# Ledger split: mapping report", "",
         "Generated by `expert/scripts/ledger_split.py` on %s from `%s` (instance %s)."
         % (ac.today(), os.path.dirname(os.path.abspath(args.sources)).replace("\\", "/"),
            args.instance),
         "The ledgers were read only; nothing in the author home was changed.", "",
         "## Counts", "",
         "| ledger | blocks | records | reproduced byte for byte from the records |",
         "|---|---|---|---|"]
    for name, r in results.items():
        L.append("| %s | %d | %d | %s |" % (name, r["blocks"], r["records"],
                                           "yes" if r["reproduced"] else "**no**"))
    L += ["",
          "- sources.md: %d cards (%d verified, %d unverified), %d block intros, "
          "%d under `_unkeyed`" % (
              sstats["cards"], sstats["status"].get("verified", 0),
              sstats["status"].get("unverified", 0), sstats["intros"],
              sstats["per_key"].get(cardlib.UNKEYED, 0)),
          "- quote check (MCP normaliser, against `<key>.src/` for a source read, else "
          "`<key>.txt`, then the other): %s" % ", ".join(
              "%s %d" % kv for kv in sorted(sstats["quotes"].items())),
          "- pinpoint collisions (later card suffixed `-2`): %s"
          % ("; ".join(sstats["collisions"]) or "none"),
          "- cards filed under another key than their block's (their own text names "
          "that source's files): %s" % ("; ".join(sstats["reassigned"]) or "none")]
    if vstats:
        L += ["- verdicts.md: %d entries, %d review records (%d run records), %d unparsed"
              % (vstats["entries"], vstats["records"], vstats["runs"],
                 len(vstats["unparsed"])),
              "- run verdicts: %s" % ", ".join("%s %d" % kv for kv in
                                                sorted(vstats["verdicts"].items())),
              "- outcomes: %s" % ", ".join("%s %d" % kv for kv in
                                            sorted(vstats["outcomes"].items()))]
    L += ["- related_work.md: %d files" % rel_n, "", "## Unmapped", ""]
    unm = []
    for name, r in results.items():
        unm += ["- %s: %s" % (name, p) for p in r["problems"]]
    if vstats:
        unm += ["- verdicts.md, kept verbatim in `reviews/_unparsed.md`: %s" % u
                for u in vstats["unparsed"]]
    L += unm or ["None: every piece of every ledger is in a record."]
    L += ["", "Text between records (the `glue` of the manifests) is only headings and "
          "blank lines; every non-blank glue line is listed here so nothing hides there.", ""]
    for name, r in results.items():
        L += ["### Glue lines of %s" % name, ""]
        L += ["    " + g for g in r["glue_lines"]] or ["(none)"]
        L.append("")
    L += ["## Blocks and their records", ""]
    for name, r in results.items():
        L += ["### %s" % name, ""]
        for head, refs in r["blocks_map"]:
            L.append("- `%s`" % head.replace("`", "'")[:160])
            L += ["  - `%s`" % x for x in refs]
        L.append("")
    L += ["## Card status", "",
          "`verified`: the ledger's quote was found in the cached text. `unverified`: it "
          "was not, or there is no quote or no text; the reason is on the card. No quote "
          "was altered.", "", "| card | status | reason |", "|---|---|---|"]
    for path, (st, why) in sorted(sstats["cards_by_status"].items()):
        L.append("| `%s` | %s | %s |" % (path, st, why.replace("|", "\\|")))
    return "\n".join(L) + "\n"


def main(argv=None):
    ex.utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sources", required=True)
    ap.add_argument("--related")
    ap.add_argument("--verdicts")
    ap.add_argument("--out", required=True)
    ap.add_argument("--library", help="library home for version lookups and quote checks "
                                      "(read-only)")
    ap.add_argument("--bib", help="references.bib, to recognise keys in headings")
    ap.add_argument("--instance", default="author@bi")
    ap.add_argument("--report-dir", help="where stats.json, stats.md and "
                                         "ledger-split-report.md go (default: --out)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    out = os.path.abspath(args.out)
    why = guard_out(out, args.force)
    if why:
        sys.stderr.write("ledger_split: %s\n" % why)
        return 2
    rdir = os.path.abspath(args.report_dir or out)
    results, texts, pieces = collections.OrderedDict(), {}, {}

    def read(p):
        with open(p, "r", encoding="utf-8", newline="") as fh:
            return fh.read().replace("\r\n", "\n")

    texts["sources.md"] = read(args.sources)
    pieces["sources.md"] = []
    written, stats = convert_sources(texts["sources.md"], out, args.library,
                                     bib_keys_of(args.bib), args.instance,
                                     pieces["sources.md"])
    counts = {"sources.md": (stats["blocks"], stats["cards"] + stats["intros"])}
    rel, vstats = [], None
    if args.related:
        texts["related_work.md"] = read(args.related)
        pieces["related_work.md"] = []
        rel = convert_related(texts["related_work.md"], out, args.instance,
                              pieces["related_work.md"])
        counts["related_work.md"] = (len(raw_blocks(texts["related_work.md"])), len(rel))
    if args.verdicts:
        texts["verdicts.md"] = read(args.verdicts)
        pieces["verdicts.md"] = []
        _vw, vstats = convert_verdicts(texts["verdicts.md"], out, args.instance,
                                       pieces=pieces["verdicts.md"])
        counts["verdicts.md"] = (vstats["blocks"], vstats["records"])
    ok = True
    for name, text in texts.items():
        man, problems = build_manifest(text, pieces[name], "Drafts/" + name, args.instance)
        mp = manifest_path(out, args.instance, os.path.splitext(name)[0])
        ac.atomic_write(mp, json.dumps(man, indent=1, ensure_ascii=False) + "\n")
        try:
            again = render_manifest(out, man)
        except (OSError, ValueError, ac.AcademyError) as exc:
            again, problems = None, problems + ["render failed: %s" % exc]
        same = again == text
        ok = ok and same and not problems
        results[name] = {"blocks": counts[name][0], "records": counts[name][1],
                         "reproduced": same, "problems": problems,
                         "glue_lines": man["glue_lines"], "blocks_map": block_map(man),
                         "manifest": _rel(mp, out)}
    js = {k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in stats.items()}
    js["related_files"] = len(rel)
    js["cards_in_order"] = [_rel(p, out) for p in written]
    js["verdicts"] = {k: (dict(v) if isinstance(v, collections.Counter) else v)
                      for k, v in (vstats or {}).items()}
    js["ledgers"] = {k: {kk: vv for kk, vv in v.items() if kk != "blocks_map"}
                     for k, v in results.items()}
    ac.atomic_write(os.path.join(rdir, "stats.json"), json.dumps(js, indent=2,
                                                                 ensure_ascii=False) + "\n")
    ac.atomic_write(os.path.join(rdir, "stats.md"), stats_md(stats, len(rel)))
    ac.atomic_write(os.path.join(rdir, "ledger-split-report.md"),
                    report_md(results, stats, vstats, len(rel), args))
    print("cards: %d from %d blocks; related-work files: %d; review records: %d; "
          "reproduced: %s; out: %s"
          % (stats["cards"], stats["blocks"], len(rel), (vstats or {}).get("records", 0),
             ", ".join("%s %s" % (k, "yes" if v["reproduced"] else "NO")
                       for k, v in results.items()), out.replace("\\", "/")))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
